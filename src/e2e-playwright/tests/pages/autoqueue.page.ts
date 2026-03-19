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
    await this.patternInput.fill(pattern);
    await this.addButton.click();
  }

  getErrorMessage() {
    return this.page.locator("[class*='alert-danger'], [class*='error']");
  }
}
