/**
 * SC-006 boundary scenario for count_down timers + multi_sub_dose
 * window fill.
 *
 * Locator strategy (round-2 robustness fix): the today row exposes a
 * stable `data-testid="today-row-<medId>"` and every dose control a
 * `data-testid="dose-control"`. We resolve the med id from the API
 * (cookie-shared with the logged-in page) and target the control by
 * those ids — render-invariant across the count_down label flip
 * ("Mark taken" ⇄ "<1m"), the optimistic-update/refetch re-render,
 * NavBar list items, sibling additions, and the shared dev DB that
 * accumulates similarly-named meds. No name/text/role-shaped row
 * scoping (that is what kept breaking).
 *
 * Skipped by default; set `E2E_RUN_TIMER_MODES=1` plus the standard
 * dev-user credentials to run locally:
 *
 *     just dev                       # in one terminal
 *     E2E_RUN_TIMER_MODES=1 \
 *       E2E_DEMO_EMAIL=demo@example.com \
 *       E2E_USER_PASSWORD=... \
 *       pnpm test:e2e                # in another, from frontend/
 *
 * Mirrors `granny-smoke.spec.ts` — gated until CI can stand up the
 * full stack.
 */

import { test, expect } from "@playwright/test";
import { login, medIdByName, setPlainDose, addSchedule } from "./helpers";

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

    // Unique per-run name so the API lookup resolves exactly this
    // run's med even though the shared dev DB accumulates duplicates.
    const medName = `PRN Boundary Test ${Date.now()}`;

    // Create a count_down med with the smallest tractable interval (1 minute).
    await page.goto("/medications/new");
    await page.getByLabel(/^name$/i).fill(medName);
    await setPlainDose(page, "1", "tab");
    await page.getByLabel(/untracked/i).check();
    await page.getByLabel(/timer mode/i).selectOption({ value: "count_down" });
    await page.getByLabel(/minimum interval/i).fill("1");
    // Unit defaults to "hours"; this scenario needs a 1-*minute* cooldown.
    await page.getByLabel(/interval unit/i).selectOption({ value: "min" });
    await addSchedule(page, new Date().toLocaleTimeString("en-GB").slice(0, 5));
    await page.getByRole("button", { name: /add medication/i }).click();
    await expect(page).toHaveURL(/\/medications$/);

    // Resolve THIS med's id, then target its today-row control by
    // stable test ids — unambiguous regardless of dev-DB accumulation,
    // the dynamic button label, or re-render timing.
    const medId = await medIdByName(page, medName);
    await page.goto("/today");
    // `today_view` emits one row per *effective dose* (the EffectiveDose
    // outerjoin has no aggregation), so a scheduled med with N
    // non-voided doses today renders N identical rows — this boundary
    // test marks 2 doses, so 2 rows. Both carry the same per-med
    // timer_state / CountDownButton, so deterministically scope to the
    // first. (This — not the testid/label — is what made round 1 & 2
    // strict-mode-ambiguous.)
    const row = page.getByTestId(`today-row-${medId}`).first();
    await expect(row).toBeVisible();
    const doseBtn = row.getByTestId("dose-control");

    // Initial state (no doses): ready → label "Mark taken". Marking
    // starts the 1-minute cooldown.
    //
    // The button only re-disables once the post-dose today *refetch*
    // (useTakeDose.onSettled invalidates ["today"] → GET
    // /api/schedules/today) returns the new timer_state and re-renders
    // — the optimistic patch doesn't touch timer_state. Await that
    // exact refetch before asserting, same as the multi_sub_dose
    // sibling. (A bare post-click `toBeDisabled()` races the
    // POST→invalidate→refetch→rerender cycle — the round-1/2 flake.)
    const todayRefetch = () =>
      page.waitForResponse(
        (r) =>
          new URL(r.url()).pathname === "/api/schedules/today" &&
          r.request().method() === "GET" &&
          r.status() === 200,
      );
    await Promise.all([todayRefetch(), doseBtn.click()]);
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
    // agrees — no 409 inline alert in this row, and the accepted dose
    // restarts the cooldown (button re-disables), proving two-way
    // agreement.
    await Promise.all([todayRefetch(), doseBtn.click()]);
    await expect(row.getByRole("alert")).toHaveCount(0);
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

    // Unique per-run name (see count_down rationale).
    const medName = `Window Fill Test ${Date.now()}`;

    // Create a multi_sub_dose med: 3 sub-doses in a 6-hour window.
    await page.goto("/medications/new");
    await page.getByLabel(/^name$/i).fill(medName);
    await setPlainDose(page, "1", "tab");
    await page.getByLabel(/untracked/i).check();
    await page.getByLabel(/times per day/i).fill("3");
    await page
      .getByLabel(/timer mode/i)
      .selectOption({ value: "multi_sub_dose" });
    await page.getByLabel(/window duration/i).fill("360");
    // Unit defaults to "hours"; this scenario means a 360-*minute* (6h) window.
    await page.getByLabel(/window unit/i).selectOption({ value: "min" });
    await page.getByRole("button", { name: /add medication/i }).click();
    await expect(page).toHaveURL(/\/medications$/);

    // Drive the CTA on the single-med detail page (isolated from the
    // multi-med list), scoped to the detail <main> and targeted by the
    // stable dose-control test id (not the dynamic "Dose available" ⇄
    // "Max reached" label).
    await page.goto("/medications");
    await page.getByRole("link", { name: medName, exact: true }).click();
    await expect(page).toHaveURL(/\/medications\/[0-9a-f-]{36}$/);
    await expect(page.getByRole("heading", { name: medName })).toBeVisible();
    const detail = page.getByRole("main");
    const cta = detail.getByTestId("dose-control");

    // Tap the CTA three times; each tap consumes a slot. multi_sub_dose
    // has no optimistic patch (no schedule context), so the card only
    // moves after POST /api/doses → useTakeDose.onSettled invalidates
    // ["medication", id] → useMedicationDetail refetches that GET →
    // re-render. Await that exact refetch before asserting.
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
      await expect(detail.getByText(new RegExp(`${i}/3 active`))).toBeVisible();
    }

    // Fourth state: at capacity → same control is now disabled
    // ("Max reached"), no overdose.
    await expect(cta).toBeDisabled();
    await expect(cta).toHaveText(/max reached/i);
  });
});
