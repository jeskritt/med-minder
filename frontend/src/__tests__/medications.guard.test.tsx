import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createRootRoute,
  createRoute,
  createRouter,
  createMemoryHistory,
  RouterProvider,
  type AnyRoute,
} from "@tanstack/react-router";

vi.mock("@/lib/api", () => ({
  client: {
    GET: vi.fn(),
    POST: vi.fn(), // needed since medications page imports useLogout which uses client.POST
  },
}));

import { client } from "@/lib/api";
import { Route as MedicationsRoute } from "@/routes/medications.index";

const mockGet = vi.mocked(client.GET);

function renderRouter(initialPath: string = "/medications") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const rootRoute = createRootRoute();

  // The actual route to test
  const medicationsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/medications",
    // Detach the file-route's Register-bound beforeLoad type so generic
    // inference for this synthetic route matches the clean pattern in
    // today.test.tsx. Runtime value is unchanged — the real auth-redirect
    // still executes (it is the behaviour under test).
    beforeLoad: MedicationsRoute.options.beforeLoad as unknown as never,
    component: MedicationsRoute.options.component,
  });

  // A dummy login route to redirect to
  const loginRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/login",
    component: () => <div data-testid="login-stub">LOGIN_PAGE</div>,
  });

  // Synthetic harness tree: the route above splices the real file-route's
  // beforeLoad (deliberately type-erased), so cast to the loose route type
  // `addChildren` expects. Runtime behaviour is unaffected.
  const routeTree = rootRoute.addChildren([
    medicationsRoute,
    loginRoute,
  ] as unknown as AnyRoute[]);
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [initialPath] }),
  });

  return {
    router,
    ...render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    ),
  };
}

describe("Medications Route Guard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects to /login when unauthenticated", async () => {
    // Mock /me to return 401
    mockGet.mockResolvedValue({
      response: new Response(null, { status: 401 }),
      data: undefined,
      error: { detail: "Not authenticated" },
    } as never);

    const { router } = renderRouter("/medications");

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/login");
    });

    // The protected content should not be rendered
    expect(
      screen.queryByRole("heading", { name: /^medications$/i }),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId("login-stub")).toBeInTheDocument();
  });

  it("renders the protected content when authenticated", async () => {
    // Mock /me to return 200 with user data
    mockGet.mockResolvedValue({
      response: new Response(null, { status: 200 }),
      data: { id: "user123", name: "Alice", role: "user" },
      error: undefined,
    } as never);

    const { router } = renderRouter("/medications");

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/medications");
    });

    expect(
      screen.getAllByRole("heading", { name: /^medications$/i }).length,
    ).toBeGreaterThan(0);
  });
});
