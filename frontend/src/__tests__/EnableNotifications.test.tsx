import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/lib/push", () => ({
  getPushStatus: vi.fn(),
  enablePushNotifications: vi.fn(),
  disablePushNotifications: vi.fn(),
  isPushSupported: vi.fn(() => true),
}));

import { enablePushNotifications, getPushStatus } from "@/lib/push";
import { EnableNotifications } from "@/components/reminders/EnableNotifications";

const mockStatus = vi.mocked(getPushStatus);
const mockEnable = vi.mocked(enablePushNotifications);

function renderControl() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    user: userEvent.setup(),
    ...render(
      <QueryClientProvider client={queryClient}>
        <EnableNotifications />
      </QueryClientProvider>,
    ),
  };
}

describe("EnableNotifications", () => {
  beforeEach(() => vi.clearAllMocks());

  it("offers an enable button when permission is default", async () => {
    mockStatus.mockResolvedValue("default");
    renderControl();
    expect(
      await screen.findByRole("button", { name: /enable notifications/i }),
    ).toBeInTheDocument();
  });

  it("offers an enable button when granted but not subscribed", async () => {
    mockStatus.mockResolvedValue("unsubscribed");
    renderControl();
    expect(
      await screen.findByRole("button", { name: /enable notifications/i }),
    ).toBeInTheDocument();
  });

  it("shows a contextual pre-prompt before invoking the native dialog", async () => {
    mockStatus.mockResolvedValue("default");
    const { user } = renderControl();
    await user.click(
      await screen.findByRole("button", { name: /enable notifications/i }),
    );
    // The pre-prompt explains what enabling does; the native dialog is not
    // invoked until the user confirms.
    expect(
      screen.getByText(/at each scheduled dose time/i),
    ).toBeInTheDocument();
    expect(mockEnable).not.toHaveBeenCalled();
  });

  it("calls enable only after the user confirms the pre-prompt", async () => {
    mockStatus.mockResolvedValue("default");
    mockEnable.mockResolvedValue(undefined);
    const { user } = renderControl();
    await user.click(
      await screen.findByRole("button", { name: /enable notifications/i }),
    );
    await user.click(
      await screen.findByRole("button", { name: /turn on reminders/i }),
    );
    expect(mockEnable).toHaveBeenCalledOnce();
  });

  it("shows the enabled state when subscribed", async () => {
    mockStatus.mockResolvedValue("subscribed");
    renderControl();
    expect(
      await screen.findByText(/notifications are on/i),
    ).toBeInTheDocument();
  });

  it("explains recovery when notifications are blocked/denied", async () => {
    mockStatus.mockResolvedValue("denied");
    renderControl();
    expect(
      await screen.findByText(/blocked for this site/i),
    ).toBeInTheDocument();
    // Actionable recovery guidance, not a dead button.
    expect(screen.getByText(/site settings/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /enable notifications/i }),
    ).not.toBeInTheDocument();
  });

  it("explains when the browser does not support notifications", async () => {
    mockStatus.mockResolvedValue("unsupported");
    renderControl();
    expect(
      await screen.findByText(/does not support notifications/i),
    ).toBeInTheDocument();
  });
});
