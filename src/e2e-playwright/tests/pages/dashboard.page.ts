import { type Page, type Locator } from "@playwright/test";

export class DashboardPage {
  readonly page: Page;
  readonly fileList: Locator;
  readonly nameFilter: Locator;
  readonly statusFilter: Locator;
  readonly sortDropdown: Locator;
  readonly detailsToggle: Locator;
  readonly bulkActionBar: Locator;

  constructor(page: Page) {
    this.page = page;
    this.fileList = page.locator(".file-list, [class*='file-list']");
    this.nameFilter = page.getByPlaceholder(/filter/i);
    this.statusFilter = page.locator("#statusFilter, [id*='status']");
    this.sortDropdown = page.locator("#sortDropdown, [id*='sort']");
    this.detailsToggle = page.locator("button", { hasText: /details/i });
    this.bulkActionBar = page.locator("app-bulk-action-bar, [class*='bulk']");
  }

  async goto() {
    await this.page.goto("/dashboard");
    await this.page.waitForLoadState("networkidle");
  }

  getFileRows() {
    return this.page.locator("app-file, [class*='file-row']");
  }

  getFileByName(name: string) {
    return this.page.locator("app-file, [class*='file-row']", {
      hasText: name,
    });
  }

  async getFileNames(): Promise<string[]> {
    const rows = this.getFileRows();
    const count = await rows.count();
    const names: string[] = [];
    for (let i = 0; i < count; i++) {
      const nameEl = rows.nth(i).locator(".file-name, [class*='name']");
      const text = await nameEl.textContent();
      if (text) names.push(text.trim());
    }
    return names;
  }

  getActionButton(fileRow: Locator, action: string) {
    return fileRow.locator("button", { hasText: new RegExp(action, "i") });
  }

  getCheckbox(fileRow: Locator) {
    return fileRow.locator("input[type='checkbox']");
  }

  getBulkButton(action: string) {
    return this.bulkActionBar.locator("button", {
      hasText: new RegExp(action, "i"),
    });
  }

  getBulkSelectedCount() {
    return this.bulkActionBar.locator("[class*='count'], span", {
      hasText: /selected/i,
    });
  }
}
