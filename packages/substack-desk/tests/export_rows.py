"""Invented export files for the tests. No real row belongs here."""

import csv
import io

HEADER: list[str] = [
    "Email", "Name", "Type", "Activity", "Start date", "Revenue", "Comments", "Comments (7d)",
    "Comments (30d)", "Shares", "Shares (7d)", "Shares (30d)", "Country", "State/Province",
    "Time zone", "Emails received (6mo)", "Emails dropped (6mo)", "num_emails_opened",
    "Emails opened (6mo)", "Emails opened (7d)", "Emails opened (30d)", "Last email open",
    "Links clicked", "Last clicked at", "Video plays (30d)", "Unique videos played (30d)",
    "Last video played", "Podcast plays (30d)", "Unique podcasts played (30d)",
    "Last podcast played", "Unique emails seen (6mo)", "Unique emails seen (7d)",
    "Unique emails seen (30d)", "Post views", "Post views (7d)", "Post views (30d)",
    "Unique posts seen", "Unique posts seen (7d)", "Unique posts seen (30d)",
    "Subscriptions gifted", "Expiration date", "Subscription source (free)",
    "Subscription source (paid)", "Days active (30d)", "First paid date", "Paid upgrade date",
    "Cancel date", "Cancel reason", "Cancel feedback", "Bestseller", "Stripe plan", "Sections",
    "Group membership",
]


def make_export(
    rows: list[dict[str, str]], sep: str = ",", header: list[str] | None = None
) -> str:
    """Write a header and one line per row; keys not in the header are ignored."""
    names = HEADER if header is None else header
    out = io.StringIO(newline="")
    writer = csv.writer(out, delimiter=sep, lineterminator="\r\n")
    writer.writerow(names)
    for row in rows:
        writer.writerow([row.get(name, "") for name in names])
    return out.getvalue()
