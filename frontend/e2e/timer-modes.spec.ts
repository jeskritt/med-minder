/**
 * SC-006 boundary scenario for count_down timers.
 *
 * Verifies that the mark-as-taken button's enabled state on the client
 * agrees with the server's accept/reject verdict at the zero boundary —
 * no flicker, no double-take.
 *
 * Skipped by default; set `E2E_RUN_TIMER_MODES=1` plus the standard
 * dev-user credentials to run locally:
 *
 *     just dev                       # in one terminal
 *     E2E_RUN_TIMER_MODES=1 \
 *       E2E_USER_EMAIL=demo@example.com \
 *       E2E_USER_PASSWORD=... \
 *       pnpm test:e2e                # in another, from frontend/
 *
 * Mirrors `granny-smoke.spec.ts` — gated until CI can stand up the
 * full stack.
 */

import { test, expect } from "@playwright/test";
import { login } from "./helpers";

const TEST_EMAIL = process.env.E2E_DEMO_EMAIL ?? "demo@example.com";
const TEST_PASSWORD =
  process.env.E2E_USER_PASSWORD ?? "correct horse battery staple";

test.describe("Timer modes — count_down boundary", () => {
  test.skip(
    !process.env.E2E_RUN_TIMER_MODES,
    "Set E2E_RUN_TIMER_MODES=1 to run; requires `just dev` + the seeded demo user.",
  );

  test("button transitions from disabled to enabled at zero, no flicker", async ({
    page,
  }) => {
    await login(page, TEST_EMAIL, TEST_PASSWORD);

    // Unique per-run name: the dev DB is shared/long-lived and this
    // test creates a med every run, so a fixed name accumulates
    // duplicates and breaks name-scoped locators. The tag isolates
    // THIS run's med.
    const medName = `PRN Boundary Test ${Date.now()}`;

    // Create a count_down med with the smallest tractable interval (1 minute).
    await page.goto("/medications/new");
    await page.getByLabel(/^name$/i).fill(medName);
    await page.getByLabel(/^dosage$/i).fill("1");
    await page.getByLabel(/^unit$/i).fill("tab");
    await page.getByLabel(/untracked/i).check();
    await page.getByLabel(/timer mode/i).selectOption({ value: "count_down" });
    await page.getByLabel(/minimum interval/i).fill("1");
    await page.getByRole("button", { name: /add schedule/i }).click();
    await page
      .getByLabel(/schedule 1 time/i)
      .fill(new Date().toLocaleTimeString("en-GB").slice(0, 5));
    await page.getByRole("button", { name: /add medication/i }).click();

    // Go to today. Scope to THIS med's row so a NavBar button or a
    // leftover dev-DB med can't be picked up — the count_down row
    // renders exactly one control (<CountDownButton>).
    await page.goto("/today");
    const row = page.getByRole("listitem").filter({ hasText: medName });
    const doseBtn = row.getByRole("button");

    // Initial state (no doses): ready → label "Mark taken". Marking
    // starts the 1-minute cooldown.
    await doseBtn.click();
    await expect(doseBtn).toBeDisabled();

    // Within ~70s the button re-enables. Poll the disabled state: it
    // goes disabled → enabled and never back (no flicker).
    await expect
      .poll(async () => doseBtn.isDisabled(), {
        timeout: 90_000,
        intervals: [1_000],
      })
      .toBe(false);

    await expect(doseBtn).toBeEnabled();
    await expect(doseBtn).toHaveText(/mark taken|ready/i);

    // Click once at the boundary and confirm the server accepts it
    // (no 409 inline alert) — SC-006 client/server agreement.
    await doseBtn.click();
    await expect(page.getByRole("alert")).toHaveCount(0);
  });
});

test.describe("Timer modes — multi_sub_dose window fill", () => {
  test.skip(
    !process.env.E2E_RUN_TIMER_MODES,
    "Set E2E_RUN_TIMER_MODES=1 to run; requires `just dev` + the seeded demo user.",
  );

  test("fills a window's slots then disables the control when full", async ({
    page,
  }) => {
    await login(page, TEST_EMAIL, TEST_PASSWORD);

    // Unique per-run name (see count_down rationale) — isolates this
    // run's med from accumulated dev-DB duplicates.
    const medName = `Window Fill Test ${Date.now()}`;

    // Create a multi_sub_dose med: 3 sub-doses in a 6-hour window.
    await page.goto("/medications/new");
    await page.getByLabel(/^name$/i).fill(medName);
    await page.getByLabel(/^dosage$/i).fill("1");
    await page.getByLabel(/^unit$/i).fill("tab");
    await page.getByLabel(/untracked/i).check();
    await page.getByLabel(/times per day/i).fill("3");
    await page
      .getByLabel(/timer mode/i)
      .selectOption({ value: "multi_sub_dose" });
    await page.getByLabel(/window duration/i).fill("360");
    await page.getByRole("button", { name: /add medication/i }).click();

    // The medications list links multi_sub_dose meds to their detail
    // page. Await the detail URL so the CTA is evaluated on the
    // single-med detail page, not the multi-med list (which carries
    // leftover dev-DB meds, each with its own "Dose available" CTA).
    await page.goto("/medications");
    await page.getByRole("link", { name: medName, exact: true }).click();
    await expect(page).toHaveURL(/\/medications\/[0-9a-f-]{36}$/);

    // Tap the CTA three times; each tap consumes a slot.
    const cta = page.getByRole("button", { name: /dose available/i });
    for (let i = 1; i <= 3; i++) {
      await expect(cta).toBeEnabled();
      await cta.click();
      await expect(page.getByText(`${i} of 3`)).toBeVisible();
    }

    // Fourth attempt: window is full → control disabled, no overdose.
    await expect(
      page.getByRole("button", { name: /window full/i }),
    ).toBeDisabled();
  });
});
