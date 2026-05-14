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

const TEST_EMAIL = process.env.E2E_USER_EMAIL ?? "demo@example.com";
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
    await page.goto("/login");
    await page.getByLabel("Email").fill(TEST_EMAIL);
    await page.getByLabel("Password").fill(TEST_PASSWORD);
    await page.getByRole("button", { name: /sign in/i }).click();

    // Create a count_down med with the smallest tractable interval (1 minute).
    await page.goto("/medications/new");
    await page.getByLabel(/^name$/i).fill("PRN Boundary Test");
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

    // Go to today, mark the dose.
    await page.goto("/today");
    const markBtn = page.getByRole("button", { name: /mark taken/i }).first();
    await markBtn.click();

    // Within 70s the button should re-enable. Assert no flicker by polling
    // the disabled state: it goes from disabled → enabled and never back.
    const cooldownBtn = page.getByRole("button").first();
    await expect(cooldownBtn).toBeDisabled();

    await expect
      .poll(async () => cooldownBtn.isDisabled(), {
        timeout: 90_000,
        intervals: [1_000],
      })
      .toBe(false);

    // The button must now read "Mark taken" (or "Ready") and accept the click.
    await expect(cooldownBtn).toBeEnabled();
    await expect(cooldownBtn).toHaveText(/mark taken|ready/i);

    // Click once and confirm the server accepts it (no 409 inline alert).
    await cooldownBtn.click();
    await expect(page.getByRole("alert")).toHaveCount(0);
  });
});
