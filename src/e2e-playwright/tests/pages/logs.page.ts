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
    this.logHistory = page.locator("[class*='log-history'], [class*='log-records']");
    this.scrollToTop = page.locator("#btn-scroll-top, button", {
      hasText: /top/i,
    });
    this.scrollToBottom = page.locator("#btn-scroll-bottom, button", {
      hasText: /bottom/i,
    });
  }

  async goto() {
    await this.page.goto("/logs");
    await this.page.waitForLoadState("networkidle");
  }

  getLogRecords() {
    return this.page.locator("[class*='log-record'], [class*='log-line']");
  }

  getLogRecordsByLevel(level: string) {
    return this.page.locator(
      `[class*='log-record'].${level.toLowerCase()}, [class*='${level.toLowerCase()}']`
    );
  }
}
