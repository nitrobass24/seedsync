import { test, expect } from "./fixtures";
import { IntegrationsPage } from "./pages/integrations.page";

// Wrap a fixture-setup API call so failures surface as "fixture creation
// failed" instead of cascading into confusing UI assertion failures.
async function expectFixtureOk(res: Response, label: string): Promise<void> {
  if (!res.ok) {
    throw new Error(`fixture creation failed: ${label} → ${res.status} ${res.statusText}`);
  }
}

test.describe("Integrations CRUD", () => {
  let integrations: IntegrationsPage;

  // Clean up all integrations before each test for a clean slate. Fail fast
  // on any API error so the test stops with a clear message instead of
  // proceeding against stale or unknown state.
  test.beforeEach(async ({ page, apiFetch }) => {
    const res = await apiFetch("/server/integrations");
    if (!res.ok) {
      throw new Error(`GET /server/integrations failed: ${res.status} ${res.statusText}`);
    }
    const instances = await res.json();
    for (const inst of instances) {
      const del = await apiFetch(`/server/integrations/${inst.id}`, {
        method: "DELETE",
      });
      if (!del.ok) {
        throw new Error(
          `DELETE /server/integrations/${inst.id} failed: ${del.status} ${del.statusText}`,
        );
      }
    }

    integrations = new IntegrationsPage(page);
    await integrations.goto();
  });

  // Clean up after each test. Same fail-fast contract as beforeEach so
  // teardown failures surface as test failures instead of being swallowed.
  test.afterEach(async ({ apiFetch }) => {
    const res = await apiFetch("/server/integrations");
    if (!res.ok) {
      throw new Error(`GET /server/integrations failed during cleanup: ${res.status} ${res.statusText}`);
    }
    const instances = await res.json();
    for (const inst of instances) {
      const del = await apiFetch(`/server/integrations/${inst.id}`, {
        method: "DELETE",
      });
      if (!del.ok) {
        throw new Error(
          `DELETE /server/integrations/${inst.id} failed during cleanup: ${del.status} ${del.statusText}`,
        );
      }
    }
  });

  test("empty state shows 'No integrations' message and add buttons", async () => {
    await expect(integrations.emptyState).toBeVisible();
    await expect(integrations.emptyState).toContainText("No integrations");
    await expect(integrations.addSonarrButton).toBeVisible();
    await expect(integrations.addRadarrButton).toBeVisible();
  });

  test("clicking + Sonarr opens add form with Sonarr pre-selected", async () => {
    await integrations.addSonarrButton.click();
    await expect(integrations.instanceForm).toBeVisible();

    const kindSelect = integrations.instanceForm.locator("select");
    await expect(kindSelect).toHaveValue("sonarr");
  });

  test("clicking + Radarr opens add form with Radarr pre-selected", async () => {
    await integrations.addRadarrButton.click();
    await expect(integrations.instanceForm).toBeVisible();

    const kindSelect = integrations.instanceForm.locator("select");
    await expect(kindSelect).toHaveValue("radarr");
  });

  test("save with empty name shows validation error", async () => {
    await integrations.addSonarrButton.click();
    await integrations.fillForm({
      url: "http://localhost:8989",
      apiKey: "test-key",
    });
    await integrations.clickSave();

    await expect(integrations.errorMessage).toBeVisible();
    await expect(integrations.errorMessage).toContainText("Name is required");
  });

  test("fill and save creates integration visible in list and API", async ({
    apiFetch,
  }) => {
    await integrations.addSonarrButton.click();
    await integrations.fillForm({
      name: "E2E Sonarr",
      url: "http://localhost:8989",
      apiKey: "test-api-key-123",
    });
    await integrations.clickSave();

    // Form should close
    await expect(integrations.instanceForm).not.toBeVisible({
      timeout: 10_000,
    });

    // Instance should appear in the list
    const row = integrations.getInstanceByName("E2E Sonarr");
    await expect(row).toBeVisible({ timeout: 10_000 });

    // Verify via API
    await expect
      .poll(
        async () => {
          const res = await apiFetch("/server/integrations");
          if (!res.ok) return undefined;
          const instances = await res.json();
          return instances.find(
            (i: { name: string }) => i.name === "E2E Sonarr"
          );
        },
        { timeout: 5000 }
      )
      .toEqual(
        expect.objectContaining({
          name: "E2E Sonarr",
          kind: "sonarr",
          url: "http://localhost:8989",
        })
      );
  });

  test("edit populates form and save updates the instance", async ({
    apiFetch,
  }) => {
    // Create an integration via API
    const created = await apiFetch("/server/integrations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "Edit Me",
        kind: "sonarr",
        url: "http://localhost:8989",
        api_key: "old-key",
        enabled: true,
      }),
    });
    await expectFixtureOk(created, 'POST /server/integrations (Edit Me)');

    await integrations.goto();

    const row = integrations.getInstanceByName("Edit Me");
    await row.waitFor({ timeout: 10_000 });
    await integrations.getEditButton(row).click();

    // Form should be visible with existing values
    await expect(integrations.instanceForm).toBeVisible();
    const nameInput = integrations.instanceForm.locator(
      'label:has-text("Name") input'
    );
    await expect(nameInput).toHaveValue("Edit Me");

    // Update the URL
    await integrations.fillForm({
      url: "http://localhost:7878",
    });
    await integrations.clickSave();

    // Verify via API
    await expect
      .poll(
        async () => {
          const res = await apiFetch("/server/integrations");
          if (!res.ok) return undefined;
          const instances = await res.json();
          return instances.find(
            (i: { name: string }) => i.name === "Edit Me"
          );
        },
        { timeout: 5000 }
      )
      .toEqual(
        expect.objectContaining({
          url: "http://localhost:7878",
        })
      );
  });

  test("single-click delete shows confirmation state", async ({
    apiFetch,
  }) => {
    // Create an integration via API
    const created = await apiFetch("/server/integrations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "Confirm Delete",
        kind: "radarr",
        url: "http://localhost:7878",
        api_key: "key",
        enabled: true,
      }),
    });
    await expectFixtureOk(created, 'POST /server/integrations (Confirm Delete)');

    await integrations.goto();

    const row = integrations.getInstanceByName("Confirm Delete");
    await row.waitFor({ timeout: 10_000 });
    const deleteBtn = integrations.getDeleteButton(row);

    // First click — should enter confirmation state
    await deleteBtn.click();
    await expect(deleteBtn).toContainText("Confirm?");
    await expect(deleteBtn).toHaveClass(/confirming/);
  });

  test("double-click delete removes the integration", async ({
    apiFetch,
  }) => {
    // Create an integration via API
    const created = await apiFetch("/server/integrations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "Delete Me",
        kind: "sonarr",
        url: "http://localhost:8989",
        api_key: "key",
        enabled: true,
      }),
    });
    await expectFixtureOk(created, 'POST /server/integrations (Delete Me)');

    await integrations.goto();

    const row = integrations.getInstanceByName("Delete Me");
    await row.waitFor({ timeout: 10_000 });
    const deleteBtn = integrations.getDeleteButton(row);

    // First click — confirmation
    await deleteBtn.click();
    await expect(deleteBtn).toContainText("Confirm?");

    // Second click — actual delete
    await deleteBtn.click();

    // Row should disappear
    await expect(row).not.toBeVisible({ timeout: 5000 });

    // Verify via API. Throw on a non-OK response so the poll keeps
    // retrying — returning undefined here would falsely satisfy
    // toBeUndefined() and mask a real API failure.
    await expect
      .poll(
        async () => {
          const res = await apiFetch("/server/integrations");
          if (!res.ok) {
            throw new Error(`GET /server/integrations failed: ${res.status} ${res.statusText}`);
          }
          const instances = await res.json();
          return instances.find(
            (i: { name: string }) => i.name === "Delete Me"
          );
        },
        { timeout: 5000 }
      )
      .toBeUndefined();
  });

  test("Test Connection button shows result", async ({ apiFetch }) => {
    // Create an integration with a URL that will likely fail connection
    const created = await apiFetch("/server/integrations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "Test Conn",
        kind: "sonarr",
        url: "http://localhost:19999",
        api_key: "bad-key",
        enabled: true,
      }),
    });
    await expectFixtureOk(created, 'POST /server/integrations (Test Conn)');

    await integrations.goto();

    const row = integrations.getInstanceByName("Test Conn");
    await row.waitFor({ timeout: 10_000 });

    const testBtn = integrations.getTestButton(row);
    await testBtn.click();

    // Button should show "Testing..." while in progress
    // Then a result should appear (success or failure)
    const result = integrations.getTestResult(row);
    await expect(result).toBeVisible({ timeout: 15_000 });
    // The result should have either success or failure styling
    const resultText = await result.textContent();
    expect(resultText?.trim().length).toBeGreaterThan(0);
  });

  test("enable/disable toggle updates via API", async ({ apiFetch }) => {
    // Create an enabled integration
    const created = await apiFetch("/server/integrations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "Toggle Me",
        kind: "sonarr",
        url: "http://localhost:8989",
        api_key: "key",
        enabled: true,
      }),
    });
    await expectFixtureOk(created, 'POST /server/integrations (Toggle Me)');

    await integrations.goto();

    const row = integrations.getInstanceByName("Toggle Me");
    await row.waitFor({ timeout: 10_000 });
    const toggle = integrations.getEnabledToggle(row);

    // Should start checked (enabled)
    await expect(toggle).toBeChecked();

    // Toggle off
    await toggle.click();

    // Poll API until disabled
    await expect
      .poll(
        async () => {
          const res = await apiFetch("/server/integrations");
          if (!res.ok) return undefined;
          const instances = await res.json();
          const inst = instances.find(
            (i: { name: string }) => i.name === "Toggle Me"
          );
          return inst?.enabled;
        },
        { timeout: 5000 }
      )
      .toBe(false);
  });

  test("cancel button closes the add form without creating", async ({
    apiFetch,
  }) => {
    await integrations.addSonarrButton.click();
    await expect(integrations.instanceForm).toBeVisible();

    await integrations.fillForm({
      name: "Should Not Exist",
      url: "http://localhost:8989",
    });
    await integrations.clickCancel();

    // Form should close
    await expect(integrations.instanceForm).not.toBeVisible();

    // Verify nothing was created. Fail loudly if the GET itself fails so
    // we don't get a false-positive (an empty list always satisfies the
    // "Should Not Exist" check).
    const res = await apiFetch("/server/integrations");
    if (!res.ok) {
      throw new Error(`GET /server/integrations failed: ${res.status} ${res.statusText}`);
    }
    const instances = await res.json();
    expect(
      instances.find((i: { name: string }) => i.name === "Should Not Exist")
    ).toBeUndefined();
  });
});
