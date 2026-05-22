import { createFileRoute, Link, redirect } from "@tanstack/react-router";
import { client } from "@/lib/api";
import { useMedicationDetail } from "@/hooks/useMedicationDetail";
import { CountUpDisplay } from "@/components/timers/CountUpDisplay";
import { CountDownButton } from "@/components/timers/CountDownButton";
import { MultiSubDoseCard } from "@/components/timers/MultiSubDoseCard";
import { formatQuantity } from "@/lib/format";

export const Route = createFileRoute("/medications/$medicationId")({
  beforeLoad: async () => {
    const { response } = await client.GET("/me");
    if (response.status === 401) {
      throw redirect({ to: "/login" });
    }
  },
  component: MedicationDetailPage,
});

function MedicationDetailPage() {
  const { medicationId } = Route.useParams();
  const detail = useMedicationDetail(medicationId);

  return (
    <main className="mx-auto max-w-2xl px-4 py-6">
      <Link to="/medications" className="text-sm text-blue-600 hover:underline">
        ← Medications
      </Link>

      {detail.isLoading && <p className="mt-4 text-slate-500">Loading…</p>}
      {detail.isError && (
        <p role="alert" className="mt-4 text-red-600">
          Could not load this medication.
        </p>
      )}

      {detail.isSuccess && (
        <article className="mt-4 space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <header>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              {detail.data.name}
            </h1>
            <p className="text-sm text-slate-500">
              {formatQuantity(detail.data.quantity_per_dose)} {detail.data.unit}{" "}
              ·{" "}
              {detail.data.timer_state?.mode === "multi_sub_dose"
                ? `max ${detail.data.times_per_day} at a time`
                : `${detail.data.times_per_day}× daily`}
            </p>
          </header>

          {detail.data.timer_state?.mode === "count_up" && (
            <p className="text-sm text-gray-700">
              <CountUpDisplay state={detail.data.timer_state} />
            </p>
          )}
          {detail.data.timer_state?.mode === "count_down" && (
            <CountDownButton
              state={detail.data.timer_state}
              medicationId={detail.data.id}
            />
          )}
          {detail.data.timer_state?.mode === "multi_sub_dose" && (
            <MultiSubDoseCard
              state={detail.data.timer_state}
              medicationId={detail.data.id}
            />
          )}
        </article>
      )}
    </main>
  );
}
