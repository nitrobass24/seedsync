import { type Page, type Locator } from "@playwright/test";

export class AboutPage {
  readonly page: Page;
  readonly versionText: Locator;
  readonly githubLink: Locator;

  constructor(page: Page) {
    this.page = page;
    this.versionText = page.locator("text=/v\\d+\\.\\d+/");
    this.githubLink = page.locator('a[href*="github.com/nitrobass24/seedsync"]');
  }

  async goto() {
    await this.page.goto("/about");
    await this.page.waitForLoadState("networkidle");
  }
}
