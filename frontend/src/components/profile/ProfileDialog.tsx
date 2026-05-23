import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  ChangePasswordError,
  useChangePassword,
  useCurrentUser,
  useUpdateProfile,
} from "@/lib/auth";

const INPUT_CLASS =
  "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30";

const nameSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "Name is required")
    .max(100, "Use 100 characters or fewer"),
});
type NameValues = z.infer<typeof nameSchema>;

const passwordSchema = z.object({
  current_password: z.string().min(1, "Enter your current password"),
  new_password: z.string().min(12, "Use at least 12 characters"),
});
type PasswordValues = z.infer<typeof passwordSchema>;

export interface ProfileDialogProps {
  open: boolean;
  onClose: () => void;
}

/**
 * Self-service profile editor (feature 007).  A modal opened from the nav-bar
 * name; lets the signed-in user change their display name and password.
 *
 * Follows the app's existing modal pattern (`UntakeConfirmModal.tsx`): a plain
 * conditional render with `role="dialog"` / `aria-modal` and a fixed overlay —
 * no native `<dialog>`, so it works in jsdom without polyfills.
 */
export function ProfileDialog({ open, onClose }: ProfileDialogProps) {
  const { data: user } = useCurrentUser();
  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Profile"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div className="max-h-[90vh] w-full max-w-md space-y-6 overflow-y-auto rounded-lg border bg-white p-6 shadow">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">Profile</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded p-1 text-slate-500 hover:bg-slate-100"
          >
            ✕
          </button>
        </div>

        <ProfileNameSection currentName={user?.name ?? ""} />
        <hr className="border-slate-200" />
        <ChangePasswordSection />
      </div>
    </div>
  );
}

function ProfileNameSection({ currentName }: { currentName: string }) {
  const updateProfile = useUpdateProfile();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<NameValues>({
    resolver: zodResolver(nameSchema),
    values: { name: currentName },
  });

  const onSubmit = handleSubmit((values) => updateProfile.mutate(values));

  return (
    <form
      onSubmit={onSubmit}
      noValidate
      aria-label="Edit profile name"
      className="space-y-2"
    >
      <div>
        <label htmlFor="profile-name" className="block text-sm font-medium">
          Display name
        </label>
        <input
          id="profile-name"
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
      {updateProfile.isError && (
        <p role="alert" className="text-sm text-red-600">
          {(updateProfile.error as Error).message}
        </p>
      )}
      {updateProfile.isSuccess && (
        <p className="text-sm text-green-700">Name saved.</p>
      )}
      <button
        type="submit"
        disabled={updateProfile.isPending}
        className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {updateProfile.isPending ? "Saving…" : "Save name"}
      </button>
    </form>
  );
}

function ChangePasswordSection() {
  const changePassword = useChangePassword();
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<PasswordValues>({ resolver: zodResolver(passwordSchema) });

  const onSubmit = handleSubmit((values) =>
    changePassword.mutate(values, {
      onSuccess: () => reset(),
      onError: (err) => {
        if (err instanceof ChangePasswordError && err.field !== "form") {
          setError(err.field, { message: err.message });
        }
      },
    }),
  );

  const formError =
    changePassword.error instanceof ChangePasswordError &&
    changePassword.error.field === "form"
      ? changePassword.error.message
      : null;

  return (
    <form
      onSubmit={onSubmit}
      noValidate
      aria-label="Change password"
      className="space-y-2"
    >
      <h3 className="text-sm font-semibold text-slate-900">Change password</h3>
      <div>
        <label htmlFor="current-password" className="block text-sm font-medium">
          Current password
        </label>
        <input
          id="current-password"
          type="password"
          autoComplete="current-password"
          className={INPUT_CLASS}
          {...register("current_password")}
        />
        {errors.current_password && (
          <p role="alert" className="mt-1 text-sm text-red-600">
            {errors.current_password.message}
          </p>
        )}
      </div>
      <div>
        <label htmlFor="new-password" className="block text-sm font-medium">
          New password
        </label>
        <input
          id="new-password"
          type="password"
          autoComplete="new-password"
          className={INPUT_CLASS}
          {...register("new_password")}
        />
        {errors.new_password && (
          <p role="alert" className="mt-1 text-sm text-red-600">
            {errors.new_password.message}
          </p>
        )}
      </div>
      {formError && (
        <p role="alert" className="text-sm text-red-600">
          {formError}
        </p>
      )}
      {changePassword.isSuccess && (
        <p className="text-sm text-green-700">
          Password changed. Other devices have been signed out.
        </p>
      )}
      <button
        type="submit"
        disabled={changePassword.isPending}
        className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {changePassword.isPending ? "Changing…" : "Change password"}
      </button>
    </form>
  );
}
