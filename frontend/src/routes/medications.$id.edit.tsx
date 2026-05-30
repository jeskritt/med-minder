import {
  createFileRoute,
  Link,
  redirect,
  useNavigate,
} from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { client } from "@/lib/api";
import {
  MedicationForm,
  type ConflictInput,
} from "@/components/medications/MedicationForm";
import { defaultsFromMedication } from "@/components/medications/medicationFormDefaults";
import {
  createInteractionRule,
  deleteInteractionRule,
  listInteractionRules,
  medicationRulesKey,
} from "@/hooks/useMedicationInteractions";
import type { components } from "@/api/v1";

type MedicationBody = components["schemas"]["MedicationBody"];

export const Route = createFileRoute("/medications/$id/edit")({
  beforeLoad: async () => {
    const { response } = await client.GET("/me");
    if (response.status === 401) {
      throw redirect({ to: "/login" });
    }
  },
  component: EditMedicationPage,
});

function EditMedicationPage() {
  const { id } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);

  // Same query key + shape as the medications list page — return
  // `data` (not `data.items`) so the shared ["medications"] cache
  // entry stays one consistent shape across all consumers.
  const medsQuery = useQuery({
    queryKey: ["medications"],
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/medications");
      if (error || !data) throw new Error("Failed to load medication");
      return data;
    },
  });

  const rulesQuery = useQuery({
    queryKey: medicationRulesKey(id),
    queryFn: () => listInteractionRules(id),
  });

  const med = medsQuery.data?.items.find((m) => m.id === id);

  const updateMutation = useMutation({
    mutationFn: async (input: {
      body: MedicationBody;
      conflicts: ConflictInput[];
    }) => {
      const { data, error, response } = await client.PUT(
        "/api/v1/medications/{medication_id}",
        { params: { path: { medication_id: id } }, body: input.body },
      );
      if (error || !data) {
        throw new Error(
          response.status === 422
            ? "Some fields are invalid. Please review and retry."
            : response.status === 404
              ? "Medication not found."
              : "Failed to update medication.",
        );
      }
      // No in-place rule edit (clarified scope): delete every existing
      // rule for this med, then recreate from the form.
      const existing = await listInteractionRules(id);
      const failed: string[] = [];
      for (const r of existing) {
        try {
          await deleteInteractionRule(id, r.id);
        } catch (e) {
          failed.push(e instanceof Error ? e.message : "delete failed");
        }
      }
      for (const c of input.conflicts) {
        try {
          await createInteractionRule(id, c);
        } catch (e) {
          failed.push(e instanceof Error ? e.message : "create failed");
        }
      }
      return { failed };
    },
    onSuccess: async ({ failed }) => {
      await queryClient.invalidateQueries({ queryKey: ["medications"] });
      await queryClient.invalidateQueries({
        queryKey: medicationRulesKey(id),
      });
      if (failed.length > 0) {
        setServerError(
          `Medication saved, but some interactions failed: ${failed.join(
            "; ",
          )}.`,
        );
        return;
      }
      setServerError(null);
      void navigate({ to: "/medications" });
    },
    onError: (err: Error) => setServerError(err.message),
  });

  const loading = medsQuery.isLoading || rulesQuery.isLoading;
  const errored = medsQuery.isError || rulesQuery.isError || !med;

  return (
    <main className="mx-auto max-w-2xl px-4 py-6">
      <div className="mb-5 flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          Edit medication
        </h1>
        <Link to="/medications" className="mm-btn mm-btn-ghost -mr-2">
          ← Back
        </Link>
      </div>

      {loading && <p className="text-muted-foreground">Loading…</p>}
      {!loading && errored && (
        <p role="alert" className="text-destructive">
          Could not load medication.
        </p>
      )}
      {!loading && med && rulesQuery.data && (
        <MedicationForm
          mode="edit"
          defaultValues={{
            ...defaultsFromMedication(med),
            conflicts: rulesQuery.data.map((r) => ({
              other_medication_id: r.conflicting_medication_id,
              cooldown_minutes: String(r.cooldown_minutes),
            })),
          }}
          availableMedications={(medsQuery.data?.items ?? [])
            .filter((m) => m.id !== id)
            .map((m) => ({ id: m.id, name: m.name }))}
          onSubmit={async (body, conflicts) => {
            await updateMutation.mutateAsync({ body, conflicts });
          }}
          serverError={serverError}
          isSubmitting={updateMutation.isPending}
        />
      )}
    </main>
  );
}
