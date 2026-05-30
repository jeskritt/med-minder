import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useCurrentUser, useUpdateQuietHours } from "@/lib/auth";

const INPUT_CLASS = "mm-input mt-1 w-auto";

const schema = z
  .object({
    enabled: z.boolean(),
    start: z.string(),
    end: z.string(),
  })
  .refine((v) => !v.enabled || (v.start !== "" && v.end !== ""), {
    message: "Pick both a start and end time.",
    path: ["end"],
  })
  .refine((v) => !v.enabled || v.start !== v.end, {
    message: "Start and end must be different.",
    path: ["end"],
  });
type QuietHoursValues = z.infer<typeof schema>;

/** Server times arrive as "HH:MM:SS" (or null); native time inputs want "HH:MM". */
function toHHMM(t: string | null | undefined): string {
  return t ? t.slice(0, 5) : "";
}

/**
 * Self-service quiet-hours editor (lives on the Reminders page beside
 * EnableNotifications).  Quiet hours are an all-or-nothing pair, so a single
 * "Mute…" checkbox gates the two time inputs: unchecked + Save clears the
 * window (`PUT /me/quiet-hours` with both null); checked sends `HH:MM` bounds.
 * The timezone label comes from `/me` and is read-only (admin/CLI-managed).
 */
export function QuietHoursSection() {
  const { data: user } = useCurrentUser();
  const update = useUpdateQuietHours();

  const startStored = toHHMM(user?.quiet_hours_start);
  const endStored = toHHMM(user?.quiet_hours_end);
  const hasQuiet = startStored !== "" && endStored !== "";

  const {
    register,
    handleSubmit,
    control,
    formState: { errors },
  } = useForm<QuietHoursValues>({
    resolver: zodResolver(schema),
    // `values` keeps the form in sync once /me loads and after a save refetch.
    values: {
      enabled: hasQuiet,
      start: hasQuiet ? startStored : "22:00",
      end: hasQuiet ? endStored : "07:00",
    },
  });

  const enabled = useWatch({ control, name: "enabled" });

  const onSubmit = handleSubmit((v) =>
    update.mutate(
      v.enabled ? { start: v.start, end: v.end } : { start: null, end: null },
    ),
  );

  return (
    <form
      onSubmit={onSubmit}
      noValidate
      aria-label="Quiet hours"
      className="space-y-2"
    >
      <h2 className="text-sm font-semibold text-foreground">
        Quiet hours{user?.timezone ? ` (${user.timezone})` : ""}
      </h2>
      <p className="text-sm text-muted-foreground">
        Reminders that fall in this window are held until it ends, instead of
        notifying you.
      </p>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" {...register("enabled")} />
        Mute reminders during these hours
      </label>
      {enabled && (
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex flex-col">
            <label
              htmlFor="quiet-start"
              className="text-sm font-medium text-foreground"
            >
              Start
            </label>
            <input
              id="quiet-start"
              type="time"
              className={INPUT_CLASS}
              {...register("start")}
            />
          </div>
          <div className="flex flex-col">
            <label
              htmlFor="quiet-end"
              className="text-sm font-medium text-foreground"
            >
              End
            </label>
            <input
              id="quiet-end"
              type="time"
              className={INPUT_CLASS}
              {...register("end")}
            />
          </div>
        </div>
      )}
      {errors.end && (
        <p role="alert" className="text-sm text-destructive">
          {errors.end.message}
        </p>
      )}
      {update.isError && (
        <p role="alert" className="text-sm text-destructive">
          {(update.error as Error).message}
        </p>
      )}
      {update.isSuccess && (
        <p className="text-sm font-medium text-success">Quiet hours saved.</p>
      )}
      <button
        type="submit"
        disabled={update.isPending}
        className="mm-btn mm-btn-primary"
      >
        {update.isPending ? "Saving…" : "Save quiet hours"}
      </button>
    </form>
  );
}
