"""
SafetyCulture Schedule Items - Export and Update

Workflow:
  1. Downloads all schedule items and writes them to schedules_export.csv
  2. Opens the file for editing (or prompts the user to edit it manually)
  3. After the user confirms, reads the updated CSV and sends PUT requests
     for any rows that changed.

Editable columns in the CSV:
  description, recurrence, start_time_hour, start_time_minute, duration,
  from_date, to_date, can_late_submit, must_complete, location_id, asset_id,
  document_id, document_type, assignees (JSON array), reminders (JSON array)

Read-only columns (changes are ignored):
  id, status, creator_name, created_at, modified_at,
  next_occurrence_start, next_occurrence_due
"""

import argparse
import asyncio
import csv
import json
import os
import subprocess
import sys
import time

import aiohttp
import requests
from rich.console import Console, Group
from rich.live import Live
from rich.table import Table

TOKEN = ""  # Set your SafetyCulture API token here

BASE_URL = "https://api.safetyculture.io"
EXPORT_FILE = "schedules_export.csv"
PAGE_SIZE = 100

MAX_CONCURRENT = 20
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}

console = Console()

VALID_STATUSES = [
    "ACTIVE",
    "PAUSED",
    "NO_TEMPLATE",
    "NO_ASSIGNEE",
    "FINISHED",
    "SUBSCRIPTION_INACTIVE",
    "NO_SITE",
]

# ---------------------------------------------------------------------------
# CSV columns
# ---------------------------------------------------------------------------

READ_ONLY_COLS = [
    "id",
    "status",
    "creator_name",
    "created_at",
    "modified_at",
    "next_occurrence_start",
    "next_occurrence_due",
]

EDITABLE_COLS = [
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
    "assignees",  # JSON array: [{"id": "...", "type": "USER"}]
    "reminders",  # JSON array: [{"event": "START", "duration": "PT5M"}]
]

CSV_HEADERS = READ_ONLY_COLS + EDITABLE_COLS


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------


def parse_schedule_item(item):
    creator = item.get("creator") or {}
    start_time = item.get("start_time") or {}
    doc = item.get("document") or {}
    next_occ = item.get("next_occurrence") or {}

    # Convert everything to str so the snapshot matches CSV roundtrip types.
    # API returns ints for start_time and None for unset fields; CSV always
    # reads back strings / empty strings.
    def s(val):
        if val is None:
            return ""
        return str(val)

    return {
        "id": s(item.get("id")),
        "status": s(item.get("status")),
        "creator_name": s(creator.get("name")),
        "created_at": s(item.get("created_at")),
        "modified_at": s(item.get("modified_at")),
        "next_occurrence_start": s(next_occ.get("start")),
        "next_occurrence_due": s(next_occ.get("due")),
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
        "assignees": json.dumps(item.get("assignees", []), separators=(",", ":")),
        "reminders": json.dumps(item.get("reminders", []), separators=(",", ":")),
    }


def export_all_schedules(headers, statuses=None):
    if statuses:
        console.print(
            f"\n[bold cyan]Step 1: Exporting schedule items "
            f"(status filter: {', '.join(statuses)})...[/bold cyan]"
        )
    else:
        console.print("\n[bold cyan]Step 1: Exporting schedule items...[/bold cyan]")

    all_items = []
    page_token = None

    while True:
        params = {"page_size": PAGE_SIZE}
        if statuses:
            params["statuses"] = statuses
        if page_token:
            params["page_token"] = page_token

        resp = requests.get(
            f"{BASE_URL}/schedules/v1/schedule_items",
            headers=headers,
            params=params,
            timeout=30,
        )

        if resp.status_code != 200:
            console.print(
                f"[red]Error fetching schedules: HTTP {resp.status_code}[/red]"
            )
            console.print(resp.text[:500])
            sys.exit(1)

        data = resp.json()
        items = data.get("items", [])
        all_items.extend(items)

        total = data.get("total", len(all_items))
        console.print(
            f"  Fetched {len(all_items):,} / {total:,} schedule items...", end="\r"
        )

        page_token = data.get("next_page_token")
        if not page_token:
            break

    console.print(f"\n  Total fetched: {len(all_items):,} schedule items")

    rows = [parse_schedule_item(item) for item in all_items]

    with open(EXPORT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    console.print(f"  Exported to [bold]{EXPORT_FILE}[/bold]")
    return {row["id"]: row for row in rows}


# ---------------------------------------------------------------------------
# Diff helpers
# ---------------------------------------------------------------------------


def load_updated_csv():
    rows = {}
    with open(EXPORT_FILE, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows[row["id"]] = row
    return rows


def detect_changes(original, updated):
    changes = []
    for item_id, new_row in updated.items():
        if item_id not in original:
            continue
        orig_row = original[item_id]
        changed_cols = {
            col for col in EDITABLE_COLS if new_row.get(col) != orig_row.get(col)
        }
        if changed_cols:
            changes.append((item_id, new_row, changed_cols))
    return changes


# ---------------------------------------------------------------------------
# Build update payload
# ---------------------------------------------------------------------------


def build_update_body(row):
    """Convert a CSV row into the PUT request body."""
    body = {}

    if row.get("description") is not None:
        body["description"] = row["description"]

    if row.get("recurrence"):
        body["recurrence"] = row["recurrence"]

    hour = row.get("start_time_hour", "")
    minute = row.get("start_time_minute", "")
    if hour != "" and minute != "":
        try:
            body["start_time"] = {"hour": int(hour), "minute": int(minute)}
        except ValueError:
            pass

    if row.get("duration"):
        body["duration"] = row["duration"]

    if row.get("timezone"):
        body["timezone"] = row["timezone"]

    if row.get("from_date"):
        body["from_date"] = row["from_date"]

    if row.get("to_date"):
        body["to_date"] = row["to_date"]

    can_late = row.get("can_late_submit", "").lower()
    if can_late in ("true", "false"):
        body["can_late_submit"] = can_late == "true"

    if row.get("must_complete"):
        body["must_complete"] = row["must_complete"]

    sba = row.get("site_based_assignment_enabled", "").lower()
    if sba in ("true", "false"):
        body["site_based_assignment_enabled"] = sba == "true"

    if row.get("location_id"):
        body["location_id"] = row["location_id"]

    if row.get("asset_id"):
        body["asset_id"] = row["asset_id"]

    doc_id = row.get("document_id", "")
    doc_type = row.get("document_type", "")
    if doc_id:
        body["document"] = {"id": doc_id, "type": doc_type or "TEMPLATE"}

    assignees_raw = row.get("assignees", "[]")
    try:
        assignees = json.loads(assignees_raw) if assignees_raw else []
        if isinstance(assignees, list):
            body["assignees"] = assignees
    except json.JSONDecodeError:
        console.print(
            f"[yellow]Warning: could not parse assignees JSON for {row.get('id')}[/yellow]"
        )

    reminders_raw = row.get("reminders", "[]")
    try:
        reminders = json.loads(reminders_raw) if reminders_raw else []
        if isinstance(reminders, list):
            body["reminders"] = reminders
    except json.JSONDecodeError:
        console.print(
            f"[yellow]Warning: could not parse reminders JSON for {row.get('id')}[/yellow]"
        )

    return body


# ---------------------------------------------------------------------------
# Async updater
# ---------------------------------------------------------------------------


class ScheduleUpdater:
    def __init__(self, auth_headers):
        self.headers = auth_headers
        self.session = None
        self.semaphore = None
        self.success_count = 0
        self.error_count = 0
        self.total_count = 0
        self.start_time = None
        self.recent_logs = []

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        self.session = aiohttp.ClientSession(
            headers=self.headers, connector=connector, timeout=timeout
        )
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        return self

    async def __aexit__(self, *_):
        if self.session:
            await self.session.close()

    def _add_log(self, msg):
        self.recent_logs.append(msg)
        if len(self.recent_logs) > 15:
            self.recent_logs.pop(0)

    def _build_display(self):
        elapsed = time.time() - self.start_time if self.start_time else 0
        processed = self.success_count + self.error_count
        rate = processed / elapsed if elapsed > 0 else 0

        stats = Table(title="Schedule Updater", expand=True)
        stats.add_column("Metric", style="cyan", width=20)
        stats.add_column("Value", style="white", width=30)
        stats.add_row("Processed", f"{processed} / {self.total_count}")
        stats.add_row("Success", f"[green]{self.success_count}[/green]")
        stats.add_row("Errors", f"[red]{self.error_count}[/red]")
        if self.total_count > 0:
            pct = processed / self.total_count * 100
            stats.add_row("Progress", f"{pct:.1f}%")
        stats.add_row("Rate", f"{rate:.1f} req/s")
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        stats.add_row("Elapsed", f"{minutes}m {seconds}s")

        log_table = Table(title="Recent Activity", expand=True)
        log_table.add_column("Log", style="white", no_wrap=False)
        for entry in self.recent_logs:
            log_table.add_row(entry)

        return Group(stats, log_table)

    async def update_one(self, item_id, row, changed_cols, live):
        url = f"{BASE_URL}/schedules/v1/schedule_items/{item_id}"
        body = build_update_body(row)

        async with self.semaphore:
            for attempt in range(MAX_RETRIES):
                try:
                    async with self.session.put(url, json=body) as resp:
                        if resp.status == 200:
                            self.success_count += 1
                            self._add_log(
                                f"[green]OK[/green]  {item_id} "
                                f"({', '.join(sorted(changed_cols))})"
                            )
                            live.update(self._build_display())
                            return

                        if resp.status == 429 and attempt < MAX_RETRIES - 1:
                            retry_after = resp.headers.get("Retry-After", "")
                            wait = (
                                int(retry_after)
                                if retry_after.isdigit()
                                else RETRY_BASE_DELAY * (2**attempt)
                            )
                            self._add_log(
                                f"[yellow]RATE LIMITED[/yellow] {item_id} "
                                f"- retry in {wait}s"
                            )
                            live.update(self._build_display())
                            await asyncio.sleep(wait)
                            continue

                        if (
                            resp.status in RETRY_STATUS_CODES
                            and attempt < MAX_RETRIES - 1
                        ):
                            await asyncio.sleep(RETRY_BASE_DELAY * (2**attempt))
                            continue

                        error_text = await resp.text()
                        self.error_count += 1
                        self._add_log(
                            f"[red]ERR[/red]  {item_id} "
                            f"- HTTP {resp.status}: {error_text[:120]}"
                        )
                        live.update(self._build_display())
                        return

                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_BASE_DELAY * (2**attempt))
                        continue
                    self.error_count += 1
                    self._add_log(
                        f"[red]ERR[/red]  {item_id} - {type(exc).__name__}: {exc}"
                    )
                    live.update(self._build_display())
                    return

    async def update_all(self, changes):
        self.total_count = len(changes)
        self.start_time = time.time()

        with Live(self._build_display(), console=console, refresh_per_second=4) as live:
            tasks = [
                self.update_one(item_id, row, changed_cols, live)
                for item_id, row, changed_cols in changes
            ]
            await asyncio.gather(*tasks)

        return self.success_count, self.error_count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export, edit, and update SafetyCulture schedule items."
    )
    parser.add_argument(
        "--status",
        nargs="+",
        choices=[s.lower() for s in VALID_STATUSES],
        metavar="STATUS",
        help=(
            "Only export schedule items with these statuses. "
            f"Choices: {', '.join(s.lower() for s in VALID_STATUSES)}"
        ),
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    console.rule("[bold blue]SafetyCulture Schedule Updater[/bold blue]")

    if not TOKEN:
        console.print(
            "\n[red]Error: TOKEN not set.[/red]\n"
            "Set your API token in the TOKEN variable at the top of the script."
        )
        return

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {TOKEN}",
    }

    # --- Step 1: Export ---
    statuses = [s.upper() for s in args.status] if args.status else None
    original = export_all_schedules(headers, statuses=statuses)

    if not original:
        console.print("[yellow]No schedule items found.[/yellow]")
        return

    # --- Step 2: Prompt user to edit ---
    console.print(
        f"\n[bold cyan]Step 2: Edit the CSV[/bold cyan]\n"
        f"  File: [bold]{os.path.abspath(EXPORT_FILE)}[/bold]\n\n"
        f"  [bold]Editable columns:[/bold]"
    )
    for col in EDITABLE_COLS:
        console.print(f"    • {col}")
    console.print(
        f"\n  [dim]Read-only columns (changes are ignored): "
        + ", ".join(READ_ONLY_COLS)
        + "[/dim]\n"
        f"\n  [dim]Note: assignees and reminders must be valid JSON arrays.[/dim]"
    )

    # Try to open the file automatically
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", EXPORT_FILE], check=False)
        elif sys.platform == "win32":
            os.startfile(EXPORT_FILE)
        else:
            subprocess.run(["xdg-open", EXPORT_FILE], check=False)
    except Exception:
        pass

    input("\n  Press [Enter] when you have finished editing the CSV...")

    # --- Step 3: Detect changes ---
    console.print("\n[bold cyan]Step 3: Detecting changes...[/bold cyan]")
    updated = load_updated_csv()
    changes = detect_changes(original, updated)

    if not changes:
        console.print("  [yellow]No changes detected. Exiting.[/yellow]")
        return

    console.print(f"  Found [bold]{len(changes)}[/bold] changed schedule item(s).")

    preview = Table(title="Changes Preview", show_lines=True)
    preview.add_column("ID", style="cyan", no_wrap=True)
    preview.add_column("Changed Fields", style="white")
    for item_id, _, changed_cols in changes[:20]:
        preview.add_row(item_id, ", ".join(sorted(changed_cols)))
    if len(changes) > 20:
        preview.add_row("...", f"({len(changes) - 20} more not shown)")
    console.print(preview)

    confirm = (
        input(f"  Proceed with updating {len(changes)} schedule item(s)? [y/N]: ")
        .strip()
        .lower()
    )
    if confirm not in ("y", "yes"):
        console.print("[yellow]Aborted.[/yellow]")
        return

    # --- Step 4: Update ---
    console.print("\n[bold cyan]Step 4: Updating schedule items...[/bold cyan]\n")
    async with ScheduleUpdater(headers) as updater:
        success, errors = await updater.update_all(changes)

    console.print()
    console.rule("Summary")
    console.print(f"  [green]Success:[/green]  {success}")
    console.print(f"  [red]Errors:[/red]   {errors}")
    console.print(f"  Total:    {len(changes)}")
    console.rule()


if __name__ == "__main__":
    asyncio.run(main())
