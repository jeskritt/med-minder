/**
 * Feature 009: end-to-end smoke for in-app admin user management.
 *
 * Two flows against the live stack:
 *   1. Access control — a non-admin (granny) sees no Admin nav link and is
 *      redirected away from /admin (FR-001/FR-015).
 *   2. Full admin lifecycle — create (generated temp shown once + typed),
 *      edit/promote, reset password, deactivate, and read the audit trail
 *      (US1–US4), incl. the self-row guard (FR-019).
 *
 * The admin (`admin@example.com`, role=admin) and granny fixtures are
 * provisioned by `e2e/global-setup.ts`. Local run:
 *
 *     just dev                                # docker compose up
 *     E2E_RUN_ADMIN=1 pnpm test:e2e           # from frontend/
 *
 * Gated like the other specs: it needs the live `just dev` docker stack.
 * Created users use unique-per-run emails because email uniqueness is
 * case-insensitive *including soft-deleted* rows — a reused email would 409 on
 * rerun even after deactivation.
 */

import { test, expect, type Page } from "@playwright/test";
import { isE2eEnabled, login } from "./helpers";

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin@example.com";
const GRANNY_EMAIL = process.env.E2E_USER_EMAIL ?? "granny@example.com";
const PASSWORD =
  process.env.E2E_USER_PASSWORD ?? "correct horse battery staple";

/** Locate a user's list row by its (unique-per-run) email. */
function row(page: Page, email: string) {
  return page.locator("li", { hasText: email });
}

test.describe("In-app admin user management", () => {
  test.skip(
    !isE2eEnabled("E2E_RUN_ADMIN"),
    "Set E2E_RUN_ADMIN=1 or E2E_RUN_ALL=1 to run; requires the live `just dev` docker stack.",
  );

  test("a non-admin gets no Admin link and is redirected from /admin", async ({
    page,
  }) => {
    await login(page, GRANNY_EMAIL, PASSWORD);

    // No Admin entry in the nav for a role=user account (FR-015).
    await expect(page.getByRole("link", { name: "Admin" })).toHaveCount(0);

    // Typing the URL is bounced by the /admin beforeLoad guard (FR-001).
    await page.goto("/admin/users");
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("heading", { name: "Users" })).toHaveCount(0);
  });

  test("admin creates, edits, resets, deactivates, and audits users", async ({
    page,
  }) => {
    const stamp = Date.now();
    const genEmail = `e2e-gen-${stamp}@example.com`;
    const typedEmail = `e2e-typed-${stamp}@example.com`;

    await login(page, ADMIN_EMAIL, PASSWORD);

    // Reach the admin area via the nav link (admins only).
    await page.getByRole("link", { name: "Admin" }).click();
    await expect(page).toHaveURL(/\/admin\/users$/);
    await expect(page.getByRole("heading", { name: "Users" })).toBeVisible();

    // --- 1. Create with a generated temp password (shown once) -----------
    await page.getByRole("button", { name: /add user/i }).click();
    const addDialog = page.getByRole("dialog", { name: "Add user" });
    await expect(addDialog).toBeVisible();
    await addDialog.getByLabel("Email", { exact: true }).fill(genEmail);
    await addDialog
      .getByLabel("Display name", { exact: true })
      .fill("Gen User");
    await addDialog.getByLabel(/generate a temporary password/i).check();

    const [createResp] = await Promise.all([
      page.waitForResponse(
        (r) =>
          new URL(r.url()).pathname === "/api/v1/users" &&
          r.request().method() === "POST" &&
          r.status() === 201,
      ),
      addDialog.getByRole("button", { name: /create user/i }).click(),
    ]);
    const genId = ((await createResp.json()) as { user: { id: string } }).user
      .id;

    await expect(page.getByTestId("temp-password")).toBeVisible();
    await expect(page.getByText(/won.t be shown again/i)).toBeVisible();
    await page.getByRole("button", { name: /^done$/i }).click();

    // --- 2. Create with a typed password --------------------------------
    await page.getByRole("button", { name: /add user/i }).click();
    const addDialog2 = page.getByRole("dialog", { name: "Add user" });
    await addDialog2.getByLabel("Email", { exact: true }).fill(typedEmail);
    await addDialog2
      .getByLabel("Display name", { exact: true })
      .fill("Typed User");
    await addDialog2
      .getByLabel("Password", { exact: true })
      .fill("a fine long password");
    await Promise.all([
      page.waitForResponse(
        (r) =>
          new URL(r.url()).pathname === "/api/v1/users" &&
          r.request().method() === "POST" &&
          r.status() === 201,
      ),
      addDialog2.getByRole("button", { name: /create user/i }).click(),
    ]);
    await expect(page.getByText(typedEmail)).toBeVisible();

    // --- 3. Edit: promote the typed user to admin + rename --------------
    await row(page, typedEmail)
      .getByRole("button", { name: /^edit$/i })
      .click();
    const editDialog = page.getByRole("dialog", { name: "Edit user" });
    await editDialog.getByLabel("Role", { exact: true }).selectOption("admin");
    await editDialog
      .getByLabel("Display name", { exact: true })
      .fill("Typed Renamed");
    await Promise.all([
      page.waitForResponse(
        (r) =>
          new URL(r.url()).pathname.startsWith("/api/v1/users/") &&
          r.request().method() === "PATCH" &&
          r.status() === 200,
      ),
      editDialog.getByRole("button", { name: /save changes/i }).click(),
    ]);
    await expect(
      row(page, typedEmail).getByText("admin", { exact: true }),
    ).toBeVisible();

    // --- 4. Reset that user's password (generated, shown once) ----------
    await row(page, typedEmail)
      .getByRole("button", { name: /reset password/i })
      .click();
    const resetDialog = page.getByRole("dialog", { name: "Reset password" });
    await resetDialog.getByLabel(/generate a temporary password/i).check();
    await Promise.all([
      page.waitForResponse(
        (r) =>
          /\/api\/v1\/users\/[^/]+\/password$/.test(
            new URL(r.url()).pathname,
          ) &&
          r.request().method() === "POST" &&
          r.status() === 200,
      ),
      resetDialog.getByRole("button", { name: /reset password/i }).click(),
    ]);
    await expect(page.getByTestId("temp-password")).toBeVisible();
    await resetDialog.getByRole("button", { name: /^done$/i }).click();

    // --- 5. Self-row guard: the acting admin's own row is read-only -----
    const selfRow = row(page, ADMIN_EMAIL);
    await expect(selfRow.getByText("(you)")).toBeVisible();
    await expect(selfRow.getByRole("button", { name: /^edit$/i })).toHaveCount(
      0,
    );

    // --- 6. Deactivate the generated user via the in-app confirm --------
    await row(page, genEmail)
      .getByRole("button", { name: /deactivate/i })
      .click();
    const confirm = page.getByRole("dialog", { name: "Deactivate user" });
    await expect(confirm).toBeVisible(); // in-app modal, not native confirm()
    await Promise.all([
      page.waitForResponse(
        (r) =>
          new URL(r.url()).pathname === `/api/v1/users/${genId}` &&
          r.request().method() === "DELETE" &&
          r.status() === 204,
      ),
      confirm.getByRole("button", { name: /^deactivate$/i }).click(),
    ]);
    await expect(page.getByText(genEmail)).toHaveCount(0);

    // --- 7. Audit trail shows the actions for the generated user --------
    await page.getByRole("link", { name: /audit log/i }).click();
    await expect(page).toHaveURL(/\/admin\/audit$/);
    // The view renders "target {target_user_id}"; the generated user has at
    // least a Created and a Deactivated entry.
    await expect(page.getByText(genId, { exact: false }).first()).toBeVisible();
    await expect(page.getByText(/^created/i).first()).toBeVisible();
    await expect(page.getByText(/^deactivated/i).first()).toBeVisible();
  });
});
