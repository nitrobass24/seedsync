import { test, expect } from "./fixtures";

test.describe("Error States — Header Notifications", () => {
  test("no enabled pairs shows warning notification", async ({
    page,
    apiFetch,
    waitForStream,
  }) => {
    // Disable all existing path pairs
    const res = await apiFetch("/server/pathpairs");
    const pairs = res.ok ? await res.json() : [];
    const originalStates: { id: string; enabled: boolean }[] = [];

    for (const pair of pairs) {
      originalStates.push({ id: pair.id, enabled: pair.enabled });
      if (pair.enabled) {
        await apiFetch(`/server/pathpairs/${pair.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: false }),
        });
      }
    }

    try {
      await page.goto("/dashboard");
      await waitForStream(page);

      // The header should show the "no enabled pairs" warning
      const notification = page.locator("#header .alert", {
        hasText: /path pairs are disabled/i,
      });
      await expect(notification).toBeVisible({ timeout: 10_000 });
      await expect(notification).toHaveClass(/alert-warning/);
    } finally {
      // Restore original enabled states
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

  test("no enabled pairs notification text matches expected string", async ({
    page,
    apiFetch,
    waitForStream,
  }) => {
    // Disable all existing path pairs
    const res = await apiFetch("/server/pathpairs");
    const pairs = res.ok ? await res.json() : [];
    const originalStates: { id: string; enabled: boolean }[] = [];

    for (const pair of pairs) {
      originalStates.push({ id: pair.id, enabled: pair.enabled });
      if (pair.enabled) {
        await apiFetch(`/server/pathpairs/${pair.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: false }),
        });
      }
    }

    try {
      // If no pairs exist at all, create a disabled one so the controller
      // reports noEnabledPairs=true rather than showing a different state
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
        if (createRes.ok) {
          const created = await createRes.json();
          tempPairId = created.id;
        }
      }

      await page.goto("/dashboard");
      await waitForStream(page);

      const notification = page.locator("#header .alert", {
        hasText: /path pairs are disabled/i,
      });
      await expect(notification).toBeVisible({ timeout: 10_000 });
      await expect(notification).toContainText(
        "Enable a pair in Settings to start syncing"
      );

      // Clean up temp pair
      if (tempPairId) {
        await apiFetch(`/server/pathpairs/${tempPairId}`, {
          method: "DELETE",
        });
      }
    } finally {
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
      const notification = page.locator(".alert", {
        hasText: /restart/i,
      });
      await expect(notification).toBeVisible({ timeout: 5000 });
    } finally {
      await apiSetConfig("lftp", "remote_address", originalAddress ?? "");
    }
  });

  test("notification has correct alert level styling", async ({
    page,
    apiFetch,
    waitForStream,
  }) => {
    // Disable all path pairs to trigger the warning notification
    const res = await apiFetch("/server/pathpairs");
    const pairs = res.ok ? await res.json() : [];
    const originalStates: { id: string; enabled: boolean }[] = [];

    for (const pair of pairs) {
      originalStates.push({ id: pair.id, enabled: pair.enabled });
      if (pair.enabled) {
        await apiFetch(`/server/pathpairs/${pair.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: false }),
        });
      }
    }

    let tempPairId: string | null = null;
    if (pairs.length === 0) {
      const createRes = await apiFetch("/server/pathpairs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: "e2e-alert-level-pair",
          remote_path: "/remote/e2e",
          local_path: "/local/e2e",
          enabled: false,
        }),
      });
      if (createRes.ok) {
        const created = await createRes.json();
        tempPairId = created.id;
      }
    }

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
  });

  test("re-enabling a pair clears the no-enabled-pairs warning", async ({
    page,
    apiFetch,
    waitForStream,
  }) => {
    // Ensure we have at least one pair, disabled
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
    expect(createRes.ok).toBe(true);
    const createdPair = await createRes.json();

    // Also disable any other enabled pairs
    const listRes = await apiFetch("/server/pathpairs");
    const allPairs = listRes.ok ? await listRes.json() : [];
    const originalStates: { id: string; enabled: boolean }[] = [];
    for (const pair of allPairs) {
      if (pair.id !== createdPair.id) {
        originalStates.push({ id: pair.id, enabled: pair.enabled });
        if (pair.enabled) {
          await apiFetch(`/server/pathpairs/${pair.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ enabled: false }),
          });
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
      await apiFetch(`/server/pathpairs/${createdPair.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: true }),
      });

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
