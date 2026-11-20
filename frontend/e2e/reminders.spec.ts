/**
 * Reminders + snooze (Phase 7): the in-app reminder loop.
 *
 * Drives the user-facing slice that is deterministic in a headless browser:
 *   1. Creating a med attached to a (daily) schedule generates that slot's
 *      dose reminder synchronously (regenerate_schedule_reminders, US4) —
 *      no scheduler tick needed.
 *   2. The reminder is visible in the in-app list (FR-008), which is the
 *      fallback channel for users without push.
 *   3. Snoozing it marks the original `snoozed` and creates a new `+1h`
 *      pending reminder (US2) — so the med shows two rows.
 *   4. Dismissing resolves a reminder and drops it from the list.
 *   5. A low-supply med, after a dose is taken, surfaces a refill warning in
 *      the same in-app list (US5): the take decrements supply past its
 *      threshold server-side, and the warning renders here.
 *
 * Out of scope here (covered by backend integration tests, not E2E): actual
 * Web Push *delivery*. Headless Chromium has no push service (and reports
 * permission "denied"), so `PushManager.subscribe` can't run — we assert the
 * notifications control renders but never subscribe. The delivery path
 * (generate → grace → quiet-hours defer → push → mark sent) is exercised by
 * `backend/tests/domain/test_reminder_dispatch.py` with a fake sender.
 *
 * Skipped by default; run locally against the live stack:
 *
 *     just dev                          # one terminal
 *     E2E_RUN_REMINDERS=1 \
 *       E2E_DEMO_EMAIL=demo@example.com \
 *       E2E_USER_PASSWORD=... \
 *       pnpm test:e2e                   # another, from frontend/
 *
 * Mirrors the gating of granny-smoke / timer-modes / schedules — un-gated in
 * CI once the docker stack lands there (Phase 10 roadmap item).
 */

import { test, expect, type Locator, type Page } from "@playwright/test";
import {
  addSchedule,
  csrfHeaders,
  isE2eEnabled,
  login,
  setPlainDose,
} from "./helpers";

const TEST_EMAIL = process.env.E2E_DEMO_EMAIL ?? "demo@example.com";
const TEST_PASSWORD =
  process.env.E2E_USER_PASSWORD ?? "correct horse battery staple";
const API_BASE = process.env.E2E_API_BASE ?? "http://localhost:8000";

/**
 * Create an `untracked`-mode med attached to a brand-new, uniquely-labelled
 * daily schedule, then land back on the medications list. Saving the med
 * generates the slot's pending dose reminder synchronously.
 */
async function createMedWithSchedule(
  page: Page,
  opts: { medName: string; label: string; time: string },
): Promise<void> {
  await page.goto("/medications/new");
  await page.getByLabel(/^name$/i).fill(opts.medName);
  await setPlainDose(page, "1", "tab");
  await page.getByLabel(/untracked/i).check();
  await addSchedule(page, opts.time, opts.label);
  await page.getByRole("button", { name: /add medication/i }).click();
  await expect(page).toHaveURL(/\/medications$/);
}

/** The reminder-list rows whose title names `medName` (unique per run). */
function rowsForMed(page: Page, medName: string): Locator {
  return page
    .getByTestId("reminder-list")
    .locator("li")
    .filter({ hasText: medName });
}

test.describe("Reminders + snooze", () => {
  test.skip(
    !isE2eEnabled("E2E_RUN_REMINDERS"),
    "Set E2E_RUN_REMINDERS=1 or E2E_RUN_ALL=1 to run; requires `just dev` + the seeded demo user.",
  );

  test("a scheduled med shows an in-app reminder that snoozes and dismisses", async ({
    page,
  }) => {
    await login(page, TEST_EMAIL, TEST_PASSWORD);
    const stamp = Date.now();
    const medName = `Reminder Med ${stamp}`;
    await createMedWithSchedule(page, {
      medName,
      label: `E2E-rem-${stamp}`,
      time: "08:00",
    });

    await page.goto("/reminders");

    // 1. Generation-on-save (US4) + in-app list (FR-008): at least one row for
    //    this med, named in the reminder title. A daily slot generates one
    //    instant per day inside the 48h horizon, so the exact count varies —
    //    snapshot it instead of hard-coding.
    const rows = rowsForMed(page, medName);
    await expect(rows.first()).toBeVisible();
    const initial = await rows.count();

    // 2. Snooze (US2): the chosen reminder → snoozed, plus a new +1h pending
    //    row referencing the same schedule (same title) → count grows by one,
    //    exactly one row flagged "snoozed".
    await rows
      .first()
      .getByRole("button", { name: /snooze 1h/i })
      .click();
    await expect(rows).toHaveCount(initial + 1);
    const snoozed = rows.filter({ hasText: /snoozed/i });
    await expect(snoozed).toHaveCount(1);

    // 3. Dismiss resolves a reminder and drops it from the list.
    await snoozed.getByRole("button", { name: /^dismiss$/i }).click();
    await expect(rows).toHaveCount(initial);

    // Clean up this med's remaining reminders so repeated local runs against
    // the shared dev DB don't accumulate them.
    for (let remaining = initial; remaining > 0; remaining -= 1) {
      await rows
        .first()
        .getByRole("button", { name: /^dismiss$/i })
        .click();
      await expect(rows).toHaveCount(remaining - 1);
    }
  });

  test("the notifications control renders and reminders stay visible without push (US6)", async ({
    page,
  }) => {
    await login(page, TEST_EMAIL, TEST_PASSWORD);
    await page.goto("/reminders");

    await expect(
      page.getByRole("heading", { name: /reminders/i }),
    ).toBeVisible();

    // The EnableNotifications control always mounts in one of its states
    // ("Enable notifications" / "on for this device" / "blocked" /
    // "does not support") — all of which mention notifications. Headless
    // Chromium reports permission "denied", so we don't assert a single
    // branch; we assert the control rendered.
    await expect(page.getByText(/notification/i).first()).toBeVisible();

    // US6 acceptance: even when push is unavailable/denied, the in-app
    // reminder view is still the reliable fallback channel (FR-008) — it
    // resolves into either the list or its empty state regardless of how many
    // reminders the demo user currently has.
    await expect(
      page
        .getByTestId("reminder-list")
        .or(page.getByText(/no reminders right now/i)),
    ).toBeVisible();
  });

  test("a low-supply med shows a refill warning after a dose is taken (US5)", async ({
    page,
  }) => {
    await login(page, TEST_EMAIL, TEST_PASSWORD);
    const stamp = Date.now();
    const medName = `Refill Med ${stamp}`;

    // Create a med whose on-hand count sits one above its warn-at threshold,
    // so a single take crosses it. Driven via the API (the suite's setup
    // pattern) — refill warnings are per-med and need no schedule. The
    // "Mark taken" UI click is already covered by granny-smoke.spec.ts; this
    // test targets the new US5 behavior: decrement → warn → in-app render.
    const csrf = await csrfHeaders(page);
    const createResp = await page.request.post(
      `${API_BASE}/api/v1/medications`,
      {
        headers: csrf,
        data: {
          name: medName,
          times_per_day: 1,
          quantity_per_dose: "1.000",
          unit: "tab",
          refill_count: 2,
          refill_threshold: 1,
        },
      },
    );
    expect(createResp.ok()).toBeTruthy();
    const { id: medId } = (await createResp.json()) as { id: string };

    // Take one dose: create_dose decrements refill_count 2 → 1, crossing the
    // threshold (before > threshold >= after) → a refill reminder is generated.
    // (The doses router is mounted at /api/doses, not /api/v1/doses.)
    const doseResp = await page.request.post(`${API_BASE}/api/doses`, {
      headers: csrf,
      data: { medication_id: medId },
    });
    expect(doseResp.ok()).toBeTruthy();

    await page.goto("/reminders");

    // The refill warning names the med and the remaining on-hand count (US5);
    // title format is "Refill {name} — {N} left".
    const refillRow = page
      .getByTestId("reminder-list")
      .locator("li")
      .filter({ hasText: `Refill ${medName}` });
    await expect(refillRow).toHaveCount(1);
    await expect(refillRow).toContainText("1 left");

    // Clean up so repeated local runs don't accumulate this med's warning.
    await refillRow.getByRole("button", { name: /^dismiss$/i }).click();
    await expect(refillRow).toHaveCount(0);
  });

  test("quiet hours can be enabled, persisted across reload, and cleared", async ({
    page,
  }) => {
    await login(page, TEST_EMAIL, TEST_PASSWORD);
    await page.goto("/reminders");

    const quietForm = page.getByRole("form", { name: "Quiet hours" });
    await expect(quietForm).toBeVisible();

    const toggle = quietForm.getByLabel(/mute reminders during these hours/i);
    if (!(await toggle.isChecked())) {
      await toggle.check();
    }
    await quietForm.getByLabel(/^start$/i).fill("22:30");
    await quietForm.getByLabel(/^end$/i).fill("06:45");
    await quietForm.getByRole("button", { name: /save quiet hours/i }).click();
    await expect(quietForm.getByText("Quiet hours saved.")).toBeVisible();

    // Reload and verify the saved window persists.
    await page.reload();
    const reloadedForm = page.getByRole("form", { name: "Quiet hours" });
    await expect(
      reloadedForm.getByLabel(/mute reminders during these hours/i),
    ).toBeChecked();
    await expect(reloadedForm.getByLabel(/^start$/i)).toHaveValue("22:30");
    await expect(reloadedForm.getByLabel(/^end$/i)).toHaveValue("06:45");

    // Clear quiet hours to leave the fixture clean.
    await reloadedForm
      .getByLabel(/mute reminders during these hours/i)
      .uncheck();
    await reloadedForm
      .getByRole("button", { name: /save quiet hours/i })
      .click();
    await expect(reloadedForm.getByText("Quiet hours saved.")).toBeVisible();
  });
});
