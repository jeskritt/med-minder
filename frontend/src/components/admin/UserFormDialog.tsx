import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  CreateUserError,
  useCreateUser,
  useUpdateUser,
  type AdminUser,
  type UserCreateBody,
} from "@/lib/adminUsers";

const INPUT_CLASS = "mm-input mt-1";
const LABEL_CLASS = "block text-sm font-medium text-foreground";

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
  /** When set, the dialog edits this user (name/email/role); password is
   *  reset via the separate dialog. When omitted, it creates a new user. */
  editUser?: AdminUser | null;
}

/**
 * Create/edit user modal (User Stories 1 & 2).  Follows the app's plain-render
 * modal pattern (`role="dialog"` + fixed overlay, no native `<dialog>`).  In
 * create mode with "generate", swaps to a one-time temp-password reveal — the
 * plaintext is shown once and never retrievable afterward (FR-004).
 */
export function UserFormDialog({
  open,
  onClose,
  editUser,
}: UserFormDialogProps) {
  const isEdit = !!editUser;
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const mutation = isEdit ? updateUser : createUser;

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
    defaultValues: {
      email: editUser?.email ?? "",
      name: editUser?.name ?? "",
      role: editUser?.role ?? "user",
      password: "",
    },
  });

  if (!open) return null;

  const closeAll = () => {
    reset();
    setGenerate(false);
    setTempPassword(null);
    setCopied(false);
    onClose();
  };

  const onError = (err: unknown) => {
    if (err instanceof CreateUserError && err.field !== "form") {
      setError(err.field, { message: err.message });
    }
  };

  const onSubmit = handleSubmit((values) => {
    if (isEdit && editUser) {
      updateUser.mutate(
        {
          userId: editUser.id,
          body: { name: values.name, email: values.email, role: values.role },
        },
        { onSuccess: () => closeAll(), onError },
      );
      return;
    }
    // Create mode: the 12-char minimum only applies to a typed password; a
    // generated one is produced server-side (server re-checks regardless).
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
      onError,
    });
  });

  const formError =
    mutation.error instanceof CreateUserError && mutation.error.field === "form"
      ? mutation.error.message
      : null;

  const title = tempPassword
    ? "User created"
    : isEdit
      ? "Edit user"
      : "Add user";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={isEdit ? "Edit user" : "Add user"}
      className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/40 p-4 backdrop-blur-sm"
    >
      <div className="mm-card max-h-[90vh] w-full max-w-md space-y-5 overflow-y-auto p-6 shadow-xl">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">{title}</h2>
          <button
            type="button"
            onClick={closeAll}
            aria-label="Close"
            className="rounded-full p-1.5 text-muted-foreground transition hover:bg-muted"
          >
            ✕
          </button>
        </div>

        {tempPassword ? (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Share this temporary password with the user now — it won’t be
              shown again.
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
                onClick={closeAll}
                className="mm-btn mm-btn-primary"
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={onSubmit} noValidate className="space-y-3">
            <div>
              <label htmlFor="user-email" className={LABEL_CLASS}>
                Email
              </label>
              <input
                id="user-email"
                type="email"
                autoComplete="off"
                className={INPUT_CLASS}
                {...register("email")}
              />
              {errors.email && (
                <p role="alert" className="mt-1 text-sm text-destructive">
                  {errors.email.message}
                </p>
              )}
            </div>
            <div>
              <label htmlFor="user-name" className={LABEL_CLASS}>
                Display name
              </label>
              <input
                id="user-name"
                type="text"
                className={INPUT_CLASS}
                {...register("name")}
              />
              {errors.name && (
                <p role="alert" className="mt-1 text-sm text-destructive">
                  {errors.name.message}
                </p>
              )}
            </div>
            <div>
              <label htmlFor="user-role" className={LABEL_CLASS}>
                Role
              </label>
              <select
                id="user-role"
                className={INPUT_CLASS}
                {...register("role")}
              >
                <option value="user">User</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            {!isEdit && (
              <>
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
                    <label htmlFor="user-password" className={LABEL_CLASS}>
                      Password
                    </label>
                    <input
                      id="user-password"
                      type="password"
                      autoComplete="new-password"
                      className={INPUT_CLASS}
                      {...register("password")}
                    />
                    {errors.password && (
                      <p role="alert" className="mt-1 text-sm text-destructive">
                        {errors.password.message}
                      </p>
                    )}
                  </div>
                )}
              </>
            )}
            {formError && (
              <p role="alert" className="text-sm text-destructive">
                {formError}
              </p>
            )}
            <button
              type="submit"
              disabled={mutation.isPending}
              className="mm-btn mm-btn-primary mm-btn-block"
            >
              {mutation.isPending
                ? "Saving…"
                : isEdit
                  ? "Save changes"
                  : "Create user"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
