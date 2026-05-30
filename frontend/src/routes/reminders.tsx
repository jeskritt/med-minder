import { createFileRoute, redirect } from "@tanstack/react-router";
import { client } from "@/lib/api";
import { EnableNotifications } from "@/components/reminders/EnableNotifications";
import { QuietHoursSection } from "@/components/reminders/QuietHoursSection";
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
      <h1 className="mb-5 text-3xl font-bold tracking-tight text-foreground">
        Reminders
      </h1>
      <div className="mm-card mb-4 p-4">
        <EnableNotifications />
      </div>
      <div className="mm-card mb-6 p-4">
        <QuietHoursSection />
      </div>
      <h2 className="mb-2 text-sm font-semibold tracking-wide text-muted-foreground uppercase">
        Upcoming
      </h2>
      <ReminderList />
    </div>
  );
}
