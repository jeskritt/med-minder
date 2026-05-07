import {
  createFileRoute,
  Link,
  redirect,
  useNavigate,
} from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { client } from "@/lib/api";
import { useLogout } from "@/lib/auth";
import { MedicationList } from "@/components/medications/MedicationList";

const medicationsQueryKey = ["medications"] as const;

export const Route = createFileRoute("/medications")({
  beforeLoad: async () => {
    const { response } = await client.GET("/me");
    if (response.status === 401) {
      throw redirect({ to: "/login" });
    }
  },
  component: MedicationsPage,
});

function MedicationsPage() {
  const navigate = useNavigate();
  const logout = useLogout();
  const queryClient = useQueryClient();
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleLogout = async () => {
    await logout.mutateAsync();
    navigate({ to: "/login" });
  };

  const medsQuery = useQuery({
    queryKey: medicationsQueryKey,
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/medications");
      if (error) {
        throw new Error("Failed to load medications");
      }
      return data;
    },
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
    <main className="mx-auto max-w-2xl p-6">
      <div className="flex items-center justify-between print:hidden">
        <h1 className="text-2xl font-bold">Medications</h1>
        <div className="flex gap-2">
          <Link
            to="/medications/new"
            className="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Add medication
          </Link>
          <button
            type="button"
            onClick={handlePrint}
            className="rounded border px-3 py-2 text-sm font-medium hover:bg-gray-50"
          >
            Print
          </button>
          <button
            onClick={handleLogout}
            disabled={logout.isPending}
            className="rounded bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
          >
            {logout.isPending ? "Logging out..." : "Logout"}
          </button>
        </div>
      </div>

      <h1 className="hidden text-2xl font-bold print:block">Medications</h1>

      {medsQuery.isLoading && <p className="mt-4 text-gray-600">Loading…</p>}
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
