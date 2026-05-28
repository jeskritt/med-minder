import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  CreateUserError,
  useCreateUser,
  type UserCreateBody,
} from "@/lib/adminUsers";

const INPUT_CLASS =
  "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30";

const schema = z.object({
  email: z.string().trim().email("Enter a valid email"),
  name: z
    .string()
    .trim()
    .min(1, "Name is required")
    .max(100, "Use 100 characters or fewer"),
  role: z.enum(["admin", "user"]),
  password: z.string(),
});
type FormValues = z.infer<typeof schema>;

export interface UserFormDialogProps {
  open: boolean;
  onClose: () => void;
}

/**
 * Create-user modal (User Story 1).  Follows the app's plain-render modal
 * pattern (`role="dialog"` + fixed overlay, no native `<dialog>`).  After a
 * generated-password create, swaps to a one-time reveal panel — the plaintext
 * is shown once and never retrievable afterward (FR-004).
 */
export function UserFormDialog({ open, onClose }: UserFormDialogProps) {
  const createUser = useCreateUser();
  const [generate, setGenerate] = useState(false);
  const [tempPassword, setTempPassword] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", name: "", role: "user", password: "" },
  });

  if (!open) return null;

  const closeAll = () => {
    reset();
    setGenerate(false);
    setTempPassword(null);
    setCopied(false);
    onClose();
  };

  const onSubmit = handleSubmit((values) => {
    // The 12-char minimum only applies to a typed password; a generated one is
    // produced server-side. Validate the typed case here so the message lands
    // on the password field (the server re-checks via `password_too_short`).
    if (!generate && values.password.length < 12) {
      setError("password", {
        message: "Use at least 12 characters (or generate one)",
      });
      return;
    }
    const body: UserCreateBody = generate
      ? {
          email: values.email,
          name: values.name,
          role: values.role,
          generate: true,
        }
      : {
          email: values.email,
          name: values.name,
          role: values.role,
          password: values.password,
          generate: false,
        };
    createUser.mutate(body, {
      onSuccess: (created) => {
        if (created.temporary_password) {
          setTempPassword(created.temporary_password);
        } else {
          closeAll();
        }
      },
      onError: (err) => {
        if (err instanceof CreateUserError && err.field !== "form") {
          setError(err.field, { message: err.message });
        }
      },
    });
  });

  const formError =
    createUser.error instanceof CreateUserError &&
    createUser.error.field === "form"
      ? createUser.error.message
      : null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Add user"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div className="max-h-[90vh] w-full max-w-md space-y-5 overflow-y-auto rounded-lg border bg-white p-6 shadow">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">
            {tempPassword ? "User created" : "Add user"}
          </h2>
          <button
            type="button"
            onClick={closeAll}
            aria-label="Close"
            className="rounded p-1 text-slate-500 hover:bg-slate-100"
          >
            ✕
          </button>
        </div>

        {tempPassword ? (
          <div className="space-y-3">
            <p className="text-sm text-slate-600">
              Share this temporary password with the user now — it won’t be
              shown again.
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
                onClick={closeAll}
                className="rounded-lg bg-blue-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-blue-700"
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={onSubmit} noValidate className="space-y-3">
            <div>
              <label
                htmlFor="new-user-email"
                className="block text-sm font-medium"
              >
                Email
              </label>
              <input
                id="new-user-email"
                type="email"
                autoComplete="off"
                className={INPUT_CLASS}
                {...register("email")}
              />
              {errors.email && (
                <p role="alert" className="mt-1 text-sm text-red-600">
                  {errors.email.message}
                </p>
              )}
            </div>
            <div>
              <label
                htmlFor="new-user-name"
                className="block text-sm font-medium"
              >
                Display name
              </label>
              <input
                id="new-user-name"
                type="text"
                className={INPUT_CLASS}
                {...register("name")}
              />
              {errors.name && (
                <p role="alert" className="mt-1 text-sm text-red-600">
                  {errors.name.message}
                </p>
              )}
            </div>
            <div>
              <label
                htmlFor="new-user-role"
                className="block text-sm font-medium"
              >
                Role
              </label>
              <select
                id="new-user-role"
                className={INPUT_CLASS}
                {...register("role")}
              >
                <option value="user">User</option>
                <option value="admin">Admin</option>
              </select>
            </div>
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
                  htmlFor="new-user-password"
                  className="block text-sm font-medium"
                >
                  Password
                </label>
                <input
                  id="new-user-password"
                  type="password"
                  autoComplete="new-password"
                  className={INPUT_CLASS}
                  {...register("password")}
                />
                {errors.password && (
                  <p role="alert" className="mt-1 text-sm text-red-600">
                    {errors.password.message}
                  </p>
                )}
              </div>
            )}
            {formError && (
              <p role="alert" className="text-sm text-red-600">
                {formError}
              </p>
            )}
            <button
              type="submit"
              disabled={createUser.isPending}
              className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {createUser.isPending ? "Creating…" : "Create user"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
