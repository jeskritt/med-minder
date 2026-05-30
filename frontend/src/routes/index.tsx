import { createFileRoute, Link } from "@tanstack/react-router";
import { Pill } from "lucide-react";
import { useCurrentUser } from "@/lib/auth";

export const Route = createFileRoute("/")({
  component: HomePage,
});

function HomePage() {
  const { data: user, isLoading: userLoading } = useCurrentUser();

  return (
    <main className="flex min-h-[calc(100vh-3.5rem)] flex-col items-center justify-center px-4">
      <div className="w-full max-w-sm text-center">
        <span className="mx-auto mb-5 flex size-14 items-center justify-center rounded-3xl bg-primary text-primary-foreground shadow-md">
          <Pill className="size-7" />
        </span>
        <h1 className="text-4xl font-bold tracking-tight text-foreground">
          MedMinder
        </h1>
        <p className="mt-3 text-lg text-muted-foreground">
          Stay on top of every dose.
        </p>

        {!userLoading && (
          <div className="mt-8 flex flex-col items-stretch gap-3">
            {user ? (
              <>
                <Link
                  to="/today"
                  className="mm-btn mm-btn-primary mm-btn-touch"
                >
                  Go to Today
                </Link>
                <Link
                  to="/medications"
                  className="mm-btn mm-btn-secondary mm-btn-touch"
                >
                  My medications
                </Link>
              </>
            ) : (
              <Link to="/login" className="mm-btn mm-btn-primary mm-btn-touch">
                Sign in
              </Link>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
