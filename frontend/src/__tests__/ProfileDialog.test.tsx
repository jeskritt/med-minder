import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/lib/api", () => ({
  client: {
    GET: vi.fn(),
    POST: vi.fn(),
    PATCH: vi.fn(),
  },
  setApiContext: vi.fn(),
  fetchHealthz: vi.fn(),
}));

import { client } from "@/lib/api";
import { ProfileDialog } from "@/components/profile/ProfileDialog";

const mockGet = vi.mocked(client.GET);
const mockPost = vi.mocked(client.POST);
const mockPatch = vi.mocked(client.PATCH);

function renderDialog() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    user: userEvent.setup(),
    ...render(
      <QueryClientProvider client={queryClient}>
        <ProfileDialog open onClose={() => {}} />
      </QueryClientProvider>,
    ),
  };
}

describe("ProfileDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // useCurrentUser() probes GET /me.
    mockGet.mockResolvedValue({
      data: { id: "u1", name: "Molly", role: "user" },
      response: new Response(null, { status: 200 }),
      error: undefined,
    } as never);
  });

  it("prefills the display name and shows both sections", async () => {
    renderDialog();
    expect(await screen.findByDisplayValue("Molly")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /save name/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/current password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/new password/i)).toBeInTheDocument();
  });

  it("saves the display name via PATCH /me", async () => {
    mockPatch.mockResolvedValue({
      data: { id: "u1", name: "Molly R.", role: "user" },
      response: new Response(null, { status: 200 }),
      error: undefined,
    } as never);

    const { user } = renderDialog();
    const nameInput = await screen.findByDisplayValue("Molly");
    await user.clear(nameInput);
    await user.type(nameInput, "Molly R.");
    await user.click(screen.getByRole("button", { name: /save name/i }));

    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalledWith("/me", {
        body: { name: "Molly R." },
      });
    });
  });

  it("blocks a too-short new password client-side", async () => {
    const { user } = renderDialog();
    await screen.findByDisplayValue("Molly");
    await user.type(screen.getByLabelText(/current password/i), "whatever-now");
    await user.type(screen.getByLabelText(/new password/i), "short");
    await user.click(screen.getByRole("button", { name: /change password/i }));

    expect(
      await screen.findByText(/use at least 12 characters/i),
    ).toBeInTheDocument();
    expect(mockPost).not.toHaveBeenCalled();
  });

  it("surfaces a 403 on the current-password field", async () => {
    mockPost.mockResolvedValue({
      response: new Response(null, { status: 403 }),
      data: undefined,
      error: undefined,
    } as never);

    const { user } = renderDialog();
    await screen.findByDisplayValue("Molly");
    await user.type(
      screen.getByLabelText(/current password/i),
      "wrong-current-pw",
    );
    await user.type(
      screen.getByLabelText(/new password/i),
      "a brand new passphrase",
    );
    await user.click(screen.getByRole("button", { name: /change password/i }));

    expect(
      await screen.findByText(/current password is incorrect/i),
    ).toBeInTheDocument();
  });
});
