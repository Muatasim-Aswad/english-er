import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  outputDir: process.env.ENGLISH_ER_E2E_ROOT
    ? `${process.env.ENGLISH_ER_E2E_ROOT}/playwright-results`
    : "test-results",
  fullyParallel: false,
  forbidOnly: true,
  workers: 1,
  reporter: "line",
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:8765",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "uv run --directory apps/backend python ../../scripts/e2e_server.py",
    cwd: "../..",
    reuseExistingServer: false,
    timeout: 30_000,
    url: "http://127.0.0.1:8765/api/v1/health",
  },
});
