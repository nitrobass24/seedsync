import { test, expect } from "./fixtures";
import { SidebarPage } from "./pages/sidebar.page";

test.describe("Sidebar Navigation", () => {
  let sidebar: SidebarPage;

  test.beforeEach(async ({ page }) => {
    sidebar = new SidebarPage(page);
  });

  test("root / redirects to /dashboard", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    expect(page.url()).toContain("/dashboard");
  });

  test("clicking Dashboard link navigates to /dashboard", async ({ page }) => {
    await page.goto("/about");
    await page.waitForLoadState("networkidle");
    await sidebar.navigateTo(sidebar.dashboardLink);
    expect(page.url()).toContain("/dashboard");
  });

  test("clicking Settings link navigates to /settings", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
    await sidebar.navigateTo(sidebar.settingsLink);
    expect(page.url()).toContain("/settings");
  });

  test("clicking AutoQueue link navigates to /autoqueue", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
    await sidebar.navigateTo(sidebar.autoqueueLink);
    expect(page.url()).toContain("/autoqueue");
  });

  test("clicking Logs link navigates to /logs", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
    await sidebar.navigateTo(sidebar.logsLink);
    expect(page.url()).toContain("/logs");
  });

  test("clicking About link navigates to /about", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
    await sidebar.navigateTo(sidebar.aboutLink);
    expect(page.url()).toContain("/about");
  });

  test("active link is highlighted after navigation", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");
    const activeLink = sidebar.getActiveLink();
    await expect(activeLink).toBeVisible();
    await expect(activeLink).toHaveAttribute("href", "/settings");
  });

  test("all 5 nav links are visible in sidebar", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
    await expect(sidebar.dashboardLink).toBeVisible();
    await expect(sidebar.settingsLink).toBeVisible();
    await expect(sidebar.autoqueueLink).toBeVisible();
    await expect(sidebar.logsLink).toBeVisible();
    await expect(sidebar.aboutLink).toBeVisible();
  });
});
