import {
  createFileRoute,
  redirect,
  useNavigate,
  Link,
} from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { client } from "@/lib/api";
import { MedicationForm } from "@/components/medications/MedicationForm";
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

  const createMutation = useMutation({
    mutationFn: async (body: MedicationBody) => {
      const { data, error, response } = await client.POST(
        "/api/v1/medications",
        { body },
      );
      if (error || !data) {
        throw new Error(
          response.status === 422
            ? "Some fields are invalid. Please review and retry."
            : "Failed to create medication.",
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
        <h1 className="text-2xl font-bold">Add medication</h1>
        <Link to="/medications" className="text-sm text-blue-600 underline">
          ← Back to list
        </Link>
      </div>

      <MedicationForm
        mode="create"
        onSubmit={(body) => createMutation.mutateAsync(body)}
        serverError={serverError}
        isSubmitting={createMutation.isPending}
      />
    </main>
  );
}
