import { test, expect } from "./fixtures";

test.describe("About Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/about");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForSelector('a[href="/dashboard"]', { timeout: 10_000 });
  });

  test("version number is displayed and matches format vX.Y.Z", async ({ page }) => {
    const versionText = page.locator("text=/v\\d+\\.\\d+\\.\\d+/");
    await expect(versionText).toBeVisible();
    expect(await versionText.textContent()).toMatch(/v\d+\.\d+\.\d+/);
  });

  test("GitHub link is present and points to correct URL", async ({ page }) => {
    const githubLink = page.locator('a[href*="github.com/nitrobass24/seedsync"]');
    await expect(githubLink).toBeVisible();
    expect(await githubLink.getAttribute("href")).toContain("github.com/nitrobass24/seedsync");
  });

  test('page renders with app name "SeedSync"', async ({ page }) => {
    await expect(page.locator("text=SeedSync").first()).toBeVisible();
  });
});
