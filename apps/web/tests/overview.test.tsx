import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LibraryCount } from "@/app/member/components/LibraryCount";

describe("LibraryCount", () => {
  it("tells a paid member that everything is open", () => {
    render(<LibraryCount counts={{ total: 12, open: 12 }} tier="paid" />);
    expect(screen.getByText("The library has 12 items. You can open all of them.")).toBeInTheDocument();
    expect(screen.queryByRole("link")).toBeNull();
  });
  it("tells a free member how many are open and where to open the rest", () => {
    render(<LibraryCount counts={{ total: 12, open: 0 }} tier="free" />);
    expect(screen.getByText("The library has 12 items. You can open 0 of them.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See how to open the rest" })).toHaveAttribute("href", "/upgrade");
  });
  it("says 1 item, and shows nothing without counts", () => {
    const { rerender } = render(<LibraryCount counts={{ total: 1, open: 1 }} tier="paid" />);
    expect(screen.getByText("The library has 1 item. You can open all of them.")).toBeInTheDocument();
    rerender(<LibraryCount counts={null} tier="free" />);
    expect(screen.queryByText(/The library has/)).toBeNull();
  });
  it("tells a free member the number even when all are open, with no link", () => {
    render(<LibraryCount counts={{ total: 2, open: 2 }} tier="free" />);
    expect(screen.getByText("The library has 2 items. You can open 2 of them.")).toBeInTheDocument();
    expect(screen.queryByRole("link")).toBeNull();
  });
  it("shows nothing for an empty library", () => {
    render(<LibraryCount counts={{ total: 0, open: 0 }} tier="paid" />);
    expect(screen.queryByText(/The library has/)).toBeNull();
  });
});
