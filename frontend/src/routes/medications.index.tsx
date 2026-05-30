import { createFileRoute, Link, redirect } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Download, Plus, Printer } from "lucide-react";
import { client } from "@/lib/api";
import { MedicationList } from "@/components/medications/MedicationList";
import { downloadDoseHistoryCsv } from "@/lib/adherence";

const medicationsQueryKey = ["medications"] as const;

export const Route = createFileRoute("/medications/")({
  beforeLoad: async () => {
    const { response } = await client.GET("/me");
    if (response.status === 401) {
      throw redirect({ to: "/login" });
    }
  },
  component: MedicationsPage,
});

function MedicationsPage() {
  const queryClient = useQueryClient();
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const medsQuery = useQuery({
    queryKey: medicationsQueryKey,
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/medications");
      if (error) {
        throw new Error("Failed to load medications");
      }
      return data;
    },
    refetchOnWindowFocus: true,
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      setDeletingId(id);
      const { error, response } = await client.DELETE(
        "/api/v1/medications/{medication_id}",
        { params: { path: { medication_id: id } } },
      );
      if (error || (response.status !== 204 && response.status !== 404)) {
        throw new Error("Delete failed");
      }
    },
    onSettled: async () => {
      setDeletingId(null);
      await queryClient.invalidateQueries({ queryKey: medicationsQueryKey });
    },
  });

  const handleDelete = (id: string) => {
    if (
      typeof window !== "undefined" &&
      !window.confirm("Delete this medication?")
    ) {
      return;
    }
    deleteMutation.mutate(id);
  };

  const handlePrint = () => {
    if (typeof window !== "undefined") {
      window.print();
    }
  };

  const exportMutation = useMutation({
    mutationFn: downloadDoseHistoryCsv,
  });

  return (
    <main className="mx-auto max-w-2xl px-4 py-6">
      <div className="flex items-center justify-between print:hidden">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          Medications
        </h1>
        <div className="flex gap-2">
          <Link to="/medications/new" className="mm-btn mm-btn-primary">
            <Plus className="size-4" />
            Add
          </Link>
          <button
            type="button"
            onClick={handlePrint}
            className="mm-btn mm-btn-secondary"
          >
            <Printer className="size-4" />
            Print
          </button>
          <button
            type="button"
            onClick={() => exportMutation.mutate()}
            disabled={exportMutation.isPending}
            className="mm-btn mm-btn-secondary"
          >
            <Download className="size-4" />
            {exportMutation.isPending ? "Exporting…" : "Export"}
          </button>
        </div>
      </div>
      {exportMutation.isError && (
        <p role="alert" className="mt-2 text-sm text-destructive print:hidden">
          Could not export your dose history. Please try again.
        </p>
      )}

      <h1 className="hidden text-2xl font-bold print:block">Medications</h1>

      {medsQuery.isLoading && (
        <p className="mt-4 text-muted-foreground">Loading…</p>
      )}
      {medsQuery.isError && (
        <p role="alert" className="mt-4 text-destructive">
          Could not load medications.
        </p>
      )}
      {medsQuery.data && (
        <MedicationList
          items={medsQuery.data.items}
          onDelete={handleDelete}
          deletingId={deletingId}
        />
      )}
    </main>
  );
}
