import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: false, // tests share a Docker container per file
  // ubuntu-latest has 4 vCPUs. Each worker runs its own chromium and
  // shares the host's CPU pool with the SeedSync container and runner
  // overhead — pushing past 4 oversubscribes and makes the suite
  // slower overall.
  workers: 4,
  retries: 0,
  reporter: [["html", { open: "never" }], ["list"]],
  use: {
    baseURL: process.env.BASE_URL || "http://localhost:8800",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { browserName: "chromium" },
    },
  ],
});
