import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { TimezoneCombobox } from "@/components/profile/TimezoneCombobox";

describe("TimezoneCombobox", () => {
  it("filters by substring and commits the picked zone", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TimezoneCombobox value="UTC" onChange={onChange} />);

    const input = screen.getByRole("combobox");
    await user.clear(input);
    await user.type(input, "Edmo");

    // "Edmo" is mid-string in "America/Edmonton" — substring match, not prefix.
    const option = await screen.findByRole("option", {
      name: "America/Edmonton",
    });
    await user.click(option);

    expect(onChange).toHaveBeenCalledWith("America/Edmonton");
    expect(input).toHaveValue("America/Edmonton");
  });

  it("reverts to the committed value when free text matches nothing", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TimezoneCombobox value="America/Toronto" onChange={onChange} />);

    const input = screen.getByRole("combobox");
    await user.clear(input);
    await user.type(input, "not-a-zone");
    await user.tab(); // blur

    expect(onChange).not.toHaveBeenCalled();
    expect(input).toHaveValue("America/Toronto");
  });
});
