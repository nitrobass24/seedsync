import { type Page, type Locator } from "@playwright/test";

export class PathPairsPage {
  readonly page: Page;
  readonly addButton: Locator;
  readonly pairsList: Locator;
  readonly emptyMessage: Locator;

  constructor(page: Page) {
    this.page = page;
    this.addButton = page.locator("button.btn-add");
    this.pairsList = page.locator(".path-pairs");
    this.emptyMessage = page.locator(".empty-state");
  }

  async goto() {
    await this.page.goto("/settings");
    await this.page.waitForLoadState("domcontentloaded");
    await this.page.waitForSelector('a[href="/dashboard"]', { timeout: 10_000 });
  }

  getPairRows() {
    return this.pairsList.locator(".pair-row");
  }

  getPairByName(name: string) {
    return this.pairsList.locator(".pair-row", {
      hasText: name,
    });
  }

  /** Fill the add/edit form fields */
  async fillForm(fields: {
    name?: string;
    remotePath?: string;
    localPath?: string;
  }) {
    const form = this.page.locator(".pair-form");
    if (fields.name !== undefined) {
      const nameInput = form.locator('label:has-text("Name") input');
      await nameInput.fill(fields.name);
    }
    if (fields.remotePath !== undefined) {
      const remoteInput = form.locator('label:has-text("Remote Path") input');
      await remoteInput.fill(fields.remotePath);
    }
    if (fields.localPath !== undefined) {
      const localInput = form.locator('label:has-text("Local Path") input');
      await localInput.fill(fields.localPath);
    }
  }

  async clickSave() {
    await this.page.locator("button.btn-save").click();
  }

  async clickCancel() {
    await this.page.locator("button.btn-cancel").click();
  }

  getErrorMessage() {
    return this.page.locator(".error-message");
  }

  getDeleteButton(pairRow: Locator) {
    return pairRow.locator("button.btn-delete");
  }

  getEditButton(pairRow: Locator) {
    return pairRow.locator("button.btn-edit");
  }

  getEnabledToggle(pairRow: Locator) {
    return pairRow.locator("input[type='checkbox']").first();
  }
}
