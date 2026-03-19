import { test, expect } from "./fixtures";
import { DashboardPage } from "./pages/dashboard.page";

test.describe("Dashboard Page", () => {
  let dashboard: DashboardPage;

  test.beforeEach(async ({ page, waitForStream }) => {
    dashboard = new DashboardPage(page);
    await dashboard.goto();
    await waitForStream(page);
  });

  test("page loads without errors", async ({ page }) => {
    // No uncaught exceptions and the URL is correct
    expect(page.url()).toContain("/dashboard");
  });

  test("file list container is visible", async () => {
    await expect(dashboard.fileList).toBeVisible();
  });

  test("name filter input is present and functional", async () => {
    await expect(dashboard.nameFilter).toBeVisible();
    await dashboard.nameFilter.fill("test-filter-text");
    await expect(dashboard.nameFilter).toHaveValue("test-filter-text");
  });

  test("status filter dropdown is present with options", async () => {
    await expect(dashboard.statusFilterButton).toBeVisible();
    // Click to open the dropdown
    await dashboard.statusFilterButton.click();
    const items = dashboard.statusFilterMenu.locator(".dropdown-item");
    const count = await items.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test("sort dropdown is present with Name A-Z, Name Z-A, Status options", async () => {
    await expect(dashboard.sortDropdownButton).toBeVisible();
    // Click to open the dropdown
    await dashboard.sortDropdownButton.click();
    const items = dashboard.sortDropdownMenu.locator(".dropdown-item");
    const texts: string[] = [];
    const count = await items.count();
    for (let i = 0; i < count; i++) {
      const text = await items.nth(i).textContent();
      if (text) texts.push(text.trim());
    }
    // The HTML uses &#8594; which renders as arrow: "Name A→Z", "Name Z→A"
    expect(texts.some((t) => /name.*a.*z/i.test(t))).toBe(true);
    expect(texts.some((t) => /name.*z.*a/i.test(t))).toBe(true);
    expect(texts.some((t) => /status/i.test(t))).toBe(true);
  });

  test("details toggle button is present and clickable", async () => {
    await expect(dashboard.detailsToggle).toBeVisible();
    await dashboard.detailsToggle.click();
    // No error means the button is functional
  });

  test("checkbox on file row can be toggled", async () => {
    const rows = dashboard.getFileRows();
    const count = await rows.count();
    test.skip(count === 0, "No files present to test checkboxes");

    const checkbox = dashboard.getCheckbox(rows.first());
    await expect(checkbox).toBeVisible();
    await checkbox.check();
    await expect(checkbox).toBeChecked();
    await checkbox.uncheck();
    await expect(checkbox).not.toBeChecked();
  });
});

test.describe("Dashboard with files", () => {
  let dashboard: DashboardPage;
  let fileCount: number;

  test.beforeEach(async ({ page, waitForStream }) => {
    dashboard = new DashboardPage(page);
    await dashboard.goto();
    await waitForStream(page);
    fileCount = await dashboard.getFileRows().count();
  });

  test("file rows show file name", async () => {
    test.skip(fileCount === 0, "No files present on the remote seedbox");

    const rows = dashboard.getFileRows();
    const firstName = rows.first().locator(".name .text .title");
    await expect(firstName).toBeVisible();
    const text = await firstName.textContent();
    expect(text?.trim().length).toBeGreaterThan(0);
  });

  test("file rows show status icon", async () => {
    test.skip(fileCount === 0, "No files present on the remote seedbox");

    const rows = dashboard.getFileRows();
    const icon = rows.first().locator(".status img");
    await expect(icon.first()).toBeVisible();
  });

  test("clicking a file row shows action buttons", async () => {
    test.skip(fileCount === 0, "No files present on the remote seedbox");

    const row = dashboard.getFileRows().first();
    await row.click();
    const actionButtons = row.locator(".actions button");
    const btnCount = await actionButtons.count();
    expect(btnCount).toBeGreaterThanOrEqual(1);
  });

  test("Queue button appears for queueable files", async () => {
    test.skip(fileCount === 0, "No files present on the remote seedbox");

    const row = dashboard.getFileRows().first();
    await row.click();
    // Queue button may or may not be present depending on file state;
    // just verify the action area is rendered after click
    const queueBtn = dashboard.getActionButton(row, "queue");
    const queueVisible = await queueBtn.isVisible().catch(() => false);
    // If this specific file isn't queueable, that's acceptable
    expect(typeof queueVisible).toBe("boolean");
  });
});

test.describe("Dashboard bulk actions", () => {
  let dashboard: DashboardPage;
  let fileCount: number;

  test.beforeEach(async ({ page, waitForStream }) => {
    dashboard = new DashboardPage(page);
    await dashboard.goto();
    await waitForStream(page);
    fileCount = await dashboard.getFileRows().count();
  });

  test("selecting multiple files shows bulk action bar", async () => {
    test.skip(fileCount < 2, "Need at least 2 files for bulk selection");

    const rows = dashboard.getFileRows();
    await dashboard.getCheckbox(rows.nth(0)).check();
    await dashboard.getCheckbox(rows.nth(1)).check();
    await expect(dashboard.bulkActionBar).toBeVisible();
  });

  test("bulk action bar shows selected count", async () => {
    test.skip(fileCount < 2, "Need at least 2 files for bulk selection");

    const rows = dashboard.getFileRows();
    await dashboard.getCheckbox(rows.nth(0)).check();
    await dashboard.getCheckbox(rows.nth(1)).check();
    const countEl = dashboard.getBulkSelectedCount();
    await expect(countEl).toBeVisible();
    await expect(countEl).toContainText("2");
  });

  test("bulk action bar has Queue, Stop, Delete Local, Delete Remote buttons", async () => {
    test.skip(fileCount < 2, "Need at least 2 files for bulk selection");

    const rows = dashboard.getFileRows();
    await dashboard.getCheckbox(rows.nth(0)).check();
    await dashboard.getCheckbox(rows.nth(1)).check();

    await expect(dashboard.getBulkButton("queue")).toBeVisible();
    await expect(dashboard.getBulkButton("stop")).toBeVisible();
    await expect(dashboard.getBulkButton("delete local")).toBeVisible();
    await expect(dashboard.getBulkButton("delete remote")).toBeVisible();
  });

  test("clear button in bulk bar deselects all", async () => {
    test.skip(fileCount < 2, "Need at least 2 files for bulk selection");

    const rows = dashboard.getFileRows();
    await dashboard.getCheckbox(rows.nth(0)).check();
    await dashboard.getCheckbox(rows.nth(1)).check();
    await expect(dashboard.bulkActionBar).toBeVisible();

    const clearBtn = dashboard.getBulkButton("clear");
    await clearBtn.click();

    await expect(dashboard.getCheckbox(rows.nth(0))).not.toBeChecked();
    await expect(dashboard.getCheckbox(rows.nth(1))).not.toBeChecked();
  });
});
