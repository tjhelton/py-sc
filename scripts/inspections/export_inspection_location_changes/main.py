import asyncio
import csv
import os
from datetime import datetime
from typing import Dict, List

import aiohttp
import pandas as pd
from tqdm.asyncio import tqdm

TOKEN = ""  # Set your SafetyCulture API token here
BASE_URL = "https://api.safetyculture.io"

# Concurrency
SEMAPHORE_VALUE = 12  # Max concurrent inspections

# Pagination
PAGE_SIZE = 10
MAX_PAGES_PER_INSPECTION = 100

# Retry
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


def get_timestamped_csv_filename() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"location_changes_{timestamp}.csv"


def extract_location_changes(results: List[Dict], audit_id: str) -> List[Dict]:
    """
    Extract location changes from inspection revision history.

    Filters for:
    - field_type == "address"
    - Excludes initial responses (old_response == "N/A - Initial Response")
    - Only includes actual changes (old != new)
    """
    changes = []

    for result in results:
        result_changes = result.get("changes", [])

        for change in result_changes:
            # Filter 1: Must be address field
            if change.get("field_type") != "address":
                continue

            old_response = change.get("old_response", {})
            new_response = change.get("new_response", {})

            old_text = old_response.get("location_text", "")
            new_text = new_response.get("location_text", "")

            # Filter 2: Exclude initial responses
            if old_text == "N/A - Initial Response":
                continue

            # Filter 3: Only include actual changes
            if old_text == new_text:
                continue

            # Transform to output format
            changes.append(
                {
                    "audit_id": audit_id,
                    "user_id": result.get("author", ""),
                    "user_name": result.get("author_name", ""),
                    "old_location_text": old_text,
                    "new_location_text": new_text,
                    "timestamp": result.get("modified_at", ""),
                    "revision_id": result.get("revision_id", ""),
                }
            )

    return changes


class InspectionLocationChangeExporter:

    def __init__(self):
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {TOKEN}",
        }
        self.session = None
        self.semaphore = None
        self.csv_file_handle = None
        self.csv_writer = None

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=100, limit_per_host=50, ttl_dns_cache=300, use_dns_cache=True
        )
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        self.session = aiohttp.ClientSession(
            headers=self.headers, connector=connector, timeout=timeout
        )
        self.semaphore = asyncio.Semaphore(SEMAPHORE_VALUE)

        csv_filename = get_timestamped_csv_filename()
        self.csv_file_handle = open(csv_filename, "w", newline="", encoding="utf-8")
        self.csv_writer = csv.DictWriter(
            self.csv_file_handle,
            fieldnames=[
                "audit_id",
                "user_id",
                "user_name",
                "old_location_text",
                "new_location_text",
                "timestamp",
                "revision_id",
            ],
        )
        self.csv_writer.writeheader()
        self.csv_file_handle.flush()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.csv_file_handle:
            self.csv_file_handle.close()
        if self.session:
            await self.session.close()

    def _write_changes_to_csv(self, changes: List[Dict]):
        """Write location changes to CSV immediately (streaming)"""
        for change in changes:
            self.csv_writer.writerow(change)
        self.csv_file_handle.flush()

    async def fetch_history_page(
        self, audit_id: str, offset: int, limit: int
    ) -> Dict[str, any]:
        """
        Fetch a single page of inspection revision history.

        Args:
            audit_id: Inspection ID
            offset: Pagination offset
            limit: Results per page

        Returns:
            Dict with success status and results
        """
        url = f"{BASE_URL}/inspections/history/{audit_id}/revisions"
        params = {"offset": offset, "limit": limit}

        for attempt in range(MAX_RETRIES):
            try:
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        return {
                            "success": True,
                            "results": response_data.get("results", []),
                            "results_count": response_data.get("results_count", 0),
                        }

                    if (
                        response.status in RETRY_STATUS_CODES
                        and attempt < MAX_RETRIES - 1
                    ):
                        delay = RETRY_BASE_DELAY * (2**attempt)
                        await asyncio.sleep(delay)
                        continue

                    error_text = await response.text()
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {error_text[:200]}",
                        "results": [],
                    }

            except (aiohttp.ClientError, asyncio.TimeoutError) as error:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2**attempt)
                    await asyncio.sleep(delay)
                    continue

                return {
                    "success": False,
                    "error": f"{type(error).__name__}: {str(error)}",
                    "results": [],
                }

        return {
            "success": False,
            "error": "Max retries exceeded",
            "results": [],
        }

    async def fetch_inspection_history_all_pages(self, audit_id: str) -> List[Dict]:
        """
        Fetch all pages of inspection history in parallel.

        Strategy:
        1. Fetch first page to check if more pages exist
        2. If more pages exist, fetch remaining pages in parallel
        3. Combine all results and return
        """
        # Step 1: Fetch first page
        first_page = await self.fetch_history_page(audit_id, offset=0, limit=PAGE_SIZE)

        if not first_page["success"]:
            return []

        all_results = first_page["results"]

        # Step 2: Check if more pages exist
        # If we got a full page (10 results), there might be more
        if len(all_results) < PAGE_SIZE:
            # No more pages, we got everything
            return all_results

        # Step 3: Fetch remaining pages in parallel
        # Create tasks for up to MAX_PAGES_PER_INSPECTION pages
        page_tasks = []
        for page_num in range(1, MAX_PAGES_PER_INSPECTION):
            offset = page_num * PAGE_SIZE
            page_tasks.append(
                self.fetch_history_page(audit_id, offset=offset, limit=PAGE_SIZE)
            )

        # Fetch all pages concurrently
        remaining_pages = await asyncio.gather(*page_tasks)

        # Step 4: Combine results, stop when empty page found
        for page_result in remaining_pages:
            if not page_result["success"]:
                # Log warning but continue with available data
                continue

            page_revisions = page_result["results"]
            if not page_revisions:
                # Empty page means we've reached the end
                break

            all_results.extend(page_revisions)

        return all_results

    async def process_single_inspection(
        self, audit_id: str, progress_bar
    ) -> Dict[str, any]:
        """
        Process a single inspection: fetch history, filter, write to CSV.

        Args:
            audit_id: Inspection ID
            progress_bar: tqdm progress bar for updates

        Returns:
            Dict with processing results
        """
        async with self.semaphore:
            # Fetch all history pages
            all_results = await self.fetch_inspection_history_all_pages(audit_id)

            if not all_results:
                log_msg = f"⚠️  {audit_id}: No history found or error fetching"
                if progress_bar:
                    progress_bar.write(log_msg)
                    progress_bar.update(1)
                return {"audit_id": audit_id, "changes_found": 0, "status": "NO_DATA"}

            # Filter for location changes
            location_changes = extract_location_changes(all_results, audit_id)

            # Write to CSV immediately
            if location_changes:
                self._write_changes_to_csv(location_changes)

            # Log progress
            if location_changes:
                log_msg = (
                    f"✅ {audit_id}: Found {len(location_changes)} location changes"
                )
            else:
                log_msg = f"📝 {audit_id}: No location changes found"

            if progress_bar:
                progress_bar.write(log_msg)
                progress_bar.update(1)

            return {
                "audit_id": audit_id,
                "changes_found": len(location_changes),
                "status": "SUCCESS",
            }

    async def export_all_inspections(self, audit_ids: List[str]) -> Dict:
        """
        Export location changes for all inspections.

        Args:
            audit_ids: List of inspection IDs

        Returns:
            Dict with summary statistics
        """
        print(
            f"\n🚀 Starting location changes export for {len(audit_ids)} inspections..."
        )
        print(f"⚡ Concurrency: {SEMAPHORE_VALUE} parallel inspections")
        print(f"📊 Output file: {self.csv_file_handle.name}\n")

        stats = {"total": len(audit_ids), "processed": 0, "total_changes": 0}
        start_time = asyncio.get_event_loop().time()

        with tqdm(
            total=len(audit_ids), desc="Processing inspections", unit="inspection"
        ) as pbar:
            tasks = [
                self.process_single_inspection(audit_id, pbar) for audit_id in audit_ids
            ]
            results = await asyncio.gather(*tasks)

        for result in results:
            stats["processed"] += 1
            stats["total_changes"] += result.get("changes_found", 0)

        end_time = asyncio.get_event_loop().time()
        stats["total_time_seconds"] = round(end_time - start_time, 2)

        return stats


def load_input_csv() -> List[str]:
    """
    Load audit IDs from input.csv.

    Returns:
        List of audit_id strings
    """
    input_file = "input.csv"

    if not os.path.exists(input_file):
        print(f"❌ Error: {input_file} not found")
        print("Please create input.csv with column: audit_id")
        return []

    try:
        df = pd.read_csv(input_file)

        if "audit_id" not in df.columns:
            print("❌ Error: input.csv missing required column: audit_id")
            print("Required column: audit_id")
            return []

        df = df.dropna(subset=["audit_id"])
        df["audit_id"] = df["audit_id"].astype(str)

        audit_ids = df["audit_id"].tolist()

        if not audit_ids:
            print("❌ Error: No valid audit_ids found in input.csv")
            return []

        print(f"📋 Loaded {len(audit_ids)} inspections from {input_file}")
        return audit_ids

    except Exception as error:
        print(f"❌ Error reading {input_file}: {error}")
        return []


async def main():
    print("=" * 80)
    print("🚀 SafetyCulture Inspection Location Changes Exporter")
    print("=" * 80)

    if not TOKEN:
        print("\n❌ Error: TOKEN not set in script")
        print("Please set your API token in the TOKEN variable at the top of main.py")
        return 1

    audit_ids = load_input_csv()
    if not audit_ids:
        return 1

    print("\n" + "=" * 80)

    async with InspectionLocationChangeExporter() as exporter:
        stats = await exporter.export_all_inspections(audit_ids)

    print("\n" + "=" * 80)
    print("📊 EXPORT SUMMARY")
    print("=" * 80)
    print(f"📝 Total Inspections: {stats['total']}")
    print(f"✅ Processed: {stats['processed']}")
    print(f"📍 Total Location Changes: {stats['total_changes']}")

    total_time = stats.get("total_time_seconds", 0)
    minutes = int(total_time // 60)
    seconds = int(total_time % 60)
    print(f"⏱️  Total Time: {minutes}m {seconds}s")

    csv_filename = get_timestamped_csv_filename()
    print(f"\n💾 Results saved to: {os.path.abspath(csv_filename)}")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    asyncio.run(main())
