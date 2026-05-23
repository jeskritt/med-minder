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
import { login } from "./helpers";

const EMAIL = process.env.E2E_USER_EMAIL ?? "granny@example.com";
const PASSWORD =
  process.env.E2E_USER_PASSWORD ?? "correct horse battery staple";
const TEMP_PASSWORD = "e2e temporary passphrase 007";

async function openProfile(page: Page): Promise<void> {
  await page.getByTestId("open-profile").click();
  await expect(page.getByRole("dialog", { name: "Profile" })).toBeVisible();
}

test.describe("Self-service profile editor", () => {
  test.skip(
    !process.env.E2E_RUN_PROFILE_EDITOR,
    "Set E2E_RUN_PROFILE_EDITOR=1 to run; requires the live `just dev` docker stack.",
  );

  test("change display name reflects in the nav bar", async ({ page }) => {
    await login(page, EMAIL, PASSWORD);

    const original = (
      await page.getByTestId("open-profile").innerText()
    ).trim();
    const renamed = `${original} ✎`;

    await openProfile(page);
    const nameInput = page.getByLabel("Display name");
    await nameInput.fill(renamed);
    await page.getByRole("button", { name: /save name/i }).click();
    await expect(page.getByText("Name saved.")).toBeVisible();
    await expect(page.getByTestId("open-profile")).toHaveText(renamed);

    // Restore the original name to keep the fixture stable.
    await nameInput.fill(original);
    await page.getByRole("button", { name: /save name/i }).click();
    await expect(page.getByTestId("open-profile")).toHaveText(original);
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
});
