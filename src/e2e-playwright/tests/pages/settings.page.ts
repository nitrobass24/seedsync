import { type Page, type Locator } from "@playwright/test";

export class SettingsPage {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  async goto() {
    await this.page.goto("/settings");
    await this.page.waitForLoadState("networkidle");
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
    const header = this.page.locator("[class*='card-header']", {
      hasText: headerText,
    });
    const collapsed = header.locator("[class*='collapsed'], .collapsed");
    if ((await collapsed.count()) > 0) {
      await header.click();
      // Wait for animation
      await this.page.waitForTimeout(500);
    }
  }

  /** Get the restart notification if visible */
  getRestartNotification() {
    return this.page.locator("[class*='alert']", {
      hasText: /restart/i,
    });
  }
}
