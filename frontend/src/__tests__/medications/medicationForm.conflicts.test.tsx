import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import {
  MedicationForm,
  type ConflictInput,
} from "@/components/medications/MedicationForm";
import type { components } from "@/api/v1";

type MedicationBody = components["schemas"]["MedicationBody"];

const AVAILABLE = [
  { id: "med-2", name: "Ibuprofen" },
  { id: "med-3", name: "Naproxen" },
];

function setup(available = AVAILABLE) {
  const onSubmit = vi.fn<(b: MedicationBody, c: ConflictInput[]) => void>();
  render(
    <MedicationForm
      mode="create"
      availableMedications={available}
      onSubmit={onSubmit}
    />,
  );
  return { user: userEvent.setup(), onSubmit };
}

async function fillRequired(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/^name$/i), "Sumatriptan");
  await user.type(screen.getByLabelText(/^dosage$/i), "1");
  await user.type(screen.getByLabelText(/^unit$/i), "tablet");
}

describe("MedicationForm — Conflicts with", () => {
  it("renders the section; Add is disabled with no available meds", () => {
    setup([]);
    expect(screen.getByText(/conflicts with/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /add interaction/i }),
    ).toBeDisabled();
  });

  it("adds a conflict row and passes it to onSubmit", async () => {
    const { user, onSubmit } = setup();
    await fillRequired(user);
    await user.click(screen.getByRole("button", { name: /add interaction/i }));
    await user.selectOptions(screen.getByLabelText(/^medication$/i), "med-2");
    await user.type(screen.getByLabelText(/cooldown/i), "30");
    await user.click(screen.getByRole("button", { name: /add medication/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const conflicts = onSubmit.mock.calls[0][1];
    expect(conflicts).toEqual([
      { other_medication_id: "med-2", cooldown_minutes: 30 },
    ]);
  });

  it("excludes an already-chosen medication from other rows' options", async () => {
    const { user } = setup();
    const add = screen.getByRole("button", { name: /add interaction/i });
    await user.click(add);
    await user.click(add);
    const selects = screen.getAllByLabelText(/^medication$/i);
    await user.selectOptions(selects[0], "med-2");
    // Row 1 must no longer offer Ibuprofen (med-2) — duplicates are
    // prevented at the UI level; the Zod refine is the backstop.
    const row1Options = Array.from(selects[1].querySelectorAll("option")).map(
      (o) => (o as HTMLOptionElement).value,
    );
    expect(row1Options).not.toContain("med-2");
    expect(row1Options).toContain("med-3");
  });
});
