import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { AdherenceTrend } from "@/components/adherence/AdherenceTrend";
import type { DayAdherence } from "@/lib/adherence";

const days: DayAdherence[] = [
  { date: "2026-05-06", expected: 2, taken: 2, status: "taken" },
  { date: "2026-05-07", expected: 2, taken: 1, status: "partial" },
  { date: "2026-05-08", expected: 2, taken: 0, status: "missed" },
];

function bar(container: HTMLElement, date: string): HTMLElement | null {
  return container.querySelector(`[aria-label^="5/${Number(date.slice(-2))}"]`);
}

describe("AdherenceTrend", () => {
  it("renders one bar per day with its status", () => {
    const { container } = render(<AdherenceTrend days={days} />);
    expect(container.querySelectorAll("[data-status]").length).toBe(3);
    expect(bar(container, "2026-05-06")?.getAttribute("data-status")).toBe(
      "taken",
    );
    expect(bar(container, "2026-05-08")?.getAttribute("data-status")).toBe(
      "missed",
    );
  });

  it("shows a taken (success) segment when doses were taken", () => {
    const { container } = render(<AdherenceTrend days={days} />);
    const taken = bar(container, "2026-05-06");
    expect(taken?.querySelector(".bg-success")).not.toBeNull();
  });

  it("shows a missed (destructive) segment for a fully missed day", () => {
    const { container } = render(<AdherenceTrend days={days} />);
    const missed = bar(container, "2026-05-08");
    expect(missed?.querySelector(".bg-destructive\\/70")).not.toBeNull();
    expect(missed?.querySelector(".bg-success")).toBeNull();
  });

  it("exposes taken-of-expected counts in the label", () => {
    const { container } = render(<AdherenceTrend days={days} />);
    expect(bar(container, "2026-05-07")?.getAttribute("aria-label")).toContain(
      "1 of 2 taken",
    );
  });
});
