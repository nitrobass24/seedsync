import { test as base, expect, type Page } from "@playwright/test";

/**
 * Extended test fixture that provides helpers for interacting with the
 * SeedSync backend. Tests run against a live Docker container at BASE_URL.
 *
 * The container must be started before running tests:
 *   make run   (or docker compose -f docker-compose.dev.yml up -d)
 */
export const test = base.extend<{
  /** The base URL of the SeedSync instance */
  appUrl: string;
  /** Helper to wait for the SSE stream to connect and deliver initial data */
  waitForStream: (page: Page) => Promise<void>;
  /** Helper to GET a JSON API endpoint */
  apiGet: (path: string) => Promise<any>;
  /** Helper to set a config value via the API */
  apiSetConfig: (section: string, key: string, value: string) => Promise<void>;
  /** Helper to make API fetch requests with proper CSRF Origin header */
  apiFetch: (path: string, init?: RequestInit) => Promise<Response>;
}>({
  appUrl: async ({ baseURL }, use) => {
    await use(baseURL || "http://localhost:8800");
  },

  waitForStream: async ({}, use) => {
    await use(async (page: Page) => {
      // Wait for the Angular app to render by checking for sidebar nav links.
      // These are rendered after the app bootstraps and the SSE stream connects.
      await page.waitForSelector('a[href="/dashboard"]', { timeout: 15_000 });
    });
  },

  apiGet: async ({ appUrl }, use) => {
    await use(async (path: string) => {
      const res = await fetch(`${appUrl}${path}`, {
        headers: { Origin: appUrl },
      });
      if (!res.ok) throw new Error(`API ${path} returned ${res.status}`);
      return res.json();
    });
  },

  apiSetConfig: async ({ appUrl }, use) => {
    await use(async (section: string, key: string, value: string) => {
      const encoded = encodeURIComponent(encodeURIComponent(value || "__empty__"));
      const res = await fetch(
        `${appUrl}/server/config/set/${section}/${key}/${encoded}`
      );
      if (!res.ok) throw new Error(`Config set failed: ${res.status}`);
    });
  },

  apiFetch: async ({ appUrl }, use) => {
    await use(async (path: string, init?: RequestInit) => {
      const headers = new Headers(init?.headers);
      // Always include Origin header for CSRF validation
      if (!headers.has("Origin")) {
        headers.set("Origin", appUrl);
      }
      return fetch(`${appUrl}${path}`, { ...init, headers });
    });
  },
});

export { expect };
