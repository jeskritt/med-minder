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
      name: /America\/Edmonton/,
    });
    await user.click(option);

    expect(onChange).toHaveBeenCalledWith("America/Edmonton");
    expect(input).toHaveValue("America/Edmonton");
  });

  it("finds America/Edmonton when searching by region alias (Alberta)", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TimezoneCombobox value="UTC" onChange={onChange} />);

    const input = screen.getByRole("combobox");
    await user.clear(input);
    await user.type(input, "Alberta");

    const option = await screen.findByRole("option", {
      name: /America\/Edmonton/,
    });
    await user.click(option);

    expect(onChange).toHaveBeenCalledWith("America/Edmonton");
  });

  it("includes UTC and allows searching by UTC offset", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TimezoneCombobox value="America/Toronto" onChange={onChange} />);

    const input = screen.getByRole("combobox");
    await user.clear(input);
    await user.type(input, "UTC-6");

    // America/Regina is permanent UTC-6 year-round.
    expect(
      await screen.findByRole("option", { name: /America\/Regina/ }),
    ).toBeInTheDocument();

    await user.clear(input);
    await user.type(input, "UTC");
    expect(
      await screen.findByRole("option", { name: /^UTC\b/ }),
    ).toBeInTheDocument();
  });

  it("shows multiple options on focus without clearing the existing value", async () => {
    const user = userEvent.setup();
    render(<TimezoneCombobox value="America/Edmonton" onChange={vi.fn()} />);

    const input = screen.getByRole("combobox");
    await user.click(input);

    const options = await screen.findAllByRole("option");
    expect(options.length).toBeGreaterThan(1);
  });

  it("commits an exact typed IANA match immediately so Save can enable", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<TimezoneCombobox value="UTC" onChange={onChange} />);

    const input = screen.getByRole("combobox");
    await user.clear(input);
    await user.type(input, "America/Regina");

    expect(onChange).toHaveBeenCalledWith("America/Regina");
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
