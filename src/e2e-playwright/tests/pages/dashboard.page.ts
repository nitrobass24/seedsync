import { type Page, type Locator } from "@playwright/test";

export class DashboardPage {
  readonly page: Page;
  readonly fileList: Locator;
  readonly nameFilter: Locator;
  readonly statusFilterButton: Locator;
  readonly statusFilterMenu: Locator;
  readonly sortDropdownButton: Locator;
  readonly sortDropdownMenu: Locator;
  readonly detailsToggle: Locator;
  readonly bulkActionBar: Locator;

  constructor(page: Page) {
    this.page = page;
    this.fileList = page.locator("#file-list");
    this.nameFilter = page.locator(
      '#filter-search input[type="search"]'
    );
    this.statusFilterButton = page.locator(
      "#filter-status .dropdown-toggle"
    );
    this.statusFilterMenu = page.locator("#filter-status .dropdown-menu");
    this.sortDropdownButton = page.locator(
      "#sort-status .dropdown-toggle"
    );
    this.sortDropdownMenu = page.locator("#sort-status .dropdown-menu");
    this.detailsToggle = page.locator("#toggle-details");
    this.bulkActionBar = page.locator("app-bulk-action-bar");
  }

  async goto() {
    await this.page.goto("/dashboard");
    await this.page.waitForLoadState("domcontentloaded");
    await this.page.waitForSelector('a[href="/dashboard"]', { timeout: 10_000 });
  }

  getFileRows() {
    return this.page.locator("app-file");
  }

  getFileByName(name: string) {
    return this.page.locator("app-file", {
      hasText: name,
    });
  }

  async getFileNames(): Promise<string[]> {
    const rows = this.getFileRows();
    const count = await rows.count();
    const names: string[] = [];
    for (let i = 0; i < count; i++) {
      const nameEl = rows.nth(i).locator(".name .text .title");
      const text = await nameEl.textContent();
      if (text) names.push(text.trim());
    }
    return names;
  }

  getActionButton(fileRow: Locator, action: string) {
    return fileRow.locator(".actions button", {
      hasText: new RegExp(action, "i"),
    });
  }

  getCheckbox(fileRow: Locator) {
    return fileRow.locator(".checkbox input[type='checkbox']");
  }

  getBulkButton(action: string) {
    return this.bulkActionBar.locator("button", {
      hasText: new RegExp(action, "i"),
    });
  }

  getBulkSelectedCount() {
    return this.bulkActionBar.locator(".count");
  }
}
