import { createFileRoute, Link, redirect } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { client } from "@/lib/api";
import { MedicationList } from "@/components/medications/MedicationList";

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

  return (
    <main className="mx-auto max-w-2xl px-4 py-6">
      <div className="flex items-center justify-between print:hidden">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Medications
        </h1>
        <div className="flex gap-2">
          <Link
            to="/medications/new"
            className="rounded-xl bg-blue-600 px-3.5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 active:scale-95"
          >
            Add
          </Link>
          <button
            type="button"
            onClick={handlePrint}
            className="rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            Print
          </button>
        </div>
      </div>

      <h1 className="hidden text-2xl font-bold print:block">Medications</h1>

      {medsQuery.isLoading && <p className="mt-4 text-slate-500">Loading…</p>}
      {medsQuery.isError && (
        <p role="alert" className="mt-4 text-red-600">
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
