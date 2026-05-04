import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
  client: {
    POST: vi.fn(),
    GET: vi.fn(),
  },
  setApiContext: vi.fn(),
  fetchHealthz: vi.fn(),
}));

import { client } from "@/lib/api";
import { Route as LoginRoute } from "@/routes/login";

const mockPost = vi.mocked(client.POST);

function renderLogin() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const rootRoute = createRootRoute();
  const loginRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/login",
    component: LoginRoute.options.component,
  });
  const medicationsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/medications",
    component: () => <div data-testid="medications-stub">MEDS</div>,
  });
  const routeTree = rootRoute.addChildren([loginRoute, medicationsRoute]);
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: ["/login"] }),
  });
  return {
    user: userEvent.setup(),
    router,
    ...render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    ),
  };
}

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the form", async () => {
    renderLogin();
    expect(
      await screen.findByRole("button", { name: /sign in/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it("blocks submission until both fields are filled", async () => {
    const { user } = renderLogin();
    await user.click(await screen.findByRole("button", { name: /sign in/i }));
    expect(mockPost).not.toHaveBeenCalled();
    expect(screen.getAllByRole("alert").length).toBeGreaterThanOrEqual(2);
  });

  it("renders the generic FR-004 error on a 401", async () => {
    mockPost.mockResolvedValue({
      response: new Response(null, { status: 401 }),
      data: undefined,
      error: { detail: "Email or password is incorrect." },
    } as never);

    const { user } = renderLogin();
    await user.type(
      await screen.findByLabelText(/email/i),
      "alice@example.com",
    );
    await user.type(screen.getByLabelText(/password/i), "wrong-password");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(
      await screen.findByText("Email or password is incorrect."),
    ).toBeInTheDocument();
  });

  it("navigates to /medications on a 204 success", async () => {
    mockPost.mockResolvedValue({
      response: new Response(null, { status: 204 }),
      data: undefined,
      error: undefined,
    } as never);

    const { user, router } = renderLogin();
    await user.type(
      await screen.findByLabelText(/email/i),
      "alice@example.com",
    );
    await user.type(
      screen.getByLabelText(/password/i),
      "correct horse battery staple",
    );
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/medications");
    });
  });
});
