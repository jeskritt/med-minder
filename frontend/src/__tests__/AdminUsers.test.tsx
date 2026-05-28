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
  type AnyRoute,
} from "@tanstack/react-router";

vi.mock("@/lib/api", () => ({
  client: { GET: vi.fn(), POST: vi.fn() },
}));

import { client } from "@/lib/api";
import { Route as AdminRoute } from "@/routes/admin";
import { UserList } from "@/components/admin/UserList";
import { UserFormDialog } from "@/components/admin/UserFormDialog";

const mockGet = vi.mocked(client.GET);
const mockPost = vi.mocked(client.POST);

function meResponse(role: "admin" | "user") {
  return {
    response: new Response(null, { status: 200 }),
    data: { id: "u1", name: "Ada", role, timezone: "UTC" },
    error: undefined,
  } as never;
}

function renderAdminGuard(initialPath = "/admin") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const rootRoute = createRootRoute();
  const adminRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/admin",
    beforeLoad: AdminRoute.options.beforeLoad as unknown as never,
    component: () => <div data-testid="admin-area">ADMIN_AREA</div>,
  });
  const loginRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/login",
    component: () => <div data-testid="login-stub">LOGIN</div>,
  });
  const homeRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/",
    component: () => <div data-testid="home-stub">HOME</div>,
  });
  const routeTree = rootRoute.addChildren([
    adminRoute,
    loginRoute,
    homeRoute,
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

function renderDialog() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const onClose = vi.fn();
  return {
    onClose,
    user: userEvent.setup(),
    ...render(
      <QueryClientProvider client={queryClient}>
        <UserFormDialog open onClose={onClose} />
      </QueryClientProvider>,
    ),
  };
}

describe("Admin route guard (FR-001)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("redirects an authenticated non-admin away from /admin", async () => {
    mockGet.mockResolvedValue(meResponse("user"));
    const { router } = renderAdminGuard("/admin");
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
    expect(screen.queryByTestId("admin-area")).not.toBeInTheDocument();
    expect(screen.getByTestId("home-stub")).toBeInTheDocument();
  });

  it("redirects an unauthenticated caller to /login", async () => {
    mockGet.mockResolvedValue({
      response: new Response(null, { status: 401 }),
      data: undefined,
      error: { detail: "Not authenticated" },
    } as never);
    const { router } = renderAdminGuard("/admin");
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  });

  it("admits an admin", async () => {
    mockGet.mockResolvedValue(meResponse("admin"));
    const { router } = renderAdminGuard("/admin");
    await waitFor(() => expect(router.state.location.pathname).toBe("/admin"));
    expect(screen.getByTestId("admin-area")).toBeInTheDocument();
  });
});

describe("UserList", () => {
  it("renders a row per active user", () => {
    render(
      <UserList
        users={[
          {
            id: "1",
            email: "a@example.com",
            name: "Ann",
            role: "admin",
            created_at: "2026-01-01T00:00:00Z",
          },
          {
            id: "2",
            email: "b@example.com",
            name: "Ben",
            role: "user",
            created_at: "2026-02-01T00:00:00Z",
          },
        ]}
      />,
    );
    expect(screen.getByText("a@example.com")).toBeInTheDocument();
    expect(screen.getByText("b@example.com")).toBeInTheDocument();
    expect(screen.getByText("admin")).toBeInTheDocument();
  });
});

describe("UserFormDialog (create)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("creates a user with a typed password via POST", async () => {
    mockPost.mockResolvedValue({
      data: {
        user: {
          id: "9",
          email: "new@example.com",
          name: "New",
          role: "user",
          created_at: "2026-05-28T00:00:00Z",
        },
        temporary_password: null,
      },
      response: new Response(null, { status: 201 }),
      error: undefined,
    } as never);

    const { user, onClose } = renderDialog();
    await user.type(screen.getByLabelText(/email/i), "new@example.com");
    await user.type(screen.getByLabelText(/display name/i), "New");
    await user.type(
      screen.getByLabelText(/^password$/i),
      "a fine long password",
    );
    await user.click(screen.getByRole("button", { name: /create user/i }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/v1/users", {
        body: {
          email: "new@example.com",
          name: "New",
          role: "user",
          password: "a fine long password",
          generate: false,
        },
      });
    });
    // No temp password → dialog closes.
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("shows a generated temporary password exactly once", async () => {
    mockPost.mockResolvedValue({
      data: {
        user: {
          id: "9",
          email: "gen@example.com",
          name: "Gen",
          role: "user",
          created_at: "2026-05-28T00:00:00Z",
        },
        temporary_password: "Xy7-generated-temp-pw",
      },
      response: new Response(null, { status: 201 }),
      error: undefined,
    } as never);

    const { user } = renderDialog();
    await user.type(screen.getByLabelText(/email/i), "gen@example.com");
    await user.type(screen.getByLabelText(/display name/i), "Gen");
    await user.click(screen.getByLabelText(/generate a temporary password/i));
    await user.click(screen.getByRole("button", { name: /create user/i }));

    expect(await screen.findByTestId("temp-password")).toHaveTextContent(
      "Xy7-generated-temp-pw",
    );
    expect(screen.getByText(/won.t be shown again/i)).toBeInTheDocument();
    // The generated path omits a typed password from the request body.
    expect(mockPost).toHaveBeenCalledWith("/api/v1/users", {
      body: {
        email: "gen@example.com",
        name: "Gen",
        role: "user",
        generate: true,
      },
    });
  });

  it("surfaces a duplicate-email 409 on the email field", async () => {
    mockPost.mockResolvedValue({
      data: undefined,
      response: new Response(null, { status: 409 }),
      error: { detail: "exists" },
    } as never);

    const { user } = renderDialog();
    await user.type(screen.getByLabelText(/email/i), "dup@example.com");
    await user.type(screen.getByLabelText(/display name/i), "Dup");
    await user.type(
      screen.getByLabelText(/^password$/i),
      "a fine long password",
    );
    await user.click(screen.getByRole("button", { name: /create user/i }));

    expect(await screen.findByText(/already exists/i)).toBeInTheDocument();
  });
});
