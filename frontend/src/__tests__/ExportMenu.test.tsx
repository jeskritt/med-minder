import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ExportMenu } from "@/components/medications/ExportMenu";
import * as adherence from "@/lib/adherence";

function renderMenu() {
  const qc = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <ExportMenu />
    </QueryClientProvider>,
  );
}

describe("ExportMenu", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("opens the popover with From/To inputs", async () => {
    const user = userEvent.setup();
    renderMenu();
    await user.click(screen.getByRole("button", { name: /export/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByLabelText("From")).toBeInTheDocument();
    expect(screen.getByLabelText("To")).toBeInTheDocument();
  });

  it("downloads with the chosen range", async () => {
    const spy = vi
      .spyOn(adherence, "downloadDoseHistoryCsv")
      .mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderMenu();
    await user.click(screen.getByRole("button", { name: /export/i }));
    fireEvent.change(screen.getByLabelText("From"), {
      target: { value: "2026-05-01" },
    });
    fireEvent.change(screen.getByLabelText("To"), {
      target: { value: "2026-05-31" },
    });
    await user.click(screen.getByRole("button", { name: /download csv/i }));
    expect(spy).toHaveBeenCalledWith({ from: "2026-05-01", to: "2026-05-31" });
  });

  it("disables download for an inverted range", async () => {
    const user = userEvent.setup();
    renderMenu();
    await user.click(screen.getByRole("button", { name: /export/i }));
    fireEvent.change(screen.getByLabelText("From"), {
      target: { value: "2026-05-31" },
    });
    fireEvent.change(screen.getByLabelText("To"), {
      target: { value: "2026-05-01" },
    });
    expect(
      screen.getByRole("button", { name: /download csv/i }),
    ).toBeDisabled();
  });
});
