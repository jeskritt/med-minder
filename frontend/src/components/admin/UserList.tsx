import type { AdminUser } from "@/lib/adminUsers";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString();
}

export interface UserListProps {
  users: AdminUser[];
  /** The signed-in admin's id — their own row's actions are disabled (FR-019). */
  currentUserId?: string;
  onEdit: (user: AdminUser) => void;
  onResetPassword: (user: AdminUser) => void;
  onDeactivate: (user: AdminUser) => void;
}

const ACTION_CLASS =
  "rounded-full px-2.5 py-1 text-sm font-medium text-muted-foreground transition hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40";

/**
 * List of active users with per-row actions (Edit / Reset password /
 * Deactivate).  The acting admin's own row is read-only here — self-management
 * lives in the profile editor (FR-019).
 */
export function UserList({
  users,
  currentUserId,
  onEdit,
  onResetPassword,
  onDeactivate,
}: UserListProps) {
  if (users.length === 0) {
    return <p className="text-sm text-muted-foreground">No active users.</p>;
  }
  return (
    <ul className="mm-card divide-y divide-border/70 overflow-hidden">
      {users.map((u) => {
        const isSelf = u.id === currentUserId;
        return (
          <li
            key={u.id}
            className="flex items-center justify-between gap-4 px-4 py-3"
          >
            <div className="min-w-0">
              <p className="truncate font-semibold text-foreground">{u.name}</p>
              <p className="truncate text-sm text-muted-foreground">
                {u.email}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2 text-sm">
              <span
                className={
                  u.role === "admin"
                    ? "mm-chip bg-primary/12 text-primary"
                    : "mm-chip bg-muted text-muted-foreground"
                }
              >
                {u.role}
              </span>
              <span className="hidden text-muted-foreground sm:inline">
                {formatDate(u.created_at)}
              </span>
              {isSelf ? (
                <span
                  className="text-xs text-muted-foreground"
                  title="Manage your own account in the profile editor"
                >
                  (you)
                </span>
              ) : (
                <>
                  <button
                    type="button"
                    className={ACTION_CLASS}
                    onClick={() => onEdit(u)}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className={ACTION_CLASS}
                    onClick={() => onResetPassword(u)}
                  >
                    Reset password
                  </button>
                  <button
                    type="button"
                    className={`${ACTION_CLASS} text-destructive hover:bg-destructive/10 hover:text-destructive`}
                    onClick={() => onDeactivate(u)}
                  >
                    Deactivate
                  </button>
                </>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
