import { test, expect } from "./fixtures";
import { SettingsPage } from "./pages/settings.page";

test.describe("Settings Page", () => {
  let settings: SettingsPage;

  test.beforeEach(async ({ page }) => {
    settings = new SettingsPage(page);
    await settings.goto();
  });

  test("page loads and shows all major sections", async () => {
    for (const section of [
      "Server",
      "AutoQueue",
      "Staging Directory",
      "Archive Extraction",
      "Integrity Check",
      "File Discovery",
      "Connections",
      "Logging",
      "Other Settings",
      "Notifications",
      "Integrations",
    ]) {
      await expect(settings.getSection(section)).toBeVisible();
    }
    // Advanced LFTP is collapsed by default but its header should still be visible
    const advancedHeader = settings.page.locator(
      "h3.card-header.collapsible-header",
      { hasText: "Advanced LFTP" }
    );
    await expect(advancedHeader).toBeVisible();
  });

  test("text field change saves to backend", async ({ apiGet, apiSetConfig }) => {
    const configBefore = await apiGet("/server/config/get");
    const originalAddress = configBefore.lftp.remote_address;

    try {
      const field = settings.getTextInput("Server Address");
      // Wait for the field to be enabled (config loaded via SSE)
      await expect(field).toBeEnabled({ timeout: 5000 });
      const testValue = "e2e-test-server";
      // fill() already clears the input before typing — calling clear()
      // separately can race with Angular's signal-driven re-render of the
      // ngModel binding and reset the field before fill() runs.
      await field.fill(testValue);
      // Blur triggers any pending change events and ensures Angular
      // processes the final value through the debounce pipeline.
      await field.blur();

      // Poll the API until the value is saved (debounce is 1 s)
      await expect
        .poll(
          async () => {
            const config = await apiGet("/server/config/get");
            return config.lftp.remote_address;
          },
          { timeout: 8000 }
        )
        .toBe(testValue);
    } finally {
      await apiSetConfig("lftp", "remote_address", originalAddress ?? "");
    }
  });

  test("checkbox toggle saves to backend", async ({ apiGet }) => {
    const checkbox = settings.getCheckbox("Verbose LFTP Logging");
    const wasBefore = await checkbox.isChecked();
    const expected = !wasBefore;

    await checkbox.click();

    try {
      // Poll the API until the value is saved
      await expect
        .poll(
          async () => {
            const config = await apiGet("/server/config/get");
            return config.general.verbose;
          },
          { timeout: 5000 }
        )
        .toBe(expected);
    } finally {
      // Toggle back to restore original state
      await checkbox.click();

      await expect
        .poll(
          async () => {
            const config = await apiGet("/server/config/get");
            return config.general.verbose;
          },
          { timeout: 5000 }
        )
        .toBe(wasBefore);
    }
  });

  test("password field masks input", async () => {
    const field = settings.getTextInput("Server Password");
    await expect(field).toHaveAttribute("type", "password");
  });

  test("select dropdown changes value and saves to backend", async ({
    apiGet,
  }) => {
    // Read the current value so we can restore it
    const configBefore = await apiGet("/server/config/get");
    const originalFormat = configBefore.logging.log_format;

    const select = settings.getSelect("Log Format");

    try {
      await select.selectOption("json");
      // Poll the API until the value is saved
      await expect
        .poll(
          async () => {
            const config = await apiGet("/server/config/get");
            return config.logging.log_format;
          },
          { timeout: 5000 }
        )
        .toBe("json");
    } finally {
      // Restore the original log format
      await select.selectOption(String(originalFormat));
      await expect
        .poll(
          async () => {
            const config = await apiGet("/server/config/get");
            return config.logging.log_format;
          },
          { timeout: 5000 }
        )
        .toBe(originalFormat);
    }
  });

  test("Advanced LFTP section is collapsed by default", async ({ page }) => {
    const header = page.locator("h3.card-header.collapsible-header", {
      hasText: "Advanced LFTP",
    });
    const card = header.locator("xpath=..");
    // When collapsed, Angular @if removes the card-body from the DOM
    const collapseBody = card.locator("app-option");
    await expect(collapseBody).toHaveCount(0);
  });

  test("clicking Advanced LFTP header expands the section", async ({
    page,
  }) => {
    await settings.expandSection("Advanced LFTP");

    // After expanding, the card-body with options should be visible
    const header = page.locator("h3.card-header.collapsible-header", {
      hasText: "Advanced LFTP",
    });
    const body = header.locator("xpath=..").locator(".card-body");
    await expect(body).toBeVisible();
  });

  test("expanded Advanced LFTP section shows all 7 advanced options", async ({
    page,
  }) => {
    await settings.expandSection("Advanced LFTP");

    const section = settings.getSection("Advanced LFTP");
    const options = section.locator("app-option");
    await expect(options).toHaveCount(7);
  });

  test("restart notification appears after config change", async ({ apiGet, apiSetConfig }) => {
    const configBefore = await apiGet("/server/config/get");
    const originalAddress = configBefore.lftp.remote_address;

    try {
      const field = settings.getTextInput("Server Address");
      // fill() already clears before typing — calling clear() separately
      // races with Angular's signal-driven re-render and can reset the
      // field before fill() runs.
      await expect(field).toBeEnabled();
      await field.fill("trigger-restart-notice-" + Date.now());
      await field.blur();

      const notification = settings.getRestartNotification();
      await expect(notification).toBeVisible({ timeout: 5000 });
    } finally {
      await apiSetConfig("lftp", "remote_address", originalAddress ?? "");
    }
  });

  test("Web GUI Port field shows current port value", async ({ apiGet }) => {
    const config = await apiGet("/server/config/get");
    const portField = settings.getTextInput("Web GUI Port");
    await expect(portField).toBeVisible();
    await expect(portField).toHaveValue(String(config.web.port));
  });

  test("API Key field is a password field", async () => {
    const otherSettings = settings.getSection("Other Settings");
    const field = otherSettings
      .locator("app-option", { hasText: "API Key" })
      .locator("input[type='text'], input[type='password']");
    await expect(field).toHaveAttribute("type", "password");
  });
});

test.describe("Settings — Staging Directory", () => {
  test("staging path text field saves to backend", async ({
    page,
    apiGet,
    apiSetConfig,
  }) => {
    const settings = new SettingsPage(page);
    await settings.goto();

    const configBefore = await apiGet("/server/config/get");
    const originalPath = configBefore.controller.staging_path;

    try {
      const field = settings.getTextInput("Staging Path");
      await expect(field).toBeEnabled();
      const testValue = "/tmp/e2e-staging-" + Date.now();
      await field.fill(testValue);
      await field.blur();

      await expect
        .poll(
          async () => {
            const config = await apiGet("/server/config/get");
            return config.controller.staging_path;
          },
          { timeout: 5000 }
        )
        .toBe(testValue);
    } finally {
      await apiSetConfig("controller", "staging_path", originalPath ?? "");
    }
  });

  test("use staging directory checkbox toggles and saves", async ({
    page,
    apiGet,
  }) => {
    const settings = new SettingsPage(page);
    await settings.goto();

    const checkbox = settings.getCheckbox("Use staging directory");
    const wasBefore = await checkbox.isChecked();
    const expected = !wasBefore;

    await checkbox.click();

    try {
      await expect
        .poll(
          async () => {
            const config = await apiGet("/server/config/get");
            return config.controller.use_staging;
          },
          { timeout: 5000 }
        )
        .toBe(expected);
    } finally {
      await checkbox.click();
      await expect
        .poll(
          async () => {
            const config = await apiGet("/server/config/get");
            return config.controller.use_staging;
          },
          { timeout: 5000 }
        )
        .toBe(wasBefore);
    }
  });
});

test.describe("Settings — Archive Extraction", () => {
  test("extract in downloads directory checkbox toggles and saves", async ({
    page,
    apiGet,
  }) => {
    const settings = new SettingsPage(page);
    await settings.goto();

    const checkbox = settings.getCheckbox(
      "Extract archives in the downloads directory"
    );
    const wasBefore = await checkbox.isChecked();
    const expected = !wasBefore;

    await checkbox.click();

    try {
      await expect
        .poll(
          async () => {
            const config = await apiGet("/server/config/get");
            return config.controller.use_local_path_as_extract_path;
          },
          { timeout: 5000 }
        )
        .toBe(expected);
    } finally {
      await checkbox.click();
      await expect
        .poll(
          async () => {
            const config = await apiGet("/server/config/get");
            return config.controller.use_local_path_as_extract_path;
          },
          { timeout: 5000 }
        )
        .toBe(wasBefore);
    }
  });
});

test.describe("Settings — Integrity Check", () => {
  test("verify transfers checkbox and algorithm select are present", async ({
    page,
  }) => {
    const settings = new SettingsPage(page);
    await settings.goto();

    const section = settings.getSection("Integrity Check");
    await expect(section).toBeVisible();

    const verifyCheckbox = settings.getCheckbox(
      "Verify transfers inline"
    );
    await expect(verifyCheckbox).toBeVisible();

    const algorithmSelect = settings.getSelect("Hash Algorithm");
    await expect(algorithmSelect).toBeVisible();
  });

  test("hash algorithm select changes and saves to backend", async ({
    page,
    apiGet,
    apiSetConfig,
    waitForStream,
  }) => {
    // The Hash Algorithm select is disabled by buildValidateContext() unless
    // validate.enabled is true (see settings-page.component.ts). Enable
    // post-download validation here, then restore in the finally block.
    const configBefore = await apiGet("/server/config/get");
    const originalAlgorithm = configBefore.validate.algorithm;
    const originalValidateEnabled = configBefore.validate.enabled;

    if (!originalValidateEnabled) {
      await apiSetConfig("validate", "enabled", "True");
    }

    const settings = new SettingsPage(page);
    await settings.goto();
    await waitForStream(page);

    const select = settings.getSelect("Hash Algorithm");
    // Wait for the SSE config to arrive AND for buildValidateContext to
    // unlock the select (the disable rule needs validate.enabled === true).
    await expect(select).toBeEnabled({ timeout: 10_000 });
    await expect(select).toHaveValue(/^(md5|sha1|sha256)$/);

    // Pick a different algorithm than current
    const newValue = originalAlgorithm === "sha256" ? "md5" : "sha256";

    try {
      await select.selectOption(newValue);

      await expect
        .poll(
          async () => {
            const config = await apiGet("/server/config/get");
            return config.validate.algorithm;
          },
          { timeout: 5000 }
        )
        .toBe(newValue);
    } finally {
      await apiSetConfig("validate", "algorithm", String(originalAlgorithm));
      if (!originalValidateEnabled) {
        await apiSetConfig("validate", "enabled", "False");
      }
    }
  });
});

test.describe("Settings — Connections", () => {
  test("Max Parallel Downloads field saves to backend", async ({
    page,
    apiGet,
    apiSetConfig,
  }) => {
    const settings = new SettingsPage(page);
    await settings.goto();

    const configBefore = await apiGet("/server/config/get");
    const originalValue = configBefore.lftp.num_max_parallel_downloads;

    try {
      const field = settings.getTextInput("Max Parallel Downloads");
      await expect(field).toBeEnabled();
      await field.fill("7");
      await field.blur();

      await expect
        .poll(
          async () => {
            const config = await apiGet("/server/config/get");
            return String(config.lftp.num_max_parallel_downloads);
          },
          { timeout: 5000 }
        )
        .toBe("7");
    } finally {
      await apiSetConfig(
        "lftp",
        "num_max_parallel_downloads",
        String(originalValue)
      );
    }
  });
});

test.describe("Settings — Notifications", () => {
  test("Discord and Telegram webhook fields are present", async ({
    page,
  }) => {
    const settings = new SettingsPage(page);
    await settings.goto();

    const section = settings.getSection("Notifications");
    await expect(section).toBeVisible();

    // Discord Webhook URL is a password field
    const discordField = section
      .locator("app-option", { hasText: "Discord Webhook URL" })
      .locator("input[type='text'], input[type='password']");
    await expect(discordField).toBeVisible();

    // Telegram Bot Token is a password field
    const telegramTokenField = section
      .locator("app-option", { hasText: "Telegram Bot Token" })
      .locator("input[type='text'], input[type='password']");
    await expect(telegramTokenField).toBeVisible();

    // Telegram Chat ID is a text field
    const telegramChatField = section
      .locator("app-option", { hasText: "Telegram Chat ID" })
      .locator("input[type='text'], input[type='password']");
    await expect(telegramChatField).toBeVisible();
  });
});

test.describe("Settings — Logging", () => {
  test("Log Level dropdown persists selected value", async ({
    page,
    apiGet,
  }) => {
    const settings = new SettingsPage(page);
    await settings.goto();

    const configBefore = await apiGet("/server/config/get");
    const originalLevel = configBefore.general.log_level;

    const select = settings.getSelect("Log Level");
    const newValue = originalLevel === "DEBUG" ? "WARNING" : "DEBUG";

    try {
      await select.selectOption(newValue);

      await expect
        .poll(
          async () => {
            const config = await apiGet("/server/config/get");
            return config.general.log_level;
          },
          { timeout: 5000 }
        )
        .toBe(newValue);

      // Reload the page and verify the value persists. settings.goto()
      // only waits for Angular bootstrap (sidebar render), not for SSE
      // config delivery, so wait for the select to become enabled — its
      // disabled gate is `value() === null || value() === undefined`, so
      // an enabled select means the model has received the SSE value.
      await settings.goto();
      const reloadedSelect = settings.getSelect("Log Level");
      await expect(reloadedSelect).toBeEnabled({ timeout: 10_000 });
      await expect(reloadedSelect).toHaveValue(newValue);
    } finally {
      await select.selectOption(String(originalLevel));
      await expect
        .poll(
          async () => {
            const config = await apiGet("/server/config/get");
            return config.general.log_level;
          },
          { timeout: 5000 }
        )
        .toBe(originalLevel);
    }
  });
});
