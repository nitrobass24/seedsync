import { type Page, type Locator } from "@playwright/test";

export class SidebarPage {
  readonly page: Page;
  readonly dashboardLink: Locator;
  readonly settingsLink: Locator;
  readonly autoqueueLink: Locator;
  readonly logsLink: Locator;
  readonly aboutLink: Locator;
  readonly restartButton: Locator;
  readonly themeToggle: Locator;

  constructor(page: Page) {
    this.page = page;
    this.dashboardLink = page.locator('a[href="/dashboard"]');
    this.settingsLink = page.locator('a[href="/settings"]');
    this.autoqueueLink = page.locator('a[href="/autoqueue"]');
    this.logsLink = page.locator('a[href="/logs"]');
    this.aboutLink = page.locator('a[href="/about"]');
    // Restart and theme toggle are <a class="button"> not <button>
    this.restartButton = page.locator("#sidebar a.button", {
      hasText: "Restart",
    });
    this.themeToggle = page.locator("#sidebar a.button", {
      hasText: /Dark Mode|Light Mode/,
    });
  }

  async navigateTo(link: Locator) {
    const href = await link.getAttribute("href");
    await link.click();
    if (href) {
      await this.page.waitForURL(`**${href}`, { timeout: 10_000 });
    }
  }

  getActiveLink() {
    return this.page.locator("#sidebar a.selected");
  }
}
