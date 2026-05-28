import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useUsers } from "@/lib/adminUsers";
import { UserList } from "@/components/admin/UserList";
import { UserFormDialog } from "@/components/admin/UserFormDialog";

export const Route = createFileRoute("/admin/users")({
  component: AdminUsersPage,
});

function AdminUsersPage() {
  const { data: users, isLoading, isError } = useUsers();
  const [addOpen, setAddOpen] = useState(false);

  return (
    <div className="mx-auto max-w-2xl px-4 py-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Users</h1>
        <button
          type="button"
          onClick={() => setAddOpen(true)}
          className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-blue-700"
        >
          Add user
        </button>
      </div>

      {isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {isError && (
        <p role="alert" className="text-sm text-red-600">
          Could not load users.
        </p>
      )}
      {users && <UserList users={users} />}

      <UserFormDialog open={addOpen} onClose={() => setAddOpen(false)} />
    </div>
  );
}
