import { test, expect } from "./fixtures";
import { AutoQueuePage } from "./pages/autoqueue.page";

test.describe("AutoQueue Page", () => {
  let autoqueue: AutoQueuePage;
  let savedEnabled: string;
  let savedPatternsOnly: string;

  test.beforeEach(async ({ apiGet, apiSetConfig }) => {
    // Save current autoqueue config
    const config = await apiGet("/server/config/get");
    savedEnabled = String(config.autoqueue?.enabled ?? "false");
    savedPatternsOnly = String(config.autoqueue?.patterns_only ?? "false");
  });

  test.afterEach(async ({ apiSetConfig, apiGet }) => {
    // Clean up any test patterns
    try {
      const data = await apiGet("/server/autoqueue/get");
      const patterns: { pattern: string }[] = Array.isArray(data)
        ? data
        : data.patterns || [];
      for (const p of patterns) {
        if (p.pattern.startsWith("test-")) {
          await apiGet(
            `/server/autoqueue/remove/${encodeURIComponent(p.pattern)}`
          );
        }
      }
    } catch {
      // Ignore cleanup errors
    }

    // Restore autoqueue config
    await apiSetConfig("autoqueue", "enabled", savedEnabled);
    await apiSetConfig("autoqueue", "patterns_only", savedPatternsOnly);
  });

  test("when autoqueue disabled: page shows disabled message", async ({
    page,
    apiSetConfig,
    waitForStream,
  }) => {
    await apiSetConfig("autoqueue", "enabled", "false");
    await apiSetConfig("autoqueue", "patterns_only", "false");

    autoqueue = new AutoQueuePage(page);
    await autoqueue.goto();
    await waitForStream(page);

    const disabledMsg = page.locator("text=/disabled/i");
    await expect(disabledMsg).toBeVisible();
  });

  test("when autoqueue enabled but patterns_only disabled: shows all files message", async ({
    page,
    apiSetConfig,
    waitForStream,
  }) => {
    await apiSetConfig("autoqueue", "enabled", "true");
    await apiSetConfig("autoqueue", "patterns_only", "false");

    autoqueue = new AutoQueuePage(page);
    await autoqueue.goto();
    await waitForStream(page);

    const allFilesMsg = page.locator("text=/all files/i");
    await expect(allFilesMsg).toBeVisible();
  });

  test("when autoqueue enabled + patterns_only: shows active UI with input", async ({
    page,
    apiSetConfig,
    waitForStream,
  }) => {
    await apiSetConfig("autoqueue", "enabled", "true");
    await apiSetConfig("autoqueue", "patterns_only", "true");

    autoqueue = new AutoQueuePage(page);
    await autoqueue.goto();
    await waitForStream(page);

    await expect(autoqueue.patternInput).toBeVisible();
    await expect(autoqueue.addButton).toBeVisible();
  });

  test("add pattern via input + button click", async ({
    page,
    apiSetConfig,
    apiGet,
    waitForStream,
  }) => {
    await apiSetConfig("autoqueue", "enabled", "true");
    await apiSetConfig("autoqueue", "patterns_only", "true");

    autoqueue = new AutoQueuePage(page);
    await autoqueue.goto();
    await waitForStream(page);

    const testPattern = `test-btn-${Date.now()}`;
    await autoqueue.addPattern(testPattern);

    // Poll the API until the pattern appears
    await expect
      .poll(
        async () => {
          const data = await apiGet("/server/autoqueue/get");
          const raw = Array.isArray(data) ? data : data.patterns || [];
          // API returns [{pattern: "..."}] objects
          const patterns: string[] = raw.map((p: any) =>
            typeof p === "string" ? p : p.pattern
          );
          return patterns;
        },
        { timeout: 5000 }
      )
      .toContain(testPattern);

    // Cleanup: remove the pattern
    const patternItem = autoqueue.getPatternByText(testPattern);
    const removeBtn = autoqueue.getRemoveButton(patternItem);
    if (await removeBtn.isVisible().catch(() => false)) {
      await removeBtn.click();
    }
  });

  test("add pattern via input + Enter key", async ({
    page,
    apiSetConfig,
    apiGet,
    waitForStream,
  }) => {
    await apiSetConfig("autoqueue", "enabled", "true");
    await apiSetConfig("autoqueue", "patterns_only", "true");

    autoqueue = new AutoQueuePage(page);
    await autoqueue.goto();
    await waitForStream(page);

    const testPattern = `test-enter-${Date.now()}`;
    await autoqueue.patternInput.fill(testPattern);
    await autoqueue.patternInput.press("Enter");

    // Poll the API until the pattern appears
    await expect
      .poll(
        async () => {
          const data = await apiGet("/server/autoqueue/get");
          const raw = Array.isArray(data) ? data : data.patterns || [];
          // API returns [{pattern: "..."}] objects
          const patterns: string[] = raw.map((p: any) =>
            typeof p === "string" ? p : p.pattern
          );
          return patterns;
        },
        { timeout: 5000 }
      )
      .toContain(testPattern);

    // Cleanup
    const patternItem = autoqueue.getPatternByText(testPattern);
    const removeBtn = autoqueue.getRemoveButton(patternItem);
    if (await removeBtn.isVisible().catch(() => false)) {
      await removeBtn.click();
    }
  });

  test("remove pattern via remove button", async ({
    page,
    apiSetConfig,
    apiGet,
    waitForStream,
  }) => {
    await apiSetConfig("autoqueue", "enabled", "true");
    await apiSetConfig("autoqueue", "patterns_only", "true");

    autoqueue = new AutoQueuePage(page);
    await autoqueue.goto();
    await waitForStream(page);

    // Add a pattern first
    const testPattern = `test-remove-${Date.now()}`;
    await autoqueue.addPattern(testPattern);

    // Poll until it appears in the API
    await expect
      .poll(
        async () => {
          const data = await apiGet("/server/autoqueue/get");
          const raw = Array.isArray(data) ? data : data.patterns || [];
          // API returns [{pattern: "..."}] objects
          const patterns: string[] = raw.map((p: any) =>
            typeof p === "string" ? p : p.pattern
          );
          return patterns;
        },
        { timeout: 5000 }
      )
      .toContain(testPattern);

    // Verify it's visible in the UI
    const patternItem = autoqueue.getPatternByText(testPattern);
    await expect(patternItem).toBeVisible();

    // Remove it
    const removeBtn = autoqueue.getRemoveButton(patternItem);
    await removeBtn.click();

    // Poll the API until it's gone
    await expect
      .poll(
        async () => {
          const data = await apiGet("/server/autoqueue/get");
          const raw = Array.isArray(data) ? data : data.patterns || [];
          // API returns [{pattern: "..."}] objects
          const patterns: string[] = raw.map((p: any) =>
            typeof p === "string" ? p : p.pattern
          );
          return patterns;
        },
        { timeout: 5000 }
      )
      .not.toContain(testPattern);
  });

  test("duplicate pattern shows error", async ({
    page,
    apiSetConfig,
    waitForStream,
  }) => {
    await apiSetConfig("autoqueue", "enabled", "true");
    await apiSetConfig("autoqueue", "patterns_only", "true");

    autoqueue = new AutoQueuePage(page);
    await autoqueue.goto();
    await waitForStream(page);

    const testPattern = `test-dup-${Date.now()}`;
    await autoqueue.addPattern(testPattern);

    // Try adding the same pattern again
    await autoqueue.addPattern(testPattern);

    const error = autoqueue.getErrorMessage();
    await expect(error).toBeVisible();

    // Cleanup
    const patternItem = autoqueue.getPatternByText(testPattern);
    const removeBtn = autoqueue.getRemoveButton(patternItem);
    if (await removeBtn.isVisible().catch(() => false)) {
      await removeBtn.click();
    }
  });

  test("added pattern is visible in list", async ({
    page,
    apiSetConfig,
    waitForStream,
  }) => {
    await apiSetConfig("autoqueue", "enabled", "true");
    await apiSetConfig("autoqueue", "patterns_only", "true");

    autoqueue = new AutoQueuePage(page);
    await autoqueue.goto();
    await waitForStream(page);

    const testPattern = `test-visible-${Date.now()}`;
    await autoqueue.addPattern(testPattern);

    const patternItem = autoqueue.getPatternByText(testPattern);
    await expect(patternItem).toBeVisible();

    // Cleanup
    const removeBtn = autoqueue.getRemoveButton(patternItem);
    if (await removeBtn.isVisible().catch(() => false)) {
      await removeBtn.click();
    }
  });
});
