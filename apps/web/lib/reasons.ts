import type { Reason } from "@/lib/platform-api/types";

const dates = new Intl.DateTimeFormat("en-GB", { dateStyle: "long", timeZone: "UTC" });

export function formatDate(iso: string | null): string | null {
  if (!iso) return null;
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return null;
  return dates.format(when);
}

export function reasonText(reason: Reason): string {
  const date = formatDate(reason.valid_until);
  switch (reason.label) {
    case "substack_subscription":
      if (reason.status === "active")
        return `Included with your Substack subscription${date ? `, which renews on ${date}` : ""}.`;
      if (reason.status === "grace")
        return `Included with your Substack subscription. A payment did not go through; access continues${date ? ` until ${date}` : ""} while Substack retries.`;
      return "Your Substack subscription has ended.";
    case "substack_status":
      if (reason.plan_interval === "month")
        return "You pay Substack on the monthly plan. Full access to the platform comes with the annual plan.";
      if (reason.plan_interval === "year") return "You pay Substack on the annual plan.";
      return "You have a Substack subscription that is not billed by card. It does not include the platform by itself.";
    case "launch_grant":
      if (reason.status === "active") return `Founding member access${date ? ` until ${date}` : ""}.`;
      return `This access ended${reason.status === "expired" && date ? ` on ${date}` : ""}.`;
    case "owner_grant":
      if (reason.status === "active") return `Access granted by the publisher${date ? ` until ${date}` : ""}.`;
      return `This access ended${reason.status === "expired" && date ? ` on ${date}` : ""}.`;
    case "purchase":
      return "You bought this item.";
    default:
      return "Access recorded.";
  }
}
