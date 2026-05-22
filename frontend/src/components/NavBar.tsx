import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { useCurrentUser, useLogout } from "@/lib/auth";

export function NavBar() {
  const { data: user, isLoading } = useCurrentUser();
  const logout = useLogout();
  const navigate = useNavigate();
  const path = useRouterState({ select: (s) => s.location.pathname });

  if (path === "/login") {
    return null;
  }

  const handleLogout = async () => {
    await logout.mutateAsync();
    void navigate({ to: "/" });
  };

  return (
    <nav
      className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white/80 px-5 py-3 backdrop-blur-md print:hidden"
      aria-label="Primary"
    >
      <div className="flex items-center gap-6">
        <Link to="/" className="text-lg font-semibold text-gray-900">
          MedMinder
        </Link>
        {user && (
          <ul className="flex items-center gap-4 text-sm">
            <li>
              <Link
                to="/today"
                className="text-slate-600 hover:text-blue-600"
                activeProps={{ className: "text-blue-600 font-semibold" }}
              >
                Today
              </Link>
            </li>
            <li>
              <Link
                to="/medications"
                className="text-slate-600 hover:text-blue-600"
                activeProps={{ className: "text-blue-600 font-semibold" }}
              >
                Medications
              </Link>
            </li>
            {/* Future tabs (Timers, etc.) drop in here. */}
          </ul>
        )}
      </div>

      <div className="flex items-center gap-3 text-sm">
        {isLoading ? null : user ? (
          <>
            <span className="text-gray-600">{user.name}</span>
            <button
              type="button"
              onClick={handleLogout}
              disabled={logout.isPending}
              className="rounded-lg border border-slate-200 px-3 py-1.5 font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
            >
              {logout.isPending ? "Logging out…" : "Logout"}
            </button>
          </>
        ) : (
          <Link
            to="/login"
            className="rounded bg-blue-600 px-3 py-1 font-medium text-white hover:bg-blue-700"
          >
            Sign in
          </Link>
        )}
      </div>
    </nav>
  );
}
