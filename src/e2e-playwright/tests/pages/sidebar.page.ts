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
    this.restartButton = page.locator("button", { hasText: "Restart" });
    this.themeToggle = page.locator("button", {
      hasText: /Dark Mode|Light Mode/,
    });
  }

  async navigateTo(link: Locator) {
    await link.click();
    await this.page.waitForLoadState("networkidle");
  }

  getActiveLink() {
    return this.page.locator(".sidebar .selected, .sidebar .active");
  }
}
