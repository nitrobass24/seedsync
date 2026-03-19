import { type Page, type Locator } from "@playwright/test";

export class PathPairsPage {
  readonly page: Page;
  readonly addButton: Locator;
  readonly pairsList: Locator;
  readonly emptyMessage: Locator;

  constructor(page: Page) {
    this.page = page;
    this.addButton = page.locator("button", { hasText: /add/i });
    this.pairsList = page.locator(
      "app-path-pairs, [class*='path-pairs']"
    );
    this.emptyMessage = page.locator("text=No path pairs configured");
  }

  async goto() {
    await this.page.goto("/settings");
    await this.page.waitForLoadState("networkidle");
  }

  getPairRows() {
    return this.pairsList.locator("[class*='pair-row'], .pair-item, tr");
  }

  getPairByName(name: string) {
    return this.pairsList.locator("[class*='pair-row'], .pair-item, tr", {
      hasText: name,
    });
  }

  /** Fill the add/edit form fields */
  async fillForm(fields: {
    name?: string;
    remotePath?: string;
    localPath?: string;
    enabled?: boolean;
    autoQueue?: boolean;
  }) {
    const form = this.page.locator(
      "[class*='pair-form'], form, [class*='edit']"
    );
    if (fields.name !== undefined) {
      const nameInput = form.locator("input").first();
      await nameInput.fill(fields.name);
    }
    if (fields.remotePath !== undefined) {
      const remoteInput = form.locator("input").nth(1);
      await remoteInput.fill(fields.remotePath);
    }
    if (fields.localPath !== undefined) {
      const localInput = form.locator("input").nth(2);
      await localInput.fill(fields.localPath);
    }
  }

  async clickSave() {
    await this.page.locator("button", { hasText: /save/i }).click();
  }

  async clickCancel() {
    await this.page.locator("button", { hasText: /cancel/i }).click();
  }

  getErrorMessage() {
    return this.page.locator("[class*='error'], [class*='danger']", {
      hasText: /already exists|error/i,
    });
  }

  getDeleteButton(pairRow: Locator) {
    return pairRow.locator("button", { hasText: /delete/i });
  }

  getEditButton(pairRow: Locator) {
    return pairRow.locator("button", { hasText: /edit/i });
  }

  getEnabledToggle(pairRow: Locator) {
    return pairRow.locator("input[type='checkbox']").first();
  }
}
