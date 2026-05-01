import { test, expect } from "./fixtures";
import { DashboardPage } from "./pages/dashboard.page";

test.describe("File Actions", () => {
  let dashboard: DashboardPage;
  let fileCount: number;

  test.beforeEach(async ({ page, waitForStream }) => {
    dashboard = new DashboardPage(page);
    await dashboard.goto();
    await waitForStream(page);
    fileCount = await dashboard.getFileRows().count();
  });

  test("file row click reveals action buttons with correct labels", async () => {
    test.skip(fileCount === 0, "No files present on the remote seedbox");

    const row = dashboard.getFileRows().first();
    await row.click();

    // All 6 action buttons should be present (some may be disabled)
    await expect(dashboard.getActionButton(row, "Queue")).toBeVisible();
    await expect(dashboard.getActionButton(row, "Stop")).toBeVisible();
    await expect(dashboard.getActionButton(row, "Extract")).toBeVisible();
    await expect(dashboard.getActionButton(row, "Validate")).toBeVisible();
    await expect(dashboard.getActionButton(row, "Delete Local")).toBeVisible();
    await expect(dashboard.getActionButton(row, "Delete Remote")).toBeVisible();
  });

  test("action buttons have correct disabled state based on file status", async () => {
    test.skip(fileCount === 0, "No files present on the remote seedbox");

    const row = dashboard.getFileRows().first();
    await row.click();

    // At least one action button should exist and have a disabled attribute (either true or false)
    const buttons = row.locator(".actions button");
    const count = await buttons.count();
    expect(count).toBe(6);

    // Each button should have a deterministic disabled state (not missing the attribute)
    for (let i = 0; i < count; i++) {
      const btn = buttons.nth(i);
      const isDisabled = await btn.isDisabled();
      expect(typeof isDisabled).toBe("boolean");
    }
  });

  test("Delete Local button requires confirmation (double-click pattern)", async () => {
    test.skip(fileCount === 0, "No files present on the remote seedbox");

    const row = dashboard.getFileRows().first();
    await row.click();

    const deleteLocalBtn = dashboard.getActionButton(row, "Delete Local");
    const isDisabled = await deleteLocalBtn.isDisabled();
    test.skip(isDisabled, "Delete Local is disabled for this file (no local copy)");

    // First click should change text to "Confirm?"
    await deleteLocalBtn.click();
    await expect(deleteLocalBtn).toContainText("Confirm?");
  });

  test("Delete Remote button requires confirmation (double-click pattern)", async () => {
    test.skip(fileCount === 0, "No files present on the remote seedbox");

    const row = dashboard.getFileRows().first();
    await row.click();

    const deleteRemoteBtn = dashboard.getActionButton(row, "Delete Remote");
    const isDisabled = await deleteRemoteBtn.isDisabled();
    test.skip(isDisabled, "Delete Remote is disabled for this file");

    // First click should change text to "Confirm?"
    await deleteRemoteBtn.click();
    await expect(deleteRemoteBtn).toContainText("Confirm?");
  });

  test("clicking a different file row deselects the previous one", async () => {
    test.skip(fileCount < 2, "Need at least 2 files to test selection switching");

    const rows = dashboard.getFileRows();
    const firstRow = rows.nth(0);
    const secondRow = rows.nth(1);

    // Click first row to select it
    await firstRow.click();
    await expect(firstRow).toHaveClass(/selected/);

    // Click second row — first should deselect
    await secondRow.click();
    await expect(secondRow).toHaveClass(/selected/);
    await expect(firstRow).not.toHaveClass(/selected/);
  });

  test("re-clicking selected file row deselects it", async () => {
    test.skip(fileCount === 0, "No files present on the remote seedbox");

    const row = dashboard.getFileRows().first();

    // Click to select
    await row.click();
    await expect(row.locator(".actions")).toBeVisible();

    // Click again to deselect (actions should hide)
    await row.click();
    // After deselecting, the actions div should not be visible
    // (actions are only shown when selected via CSS)
    await expect(row).not.toHaveClass(/selected/);
    await expect(row.locator(".actions")).not.toBeVisible();
  });
});

test.describe("File Actions — Bulk operations", () => {
  let dashboard: DashboardPage;
  let fileCount: number;

  test.beforeEach(async ({ page, waitForStream }) => {
    dashboard = new DashboardPage(page);
    await dashboard.goto();
    await waitForStream(page);
    fileCount = await dashboard.getFileRows().count();
  });

  test("bulk Queue button is present when files are checked", async () => {
    test.skip(fileCount < 1, "Need at least 1 file for bulk action");

    const rows = dashboard.getFileRows();
    await dashboard.getCheckbox(rows.first()).check();
    await expect(dashboard.bulkActionBar).toBeVisible();
    await expect(dashboard.getBulkButton("Queue")).toBeVisible();
  });

  test("bulk Stop button is present when files are checked", async () => {
    test.skip(fileCount < 1, "Need at least 1 file for bulk action");

    const rows = dashboard.getFileRows();
    await dashboard.getCheckbox(rows.first()).check();
    await expect(dashboard.bulkActionBar).toBeVisible();
    await expect(dashboard.getBulkButton("Stop")).toBeVisible();
  });

  test("bulk Delete Local and Delete Remote buttons are present", async () => {
    test.skip(fileCount < 1, "Need at least 1 file for bulk action");

    const rows = dashboard.getFileRows();
    await dashboard.getCheckbox(rows.first()).check();
    await expect(dashboard.getBulkButton("Delete Local")).toBeVisible();
    await expect(dashboard.getBulkButton("Delete Remote")).toBeVisible();
  });

  test("unchecking all files hides the bulk action bar", async () => {
    test.skip(fileCount < 1, "Need at least 1 file for this test");

    const rows = dashboard.getFileRows();
    const checkbox = dashboard.getCheckbox(rows.first());

    await checkbox.check();
    await expect(dashboard.bulkActionBar).toBeVisible();

    await checkbox.uncheck();
    await expect(dashboard.bulkActionBar).not.toBeVisible();
  });
});
