import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const pathname = vi.hoisted(() => ({ value: "/" }));
vi.mock("next/navigation", () => ({ usePathname: () => pathname.value }));
import { PromotionBanner } from "@/app/components/PromotionBanner";

afterEach(() => vi.unstubAllGlobals());
const stub = () => {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify([{ badge: "Offer", headline: "A headline" }]), { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
};

describe("PromotionBanner placement", () => {
  it("shows the offer on other pages", async () => {
    pathname.value = "/";
    stub();
    render(<PromotionBanner />);
    expect(await screen.findByText("A headline")).toBeInTheDocument();
  });
  it("renders nothing on /upgrade", async () => {
    pathname.value = "/upgrade";
    const fetchMock = stub();
    const { container } = render(<PromotionBanner />);
    await new Promise((r) => setTimeout(r, 20));
    expect(container).toBeEmptyDOMElement();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
