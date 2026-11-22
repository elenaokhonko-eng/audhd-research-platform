// @vitest-environment node
import { describe, expect, it } from "vitest";
import type { Reason } from "@/lib/platform-api/types";
import { formatDate, reasonText } from "@/lib/reasons";

const r = (over: Partial<Reason>): Reason => ({ grant: "tier:paid", source: "substack_stripe", label: "substack_subscription",
  access_scope: "substack+platform", status: "active", valid_until: "2027-03-01T00:00:00Z", campaign: null, plan_interval: "year", ...over });

describe("reasonText", () => {
  it.each([
    [r({}), "Included with your Substack subscription, which renews on 1 March 2027."],
    [r({ valid_until: null }), "Included with your Substack subscription."],
    [r({ status: "grace" }), "Included with your Substack subscription. A payment did not go through; access continues until 1 March 2027 while Substack retries."],
    [r({ label: "substack_status", grant: "status:substack_paid", plan_interval: "month" }), "You pay Substack on the monthly plan. Full access to the platform comes with the annual plan."],
    [r({ label: "substack_status", grant: "status:substack_paid", plan_interval: null }), "You have a Substack subscription that is not billed by card. It does not include the platform by itself."],
    [r({ label: "launch_grant", source: "grant" }), "Founding member access until 1 March 2027."],
    [r({ label: "launch_grant", source: "grant", status: "expired" }), "This access ended on 1 March 2027."],
    [r({ label: "owner_grant", source: "grant", status: "revoked", valid_until: "2099-01-01T00:00:00Z" }), "This access ended."],
    [r({ label: "launch_grant", source: "grant", status: "revoked" }), "This access ended."],
    [r({ label: "owner_grant", source: "grant", status: "expired" }), "This access ended on 1 March 2027."],
    [r({ label: "owner_grant", source: "grant", valid_until: null }), "Access granted by the publisher."],
    [r({ label: "purchase", source: "payhip", grant: "item:sample-map" }), "You bought this item."],
  ])("%#", (reason, text) => expect(reasonText(reason)).toBe(text));
  it("formats a date in UTC and gives null for none or nonsense", () =>
    expect([formatDate("2026-11-30T23:30:00Z"), formatDate(null), formatDate("soon")]).toEqual(["30 November 2026", null, null]));
});
