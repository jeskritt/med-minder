/**
 * Feature 007: end-to-end smoke for the self-service profile editor.
 *
 * Two flows against the live stack:
 *   1. Change display name → nav reflects it (then restore).
 *   2. Change password → this device stays in, a second device is logged out
 *      (SC-003) → then restore the original password so the fixture stays usable.
 *
 * The test user is provisioned by `e2e/global-setup.ts`. Local run:
 *
 *     just dev                                   # docker compose up
 *     E2E_RUN_PROFILE_EDITOR=1 pnpm test:e2e     # from frontend/
 *
 * Gated like the other specs: it needs the live `just dev` docker stack. The
 * password flow restores the original password at the end so reruns and other
 * specs keep working against the shared dev DB.
 */

import { test, expect, type Page } from "@playwright/test";
import { isE2eEnabled, login } from "./helpers";

const EMAIL = process.env.E2E_USER_EMAIL ?? "granny@example.com";
const PASSWORD =
  process.env.E2E_USER_PASSWORD ?? "correct horse battery staple";
const TEMP_PASSWORD = "e2e temporary passphrase 007";
const API_BASE = process.env.E2E_API_BASE ?? "http://localhost:8000";

async function openProfile(page: Page): Promise<void> {
  await page.getByTestId("open-profile").click();
  await expect(page.getByRole("dialog", { name: "Profile" })).toBeVisible();
}

test.describe("Self-service profile editor", () => {
  test.skip(
    !isE2eEnabled("E2E_RUN_PROFILE_EDITOR"),
    "Set E2E_RUN_PROFILE_EDITOR=1 or E2E_RUN_ALL=1 to run; requires the live `just dev` docker stack.",
  );

  test("change display name reflects in the nav bar", async ({ page }) => {
    await login(page, EMAIL, PASSWORD);

    await openProfile(page);
    const nameInput = page.getByLabel("Display name");
    const original = (await nameInput.inputValue()).trim();
    const renamed = `${original} ✎`;

    await nameInput.fill(renamed);
    await page.getByRole("button", { name: /save name/i }).click();
    await expect(page.getByText("Name saved.")).toBeVisible();
    await expect(page.getByTestId("open-profile")).toContainText(renamed);

    // Restore the original name to keep the fixture stable.
    await nameInput.fill(original);
    await page.getByRole("button", { name: /save name/i }).click();
    await expect(page.getByTestId("open-profile")).toContainText(original);
  });

  test("password change keeps this device, signs out the other", async ({
    browser,
  }) => {
    const deviceA = await browser.newContext();
    const deviceB = await browser.newContext();
    const pageA = await deviceA.newPage();
    const pageB = await deviceB.newPage();

    try {
      await login(pageA, EMAIL, PASSWORD);
      await login(pageB, EMAIL, PASSWORD); // independent second session

      // Device A changes the password.
      await openProfile(pageA);
      await pageA.getByLabel("Current password").fill(PASSWORD);
      await pageA.getByLabel("New password").fill(TEMP_PASSWORD);
      await pageA.getByRole("button", { name: /change password/i }).click();
      await expect(pageA.getByText(/password changed/i)).toBeVisible();

      // Device B's session is revoked → next navigation bounces to /login.
      await pageB.goto("/medications");
      await expect(pageB).toHaveURL(/\/login$/);

      // Device A is still authenticated.
      await pageA.goto("/medications");
      await expect(pageA).toHaveURL(/\/medications$/);

      // Restore the original password so the fixture stays usable.
      await openProfile(pageA);
      await pageA.getByLabel("Current password").fill(TEMP_PASSWORD);
      await pageA.getByLabel("New password").fill(PASSWORD);
      await pageA.getByRole("button", { name: /change password/i }).click();
      await expect(pageA.getByText(/password changed/i)).toBeVisible();
    } finally {
      await deviceA.close();
      await deviceB.close();
    }
  });

  test("change timezone via Alberta alias persists and updates quiet-hours label", async ({
    page,
  }) => {
    await login(page, EMAIL, PASSWORD);

    // Snapshot original timezone so we can restore cleanly.
    const meBefore = await page.request.get(`${API_BASE}/me`);
    expect(meBefore.ok()).toBeTruthy();
    const originalTz = ((await meBefore.json()) as { timezone: string })
      .timezone;

    // First switch to UTC if already America/Edmonton so the save is dirty.
    const targetTz = "America/Edmonton";
    const prepTz = originalTz === targetTz ? "UTC" : null;

    await openProfile(page);
    const dialog = page.getByRole("dialog", { name: "Profile" });
    const tzInput = dialog.getByRole("combobox");
    const saveTzBtn = dialog.getByRole("button", { name: /save timezone/i });

    if (prepTz) {
      await tzInput.click();
      await tzInput.fill(prepTz);
      await dialog.getByRole("option", { name: /^UTC\b/ }).click();
      await saveTzBtn.click();
      await expect(dialog.getByText("Timezone saved.")).toBeVisible();
    }

    // Search using the friendly "Alberta" alias and pick America/Edmonton.
    await tzInput.click();
    await tzInput.fill("Alberta");
    const edmontonOpt = dialog.getByRole("option", {
      name: /America\/Edmonton/,
    });
    await expect(edmontonOpt).toBeVisible();
    await edmontonOpt.click();
    await saveTzBtn.click();
    await expect(dialog.getByText("Timezone saved.")).toBeVisible();

    // Verify persistence on /reminders Quiet Hours heading and across reload.
    await dialog.getByRole("button", { name: "Close" }).click();
    await page.goto("/reminders");
    await expect(
      page.getByRole("heading", { name: /Quiet hours \(America\/Edmonton\)/ }),
    ).toBeVisible();

    // Restore original timezone if it differed.
    if (originalTz !== targetTz) {
      await openProfile(page);
      const restoreDialog = page.getByRole("dialog", { name: "Profile" });
      const restoreInput = restoreDialog.getByRole("combobox");
      await restoreInput.click();
      await restoreInput.fill(originalTz);
      await restoreDialog
        .getByRole("option", { name: new RegExp(originalTz) })
        .first()
        .click();
      await restoreDialog
        .getByRole("button", { name: /save timezone/i })
        .click();
      await expect(restoreDialog.getByText("Timezone saved.")).toBeVisible();
    }
  });
});
