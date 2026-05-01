import { type Page, type Locator } from "@playwright/test";

export class IntegrationsPage {
  readonly page: Page;
  readonly container: Locator;
  readonly addSonarrButton: Locator;
  readonly addRadarrButton: Locator;
  readonly emptyState: Locator;
  readonly instanceForm: Locator;
  readonly errorMessage: Locator;

  constructor(page: Page) {
    this.page = page;
    // Scope all selectors to .integrations to avoid collisions with .path-pairs
    this.container = page.locator(".integrations");
    this.addSonarrButton = this.container.locator("button.btn-add", {
      hasText: "Sonarr",
    });
    this.addRadarrButton = this.container.locator("button.btn-add", {
      hasText: "Radarr",
    });
    this.emptyState = this.container.locator(".empty-state");
    this.instanceForm = this.container.locator(".instance-form");
    this.errorMessage = this.container.locator(".error-message");
  }

  async goto() {
    await this.page.goto("/settings");
    await this.page.waitForURL("**/settings", { timeout: 10_000 });
    await this.page.waitForSelector('a[href="/dashboard"]', {
      timeout: 10_000,
    });
  }

  /** Fill the add/edit instance form */
  async fillForm(fields: {
    name?: string;
    url?: string;
    apiKey?: string;
    kind?: string;
  }) {
    const form = this.instanceForm;
    if (fields.kind !== undefined) {
      const select = form.locator("select");
      await select.selectOption(fields.kind);
    }
    if (fields.name !== undefined) {
      const nameInput = form.locator('label:has-text("Name") input');
      await nameInput.fill(fields.name);
    }
    if (fields.url !== undefined) {
      const urlInput = form.locator('label:has-text("URL") input');
      await urlInput.fill(fields.url);
    }
    if (fields.apiKey !== undefined) {
      const apiKeyInput = form.locator('label:has-text("API Key") input');
      await apiKeyInput.fill(fields.apiKey);
    }
  }

  async clickSave() {
    await this.instanceForm.locator("button.btn-save").click();
  }

  async clickCancel() {
    await this.instanceForm.locator("button.btn-cancel").click();
  }

  getInstanceRows() {
    return this.container.locator(".instance-row");
  }

  getInstanceByName(name: string) {
    const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return this.container.locator(".instance-row").filter({
      has: this.page.locator(".instance-name", {
        hasText: new RegExp(escaped),
      }),
    });
  }

  getEditButton(row: Locator) {
    return row.locator("button.btn-edit");
  }

  getDeleteButton(row: Locator) {
    return row.locator("button.btn-delete");
  }

  getTestButton(row: Locator) {
    return row.locator("button", { hasText: /Test Connection|Testing/i });
  }

  getTestResult(row: Locator) {
    return row.locator(".test-result");
  }

  getEnabledToggle(row: Locator) {
    return row.locator('input[type="checkbox"]');
  }
}
