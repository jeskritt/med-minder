import { createFileRoute, redirect } from "@tanstack/react-router";
import { client } from "@/lib/api";
import { EnableNotifications } from "@/components/reminders/EnableNotifications";
import { ReminderList } from "@/components/reminders/ReminderList";

export const Route = createFileRoute("/reminders")({
  beforeLoad: async () => {
    const { response } = await client.GET("/me");
    if (response.status === 401) {
      throw redirect({ to: "/login" });
    }
  },
  component: RemindersPage,
});

function RemindersPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-6">
      <h1 className="mb-4 text-xl font-semibold text-gray-900">Reminders</h1>
      <div className="mb-6">
        <EnableNotifications />
      </div>
      <ReminderList />
    </div>
  );
}
