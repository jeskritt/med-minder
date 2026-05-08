/**
 * FR-006: end-to-end smoke for the Granny flow.
 *
 * Log in → create medication with one schedule → open `/today` → click
 * Taken → assert greyed out → open the FR-005 confirm modal → cancel
 * → confirm un-take → assert untaken.
 *
 * The medication+schedule fixture is created server-side via the
 * domain APIs once Phase 5 (medication CRUD) lands; for now this
 * smoke is gated behind a real test user that the dev environment
 * is expected to provide. Local runs:
 *
 *     just dev           # docker compose up
 *     pnpm test:e2e      # in another terminal, from frontend/
 *
 * Skipped in CI until Phase 5 ships the medication CRUD endpoints
 * the smoke needs to seed its fixture (Phase 4 ships only the dose
 * endpoints).
 */

import { test, expect } from "@playwright/test";

const TEST_EMAIL = process.env.E2E_USER_EMAIL ?? "granny@example.com";
const TEST_PASSWORD =
  process.env.E2E_USER_PASSWORD ?? "correct horse battery staple";

test.describe("Granny flow", () => {
  test.skip(
    !process.env.E2E_RUN_GRANNY,
    "Set E2E_RUN_GRANNY=1 once a dev medication+schedule fixture is provisioned for the test user.",
  );

  test("login, mark taken, cancel, then un-take", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(TEST_EMAIL);
    await page.getByLabel("Password").fill(TEST_PASSWORD);
    await page.getByRole("button", { name: /sign in/i }).click();

    await page.goto("/today");
    await expect(page.getByRole("heading", { name: "Today" })).toBeVisible();

    const markBtn = page.getByRole("button", { name: /mark taken/i }).first();
    await markBtn.click();

    // Optimistic + persisted: row flips to greyed-out "Taken".
    const takenBtn = page.getByRole("button", { name: /^taken$/i }).first();
    await expect(takenBtn).toBeVisible();

    // Open the FR-005 modal, cancel, confirm state is preserved.
    await takenBtn.click();
    await expect(
      page.getByText(
        "This med has already been taken. Remove the 'taken' status?",
      ),
    ).toBeVisible();
    await page.getByRole("button", { name: /^cancel$/i }).click();
    await expect(page.getByRole("button", { name: /^taken$/i })).toBeVisible();

    // Open again and confirm — slot returns to untaken.
    await takenBtn.click();
    await page.getByRole("button", { name: /^confirm$/i }).click();
    await expect(
      page.getByRole("button", { name: /mark taken/i }),
    ).toBeVisible();
  });
});
