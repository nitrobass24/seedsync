import { test, expect } from "./fixtures";
import { SidebarPage } from "./pages/sidebar.page";

test.describe("Theme Switching", () => {
  let sidebar: SidebarPage;

  test.beforeEach(async ({ page }) => {
    sidebar = new SidebarPage(page);
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
  });

  test("default theme has data-bs-theme attribute on html element", async ({
    page,
  }) => {
    const theme = await page.locator("html").getAttribute("data-bs-theme");
    expect(theme).toBeTruthy();
    expect(["light", "dark"]).toContain(theme);
  });

  test("clicking theme toggle switches from current theme to opposite", async ({
    page,
  }) => {
    const initialTheme = await page
      .locator("html")
      .getAttribute("data-bs-theme");
    await sidebar.themeToggle.click();
    const newTheme = await page.locator("html").getAttribute("data-bs-theme");
    expect(newTheme).not.toEqual(initialTheme);
    expect(["light", "dark"]).toContain(newTheme);
  });

  test("clicking theme toggle again switches back to original theme", async ({
    page,
  }) => {
    const initialTheme = await page
      .locator("html")
      .getAttribute("data-bs-theme");
    await sidebar.themeToggle.click();
    await sidebar.themeToggle.click();
    const restoredTheme = await page
      .locator("html")
      .getAttribute("data-bs-theme");
    expect(restoredTheme).toEqual(initialTheme);
  });

  test("theme persists after page reload", async ({ page }) => {
    const initialTheme = await page
      .locator("html")
      .getAttribute("data-bs-theme");
    await sidebar.themeToggle.click();
    const toggledTheme = await page
      .locator("html")
      .getAttribute("data-bs-theme");
    expect(toggledTheme).not.toEqual(initialTheme);

    await page.reload();
    await page.waitForLoadState("networkidle");

    const persistedTheme = await page
      .locator("html")
      .getAttribute("data-bs-theme");
    expect(persistedTheme).toEqual(toggledTheme);
  });
});
