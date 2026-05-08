import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";

import { UntakeConfirmModal } from "@/components/UntakeConfirmModal";

const FR_005_TEXT =
  "This med has already been taken. Remove the 'taken' status?";

describe("UntakeConfirmModal", () => {
  it("renders the FR-005 text exactly", () => {
    render(<UntakeConfirmModal open onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByText(FR_005_TEXT)).toBeInTheDocument();
  });

  it("calls onCancel when the cancel button is clicked", async () => {
    const onCancel = vi.fn();
    const onConfirm = vi.fn();
    render(
      <UntakeConfirmModal open onConfirm={onConfirm} onCancel={onCancel} />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("calls onConfirm when the confirm button is clicked", async () => {
    const onCancel = vi.fn();
    const onConfirm = vi.fn();
    render(
      <UntakeConfirmModal open onConfirm={onConfirm} onCancel={onCancel} />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /^confirm$/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onCancel).not.toHaveBeenCalled();
  });
});
