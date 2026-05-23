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
  // Deterministically await the login POST (204) AS the click fires.
  // `login.tsx` awaits POST /auth/login then navigate("/medications"),
  // whose `beforeLoad` re-fetches /me — and on a cold rebuild (first
  // spec, cold Vite + cold backend) the click→POST→cookie→nav→/me
  // path can exceed Playwright's default 5 s expect timeout, leaving
  // the page still at /login when `toHaveURL(/\/medications$/)`
  // checks. Waiting for the 204 here proves the cookie round-trip
  // completed before the URL assertion, and a 30 s timeout absorbs
  // the cold first-spec latency without affecting warm runs (which
  // still resolve in ms).
  await Promise.all([
    page.waitForResponse(
      (r) =>
        new URL(r.url()).pathname === "/auth/login" &&
        r.request().method() === "POST" &&
        r.status() === 204,
    ),
    page.getByRole("button", { name: /sign in/i }).click(),
  ]);
  await expect(page).toHaveURL(/\/medications$/, { timeout: 30_000 });
}

/**
 * Backend base URL — hit the API directly (not via Playwright's
 * baseURL → the Vite dev server, whose `/api` proxy *strips* the
 * prefix and 404s). Mirrors `e2e/global-setup.ts`. `page.request`
 * shares the browser context's `mm_session` cookie (domain `localhost`,
 * port-agnostic), so this is authenticated like the app's own fetches.
 */
const API_BASE = process.env.E2E_API_BASE ?? "http://localhost:8000";

/**
 * Switch the medication form out of its default pill-based mode and set
 * a plain quantity-per-dose + unit. The form now defaults `pill_based`
 * ON (most meds are pills), which hides the bare quantity field; these
 * specs use simple "1 tab" doses, so flip it off first.
 */
export async function setPlainDose(
  page: Page,
  quantity: string,
  unit: string,
): Promise<void> {
  const pill = page.getByLabel(/pill-based/i);
  if (await pill.isChecked()) {
    await pill.uncheck();
  }
  await page.getByLabel(/quantity per dose/i).fill(quantity);
  await page.getByLabel(/^unit$/i).fill(unit);
}

/**
 * Add a new schedule slot through the SchedulePicker (UX enhancements
 * replaced the old per-med time inputs with a shared-schedule chip
 * picker). Creates the slot and auto-selects its chip.
 *
 * Pass a unique `label` when a test needs to target this slot's
 * chip / edit / delete controls unambiguously — the shared dev DB
 * accumulates many same-time chips, and the controls key on the
 * displayed label.
 */
export async function addSchedule(
  page: Page,
  time: string,
  label?: string,
): Promise<void> {
  await page.getByRole("button", { name: /add a new schedule/i }).click();
  await page.getByLabel(/^time$/i).fill(time);
  if (label !== undefined) {
    await page.getByLabel(/label \(optional\)/i).fill(label);
  }
  await page.getByRole("button", { name: /^add$/i }).click();
}

/**
 * Resolve a medication's id by its (unique-per-run) name via the API.
 * Used to target today-row controls by stable `data-testid` instead of
 * fragile name/text/role row scoping over a shared, accumulating dev DB.
 */
export async function medIdByName(page: Page, name: string): Promise<string> {
  const resp = await page.request.get(`${API_BASE}/api/v1/medications`);
  expect(resp.ok()).toBeTruthy();
  const body = (await resp.json()) as {
    items: { id: string; name: string }[];
  };
  const med = body.items.find((m) => m.name === name);
  if (!med) throw new Error(`medication not found by name: ${name}`);
  return med.id;
}
