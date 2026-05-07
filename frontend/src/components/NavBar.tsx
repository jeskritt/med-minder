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
      className="flex items-center justify-between border-b bg-white px-6 py-3 print:hidden"
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
                to="/medications"
                className="text-gray-700 hover:text-blue-600"
                activeProps={{ className: "text-blue-600 font-medium" }}
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
              className="rounded border px-3 py-1 hover:bg-gray-50 disabled:opacity-50"
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
