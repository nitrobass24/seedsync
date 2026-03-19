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
}>({
  appUrl: async ({ baseURL }, use) => {
    await use(baseURL || "http://localhost:8800");
  },

  waitForStream: async ({ appUrl }, use) => {
    await use(async (page: Page) => {
      // Wait for the Angular app to connect to the SSE stream and receive
      // the initial model data. The file list renders after model-init.
      // We detect this by waiting for the stream-connected class or for
      // the file list to be present.
      await page.waitForFunction(
        () => {
          // The app sets a connected flag that enables buttons
          const restartBtn = document.querySelector(
            '[data-testid="restart-btn"], .sidebar-restart'
          );
          return restartBtn && !restartBtn.hasAttribute("disabled");
        },
        { timeout: 15_000 }
      );
    });
  },

  apiGet: async ({ appUrl }, use) => {
    await use(async (path: string) => {
      const res = await fetch(`${appUrl}${path}`);
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
});

export { expect };
