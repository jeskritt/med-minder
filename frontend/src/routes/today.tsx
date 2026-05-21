import { createFileRoute, Link, redirect } from "@tanstack/react-router";
import { useCallback, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { client } from "@/lib/api";
import { useToday, type TodayItem } from "@/hooks/useToday";
import { useTakeDose } from "@/hooks/useTakeDose";
import { TakenToggle } from "@/components/TakenToggle";
import { InteractionIndicator } from "@/components/InteractionIndicator";
import { CountUpDisplay } from "@/components/timers/CountUpDisplay";
import { CountDownButton } from "@/components/timers/CountDownButton";
import { MultiSubDoseCard } from "@/components/timers/MultiSubDoseCard";
import { DoseProgressBar } from "@/components/today/DoseProgressBar";
import { OutOfScheduleConfirmModal } from "@/components/today/OutOfScheduleConfirmModal";

export const Route = createFileRoute("/today")({
  beforeLoad: async () => {
    const { response } = await client.GET("/me");
    if (response.status === 401) {
      throw redirect({ to: "/login" });
    }
  },
  component: TodayPage,
});

const OUT_OF_SCHEDULE_HORIZON_MS = 2 * 60 * 60 * 1000; // ±2h

function parseHHMM(t: string): { h: number; m: number } {
  const [hh, mm] = t.split(":");
  return { h: Number(hh), m: Number(mm) };
}

function dayBandFor(timeOfDay: string): string {
  const { h } = parseHHMM(timeOfDay);
  if (h >= 5 && h < 11) return "Morning";
  if (h >= 11 && h < 14) return "Midday";
  if (h >= 14 && h < 18) return "Afternoon";
  if (h >= 18 && h < 22) return "Evening";
  return "Night";
}

function formatTime12h(timeOfDay: string): string {
  const { h, m } = parseHHMM(timeOfDay);
  const d = new Date();
  d.setHours(h, m, 0, 0);
  return d.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatTakenAt(taken_at: string): string {
  const dt = new Date(taken_at);
  const t = dt.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
  return `Taken ${t}`;
}

function isOutOfSchedule(item: TodayItem, now: number): boolean {
  if (!item.scheduled_today) return true;
  const ref = new Date(now);
  const { h, m } = parseHHMM(item.scheduled_time);
  ref.setHours(h, m, 0, 0);
  return Math.abs(now - ref.getTime()) > OUT_OF_SCHEDULE_HORIZON_MS;
}

interface GroupedItems {
  schedule_id: string;
  scheduled_time: string;
  schedule_label: string;
  items: TodayItem[];
}

function groupByScheduleId(items: TodayItem[]): GroupedItems[] {
  const map = new Map<string, GroupedItems>();
  for (const item of items) {
    const existing = map.get(item.schedule_id);
    if (existing) {
      existing.items.push(item);
    } else {
      map.set(item.schedule_id, {
        schedule_id: item.schedule_id,
        scheduled_time: item.scheduled_time,
        schedule_label: item.schedule_label,
        items: [item],
      });
    }
  }
  // Preserve the server's HH:MM ordering — the today_view query already
  // orders by Schedule.time_of_day, Medication.name; the dict above is
  // insertion-ordered in JS so groups inherit that order.
  return Array.from(map.values());
}

function canTakeNow(item: TodayItem): { ok: boolean; reason?: string } {
  if (item.dose !== null) {
    return { ok: false, reason: "already taken" };
  }
  if (item.interaction_state) {
    return { ok: false, reason: "drug-interaction conflict" };
  }
  const cd = item.timer_state?.count_down;
  if (cd && cd.remaining_seconds > 0) {
    return { ok: false, reason: "min-interval not elapsed" };
  }
  const msd = item.timer_state?.multi_sub_dose;
  if (msd?.active_window && msd.active_window.slots_remaining === 0) {
    return { ok: false, reason: "window full" };
  }
  return { ok: true };
}

function useDeleteMedication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (medicationId: string) => {
      const { error } = await client.DELETE(
        "/api/v1/medications/{medication_id}",
        { params: { path: { medication_id: medicationId } } },
      );
      if (error) throw new Error("Failed to delete medication");
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["today", null] });
      await queryClient.invalidateQueries({ queryKey: ["medications"] });
    },
  });
}

function TodayPage() {
  const today = useToday();
  const take = useTakeDose();
  const deleteMed = useDeleteMedication();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const confirmResolveRef = useRef<((v: boolean) => void) | null>(null);
  const [takeAllReport, setTakeAllReport] = useState<{
    taken: number;
    skipped: { name: string; reason: string }[];
  } | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const groups = useMemo(
    () => (today.data ? groupByScheduleId(today.data.items) : []),
    [today.data],
  );

  const requestConfirm = useCallback(() => {
    setConfirmOpen(true);
    return new Promise<boolean>((resolve) => {
      confirmResolveRef.current = resolve;
    });
  }, []);

  const resolveConfirm = useCallback((value: boolean) => {
    confirmResolveRef.current?.(value);
    confirmResolveRef.current = null;
    setConfirmOpen(false);
  }, []);

  const onBeforeTakeFor = useCallback(
    (item: TodayItem) => async () => {
      if (!isOutOfSchedule(item, Date.now())) return true;
      return await requestConfirm();
    },
    [requestConfirm],
  );

  const handleTakeAll = useCallback(
    async (group: GroupedItems) => {
      const now = Date.now();
      const taken: string[] = [];
      const skipped: { name: string; reason: string }[] = [];
      for (const item of group.items) {
        const check = canTakeNow(item);
        if (!check.ok) {
          skipped.push({ name: item.name, reason: check.reason ?? "skipped" });
          continue;
        }
        if (isOutOfSchedule(item, now)) {
          skipped.push({ name: item.name, reason: "out of schedule" });
          continue;
        }
        try {
          await take.mutateAsync({
            medicationId: item.medication_id,
            scheduleId: item.schedule_id,
          });
          taken.push(item.name);
        } catch (e) {
          skipped.push({
            name: item.name,
            reason: e instanceof Error ? e.message : "failed",
          });
        }
      }
      setTakeAllReport({ taken: taken.length, skipped });
    },
    [take],
  );

  const handleDelete = (id: string, name: string) => {
    if (
      !window.confirm(
        `Delete ${name}? Its history is kept but it stops appearing in lists.`,
      )
    ) {
      return;
    }
    setDeletingId(id);
    deleteMed.mutate(id, {
      onSettled: () => setDeletingId(null),
    });
  };

  return (
    <main className="mx-auto max-w-2xl p-6">
      <h1 className="text-2xl font-bold">Today</h1>

      {today.isLoading && (
        <p className="mt-4 text-gray-600">Loading today's schedule…</p>
      )}

      {today.isError && (
        <p className="mt-4 text-red-600">Could not load today.</p>
      )}

      {today.isSuccess && groups.length === 0 && (
        <p className="mt-4 text-gray-600">Nothing scheduled for today.</p>
      )}

      {takeAllReport && (
        <div
          role="status"
          className="mt-4 rounded border border-blue-200 bg-blue-50 p-3 text-sm"
        >
          <p>
            Marked {takeAllReport.taken} taken
            {takeAllReport.skipped.length > 0
              ? ` · skipped ${takeAllReport.skipped.length}`
              : ""}
            .
          </p>
          {takeAllReport.skipped.length > 0 && (
            <ul className="ml-4 mt-1 list-disc text-xs text-gray-700">
              {takeAllReport.skipped.map((s, i) => (
                <li key={i}>
                  <strong>{s.name}</strong>: {s.reason}
                </li>
              ))}
            </ul>
          )}
          <button
            type="button"
            onClick={() => setTakeAllReport(null)}
            className="mt-2 text-xs text-blue-700 underline"
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="mt-4 space-y-4">
        {groups.map((group) => {
          const headerTitle =
            group.schedule_label.trim() === ""
              ? `${dayBandFor(group.scheduled_time)} meds`
              : group.schedule_label;
          const headerTime = formatTime12h(group.scheduled_time);
          return (
            <section
              key={group.schedule_id}
              data-testid={`today-group-${group.schedule_id}`}
              className="rounded border bg-white"
            >
              <header className="flex items-center justify-between gap-3 border-b px-4 py-3">
                <div>
                  <p className="font-medium">{headerTitle}</p>
                  <p className="text-xs text-gray-500">{headerTime}</p>
                </div>
                <button
                  type="button"
                  data-testid={`take-all-${group.schedule_id}`}
                  onClick={() => {
                    void handleTakeAll(group);
                  }}
                  disabled={take.isPending}
                  className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
                >
                  Take all
                </button>
              </header>

              <ul className="divide-y">
                {group.items.map((item) => {
                  const muted = !item.scheduled_today;
                  const before = onBeforeTakeFor(item);
                  return (
                    <li
                      key={`${item.schedule_id}-${item.medication_id}`}
                      data-testid={`today-row-${item.medication_id}`}
                      className={
                        "px-4 py-3 " +
                        (muted ? "italic opacity-70 " : "") +
                        (item.dose !== null ? "bg-gray-50 text-gray-500" : "")
                      }
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="font-medium">
                            {item.timer_state?.mode === "multi_sub_dose" ? (
                              <Link
                                to="/medications/$medicationId"
                                params={{ medicationId: item.medication_id }}
                                className="text-blue-600 underline"
                              >
                                {item.name}
                              </Link>
                            ) : (
                              item.name
                            )}{" "}
                            <span className="text-sm font-normal text-gray-600">
                              ({item.quantity_per_dose} {item.unit})
                            </span>
                          </p>
                          {muted && (
                            <p className="text-xs text-gray-500">
                              not normally scheduled today
                            </p>
                          )}
                          {item.dose !== null && (
                            <p className="text-xs text-gray-500">
                              {formatTakenAt(item.dose.taken_at)}
                            </p>
                          )}
                        </div>
                        <div className="flex shrink-0 gap-2">
                          <Link
                            to="/medications/$id/edit"
                            params={{ id: item.medication_id }}
                            className="rounded border px-2 py-1 text-xs hover:bg-gray-50"
                          >
                            Edit
                          </Link>
                          <button
                            type="button"
                            onClick={() =>
                              handleDelete(item.medication_id, item.name)
                            }
                            disabled={deletingId === item.medication_id}
                            className="rounded bg-red-600 px-2 py-1 text-xs text-white hover:bg-red-700 disabled:opacity-50"
                          >
                            {deletingId === item.medication_id
                              ? "Deleting…"
                              : "Delete"}
                          </button>
                        </div>
                      </div>

                      <div className="mt-2">
                        <DoseProgressBar item={item} />
                      </div>

                      <div className="mt-2 flex items-center justify-between gap-3">
                        <div className="min-w-0 flex-1 space-y-1">
                          {item.timer_state?.mode === "count_up" && (
                            <p className="text-xs text-gray-600">
                              <CountUpDisplay state={item.timer_state} />
                            </p>
                          )}
                          {item.interaction_state && (
                            <InteractionIndicator
                              state={item.interaction_state}
                            />
                          )}
                        </div>
                        <div className="shrink-0">
                          {item.timer_state?.mode === "count_down" ? (
                            <CountDownButton
                              state={item.timer_state}
                              medicationId={item.medication_id}
                              scheduleId={item.schedule_id}
                              onBeforeTake={before}
                            />
                          ) : item.timer_state?.mode === "multi_sub_dose" ? (
                            <MultiSubDoseCard
                              state={item.timer_state}
                              medicationId={item.medication_id}
                              scheduleId={item.schedule_id}
                              onBeforeTake={before}
                            />
                          ) : (
                            <TakenToggle
                              scheduleId={item.schedule_id}
                              medicationId={item.medication_id}
                              dose={item.dose}
                              onBeforeTake={before}
                            />
                          )}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })}
      </div>

      <OutOfScheduleConfirmModal
        open={confirmOpen}
        onConfirm={() => resolveConfirm(true)}
        onCancel={() => resolveConfirm(false)}
      />
    </main>
  );
}
