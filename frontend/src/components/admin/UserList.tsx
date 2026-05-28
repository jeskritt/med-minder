import type { AdminUser } from "@/lib/adminUsers";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString();
}

export interface UserListProps {
  users: AdminUser[];
}

/**
 * Read-only list of active users (FR-002).  Row actions (edit / reset /
 * deactivate) arrive with User Stories 2 and 3.
 */
export function UserList({ users }: UserListProps) {
  if (users.length === 0) {
    return <p className="text-sm text-slate-500">No active users.</p>;
  }
  return (
    <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200">
      {users.map((u) => (
        <li
          key={u.id}
          className="flex items-center justify-between gap-4 px-4 py-3"
        >
          <div className="min-w-0">
            <p className="truncate font-medium text-slate-900">{u.name}</p>
            <p className="truncate text-sm text-slate-500">{u.email}</p>
          </div>
          <div className="flex shrink-0 items-center gap-3 text-sm">
            <span
              className={
                u.role === "admin"
                  ? "rounded-full bg-blue-100 px-2 py-0.5 font-medium text-blue-700"
                  : "rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-600"
              }
            >
              {u.role}
            </span>
            <span className="text-slate-400">{formatDate(u.created_at)}</span>
          </div>
        </li>
      ))}
    </ul>
  );
}
