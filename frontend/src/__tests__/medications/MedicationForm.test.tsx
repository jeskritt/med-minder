import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, type Mock } from "vitest";
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
import { MedicationForm } from "@/components/medications/MedicationForm";
import type { components } from "@/api/v1";

type MedicationBody = components["schemas"]["MedicationBody"];
type OnSubmit = (body: MedicationBody) => void | Promise<void>;

const mockGet = vi.mocked(client.GET);
const mockPost = vi.mocked(client.POST);

const SCHEDULE_ID = "11111111-1111-1111-1111-111111111111";

beforeEach(() => {
  mockGet.mockReset();
  mockPost.mockReset();
  mockGet.mockResolvedValue({
    data: {
      items: [
        {
          id: SCHEDULE_ID,
          label: "Morning",
          time_of_day: "08:00:00",
          days_of_week: 127,
        },
      ],
    },
    response: new Response(null, { status: 200 }),
  } as unknown as Awaited<ReturnType<typeof client.GET>>);
});

function renderForm(onSubmit: Mock<OnSubmit> = vi.fn<OnSubmit>()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    user: userEvent.setup(),
    onSubmit,
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <MedicationForm mode="create" onSubmit={onSubmit} />
      </QueryClientProvider>,
    ),
  };
}

describe("MedicationForm (Add)", () => {
  it("renders core inputs and submit button", () => {
    renderForm();
    expect(screen.getByLabelText(/^name$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^quantity per dose$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^unit$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^times per day$/i)).toBeInTheDocument();
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
    await user.type(screen.getByLabelText(/^quantity per dose$/i), "200");
    await user.clear(screen.getByLabelText(/^unit$/i));
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
    await user.type(screen.getByLabelText(/^quantity per dose$/i), "200");
    await user.clear(screen.getByLabelText(/^unit$/i));
    await user.type(screen.getByLabelText(/^unit$/i), "mg");
    await user.type(screen.getByLabelText(/total doses/i), "0");
    await user.click(screen.getByRole("button", { name: /add medication/i }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(
      await screen.findByText(/total doses must be > 0/i),
    ).toBeInTheDocument();
  });

  it("warns when times_per_day differs from selected schedule count", async () => {
    const { user } = renderForm();
    await user.clear(screen.getByLabelText(/^times per day$/i));
    await user.type(screen.getByLabelText(/^times per day$/i), "3");
    // No schedules selected → mismatch (0 vs 3).
    expect(await screen.findByText(/heads up: you set/i)).toBeInTheDocument();
  });

  it("submits a valid payload as the API body shape", async () => {
    const onSubmit = vi.fn<OnSubmit>();
    const { user } = renderForm(onSubmit);

    await user.type(screen.getByLabelText(/^name$/i), "Ibuprofen");
    await user.type(screen.getByLabelText(/^quantity per dose$/i), "200");
    await user.clear(screen.getByLabelText(/^unit$/i));
    await user.type(screen.getByLabelText(/^unit$/i), "mg");
    await user.clear(screen.getByLabelText(/^times per day$/i));
    await user.type(screen.getByLabelText(/^times per day$/i), "1");
    await user.click(screen.getByLabelText(/untracked/i));
    // Toggle the "Morning" chip → adds its id to selected_schedule_ids.
    await user.click(await screen.findByRole("button", { name: /morning/i }));
    await user.click(screen.getByRole("button", { name: /add medication/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      name: "Ibuprofen",
      quantity_per_dose: "200",
      unit: "mg",
      times_per_day: 1,
      total_doses: null,
      schedules: [SCHEDULE_ID],
      timer_preference: "none",
      min_interval_minutes: null,
      window_duration_minutes: null,
      pill_strength: null,
      pills_per_dose: null,
      max_doses_per_day: null,
    });
  });

  it("hides timer-config inputs when timer mode is 'none'", () => {
    renderForm();
    expect(screen.getByLabelText(/timer mode/i)).toBeInTheDocument();
    expect(
      screen.queryByLabelText(/minimum interval/i),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/window duration/i)).not.toBeInTheDocument();
  });

  it("shows min_interval input when count_down is selected", async () => {
    const { user } = renderForm();
    await user.selectOptions(
      screen.getByLabelText(/timer mode/i),
      "count_down",
    );
    expect(screen.getByLabelText(/minimum interval/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/window duration/i)).not.toBeInTheDocument();
  });

  it("blocks count_down submission without a minimum interval", async () => {
    const { user, onSubmit } = renderForm();
    await user.type(screen.getByLabelText(/^name$/i), "Ibuprofen");
    await user.type(screen.getByLabelText(/^quantity per dose$/i), "200");
    await user.clear(screen.getByLabelText(/^unit$/i));
    await user.type(screen.getByLabelText(/^unit$/i), "mg");
    await user.click(screen.getByLabelText(/untracked/i));
    await user.selectOptions(
      screen.getByLabelText(/timer mode/i),
      "count_down",
    );
    await user.click(screen.getByRole("button", { name: /add medication/i }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(
      await screen.findByText(/count_down requires a minimum interval/i),
    ).toBeInTheDocument();
  });

  it("submits count_up timer_preference cleanly", async () => {
    const onSubmit = vi.fn<OnSubmit>();
    const { user } = renderForm(onSubmit);
    await user.type(screen.getByLabelText(/^name$/i), "Sumatriptan");
    await user.type(screen.getByLabelText(/^quantity per dose$/i), "1");
    await user.clear(screen.getByLabelText(/^unit$/i));
    await user.type(screen.getByLabelText(/^unit$/i), "tablet");
    await user.click(screen.getByLabelText(/untracked/i));
    await user.selectOptions(screen.getByLabelText(/timer mode/i), "count_up");
    await user.click(screen.getByRole("button", { name: /add medication/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      timer_preference: "count_up",
      min_interval_minutes: null,
      window_duration_minutes: null,
    });
  });

  it("converts min_interval value+unit into minutes on submit", async () => {
    const onSubmit = vi.fn<OnSubmit>();
    const { user } = renderForm(onSubmit);
    await user.type(screen.getByLabelText(/^name$/i), "Tramadol");
    await user.type(screen.getByLabelText(/^quantity per dose$/i), "50");
    await user.clear(screen.getByLabelText(/^unit$/i));
    await user.type(screen.getByLabelText(/^unit$/i), "mg");
    await user.click(screen.getByLabelText(/untracked/i));
    await user.selectOptions(
      screen.getByLabelText(/timer mode/i),
      "count_down",
    );
    await user.type(screen.getByLabelText(/minimum interval/i), "4");
    await user.selectOptions(screen.getByLabelText(/interval unit/i), "hour");
    await user.click(screen.getByRole("button", { name: /add medication/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      timer_preference: "count_down",
      min_interval_minutes: 240,
    });
  });

  it("derives quantity_per_dose from pill_strength × pills_per_dose when pill-based", async () => {
    const onSubmit = vi.fn<OnSubmit>();
    const { user } = renderForm(onSubmit);
    await user.type(screen.getByLabelText(/^name$/i), "Tylenol");
    await user.click(screen.getByLabelText(/pill-based/i));
    await user.type(screen.getByLabelText(/strength per pill/i), "500");
    await user.clear(screen.getByLabelText(/^unit$/i));
    await user.type(screen.getByLabelText(/^unit$/i), "mg");
    await user.type(screen.getByLabelText(/pills per dose/i), "2");
    await user.click(screen.getByLabelText(/untracked/i));
    await user.click(screen.getByRole("button", { name: /add medication/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      pill_strength: "500",
      pills_per_dose: 2,
      quantity_per_dose: "1000",
      unit: "mg",
    });
  });
});
