/**
 * Phase 9 adherence views: smoke + regression guards.
 *
 * Guards two regressions that unit tests can't catch (jsdom does no layout):
 *   1. Entry point — the medication list must link to the per-med adherence
 *      view (the list once linked only multi_sub_dose meds).
 *   2. Trend bars must have real height (they collapsed to 0px under a flexbox
 *      `items-end` bug). Playwright measures the rendered bounding box.
 * Plus a basic calendar render and a CSV-export download.
 *
 * Seeds a med + daily schedule via the UI and one backdated dose via the API
 * (`POST /api/doses` accepts `taken_at`), so the calendar/trend have real data.
 *
 * Skipped by default; run locally against the live stack:
 *
 *     just dev                                   # one terminal
 *     E2E_RUN_ADHERENCE=1 pnpm test:e2e adherence.spec.ts   # from frontend/
 *
 * Un-gated in CI once the docker stack lands there (Phase 10 roadmap item).
 */

import { test, expect } from "@playwright/test";
import {
  addSchedule,
  csrfHeaders,
  isE2eEnabled,
  login,
  medIdByName,
  setPlainDose,
} from "./helpers";

const TEST_EMAIL = process.env.E2E_DEMO_EMAIL ?? "demo@example.com";
const TEST_PASSWORD =
  process.env.E2E_USER_PASSWORD ?? "correct horse battery staple";
const API_BASE = process.env.E2E_API_BASE ?? "http://localhost:8000";

test.describe("Adherence views", () => {
  test.skip(
    !isE2eEnabled("E2E_RUN_ADHERENCE"),
    "Set E2E_RUN_ADHERENCE=1 or E2E_RUN_ALL=1 to run; requires the live `just dev` docker stack + seeded demo user.",
  );

  test("entry point, calendar, trend bars, and CSV export", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    await login(page, TEST_EMAIL, TEST_PASSWORD);

    // --- Seed a med with a daily schedule + one backdated dose ---------------
    const medName = `Smoke Med ${Date.now()}`;
    await page.goto("/medications/new");
    await page.getByLabel(/^name$/i).fill(medName);
    await setPlainDose(page, "1", "tab");
    await page.getByLabel(/untracked/i).check();
    await addSchedule(page, "08:00", `E2E-adh-${Date.now()}`);
    await page.getByRole("button", { name: /add medication/i }).click();
    await expect(page).toHaveURL(/\/medications$/);

    const medId = await medIdByName(page, medName);
    const twoDaysAgo = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000);
    const doseResp = await page.request.post(`${API_BASE}/api/doses`, {
      headers: await csrfHeaders(page),
      data: { medication_id: medId, taken_at: twoDaysAgo.toISOString() },
    });
    expect(doseResp.ok()).toBeTruthy();

    // --- 1. Entry point: the list links to the adherence view ----------------
    await page.goto("/medications");
    await page
      .getByRole("link", {
        name: new RegExp(`view adherence for ${medName}`, "i"),
      })
      .click();
    await expect(page).toHaveURL(new RegExp(`/medications/${medId}$`));
    await expect(
      page.getByRole("heading", { name: "Adherence", exact: true }),
    ).toBeVisible();

    // --- 2. Calendar renders day cells ---------------------------------------
    await expect(page.locator("[data-status]").first()).toBeVisible();

    // --- 3. Trend bars have real height (the 0px-collapse guard) -------------
    await page.getByRole("tab", { name: /trend/i }).click();
    const trend = page.getByTestId("adherence-trend");
    await expect(trend).toBeVisible();
    const bar = trend.locator("[data-status]").first();
    const box = await bar.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.height).toBeGreaterThan(20);

    // --- 4. CSV export downloads ---------------------------------------------
    await page.goto("/medications");
    await page.getByRole("button", { name: /^export$/i }).click();
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: /download csv/i }).click(),
    ]);
    expect(download.suggestedFilename()).toBe("medminder-doses.csv");
  });
});
