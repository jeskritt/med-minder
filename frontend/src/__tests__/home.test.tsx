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
import { useQuery } from "@tanstack/react-query";

// Mock the API module
vi.mock("@/lib/api", () => ({
  fetchHealthz: vi.fn(),
}));

import { fetchHealthz } from "@/lib/api";
const mockFetchHealthz = vi.mocked(fetchHealthz);

// ---------------------------------------------------------------------------
// Test component — mirrors the real home page for isolated testing
// ---------------------------------------------------------------------------

function HomePageComponent() {
  const healthQuery = useQuery({
    queryKey: ["healthz"],
    queryFn: fetchHealthz,
    retry: false,
  });

  return (
    <main>
      <h1>Hello MedMinder</h1>
      <div id="health-status">
        {healthQuery.isLoading && <span>Checking backend…</span>}
        {healthQuery.isSuccess && (
          <span>Backend: {healthQuery.data.status}</span>
        )}
        {healthQuery.isError && <span>Backend: error</span>}
      </div>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Router + providers wrapper
// ---------------------------------------------------------------------------

function createTestRouter() {
  const rootRoute = createRootRoute();
  const indexRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/",
    component: HomePageComponent,
  });
  const routeTree = rootRoute.addChildren([indexRoute]);
  const memoryHistory = createMemoryHistory({ initialEntries: ["/"] });
  return createRouter({ routeTree, history: memoryHistory });
}

function renderWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  const router = createTestRouter();

  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Home page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders 'Hello MedMinder' heading", async () => {
    mockFetchHealthz.mockResolvedValue({ status: "ok" });
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Hello MedMinder")).toBeInTheDocument();
    });
  });

  it("shows success state when /healthz returns ok", async () => {
    mockFetchHealthz.mockResolvedValue({ status: "ok" });
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Backend: ok")).toBeInTheDocument();
    });
  });

  it("shows error state when /healthz fails", async () => {
    mockFetchHealthz.mockRejectedValue(new Error("Health check failed"));
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Backend: error")).toBeInTheDocument();
    });
  });
});
