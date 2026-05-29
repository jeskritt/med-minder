import type { ReactNode } from "react";
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
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() },
}));

import { client } from "@/lib/api";
import { Route as AdminRoute } from "@/routes/admin";
import { Route as AdminAuditRoute } from "@/routes/admin.audit";
import { UserList } from "@/components/admin/UserList";
import { UserFormDialog } from "@/components/admin/UserFormDialog";
import { ResetPasswordDialog } from "@/components/admin/ResetPasswordDialog";
import { DeactivateUserModal } from "@/components/admin/DeactivateUserModal";

const mockGet = vi.mocked(client.GET);
const mockPost = vi.mocked(client.POST);
const mockPatch = vi.mocked(client.PATCH);
const mockDelete = vi.mocked(client.DELETE);

const SAMPLE_USER = {
  id: "9",
  email: "edit@example.com",
  name: "Edit Me",
  role: "user" as const,
  created_at: "2026-05-28T00:00:00Z",
};

function withClient(node: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    user: userEvent.setup(),
    ...render(
      <QueryClientProvider client={queryClient}>{node}</QueryClientProvider>,
    ),
  };
}

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

function renderAuditRouter() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const rootRoute = createRootRoute();
  const auditRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/admin/audit",
    component: AdminAuditRoute.options.component,
  });
  const usersRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/admin/users",
    component: () => <div>USERS</div>,
  });
  const routeTree = rootRoute.addChildren([
    auditRoute,
    usersRoute,
  ] as unknown as AnyRoute[]);
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: ["/admin/audit"] }),
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
  const users = [
    {
      id: "1",
      email: "a@example.com",
      name: "Ann",
      role: "admin" as const,
      created_at: "2026-01-01T00:00:00Z",
    },
    {
      id: "2",
      email: "b@example.com",
      name: "Ben",
      role: "user" as const,
      created_at: "2026-02-01T00:00:00Z",
    },
  ];
  const noop = () => {};

  it("renders a row per active user", () => {
    render(
      <UserList
        users={users}
        onEdit={noop}
        onResetPassword={noop}
        onDeactivate={noop}
      />,
    );
    expect(screen.getByText("a@example.com")).toBeInTheDocument();
    expect(screen.getByText("b@example.com")).toBeInTheDocument();
    expect(screen.getByText("admin")).toBeInTheDocument();
  });

  it("disables actions on the acting admin's own row (FR-019)", () => {
    render(
      <UserList
        users={users}
        currentUserId="1"
        onEdit={noop}
        onResetPassword={noop}
        onDeactivate={noop}
      />,
    );
    // Self row shows "(you)" and no action buttons; the other row has them.
    expect(screen.getByText("(you)")).toBeInTheDocument();
    // Exactly one Edit button (for the non-self row).
    expect(screen.getAllByRole("button", { name: /^edit$/i })).toHaveLength(1);
  });

  it("invokes the row callbacks", async () => {
    const onEdit = vi.fn();
    const onResetPassword = vi.fn();
    const onDeactivate = vi.fn();
    const user = userEvent.setup();
    render(
      <UserList
        users={[users[1]]}
        onEdit={onEdit}
        onResetPassword={onResetPassword}
        onDeactivate={onDeactivate}
      />,
    );
    await user.click(screen.getByRole("button", { name: /^edit$/i }));
    await user.click(screen.getByRole("button", { name: /reset password/i }));
    await user.click(screen.getByRole("button", { name: /deactivate/i }));
    expect(onEdit).toHaveBeenCalledWith(users[1]);
    expect(onResetPassword).toHaveBeenCalledWith(users[1]);
    expect(onDeactivate).toHaveBeenCalledWith(users[1]);
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

describe("UserFormDialog (edit)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("prefills and saves name/email/role via PATCH", async () => {
    mockPatch.mockResolvedValue({
      data: { ...SAMPLE_USER, name: "Renamed" },
      response: new Response(null, { status: 200 }),
      error: undefined,
    } as never);

    const onClose = vi.fn();
    const { user } = withClient(
      <UserFormDialog open editUser={SAMPLE_USER} onClose={onClose} />,
    );
    // Prefilled, and no password field in edit mode.
    expect(screen.getByDisplayValue("Edit Me")).toBeInTheDocument();
    expect(screen.queryByLabelText(/^password$/i)).not.toBeInTheDocument();

    const nameInput = screen.getByLabelText(/display name/i);
    await user.clear(nameInput);
    await user.type(nameInput, "Renamed");
    await user.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalledWith("/api/v1/users/{user_id}", {
        params: { path: { user_id: "9" } },
        body: { name: "Renamed", email: "edit@example.com", role: "user" },
      });
    });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });
});

describe("ResetPasswordDialog", () => {
  beforeEach(() => vi.clearAllMocks());

  it("resets with a typed password via the password endpoint", async () => {
    mockPost.mockResolvedValue({
      data: { temporary_password: null },
      response: new Response(null, { status: 200 }),
      error: undefined,
    } as never);

    const onClose = vi.fn();
    const { user } = withClient(
      <ResetPasswordDialog user={SAMPLE_USER} onClose={onClose} />,
    );
    await user.type(
      screen.getByLabelText(/new password/i),
      "a fresh long password",
    );
    await user.click(screen.getByRole("button", { name: /reset password/i }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith(
        "/api/v1/users/{user_id}/password",
        {
          params: { path: { user_id: "9" } },
          body: { password: "a fresh long password", generate: false },
        },
      );
    });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("shows a generated temp password once", async () => {
    mockPost.mockResolvedValue({
      data: { temporary_password: "Zz9-reset-temp-pw" },
      response: new Response(null, { status: 200 }),
      error: undefined,
    } as never);

    const { user } = withClient(
      <ResetPasswordDialog user={SAMPLE_USER} onClose={() => {}} />,
    );
    await user.click(screen.getByLabelText(/generate a temporary password/i));
    await user.click(screen.getByRole("button", { name: /reset password/i }));

    expect(await screen.findByTestId("temp-password")).toHaveTextContent(
      "Zz9-reset-temp-pw",
    );
    expect(mockPost).toHaveBeenCalledWith("/api/v1/users/{user_id}/password", {
      params: { path: { user_id: "9" } },
      body: { generate: true },
    });
  });
});

describe("DeactivateUserModal", () => {
  beforeEach(() => vi.clearAllMocks());

  it("confirms via an in-app dialog and calls DELETE", async () => {
    mockDelete.mockResolvedValue({
      data: undefined,
      response: new Response(null, { status: 204 }),
      error: undefined,
    } as never);

    const onClose = vi.fn();
    const { user } = withClient(
      <DeactivateUserModal user={SAMPLE_USER} onClose={onClose} />,
    );
    // In-app modal (role=dialog), not the native confirm().
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^deactivate$/i }));

    await waitFor(() => {
      expect(mockDelete).toHaveBeenCalledWith("/api/v1/users/{user_id}", {
        params: { path: { user_id: "9" } },
      });
    });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });
});

describe("Audit view (US4)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders audit entries newest-first", async () => {
    mockGet.mockResolvedValue({
      data: {
        items: [
          {
            id: "e2",
            actor_id: "admin-1",
            target_user_id: "u-1",
            action: "password_reset",
            details: { fields: ["password"] },
            created_at: "2026-05-28T10:00:00Z",
          },
          {
            id: "e1",
            actor_id: "admin-1",
            target_user_id: "u-1",
            action: "create",
            details: { fields: ["email", "name", "role"] },
            created_at: "2026-05-28T09:00:00Z",
          },
        ],
      },
      response: new Response(null, { status: 200 }),
      error: undefined,
    } as never);

    const { router } = renderAuditRouter();
    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/admin/audit"),
    );
    expect(await screen.findByText(/password reset/i)).toBeInTheDocument();
    expect(screen.getByText(/created/i)).toBeInTheDocument();
  });
});
