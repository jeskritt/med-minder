/**
 * FR-006: end-to-end smoke for the Granny flow (mode `none`).
 *
 * Log in → open `/today` → click Taken → assert greyed out → open the
 * FR-005 confirm modal → cancel → confirm un-take → assert untaken.
 *
 * The granny user and a `none`-mode medication + 08:00 schedule are
 * provisioned idempotently by `e2e/global-setup.ts`, so this spec is
 * self-sufficient against a running stack. Local run:
 *
 *     just dev                              # docker compose up
 *     E2E_RUN_GRANNY=1 pnpm test:e2e        # from frontend/
 *
 * The skip gate is now purely "needs the live docker stack" (matching
 * timer-modes.spec.ts's E2E_RUN_TIMER_MODES gate). Un-gating in CI —
 * standing the stack up in GitHub Actions — is a Phase 10 roadmap item.
 */

import { test, expect } from "@playwright/test";
import { login } from "./helpers";

const TEST_EMAIL = process.env.E2E_USER_EMAIL ?? "granny@example.com";
const TEST_PASSWORD =
  process.env.E2E_USER_PASSWORD ?? "correct horse battery staple";

test.describe("Granny flow", () => {
  test.skip(
    !process.env.E2E_RUN_GRANNY,
    "Set E2E_RUN_GRANNY=1 to run; requires the live `just dev` docker stack (global-setup provisions the fixture).",
  );

  test("login, mark taken, cancel, then un-take", async ({ page }) => {
    await login(page, TEST_EMAIL, TEST_PASSWORD);

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
