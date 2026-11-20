import { defineConfig, devices } from "@playwright/test";

const isCI = !!process.env.CI;

/**
 * Playwright config — first E2E framework in this repo.
 *
 * Two `webServer` entries:
 *   1. The Vite dev server (`pnpm dev`).
 *   2. The backend, started via `docker compose up -d backend` locally.
 *      In CI the backend already runs as a service container, so we
 *      skip this (`cmd: 'true'` is a no-op).
 *
 * Chromium only this phase; Phase 10 broadens the matrix per the
 * roadmap.
 */
export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  fullyParallel: false,
  // All specs share one live dev DB and the same seeded fixture users
  // (and profile-editor revokes sessions on password change), so run serially.
  workers: 1,
  retries: 0,
  reporter: isCI ? "github" : "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: "pnpm dev",
      url: "http://localhost:5173",
      reuseExistingServer: !isCI,
      timeout: 120_000,
    },
    {
      command: isCI
        ? "cmd /c exit 0"
        : "docker compose -f ../docker-compose.yml up -d backend",
      url: "http://localhost:8000/healthz",
      reuseExistingServer: true,
      timeout: 120_000,
      ignoreHTTPSErrors: true,
    },
  ],
});
