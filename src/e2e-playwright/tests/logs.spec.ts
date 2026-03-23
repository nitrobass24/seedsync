import { test, expect } from "./fixtures";
import { LogsPage } from "./pages/logs.page";

test.describe("Logs Page", () => {
  let logs: LogsPage;

  test.beforeEach(async ({ page, waitForStream }) => {
    logs = new LogsPage(page);
    await logs.goto();
    await waitForStream(page);
  });

  test("page loads without errors", async ({ page }) => {
    expect(page.url()).toContain("/logs");
  });

  test("search input is present", async () => {
    await expect(logs.searchInput).toBeVisible();
  });

  test("level filter dropdown has expected options", async () => {
    await expect(logs.levelFilter).toBeVisible();
    const options = logs.levelFilter.locator("option");
    const texts: string[] = [];
    const count = await options.count();
    for (let i = 0; i < count; i++) {
      const text = await options.nth(i).textContent();
      if (text) texts.push(text.trim().toUpperCase());
    }

    const expected = ["ALL LEVELS", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];
    for (const level of expected) {
      expect(texts.some((t) => t.includes(level))).toBe(true);
    }
  });

  test("log filters section is visible", async () => {
    await expect(logs.logFilters).toBeVisible();
  });

  test("if log records exist: records show timestamp, level, and message", async () => {
    const records = logs.getLogRecords();
    const count = await records.count();
    test.skip(count === 0, "No log records present");

    const firstRecord = records.first();
    const text = await firstRecord.textContent();
    expect(text).toBeTruthy();

    // Expect a timestamp-like pattern (e.g., HH:MM:SS or YYYY-MM-DD)
    expect(text).toMatch(/\d{2}[:\-]\d{2}/);

    // Expect a log level keyword
    expect(text).toMatch(/DEBUG|INFO|WARNING|ERROR|CRITICAL/i);
  });

  test("search filter narrows displayed records", async () => {
    const records = logs.getLogRecords();
    const count = await records.count();
    test.skip(count === 0, "No log records to search through");

    // Get text from the first record to use as a valid search term
    const firstText = await records.first().textContent();
    const searchTerm = firstText?.trim().split(/\s+/).filter(Boolean).pop() || "";
    test.skip(searchTerm === "", "Could not derive a non-empty search term from log records");

    // Type a term that exists
    await logs.searchInput.fill(searchTerm);
    await expect
      .poll(async () => await records.count(), { timeout: 5000 })
      .toBeLessThanOrEqual(count);

    // Type a nonsense term that should match nothing
    await logs.searchInput.fill("zzz_no_match_xyz_99999");
    await expect(records).toHaveCount(0, { timeout: 5000 });
  });
});
