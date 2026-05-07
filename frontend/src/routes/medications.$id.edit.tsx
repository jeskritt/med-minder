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
  defaultsFromMedication,
} from "@/components/medications/MedicationForm";
import type { components } from "@/api/v1";

type MedicationBody = components["schemas"]["MedicationBody"];
type MedicationOut = components["schemas"]["MedicationOut"];

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

  const medQuery = useQuery({
    queryKey: ["medications", id],
    queryFn: async (): Promise<MedicationOut> => {
      const { data, error } = await client.GET("/api/v1/medications");
      if (error || !data) throw new Error("Failed to load medication");
      const found = data.items.find((m) => m.id === id);
      if (!found) throw new Error("Medication not found");
      return found;
    },
  });

  const updateMutation = useMutation({
    mutationFn: async (body: MedicationBody) => {
      const { data, error, response } = await client.PUT(
        "/api/v1/medications/{medication_id}",
        { params: { path: { medication_id: id } }, body },
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
    },
    onSuccess: async () => {
      setServerError(null);
      await queryClient.invalidateQueries({ queryKey: ["medications"] });
      void navigate({ to: "/medications" });
    },
    onError: (err: Error) => setServerError(err.message),
  });

  return (
    <main className="mx-auto max-w-2xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Edit medication</h1>
        <Link to="/medications" className="text-sm text-blue-600 underline">
          ← Back to list
        </Link>
      </div>

      {medQuery.isLoading && <p className="text-gray-600">Loading…</p>}
      {medQuery.isError && (
        <p role="alert" className="text-red-600">
          {medQuery.error instanceof Error
            ? medQuery.error.message
            : "Could not load medication."}
        </p>
      )}
      {medQuery.data && (
        <MedicationForm
          mode="edit"
          defaultValues={defaultsFromMedication(medQuery.data)}
          onSubmit={(body) => updateMutation.mutateAsync(body)}
          serverError={serverError}
          isSubmitting={updateMutation.isPending}
        />
      )}
    </main>
  );
}
