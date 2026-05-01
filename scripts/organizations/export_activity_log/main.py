import asyncio
import csv
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

TOKEN = ""  # Set your SafetyCulture API token here

BASE_URL = "https://api.safetyculture.io"
ACTIVITY_LOG_ENDPOINT = f"{BASE_URL}/feed/activity_log_events"
LIMIT = 250  # Maximum allowed by the API
MAX_CONCURRENT_REQUESTS = 20

# Optional date filters (ISO 8601 format, e.g. "2024-01-01T00:00:00.000Z")
# Leave as "" to export all events.
TRIGGERED_AFTER = ""
MODIFIED_AFTER = ""
MODIFIED_BEFORE = ""


class ActivityLogExporter:
    def __init__(
        self,
        triggered_after: str = "",
        modified_after: str = "",
        modified_before: str = "",
    ):
        self.triggered_after = triggered_after
        self.modified_after = modified_after
        self.modified_before = modified_before
        self.headers = {
            "accept": "application/json",
            "authorization": f"Bearer {TOKEN}",
        }
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore: Optional[asyncio.Semaphore] = None

    async def __aenter__(self) -> "ActivityLogExporter":
        connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=30,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        self.session = aiohttp.ClientSession(
            headers=self.headers, connector=connector, timeout=timeout
        )
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.session:
            await self.session.close()

    def _build_params(self, offset: int) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": LIMIT, "offset": offset}
        if self.triggered_after:
            params["triggered_after"] = self.triggered_after
        if self.modified_after:
            params["modified_after"] = self.modified_after
        if self.modified_before:
            params["modified_before"] = self.modified_before
        return params

    async def _fetch_page(self, offset: int) -> Dict[str, Any]:
        params = self._build_params(offset)
        assert self.semaphore and self.session
        async with self.semaphore:
            try:
                async with self.session.get(
                    ACTIVITY_LOG_ENDPOINT, params=params
                ) as response:
                    response.raise_for_status()
                    return await response.json()
            except Exception as e:
                print(f"❌ Error fetching offset {offset}: {e}")
                raise

    async def export(self, output_file: str) -> int:
        print("🚀 Starting activity log export...")
        print(f"💾 Output file: {output_file}")
        if self.triggered_after or self.modified_after or self.modified_before:
            print("🔎 Filters applied:")
            if self.triggered_after:
                print(f"   triggered_after:  {self.triggered_after}")
            if self.modified_after:
                print(f"   modified_after:   {self.modified_after}")
            if self.modified_before:
                print(f"   modified_before:  {self.modified_before}")
        print("=" * 80)

        start_time = time.time()
        offset = 0
        written = 0
        csv_writer = None

        with open(output_file, "w", newline="", encoding="utf-8") as csv_file:
            while True:
                # Fire MAX_CONCURRENT_REQUESTS pages in parallel
                batch_offsets = [
                    offset + i * LIMIT for i in range(MAX_CONCURRENT_REQUESTS)
                ]
                tasks = [self._fetch_page(off) for off in batch_offsets]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                last_nonempty_result: Optional[Dict[str, Any]] = None
                last_nonempty_offset: Optional[int] = None

                for i, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        print(f"❌ Failed at offset {batch_offsets[i]}: {result}")
                        continue
                    page_data: List[Dict[str, Any]] = result.get("data", [])  # type: ignore[union-attr]
                    if not page_data:
                        continue
                    last_nonempty_result = result  # type: ignore[assignment]
                    last_nonempty_offset = batch_offsets[i]
                    if csv_writer is None:
                        fieldnames = list(page_data[0].keys())
                        csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                        csv_writer.writeheader()
                    csv_writer.writerows(page_data)
                    written += len(page_data)

                csv_file.flush()

                elapsed = time.time() - start_time
                rate = written / elapsed if elapsed > 0 else 0
                print(
                    f"📦 Batch at offset {offset:,} | "
                    f"Events so far: {written:,} | "
                    f"Rate: {rate:.1f} events/sec"
                )

                if last_nonempty_result is None:
                    # Entire batch returned empty — we're done
                    break

                has_more = bool(
                    last_nonempty_result.get("metadata", {}).get("next_page_token")
                )
                if not has_more:
                    break

                # Advance past the last page that had data
                offset = last_nonempty_offset + LIMIT  # type: ignore[operator]

        elapsed = time.time() - start_time
        throughput = written / elapsed if elapsed > 0 else 0

        print("=" * 80)
        print("🎉 EXPORT COMPLETE!")
        print("=" * 80)
        print(f"📊 Total Events Exported: {written:,}")
        print(f"⏱️  Total Time: {elapsed:.2f}s ({elapsed / 60:.2f} minutes)")
        print(f"⚡ Throughput: {throughput:.1f} events/sec")
        print(f"💾 Output saved to: {output_file}")
        print("=" * 80)

        return written


def get_output_filename() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"activity_log_{timestamp}.csv"


def prompt_date_filter() -> str:
    print(
        "Do you want to only pull events from a certain date? "
        "If not, leave blank. If so, enter in YYYY-MM-DD format:"
    )
    raw = input("> ").strip()
    if not raw:
        return ""
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d")
        return parsed.strftime("%Y-%m-%dT00:00:00.000Z")
    except ValueError:
        print(f"⚠️  '{raw}' is not a valid YYYY-MM-DD date — exporting all events.")
        return ""


async def main() -> int:
    if not TOKEN:
        print("❌ Error: TOKEN is not set.")
        print(
            "Set your SafetyCulture API token in the TOKEN variable at the top of main.py"
        )
        return 1

    triggered_after = TRIGGERED_AFTER or prompt_date_filter()

    output_file = get_output_filename()

    async with ActivityLogExporter(
        triggered_after=triggered_after,
        modified_after=MODIFIED_AFTER,
        modified_before=MODIFIED_BEFORE,
    ) as exporter:
        count = await exporter.export(output_file)

    return 0 if count >= 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
