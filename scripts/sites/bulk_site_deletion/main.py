import asyncio
import csv
import time
from datetime import datetime
from typing import Dict, List

import aiohttp

TOKEN = ""  # Set your SafetyCulture API token here
BASE_URL = "https://api.safetyculture.io"

MAX_CONCURRENT = 10  # Max concurrent delete requests in flight at once
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class SiteDeletor:
    def __init__(self):
        self.headers = {
            "accept": "application/json",
            "authorization": f"Bearer {TOKEN}",
        }
        self.session = None
        self.semaphore = None
        self.success_count = 0
        self.error_count = 0

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=50, limit_per_host=20, ttl_dns_cache=300, use_dns_cache=True
        )
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        self.session = aiohttp.ClientSession(
            headers=self.headers, connector=connector, timeout=timeout
        )
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def delete_one(self, site_id: str, index: int, total: int) -> Dict:
        params = [("folder_ids", site_id), ("cascade_up", "true")]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        async with self.semaphore:
            for attempt in range(MAX_RETRIES):
                try:
                    async with self.session.delete(
                        f"{BASE_URL}/directory/v1/folders",
                        params=params,
                    ) as response:
                        if response.status == 200:
                            self.success_count += 1
                            print(f"  ✓ [{index}/{total}] {site_id}")
                            return {
                                "site_id": site_id,
                                "status": "deleted",
                                "error": "",
                                "timestamp": timestamp,
                            }

                        if response.status == 429 and attempt < MAX_RETRIES - 1:
                            retry_after = response.headers.get("Retry-After")
                            wait_time = (
                                int(retry_after)
                                if retry_after and retry_after.isdigit()
                                else RETRY_BASE_DELAY * (2**attempt)
                            )
                            await asyncio.sleep(max(1, min(wait_time, 300)))
                            continue

                        if (
                            response.status in RETRY_STATUS_CODES
                            and attempt < MAX_RETRIES - 1
                        ):
                            await asyncio.sleep(RETRY_BASE_DELAY * (2**attempt))
                            continue

                        error_text = await response.text()
                        error = f"HTTP {response.status}: {error_text[:200]}"
                        self.error_count += 1
                        print(f"  ✗ [{index}/{total}] {site_id} — {error}")
                        return {
                            "site_id": site_id,
                            "status": "error",
                            "error": error,
                            "timestamp": timestamp,
                        }

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_BASE_DELAY * (2**attempt))
                        continue
                    error = f"{type(e).__name__}: {str(e)}"
                    self.error_count += 1
                    print(f"  ✗ [{index}/{total}] {site_id} — {error}")
                    return {
                        "site_id": site_id,
                        "status": "error",
                        "error": error,
                        "timestamp": timestamp,
                    }

        error = "Max retries exceeded"
        self.error_count += 1
        print(f"  ✗ [{index}/{total}] {site_id} — {error}")
        return {
            "site_id": site_id,
            "status": "error",
            "error": error,
            "timestamp": timestamp,
        }

    async def delete_all(self, site_ids: List[str]) -> List[Dict]:
        total = len(site_ids)
        print(
            f"🗑️  Deleting {total} sites (cascade_up=true, concurrency={MAX_CONCURRENT})...\n"
        )

        tasks = [self.delete_one(sid, i + 1, total) for i, sid in enumerate(site_ids)]
        results = []
        for coro in asyncio.as_completed(tasks):
            results.append(await coro)
        return results


def read_csv(filename: str) -> List[str]:
    site_ids = []
    with open(filename, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if "site_id" not in (reader.fieldnames or []):
            print("❌ Error: input.csv must have a 'site_id' column")
            return []
        for row in reader:
            sid = row["site_id"].strip()
            if sid:
                site_ids.append(sid)
    return site_ids


def write_csv(results: List[Dict], filename: str):
    fieldnames = ["site_id", "status", "error", "timestamp"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"💾 Saved {len(results)} records to {filename}")


async def main():
    if not TOKEN:
        print("❌ Error: TOKEN not set in script")
        print("Please set your API token in the TOKEN variable at the top of main.py")
        return

    print("🚀 Starting SafetyCulture Bulk Site Deletion")
    print("=" * 80)

    site_ids = read_csv("input.csv")
    if not site_ids:
        print("❌ No valid site IDs found in input.csv")
        return

    print(f"✅ Loaded {len(site_ids):,} site IDs from input.csv\n")

    start_time = time.time()

    async with SiteDeletor() as deletor:
        results = await deletor.delete_all(site_ids)

    write_csv(results, "output.csv")

    elapsed = time.time() - start_time
    deleted = sum(1 for r in results if r["status"] == "deleted")
    errors = sum(1 for r in results if r["status"] == "error")

    print("\n" + "=" * 80)
    print("📋 SUMMARY")
    print("=" * 80)
    print(f"📊 Total Sites:   {len(site_ids):,}")
    print(f"✅ Deleted:       {deleted:,}")
    print(f"❌ Failed:        {errors:,}")
    print(f"⏱️  Runtime:       {elapsed:.1f}s")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
