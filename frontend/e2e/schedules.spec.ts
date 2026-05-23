/**
 * Schedule management (UX-enhancements / schedule-mutability work):
 * inline edit, delete-with-attached-meds, and the move-shared-time
 * warning — all driven through the SchedulePicker inside the medication
 * form (there is no standalone schedules page).
 *
 * Each test provisions its own uniquely-labelled schedule attached to a
 * fresh med, so the controls (keyed on the displayed label) are
 * unambiguous against the shared, accumulating dev DB. Skipped by
 * default; run locally against the live stack:
 *
 *     just dev                          # one terminal
 *     E2E_RUN_SCHEDULES=1 \
 *       E2E_DEMO_EMAIL=demo@example.com \
 *       E2E_USER_PASSWORD=... \
 *       pnpm test:e2e                   # another, from frontend/
 *
 * Mirrors the gating of granny-smoke / timer-modes — un-gated in CI
 * once the docker stack lands there (Phase 10 roadmap item).
 */

import { test, expect, type Page } from "@playwright/test";
import { login, medIdByName, setPlainDose, addSchedule } from "./helpers";

const TEST_EMAIL = process.env.E2E_DEMO_EMAIL ?? "demo@example.com";
const TEST_PASSWORD =
  process.env.E2E_USER_PASSWORD ?? "correct horse battery staple";
const API_BASE = process.env.E2E_API_BASE ?? "http://localhost:8000";

/**
 * Create a `none`-mode med attached to a brand-new, uniquely-labelled
 * schedule, then land back on the medications list. Returns the names so
 * the caller can target the chip / verify via the API.
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

test.describe("Schedule management", () => {
  test.skip(
    !process.env.E2E_RUN_SCHEDULES,
    "Set E2E_RUN_SCHEDULES=1 to run; requires `just dev` + the seeded demo user.",
  );

  test("inline label edit persists without a warning", async ({ page }) => {
    await login(page, TEST_EMAIL, TEST_PASSWORD);
    const stamp = Date.now();
    const label = `E2E-label-${stamp}`;
    const renamed = `E2E-renamed-${stamp}`;
    await createMedWithSchedule(page, {
      medName: `Sched Label Med ${stamp}`,
      label,
      time: "08:00",
    });

    // Reopen a fresh form; the picker lists the shared schedule.
    await page.goto("/medications/new");
    await page
      .getByRole("button", { name: new RegExp(`Edit ${label}`) })
      .click();
    // Change only the label — time unchanged → no move warning.
    const labelInput = page.getByLabel(/label \(optional\)/i);
    await labelInput.clear();
    await labelInput.fill(renamed);
    await page.getByRole("button", { name: /^save$/i }).click();

    // Chip re-renders with the new label; no confirm modal ever appeared.
    // Exact name targets the toggle chip, not the Edit/Delete icon buttons
    // (whose aria-labels contain the same "{label} ({time})" text).
    await expect(
      page.getByRole("button", { name: `${renamed} (08:00)`, exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });

  test("deleting a schedule warns about attached meds, then unschedules them", async ({
    page,
  }) => {
    await login(page, TEST_EMAIL, TEST_PASSWORD);
    const stamp = Date.now();
    const label = `E2E-del-${stamp}`;
    const medName = `Sched Delete Med ${stamp}`;
    await createMedWithSchedule(page, { medName, label, time: "09:00" });

    await page.goto("/medications/new");
    await page
      .getByRole("button", { name: new RegExp(`Delete ${label}`) })
      .click();

    // The confirm modal names the attached med.
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText(medName)).toBeVisible();
    await dialog.getByRole("button", { name: /delete schedule/i }).click();

    // Chip is gone…
    await expect(
      page.getByRole("button", { name: new RegExp(`Delete ${label}`) }),
    ).toHaveCount(0);

    // …and the med is unscheduled (detached), not deleted.
    const medId = await medIdByName(page, medName);
    const resp = await page.request.get(`${API_BASE}/api/v1/medications`);
    expect(resp.ok()).toBeTruthy();
    const body = (await resp.json()) as {
      items: { id: string; schedules: unknown[] }[];
    };
    const med = body.items.find((m) => m.id === medId);
    expect(med?.schedules).toEqual([]);
  });

  test("moving a shared time warns, then moves on confirm", async ({
    page,
  }) => {
    await login(page, TEST_EMAIL, TEST_PASSWORD);
    const stamp = Date.now();
    const label = `E2E-move-${stamp}`;
    const medName = `Sched Move Med ${stamp}`;
    await createMedWithSchedule(page, { medName, label, time: "08:00" });

    await page.goto("/medications/new");
    await page
      .getByRole("button", { name: new RegExp(`Edit ${label}`) })
      .click();
    const timeInput = page.getByLabel(/^time$/i);
    await timeInput.clear();
    await timeInput.fill("09:30");
    await page.getByRole("button", { name: /^save$/i }).click();

    // Move-confirm modal names the attached med; the move only lands on
    // confirm.
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText(medName)).toBeVisible();
    await dialog.getByRole("button", { name: /move time/i }).click();

    await expect(
      page.getByRole("button", { name: `${label} (09:30)`, exact: true }),
    ).toBeVisible();
  });
});
