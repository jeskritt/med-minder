import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { DoseProgressBar } from "@/components/today/DoseProgressBar";
import type { components } from "@/api/v1";

type TodayItem = components["schemas"]["TodayItem"];

const BASE: TodayItem = {
  schedule_id: "s1",
  medication_id: "m1",
  name: "Lisinopril",
  scheduled_time: "08:00:00",
  quantity_per_dose: "10.000",
  unit: "mg",
  dose: null,
  days_of_week: 127,
  scheduled_today: true,
  schedule_label: "",
};

function getColor(container: HTMLElement): string | null {
  return (
    container
      .querySelector("[role='progressbar']")
      ?.getAttribute("data-color") ?? null
  );
}

function getValue(container: HTMLElement): number | null {
  const v = container
    .querySelector("[role='progressbar']")
    ?.getAttribute("aria-valuenow");
  return v === null || v === undefined ? null : Number(v);
}

const NOON = new Date("2026-05-08T12:00:00Z").getTime();

describe("DoseProgressBar", () => {
  it("is green when the dose has been taken", () => {
    const { container } = render(
      <DoseProgressBar
        item={{ ...BASE, dose: { id: "d", taken_at: "2026-05-08T08:05:00Z" } }}
        now={NOON}
      />,
    );
    expect(getColor(container)).toBe("green");
    expect(getValue(container)).toBe(1);
  });

  it("is amber when scheduled today and > 1h past scheduled time", () => {
    // Scheduled 08:00 local, "now" is 12:00 local → 4h late.
    const fourHoursAfter8amLocal = new Date(2026, 4, 8, 12, 0, 0).getTime();
    const { container } = render(
      <DoseProgressBar item={BASE} now={fourHoursAfter8amLocal} />,
    );
    expect(getColor(container)).toBe("amber");
  });

  it("is neutral when scheduled today but within 1h past scheduled time", () => {
    const halfHourAfter8amLocal = new Date(2026, 4, 8, 8, 30, 0).getTime();
    const { container } = render(
      <DoseProgressBar item={BASE} now={halfHourAfter8amLocal} />,
    );
    expect(getColor(container)).toBe("neutral");
  });

  it("is red when an active interaction conflict exists", () => {
    const { container } = render(
      <DoseProgressBar
        item={{
          ...BASE,
          interaction_state: {
            as_of: "2026-05-08T12:00:00Z",
            cooldown_elapses_at: "2026-05-08T14:00:00Z",
            remaining_seconds: 3600,
            conflicts: [
              {
                conflicting_medication_id: "m99",
                conflicting_medication_name: "Aspirin",
                cooldown_elapses_at: "2026-05-08T14:00:00Z",
                remaining_seconds: 3600,
              },
            ],
          },
        }}
        now={NOON}
      />,
    );
    expect(getColor(container)).toBe("red");
  });

  it("is red when the multi_sub_dose med is at capacity", () => {
    const { container } = render(
      <DoseProgressBar
        item={{
          ...BASE,
          timer_state: {
            mode: "multi_sub_dose",
            as_of: "2026-05-08T12:00:00Z",
            last_dose_at: "2026-05-08T12:00:00Z",
            multi_sub_dose: {
              window_duration_seconds: 21600,
              max_concurrent: 3,
              active_sub_doses: [
                {
                  taken_at: "2026-05-08T11:00:00Z",
                  expires_at: "2026-05-08T17:00:00Z",
                },
                {
                  taken_at: "2026-05-08T11:30:00Z",
                  expires_at: "2026-05-08T17:30:00Z",
                },
                {
                  taken_at: "2026-05-08T12:00:00Z",
                  expires_at: "2026-05-08T18:00:00Z",
                },
              ],
              slots_used: 3,
              slots_remaining: 0,
              next_available_at: "2026-05-08T17:00:00Z",
            },
          },
        }}
        now={NOON}
      />,
    );
    expect(getColor(container)).toBe("red");
  });

  it("is neutral when the slot is not scheduled today", () => {
    const fourHoursAfter8amLocal = new Date(2026, 4, 8, 12, 0, 0).getTime();
    const { container } = render(
      <DoseProgressBar
        item={{ ...BASE, scheduled_today: false }}
        now={fourHoursAfter8amLocal}
      />,
    );
    expect(getColor(container)).toBe("neutral");
  });
});
