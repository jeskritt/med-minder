import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { InstallHint } from "@/components/pwa/InstallHint";

const IOS_UA =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1";
const ANDROID_UA =
  "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Mobile Safari/537.36";

function setUserAgent(ua: string) {
  Object.defineProperty(navigator, "userAgent", {
    value: ua,
    configurable: true,
  });
}

beforeEach(() => {
  localStorage.clear();
  // Not running standalone, and matchMedia reports non-standalone.
  vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: false }));
});

afterEach(() => vi.unstubAllGlobals());

describe("InstallHint", () => {
  it("shows the Add to Home Screen hint on iOS Safari", async () => {
    setUserAgent(IOS_UA);
    render(<InstallHint />);
    expect(await screen.findByText(/add to home screen/i)).toBeInTheDocument();
  });

  it("does not show on non-iOS browsers", () => {
    setUserAgent(ANDROID_UA);
    render(<InstallHint />);
    expect(screen.queryByText(/add to home screen/i)).not.toBeInTheDocument();
  });

  it("stays dismissed after the user dismisses it", async () => {
    setUserAgent(IOS_UA);
    const user = userEvent.setup();
    const first = render(<InstallHint />);
    await user.click(await screen.findByRole("button", { name: /dismiss/i }));
    expect(screen.queryByText(/add to home screen/i)).not.toBeInTheDocument();
    first.unmount();

    render(<InstallHint />);
    expect(screen.queryByText(/add to home screen/i)).not.toBeInTheDocument();
  });
});
