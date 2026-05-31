import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/lib/api", () => ({
  client: {
    POST: vi.fn(),
    GET: vi.fn(),
    DELETE: vi.fn(),
  },
  setApiContext: vi.fn(),
  fetchHealthz: vi.fn(),
}));

import { client } from "@/lib/api";
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

const mockGet = vi.mocked(client.GET);

beforeEach(() => {
  mockGet.mockReset();
  mockGet.mockResolvedValue({
    data: { items: [] },
    response: new Response(null, { status: 200 }),
  } as unknown as Awaited<ReturnType<typeof client.GET>>);
});

function setup(available = AVAILABLE) {
  const onSubmit = vi.fn<(b: MedicationBody, c: ConflictInput[]) => void>();
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MedicationForm
        mode="create"
        availableMedications={available}
        onSubmit={onSubmit}
      />
    </QueryClientProvider>,
  );
  return { user: userEvent.setup(), onSubmit };
}

async function fillRequired(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/^name$/i), "Sumatriptan");
  // Pill-based defaults ON; uncheck to reveal the plain quantity field.
  await user.click(screen.getByLabelText(/pill-based/i));
  await user.type(screen.getByLabelText(/^quantity per dose$/i), "1");
  await user.clear(screen.getByLabelText(/^unit$/i));
  await user.type(screen.getByLabelText(/^unit$/i), "tablet");
  // Untracked / As Needed is checked by default → total_doses: null.
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
    // Cooldown is a value + unit pair; 2 hours → 120 minutes on submit.
    await user.type(screen.getByLabelText("Cooldown"), "2");
    await user.selectOptions(screen.getByLabelText("Cooldown unit"), "hour");
    await user.click(screen.getByRole("button", { name: /add medication/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const conflicts = onSubmit.mock.calls[0][1];
    expect(conflicts).toEqual([
      { other_medication_id: "med-2", cooldown_minutes: 120 },
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
