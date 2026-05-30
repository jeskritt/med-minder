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
    <div className="min-h-screen text-foreground">
      <UpdatePrompt />
      <OfflineIndicator />
      <InstallHint />
      <NavBar />
      {/* Bottom padding clears the mobile tab bar; removed on md+ and print. */}
      <div className="pb-24 md:pb-0 print:pb-0">
        <Outlet />
      </div>
    </div>
  );
}
