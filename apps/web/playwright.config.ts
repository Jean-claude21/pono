import { defineConfig } from "@playwright/test";

// The console runs against a scripted stand-in for the service (tests/e2e/mock-service.mjs).
// PONO_CHROMIUM lets a machine without the bundled browser point at one it already has.
const CONSOLE_PORT = 3100;
const MOCK_PORT = 8123;

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 60_000,
  reporter: [["list"]],
  use: {
    baseURL: `http://localhost:${CONSOLE_PORT}`,
    viewport: { width: 1440, height: 900 },
    launchOptions: process.env.PONO_CHROMIUM ? { executablePath: process.env.PONO_CHROMIUM } : {},
  },
  webServer: [
    {
      command: "node tests/e2e/mock-service.mjs",
      port: MOCK_PORT,
      env: { MOCK_PORT: String(MOCK_PORT) },
      reuseExistingServer: false,
    },
    {
      command: `pnpm exec vite --port ${CONSOLE_PORT} --strictPort`,
      port: CONSOLE_PORT,
      env: { PONO_API_URL: `http://localhost:${MOCK_PORT}` },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
