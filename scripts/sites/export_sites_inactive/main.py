import asyncio
import csv
import os
import time
from datetime import datetime
from typing import Dict, List, Set

import aiohttp

TOKEN = ""  # Set your SafetyCulture API token here
BASE_URL = "https://api.safetyculture.io"


class SafetyCultureAPI:

    def __init__(self, max_concurrent_requests=25):
        self.headers = {
            "accept": "application/json",
            "authorization": f"Bearer {TOKEN}",
        }
        self.max_concurrent_requests = max_concurrent_requests
        self.session = None
        self.semaphore = None

    async def __aenter__(self):
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
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def fetch_page(self, url: str) -> Dict:
        async with self.semaphore:
            try:
                async with self.session.get(url) as response:
                    response.raise_for_status()
                    return await response.json()
            except Exception as e:
                print(f"❌ Error fetching {url}: {e}")
                raise

    async def fetch_all_inspections(self) -> List[Dict]:
        initial_url = f"{BASE_URL}/feed/inspections?archived=false&completed=both"
        print("🚀 Starting inspection fetch...")

        all_data = []
        url = initial_url
        page_count = 0
        start_time = time.time()

        while url:
            try:
                response = await self.fetch_page(url)
                data = response.get("data", [])
                all_data.extend(data)
                page_count += 1

                metadata = response.get("metadata", {})
                remaining_records = metadata.get("remaining_records", 0)

                elapsed = time.time() - start_time
                rate = page_count / elapsed if elapsed > 0 else 0

                if remaining_records > 0 and rate > 0:
                    remaining_pages = remaining_records / 25  # 25 records per page
                    estimated_time_remaining = remaining_pages / rate
                    eta_minutes = int(estimated_time_remaining // 60)
                    eta_seconds = int(estimated_time_remaining % 60)
                    eta_str = f"{eta_minutes}m {eta_seconds}s"
                else:
                    eta_str = "calculating..."

                print(
                    f"  📄 Page {page_count}: {len(data)} records | Total: {len(all_data):,} | Remaining: {remaining_records:,} | Rate: {rate:.2f} pages/sec | ETA: {eta_str}"
                )

                next_url = metadata.get("next_page")
                if next_url:
                    if not next_url.startswith("http"):
                        next_url = f"{BASE_URL}{next_url}"
                    url = next_url
                else:
                    url = None

            except Exception as e:
                print(f"❌ Error on page {page_count}: {e}")
                break

        elapsed = time.time() - start_time
        rate = page_count / elapsed if elapsed > 0 else 0
        print(
            f"🎉 Completed inspection fetch: {len(all_data):,} records from {page_count} pages in {elapsed:.1f}s ({rate:.1f} pages/sec)"
        )
        return all_data

    async def fetch_all_sites(self) -> List[Dict]:
        initial_url = f"{BASE_URL}/directory/v1/folders?page_size=1500"
        print("🚀 Starting folder fetch...")

        all_data = []
        url = initial_url
        page_count = 0
        start_time = time.time()

        while url:
            try:
                response = await self.fetch_page(url)
                folders = response.get("folders", [])
                all_data.extend(folders)
                page_count += 1

                next_page_token = response.get("next_page_token")
                if next_page_token:
                    base_url = url.split("?")[0]
                    url = f"{base_url}?page_size=1500&page_token={next_page_token}"
                else:
                    url = None

            except Exception as e:
                print(f"❌ Error on page {page_count}: {e}")
                break

        elapsed = time.time() - start_time
        print(
            f"🎉 Completed folder fetch: {len(all_data):,} records from {page_count} pages in {elapsed:.1f}s"
        )
        return all_data


def get_sites_with_activity(inspections: List[Dict]) -> Set[str]:
    sites_with_activity = set()

    for inspection in inspections:
        site_id = inspection.get("site_id")
        if site_id:
            sites_with_activity.add(site_id)

    print(f"🎯 Found {len(sites_with_activity)} unique sites with inspection activity")
    return sites_with_activity


def find_sites_without_activity(
    sites: List[Dict], sites_with_activity: Set[str]
) -> List[Dict]:
    sites_without_activity = []

    for site in sites:
        site_id = site.get("id")
        if site_id and site_id not in sites_with_activity:
            sites_without_activity.append(site)

    print(
        f"📊 {len(sites_without_activity)} out of {len(sites)} sites have no inspection activity"
    )
    return sites_without_activity


def get_next_output_dir() -> str:
    base_dir = "output"
    if not os.path.exists(base_dir):
        return base_dir

    index = 1
    while True:
        indexed_dir = f"{base_dir}_{index}"
        if not os.path.exists(indexed_dir):
            return indexed_dir
        index += 1


def write_csv(data: List[Dict], filename: str):
    if not data:
        print(f"⚠️  No data to write to {filename}")
        return

    os.makedirs(os.path.dirname(filename), exist_ok=True)

    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        if data:
            fieldnames = data[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

    print(f"💾 Saved {len(data)} records to {filename}")


async def main():
    if not TOKEN:
        print("❌ Error: TOKEN not set in script")
        print("Please set your token in the TOKEN variable at the top of main.py")
        return

    print("🚀 Starting SafetyCulture Sites Without Activity Analysis")
    print("=" * 80)
    print("📊 Expected runtime: ~25-30 minutes for ~69K inspections")
    print("=" * 80)

    start_time = datetime.now()

    async with SafetyCultureAPI(max_concurrent_requests=25) as api:
        print("🔄 Fetching inspections and sites concurrently...")

        fetch_start = time.time()
        inspections_task = asyncio.create_task(api.fetch_all_inspections())
        sites_task = asyncio.create_task(api.fetch_all_sites())

        inspections, sites = await asyncio.gather(inspections_task, sites_task)
        fetch_time = time.time() - fetch_start

        print(f"⚡ Total fetch time: {fetch_time:.1f} seconds")

    print("\n📈 Processing data...")
    process_start = time.time()

    sites_with_activity = get_sites_with_activity(inspections)

    sites_without_activity = find_sites_without_activity(sites, sites_with_activity)
    process_time = time.time() - process_start

    output_dir = get_next_output_dir()

    print(f"\n💾 Saving results to {output_dir}/...")
    save_start = time.time()
    write_csv(sites_without_activity, f"{output_dir}/sites_without_activity.csv")
    write_csv(inspections, f"{output_dir}/all_inspections.csv")
    write_csv(sites, f"{output_dir}/all_sites.csv")
    save_time = time.time() - save_start

    end_time = datetime.now()
    duration = end_time - start_time

    print("\n" + "=" * 80)
    print("📋 PERFORMANCE SUMMARY")
    print("=" * 80)
    print(f"🏢 Total Sites: {len(sites):,}")
    print(f"🔍 Total Inspections: {len(inspections):,}")
    print(f"🎯 Sites with Activity: {len(sites_with_activity):,}")
    print(f"⚪ Sites without Activity: {len(sites_without_activity):,}")
    print(
        f"📊 Percentage without Activity: {(len(sites_without_activity)/len(sites)*100):.1f}%"
    )
    print("\n🚀 TIMING BREAKDOWN:")
    print(f"  🏁 API Fetching: {fetch_time:.1f}s")
    print(f"  📊 Data Processing: {process_time:.1f}s")
    print(f"  💾 File Saving: {save_time:.1f}s")
    print(f"  ⏱️  Total Runtime: {duration.total_seconds():.1f}s")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
