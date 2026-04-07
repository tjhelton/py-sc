"""
SafetyCulture Schedule Items - Export

Fetches all schedule items from an organisation and exports them to CSV.
Supports filtering by status via command-line arguments.

Usage:
  python main.py                          # Export all schedules
  python main.py --status ACTIVE          # Only active schedules
  python main.py --status ACTIVE PAUSED   # Active and paused schedules
"""

import argparse
import csv
import json
import sys
from datetime import datetime

import requests

TOKEN = ""  # Set your SafetyCulture API token here

BASE_URL = "https://api.safetyculture.io"
PAGE_SIZE = 100

VALID_STATUSES = ["ACTIVE", "PAUSED", "ARCHIVED"]

CSV_HEADERS = [
    "id",
    "status",
    "description",
    "recurrence",
    "start_time_hour",
    "start_time_minute",
    "duration",
    "timezone",
    "from_date",
    "to_date",
    "can_late_submit",
    "must_complete",
    "site_based_assignment_enabled",
    "location_id",
    "asset_id",
    "document_id",
    "document_type",
    "creator_name",
    "created_at",
    "modified_at",
    "next_occurrence_start",
    "next_occurrence_due",
    "assignees",
    "reminders",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export SafetyCulture schedule items to CSV."
    )
    parser.add_argument(
        "--status",
        nargs="+",
        choices=VALID_STATUSES,
        default=None,
        help="Filter by schedule status. Accepts one or more values: "
        + ", ".join(VALID_STATUSES),
    )
    return parser.parse_args()


def parse_schedule_item(item):
    creator = item.get("creator", {})
    start_time = item.get("start_time", {})
    doc = item.get("document", {})
    next_occ = item.get("next_occurrence", {})

    def s(val):
        if val is None:
            return ""
        return str(val)

    return {
        "id": s(item.get("id")),
        "status": s(item.get("status")),
        "description": s(item.get("description")),
        "recurrence": s(item.get("recurrence")),
        "start_time_hour": s(start_time.get("hour")),
        "start_time_minute": s(start_time.get("minute")),
        "duration": s(item.get("duration")),
        "timezone": s(item.get("timezone")),
        "from_date": s(item.get("from_date")),
        "to_date": s(item.get("to_date")),
        "can_late_submit": s(item.get("can_late_submit")).lower(),
        "must_complete": s(item.get("must_complete")),
        "site_based_assignment_enabled": s(
            item.get("site_based_assignment_enabled")
        ).lower(),
        "location_id": s(item.get("location_id")),
        "asset_id": s(item.get("asset_id")),
        "document_id": doc.get("id", ""),
        "document_type": doc.get("type", ""),
        "creator_name": s(creator.get("name")),
        "created_at": s(item.get("created_at")),
        "modified_at": s(item.get("modified_at")),
        "next_occurrence_start": s(next_occ.get("start")),
        "next_occurrence_due": s(next_occ.get("due")),
        "assignees": json.dumps(item.get("assignees", []), separators=(",", ":")),
        "reminders": json.dumps(item.get("reminders", []), separators=(",", ":")),
    }


def fetch_schedules(headers, status_filter=None):
    all_items = []
    page_token = None

    while True:
        params = {"page_size": PAGE_SIZE}
        if page_token:
            params["page_token"] = page_token
        if status_filter:
            params["status"] = status_filter

        resp = requests.get(
            f"{BASE_URL}/schedules/v1/schedule_items",
            headers=headers,
            params=params,
            timeout=30,
        )

        if resp.status_code != 200:
            print(f"Error fetching schedules: HTTP {resp.status_code}")
            print(resp.text[:500])
            sys.exit(1)

        data = resp.json()
        items = data.get("items", [])
        all_items.extend(items)

        total = data.get("total", len(all_items))
        print(f"  Fetched {len(all_items):,} / {total:,} schedule items...", end="\r")

        page_token = data.get("next_page_token")
        if not page_token:
            break

    print(f"\n  Total: {len(all_items):,} schedule items")
    return all_items


def write_csv(rows, filename):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved to {filename}")


def main():
    args = parse_args()

    if not TOKEN:
        print(
            "Error: TOKEN not set.\n"
            "Set your API token in the TOKEN variable at the top of the script."
        )
        sys.exit(1)

    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {TOKEN}",
    }

    status_filter = args.status if args.status else None
    filter_label = ", ".join(status_filter) if status_filter else "ALL"

    print(f"\nExporting schedule items (status: {filter_label})...")

    items = fetch_schedules(headers, status_filter)

    if not items:
        print("No schedule items found.")
        return

    rows = [parse_schedule_item(item) for item in items]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"schedules_export_{timestamp}.csv"

    write_csv(rows, filename)
    print(f"\nDone! {len(rows):,} schedule items exported to {filename}")


if __name__ == "__main__":
    main()
