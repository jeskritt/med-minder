import { createFileRoute, Link } from "@tanstack/react-router";
import { useAuditLog, type AuditEntry } from "@/lib/adminUsers";

export const Route = createFileRoute("/admin/audit")({
  component: AdminAuditPage,
});

function actionLabel(action: AuditEntry["action"]): string {
  switch (action) {
    case "create":
      return "Created";
    case "update":
      return "Updated";
    case "role_change":
      return "Role changed";
    case "password_reset":
      return "Password reset";
    case "deactivate":
      return "Deactivated";
  }
}

function summarize(details: AuditEntry["details"]): string {
  const role = (details as { role?: unknown }).role;
  if (typeof role === "string") return `role ${role}`;
  const fields = (details as { fields?: unknown }).fields;
  if (Array.isArray(fields) && fields.length > 0) return fields.join(", ");
  return "";
}

function formatWhen(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

/**
 * Read-only audit trail (User Story 4).  Successful admin actions, newest
 * first; never any secret values (FR-013/FR-014).
 */
function AdminAuditPage() {
  const { data: entries, isLoading, isError } = useAuditLog();

  return (
    <div className="mx-auto max-w-2xl px-4 py-6">
      <div className="mb-5 flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          Audit log
        </h1>
        <Link to="/admin/users" className="mm-btn mm-btn-ghost -mr-2">
          ← Users
        </Link>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {isError && (
        <p role="alert" className="text-sm text-destructive">
          Could not load the audit log.
        </p>
      )}
      {entries && entries.length === 0 && (
        <p className="text-sm text-muted-foreground">No audit entries yet.</p>
      )}
      {entries && entries.length > 0 && (
        <ul className="mm-card divide-y divide-border/70 overflow-hidden">
          {entries.map((e) => {
            const summary = summarize(e.details);
            return (
              <li key={e.id} className="px-4 py-3 text-sm">
                <div className="flex items-center justify-between gap-4">
                  <span className="font-semibold text-foreground">
                    {actionLabel(e.action)}
                    {summary && (
                      <span className="font-normal text-muted-foreground">
                        {" "}
                        — {summary}
                      </span>
                    )}
                  </span>
                  <span className="shrink-0 text-muted-foreground">
                    {formatWhen(e.created_at)}
                  </span>
                </div>
                <p className="mt-0.5 font-mono text-xs text-muted-foreground/70">
                  actor {e.actor_id} → target {e.target_user_id}
                </p>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
