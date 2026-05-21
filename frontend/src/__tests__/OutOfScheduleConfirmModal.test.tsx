import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { OutOfScheduleConfirmModal } from "@/components/today/OutOfScheduleConfirmModal";

describe("OutOfScheduleConfirmModal", () => {
  it("renders nothing when closed", () => {
    const { container } = render(
      <OutOfScheduleConfirmModal
        open={false}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("calls onConfirm when 'Take anyway' is clicked", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(
      <OutOfScheduleConfirmModal
        open
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: /take anyway/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("calls onCancel when Cancel is clicked", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(
      <OutOfScheduleConfirmModal
        open
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    );
    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
