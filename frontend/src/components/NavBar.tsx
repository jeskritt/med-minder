import { useState } from "react";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import {
  Bell,
  CalendarCheck,
  LogOut,
  Pill,
  Shield,
  type LucideIcon,
} from "lucide-react";
import { useCurrentUser, useLogout } from "@/lib/auth";
import { ProfileDialog } from "@/components/profile/ProfileDialog";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/today", label: "Today", icon: CalendarCheck },
  { to: "/medications", label: "Medications", icon: Pill },
  { to: "/reminders", label: "Reminders", icon: Bell },
  { to: "/admin/users", label: "Admin", icon: Shield, adminOnly: true },
];

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

  const items = NAV_ITEMS.filter(
    (item) => !item.adminOnly || user?.role === "admin",
  );

  return (
    <>
      <header
        className="sticky top-0 z-30 border-b border-border/70 bg-background/80 backdrop-blur-md print:hidden"
        aria-label="Primary"
      >
        <div className="mx-auto flex h-14 max-w-2xl items-center justify-between gap-4 px-4">
          <div className="flex items-center gap-7">
            <Link
              to="/"
              className="flex items-center gap-2 text-lg font-semibold tracking-tight text-foreground"
            >
              <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
                <Pill className="size-4" />
              </span>
              MedMinder
            </Link>
            {user && (
              <nav className="hidden md:block">
                <ul className="flex items-center gap-1 text-sm">
                  {items.map((item) => (
                    <li key={item.to}>
                      <Link
                        to={item.to}
                        className="rounded-full px-3 py-1.5 font-medium text-muted-foreground transition hover:bg-muted hover:text-foreground"
                        activeProps={{
                          className:
                            "rounded-full px-3 py-1.5 font-semibold bg-accent text-accent-foreground",
                        }}
                      >
                        {item.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </nav>
            )}
          </div>

          <div className="flex items-center gap-1.5 text-sm">
            {isLoading ? null : user ? (
              <>
                <button
                  type="button"
                  data-testid="open-profile"
                  onClick={() => setProfileOpen(true)}
                  className="flex items-center gap-2 rounded-full py-1 pr-1 pl-2.5 font-medium text-foreground transition hover:bg-muted"
                >
                  <span className="hidden max-w-[8rem] truncate sm:inline">
                    {user.name}
                  </span>
                  <span
                    className="flex size-7 items-center justify-center rounded-full bg-primary/12 text-xs font-semibold text-primary uppercase"
                    aria-hidden="true"
                  >
                    {user.name.trim().charAt(0) || "?"}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={handleLogout}
                  disabled={logout.isPending}
                  aria-label="Logout"
                  className="mm-btn mm-btn-ghost size-9 p-0"
                >
                  <LogOut className="size-4" />
                </button>
              </>
            ) : (
              <Link to="/login" className="mm-btn mm-btn-primary">
                Sign in
              </Link>
            )}
          </div>
        </div>
      </header>

      {/* Mobile bottom tab bar — the primary navigation on phones. */}
      {user && (
        <nav
          aria-label="Primary"
          className="fixed inset-x-0 bottom-0 z-30 border-t border-border/70 bg-background/90 backdrop-blur-md md:hidden print:hidden"
          style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
        >
          <ul className="mx-auto flex max-w-2xl items-stretch justify-around">
            {items.map((item) => {
              const Icon = item.icon;
              return (
                <li key={item.to} className="flex-1">
                  <Link
                    to={item.to}
                    className="flex flex-col items-center gap-1 px-1 py-2 text-[0.7rem] font-medium text-muted-foreground transition"
                    activeProps={{
                      className:
                        "flex flex-col items-center gap-1 px-1 py-2 text-[0.7rem] font-semibold text-primary",
                    }}
                  >
                    <Icon className="size-5" strokeWidth={2} />
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      )}

      {/* Rendered outside the sticky header — the header's backdrop-blur
          would otherwise become the containing block for this fixed modal. */}
      {user && (
        <ProfileDialog
          open={profileOpen}
          onClose={() => setProfileOpen(false)}
        />
      )}
    </>
  );
}
