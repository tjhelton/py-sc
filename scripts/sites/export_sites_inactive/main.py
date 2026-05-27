import asyncio
import csv
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import aiohttp

TOKEN = ""  # Set your SafetyCulture API token here

BASE_URL = "https://api.safetyculture.io"
INPUT_CSV = "input.csv"
MAX_CONCURRENT = 20
MAX_REQUESTS_PER_MINUTE = 200
MAX_RETRIES = 5


class TokenBucketRateLimiter:

    def __init__(self, requests_per_minute: int, burst_size: Optional[int] = None):
        self.rate = requests_per_minute / 60.0
        self.burst_size = float(burst_size or requests_per_minute)
        self.tokens = self.burst_size
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self.last_refill
                self.tokens = min(self.burst_size, self.tokens + elapsed * self.rate)
                self.last_refill = now

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return

                wait_time = (1.0 - self.tokens) / self.rate

            await asyncio.sleep(wait_time)


class SafetyCultureAPI:

    def __init__(self, max_concurrent_requests: int = MAX_CONCURRENT):
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {TOKEN}",
        }
        self.max_concurrent_requests = max_concurrent_requests
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore: Optional[asyncio.Semaphore] = None
        self.rate_limiter: Optional[TokenBucketRateLimiter] = None

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=300,
            limit_per_host=200,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        timeout = aiohttp.ClientTimeout(total=120, connect=10)
        self.session = aiohttp.ClientSession(
            headers=self.headers, connector=connector, timeout=timeout
        )
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        self.rate_limiter = TokenBucketRateLimiter(MAX_REQUESTS_PER_MINUTE)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _request(
        self, method: str, url: str, json_body: Optional[Dict] = None
    ) -> Dict:
        async with self.semaphore:
            for attempt in range(MAX_RETRIES):
                try:
                    await self.rate_limiter.acquire()
                    async with self.session.request(
                        method, url, json=json_body
                    ) as response:
                        if response.status == 429:
                            retry_after = int(
                                response.headers.get("Retry-After", 2**attempt)
                            )
                            await asyncio.sleep(retry_after)
                            continue
                        response.raise_for_status()
                        return await response.json()
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    if attempt == MAX_RETRIES - 1:
                        raise
                    await asyncio.sleep(2**attempt)
        return {}

    async def search_leaf_sites(self) -> List[Dict[str, str]]:
        url = f"{BASE_URL}/directory/v1/folders/search"
        print("🚀 Searching leaf sites (only_leaf_nodes=true, limit=1500)...")

        sites: List[Dict[str, str]] = []
        page_token: Optional[str] = None
        page_count = 0
        start_time = time.time()

        while True:
            payload: Dict = {"limit": 1500, "only_leaf_nodes": True}
            if page_token:
                payload["page_token"] = page_token

            response = await self._request("POST", url, json_body=payload)
            folders = response.get("folders", []) or []
            for entry in folders:
                folder = entry.get("folder") or entry
                folder_id = folder.get("id")
                if folder_id:
                    sites.append({"id": folder_id, "name": folder.get("name", "")})
            page_count += 1

            page_token = response.get("next_page_token")
            if not page_token:
                break

        elapsed = time.time() - start_time
        print(
            f"🎉 Found {len(sites):,} leaf sites from {page_count} pages in {elapsed:.1f}s"
        )
        return sites

    async def count_inspections(self, site_id: str, is_not_sync: bool) -> int:
        url = f"{BASE_URL}/inspections/v1/inspection:GetInspections"
        payload = {
            "page_size": 1,
            "offset": 0,
            "query": {"location_ids": [site_id]},
            "is_not_sync": is_not_sync,
            "is_archived": False,
            "suppress_total": False,
        }
        data = await self._request("POST", url, json_body=payload)
        return int(data.get("total", 0) or 0)

    async def count_actions(self, site_id: str) -> int:
        url = f"{BASE_URL}/tasks/v1/actions/list"
        payload = {
            "page_size": 1,
            "task_filters": [
                {
                    "site_id": {
                        "operator": "FILTER_OPERATOR_IN",
                        "value": [site_id],
                    }
                }
            ],
        }
        data = await self._request("POST", url, json_body=payload)
        return int(data.get("total", 0) or 0)

    async def count_issues(self, site_id: str) -> int:
        url = f"{BASE_URL}/tasks/v1/incidents/list"
        payload = {
            "page_size": 1,
            "filters": [
                {
                    "site_id": {
                        "operator": "IN",
                        "value": [site_id],
                    }
                }
            ],
        }
        data = await self._request("POST", url, json_body=payload)
        return int(data.get("total", 0) or 0)

    async def get_site_activity(
        self, site_id: str, site_name: str
    ) -> Dict[str, object]:
        inspections_sync_task = self.count_inspections(site_id, is_not_sync=False)
        inspections_nonsync_task = self.count_inspections(site_id, is_not_sync=True)
        actions_task = self.count_actions(site_id)
        issues_task = self.count_issues(site_id)

        inspections_sync, inspections_nonsync, actions, issues = await asyncio.gather(
            inspections_sync_task,
            inspections_nonsync_task,
            actions_task,
            issues_task,
            return_exceptions=False,
        )

        inspection_count = inspections_sync + inspections_nonsync
        total = inspection_count + actions + issues

        return {
            "site_id": site_id,
            "site_name": site_name,
            "action_count": actions,
            "issue_count": issues,
            "inspection_count": inspection_count,
            "total_count": total,
        }


def load_sites_from_csv(path: str) -> List[Dict[str, str]]:
    sites: List[Dict[str, str]] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            site_id = (row.get("site_id") or row.get("id") or "").strip()
            site_name = (row.get("site_name") or row.get("name") or "").strip()
            if site_id:
                sites.append({"id": site_id, "name": site_name})
    return sites


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


def write_csv(rows: List[Dict], filename: str, fieldnames: List[str]):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"💾 Saved {len(rows)} records to {filename}")


async def process_sites(
    api: SafetyCultureAPI, sites: List[Dict[str, str]]
) -> Tuple[List[Dict], List[Dict]]:
    print(f"🔍 Checking activity for {len(sites):,} sites...")
    start = time.time()
    processed = 0

    total = len(sites)
    width = len(f"{total:,}")

    async def wrapped(site: Dict[str, str]) -> Optional[Dict]:
        nonlocal processed
        try:
            result = await api.get_site_activity(site["id"], site["name"])
        except Exception as e:
            print(f"  ❌ Error checking site {site['id']} ({site['name']}): {e}")
            return None
        processed += 1

        insp = result["inspection_count"]
        act = result["action_count"]
        iss = result["issue_count"]
        marker = "⚪" if result["total_count"] == 0 else "🟢"
        name = (site["name"] or site["id"])[:40]
        print(
            f"  [{processed:>{width},}/{total:,}] {marker} {name:<40} "
            f"insp:{insp:<4} act:{act:<4} iss:{iss:<4}"
        )

        if processed % 100 == 0 or processed == total:
            elapsed = time.time() - start
            rate = processed / elapsed if elapsed > 0 else 0
            remaining = (total - processed) / rate if rate > 0 else 0
            print(
                f"  📊 {processed:,}/{total:,} sites checked | "
                f"{rate:.1f} sites/sec | ETA: {int(remaining // 60)}m {int(remaining % 60)}s"
            )
        return result

    results = await asyncio.gather(*(wrapped(s) for s in sites))
    all_rows = [r for r in results if r is not None]
    inactive_rows = [r for r in all_rows if r["total_count"] == 0]

    elapsed = time.time() - start
    print(f"✅ Done: {len(all_rows):,} sites checked in {elapsed:.1f}s")
    return all_rows, inactive_rows


async def main():
    if not TOKEN:
        print("❌ Error: TOKEN not set in script")
        print("Please set your token in the TOKEN variable at the top of main.py")
        return

    print("🚀 SafetyCulture Sites Without Activity Report")
    print("=" * 80)

    start_time = datetime.now()

    async with SafetyCultureAPI(max_concurrent_requests=MAX_CONCURRENT) as api:
        if os.path.exists(INPUT_CSV):
            print(f"📥 Loading sites from {INPUT_CSV}")
            sites = load_sites_from_csv(INPUT_CSV)
            if not sites:
                print(
                    f"❌ {INPUT_CSV} contains no usable rows (expected site_id column)"
                )
                return
            print(f"   Loaded {len(sites):,} sites from input")
        else:
            print(f"📥 No {INPUT_CSV} found — fetching all leaf sites from API")
            sites = await api.search_leaf_sites()

        if not sites:
            print("❌ No sites to check")
            return

        all_rows, inactive_rows = await process_sites(api, sites)

    output_dir = get_next_output_dir()
    fieldnames = [
        "site_id",
        "site_name",
        "action_count",
        "issue_count",
        "inspection_count",
        "total_count",
    ]
    write_csv(inactive_rows, f"{output_dir}/sites_without_activity.csv", fieldnames)

    end_time = datetime.now()
    duration = end_time - start_time

    print("\n" + "=" * 80)
    print("📋 SUMMARY")
    print("=" * 80)
    print(f"🏢 Sites checked: {len(all_rows):,}")
    print(f"⚪ Sites without activity: {len(inactive_rows):,}")
    if all_rows:
        pct = len(inactive_rows) / len(all_rows) * 100
        print(f"📊 Percentage without activity: {pct:.1f}%")
    print(f"⏱️  Total runtime: {duration.total_seconds():.1f}s")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
