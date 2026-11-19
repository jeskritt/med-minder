/**
 * Phase 6 (ADR-0008) — drug-interaction warn → take-anyway → recorded.
 *
 * Locator strategy: resolve each med's id from the API and target its
 * today row + dose control by stable `data-testid`
 * (`today-row-<medId>` / `dose-control`). Render-invariant across the
 * shared dev DB's accumulated meds and the symmetric interaction
 * indicator (which names the *partner* med — a substring/role row
 * filter is ambiguous because of it). No name/text row scoping.
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
 * Verifies SC-007: mark conflicting med → see warning + remaining
 * cooldown → explicitly proceed with an audited override.
 */

import { test, expect } from "@playwright/test";
import {
  addSchedule,
  isE2eEnabled,
  login,
  medIdByName,
  setPlainDose,
} from "./helpers";

const TEST_EMAIL = process.env.E2E_DEMO_EMAIL ?? "demo@example.com";
const TEST_PASSWORD =
  process.env.E2E_USER_PASSWORD ?? "correct horse battery staple";

test.describe("Drug-interaction cooldown — warn + take anyway", () => {
  test.skip(
    !isE2eEnabled("E2E_RUN_DRUG_INTERACTION"),
    "Set E2E_RUN_DRUG_INTERACTION=1 or E2E_RUN_ALL=1 to run; requires `just dev` + the seeded demo user.",
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
    await setPlainDose(page, "1", "tab");
    await page.getByLabel(/untracked/i).check();
    await addSchedule(page, slot);
    await page.getByRole("button", { name: /add medication/i }).click();
    await expect(page).toHaveURL(/\/medications$/);

    // Med A, paired with B (120-minute cooldown).
    await page.goto("/medications/new");
    await page.getByLabel(/^name$/i).fill(aName);
    await setPlainDose(page, "1", "tab");
    await page.getByLabel(/untracked/i).check();
    await addSchedule(page, slot);
    await page.getByRole("button", { name: /add interaction/i }).click();
    await page.getByLabel(/^medication$/i).selectOption({ label: bName });
    // Cooldown is a value + unit pair (defaults to hours); pick minutes so the
    // 120 below is a 120-minute cooldown.
    await page.getByLabel("Cooldown unit").selectOption("min");
    await page.getByLabel("Cooldown", { exact: true }).fill("120");
    await page.getByRole("button", { name: /add medication/i }).click();
    await expect(page).toHaveURL(/\/medications$/);

    // Resolve ids, target each row's control by stable test id.
    const aId = await medIdByName(page, aName);
    const bId = await medIdByName(page, bName);
    await page.goto("/today");
    // `.first()`: `today_view` emits one row per effective dose, so a
    // med can have >1 identical today row. Both carry the same per-med
    // state, so scope deterministically to the first.
    const aRow = page.getByTestId(`today-row-${aId}`).first();
    const bRow = page.getByTestId(`today-row-${bId}`).first();
    const aBtn = aRow.getByTestId("dose-control");
    const bBtn = bRow.getByTestId("dose-control");

    // Mark A taken (mode none → TakenToggle; label flips to "Taken").
    await expect(aBtn).toBeVisible();
    await aBtn.click();
    await expect(aBtn).toHaveText(/^taken$/i);

    // B now shows the interaction indicator naming A.
    await expect(bRow.getByText(/Interacts with .*safe in/i)).toBeVisible();

    // Attempting B opens the overridable "take anyway" modal (NOT a
    // dead-end). Confirm → B is recorded with an audited override.
    await bBtn.click();
    const modal = page.getByRole("dialog", {
      name: /confirm interaction override/i,
    });
    await expect(modal).toBeVisible();
    await expect(modal).toContainText(aName);
    await modal.getByRole("button", { name: /take anyway/i }).click();

    await expect(bBtn).toHaveText(/^taken$/i);
  });
});
