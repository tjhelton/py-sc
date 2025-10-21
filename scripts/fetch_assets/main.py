import asyncio
import csv
import os
import time
from datetime import datetime
from typing import Dict

import aiohttp

TOKEN = ""
BASE_URL = "https://api.safetyculture.io"


class SafetyCultureAssetFetcher:
    """High-performance SafetyCulture asset fetcher using async I/O."""

    def __init__(self):
        self.headers = {
            "accept": "application/json",
            "authorization": f"Bearer {TOKEN}",
        }
        self.session = None
        self.stats = {
            "total_pages": 0,
            "total_assets": 0,
            "total_time": 0,
            "avg_page_time": 0,
        }

    async def __aenter__(self):
        """Create optimized async HTTP session with connection pooling."""
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
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close session on exit."""
        if self.session:
            await self.session.close()

    async def fetch_page(self, url: str) -> Dict:
        """Fetch a single page from the API."""
        try:
            async with self.session.get(url) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            print(f"❌ Error fetching {url}: {e}")
            raise

    async def fetch_all_assets(self, output_file: str):
        """
        Fetch all assets with sequential pagination and incremental CSV writing.

        This method optimizes for speed by:
        1. Writing data immediately to CSV (no memory accumulation)
        2. Using async I/O for non-blocking network operations
        3. Reusing TCP connections with optimized pooling
        4. Providing real-time progress feedback
        """
        initial_url = f"{BASE_URL}/feed/assets"
        print("🚀 Starting high-performance asset fetch...")
        print(f"💾 Streaming results to: {output_file}")
        print("=" * 80)

        url = initial_url
        page_count = 0
        total_assets = 0
        start_time = time.time()
        csv_writer = None
        csv_file = None

        try:
            # Open CSV file for incremental writing
            csv_file = open(output_file, "w", newline="", encoding="utf-8")

            while url:
                page_start = time.time()

                # Fetch page data
                response = await self.fetch_page(url)
                data = response.get("data", [])
                page_count += 1
                total_assets += len(data)

                # Initialize CSV writer on first page (use first row for headers)
                if csv_writer is None and data:
                    fieldnames = data[0].keys()
                    csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                    csv_writer.writeheader()

                # Write data immediately to CSV
                if csv_writer and data:
                    csv_writer.writerows(data)
                    csv_file.flush()  # Ensure data is written immediately

                # Calculate timing and progress metrics
                page_time = time.time() - page_start
                elapsed = time.time() - start_time
                rate = page_count / elapsed if elapsed > 0 else 0

                # Get metadata for remaining records estimate
                metadata = response.get("metadata", {})
                remaining_records = metadata.get("remaining_records", 0)

                # Calculate ETA
                if remaining_records > 0 and rate > 0:
                    # Estimate based on average records per page
                    avg_records_per_page = (
                        total_assets / page_count if page_count > 0 else 25
                    )
                    remaining_pages = remaining_records / avg_records_per_page
                    estimated_time_remaining = remaining_pages / rate
                    eta_minutes = int(estimated_time_remaining // 60)
                    eta_seconds = int(estimated_time_remaining % 60)
                    eta_str = f"{eta_minutes}m {eta_seconds}s"
                else:
                    eta_str = "calculating..."

                # Real-time progress logging
                print(
                    f"📄 Page {page_count}: {len(data)} assets | "
                    f"Total: {total_assets:,} | "
                    f"Remaining: {remaining_records:,} | "
                    f"Rate: {rate:.2f} pages/sec | "
                    f"Page time: {page_time:.2f}s | "
                    f"ETA: {eta_str}"
                )

                # Get next page URL
                next_url = metadata.get("next_page")
                if next_url:
                    # Handle relative URLs
                    if not next_url.startswith("http"):
                        next_url = f"{BASE_URL}{next_url}"
                    url = next_url
                else:
                    url = None

        except Exception as e:
            print(f"❌ Error during asset fetch: {e}")
            raise

        finally:
            # Close CSV file
            if csv_file:
                csv_file.close()

        # Final statistics
        elapsed = time.time() - start_time
        rate = page_count / elapsed if elapsed > 0 else 0
        avg_page_time = elapsed / page_count if page_count > 0 else 0
        throughput = total_assets / elapsed if elapsed > 0 else 0

        self.stats = {
            "total_pages": page_count,
            "total_assets": total_assets,
            "total_time": elapsed,
            "avg_page_time": avg_page_time,
            "pages_per_sec": rate,
            "assets_per_sec": throughput,
        }

        print("=" * 80)
        print("🎉 FETCH COMPLETE!")
        print("=" * 80)
        print(f"📊 Total Assets: {total_assets:,}")
        print(f"📄 Total Pages: {page_count:,}")
        print(f"⏱️  Total Time: {elapsed:.2f}s ({elapsed/60:.2f} minutes)")
        print(f"⚡ Average Page Time: {avg_page_time:.3f}s")
        print(f"🚀 Throughput: {rate:.2f} pages/sec | {throughput:.1f} assets/sec")
        print(f"💾 Output saved to: {output_file}")
        print("=" * 80)


def get_next_output_file() -> str:
    """Generate unique output filename with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"assets_{timestamp}"
    extension = ".csv"
    output_file = f"{base_name}{extension}"

    # If file exists (unlikely with timestamp), add counter
    counter = 1
    while os.path.exists(output_file):
        output_file = f"{base_name}_{counter}{extension}"
        counter += 1

    return output_file


async def main():
    """Main execution function."""
    if not TOKEN:
        print("❌ Error: TOKEN not set in script")
        print(
            "Please set your SafetyCulture API token in the TOKEN variable at the top of main.py"
        )
        return 1

    print("=" * 80)
    print("🚀 SafetyCulture High-Performance Asset Fetcher")
    print("=" * 80)
    print("📋 This script will fetch ALL assets from your SafetyCulture account")
    print("⚡ Optimized for maximum speed with:")
    print("   - Async I/O for non-blocking network operations")
    print("   - Incremental CSV writing (no memory accumulation)")
    print("   - Connection pooling and reuse")
    print("   - Real-time progress tracking")
    print("=" * 80)

    # Generate output filename
    output_file = get_next_output_file()

    start_time = datetime.now()

    # Fetch assets
    async with SafetyCultureAssetFetcher() as fetcher:
        await fetcher.fetch_all_assets(output_file)

    end_time = datetime.now()
    duration = end_time - start_time

    print("\n✅ Script completed successfully!")
    print(f"📅 Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📅 End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️  Duration: {duration}")

    return 0


if __name__ == "__main__":
    asyncio.run(main())
