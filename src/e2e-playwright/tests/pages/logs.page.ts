import { type Page, type Locator } from "@playwright/test";

export class LogsPage {
  readonly page: Page;
  readonly searchInput: Locator;
  readonly levelFilter: Locator;
  readonly logFilters: Locator;
  readonly scrollToTop: Locator;
  readonly scrollToBottom: Locator;

  constructor(page: Page) {
    this.page = page;
    this.searchInput = page.locator("#log-search");
    this.levelFilter = page.locator("#log-level");
    this.logFilters = page.locator(".log-filters");
    this.scrollToTop = page.locator("#btn-scroll-top");
    this.scrollToBottom = page.locator("#btn-scroll-bottom");
  }

  async goto() {
    await this.page.goto("/logs");
    await this.page.waitForLoadState("domcontentloaded");
    await this.page.waitForSelector('a[href="/dashboard"]', { timeout: 10_000 });
  }

  getLogRecords() {
    return this.page.locator("#logs .record");
  }

  getLogRecordsByLevel(level: string) {
    return this.page.locator(`#logs .record.${level.toLowerCase()}`);
  }
}
