import { useState } from "react";
import {
  CreateUserError,
  useResetPassword,
  type AdminUser,
  type PasswordSetBody,
} from "@/lib/adminUsers";

const INPUT_CLASS =
  "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30";

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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div className="w-full max-w-md space-y-4 rounded-lg border bg-white p-6 shadow">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">
            Reset password
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded p-1 text-slate-500 hover:bg-slate-100"
          >
            ✕
          </button>
        </div>
        <p className="text-sm text-slate-600">
          For <span className="font-medium">{user.email}</span>. This signs them
          out everywhere.
        </p>

        {tempPassword ? (
          <div className="space-y-3">
            <p className="text-sm text-slate-600">
              Share this temporary password now — it won’t be shown again.
            </p>
            <code
              data-testid="temp-password"
              className="block break-all rounded-lg bg-slate-100 px-3 py-2 font-mono text-sm text-slate-900"
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
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                {copied ? "Copied" : "Copy"}
              </button>
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg bg-blue-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-blue-700"
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={generate}
                onChange={(e) => setGenerate(e.target.checked)}
              />
              Generate a temporary password
            </label>
            {!generate && (
              <div>
                <label
                  htmlFor="reset-password"
                  className="block text-sm font-medium"
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
              <p role="alert" className="text-sm text-red-600">
                {fieldError}
              </p>
            )}
            {formError && (
              <p role="alert" className="text-sm text-red-600">
                {formError}
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
                onClick={submit}
                disabled={reset.isPending}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
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
