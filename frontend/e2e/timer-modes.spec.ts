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
    // The smallest count_down interval is 1 minute, so this scenario
    // must wait out a ~60s server-side cooldown. Playwright's default
    // per-test timeout is 30s — extend it generously.
    test.setTimeout(150_000);
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
    // /today loads async (useToday); wait for THIS run's row to render
    // before interacting. Unique medName ⇒ exactly one matching row.
    await expect(row).toBeVisible();
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

    // Client ticker zero ≠ server-clocked 60s: the server clocks the
    // min-interval from the recorded dose #1 timestamp, so its window
    // ends slightly after the client countdown reaches 0 (POST/fetch
    // latency, sub-2s on localhost). Wait a bounded buffer so the 2nd
    // click is unambiguously past the server boundary — the test
    // budget (test.setTimeout(150_000)) still has ample headroom.
    await page.waitForTimeout(5000);

    // SC-006: at/after the boundary the server accepts AND the client
    // agrees — no 409 inline alert, and the accepted dose restarts the
    // cooldown (button re-disables), proving two-way agreement.
    await doseBtn.click();
    await expect(page.getByRole("alert")).toHaveCount(0);
    await expect(doseBtn).toBeDisabled();
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

    // The detail data loads async (useMedicationDetail shows "Loading…").
    // Await the med's heading so the list is fully unmounted and the
    // single detail card is rendered, then scope every assertion to the
    // detail <main> — immune to the transient list paint and to
    // accumulated dev-DB meds (each of which renders its own CTA on the
    // list, but never inside this detail main).
    await expect(page.getByRole("heading", { name: medName })).toBeVisible();
    const detail = page.getByRole("main");

    // Tap the CTA three times; each tap consumes a slot. multi_sub_dose
    // has no optimistic patch (no schedule context), so the card only
    // moves after POST /api/doses → useTakeDose.onSettled invalidates
    // ["medication", id] → useMedicationDetail refetches that GET →
    // re-render. Await that exact refetch before asserting, instead of
    // racing a bare text wait. (Verified live in Chrome: POST 201 then
    // GET /api/v1/medications/<uuid> 200, card flips to "i of 3".)
    const cta = detail.getByRole("button", { name: /dose available/i });
    for (let i = 1; i <= 3; i++) {
      await expect(cta).toBeEnabled();
      await Promise.all([
        page.waitForResponse(
          (r) =>
            /\/api\/v1\/medications\/[0-9a-f-]{36}$/.test(
              new URL(r.url()).pathname,
            ) &&
            r.request().method() === "GET" &&
            r.status() === 200,
        ),
        cta.click(),
      ]);
      await expect(detail.getByText(`${i} of 3`)).toBeVisible();
    }

    // Fourth attempt: window is full → control disabled, no overdose.
    await expect(
      detail.getByRole("button", { name: /window full/i }),
    ).toBeDisabled();
  });
});
