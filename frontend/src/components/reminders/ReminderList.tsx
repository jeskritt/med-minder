import { useReminders } from "@/hooks/useReminders";

/**
 * In-app reminder list (Phase 7, FR-008). Display-only for US1; snooze /
 * dismiss controls arrive in US2.
 */
export function ReminderList() {
  const { data, isLoading, isError } = useReminders();

  if (isLoading) {
    return <p className="text-sm text-slate-500">Loading reminders…</p>;
  }
  if (isError) {
    return (
      <p className="text-sm text-amber-700">Could not load reminders.</p>
    );
  }
  if (!data || data.length === 0) {
    return <p className="text-sm text-slate-500">No reminders right now.</p>;
  }

  return (
    <ul className="flex flex-col gap-2" data-testid="reminder-list">
      {data.map((reminder) => (
        <li
          key={reminder.id}
          className={`rounded-lg border px-3 py-2 text-sm ${
            reminder.overdue
              ? "border-amber-300 bg-amber-50"
              : "border-slate-200"
          }`}
        >
          <div className="font-medium text-gray-900">{reminder.title}</div>
          <div className="text-xs text-slate-500">
            {new Date(reminder.scheduled_for).toLocaleString()}
            {reminder.overdue && (
              <span className="ml-2 text-amber-700">overdue</span>
            )}
            {reminder.status === "snoozed" && (
              <span className="ml-2 text-slate-500">snoozed</span>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
