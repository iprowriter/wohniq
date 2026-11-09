import { defineConfig, devices } from "@playwright/test";

// End-to-end tests for Lifestyle Match (e2e/). Starts the offline demo backend
// (WOHNIQ_DEMO=1: bundled data, no database, no network) and the production frontend.
//
//   npm run test:e2e          # build + run (first time: npx playwright install chromium)
//
// PW_CHROMIUM_PATH lets you point at an existing Chromium instead of Playwright's
// download (e.g. in sandboxes without access to the browser CDN).
const chromiumPath = process.env.PW_CHROMIUM_PATH;
const launchOptions = chromiumPath
  ? {
      executablePath: chromiumPath,
      args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
    }
  : {};

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    launchOptions,
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1366, height: 900 } } },
    { name: "mobile", use: { ...devices["Pixel 5"] } },
  ],
  webServer: [
    {
      command: "cd ../backend && WOHNIQ_DEMO=1 uv run uvicorn app.main:app --port 8000",
      url: "http://localhost:8000/api/v1/health",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: "npx next start -p 3000",
      url: "http://localhost:3000",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
