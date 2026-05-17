import { type Page, expect } from "@playwright/test";

/**
 * Log in through the real UI and wait for the app's own post-login
 * navigation to settle.
 *
 * `src/routes/login.tsx` performs an async `POST /auth/login` and, on
 * success, `navigate({ to: "/medications" })`. The session cookie is
 * set by that round-trip. Specs used to `click("Sign in")` then
 * immediately `page.goto(...)`, racing the cookie — the destination
 * route's `beforeLoad` `/me` check 401'd and redirected back to
 * `/login`. Awaiting the `/medications` URL is the app's own success
 * signal: it proves the login resolved and the cookie is set before
 * the caller navigates anywhere.
 */
export async function login(
  page: Page,
  email: string,
  password: string,
): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/medications$/);
}
