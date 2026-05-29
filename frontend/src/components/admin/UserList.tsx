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
  "rounded-md px-2 py-1 text-sm font-medium text-slate-600 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40";

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
    return <p className="text-sm text-slate-500">No active users.</p>;
  }
  return (
    <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200">
      {users.map((u) => {
        const isSelf = u.id === currentUserId;
        return (
          <li
            key={u.id}
            className="flex items-center justify-between gap-4 px-4 py-3"
          >
            <div className="min-w-0">
              <p className="truncate font-medium text-slate-900">{u.name}</p>
              <p className="truncate text-sm text-slate-500">{u.email}</p>
            </div>
            <div className="flex shrink-0 items-center gap-2 text-sm">
              <span
                className={
                  u.role === "admin"
                    ? "rounded-full bg-blue-100 px-2 py-0.5 font-medium text-blue-700"
                    : "rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-600"
                }
              >
                {u.role}
              </span>
              <span className="hidden text-slate-400 sm:inline">
                {formatDate(u.created_at)}
              </span>
              {isSelf ? (
                <span
                  className="text-xs text-slate-400"
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
                    className={`${ACTION_CLASS} text-red-600 hover:bg-red-50`}
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
