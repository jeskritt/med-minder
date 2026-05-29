import { createRootRouteWithContext, Outlet } from "@tanstack/react-router";
import type { QueryClient } from "@tanstack/react-query";
import { NavBar } from "@/components/NavBar";
import { InstallHint } from "@/components/pwa/InstallHint";
import { OfflineIndicator } from "@/components/pwa/OfflineIndicator";
import { UpdatePrompt } from "@/components/pwa/UpdatePrompt";

interface RouterContext {
  queryClient: QueryClient;
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootComponent,
});

function RootComponent() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <UpdatePrompt />
      <OfflineIndicator />
      <InstallHint />
      <NavBar />
      <Outlet />
    </div>
  );
}
