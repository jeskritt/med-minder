/**
 * End-to-end coverage for core authentication & medication CRUD flows:
 *   1. Unauthenticated visits to protected routes redirect to /login.
 *   2. Invalid credentials show the generic auth error; valid login + logout
 *      revokes the session so protected routes bounce back to /login.
 *   3. Medication CRUD lifecycle: create → edit name & dose → delete.
 *
 * Run against the live docker stack:
 *
 *     E2E_RUN_CORE=1 pnpm test:e2e    # or E2E_RUN_ALL=1 pnpm test:e2e
 */

import { test, expect } from "@playwright/test";
import { isE2eEnabled, login, setPlainDose } from "./helpers";

const TEST_EMAIL = process.env.E2E_DEMO_EMAIL ?? "demo@example.com";
const TEST_PASSWORD =
  process.env.E2E_USER_PASSWORD ?? "correct horse battery staple";

test.describe("Auth & Medication CRUD flows", () => {
  test.skip(
    !isE2eEnabled("E2E_RUN_CORE"),
    "Set E2E_RUN_CORE=1 or E2E_RUN_ALL=1 to run; requires the live `just dev` docker stack.",
  );

  test("unauthenticated visitors are redirected from protected routes to /login", async ({
    page,
  }) => {
    for (const path of ["/today", "/medications", "/reminders"]) {
      await page.goto(path);
      await expect(page).toHaveURL(/\/login$/);
    }
  });

  test("invalid login shows generic error; logout clears session", async ({
    page,
  }) => {
    await page.goto("/login");
    // Unique bogus email so we never hit the per-email rate limit for fixtures.
    await page.getByLabel("Email").fill(`nobody-${Date.now()}@example.com`);
    await page.getByLabel("Password").fill("wrong password 12345");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(
      page.getByText("Email or password is incorrect."),
    ).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);

    // Valid login succeeds, then Logout ends the session.
    await login(page, TEST_EMAIL, TEST_PASSWORD);
    await page.getByRole("button", { name: "Logout" }).click();
    await expect(page).toHaveURL(/\/$/);

    // Protected route now bounces back to /login.
    await page.goto("/medications");
    await expect(page).toHaveURL(/\/login$/);
  });

  test("create, edit, and delete a medication", async ({ page }) => {
    await login(page, TEST_EMAIL, TEST_PASSWORD);

    const stamp = Date.now();
    const initialName = `E2E CRUD Med ${stamp}`;
    const updatedName = `E2E CRUD Edited ${stamp}`;

    // 1. Create
    await page.goto("/medications/new");
    await page.getByLabel(/^name$/i).fill(initialName);
    await setPlainDose(page, "250", "mg");
    await page.getByLabel(/untracked/i).check();
    await page.getByRole("button", { name: /add medication/i }).click();
    await expect(page).toHaveURL(/\/medications$/);
    await expect(
      page.getByRole("link", { name: initialName, exact: true }),
    ).toBeVisible();

    // 2. Edit name and quantity
    await page.getByRole("link", { name: `Edit ${initialName}` }).click();
    await expect(page).toHaveURL(/\/medications\/[0-9a-f-]{36}\/edit$/);
    const nameInput = page.getByLabel(/^name$/i);
    await nameInput.clear();
    await nameInput.fill(updatedName);
    await page.getByLabel(/quantity per dose/i).fill("500");
    await page.getByRole("button", { name: /save changes/i }).click();
    await expect(page).toHaveURL(/\/medications$/);
    await expect(
      page.getByRole("link", { name: updatedName, exact: true }),
    ).toBeVisible();
    await expect(page.getByText("500 mg").first()).toBeVisible();

    // 3. Delete
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: `Delete ${updatedName}` }).click();
    await expect(
      page.getByRole("link", { name: updatedName, exact: true }),
    ).toHaveCount(0);
  });
});
