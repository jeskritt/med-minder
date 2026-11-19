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
 *   - granny@example.com (granny smoke; the non-admin in the admin spec)
 *   - admin@example.com  (role=admin; the admin-users spec)
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
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin@example.com";
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

function ensureUser(
  email: string,
  name: string,
  role: "admin" | "user" = "user",
): void {
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
      role,
      "--timezone",
      "America/Toronto",
    ],
    PASSWORD,
  );
  if (add.ok) return;
  // Already exists (or transient) — force the known name & password so the
  // specs can log in deterministically regardless of prior state.
  const upd = dc(
    [
      "medminder-admin",
      "user",
      "update",
      "--email",
      email,
      "--name",
      name,
      "--password-stdin",
    ],
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
  const setCookies = loginResp.headers.getSetCookie();
  if (setCookies.length === 0) {
    throw new Error("global-setup: no session cookie returned");
  }
  const cookiePairs = setCookies.map((c) => c.split(";")[0]);
  const cookie = cookiePairs.join("; ");
  const csrfPair = cookiePairs.find((p) => p.startsWith("mm_csrf="));
  const csrfToken = csrfPair
    ? decodeURIComponent(csrfPair.slice("mm_csrf=".length))
    : "";
  const writeHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    Cookie: cookie,
    ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
  };

  // UX enhancements: schedules are shared user-level resources. Refresh
  // (or create) granny's "Morning" slot at the CURRENT local time on
  // every run, so the smoke's "Mark taken" always lands inside the ±2h
  // window and isn't intercepted by the out-of-schedule confirm. Without
  // the refresh the slot's time froze at first-creation and drifted out
  // of the window over days (the smoke then hit the confirm modal).
  const slot = new Date().toTimeString().slice(0, 5);
  const schedList = await fetch(`${API}/api/v1/schedules`, {
    headers: { Cookie: cookie },
  });
  const schedItems = (
    (await schedList.json()) as { items: { id: string; label: string }[] }
  ).items;
  const existingSlot = schedItems.find((s) => s.label === "Morning");
  let scheduleId: string;
  if (existingSlot) {
    const upd = await fetch(`${API}/api/v1/schedules/${existingSlot.id}`, {
      method: "PUT",
      headers: writeHeaders,
      body: JSON.stringify({
        time_of_day: slot,
        label: "Morning",
        days_of_week: 127,
      }),
    });
    if (upd.status !== 200) {
      throw new Error(
        `global-setup: granny schedule refresh failed (HTTP ${upd.status})`,
      );
    }
    scheduleId = existingSlot.id;
  } else {
    const schedResp = await fetch(`${API}/api/v1/schedules`, {
      method: "POST",
      headers: writeHeaders,
      body: JSON.stringify({ time_of_day: slot, label: "Morning" }),
    });
    if (schedResp.status !== 201) {
      throw new Error(
        `global-setup: granny schedule create failed (HTTP ${schedResp.status})`,
      );
    }
    scheduleId = ((await schedResp.json()) as { id: string }).id;
  }

  const list = await fetch(`${API}/api/v1/medications`, {
    headers: { Cookie: cookie },
  });
  const body = (await list.json()) as { items: { name: string }[] };
  if (!body.items.some((m) => m.name === GRANNY_MED_NAME)) {
    const create = await fetch(`${API}/api/v1/medications`, {
      method: "POST",
      headers: writeHeaders,
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

  // Ensure Granny's today slot starts untaken so reruns stay idempotent even if
  // a previous run aborted between "Mark taken" and "Confirm un-take".
  const todayResp = await fetch(`${API}/api/schedules/today`, {
    headers: { Cookie: cookie },
  });
  if (todayResp.ok) {
    const todayBody = (await todayResp.json()) as {
      items: { name: string; dose: { id: string } | null }[];
    };
    for (const item of todayBody.items) {
      if (item.name === GRANNY_MED_NAME && item.dose) {
        await fetch(`${API}/api/doses/${item.dose.id}/void`, {
          method: "POST",
          headers: writeHeaders,
        });
      }
    }
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
  const mig = dc(["alembic", "upgrade", "head"]);
  if (!mig.ok) {
    throw new Error(`global-setup: alembic upgrade head failed:\n${mig.out}`);
  }
  ensureUser(DEMO_EMAIL, "Demo User");
  ensureUser(GRANNY_EMAIL, "Granny");
  ensureUser(ADMIN_EMAIL, "Admin", "admin");
  await ensureGrannyMedication();
}
