import asyncio
import csv
import time
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp

TOKEN = ""  # Set your SafetyCulture API token here
BASE_URL = "https://api.safetyculture.io"

MAX_CONCURRENT = 10  # Max concurrent create requests in flight at once
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class SiteCreator:
    def __init__(self):
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {TOKEN}",
        }
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore: Optional[asyncio.Semaphore] = None
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

    async def create_one(
        self,
        name: str,
        parent: str,
        meta_label: str,
        index: int,
        total: int,
    ) -> Dict:
        payload: Dict[str, str] = {"meta_label": meta_label, "name": name}
        if parent:
            payload["parent_id"] = parent
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        async with self.semaphore:
            for attempt in range(MAX_RETRIES):
                try:
                    async with self.session.post(
                        f"{BASE_URL}/directory/v1/folder",
                        json=payload,
                    ) as response:
                        if response.status in (200, 201):
                            self.success_count += 1
                            status = f"#{index} - Successfully Created {name}"
                            print(f"  ✓ [{index}/{total}] {name}")
                            return {
                                "count": index,
                                "site_name": name,
                                "meta_label": meta_label,
                                "status": status,
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
                        status = f"#{index} - ERROR creating {name}: {error}"
                        self.error_count += 1
                        print(f"  ✗ [{index}/{total}] {name} — {error}")
                        return {
                            "count": index,
                            "site_name": name,
                            "meta_label": meta_label,
                            "status": status,
                            "timestamp": timestamp,
                        }

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_BASE_DELAY * (2**attempt))
                        continue
                    error = f"{type(e).__name__}: {str(e)}"
                    status = f"#{index} - ERROR creating {name}: {error}"
                    self.error_count += 1
                    print(f"  ✗ [{index}/{total}] {name} — {error}")
                    return {
                        "count": index,
                        "site_name": name,
                        "meta_label": meta_label,
                        "status": status,
                        "timestamp": timestamp,
                    }

        error = "Max retries exceeded"
        status = f"#{index} - ERROR creating {name}: {error}"
        self.error_count += 1
        print(f"  ✗ [{index}/{total}] {name} — {error}")
        return {
            "count": index,
            "site_name": name,
            "meta_label": meta_label,
            "status": status,
            "timestamp": timestamp,
        }

    async def create_all(self, rows: List[Dict]) -> List[Dict]:
        total = len(rows)
        print(f"🏗️  Creating {total} sites (concurrency={MAX_CONCURRENT})...\n")

        tasks = [
            self.create_one(
                row["name"],
                row.get("parent", ""),
                row.get("meta_label", ""),
                i,
                total,
            )
            for i, row in enumerate(rows)
        ]
        results = []
        for coro in asyncio.as_completed(tasks):
            results.append(await coro)
        results.sort(key=lambda r: r["count"])
        return results


def read_csv(filename: str) -> List[Dict]:
    rows: List[Dict] = []
    with open(filename, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if "name" not in (reader.fieldnames or []):
            print("❌ Error: input.csv must have a 'name' column")
            return []
        for row in reader:
            name = (row.get("name") or "").strip()
            if not name:
                continue
            rows.append(
                {
                    "name": name,
                    "parent": (row.get("parent") or "").strip(),
                    "meta_label": (row.get("meta_label") or "").strip(),
                }
            )
    return rows


def write_csv(results: List[Dict], filename: str):
    fieldnames = ["count", "site_name", "meta_label", "status", "timestamp"]
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

    print("🚀 Starting SafetyCulture Bulk Site Creation")
    print("=" * 80)

    rows = read_csv("input.csv")
    if not rows:
        print("❌ No valid site rows found in input.csv")
        return

    print(f"✅ Loaded {len(rows):,} site rows from input.csv\n")

    start_time = time.time()

    async with SiteCreator() as creator:
        results = await creator.create_all(rows)

    write_csv(results, "output.csv")

    elapsed = time.time() - start_time
    created = sum(1 for r in results if "Successfully Created" in r["status"])
    errors = len(results) - created

    print("\n" + "=" * 80)
    print("📋 SUMMARY")
    print("=" * 80)
    print(f"📊 Total Sites:   {len(rows):,}")
    print(f"✅ Created:       {created:,}")
    print(f"❌ Failed:        {errors:,}")
    print(f"⏱️  Runtime:       {elapsed:.1f}s")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
