import asyncio
import csv
import sys
import time
from typing import Dict, List

import aiohttp
from tqdm import tqdm

TOKEN = ""  # Add your API token here
BASE_URL = "https://api.safetyculture.io"

# Rate limiting: 800 req/60sec for general endpoints, targeting 80% = 640 req/min
TARGET_RATE_LIMIT = 640  # requests per 60 seconds
RATE_LIMIT_WINDOW = 60  # seconds
REQUESTS_PER_SECOND = TARGET_RATE_LIMIT / RATE_LIMIT_WINDOW  # ~10.67 req/sec
REQUEST_DELAY = (
    RATE_LIMIT_WINDOW / TARGET_RATE_LIMIT
)  # ~0.09375 seconds between requests


class AsyncSafetyCultureClient:
    """Async client for SafetyCulture API with rate limiting."""

    def __init__(self, base_url, api_token):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {api_token}"}
        self.session = None
        # Semaphore to control concurrent requests
        self.rate_limiter = asyncio.Semaphore(30)  # Max 30 concurrent requests
        self.request_times = []  # Track request timing for rate limiting
        self.stats = {
            "total_requests": 0,
            "rate_limit_delays": 0,
            "errors": 0,
        }

    async def __aenter__(self):
        """Create async HTTP session with connection pooling."""
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection limit
            limit_per_host=30,  # Per-host connection limit
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        timeout = aiohttp.ClientTimeout(total=90, connect=10)
        self.session = aiohttp.ClientSession(
            headers=self.headers, connector=connector, timeout=timeout
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close session on exit."""
        if self.session:
            await self.session.close()

    async def _enforce_rate_limit(self):
        """Enforce rate limiting to stay at 80% of API limit."""
        current_time = time.time()

        # Remove requests older than the rate limit window
        self.request_times = [
            t for t in self.request_times if current_time - t < RATE_LIMIT_WINDOW
        ]

        # If we're at the rate limit, wait before making next request
        if len(self.request_times) >= TARGET_RATE_LIMIT:
            # Calculate how long to wait for the oldest request to age out
            oldest_request = self.request_times[0]
            wait_time = RATE_LIMIT_WINDOW - (current_time - oldest_request)
            if wait_time > 0:
                self.stats["rate_limit_delays"] += 1
                await asyncio.sleep(wait_time + 0.1)  # Add small buffer

        # Add small delay between requests to smooth out the rate
        await asyncio.sleep(REQUEST_DELAY)

        # Record this request time
        self.request_times.append(time.time())
        self.stats["total_requests"] += 1

    async def _make_request(self, url, method="GET", **kwargs):
        """Make rate-limited HTTP request."""
        async with self.rate_limiter:
            await self._enforce_rate_limit()

            try:
                async with self.session.request(method, url, **kwargs) as response:
                    # Handle rate limiting
                    if response.status == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        print(
                            f"\n⚠️  Rate limit hit, waiting {retry_after}s before retry..."
                        )
                        await asyncio.sleep(retry_after)
                        return await self._make_request(url, method, **kwargs)

                    response.raise_for_status()
                    return await response.json()

            except aiohttp.ClientError as e:
                self.stats["errors"] += 1
                print(f"\n❌ Request error for {url}: {e}")
                raise

    def transform_feed_id(self, feed_id):
        """Transform feed ID to UUID format if needed."""
        if "_" not in feed_id:
            return feed_id
        uuid_part = feed_id.split("_")[1]
        if len(uuid_part) == 32:
            return f"{uuid_part[:8]}-{uuid_part[8:12]}-{uuid_part[12:16]}-{uuid_part[16:20]}-{uuid_part[20:]}"
        return uuid_part

    async def fetch_paginated_feed(self, endpoint):
        """Fetch all pages from a paginated feed endpoint."""
        url = f"{self.base_url}{endpoint}"
        all_data = []

        while url:
            response = await self._make_request(url)
            data = response.get("data", [])
            all_data.extend(data)

            metadata = response.get("metadata", {})
            next_page = metadata.get("next_page")
            url = f"{self.base_url}{next_page}" if next_page else None

        return all_data

    async def get_template_by_id(self, template_id):
        """Fetch a single template by ID."""
        try:
            response = await self._make_request(
                f"{self.base_url}/templates/v1/templates/{template_id}"
            )
            return response.get("template")
        except Exception:
            return None

    async def get_templates_batch(self, template_ids: List[str]) -> List[Dict]:
        """Fetch multiple templates in parallel."""
        tasks = [self.get_template_by_id(tid) for tid in template_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out None results and exceptions
        templates = []
        for result in results:
            if result is not None and not isinstance(result, Exception):
                templates.append(result)
            # Small delay between processing results to prevent burst traffic
            await asyncio.sleep(0.05)

        return templates


def process_template_permissions(
    template, template_summary, users_lookup, groups_lookup
):
    """Process template permissions and return records."""
    records = []
    template_id, template_name = template.get("id", ""), template.get("name", "")
    # Use owner_name from feed/templates data
    owner_name = template_summary.get("owner_name", "Unknown Owner")
    permissions = template.get("permissions", {})

    for permission_type, permission_list in permissions.items():
        if not isinstance(permission_list, list):
            continue
        for permission_entry in permission_list:
            assignee_id = permission_entry.get("id", "")
            permission_obj_type = permission_entry.get("type", "USER")
            if permission_obj_type == "ROLE":
                assignee_type, assignee_name = "group", groups_lookup.get(
                    assignee_id, f"Unknown Group ({assignee_id})"
                )
            else:
                assignee_type, assignee_name = "user", users_lookup.get(
                    assignee_id, f"Unknown User ({assignee_id})"
                )
            records.append(
                {
                    "template_id": template_id,
                    "name": template_name,
                    "template_owner": owner_name,
                    "permission": permission_type,
                    "assignee_type": assignee_type,
                    "assignee_id": assignee_id,
                    "assignee_name": assignee_name,
                }
            )
    return records


async def fetch_users_lookup(client):
    """Fetch all users and create lookup dictionary."""
    print("🔍 Fetching users...")
    start_time = time.time()

    users_data = await client.fetch_paginated_feed("/feed/users")

    users_lookup = {}
    for user in users_data:
        user_id = user.get("id", "")
        user_name = (
            f"{user.get('firstname', '')} {user.get('lastname', '')}".strip()
            or user.get("email", "Unknown User")
        )
        users_lookup[client.transform_feed_id(user_id)] = user_name

    elapsed = time.time() - start_time
    print(f"✓ Loaded {len(users_lookup):,} users in {elapsed:.2f}s\n")
    return users_lookup


async def fetch_groups_lookup(client):
    """Fetch all groups and create lookup dictionary."""
    print("🔍 Fetching groups...")
    start_time = time.time()

    groups_data = await client.fetch_paginated_feed("/feed/groups")

    groups_lookup = {}
    for group in groups_data:
        group_id = group.get("id", "")
        groups_lookup[client.transform_feed_id(group_id)] = group.get(
            "name", "Unknown Group"
        )

    elapsed = time.time() - start_time
    print(f"✓ Loaded {len(groups_lookup):,} groups in {elapsed:.2f}s\n")
    return groups_lookup


async def main():
    """Main async execution function."""
    if not TOKEN:
        print("Error: Please set your SafetyCulture API token in the TOKEN variable")
        return 1

    print("=" * 80)
    print("🚀 High-Performance Template Access Rules Exporter")
    print("=" * 80)
    print(f"⚡ Rate limit: {TARGET_RATE_LIMIT} req/{RATE_LIMIT_WINDOW}s")
    print(f"   (~{REQUESTS_PER_SECOND:.2f} requests/second)")
    print("=" * 80)
    print()

    overall_start = time.time()

    async with AsyncSafetyCultureClient(BASE_URL, TOKEN) as client:
        # Fetch lookups (fast, sequential is fine)
        users_lookup = await fetch_users_lookup(client)
        groups_lookup = await fetch_groups_lookup(client)

        # Get list of all templates
        print("🔍 Fetching template list...")
        fetch_start = time.time()
        all_templates = await client.fetch_paginated_feed("/feed/templates")

        # Filter out archived templates
        active_templates = [t for t in all_templates if not t.get("archived", False)]
        fetch_elapsed = time.time() - fetch_start

        print(
            f"✓ Found {len(active_templates):,} active templates "
            f"(out of {len(all_templates):,} total) in {fetch_elapsed:.2f}s\n"
        )

        # Fetch detailed template data in parallel batches
        print("⚡ Fetching template details with parallel async requests...")
        print(
            f"   Processing with rate limit: {TARGET_RATE_LIMIT} req/{RATE_LIMIT_WINDOW}s\n"
        )

        # Create lookup for template summaries to get owner_name
        # Store both feed ID and transformed UUID for lookup
        template_summaries = {}
        template_ids = []
        for t in active_templates:
            feed_id = t.get("id")
            transformed_id = client.transform_feed_id(feed_id)
            template_summaries[feed_id] = t
            template_summaries[transformed_id] = t
            template_ids.append(feed_id)
        batch_size = 50  # Process in batches for better progress tracking

        all_template_details = []
        detail_start = time.time()

        with tqdm(total=len(template_ids), desc="Templates", unit="template") as pbar:
            for i in range(0, len(template_ids), batch_size):
                batch = template_ids[i : i + batch_size]
                batch_results = await client.get_templates_batch(batch)
                all_template_details.extend(batch_results)
                pbar.update(len(batch))

                # Add delay after each batch to give API breathing room
                await asyncio.sleep(0.5)

                # Show rate statistics periodically
                if (i // batch_size) % 5 == 0 and i > 0:
                    elapsed = time.time() - detail_start
                    rate = (
                        client.stats["total_requests"] / elapsed if elapsed > 0 else 0
                    )
                    pbar.set_postfix(
                        {
                            "req/s": f"{rate:.2f}",
                            "delays": client.stats["rate_limit_delays"],
                        }
                    )

        detail_elapsed = time.time() - detail_start
        avg_rate = (
            client.stats["total_requests"] / detail_elapsed if detail_elapsed > 0 else 0
        )

        print(
            f"\n✓ Fetched {len(all_template_details):,} template details in {detail_elapsed:.2f}s"
        )
        print(f"   Average rate: {avg_rate:.2f} req/sec")
        print(f"   Rate limit delays: {client.stats['rate_limit_delays']}")
        print(f"   Errors: {client.stats['errors']}\n")

        # Process templates and write to CSV
        print("📝 Processing permissions and writing to CSV...")
        write_start = time.time()

        with open(
            "template_access_rules.csv", "w", newline="", encoding="utf-8"
        ) as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(
                [
                    "template_id",
                    "name",
                    "template_owner",
                    "permission",
                    "assignee_type",
                    "assignee_id",
                    "assignee_name",
                ]
            )

            records_written = 0
            for template in all_template_details:
                template_id = template.get("id")
                template_summary = template_summaries.get(template_id, {})
                for record in process_template_permissions(
                    template, template_summary, users_lookup, groups_lookup
                ):
                    csv_writer.writerow(
                        [
                            record["template_id"],
                            record["name"],
                            record["template_owner"],
                            record["permission"],
                            record["assignee_type"],
                            record["assignee_id"],
                            record["assignee_name"],
                        ]
                    )
                    records_written += 1

        write_elapsed = time.time() - write_start
        print(f"✓ Wrote {records_written:,} access rules in {write_elapsed:.2f}s\n")

    # Final statistics
    overall_elapsed = time.time() - overall_start
    print("=" * 80)
    print("🎉 EXPORT COMPLETE!")
    print("=" * 80)
    print(f"⏱️  Total time: {overall_elapsed:.2f}s ({overall_elapsed/60:.2f} minutes)")
    print(f"📊 Templates processed: {len(all_template_details):,}")
    print(f"📝 Access rules written: {records_written:,}")
    print("💾 Output: template_access_rules.csv")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
