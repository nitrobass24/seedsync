import { test, expect } from "./fixtures";

test.describe("About Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/about");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForSelector('a[href="/dashboard"]', { timeout: 10_000 });
  });

  test("version number is displayed and matches format vX.Y.Z", async ({ page }) => {
    const version = page.locator("#version");
    await expect(version).toBeVisible();
    expect((await version.textContent())?.trim()).toMatch(/^v\d+\.\d+\.\d+$/);
  });

  test("GitHub link is present and points to correct URL", async ({ page }) => {
    const githubLink = page.locator("#github a");
    await expect(githubLink).toBeVisible();
    expect(await githubLink.getAttribute("href")).toBe("https://github.com/nitrobass24/seedsync");
  });

  test('page renders with app name "SeedSync"', async ({ page }) => {
    await expect(page.locator("#banner span")).toBeVisible();
    await expect(page.locator("#banner span")).toHaveText("SeedSync");
  });
});
