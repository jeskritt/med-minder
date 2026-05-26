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

  it("calls enable when the button is clicked", async () => {
    mockStatus.mockResolvedValue("default");
    mockEnable.mockResolvedValue(undefined);
    const { user } = renderControl();
    await user.click(
      await screen.findByRole("button", { name: /enable notifications/i }),
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

  it("explains when the browser does not support notifications", async () => {
    mockStatus.mockResolvedValue("unsupported");
    renderControl();
    expect(
      await screen.findByText(/does not support notifications/i),
    ).toBeInTheDocument();
  });
});
