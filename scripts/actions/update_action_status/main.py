import asyncio
import csv
import os
import time
from datetime import datetime

import aiohttp
from rich.console import Console
from rich.live import Live
from rich.table import Table

TOKEN = ""  # Set your SafetyCulture API token here
BASE_URL = "https://api.safetyculture.io"

# Rate limiting configuration
MAX_REQUESTS_PER_SECOND = 400
SEMAPHORE_VALUE = 100  # Max concurrent connections

# Batch processing configuration
BATCH_SIZE = 5000  # Process records in chunks to reduce memory usage

# CSV buffering configuration
CSV_BUFFER_SIZE = 100  # Flush CSV every N records

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}

# Valid action status IDs for reference
ACTION_STATUSES = {
    "17e793a1-26a3-4ecd-99ca-f38ecc6eaa2e": "To do",
    "20ce0cb1-387a-47d4-8c34-bc6fd3be0e27": "In progress",
    "7223d809-553e-4714-a038-62dc98f3fbf3": "Complete",
    "06308884-41c2-4ee0-9da7-5676647d3d75": "Can't do",
}

console = Console()


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter for high-throughput async requests.
    Supports bursts up to bucket capacity while maintaining average rate.
    """

    def __init__(self, requests_per_second, burst_size=None):
        self.rate = float(requests_per_second)
        self.burst_size = burst_size or requests_per_second
        self.tokens = float(self.burst_size)
        self.last_refill = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self):
        while True:
            async with self._lock:
                now = time.time()
                elapsed = now - self.last_refill
                self.tokens = min(self.burst_size, self.tokens + elapsed * self.rate)
                self.last_refill = now

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return

                wait_time = (1.0 - self.tokens) / self.rate

            await asyncio.sleep(wait_time)


class ActionStatusUpdater:

    def __init__(self):
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {TOKEN}",
        }
        self.session = None
        self.semaphore = None
        self.rate_limiter = None
        self.csv_file_handle = None
        self.csv_writer = None
        self.csv_buffer = []
        self.buffer_lock = asyncio.Lock()

        # Live stats
        self.success_count = 0
        self.error_count = 0
        self.total_count = 0
        self.start_time = None
        self.recent_logs = []
        self.max_recent_logs = 20

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=200, limit_per_host=100, ttl_dns_cache=300, use_dns_cache=True
        )
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        self.session = aiohttp.ClientSession(
            headers=self.headers, connector=connector, timeout=timeout
        )
        self.semaphore = asyncio.Semaphore(SEMAPHORE_VALUE)
        self.rate_limiter = TokenBucketRateLimiter(MAX_REQUESTS_PER_SECOND)

        csv_filename = "output.csv"
        fieldnames = [
            "action_id",
            "status_id",
            "status_name",
            "result",
            "error_message",
            "timestamp",
        ]

        if os.path.exists(csv_filename):
            self.csv_file_handle = open(csv_filename, "a", newline="", encoding="utf-8")
            self.csv_writer = csv.DictWriter(
                self.csv_file_handle, fieldnames=fieldnames
            )
        else:
            self.csv_file_handle = open(csv_filename, "w", newline="", encoding="utf-8")
            self.csv_writer = csv.DictWriter(
                self.csv_file_handle, fieldnames=fieldnames
            )
            self.csv_writer.writeheader()

        self.csv_file_handle.flush()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.csv_buffer:
            async with self.buffer_lock:
                await self._flush_csv_buffer()
        if self.csv_file_handle:
            self.csv_file_handle.close()
        if self.session:
            await self.session.close()

    async def _write_result_buffered(self, result):
        async with self.buffer_lock:
            self.csv_buffer.append(result)
            if len(self.csv_buffer) >= CSV_BUFFER_SIZE:
                await self._flush_csv_buffer()

    async def _flush_csv_buffer(self):
        if not self.csv_buffer:
            return
        for result in self.csv_buffer:
            self.csv_writer.writerow(result)
        self.csv_file_handle.flush()
        self.csv_buffer.clear()

    def _add_log(self, message):
        self.recent_logs.append(message)
        if len(self.recent_logs) > self.max_recent_logs:
            self.recent_logs.pop(0)

    def _build_display(self):
        elapsed = time.time() - self.start_time if self.start_time else 0
        processed = self.success_count + self.error_count
        rate = processed / elapsed if elapsed > 0 else 0

        # Stats table
        stats = Table(title="Action Status Updater", expand=True)
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

        if rate > 0 and processed < self.total_count:
            remaining = (self.total_count - processed) / rate
            eta_min = int(remaining // 60)
            eta_sec = int(remaining % 60)
            stats.add_row("ETA", f"{eta_min}m {eta_sec}s")

        # Recent activity log
        log_table = Table(title="Recent Activity", expand=True)
        log_table.add_column("Log", style="white", no_wrap=False)
        for entry in self.recent_logs[-self.max_recent_logs :]:
            log_table.add_row(entry)

        # Combine into a group
        from rich.console import Group

        return Group(stats, log_table)

    async def update_single_action(self, action_id, status_id, live):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_name = ACTION_STATUSES.get(status_id, "Unknown")

        async with self.semaphore:
            await self.rate_limiter.acquire()

            url = f"{BASE_URL}/tasks/v1/actions/{action_id}/status"
            body = {"status_id": status_id}

            for attempt in range(MAX_RETRIES):
                try:
                    async with self.session.put(url, json=body) as response:
                        if response.status == 200:
                            result = {
                                "action_id": action_id,
                                "status_id": status_id,
                                "status_name": status_name,
                                "result": "SUCCESS",
                                "error_message": "",
                                "timestamp": timestamp,
                            }
                            self.success_count += 1
                            self._add_log(
                                f"[green]OK[/green]  {action_id} -> {status_name}"
                            )
                            live.update(self._build_display())
                            await self._write_result_buffered(result)
                            return result

                        if response.status == 429 and attempt < MAX_RETRIES - 1:
                            retry_after = response.headers.get("Retry-After")
                            if retry_after and retry_after.isdigit():
                                wait_time = max(1, min(int(retry_after), 300))
                            else:
                                wait_time = RETRY_BASE_DELAY * (2**attempt)
                            self._add_log(
                                f"[yellow]RATE LIMITED[/yellow]  {action_id} "
                                f"- retry in {wait_time}s"
                            )
                            live.update(self._build_display())
                            await asyncio.sleep(wait_time)
                            continue

                        if (
                            response.status in RETRY_STATUS_CODES
                            and attempt < MAX_RETRIES - 1
                        ):
                            delay = RETRY_BASE_DELAY * (2**attempt)
                            await asyncio.sleep(delay)
                            continue

                        error_text = await response.text()
                        result = {
                            "action_id": action_id,
                            "status_id": status_id,
                            "status_name": status_name,
                            "result": "ERROR",
                            "error_message": f"HTTP {response.status}: {error_text[:200]}",
                            "timestamp": timestamp,
                        }
                        self.error_count += 1
                        self._add_log(
                            f"[red]ERR[/red]  {action_id} - HTTP {response.status}"
                        )
                        live.update(self._build_display())
                        await self._write_result_buffered(result)
                        return result

                except (aiohttp.ClientError, asyncio.TimeoutError) as error:
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_BASE_DELAY * (2**attempt)
                        await asyncio.sleep(delay)
                        continue

                    result = {
                        "action_id": action_id,
                        "status_id": status_id,
                        "status_name": status_name,
                        "result": "ERROR",
                        "error_message": f"{type(error).__name__}: {str(error)}",
                        "timestamp": timestamp,
                    }
                    self.error_count += 1
                    self._add_log(
                        f"[red]ERR[/red]  {action_id} - {type(error).__name__}"
                    )
                    live.update(self._build_display())
                    await self._write_result_buffered(result)
                    return result

            # Max retries exceeded
            result = {
                "action_id": action_id,
                "status_id": status_id,
                "status_name": status_name,
                "result": "ERROR",
                "error_message": "Max retries exceeded",
                "timestamp": timestamp,
            }
            self.error_count += 1
            self._add_log(f"[red]ERR[/red]  {action_id} - Max retries exceeded")
            live.update(self._build_display())
            await self._write_result_buffered(result)
            return result

    async def update_all_actions(self, records):
        self.total_count = len(records)
        self.start_time = time.time()

        console.print(f"\nStarting bulk update for {len(records)} actions...")
        console.print(f"Rate limit: {MAX_REQUESTS_PER_SECOND} req/s")
        console.print(f"Concurrent connections: {SEMAPHORE_VALUE}")
        console.print("Output log: output.csv\n")

        total_batches = (len(records) + BATCH_SIZE - 1) // BATCH_SIZE

        with Live(self._build_display(), console=console, refresh_per_second=4) as live:
            for batch_num in range(total_batches):
                start_idx = batch_num * BATCH_SIZE
                end_idx = min(start_idx + BATCH_SIZE, len(records))
                batch = records[start_idx:end_idx]

                self._add_log(
                    f"[cyan]BATCH {batch_num + 1}/{total_batches}[/cyan] "
                    f"- Processing {len(batch)} records"
                )
                live.update(self._build_display())

                tasks = [
                    self.update_single_action(rec["action_id"], rec["status_id"], live)
                    for rec in batch
                ]
                await asyncio.gather(*tasks)

                self._add_log(
                    f"[cyan]BATCH {batch_num + 1}/{total_batches} COMPLETE[/cyan]"
                )
                live.update(self._build_display())

        total_time = time.time() - self.start_time
        return {
            "success": self.success_count,
            "error": self.error_count,
            "total": self.total_count,
            "total_time_seconds": round(total_time, 2),
        }


def load_completed_ids(csv_path="output.csv"):
    if not os.path.exists(csv_path):
        return set()
    try:
        completed = set()
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                completed.add(row["action_id"])
        if completed:
            console.print(f"Resuming: found {len(completed)} already-processed IDs")
        return completed
    except Exception as error:
        console.print(f"[yellow]Warning: Could not read {csv_path}: {error}[/yellow]")
        return set()


def load_input_csv():
    input_file = "input.csv"

    if not os.path.exists(input_file):
        console.print(f"[red]Error: {input_file} not found[/red]")
        console.print("Create input.csv with columns: action_id, status_id")
        return []

    try:
        records = []
        with open(input_file, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            if (
                "action_id" not in reader.fieldnames
                or "status_id" not in reader.fieldnames
            ):
                console.print(
                    "[red]Error: input.csv must have columns: action_id, status_id[/red]"
                )
                return []

            for row in reader:
                action_id = row["action_id"].strip()
                status_id = row["status_id"].strip()
                if action_id and status_id:
                    records.append({"action_id": action_id, "status_id": status_id})

        if not records:
            console.print("[red]Error: No valid records found in input.csv[/red]")
            return []

        console.print(f"Loaded {len(records)} records from {input_file}")
        return records

    except Exception as error:
        console.print(f"[red]Error reading {input_file}: {error}[/red]")
        return []


async def main():
    console.rule("SafetyCulture Action Status Updater")

    if not TOKEN:
        console.print(
            "\n[red]Error: TOKEN not set.[/red]\n"
            "Set your API token in the TOKEN variable at the top of main.py"
        )
        return 1

    # Show valid statuses
    console.print("\n[bold]Valid action statuses:[/bold]")
    for sid, name in ACTION_STATUSES.items():
        console.print(f"  {name:<15} {sid}")
    console.print()

    records = load_input_csv()
    if not records:
        return 1

    # Validate status IDs
    invalid = [r for r in records if r["status_id"] not in ACTION_STATUSES]
    if invalid:
        console.print(
            f"[yellow]Warning: {len(invalid)} records have unrecognised status_id values. "
            f"They will be sent as-is.[/yellow]"
        )

    # Resume support
    completed_ids = load_completed_ids()
    if completed_ids:
        original_count = len(records)
        records = [r for r in records if r["action_id"] not in completed_ids]
        skipped = original_count - len(records)
        console.print(f"Skipping {skipped} already-processed actions")
        console.print(f"Remaining: {len(records)}")
        if not records:
            console.print("\n[green]All actions already processed![/green]")
            return 0

    async with ActionStatusUpdater() as updater:
        results = await updater.update_all_actions(records)

    console.print()
    console.rule("Summary")
    console.print(f"  [green]Success:[/green]  {results['success']}")
    console.print(f"  [red]Errors:[/red]   {results['error']}")
    console.print(f"  Total:    {results['total']}")

    if results["total"] > 0:
        pct = results["success"] / results["total"] * 100
        console.print(f"  Rate:     {pct:.1f}%")

    total_time = results.get("total_time_seconds", 0)
    minutes = int(total_time // 60)
    seconds = int(total_time % 60)
    console.print(f"  Time:     {minutes}m {seconds}s")
    console.print(f"\n  Results:  {os.path.abspath('output.csv')}")
    console.rule()

    return 0


if __name__ == "__main__":
    asyncio.run(main())
