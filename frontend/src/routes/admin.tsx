import { createFileRoute, Outlet, redirect } from "@tanstack/react-router";
import { client } from "@/lib/api";

/**
 * Admin section layout + guard (FR-001/FR-015).  Server-side `require_admin`
 * is the real control; this `beforeLoad` is the matching client gate so a
 * non-admin who types the URL is bounced rather than shown a broken page.
 * Unauthenticated → /login; authenticated non-admin → home.
 */
export const Route = createFileRoute("/admin")({
  beforeLoad: async () => {
    const { data, response } = await client.GET("/me");
    if (response.status === 401 || !data) {
      throw redirect({ to: "/login" });
    }
    if (data.role !== "admin") {
      throw redirect({ to: "/" });
    }
  },
  component: () => <Outlet />,
});
