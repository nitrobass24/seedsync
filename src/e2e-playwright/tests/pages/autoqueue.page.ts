import { type Page, type Locator } from "@playwright/test";

export class AutoQueuePage {
  readonly page: Page;
  readonly patternInput: Locator;
  readonly addButton: Locator;
  readonly patternList: Locator;
  readonly disabledMessage: Locator;

  constructor(page: Page) {
    this.page = page;
    this.patternInput = page.locator("input[type='search']");
    this.addButton = page.locator("#add-pattern .button");
    this.patternList = page.locator("#controls");
    this.disabledMessage = page.locator("text=/disabled|all files/i");
  }

  async goto() {
    await this.page.goto("/autoqueue");
    await this.page.waitForLoadState("domcontentloaded");
    await this.page.waitForSelector('a[href="/dashboard"]', { timeout: 10_000 });
  }

  getPatternItems() {
    return this.page.locator("#controls .pattern");
  }

  getPatternByText(pattern: string) {
    return this.page.locator("[class*='pattern']", { hasText: pattern });
  }

  getRemoveButton(patternItem: Locator) {
    return patternItem.locator(".button");
  }

  async addPattern(pattern: string) {
    // Wait for input to be enabled (SSE stream must have delivered config)
    await this.patternInput.waitFor({ state: "visible", timeout: 10_000 });
    // Wait until the input is not disabled (config has been received)
    await this.page.waitForFunction(
      () => {
        const el = document.querySelector("input[type='search']") as HTMLInputElement;
        return el && !el.disabled;
      },
      { timeout: 10_000 }
    );
    await this.patternInput.fill(pattern);
    // Small delay for Angular change detection to process the input value
    await this.page.waitForTimeout(200);
    // Click with force since it's a div, not a native button
    await this.addButton.click({ force: true });
  }

  getErrorMessage() {
    return this.page.locator(".alert-danger.alert-dismissible", {
      hasText: /already exists|error/i,
    });
  }
}
