import { test, expect } from "./fixtures";
import { SidebarPage } from "./pages/sidebar.page";

test.describe("Theme Switching", () => {
  let sidebar: SidebarPage;

  test.beforeEach(async ({ page }) => {
    sidebar = new SidebarPage(page);
    await page.goto("/dashboard");
    await page.waitForLoadState("domcontentloaded");
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
    const expectedTheme = initialTheme === "dark" ? "light" : "dark";

    await sidebar.themeToggle.click();
    await expect(page.locator("html")).toHaveAttribute(
      "data-bs-theme",
      expectedTheme
    );
  });

  test("clicking theme toggle again switches back to original theme", async ({
    page,
  }) => {
    const initialTheme = await page
      .locator("html")
      .getAttribute("data-bs-theme");
    const oppositeTheme = initialTheme === "dark" ? "light" : "dark";

    await sidebar.themeToggle.click();
    await expect(page.locator("html")).toHaveAttribute(
      "data-bs-theme",
      oppositeTheme
    );

    await sidebar.themeToggle.click();
    await expect(page.locator("html")).toHaveAttribute(
      "data-bs-theme",
      initialTheme!
    );
  });

  test("theme persists after page reload", async ({ page }) => {
    const initialTheme = await page
      .locator("html")
      .getAttribute("data-bs-theme");
    const expectedTheme = initialTheme === "dark" ? "light" : "dark";

    await sidebar.themeToggle.click();
    await expect(page.locator("html")).toHaveAttribute(
      "data-bs-theme",
      expectedTheme
    );

    await page.reload();
    await page.waitForLoadState("domcontentloaded");

    await expect(page.locator("html")).toHaveAttribute(
      "data-bs-theme",
      expectedTheme
    );
  });
});
