import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createRouter } from "@tanstack/react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { routeTree } from "./routeTree.gen";
import { setApiContext } from "@/lib/api";
import { initPwa } from "@/lib/pwa";
import "./index.css";

const queryClient = new QueryClient();

const router = createRouter({
  routeTree,
  context: { queryClient },
  defaultPreload: "intent",
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

// Wire the api-client middleware so 401s on non-/auth endpoints clear
// the cache and bounce the user to /login (FR-008).
setApiContext({
  queryClient,
  onUnauthenticated: () => {
    void router.navigate({ to: "/login" });
  },
});

// Register the PWA service worker (offline shell + push) at startup.
initPwa();

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Root element not found");

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
