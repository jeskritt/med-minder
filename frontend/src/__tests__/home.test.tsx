import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createRootRoute,
  createRoute,
  createRouter,
  createMemoryHistory,
  RouterProvider,
} from "@tanstack/react-router";

vi.mock("@/lib/api", () => ({
  client: { GET: vi.fn(), POST: vi.fn() },
  setApiContext: vi.fn(),
  fetchHealthz: vi.fn(),
}));

import { client } from "@/lib/api";
import { Route as IndexRoute } from "@/routes/index";

const mockGet = vi.mocked(client.GET);

function renderHome() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const rootRoute = createRootRoute();
  const indexRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/",
    component: IndexRoute.options.component,
  });
  const loginRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/login",
    component: () => <div>LOGIN</div>,
  });
  const routeTree = rootRoute.addChildren([indexRoute, loginRoute]);
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("Home page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the MedMinder hero", async () => {
    mockGet.mockResolvedValue({
      response: new Response(null, { status: 401 }),
      data: undefined,
      error: undefined,
    } as never);
    renderHome();
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "MedMinder" }),
      ).toBeInTheDocument();
    });
  });

  it("shows a Sign in CTA when logged out", async () => {
    mockGet.mockResolvedValue({
      response: new Response(null, { status: 401 }),
      data: undefined,
      error: undefined,
    } as never);
    renderHome();
    await waitFor(() => {
      expect(
        screen.getByRole("link", { name: /sign in/i }),
      ).toBeInTheDocument();
    });
  });

  it("shows Today + medications CTAs when logged in", async () => {
    mockGet.mockResolvedValue({
      response: new Response(null, { status: 200 }),
      data: { id: "u", name: "Testy", role: "user" },
      error: undefined,
    } as never);
    renderHome();
    await waitFor(() => {
      expect(
        screen.getByRole("link", { name: /go to today/i }),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByRole("link", { name: /my medications/i }),
    ).toBeInTheDocument();
  });

  it("does not show a backend health indicator", async () => {
    mockGet.mockResolvedValue({
      response: new Response(null, { status: 401 }),
      data: undefined,
      error: undefined,
    } as never);
    renderHome();
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "MedMinder" }),
      ).toBeInTheDocument();
    });
    expect(screen.queryByText(/backend/i)).not.toBeInTheDocument();
  });
});
