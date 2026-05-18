/**
 * Phase 6 (ADR-0008) — drug-interaction warn → take-anyway → recorded.
 *
 * Skipped by default; set `E2E_RUN_DRUG_INTERACTION=1` plus the
 * standard dev-user credentials to run locally against a live stack:
 *
 *     just dev                          # one terminal
 *     E2E_RUN_DRUG_INTERACTION=1 \
 *       E2E_DEMO_EMAIL=demo@example.com \
 *       E2E_USER_PASSWORD=... \
 *       pnpm test:e2e                    # another, from frontend/
 *
 * Mirrors `timer-modes.spec.ts` — gated until CI can stand up the
 * full stack. Verifies SC-007: mark conflicting med → see warning +
 * remaining cooldown → explicitly proceed with an audited override.
 */

import { test, expect } from "@playwright/test";
import { login } from "./helpers";

const TEST_EMAIL = process.env.E2E_DEMO_EMAIL ?? "demo@example.com";
const TEST_PASSWORD =
  process.env.E2E_USER_PASSWORD ?? "correct horse battery staple";

test.describe("Drug-interaction cooldown — warn + take anyway", () => {
  test.skip(
    !process.env.E2E_RUN_DRUG_INTERACTION,
    "Set E2E_RUN_DRUG_INTERACTION=1 to run; requires `just dev` + the seeded demo user.",
  );

  test("conflicting dose warns, is overridable, and is recorded", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    await login(page, TEST_EMAIL, TEST_PASSWORD);

    const ts = Date.now();
    const aName = `DI-A ${ts}`;
    const bName = `DI-B ${ts}`;
    const slot = new Date().toLocaleTimeString("en-GB").slice(0, 5);

    // Med B first so it exists in A's "Conflicts with" selector.
    await page.goto("/medications/new");
    await page.getByLabel(/^name$/i).fill(bName);
    await page.getByLabel(/^dosage$/i).fill("1");
    await page.getByLabel(/^unit$/i).fill("tab");
    await page.getByLabel(/untracked/i).check();
    await page.getByRole("button", { name: /add schedule/i }).click();
    await page.getByLabel(/schedule 1 time/i).fill(slot);
    await page.getByRole("button", { name: /add medication/i }).click();
    await expect(page).toHaveURL(/\/medications$/);

    // Med A, paired with B (120-minute cooldown).
    await page.goto("/medications/new");
    await page.getByLabel(/^name$/i).fill(aName);
    await page.getByLabel(/^dosage$/i).fill("1");
    await page.getByLabel(/^unit$/i).fill("tab");
    await page.getByLabel(/untracked/i).check();
    await page.getByRole("button", { name: /add schedule/i }).click();
    await page.getByLabel(/schedule 1 time/i).fill(slot);
    await page.getByRole("button", { name: /add interaction/i }).click();
    await page
      .getByLabel(/^medication$/i)
      .selectOption({ label: bName });
    await page.getByLabel(/cooldown/i).fill("120");
    await page.getByRole("button", { name: /add medication/i }).click();
    await expect(page).toHaveURL(/\/medications$/);

    // Mark A taken on /today (mode none → plain TakenToggle).
    // Scope each row by its OWN name paragraph (anchored ^name): the
    // symmetric interaction indicator on one row also contains the
    // partner's name, so a plain hasText match is ambiguous.
    await page.goto("/today");
    const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const rowFor = (name: string) =>
      page
        .locator("li")
        .filter({
          has: page.locator("p", { hasText: new RegExp(`^${esc(name)}`) }),
        });
    const aRow = rowFor(aName);
    const bRow = rowFor(bName);
    await aRow.getByRole("button", { name: /^mark taken$/i }).click();
    await expect(aRow.getByRole("button", { name: /^taken$/i })).toBeVisible();

    // B now shows the interaction indicator naming A.
    await expect(bRow.getByText(/Interacts with .*safe in/i)).toBeVisible();

    // Attempting B opens the overridable "take anyway" modal (NOT a
    // dead-end). Confirm → B is recorded with an audited override.
    await bRow.getByRole("button", { name: /^mark taken$/i }).click();
    const modal = page.getByRole("dialog", {
      name: /confirm interaction override/i,
    });
    await expect(modal).toBeVisible();
    await expect(modal).toContainText(aName);
    await modal.getByRole("button", { name: /take anyway/i }).click();

    await expect(
      bRow.getByRole("button", { name: /^taken$/i }),
    ).toBeVisible();
  });
});
