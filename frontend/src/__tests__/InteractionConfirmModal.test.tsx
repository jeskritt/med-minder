import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";

import { InteractionConfirmModal } from "@/components/InteractionConfirmModal";
import type { components } from "@/api/v1";

type InteractionCooldownViolation =
  components["schemas"]["InteractionCooldownViolation"];

const conflict: InteractionCooldownViolation = {
  code: "interaction_cooldown_active",
  medication_id: "00000000-0000-0000-0000-000000000001",
  conflicts: [
    {
      conflicting_medication_id: "00000000-0000-0000-0000-000000000002",
      conflicting_medication_name: "Sumatriptan",
      cooldown_elapses_at: "2026-05-18T15:00:00Z",
      remaining_seconds: 6600,
    },
  ],
  cooldown_elapses_at: "2026-05-18T15:00:00Z",
  remaining_seconds: 6600,
};

describe("InteractionConfirmModal", () => {
  it("names the conflicting medication and shows remaining cooldown", () => {
    render(
      <InteractionConfirmModal
        open
        conflict={conflict}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText(/Interacts with Sumatriptan/)).toBeInTheDocument();
    // 6600s → "1h 50m" via formatRemaining
    expect(screen.getByText(/Safe in 1h 50m/)).toBeInTheDocument();
  });

  it("offers an overridable 'Take anyway' action distinct from a dead-end", async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <InteractionConfirmModal
        open
        conflict={conflict}
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /take anyway/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("renders nothing when closed or no conflict", () => {
    const { container, rerender } = render(
      <InteractionConfirmModal
        open={false}
        conflict={conflict}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
    rerender(
      <InteractionConfirmModal
        open
        conflict={null}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
