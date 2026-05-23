import {
  createFileRoute,
  redirect,
  useNavigate,
  Link,
} from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { client } from "@/lib/api";
import {
  MedicationForm,
  type ConflictInput,
} from "@/components/medications/MedicationForm";
import { createInteractionRule } from "@/hooks/useMedicationInteractions";
import type { components } from "@/api/v1";

type MedicationBody = components["schemas"]["MedicationBody"];

export const Route = createFileRoute("/medications/new")({
  beforeLoad: async () => {
    const { response } = await client.GET("/me");
    if (response.status === 401) {
      throw redirect({ to: "/login" });
    }
  },
  component: NewMedicationPage,
});

function NewMedicationPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);

  // Same query key + shape as the medications list page
  // (`medications.index.tsx`) — returning `data` (not `data.items`)
  // keeps the shared ["medications"] cache entry one consistent shape.
  const medsQuery = useQuery({
    queryKey: ["medications"],
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/medications");
      if (error || !data) throw new Error("Failed to load medications");
      return data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (input: {
      body: MedicationBody;
      conflicts: ConflictInput[];
    }) => {
      const { data, error, response } = await client.POST(
        "/api/v1/medications",
        { body: input.body },
      );
      if (error || !data) {
        throw new Error(
          response.status === 422
            ? "Some fields are invalid. Please review and retry."
            : "Failed to create medication.",
        );
      }
      // Sequence the rule POSTs with the new medication's id. A rule
      // failure does not roll back the saved medication (US3 / D6).
      const failed: string[] = [];
      for (const c of input.conflicts) {
        try {
          await createInteractionRule(data.id, c);
        } catch (e) {
          failed.push(e instanceof Error ? e.message : "unknown error");
        }
      }
      return { id: data.id, failed };
    },
    onSuccess: async ({ id, failed }) => {
      await queryClient.invalidateQueries({ queryKey: ["medications"] });
      if (failed.length > 0) {
        setServerError(
          `Medication saved, but some interactions failed: ${failed.join(
            "; ",
          )}. Retry them from the edit page.`,
        );
        void navigate({ to: "/medications/$id/edit", params: { id } });
        return;
      }
      setServerError(null);
      void navigate({ to: "/medications" });
    },
    onError: (err: Error) => setServerError(err.message),
  });

  return (
    <main className="mx-auto max-w-2xl px-4 py-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Add medication
        </h1>
        <Link
          to="/medications"
          className="text-sm text-blue-600 hover:underline"
        >
          ← Back
        </Link>
      </div>

      <MedicationForm
        mode="create"
        availableMedications={(medsQuery.data?.items ?? []).map((m) => ({
          id: m.id,
          name: m.name,
        }))}
        onSubmit={async (body, conflicts) => {
          await createMutation.mutateAsync({ body, conflicts });
        }}
        serverError={serverError}
        isSubmitting={createMutation.isPending}
      />
    </main>
  );
}
