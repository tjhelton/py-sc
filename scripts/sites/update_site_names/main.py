import asyncio
import csv
import time
from datetime import datetime
from typing import Dict, List

import aiohttp

TOKEN = ""  # Set your SafetyCulture API token here
BASE_URL = "https://api.safetyculture.io"


class SafetyCultureAPI:
    def __init__(self, max_concurrent_requests=10):
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {TOKEN}",
        }
        self.max_concurrent_requests = max_concurrent_requests
        self.session = None
        self.semaphore = None

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=100, limit_per_host=30, ttl_dns_cache=300, use_dns_cache=True
        )
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        self.session = aiohttp.ClientSession(
            headers=self.headers, connector=connector, timeout=timeout
        )
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def update_site_name(self, site_id: str, new_name: str) -> Dict:
        url = f"{BASE_URL}/directory/v1/folder/{site_id}"
        async with self.semaphore:
            try:
                async with self.session.patch(url, json={"name": new_name}) as response:
                    status_code = response.status
                    if response.status == 200:
                        return {
                            "site_id": site_id,
                            "new_name": new_name,
                            "status": "success",
                            "status_code": status_code,
                            "error": "",
                        }
                    else:
                        body = await response.text()
                        return {
                            "site_id": site_id,
                            "new_name": new_name,
                            "status": "error",
                            "status_code": status_code,
                            "error": body[:200],
                        }
            except Exception as e:
                return {
                    "site_id": site_id,
                    "new_name": new_name,
                    "status": "error",
                    "status_code": "",
                    "error": str(e),
                }

    async def update_all_sites(self, rows: List[Dict]) -> List[Dict]:
        print(f"🔄 Updating {len(rows)} sites...\n")
        start_time = time.time()

        tasks = [self.update_site_name(row["site_id"], row["new_name"]) for row in rows]

        results = []
        completed = 0
        success_count = 0
        error_count = 0

        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            completed += 1

            if result["status"] == "success":
                success_count += 1
                print(
                    f"  ✓ [{completed}/{len(rows)}] Updated site {result['site_id']} → \"{result['new_name']}\""
                )
            else:
                error_count += 1
                print(
                    f"  ✗ [{completed}/{len(rows)}] Failed site {result['site_id']}: {result['error']}"
                )

        elapsed = time.time() - start_time
        print(
            f"\n🎉 Completed: {success_count} succeeded, {error_count} failed in {elapsed:.1f}s"
        )

        return results


def read_csv(filename: str) -> List[Dict]:
    rows = []
    with open(filename, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            site_id = row.get("site_id", "").strip()
            new_name = row.get("new_name", "").strip()
            if site_id and new_name:
                rows.append({"site_id": site_id, "new_name": new_name})
            else:
                print(f"⚠️  Skipping row with missing site_id or new_name: {row}")
    return rows


def write_csv(data: List[Dict], filename: str):
    if not data:
        print(f"⚠️  No data to write to {filename}")
        return

    fieldnames = ["site_id", "new_name", "status", "status_code", "error"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    print(f"💾 Saved {len(data)} records to {filename}")


async def main():
    if not TOKEN:
        print("❌ Error: TOKEN not set in script")
        print("Please set your token in the TOKEN variable at the top of main.py")
        return

    print("🚀 Starting SafetyCulture Bulk Site Name Update")
    print("=" * 80)

    start_time = datetime.now()

    print("📂 Reading input.csv...")
    rows = read_csv("input.csv")

    if not rows:
        print("❌ No valid rows found in input.csv")
        return

    print(f"✅ Loaded {len(rows)} sites to update\n")

    async with SafetyCultureAPI(max_concurrent_requests=10) as api:
        results = await api.update_all_sites(rows)

    print("\n💾 Saving results...")
    write_csv(results, "output.csv")

    end_time = datetime.now()
    duration = end_time - start_time

    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = sum(1 for r in results if r["status"] == "error")

    print("\n" + "=" * 80)
    print("📋 SUMMARY")
    print("=" * 80)
    print(f"📊 Total Sites Processed: {len(results):,}")
    print(f"✅ Succeeded: {success_count:,}")
    print(f"❌ Failed:    {error_count:,}")
    print(f"⏱️  Total Runtime: {duration.total_seconds():.1f}s")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
