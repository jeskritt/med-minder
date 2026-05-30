import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { CourseProgress } from "@/components/adherence/CourseProgress";

describe("CourseProgress", () => {
  it("shows N of M doses", () => {
    render(
      <CourseProgress course={{ total: 14, taken: 9, complete: false }} />,
    );
    expect(screen.getByText("9")).toBeInTheDocument();
    expect(screen.getByText(/of 14 doses/)).toBeInTheDocument();
    const bar = screen.getByRole("progressbar");
    expect(bar.getAttribute("aria-valuenow")).toBe("9");
    expect(bar.getAttribute("aria-valuemax")).toBe("14");
  });

  it("does not show the complete badge while in progress", () => {
    render(
      <CourseProgress course={{ total: 14, taken: 9, complete: false }} />,
    );
    expect(screen.queryByText(/course complete/i)).not.toBeInTheDocument();
  });

  it("shows the complete badge once the course is done", () => {
    render(
      <CourseProgress course={{ total: 14, taken: 14, complete: true }} />,
    );
    expect(screen.getByText(/course complete/i)).toBeInTheDocument();
  });
});
