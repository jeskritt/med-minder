import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import { useUsers, type AdminUser } from "@/lib/adminUsers";
import { useCurrentUser } from "@/lib/auth";
import { UserList } from "@/components/admin/UserList";
import { UserFormDialog } from "@/components/admin/UserFormDialog";
import { ResetPasswordDialog } from "@/components/admin/ResetPasswordDialog";
import { DeactivateUserModal } from "@/components/admin/DeactivateUserModal";

export const Route = createFileRoute("/admin/users")({
  component: AdminUsersPage,
});

function AdminUsersPage() {
  const { data: users, isLoading, isError } = useUsers();
  const { data: me } = useCurrentUser();
  const [addOpen, setAddOpen] = useState(false);
  const [editUser, setEditUser] = useState<AdminUser | null>(null);
  const [resetUser, setResetUser] = useState<AdminUser | null>(null);
  const [deactivateUser, setDeactivateUser] = useState<AdminUser | null>(null);

  return (
    <div className="mx-auto max-w-2xl px-4 py-6">
      <div className="mb-5 flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          Users
        </h1>
        <div className="flex items-center gap-2">
          <Link to="/admin/audit" className="mm-btn mm-btn-ghost">
            Audit log
          </Link>
          <button
            type="button"
            onClick={() => setAddOpen(true)}
            className="mm-btn mm-btn-primary"
          >
            <Plus className="size-4" />
            Add user
          </button>
        </div>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {isError && (
        <p role="alert" className="text-sm text-destructive">
          Could not load users.
        </p>
      )}
      {users && (
        <UserList
          users={users}
          currentUserId={me?.id}
          onEdit={setEditUser}
          onResetPassword={setResetUser}
          onDeactivate={setDeactivateUser}
        />
      )}

      {addOpen && <UserFormDialog open onClose={() => setAddOpen(false)} />}
      {editUser && (
        <UserFormDialog
          key={editUser.id}
          open
          editUser={editUser}
          onClose={() => setEditUser(null)}
        />
      )}
      {resetUser && (
        <ResetPasswordDialog
          user={resetUser}
          onClose={() => setResetUser(null)}
        />
      )}
      {deactivateUser && (
        <DeactivateUserModal
          user={deactivateUser}
          onClose={() => setDeactivateUser(null)}
        />
      )}
    </div>
  );
}
