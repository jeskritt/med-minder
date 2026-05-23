import { createFileRoute, Link } from "@tanstack/react-router";
import { useCurrentUser } from "@/lib/auth";

export const Route = createFileRoute("/")({
  component: HomePage,
});

function HomePage() {
  const { data: user, isLoading: userLoading } = useCurrentUser();

  return (
    <main className="flex min-h-[calc(100vh-3.5rem)] flex-col items-center justify-center px-4">
      <div className="w-full max-w-sm text-center">
        <h1 className="text-4xl font-bold tracking-tight text-slate-900">
          MedMinder
        </h1>
        <p className="mt-3 text-lg text-slate-500">
          Stay on top of every dose.
        </p>

        {!userLoading && (
          <div className="mt-8 flex flex-col items-stretch gap-3">
            {user ? (
              <>
                <Link
                  to="/today"
                  className="rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 active:scale-[0.98]"
                >
                  Go to Today
                </Link>
                <Link
                  to="/medications"
                  className="rounded-xl border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
                >
                  My medications
                </Link>
              </>
            ) : (
              <Link
                to="/login"
                className="rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 active:scale-[0.98]"
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
