import { useState } from "react";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { useCurrentUser, useLogout } from "@/lib/auth";
import { ProfileDialog } from "@/components/profile/ProfileDialog";

export function NavBar() {
  const { data: user, isLoading } = useCurrentUser();
  const logout = useLogout();
  const navigate = useNavigate();
  const path = useRouterState({ select: (s) => s.location.pathname });
  const [profileOpen, setProfileOpen] = useState(false);

  if (path === "/login") {
    return null;
  }

  const handleLogout = async () => {
    await logout.mutateAsync();
    void navigate({ to: "/" });
  };

  return (
    <>
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
              <li>
                <Link
                  to="/reminders"
                  className="text-slate-600 hover:text-blue-600"
                  activeProps={{ className: "text-blue-600 font-semibold" }}
                >
                  Reminders
                </Link>
              </li>
              {user.role === "admin" && (
                <li>
                  <Link
                    to="/admin/users"
                    className="text-slate-600 hover:text-blue-600"
                    activeProps={{ className: "text-blue-600 font-semibold" }}
                  >
                    Admin
                  </Link>
                </li>
              )}
              {/* Future tabs (Timers, etc.) drop in here. */}
            </ul>
          )}
        </div>

        <div className="flex items-center gap-3 text-sm">
          {isLoading ? null : user ? (
            <>
              <button
                type="button"
                data-testid="open-profile"
                onClick={() => setProfileOpen(true)}
                className="rounded-lg px-2 py-1.5 font-medium text-gray-600 hover:bg-slate-100"
              >
                {user.name}
              </button>
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
      {/* Rendered outside <nav> — the nav's backdrop-blur would otherwise
          become the containing block for this fixed-position modal. */}
      {user && (
        <ProfileDialog
          open={profileOpen}
          onClose={() => setProfileOpen(false)}
        />
      )}
    </>
  );
}
