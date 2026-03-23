import { test, expect } from "./fixtures";
import { PathPairsPage } from "./pages/path-pairs.page";

test.describe("Path Pairs", () => {
  let pathPairs: PathPairsPage;

  // Clean up all path pairs before each test to ensure clean state
  test.beforeEach(async ({ page, apiFetch }) => {
    const res = await apiFetch("/server/pathpairs");
    if (res.ok) {
      const pairs = await res.json();
      for (const pair of pairs) {
        await apiFetch(`/server/pathpairs/${pair.id}`, {
          method: "DELETE",
        });
      }
    }

    pathPairs = new PathPairsPage(page);
    await pathPairs.goto();
  });

  // Clean up all path pairs after each test
  test.afterEach(async ({ apiFetch }) => {
    const res = await apiFetch("/server/pathpairs");
    if (!res.ok) return;
    const pairs = await res.json();
    for (const pair of pairs) {
      await apiFetch(`/server/pathpairs/${pair.id}`, {
        method: "DELETE",
      });
    }
  });

  test("empty state shows No path pairs message", async () => {
    await expect(pathPairs.emptyMessage).toBeVisible();
  });

  test("click Add shows the form", async ({ page }) => {
    await pathPairs.addButton.click();
    const form = page.locator(".pair-form");
    await expect(form.first()).toBeVisible();
  });

  test("fill and save creates a pair via API", async ({ apiFetch }) => {
    await pathPairs.addButton.click();
    await pathPairs.fillForm({
      name: "e2e-test-pair",
      remotePath: "/remote/e2e",
      localPath: "/local/e2e",
    });
    await pathPairs.clickSave();

    // Poll the API until the pair appears
    await expect
      .poll(
        async () => {
          const res = await apiFetch("/server/pathpairs");
          if (!res.ok) return undefined;
          const pairs = await res.json();
          return pairs.find(
            (p: { name: string }) => p.name === "e2e-test-pair"
          );
        },
        { timeout: 5000 }
      )
      .toEqual(
        expect.objectContaining({
          name: "e2e-test-pair",
          remote_path: "/remote/e2e",
          local_path: "/local/e2e",
        })
      );
  });

  test("created pair appears in the list", async ({ page }) => {
    await pathPairs.addButton.click();
    await pathPairs.fillForm({
      name: "visible-pair",
      remotePath: "/remote/visible",
      localPath: "/local/visible",
    });
    await pathPairs.clickSave();

    // Wait for the form to close (save completes async)
    await expect(page.locator(".pair-form")).not.toBeVisible({ timeout: 10_000 });

    const row = pathPairs.getPairByName("visible-pair");
    await expect(row).toBeVisible({ timeout: 10_000 });
  });

  test("duplicate name shows error message", async ({ page, apiFetch }) => {
    // Create a pair via API first
    await apiFetch("/server/pathpairs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "dup-pair",
        remote_path: "/remote/dup",
        local_path: "/local/dup",
        enabled: true,
      }),
    });

    // Reload to see the pair
    await pathPairs.goto();
    await pathPairs.getPairByName("dup-pair").waitFor({ timeout: 10_000 });

    // Try to add a pair with the same name
    await pathPairs.addButton.click();
    await pathPairs.fillForm({
      name: "dup-pair",
      remotePath: "/remote/dup2",
      localPath: "/local/dup2",
    });
    await pathPairs.clickSave();

    const error = pathPairs.getErrorMessage();
    await expect(error).toBeVisible();
  });

  test("click Edit shows form with existing values", async ({
    page,
    apiFetch,
  }) => {
    // Create a pair via API
    await apiFetch("/server/pathpairs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "edit-me",
        remote_path: "/remote/edit",
        local_path: "/local/edit",
        enabled: true,
      }),
    });

    await pathPairs.goto();

    const row = pathPairs.getPairByName("edit-me");
    await row.waitFor({ timeout: 10_000 });
    await pathPairs.getEditButton(row).click();

    const form = page.locator(".pair-form");
    await expect(form.first()).toBeVisible();

    // Verify the form contains the existing values
    const inputs = form.first().locator("input");
    await expect(inputs.first()).toHaveValue("edit-me");
    await expect(inputs.nth(1)).toHaveValue("/remote/edit");
    await expect(inputs.nth(2)).toHaveValue("/local/edit");
  });

  test("edit and save updates the pair via API", async ({ apiFetch }) => {
    // Create a pair via API
    await apiFetch("/server/pathpairs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "update-me",
        remote_path: "/remote/old",
        local_path: "/local/old",
        enabled: true,
      }),
    });

    await pathPairs.goto();

    const row = pathPairs.getPairByName("update-me");
    await row.waitFor({ timeout: 10_000 });
    await pathPairs.getEditButton(row).click();

    await pathPairs.fillForm({
      remotePath: "/remote/updated",
      localPath: "/local/updated",
    });
    await pathPairs.clickSave();

    // Poll the API until the pair is updated
    await expect
      .poll(
        async () => {
          const res = await apiFetch("/server/pathpairs");
          if (!res.ok) return undefined;
          const pairs = await res.json();
          return pairs.find(
            (p: { name: string }) => p.name === "update-me"
          );
        },
        { timeout: 5000 }
      )
      .toEqual(
        expect.objectContaining({
          remote_path: "/remote/updated",
          local_path: "/local/updated",
        })
      );
  });

  test("delete requires two clicks with confirmation", async ({
    page,
    apiFetch,
  }) => {
    // Create a pair via API
    await apiFetch("/server/pathpairs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "delete-me",
        remote_path: "/remote/del",
        local_path: "/local/del",
        enabled: true,
      }),
    });

    await pathPairs.goto();

    const row = pathPairs.getPairByName("delete-me");
    await row.waitFor({ timeout: 10_000 });
    const deleteBtn = pathPairs.getDeleteButton(row);

    // First click should show confirmation
    await deleteBtn.click();
    // After first click, button text changes to "Confirm?"
    await expect(deleteBtn).toContainText("Confirm");

    // Second click actually deletes
    await deleteBtn.click();

    // Assert the row is gone
    await expect(row).not.toBeVisible({ timeout: 5000 });
  });

  test("delete removes the pair via API", async ({ apiFetch }) => {
    // Create a pair via API
    await apiFetch("/server/pathpairs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "gone-pair",
        remote_path: "/remote/gone",
        local_path: "/local/gone",
        enabled: true,
      }),
    });

    await pathPairs.goto();

    const row = pathPairs.getPairByName("gone-pair");
    await row.waitFor({ timeout: 10_000 });
    const deleteBtn = pathPairs.getDeleteButton(row);

    // First click to show confirmation
    await deleteBtn.click();
    // After first click, button text changes to "Confirm?"
    await expect(deleteBtn).toContainText("Confirm");

    // Second click to confirm delete
    await deleteBtn.click();

    // Poll the API until the pair is gone
    await expect
      .poll(
        async () => {
          const res = await apiFetch("/server/pathpairs");
          if (!res.ok) return undefined;
          const pairs = await res.json();
          return pairs.find(
            (p: { name: string }) => p.name === "gone-pair"
          );
        },
        { timeout: 5000 }
      )
      .toBeUndefined();
  });

  test("enable/disable toggle updates via API", async ({ apiFetch }) => {
    // Create an enabled pair via API
    await apiFetch("/server/pathpairs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "toggle-pair",
        remote_path: "/remote/toggle",
        local_path: "/local/toggle",
        enabled: true,
      }),
    });

    await pathPairs.goto();

    const row = pathPairs.getPairByName("toggle-pair");
    await row.waitFor({ timeout: 10_000 });
    const toggle = pathPairs.getEnabledToggle(row);

    // Toggle off
    await toggle.click();

    // Poll the API until the pair is disabled
    await expect
      .poll(
        async () => {
          const res = await apiFetch("/server/pathpairs");
          if (!res.ok) return undefined;
          const pairs = await res.json();
          const pair = pairs.find(
            (p: { name: string }) => p.name === "toggle-pair"
          );
          return pair?.enabled;
        },
        { timeout: 5000 }
      )
      .toBe(false);
  });
});
