import { type Page, type Locator } from "@playwright/test";

export class PathPairsPage {
  readonly page: Page;
  readonly pairsList: Locator;
  readonly addButton: Locator;
  readonly emptyMessage: Locator;
  readonly pairForm: Locator;
  readonly errorMessage: Locator;

  constructor(page: Page) {
    this.page = page;
    // All selectors are scoped under .path-pairs to avoid colliding with the
    // sibling .integrations card, which reuses class names like .empty-state,
    // .btn-add, .btn-save, .btn-cancel, and .error-message.
    this.pairsList = page.locator(".path-pairs");
    this.addButton = this.pairsList.locator("button.btn-add");
    this.emptyMessage = this.pairsList.locator(".empty-state");
    this.pairForm = this.pairsList.locator(".pair-form");
    this.errorMessage = this.pairsList.locator(".error-message");
  }

  async goto() {
    await this.page.goto("/settings");
    await this.page.waitForURL("**/settings", { timeout: 10_000 });
    await this.page.waitForSelector('a[href="/dashboard"]', { timeout: 10_000 });
  }

  getPairRows() {
    return this.pairsList.locator(".pair-row");
  }

  getPairByName(name: string) {
    // Use exact match on .pair-name to avoid substring collisions
    const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return this.pairsList.locator(".pair-row").filter({
      has: this.page.locator(".pair-name", { hasText: new RegExp(`^${escaped}$`) }),
    });
  }

  /** Fill the add/edit form fields */
  async fillForm(fields: {
    name?: string;
    remotePath?: string;
    localPath?: string;
  }) {
    const form = this.pairForm;
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
    await this.pairForm.locator("button.btn-save").click();
  }

  async clickCancel() {
    await this.pairForm.locator("button.btn-cancel").click();
  }

  getErrorMessage() {
    return this.errorMessage;
  }

  getDeleteButton(pairRow: Locator) {
    return pairRow.locator("button.btn-delete");
  }

  getEditButton(pairRow: Locator) {
    return pairRow.locator("button.btn-edit");
  }

  getEnabledToggle(pairRow: Locator) {
    return pairRow.locator('label:has-text("Enabled") input[type="checkbox"]');
  }
}
