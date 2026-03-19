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
      "Connections",
      "AutoQueue",
      "Advanced LFTP",
    ]) {
      await expect(settings.getSection(section)).toBeVisible();
    }
  });

  test("text field change saves to backend", async ({ page, apiGet }) => {
    const field = settings.getTextInput("Server Address");
    await field.clear();
    const testValue = "test-server-" + Date.now();
    await field.fill(testValue);

    // Wait for debounce to fire and save
    await page.waitForTimeout(1500);

    const config = await apiGet("/server/config/get");
    expect(config.lftp.remote_address).toBe(testValue);
  });

  test("checkbox toggle saves to backend", async ({ page, apiGet }) => {
    const checkbox = settings.getCheckbox("Enable Debug");
    const wasBefore = await checkbox.isChecked();

    await checkbox.click();
    await page.waitForTimeout(1500);

    const config = await apiGet("/server/config/get");
    const expected = !wasBefore;
    expect(config.general.debug).toBe(expected);

    // Toggle back to restore original state
    await checkbox.click();
    await page.waitForTimeout(1500);
  });

  test("password field masks input", async () => {
    const field = settings.getTextInput("Server Password");
    await expect(field).toHaveAttribute("type", "password");
  });

  test("select dropdown changes value and saves to backend", async ({
    page,
    apiGet,
  }) => {
    const select = settings.getSelect("Log Format");
    await select.selectOption("json");
    await page.waitForTimeout(1500);

    const config = await apiGet("/server/config/get");
    expect(config.general.log_format).toBe("json");
  });

  test("Advanced LFTP section is collapsed by default", async ({ page }) => {
    const header = page.locator("[class*='card-header']", {
      hasText: "Advanced LFTP",
    });
    const collapsed = header.locator("[class*='collapsed'], .collapsed");
    await expect(collapsed.first()).toBeVisible();
  });

  test("clicking Advanced LFTP header expands the section", async ({
    page,
  }) => {
    await settings.expandSection("Advanced LFTP");

    // After expanding, the collapse body should be visible
    const body = page
      .locator(".card, [class*='card']", {
        has: page.locator("text=Advanced LFTP"),
      })
      .locator("[class*='collapse']")
      .filter({ has: page.locator("input, select") });
    await expect(body.first()).toBeVisible();
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
    page,
    appUrl,
  }) => {
    // Create a path pair via API
    const res = await fetch(`${appUrl}/server/pathpairs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "temp-pair",
        remote_path: "/remote/test",
        local_path: "/local/test",
        enabled: true,
      }),
    });
    const pair = await res.json();

    // Reload to pick up the new state
    await settings.goto();

    const serverDir = settings.getTextInput("Server Directory");
    await expect(serverDir).toBeDisabled();

    // Clean up
    await fetch(`${appUrl}/server/pathpairs/${pair.id}`, {
      method: "DELETE",
    });
  });

  test("restart notification appears after config change", async ({
    page,
  }) => {
    const field = settings.getTextInput("Server Address");
    await field.clear();
    await field.fill("trigger-restart-notice-" + Date.now());
    await page.waitForTimeout(1500);

    const notification = settings.getRestartNotification();
    await expect(notification).toBeVisible();
  });

  test("Web GUI Port field shows current port value", async ({ apiGet }) => {
    const config = await apiGet("/server/config/get");
    const portField = settings.getTextInput("Web GUI Port");
    await expect(portField).toBeVisible();
    await expect(portField).toHaveValue(String(config.web.port));
  });

  test("API Key field is a password field", async () => {
    const field = settings.getTextInput("API Key");
    await expect(field).toHaveAttribute("type", "password");
  });
});
