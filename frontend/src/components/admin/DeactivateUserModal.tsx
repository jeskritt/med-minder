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
      className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/40 p-4 backdrop-blur-sm"
    >
      <div className="mm-card w-full max-w-md space-y-4 p-6 shadow-xl">
        <h2 className="text-lg font-semibold text-foreground">
          Deactivate user
        </h2>
        <p className="text-sm text-muted-foreground">
          Deactivate{" "}
          <span className="font-medium text-foreground">{user.email}</span>?
          They’ll be signed out everywhere and removed from the list. This can’t
          be undone in the app.
        </p>
        {deactivate.isError && (
          <p role="alert" className="text-sm text-destructive">
            {(deactivate.error as Error).message}
          </p>
        )}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="mm-btn mm-btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={confirm}
            disabled={deactivate.isPending}
            className="mm-btn mm-btn-danger"
          >
            {deactivate.isPending ? "Deactivating…" : "Deactivate"}
          </button>
        </div>
      </div>
    </div>
  );
}
