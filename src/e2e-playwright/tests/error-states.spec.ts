import { test, expect } from "./fixtures";

test.describe("Error States — Header Notifications", () => {
  // The noEnabledPairs notification only appears when the server is fully
  // configured and running (status.server.up === true).  CI containers start
  // with incomplete config so the server reports "not up" and the controller
  // never evaluates pair state.  Skip these tests when the server is down.

  /**
   * Helper: disable all path pairs and ensure at least one disabled pair exists.
   *
   * The backend only sets `no_enabled_pairs = true` when there are path pairs
   * configured but none are enabled.  If no pairs exist at all, it falls through
   * to the legacy single-path mode.  So every test that expects the
   * "no enabled pairs" notification must guarantee a disabled pair exists.
   *
   * Returns cleanup info so the caller can restore state in a `finally` block.
   */
  async function disableAllPairs(apiFetch: (path: string, init?: RequestInit) => Promise<Response>) {
    const res = await apiFetch("/server/pathpairs");
    expect(res.ok, `GET /server/pathpairs failed: ${res.status}`).toBe(true);
    const pairs = await res.json();
    const originalStates: { id: string; enabled: boolean }[] = [];

    for (const pair of pairs) {
      originalStates.push({ id: pair.id, enabled: pair.enabled });
      if (pair.enabled) {
        const updateRes = await apiFetch(`/server/pathpairs/${pair.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: false }),
        });
        expect(updateRes.ok, `PUT pathpairs/${pair.id} failed: ${updateRes.status}`).toBe(true);
      }
    }

    // If no pairs exist at all, create a disabled one so the backend reports
    // noEnabledPairs=true rather than falling through to legacy single-path mode.
    let tempPairId: string | null = null;
    if (pairs.length === 0) {
      const createRes = await apiFetch("/server/pathpairs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: "e2e-disabled-pair",
          remote_path: "/remote/e2e",
          local_path: "/local/e2e",
          enabled: false,
        }),
      });
      expect(createRes.ok, `POST /server/pathpairs failed: ${createRes.status}`).toBe(true);
      const created = await createRes.json();
      tempPairId = created.id;
    }

    return { originalStates, tempPairId };
  }

  /**
   * Helper: restore original pair states and clean up any temp pair.
   */
  async function restorePairs(
    apiFetch: (path: string, init?: RequestInit) => Promise<Response>,
    originalStates: { id: string; enabled: boolean }[],
    tempPairId: string | null,
  ) {
    if (tempPairId) {
      await apiFetch(`/server/pathpairs/${tempPairId}`, { method: "DELETE" });
    }
    for (const state of originalStates) {
      if (state.enabled) {
        await apiFetch(`/server/pathpairs/${state.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: true }),
        });
      }
    }
  }

  test("no enabled pairs shows warning notification", async ({
    page,
    apiGet,
    apiFetch,
    waitForStream,
  }) => {
    const status = await apiGet("/server/status");
    test.skip(!status.server.up, "Server is not fully configured — noEnabledPairs notification requires server.up");

    const { originalStates, tempPairId } = await disableAllPairs(apiFetch);

    try {
      await page.goto("/dashboard");
      await waitForStream(page);

      const notification = page.locator("#header .alert", {
        hasText: /path pairs are disabled/i,
      });
      await expect(notification).toBeVisible({ timeout: 15_000 });
      await expect(notification).toHaveClass(/alert-warning/);
    } finally {
      await restorePairs(apiFetch, originalStates, tempPairId);
    }
  });

  test("no enabled pairs notification text matches expected string", async ({
    page,
    apiGet,
    apiFetch,
    waitForStream,
  }) => {
    const status = await apiGet("/server/status");
    test.skip(!status.server.up, "Server is not fully configured — noEnabledPairs notification requires server.up");

    const { originalStates, tempPairId } = await disableAllPairs(apiFetch);

    try {
      await page.goto("/dashboard");
      await waitForStream(page);

      const notification = page.locator("#header .alert", {
        hasText: /path pairs are disabled/i,
      });
      await expect(notification).toBeVisible({ timeout: 15_000 });
      await expect(notification).toContainText(
        "Enable a pair in Settings to start syncing"
      );
    } finally {
      await restorePairs(apiFetch, originalStates, tempPairId);
    }
  });

  test("restart notification appears after config change on settings page", async ({
    page,
    waitForStream,
    apiGet,
    apiSetConfig,
  }) => {
    await page.goto("/settings");
    await waitForStream(page);

    const configBefore = await apiGet("/server/config/get");
    const originalAddress = configBefore.lftp.remote_address;

    try {
      const field = page
        .locator("app-option", { hasText: "Server Address" })
        .locator("input[type='text'], input[type='password']");
      await field.clear();
      await field.fill("trigger-restart-" + Date.now());

      // The restart notification should appear in the header
      const notification = page.locator("#header .alert", {
        hasText: /restart/i,
      });
      await expect(notification).toBeVisible({ timeout: 5000 });
    } finally {
      await apiSetConfig("lftp", "remote_address", originalAddress ?? "");
    }
  });

  test("notification has correct alert level styling", async ({
    page,
    apiGet,
    apiFetch,
    waitForStream,
  }) => {
    const status = await apiGet("/server/status");
    test.skip(!status.server.up, "Server is not fully configured — noEnabledPairs notification requires server.up");

    const { originalStates, tempPairId } = await disableAllPairs(apiFetch);

    try {
      await page.goto("/dashboard");
      await waitForStream(page);

      // The no-enabled-pairs notification should be a warning (not danger or info)
      const notification = page.locator("#header .alert", {
        hasText: /path pairs are disabled/i,
      });
      await expect(notification).toBeVisible({ timeout: 10_000 });
      await expect(notification).toHaveClass(/alert-warning/);
      await expect(notification).not.toHaveClass(/alert-danger/);
      await expect(notification).not.toHaveClass(/alert-info/);
    } finally {
      await restorePairs(apiFetch, originalStates, tempPairId);
    }
  });

  test("re-enabling a pair clears the no-enabled-pairs warning", async ({
    page,
    apiGet,
    apiFetch,
    waitForStream,
  }) => {
    const status = await apiGet("/server/status");
    test.skip(!status.server.up, "Server is not fully configured — noEnabledPairs notification requires server.up");
    // Create a disabled pair for this test
    const pairName = `e2e-reenable-${Date.now()}`;
    const createRes = await apiFetch("/server/pathpairs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: pairName,
        remote_path: "/remote/reenable",
        local_path: "/local/reenable",
        enabled: false,
      }),
    });
    expect(createRes.ok, `POST /server/pathpairs failed: ${createRes.status}`).toBe(true);
    const createdPair = await createRes.json();

    // Also disable any other enabled pairs
    const listRes = await apiFetch("/server/pathpairs");
    expect(listRes.ok, `GET /server/pathpairs failed: ${listRes.status}`).toBe(true);
    const allPairs = await listRes.json();
    const originalStates: { id: string; enabled: boolean }[] = [];
    for (const pair of allPairs) {
      if (pair.id !== createdPair.id) {
        originalStates.push({ id: pair.id, enabled: pair.enabled });
        if (pair.enabled) {
          const updateRes = await apiFetch(`/server/pathpairs/${pair.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ enabled: false }),
          });
          expect(updateRes.ok, `PUT pathpairs/${pair.id} failed: ${updateRes.status}`).toBe(true);
        }
      }
    }

    try {
      await page.goto("/dashboard");
      await waitForStream(page);

      // Warning should be visible
      const notification = page.locator("#header .alert", {
        hasText: /path pairs are disabled/i,
      });
      await expect(notification).toBeVisible({ timeout: 10_000 });

      // Re-enable the pair via API
      const enableRes = await apiFetch(`/server/pathpairs/${createdPair.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: true }),
      });
      expect(enableRes.ok, `PUT pathpairs/${createdPair.id} failed: ${enableRes.status}`).toBe(true);

      // The warning should disappear (SSE pushes status updates)
      await expect(notification).not.toBeVisible({ timeout: 10_000 });
    } finally {
      // Clean up: delete the test pair and restore others
      await apiFetch(`/server/pathpairs/${createdPair.id}`, {
        method: "DELETE",
      });
      for (const state of originalStates) {
        if (state.enabled) {
          await apiFetch(`/server/pathpairs/${state.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ enabled: true }),
          });
        }
      }
    }
  });
});
