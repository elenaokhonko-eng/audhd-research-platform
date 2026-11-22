// Invented people at example.org, mirroring services/platform-api/tests/fixtures/people.py
// (docs/contracts/stage-1-launch.md section 8). No real data.
import type { Reason } from "@/lib/platform-api/types";

export const LAUNCH_GRANT_UNTIL = "2027-06-30T00:00:00Z";

const substackSubscription: Reason = {
  grant: "tier:paid",
  source: "substack_stripe",
  label: "substack_subscription",
  access_scope: "substack+platform",
  status: "active",
  valid_until: null,
  campaign: null,
  plan_interval: "year",
};

const launchGrant: Reason = {
  grant: "tier:paid",
  source: "grant",
  label: "launch_grant",
  access_scope: "platform_only",
  status: "active",
  valid_until: LAUNCH_GRANT_UNTIL,
  campaign: "founding",
  plan_interval: null,
};

// A paying reader whose Substack plan does not include the platform (contracts 0.4).
const statusReason = (source: Reason["source"], planInterval: Reason["plan_interval"]): Reason => ({
  grant: "status:substack_paid",
  source,
  label: "substack_status",
  access_scope: "substack+platform",
  status: "active",
  valid_until: null,
  campaign: null,
  plan_interval: planInterval,
});

export interface Person {
  name: string;
  email: string;
  tier: "free" | "paid";
  reasons: Reason[];
  termsAccepted: boolean;
}

const person = (name: string, tier: "free" | "paid", reasons: Reason[]): Person => ({
  name,
  email: `${name}@example.org`,
  tier,
  reasons,
  termsAccepted: false,
});

export const people: Person[] = [
  person("ana", "paid", [substackSubscription, launchGrant]),
  person("bo", "free", []),
  person("cy", "free", [statusReason("substack_stripe", "month")]),
  person("di", "free", [statusReason("substack_roster", null)]),
  person("ed", "free", []),
  person("fay", "paid", [launchGrant]),
  person("gus", "paid", [substackSubscription]),
  person("hal", "free", [statusReason("substack_stripe", "month")]),
];
