import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { InteractionIndicator } from "@/components/InteractionIndicator";
import type { components } from "@/api/v1";

type InteractionStateOut = components["schemas"]["InteractionStateOut"];

function state(remaining: number): InteractionStateOut {
  const asOf = new Date().toISOString();
  return {
    as_of: asOf,
    conflicts: [
      {
        conflicting_medication_id: "00000000-0000-0000-0000-000000000002",
        conflicting_medication_name: "Sumatriptan",
        cooldown_elapses_at: asOf,
        remaining_seconds: remaining,
      },
    ],
    cooldown_elapses_at: asOf,
    remaining_seconds: remaining,
  };
}

describe("InteractionIndicator", () => {
  it("names the conflicting medication and a live remaining time", () => {
    render(<InteractionIndicator state={state(6600)} />);
    // 6600s → "1h 50m" via formatRemaining; as_of≈now so ~no drift.
    expect(
      screen.getByText(/Interacts with Sumatriptan — safe in 1h 50m/),
    ).toBeInTheDocument();
  });

  it("lists every currently-conflicting medication", () => {
    const s = state(600);
    s.conflicts.push({
      conflicting_medication_id: "00000000-0000-0000-0000-000000000003",
      conflicting_medication_name: "Naproxen",
      cooldown_elapses_at: s.as_of,
      remaining_seconds: 600,
    });
    render(<InteractionIndicator state={s} />);
    expect(
      screen.getByText(/Interacts with Sumatriptan, Naproxen/),
    ).toBeInTheDocument();
  });
});
