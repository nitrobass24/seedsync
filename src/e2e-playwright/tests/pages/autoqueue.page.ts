import { type Page, type Locator } from "@playwright/test";

export class AutoQueuePage {
  readonly page: Page;
  readonly patternInput: Locator;
  readonly addButton: Locator;
  readonly patternList: Locator;
  readonly disabledMessage: Locator;

  constructor(page: Page) {
    this.page = page;
    this.patternInput = page.locator(
      "input[placeholder*='pattern' i], input[type='text']"
    );
    this.addButton = page.locator("button", { hasText: "+" });
    this.patternList = page.locator(
      "[class*='pattern-list'], [class*='patterns']"
    );
    this.disabledMessage = page.locator("text=/disabled|all files/i");
  }

  async goto() {
    await this.page.goto("/autoqueue");
    await this.page.waitForLoadState("networkidle");
  }

  getPatternItems() {
    return this.page.locator("[class*='pattern-item'], [class*='pattern'] li");
  }

  getPatternByText(pattern: string) {
    return this.page.locator("[class*='pattern']", { hasText: pattern });
  }

  getRemoveButton(patternItem: Locator) {
    return patternItem.locator("button", { hasText: /−|remove|-/i });
  }

  async addPattern(pattern: string) {
    await this.patternInput.fill(pattern);
    await this.addButton.click();
  }

  getErrorMessage() {
    return this.page.locator("[class*='alert-danger'], [class*='error']");
  }
}
