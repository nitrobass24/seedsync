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

  /**
   * The Remote Path field is locked until the SSH connection is verified
   * (see connection-status.service.ts). There's no live SSH server in the
   * e2e environment, so mock the test-connection call and click the button
   * in the Server section above Path Pairs; the resulting verified state is
   * shared with PathPairsComponent via ConnectionStatusService.
   *
   * Scoped to #left: the Integrations card (in #right) renders its own
   * per-instance "Test Connection" button with the same text, and its rows
   * may exist concurrently from integrations.spec.ts sharing this backend.
   */
  async verifyConnection() {
    await this.page.route("**/server/config/test-connection", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: "{}" }),
    );
    const responsePromise = this.page.waitForResponse("**/server/config/test-connection");
    await this.page.locator("#left").getByRole("button", { name: "Test Connection" }).click();
    await responsePromise;
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
