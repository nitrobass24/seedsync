import { type Page, type Locator } from "@playwright/test";

export class SettingsPage {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  async goto() {
    await this.page.goto("/settings");
    await this.page.waitForLoadState("domcontentloaded");
    await this.page.waitForSelector('a[href="/dashboard"]', { timeout: 10_000 });
  }

  /** Get a settings section card by its header text */
  getSection(headerText: string) {
    return this.page.locator(".card, [class*='card']", {
      has: this.page.locator("text=" + headerText),
    });
  }

  /** Get a text/password input by its label */
  getTextInput(label: string) {
    return this.page
      .locator("app-option", { hasText: label })
      .locator("input[type='text'], input[type='password']");
  }

  /** Get a checkbox by its label */
  getCheckbox(label: string) {
    return this.page
      .locator("app-option", { hasText: label })
      .locator("input[type='checkbox']");
  }

  /** Get a select dropdown by its label */
  getSelect(label: string) {
    return this.page
      .locator("app-option", { hasText: label })
      .locator("select");
  }

  /** Expand a collapsed section (e.g., Advanced LFTP) */
  async expandSection(headerText: string) {
    const card = this.page.locator(".card, [class*='card']", {
      has: this.page.locator(`text=${headerText}`),
    });
    const collapseBody = card.locator("app-option");

    // If the body content is not visible, click the header to expand
    if ((await collapseBody.count()) === 0) {
      const header = this.page.locator("h3.card-header.collapsible-header", {
        hasText: headerText,
      });
      await header.click();
      // Wait for Angular *ngIf to render the content
      await collapseBody.first().waitFor({ state: "visible", timeout: 3000 });
    }
  }

  /** Get the restart notification if visible */
  getRestartNotification() {
    return this.page.locator("[class*='alert']", {
      hasText: /restart/i,
    });
  }
}
