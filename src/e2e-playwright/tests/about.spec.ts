import { test, expect } from "./fixtures";
import { AboutPage } from "./pages/about.page";

test.describe("About Page", () => {
  let aboutPage: AboutPage;

  test.beforeEach(async ({ page }) => {
    aboutPage = new AboutPage(page);
    await aboutPage.goto();
  });

  test("version number is displayed and matches format vX.Y.Z", async ({
    page,
  }) => {
    await expect(aboutPage.versionText).toBeVisible();
    const versionContent = await aboutPage.versionText.textContent();
    expect(versionContent).toMatch(/v\d+\.\d+\.\d+/);
  });

  test("GitHub link is present and points to correct URL", async () => {
    await expect(aboutPage.githubLink).toBeVisible();
    const href = await aboutPage.githubLink.getAttribute("href");
    expect(href).toContain("github.com/nitrobass24/seedsync");
  });

  test('page renders with app name "SeedSync"', async ({ page }) => {
    const appName = page.locator("text=SeedSync");
    await expect(appName.first()).toBeVisible();
  });
});
