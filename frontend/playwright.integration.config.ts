import { defineConfig, devices } from "@playwright/test";

const port = Number(process.env.PW_PORT ?? 13110);
const apiPort = Number(process.env.PW_API_PORT ?? 18001);

// Build with NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:18001 first.
// No browser route interception: requests reach FastAPI and temporary SQLite.
export default defineConfig({
  testDir: "e2e",
  testMatch: "**/*.integration.ts",
  workers: 1,
  retries: 0,
  use: {
    ...devices["Desktop Chrome"],
    baseURL: `http://127.0.0.1:${port}`,
    channel: process.env.PW_CHANNEL || undefined,
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `python -m uvicorn integration_api:app --app-dir e2e --host 127.0.0.1 --port ${apiPort}`,
      url: `http://127.0.0.1:${apiPort}/health`,
      env: { ALLOWED_ORIGINS: `http://127.0.0.1:${port}` },
      reuseExistingServer: false,
    },
    {
      command: `npm run start -- -H 127.0.0.1 -p ${port}`,
      url: `http://127.0.0.1:${port}`,
      reuseExistingServer: false,
    },
  ],
});
