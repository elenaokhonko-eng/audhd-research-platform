import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import MemberError from "@/app/member/error";

describe("member error page", () => {
  it("has one h1, the message, and a Try again button that resets", () => {
    const reset = vi.fn();
    render(<MemberError error={new Error("unavailable")} reset={reset} />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("main")).toBeTruthy();
    expect(screen.getByText("The member area cannot be reached right now. Please try again in a minute.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(reset).toHaveBeenCalledTimes(1);
  });
});
