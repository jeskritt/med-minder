import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

/**
 * Playwright global setup — idempotently provisions the e2e fixtures
 * so the smokes are deterministic regardless of prior dev-DB state.
 *
 * Assumes the `just dev` docker stack is already up (the E2E_RUN_*
 * gate on each spec means "a live stack is provided"). We fail fast
 * with a clear message if the backend is unreachable.
 *
 * Provisions:
 *   - demo@example.com   (timer-modes specs)
 *   - granny@example.com (granny smoke)
 *   - a `none`-mode medication + 08:00 schedule owned by granny, so
 *     /today shows it with timer_state: null → the unchanged
 *     <TakenToggle> the granny smoke drives.
 *
 * Users are provisioned via the `medminder-admin` CLI in the backend
 * container (no public signup endpoint). `add` then, on duplicate,
 * `update --password-stdin` guarantees the password matches what the
 * specs expect even if the user pre-existed with another password.
 */

const REPO_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
);
const COMPOSE_FILE = path.join(REPO_ROOT, "docker-compose.yml");
const API = process.env.E2E_API_BASE ?? "http://localhost:8000";

const PASSWORD =
  process.env.E2E_USER_PASSWORD ?? "correct horse battery staple";
const DEMO_EMAIL = process.env.E2E_DEMO_EMAIL ?? "demo@example.com";
const GRANNY_EMAIL = process.env.E2E_USER_EMAIL ?? "granny@example.com";
const GRANNY_MED_NAME = "E2E Granny Lisinopril";

function dc(args: string[], stdin?: string): { ok: boolean; out: string } {
  try {
    const out = execFileSync(
      "docker",
      ["compose", "-f", COMPOSE_FILE, "exec", "-T", "backend", ...args],
      { input: stdin ?? "", encoding: "utf8", stdio: ["pipe", "pipe", "pipe"] },
    );
    return { ok: true, out };
  } catch (err) {
    const e = err as { stdout?: string; stderr?: string };
    return { ok: false, out: `${e.stdout ?? ""}${e.stderr ?? ""}` };
  }
}

function ensureUser(email: string, name: string): void {
  const add = dc(
    [
      "medminder-admin",
      "user",
      "add",
      "--email",
      email,
      "--name",
      name,
      "--role",
      "user",
      "--timezone",
      "America/Toronto",
    ],
    PASSWORD,
  );
  if (add.ok) return;
  // Already exists (or transient) — force the known password so the
  // specs can log in deterministically regardless of prior state.
  const upd = dc(
    ["medminder-admin", "user", "update", "--email", email, "--password-stdin"],
    PASSWORD,
  );
  if (!upd.ok) {
    throw new Error(
      `global-setup: could not provision ${email}.\nadd: ${add.out}\nupdate: ${upd.out}`,
    );
  }
}

async function ensureGrannyMedication(): Promise<void> {
  const loginResp = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: GRANNY_EMAIL, password: PASSWORD }),
  });
  if (loginResp.status !== 204) {
    throw new Error(
      `global-setup: granny login failed (HTTP ${loginResp.status})`,
    );
  }
  const setCookie = loginResp.headers.get("set-cookie");
  if (!setCookie) throw new Error("global-setup: no session cookie returned");
  const cookie = setCookie.split(";")[0];

  const list = await fetch(`${API}/api/v1/medications`, {
    headers: { Cookie: cookie },
  });
  const body = (await list.json()) as { items: { name: string }[] };
  if (body.items.some((m) => m.name === GRANNY_MED_NAME)) return;

  // UX enhancements: schedules are shared user-level resources; create
  // the slot first, then attach the medication by id. Use the current
  // local time so the granny smoke's "Mark taken" lands inside the
  // ±2h window and isn't intercepted by the out-of-schedule confirm.
  const slot = new Date().toTimeString().slice(0, 5);
  const schedResp = await fetch(`${API}/api/v1/schedules`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Cookie: cookie },
    body: JSON.stringify({ time_of_day: slot, label: "Morning" }),
  });
  if (schedResp.status !== 201) {
    throw new Error(
      `global-setup: granny schedule create failed (HTTP ${schedResp.status})`,
    );
  }
  const scheduleId = ((await schedResp.json()) as { id: string }).id;

  const create = await fetch(`${API}/api/v1/medications`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Cookie: cookie },
    body: JSON.stringify({
      name: GRANNY_MED_NAME,
      times_per_day: 1,
      quantity_per_dose: "10.000",
      unit: "mg",
      schedules: [scheduleId],
    }),
  });
  if (create.status !== 201) {
    throw new Error(
      `global-setup: granny medication create failed (HTTP ${create.status})`,
    );
  }
}

async function waitForBackend(): Promise<void> {
  for (let i = 0; i < 30; i++) {
    try {
      const r = await fetch(`${API}/healthz`);
      if (r.status === 200) return;
    } catch {
      /* not up yet */
    }
    await new Promise((res) => setTimeout(res, 1000));
  }
  throw new Error(
    `global-setup: backend not reachable at ${API} — is the docker stack up (just dev)?`,
  );
}

export default async function globalSetup(): Promise<void> {
  await waitForBackend();
  ensureUser(DEMO_EMAIL, "Demo User");
  ensureUser(GRANNY_EMAIL, "Granny");
  await ensureGrannyMedication();
}
