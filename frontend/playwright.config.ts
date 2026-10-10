import { defineConfig, devices } from "@playwright/test";

// End-to-end tests drive the production build in a real browser. Every API
// call is answered from fixtures (see e2e/fixtures/make_fixtures.py), so the
// tests never depend on the live API or on the market-data provider.
//
// Files are named *.e2e.ts so Vitest, which picks up *.test.ts and *.spec.ts,
// does not try to run them.

const PORT = 3100;

export default defineConfig({
  testDir: "e2e",
  testMatch: "**/*.e2e.ts",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "retain-on-failure",
    // CI installs Playwright's Chromium; locally an installed browser can be
    // used instead, e.g. PW_CHANNEL=msedge or PW_CHANNEL=chrome.
    channel: process.env.PW_CHANNEL || undefined,
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], channel: process.env.PW_CHANNEL || undefined } },
    { name: "mobile", use: { ...devices["Pixel 7"], channel: process.env.PW_CHANNEL || undefined } },
  ],
  webServer: {
    command: `npm run start -- -H 127.0.0.1 -p ${PORT}`,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
