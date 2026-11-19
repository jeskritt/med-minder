import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  ChangePasswordError,
  useChangePassword,
  useCurrentUser,
  useUpdateProfile,
  useUpdateTimezone,
} from "@/lib/auth";
import { TimezoneCombobox } from "@/components/profile/TimezoneCombobox";

const INPUT_CLASS = "mm-input mt-1";

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
      className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/40 p-4 backdrop-blur-sm"
    >
      <div className="mm-card max-h-[90vh] w-full max-w-md space-y-6 overflow-y-auto p-6 shadow-xl">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">Profile</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-full p-1.5 text-muted-foreground transition hover:bg-muted"
          >
            ✕
          </button>
        </div>

        <ProfileNameSection currentName={user?.name ?? ""} />
        <hr className="border-border" />
        <TimezoneSection currentTimezone={user?.timezone ?? "UTC"} />
        <hr className="border-border" />
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
          <p role="alert" className="mt-1 text-sm text-destructive">
            {errors.name.message}
          </p>
        )}
      </div>
      {updateProfile.isError && (
        <p role="alert" className="text-sm text-destructive">
          {(updateProfile.error as Error).message}
        </p>
      )}
      {updateProfile.isSuccess && (
        <p className="text-sm font-medium text-success">Name saved.</p>
      )}
      <button
        type="submit"
        disabled={updateProfile.isPending}
        className="mm-btn mm-btn-primary"
      >
        {updateProfile.isPending ? "Saving…" : "Save name"}
      </button>
    </form>
  );
}

function TimezoneSection({ currentTimezone }: { currentTimezone: string }) {
  const update = useUpdateTimezone();
  const [selected, setSelected] = useState(currentTimezone);
  // Re-sync when /me resolves (or a save round-trips) so the field reflects the
  // stored value and "dirty" compares against the truth. Render-phase
  // reconciliation, not an effect.
  const [lastTz, setLastTz] = useState(currentTimezone);
  if (currentTimezone !== lastTz) {
    setLastTz(currentTimezone);
    setSelected(currentTimezone);
  }

  const dirty = selected !== currentTimezone;

  return (
    <section aria-label="Timezone" className="space-y-2">
      <label htmlFor="profile-timezone" className="block text-sm font-medium">
        Timezone
      </label>
      <p className="text-sm text-muted-foreground">
        Used for your reminder times and quiet hours. Search by city, region, or
        UTC offset — e.g. “Edmonton”, “Alberta”, or “UTC-6”.
      </p>
      <TimezoneCombobox
        id="profile-timezone"
        value={selected}
        onChange={setSelected}
      />
      {update.isError && (
        <p role="alert" className="text-sm text-destructive">
          {(update.error as Error).message}
        </p>
      )}
      {update.isSuccess && !dirty && (
        <p className="text-sm font-medium text-success">Timezone saved.</p>
      )}
      <button
        type="button"
        onClick={() => update.mutate({ timezone: selected })}
        disabled={update.isPending || !dirty}
        className="mm-btn mm-btn-primary"
      >
        {update.isPending ? "Saving…" : "Save timezone"}
      </button>
    </section>
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
      <h3 className="text-sm font-semibold text-foreground">Change password</h3>
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
          <p role="alert" className="mt-1 text-sm text-destructive">
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
          <p role="alert" className="mt-1 text-sm text-destructive">
            {errors.new_password.message}
          </p>
        )}
      </div>
      {formError && (
        <p role="alert" className="text-sm text-destructive">
          {formError}
        </p>
      )}
      {changePassword.isSuccess && (
        <p className="text-sm font-medium text-success">
          Password changed. Other devices have been signed out.
        </p>
      )}
      <button
        type="submit"
        disabled={changePassword.isPending}
        className="mm-btn mm-btn-primary"
      >
        {changePassword.isPending ? "Changing…" : "Change password"}
      </button>
    </form>
  );
}
