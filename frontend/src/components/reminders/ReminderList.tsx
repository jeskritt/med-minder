import {
  useDismissReminder,
  useReminders,
  useSnoozeReminder,
} from "@/hooks/useReminders";

/**
 * In-app reminder list (Phase 7, FR-008) with snooze / dismiss actions (US2).
 */
export function ReminderList() {
  const { data, isLoading, isError } = useReminders();
  const snooze = useSnoozeReminder();
  const dismiss = useDismissReminder();

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading reminders…</p>;
  }
  if (isError) {
    return (
      <p className="text-sm text-destructive">Could not load reminders.</p>
    );
  }
  if (!data || data.length === 0) {
    return (
      <div className="mm-card px-6 py-10 text-center">
        <p className="font-medium text-foreground">You're all caught up</p>
        <p className="mt-1 text-sm text-muted-foreground">
          No reminders right now.
        </p>
      </div>
    );
  }

  return (
    <ul className="flex flex-col gap-2" data-testid="reminder-list">
      {data.map((reminder) => (
        <li
          key={reminder.id}
          className={`mm-card flex items-start justify-between gap-3 px-4 py-3 text-sm ${
            reminder.overdue ? "border-warning/50 bg-warning/10" : ""
          }`}
        >
          <div>
            <div className="font-semibold text-foreground">
              {reminder.title}
            </div>
            <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              {new Date(reminder.scheduled_for).toLocaleString()}
              {reminder.overdue && (
                <span className="mm-chip bg-warning/20 text-warning-foreground">
                  overdue
                </span>
              )}
              {reminder.status === "snoozed" && (
                <span className="mm-chip bg-muted text-muted-foreground">
                  snoozed
                </span>
              )}
            </div>
          </div>
          <div className="flex shrink-0 gap-2">
            <button
              type="button"
              onClick={() => snooze.mutate(reminder.id)}
              disabled={snooze.isPending}
              className="mm-btn mm-btn-secondary mm-btn-sm"
            >
              Snooze 1h
            </button>
            <button
              type="button"
              onClick={() => dismiss.mutate(reminder.id)}
              disabled={dismiss.isPending}
              className="mm-btn mm-btn-ghost mm-btn-sm"
            >
              Dismiss
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}
