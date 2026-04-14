import { test, expect } from "./fixtures";
import { SettingsPage } from "./pages/settings.page";

test.describe("Settings Page", () => {
  let settings: SettingsPage;

  test.beforeEach(async ({ page }) => {
    settings = new SettingsPage(page);
    await settings.goto();
  });

  test("page loads and shows all major sections", async () => {
    for (const section of [
      "Server",
      "AutoQueue",
      "Staging Directory",
      "Archive Extraction",
      "Integrity Check",
      "File Discovery",
      "Connections",
      "Logging",
      "Other Settings",
      "Notifications",
      "Integrations",
    ]) {
      await expect(settings.getSection(section)).toBeVisible();
    }
    // Advanced LFTP is collapsed by default but its header should still be visible
    const advancedHeader = settings.page.locator(
      "h3.card-header.collapsible-header",
      { hasText: "Advanced LFTP" }
    );
    await expect(advancedHeader).toBeVisible();
  });

  test("text field change saves to backend", async ({ apiGet, apiSetConfig }) => {
    const configBefore = await apiGet("/server/config/get");
    const originalAddress = configBefore.lftp.remote_address;

    try {
      const field = settings.getTextInput("Server Address");
      await field.clear();
      const testValue = "e2e-test-server";
      await field.fill(testValue);

      // Poll the API until the value is saved
      await expect
        .poll(
          async () => {
            const config = await apiGet("/server/config/get");
            return config.lftp.remote_address;
          },
          { timeout: 5000 }
        )
        .toBe(testValue);
    } finally {
      await apiSetConfig("lftp", "remote_address", originalAddress ?? "");
    }
  });

  test("checkbox toggle saves to backend", async ({ apiGet }) => {
    const checkbox = settings.getCheckbox("Verbose LFTP Logging");
    const wasBefore = await checkbox.isChecked();
    const expected = !wasBefore;

    await checkbox.click();

    try {
      // Poll the API until the value is saved
      await expect
        .poll(
          async () => {
            const config = await apiGet("/server/config/get");
            return config.general.verbose;
          },
          { timeout: 5000 }
        )
        .toBe(expected);
    } finally {
      // Toggle back to restore original state
      await checkbox.click();

      await expect
        .poll(
          async () => {
            const config = await apiGet("/server/config/get");
            return config.general.verbose;
          },
          { timeout: 5000 }
        )
        .toBe(wasBefore);
    }
  });

  test("password field masks input", async () => {
    const field = settings.getTextInput("Server Password");
    await expect(field).toHaveAttribute("type", "password");
  });

  test("select dropdown changes value and saves to backend", async ({
    apiGet,
  }) => {
    // Read the current value so we can restore it
    const configBefore = await apiGet("/server/config/get");
    const originalFormat = configBefore.logging.log_format;

    const select = settings.getSelect("Log Format");

    try {
      await select.selectOption("json");
      // Poll the API until the value is saved
      await expect
        .poll(
          async () => {
            const config = await apiGet("/server/config/get");
            return config.logging.log_format;
          },
          { timeout: 5000 }
        )
        .toBe("json");
    } finally {
      // Restore the original log format
      await select.selectOption(String(originalFormat));
      await expect
        .poll(
          async () => {
            const config = await apiGet("/server/config/get");
            return config.logging.log_format;
          },
          { timeout: 5000 }
        )
        .toBe(originalFormat);
    }
  });

  test("Advanced LFTP section is collapsed by default", async ({ page }) => {
    const header = page.locator("h3.card-header.collapsible-header", {
      hasText: "Advanced LFTP",
    });
    const card = header.locator("xpath=..");
    // When collapsed, Angular @if removes the card-body from the DOM
    const collapseBody = card.locator("app-option");
    await expect(collapseBody).toHaveCount(0);
  });

  test("clicking Advanced LFTP header expands the section", async ({
    page,
  }) => {
    await settings.expandSection("Advanced LFTP");

    // After expanding, the card-body with options should be visible
    const header = page.locator("h3.card-header.collapsible-header", {
      hasText: "Advanced LFTP",
    });
    const body = header.locator("xpath=..").locator(".card-body");
    await expect(body).toBeVisible();
  });

  test("expanded Advanced LFTP section shows all 7 advanced options", async ({
    page,
  }) => {
    await settings.expandSection("Advanced LFTP");

    const section = settings.getSection("Advanced LFTP");
    const options = section.locator("app-option");
    await expect(options).toHaveCount(7);
  });

  test("Server Directory field is disabled when path pairs exist", async ({
    apiFetch,
  }) => {
    // Create a path pair via API
    const pairName = `temp-pair-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const res = await apiFetch("/server/pathpairs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: pairName,
        remote_path: "/remote/test",
        local_path: "/local/test",
        enabled: true,
      }),
    });
    expect(res.ok).toBe(true);
    const pair = await res.json();

    try {
      await settings.goto();
      const serverDir = settings.getTextInput("Server Directory");
      await expect(serverDir).toBeDisabled();
    } finally {
      // Always clean up the pair
      if (pair?.id) {
        const del = await apiFetch(`/server/pathpairs/${pair.id}`, { method: "DELETE" });
        expect(del.ok, `Failed to delete temp pair ${pair.id}: ${del.status}`).toBe(true);
      }
    }
  });

  test("restart notification appears after config change", async ({ apiGet, apiSetConfig }) => {
    const configBefore = await apiGet("/server/config/get");
    const originalAddress = configBefore.lftp.remote_address;

    try {
      const field = settings.getTextInput("Server Address");
      await field.clear();
      await field.fill("trigger-restart-notice-" + Date.now());

      const notification = settings.getRestartNotification();
      await expect(notification).toBeVisible({ timeout: 5000 });
    } finally {
      await apiSetConfig("lftp", "remote_address", originalAddress ?? "");
    }
  });

  test("Web GUI Port field shows current port value", async ({ apiGet }) => {
    const config = await apiGet("/server/config/get");
    const portField = settings.getTextInput("Web GUI Port");
    await expect(portField).toBeVisible();
    await expect(portField).toHaveValue(String(config.web.port));
  });

  test("API Key field is a password field", async () => {
    const otherSettings = settings.getSection("Other Settings");
    const field = otherSettings
      .locator("app-option", { hasText: "API Key" })
      .locator("input[type='text'], input[type='password']");
    await expect(field).toHaveAttribute("type", "password");
  });
});
