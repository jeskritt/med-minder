import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router";
import { client } from "@/lib/api";
import { useLogout } from "@/lib/auth";

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

  const handleLogout = async () => {
    await logout.mutateAsync();
    navigate({ to: "/login" });
  };

  return (
    <main className="mx-auto max-w-2xl p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Medications</h1>
        <button
          onClick={handleLogout}
          disabled={logout.isPending}
          className="rounded bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
        >
          {logout.isPending ? "Logging out..." : "Logout"}
        </button>
      </div>
      <p className="mt-4 text-gray-600">
        Phase 3 will populate this list with real data.
      </p>
    </main>
  );
}
