import { useState } from "react";
import {
  CreateUserError,
  useResetPassword,
  type AdminUser,
  type PasswordSetBody,
} from "@/lib/adminUsers";

const INPUT_CLASS = "mm-input mt-1";

export interface ResetPasswordDialogProps {
  user: AdminUser;
  onClose: () => void;
}

/**
 * Reset another user's password (User Story 2).  Type a password or generate a
 * one-time temporary one (shown once, FR-004).  Either way the target's other
 * sessions are revoked server-side (FR-007).
 */
export function ResetPasswordDialog({
  user,
  onClose,
}: ResetPasswordDialogProps) {
  const reset = useResetPassword();
  const [generate, setGenerate] = useState(false);
  const [password, setPassword] = useState("");
  const [tempPassword, setTempPassword] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [fieldError, setFieldError] = useState<string | null>(null);

  const submit = () => {
    setFieldError(null);
    if (!generate && password.length < 12) {
      setFieldError("Use at least 12 characters (or generate one).");
      return;
    }
    const body: PasswordSetBody = generate
      ? { generate: true }
      : { password, generate: false };
    reset.mutate(
      { userId: user.id, body },
      {
        onSuccess: (out) => {
          if (out.temporary_password) {
            setTempPassword(out.temporary_password);
          } else {
            onClose();
          }
        },
        onError: (err) => {
          if (err instanceof CreateUserError && err.field === "password") {
            setFieldError(err.message);
          }
        },
      },
    );
  };

  const formError =
    reset.error instanceof CreateUserError && reset.error.field === "form"
      ? reset.error.message
      : null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Reset password"
      className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/40 p-4 backdrop-blur-sm"
    >
      <div className="mm-card w-full max-w-md space-y-4 p-6 shadow-xl">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">
            Reset password
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-full p-1.5 text-muted-foreground transition hover:bg-muted"
          >
            ✕
          </button>
        </div>
        <p className="text-sm text-muted-foreground">
          For <span className="font-medium text-foreground">{user.email}</span>.
          This signs them out everywhere.
        </p>

        {tempPassword ? (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Share this temporary password now — it won’t be shown again.
            </p>
            <code
              data-testid="temp-password"
              className="block break-all rounded-lg bg-muted px-3 py-2 font-mono text-sm text-foreground"
            >
              {tempPassword}
            </code>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => {
                  void navigator.clipboard?.writeText(tempPassword);
                  setCopied(true);
                }}
                className="mm-btn mm-btn-secondary"
              >
                {copied ? "Copied" : "Copy"}
              </button>
              <button
                type="button"
                onClick={onClose}
                className="mm-btn mm-btn-primary"
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                className="size-4 rounded"
                checked={generate}
                onChange={(e) => setGenerate(e.target.checked)}
              />
              Generate a temporary password
            </label>
            {!generate && (
              <div>
                <label
                  htmlFor="reset-password"
                  className="block text-sm font-medium text-foreground"
                >
                  New password
                </label>
                <input
                  id="reset-password"
                  type="password"
                  autoComplete="new-password"
                  className={INPUT_CLASS}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            )}
            {fieldError && (
              <p role="alert" className="text-sm text-destructive">
                {fieldError}
              </p>
            )}
            {formError && (
              <p role="alert" className="text-sm text-destructive">
                {formError}
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
                onClick={submit}
                disabled={reset.isPending}
                className="mm-btn mm-btn-primary"
              >
                {reset.isPending ? "Resetting…" : "Reset password"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
