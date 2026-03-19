import { type Page, type Locator } from "@playwright/test";

export class LogsPage {
  readonly page: Page;
  readonly searchInput: Locator;
  readonly levelFilter: Locator;
  readonly logHistory: Locator;
  readonly scrollToTop: Locator;
  readonly scrollToBottom: Locator;

  constructor(page: Page) {
    this.page = page;
    this.searchInput = page.locator("#log-search, input[placeholder*='search' i]");
    this.levelFilter = page.locator("#log-level, select");
    this.logHistory = page.locator(".history-section, [class*='history']");
    this.scrollToTop = page.locator("#btn-scroll-top, button", {
      hasText: /top/i,
    });
    this.scrollToBottom = page.locator("#btn-scroll-bottom, button", {
      hasText: /bottom/i,
    });
  }

  async goto() {
    await this.page.goto("/logs");
    await this.page.waitForLoadState("domcontentloaded");
    await this.page.waitForSelector('a[href="/dashboard"]', { timeout: 10_000 });
  }

  getLogRecords() {
    return this.page.locator(".record");
  }

  getLogRecordsByLevel(level: string) {
    return this.page.locator(`.record.${level.toLowerCase()}`);
  }
}
