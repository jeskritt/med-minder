import { createFileRoute, Link, redirect } from "@tanstack/react-router";
import { useCallback, useMemo, useRef, useState } from "react";
import { Check, Pencil, Trash2 } from "lucide-react";
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
import { formatQuantity } from "@/lib/format";

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
  // Unscheduled (PRN) timer rows have no slot — taking them is never
  // "out of schedule", so the confirm modal never intercepts them.
  if (item.schedule_id === null || item.scheduled_time === null) return false;
  if (!item.scheduled_today) return true;
  const ref = new Date(now);
  const { h, m } = parseHHMM(item.scheduled_time);
  ref.setHours(h, m, 0, 0);
  return Math.abs(now - ref.getTime()) > OUT_OF_SCHEDULE_HORIZON_MS;
}

// Synthetic group key for unscheduled (PRN) timer rows, which share a
// single "As needed" group instead of a per-schedule one.
const PRN_GROUP_KEY = "__prn__";

interface GroupedItems {
  schedule_id: string | null;
  scheduled_time: string | null;
  schedule_label: string;
  items: TodayItem[];
}

function groupByScheduleId(items: TodayItem[]): GroupedItems[] {
  const map = new Map<string, GroupedItems>();
  for (const item of items) {
    const key = item.schedule_id ?? PRN_GROUP_KEY;
    const existing = map.get(key);
    if (existing) {
      existing.items.push(item);
    } else {
      map.set(key, {
        schedule_id: item.schedule_id,
        scheduled_time: item.scheduled_time,
        schedule_label: item.schedule_label,
        items: [item],
      });
    }
  }
  // Preserve the server's ordering — today_view orders scheduled slots
  // by Schedule.time_of_day, Medication.name and the endpoint appends
  // PRN rows last; the Map is insertion-ordered so the "As needed"
  // group lands after the time-ordered groups.
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
  if (msd && msd.slots_remaining === 0) {
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
      const takeable = group.items.filter((i) => canTakeNow(i).ok);
      // If any takeable item is out of schedule, confirm once for the
      // whole group (mirrors the per-row "Mark taken" gate). Cancel
      // aborts the entire Take-all — nothing is marked.
      if (takeable.some((i) => isOutOfSchedule(i, now))) {
        const proceed = await requestConfirm();
        if (!proceed) return;
      }
      const taken: string[] = [];
      const skipped: { name: string; reason: string }[] = [];
      for (const item of group.items) {
        const check = canTakeNow(item);
        if (!check.ok) {
          skipped.push({ name: item.name, reason: check.reason ?? "skipped" });
          continue;
        }
        // Out-of-schedule items are now included — the confirm above
        // covered them. Drug-interaction / hard-block items were
        // already filtered out by canTakeNow (no bulk override).
        try {
          await take.mutateAsync({
            medicationId: item.medication_id,
            scheduleId: item.schedule_id ?? undefined,
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
    [take, requestConfirm],
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
    <main className="mx-auto max-w-2xl px-4 py-6">
      <h1 className="text-3xl font-bold tracking-tight text-foreground">
        Today
      </h1>
      <p className="mt-1 text-sm text-muted-foreground">
        {new Date().toLocaleDateString(undefined, {
          weekday: "long",
          month: "long",
          day: "numeric",
        })}
      </p>

      {today.isLoading && (
        <p className="mt-6 text-muted-foreground">Loading today's schedule…</p>
      )}

      {today.isError && (
        <p className="mt-6 text-destructive">Could not load today.</p>
      )}

      {today.isSuccess && groups.length === 0 && (
        <div className="mm-card mt-6 px-6 py-10 text-center">
          <p className="font-medium text-foreground">All clear</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Nothing scheduled for today.
          </p>
        </div>
      )}

      {takeAllReport && (
        <div
          role="status"
          className="mt-4 rounded-xl border border-accent bg-accent/50 p-3 text-sm text-foreground"
        >
          <p className="font-medium">
            Marked {takeAllReport.taken} taken
            {takeAllReport.skipped.length > 0
              ? ` · skipped ${takeAllReport.skipped.length}`
              : ""}
            .
          </p>
          {takeAllReport.skipped.length > 0 && (
            <ul className="mt-1 ml-4 list-disc text-xs text-muted-foreground">
              {takeAllReport.skipped.map((s, i) => (
                <li key={i}>
                  <strong className="font-medium text-foreground">
                    {s.name}
                  </strong>
                  : {s.reason}
                </li>
              ))}
            </ul>
          )}
          <button
            type="button"
            onClick={() => setTakeAllReport(null)}
            className="mt-2 text-xs font-medium text-primary hover:underline"
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="mt-4 space-y-4">
        {groups.map((group) => {
          const isPrn = group.schedule_id === null;
          const groupKey = group.schedule_id ?? PRN_GROUP_KEY;
          const headerTitle =
            group.schedule_label.trim() !== ""
              ? group.schedule_label
              : group.scheduled_time !== null
                ? `${dayBandFor(group.scheduled_time)} meds`
                : "As needed";
          const headerTime =
            group.scheduled_time !== null
              ? formatTime12h(group.scheduled_time)
              : null;
          return (
            <section
              key={groupKey}
              data-testid={`today-group-${groupKey}`}
              className="mm-card overflow-hidden"
            >
              <header className="flex items-center justify-between gap-3 border-b border-border/70 bg-muted/40 px-4 py-3">
                <div>
                  <p className="font-semibold text-foreground">{headerTitle}</p>
                  {headerTime && (
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      {headerTime}
                    </p>
                  )}
                </div>
                {!isPrn && (
                  <button
                    type="button"
                    data-testid={`take-all-${groupKey}`}
                    onClick={() => {
                      void handleTakeAll(group);
                    }}
                    disabled={take.isPending}
                    className="mm-btn mm-btn-secondary"
                  >
                    <Check className="size-4" />
                    Take all
                  </button>
                )}
              </header>

              <ul className="divide-y divide-border/70">
                {group.items.map((item) => {
                  // PRN rows have no day-of-week concept — never mute them.
                  const muted =
                    item.schedule_id !== null && !item.scheduled_today;
                  const before = onBeforeTakeFor(item);
                  return (
                    <li
                      key={`${item.schedule_id}-${item.medication_id}`}
                      data-testid={`today-row-${item.medication_id}`}
                      className={
                        "px-4 py-3.5 transition-colors " +
                        (muted ? "italic opacity-70 " : "") +
                        (item.dose !== null ? "bg-success/[0.06]" : "")
                      }
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate font-semibold text-foreground">
                            {item.timer_state?.mode === "multi_sub_dose" ? (
                              <Link
                                to="/medications/$medicationId"
                                params={{ medicationId: item.medication_id }}
                                className="text-primary underline decoration-primary/30 underline-offset-2 hover:decoration-primary"
                              >
                                {item.name}
                              </Link>
                            ) : (
                              item.name
                            )}{" "}
                            <span className="text-sm font-normal text-muted-foreground">
                              {formatQuantity(item.quantity_per_dose)}{" "}
                              {item.unit}
                            </span>
                          </p>
                          {muted && (
                            <p className="text-xs text-muted-foreground">
                              not normally scheduled today
                            </p>
                          )}
                          {item.dose !== null && (
                            <p className="mt-0.5 inline-flex items-center gap-1 text-xs font-medium text-success">
                              <Check className="size-3.5" />
                              {formatTakenAt(item.dose.taken_at)}
                            </p>
                          )}
                        </div>
                        <div className="shrink-0">
                          {item.timer_state?.mode === "count_down" ? (
                            <CountDownButton
                              state={item.timer_state}
                              medicationId={item.medication_id}
                              scheduleId={item.schedule_id ?? undefined}
                              onBeforeTake={before}
                            />
                          ) : item.timer_state?.mode === "multi_sub_dose" ? (
                            <MultiSubDoseCard
                              state={item.timer_state}
                              medicationId={item.medication_id}
                              scheduleId={item.schedule_id ?? undefined}
                              onBeforeTake={before}
                            />
                          ) : (
                            <TakenToggle
                              scheduleId={item.schedule_id ?? undefined}
                              medicationId={item.medication_id}
                              dose={item.dose}
                              onBeforeTake={before}
                            />
                          )}
                        </div>
                      </div>

                      <div className="mt-2.5">
                        <DoseProgressBar item={item} />
                      </div>

                      <div className="mt-2 flex items-center justify-between gap-3">
                        <div className="min-w-0 flex-1 space-y-1">
                          {item.timer_state?.mode === "count_up" && (
                            <p className="text-xs text-muted-foreground">
                              <CountUpDisplay state={item.timer_state} />
                            </p>
                          )}
                          {item.interaction_state && (
                            <InteractionIndicator
                              state={item.interaction_state}
                            />
                          )}
                        </div>
                        <div className="flex shrink-0 items-center gap-1">
                          <Link
                            to="/medications/$id/edit"
                            params={{ id: item.medication_id }}
                            aria-label={`Edit ${item.name}`}
                            className="mm-btn mm-btn-ghost size-8 p-0"
                          >
                            <Pencil className="size-4" />
                          </Link>
                          <button
                            type="button"
                            onClick={() =>
                              handleDelete(item.medication_id, item.name)
                            }
                            disabled={deletingId === item.medication_id}
                            aria-label={`Delete ${item.name}`}
                            className="mm-btn mm-btn-ghost size-8 p-0 hover:bg-destructive/10 hover:text-destructive"
                          >
                            <Trash2 className="size-4" />
                          </button>
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
