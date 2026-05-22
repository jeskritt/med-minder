import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { fetchHealthz } from "@/lib/api";
import { useCurrentUser } from "@/lib/auth";

export const Route = createFileRoute("/")({
  component: HomePage,
});

function HomePage() {
  const healthQuery = useQuery({
    queryKey: ["healthz"],
    queryFn: fetchHealthz,
    retry: 1,
    refetchInterval: 30_000,
  });
  const { data: user, isLoading: userLoading } = useCurrentUser();

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight text-slate-900">
          MedMinder
        </h1>
        <p className="mt-3 text-lg text-slate-500">
          Personal medication tracker
        </p>

        <p className="mt-6">
          <Link
            to="/today"
            className="inline-block rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 active:scale-95"
          >
            Today
          </Link>
        </p>

        <div className="mt-8" id="health-status">
          {healthQuery.isLoading && (
            <span className="inline-flex items-center gap-2 rounded-full bg-gray-100 px-4 py-2 text-sm text-gray-500">
              <span className="h-2 w-2 animate-pulse rounded-full bg-gray-400" />
              Checking backend…
            </span>
          )}

          {healthQuery.isSuccess && (
            <span className="inline-flex items-center gap-2 rounded-full bg-green-50 px-4 py-2 text-sm font-medium text-green-700">
              <span className="h-2 w-2 rounded-full bg-green-500" />
              Backend: {healthQuery.data.status}
            </span>
          )}

          {healthQuery.isError && (
            <span className="inline-flex items-center gap-2 rounded-full bg-red-50 px-4 py-2 text-sm font-medium text-red-700">
              <span className="h-2 w-2 rounded-full bg-red-500" />
              Backend: error
            </span>
          )}
        </div>

        {!userLoading && (
          <div className="mt-8">
            {user ? (
              <Link
                to="/medications"
                className="rounded-xl border border-slate-200 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
              >
                Open my medications
              </Link>
            ) : (
              <Link
                to="/login"
                className="rounded-xl border border-slate-200 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
              >
                Sign in
              </Link>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
