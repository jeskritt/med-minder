import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { AdherenceCalendar } from "@/components/adherence/AdherenceCalendar";
import type { DayAdherence } from "@/lib/adherence";

const MAY = new Date(2026, 4, 1); // May 2026

const days: DayAdherence[] = [
  { date: "2026-05-01", expected: 1, taken: 1, status: "taken" },
  { date: "2026-05-02", expected: 2, taken: 1, status: "partial" },
  { date: "2026-05-03", expected: 1, taken: 0, status: "missed" },
  { date: "2026-05-04", expected: 1, taken: 0, status: "future" },
  { date: "2026-05-05", expected: 0, taken: 0, status: "inactive" },
];

function cell(container: HTMLElement, date: string): HTMLElement | null {
  return container.querySelector(`[aria-label^="${date}:"]`);
}

describe("AdherenceCalendar", () => {
  it("colours and labels each status, with a non-color icon on every status day", () => {
    const { container } = render(
      <AdherenceCalendar days={days} monthAnchor={MAY} />,
    );

    const taken = cell(container, "2026-05-01");
    expect(taken?.getAttribute("data-status")).toBe("taken");
    expect(taken?.querySelector("svg")).not.toBeNull(); // check icon

    const partial = cell(container, "2026-05-02");
    expect(partial?.getAttribute("data-status")).toBe("partial");
    expect(partial?.querySelector("svg")).not.toBeNull(); // dash icon

    const missed = cell(container, "2026-05-03");
    expect(missed?.getAttribute("data-status")).toBe("missed");
    expect(missed?.querySelector("svg")).not.toBeNull(); // cross icon

    const future = cell(container, "2026-05-04");
    expect(future?.getAttribute("data-status")).toBe("future");
    expect(future?.querySelector("svg")).not.toBeNull(); // clock icon
  });

  it("exposes taken-of-expected counts in the accessible label", () => {
    const { container } = render(
      <AdherenceCalendar days={days} monthAnchor={MAY} />,
    );
    expect(cell(container, "2026-05-02")?.getAttribute("aria-label")).toContain(
      "1 of 2 taken",
    );
  });

  it("renders inactive days without a status icon", () => {
    const { container } = render(
      <AdherenceCalendar days={days} monthAnchor={MAY} />,
    );
    const inactive = cell(container, "2026-05-05");
    expect(inactive?.getAttribute("data-status")).toBe("inactive");
    expect(inactive?.querySelector("svg")).toBeNull();
  });

  it("renders one cell per day of the month", () => {
    const { container } = render(
      <AdherenceCalendar days={days} monthAnchor={MAY} />,
    );
    // May has 31 days.
    expect(container.querySelectorAll("[data-status]").length).toBe(31);
  });
});
