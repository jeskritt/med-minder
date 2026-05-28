import { useDeactivateUser, type AdminUser } from "@/lib/adminUsers";

export interface DeactivateUserModalProps {
  user: AdminUser;
  onClose: () => void;
}

/**
 * In-app confirm for deactivating a user (User Story 3).  Deliberately an
 * in-app `role="dialog"` modal, NOT the native `confirm()` — consistent with
 * the rest of the app's destructive-action confirms.  On confirm the user is
 * soft-deleted and signed out everywhere (FR-008); there is no in-app restore
 * (FR-016).
 */
export function DeactivateUserModal({
  user,
  onClose,
}: DeactivateUserModalProps) {
  const deactivate = useDeactivateUser();

  const confirm = () => {
    deactivate.mutate(user.id, { onSuccess: () => onClose() });
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Deactivate user"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div className="w-full max-w-md space-y-4 rounded-lg border bg-white p-6 shadow">
        <h2 className="text-lg font-semibold text-slate-900">
          Deactivate user
        </h2>
        <p className="text-sm text-slate-600">
          Deactivate <span className="font-medium">{user.email}</span>? They’ll
          be signed out everywhere and removed from the list. This can’t be
          undone in the app.
        </p>
        {deactivate.isError && (
          <p role="alert" className="text-sm text-red-600">
            {(deactivate.error as Error).message}
          </p>
        )}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={confirm}
            disabled={deactivate.isPending}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
          >
            {deactivate.isPending ? "Deactivating…" : "Deactivate"}
          </button>
        </div>
      </div>
    </div>
  );
}
