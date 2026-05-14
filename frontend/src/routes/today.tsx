import { createFileRoute, redirect } from "@tanstack/react-router";
import { client } from "@/lib/api";
import { useToday } from "@/hooks/useToday";
import { TakenToggle } from "@/components/TakenToggle";
import { CountUpDisplay } from "@/components/timers/CountUpDisplay";
import { CountDownButton } from "@/components/timers/CountDownButton";

export const Route = createFileRoute("/today")({
  beforeLoad: async () => {
    const { response } = await client.GET("/me");
    if (response.status === 401) {
      throw redirect({ to: "/login" });
    }
  },
  component: TodayPage,
});

function formatTakenAt(taken_at: string): string {
  const dt = new Date(taken_at);
  const t = dt.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
  return `Taken ${t}`;
}

function TodayPage() {
  const today = useToday();

  return (
    <main className="mx-auto max-w-2xl p-6">
      <h1 className="text-2xl font-bold">Today</h1>

      {today.isLoading && (
        <p className="mt-4 text-gray-600">Loading today's schedule…</p>
      )}

      {today.isError && (
        <p className="mt-4 text-red-600">Could not load today.</p>
      )}

      {today.isSuccess && today.data.items.length === 0 && (
        <p className="mt-4 text-gray-600">Nothing scheduled for today.</p>
      )}

      {today.isSuccess && today.data.items.length > 0 && (
        <ul className="mt-4 divide-y rounded border bg-white">
          {today.data.items.map((item) => {
            const taken = item.dose !== null;
            return (
              <li
                key={`${item.schedule_id}-${item.medication_id}`}
                className={
                  "flex items-center justify-between gap-3 px-4 py-3 " +
                  (taken ? "bg-gray-50 text-gray-500" : "")
                }
              >
                <div>
                  <p className="font-medium">
                    {item.name}
                    {item.dose !== null && (
                      <span className="ml-2 text-sm font-normal text-gray-500">
                        {formatTakenAt(item.dose.taken_at)}
                      </span>
                    )}
                  </p>
                  <p className="text-sm">
                    {item.scheduled_time.slice(0, 5)} · {item.quantity_per_dose}{" "}
                    {item.unit}
                  </p>
                  {item.timer_state?.mode === "count_up" && (
                    <p className="text-sm text-gray-600">
                      <CountUpDisplay state={item.timer_state} />
                    </p>
                  )}
                </div>
                {item.timer_state?.mode === "count_down" ? (
                  <CountDownButton
                    state={item.timer_state}
                    medicationId={item.medication_id}
                    scheduleId={item.schedule_id}
                  />
                ) : (
                  <TakenToggle
                    scheduleId={item.schedule_id}
                    medicationId={item.medication_id}
                    dose={item.dose}
                  />
                )}
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
