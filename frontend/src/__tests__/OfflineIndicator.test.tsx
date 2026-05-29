import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { OfflineIndicator } from "@/components/pwa/OfflineIndicator";

function setOnLine(value: boolean) {
  Object.defineProperty(navigator, "onLine", {
    value,
    configurable: true,
  });
}

describe("OfflineIndicator", () => {
  beforeEach(() => setOnLine(true));

  it("renders nothing while online", () => {
    render(<OfflineIndicator />);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("shows the banner when an offline event fires", () => {
    render(<OfflineIndicator />);
    act(() => {
      setOnLine(false);
      window.dispatchEvent(new Event("offline"));
    });
    expect(screen.getByRole("status")).toHaveTextContent(/offline/i);
  });

  it("hides again once back online", () => {
    setOnLine(false);
    render(<OfflineIndicator />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    act(() => {
      setOnLine(true);
      window.dispatchEvent(new Event("online"));
    });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
