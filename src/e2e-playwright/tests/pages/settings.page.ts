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
    // Find the card that contains a matching h3 header
    // Use XPath parent to go from h3 back to its .card container
    return this.page
      .locator("h3.card-header", { hasText: headerText })
      .first()
      .locator("xpath=..");
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
    const header = this.page.locator("h3.card-header.collapsible-header", {
      hasText: headerText,
    });
    const card = header.locator("xpath=..");
    const collapseBody = card.locator("app-option");

    // If the body content is not visible, click the header to expand
    if ((await collapseBody.count()) === 0) {
      await header.click();
      // Wait for Angular @if to render the content
      await collapseBody.first().waitFor({ state: "visible", timeout: 3000 });
    }
  }

  /** Get the restart notification if visible */
  getRestartNotification() {
    return this.page.locator(".alert", {
      hasText: /restart/i,
    });
  }
}
