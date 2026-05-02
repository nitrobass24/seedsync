import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: false, // tests share a Docker container per file
  // ubuntu-latest has 4 vCPUs and we run a chromium per worker plus the
  // SeedSync Docker container, so > 4 workers oversubscribes CPU and
  // slows the suite overall.
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
