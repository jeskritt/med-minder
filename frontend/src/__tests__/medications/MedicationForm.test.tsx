import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { MedicationForm } from "@/components/medications/MedicationForm";

function renderForm(onSubmit: ReturnType<typeof vi.fn> = vi.fn()) {
  return {
    user: userEvent.setup(),
    onSubmit,
    ...render(<MedicationForm mode="create" onSubmit={onSubmit} />),
  };
}

describe("MedicationForm (Add)", () => {
  it("renders core inputs and submit button", () => {
    renderForm();
    expect(screen.getByLabelText(/^name$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^dosage$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^unit$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/times per day/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/start date/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/end date/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/untracked/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /add medication/i }),
    ).toBeInTheDocument();
  });

  it("blocks submission when required fields are blank", async () => {
    const { user, onSubmit } = renderForm();
    await user.click(screen.getByRole("button", { name: /add medication/i }));
    expect(onSubmit).not.toHaveBeenCalled();
    const alerts = screen.getAllByRole("alert");
    expect(alerts.length).toBeGreaterThan(0);
  });

  it("rejects an end date before the start date", async () => {
    const { user, onSubmit } = renderForm();
    await user.type(screen.getByLabelText(/^name$/i), "Ibuprofen");
    await user.type(screen.getByLabelText(/^dosage$/i), "200");
    await user.type(screen.getByLabelText(/^unit$/i), "mg");
    await user.type(screen.getByLabelText(/start date/i), "2026-05-10");
    await user.type(screen.getByLabelText(/end date/i), "2026-05-01");
    await user.click(screen.getByRole("button", { name: /add medication/i }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(
      await screen.findByText(/end date must be on or after start date/i),
    ).toBeInTheDocument();
  });

  it("rejects total_doses=0 unless Untracked is checked", async () => {
    const { user, onSubmit } = renderForm();
    await user.type(screen.getByLabelText(/^name$/i), "Ibuprofen");
    await user.type(screen.getByLabelText(/^dosage$/i), "200");
    await user.type(screen.getByLabelText(/^unit$/i), "mg");
    await user.type(screen.getByLabelText(/total doses/i), "0");
    await user.click(screen.getByRole("button", { name: /add medication/i }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(
      await screen.findByText(/total doses must be > 0/i),
    ).toBeInTheDocument();
  });

  it("warns when times_per_day differs from schedule count", async () => {
    const { user } = renderForm();
    await user.clear(screen.getByLabelText(/times per day/i));
    await user.type(screen.getByLabelText(/times per day/i), "3");
    await user.click(screen.getByRole("button", { name: /add schedule/i }));

    expect(await screen.findByText(/heads up: you set/i)).toBeInTheDocument();
  });

  it("submits a valid payload as the API body shape", async () => {
    const onSubmit = vi.fn();
    const { user } = renderForm(onSubmit);

    await user.type(screen.getByLabelText(/^name$/i), "Ibuprofen");
    await user.type(screen.getByLabelText(/^dosage$/i), "200");
    await user.type(screen.getByLabelText(/^unit$/i), "mg");
    await user.clear(screen.getByLabelText(/times per day/i));
    await user.type(screen.getByLabelText(/times per day/i), "1");
    await user.click(screen.getByLabelText(/untracked/i));
    await user.click(screen.getByRole("button", { name: /add schedule/i }));
    const timeInput = screen.getByLabelText(/schedule 1 time/i);
    await user.type(timeInput, "08:00");
    await user.click(screen.getByRole("button", { name: /add medication/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      name: "Ibuprofen",
      quantity_per_dose: "200",
      unit: "mg",
      times_per_day: 1,
      total_doses: null,
      schedules: ["08:00"],
    });
  });
});
