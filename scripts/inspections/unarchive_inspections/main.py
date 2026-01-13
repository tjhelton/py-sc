import asyncio
import csv
import os
import time
from datetime import datetime
from typing import Dict, List

import aiohttp
import pandas as pd
from tqdm.asyncio import tqdm

TOKEN = ""  # Set your SafetyCulture API token here
BASE_URL = "https://api.safetyculture.io"

# Rate limiting configuration
# SafetyCulture API typically allows ~1000 requests/minute
# Using 800/min for optimal throughput while staying under API limits
MAX_REQUESTS_PER_MINUTE = 800  # 13.33 requests/sec
SEMAPHORE_VALUE = 30  # Optimal for 800/min (allows bursts with headroom)

# Batch processing configuration
BATCH_SIZE = 5000  # Process inspections in chunks to reduce memory usage

# CSV buffering configuration
CSV_BUFFER_SIZE = 100  # Flush CSV every N records for balance of I/O efficiency and real-time visibility

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class InspectionUnarchiver:

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
        self.rate_limiter = None
        # CSV buffering for I/O efficiency
        self.csv_buffer = []
        self.buffer_lock = asyncio.Lock()

    async def __aenter__(self):
        # Configure aiohttp session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=100, limit_per_host=50, ttl_dns_cache=300, use_dns_cache=True
        )
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        self.session = aiohttp.ClientSession(
            headers=self.headers, connector=connector, timeout=timeout
        )
        self.semaphore = asyncio.Semaphore(SEMAPHORE_VALUE)

        # Set up rate limiter
        self.rate_limiter = TokenBucketRateLimiter(MAX_REQUESTS_PER_MINUTE)

        # Set up output CSV with resume support
        csv_filename = "unarchive_results.csv"
        if os.path.exists(csv_filename):
            # Resume mode: append to existing file
            self.csv_file_handle = open(csv_filename, "a", newline="", encoding="utf-8")
            self.csv_writer = csv.DictWriter(
                self.csv_file_handle,
                fieldnames=[
                    "audit_id",
                    "status",
                    "error_message",
                    "timestamp",
                ],
            )
            # Don't write header when appending
            print(f"📝 Resuming: Appending to existing {csv_filename}")
        else:
            # Fresh start: create new file with header
            self.csv_file_handle = open(csv_filename, "w", newline="", encoding="utf-8")
            self.csv_writer = csv.DictWriter(
                self.csv_file_handle,
                fieldnames=[
                    "audit_id",
                    "status",
                    "error_message",
                    "timestamp",
                ],
            )
            self.csv_writer.writeheader()
            print(f"📝 Starting fresh: Creating {csv_filename}")

        self.csv_file_handle.flush()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Flush any remaining buffered results before closing
        if self.csv_buffer:
            async with self.buffer_lock:
                await self._flush_csv_buffer()

        if self.csv_file_handle:
            self.csv_file_handle.close()
        if self.session:
            await self.session.close()

    async def _write_result_to_csv_buffered(self, result: Dict):
        """
        Buffer CSV writes and flush periodically for I/O efficiency.
        Thread-safe for concurrent async access.
        """
        async with self.buffer_lock:
            self.csv_buffer.append(result)

            # Flush when buffer reaches threshold
            if len(self.csv_buffer) >= CSV_BUFFER_SIZE:
                await self._flush_csv_buffer()

    async def _flush_csv_buffer(self):
        """
        Flush buffered results to CSV.
        Must be called with buffer_lock held.
        """
        if not self.csv_buffer:
            return

        for result in self.csv_buffer:
            self.csv_writer.writerow(result)

        self.csv_file_handle.flush()
        self.csv_buffer.clear()

    async def unarchive_single_inspection(
        self, audit_id: str, progress_bar
    ) -> Dict[str, any]:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        async with self.semaphore:
            # Rate limiting
            await self.rate_limiter.acquire()

            url = f"{BASE_URL}/audits/{audit_id}"

            for attempt in range(MAX_RETRIES):
                try:
                    # Unarchive endpoint requires archived: false in JSON body
                    async with self.session.put(
                        url, json={"archived": False}
                    ) as response:
                        if response.status == 200:
                            result = {
                                "audit_id": audit_id,
                                "status": "SUCCESS",
                                "error_message": "",
                                "timestamp": timestamp,
                            }

                            log_msg = f"✅ Unarchived: {audit_id}"
                            if progress_bar:
                                progress_bar.write(log_msg)
                                progress_bar.update(1)

                            await self._write_result_to_csv_buffered(result)
                            return result

                        # Handle 429 with Retry-After header support
                        if response.status == 429 and attempt < MAX_RETRIES - 1:
                            retry_after = response.headers.get("Retry-After")

                            if retry_after and retry_after.isdigit():
                                # Retry-After is in seconds
                                wait_time = int(retry_after)
                                # Cap at 5 minutes for safety
                                wait_time = max(1, min(wait_time, 300))

                                if progress_bar:
                                    progress_bar.write(
                                        f"⏳ Rate limited: {audit_id}, "
                                        f"waiting {wait_time}s (from Retry-After header)"
                                    )

                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                # No Retry-After or invalid - use exponential backoff
                                delay = RETRY_BASE_DELAY * (2**attempt)
                                if progress_bar:
                                    progress_bar.write(
                                        f"⏳ Rate limited: {audit_id}, "
                                        f"waiting {delay}s (exponential backoff)"
                                    )
                                await asyncio.sleep(delay)
                                continue

                        # Handle other retryable errors
                        if (
                            response.status in RETRY_STATUS_CODES
                            and attempt < MAX_RETRIES - 1
                        ):
                            delay = RETRY_BASE_DELAY * (2**attempt)
                            await asyncio.sleep(delay)
                            continue

                        # Non-retryable error
                        error_text = await response.text()
                        result = {
                            "audit_id": audit_id,
                            "status": "ERROR",
                            "error_message": f"HTTP {response.status}: {error_text[:200]}",
                            "timestamp": timestamp,
                        }

                        log_msg = f"❌ Error: {audit_id} - HTTP {response.status}"
                        if progress_bar:
                            progress_bar.write(log_msg)
                            progress_bar.update(1)

                        await self._write_result_to_csv_buffered(result)
                        return result

                except (aiohttp.ClientError, asyncio.TimeoutError) as error:
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_BASE_DELAY * (2**attempt)
                        await asyncio.sleep(delay)
                        continue

                    result = {
                        "audit_id": audit_id,
                        "status": "ERROR",
                        "error_message": f"{type(error).__name__}: {str(error)}",
                        "timestamp": timestamp,
                    }

                    log_msg = f"❌ Error: {audit_id} - {type(error).__name__}"
                    if progress_bar:
                        progress_bar.write(log_msg)
                        progress_bar.update(1)

                    await self._write_result_to_csv_buffered(result)
                    return result

            # Max retries exceeded
            result = {
                "audit_id": audit_id,
                "status": "ERROR",
                "error_message": "Max retries exceeded",
                "timestamp": timestamp,
            }

            log_msg = f"❌ Error: {audit_id} - Max retries exceeded"
            if progress_bar:
                progress_bar.write(log_msg)
                progress_bar.update(1)

            await self._write_result_to_csv_buffered(result)
            return result

    async def unarchive_all_inspections(self, audit_ids: List[str]) -> Dict:
        """
        Process inspections in batches to reduce memory footprint.

        Key improvements:
        - Only create tasks for current batch (5000 at a time)
        - Memory: ~2.5 MB per batch vs 360 MB for all
        - More responsive to interruptions
        - Better progress visibility with batch-level updates
        """
        print(f"\n🚀 Starting bulk unarchive for {len(audit_ids)} inspections...")
        print(f"⚡ Rate limit: {MAX_REQUESTS_PER_MINUTE} requests per minute")
        print(f"🔄 Concurrent requests: {SEMAPHORE_VALUE}")
        print(f"📦 Batch size: {BATCH_SIZE} inspections")
        print("📊 Live results: unarchive_results.csv\n")

        results = {"success": 0, "error": 0, "total": len(audit_ids)}
        start_time = time.time()

        # Calculate total batches for progress tracking
        total_batches = (len(audit_ids) + BATCH_SIZE - 1) // BATCH_SIZE

        with tqdm(total=len(audit_ids), desc="Unarchiving", unit="inspection") as pbar:
            for batch_num in range(total_batches):
                # Calculate batch slice
                start_idx = batch_num * BATCH_SIZE
                end_idx = min(start_idx + BATCH_SIZE, len(audit_ids))
                batch = audit_ids[start_idx:end_idx]

                # Update progress bar description with batch info
                pbar.set_description(
                    f"Unarchiving (Batch {batch_num + 1}/{total_batches})"
                )

                # Create tasks ONLY for this batch
                tasks = [
                    self.unarchive_single_inspection(audit_id, pbar)
                    for audit_id in batch
                ]

                # Execute batch
                batch_results = await asyncio.gather(*tasks)

                # Aggregate results
                batch_success = 0
                batch_error = 0
                for result in batch_results:
                    if result["status"] == "SUCCESS":
                        results["success"] += 1
                        batch_success += 1
                    else:
                        results["error"] += 1
                        batch_error += 1

                # Log batch completion with stats
                elapsed = time.time() - start_time
                processed_count = start_idx + len(batch)
                rate = (processed_count / elapsed * 60) if elapsed > 0 else 0
                pbar.write(
                    f"📦 Batch {batch_num + 1}/{total_batches} complete | "
                    f"Rate: {rate:.1f} req/min | "
                    f"Success: {batch_success}/{len(batch)} | "
                    f"Errors: {batch_error}"
                )

        results["total_time_seconds"] = round(time.time() - start_time, 2)
        return results


class TokenBucketRateLimiter:
    """
    Lock-free token bucket rate limiter allowing concurrent access.

    Key improvements over previous RateLimiter:
    - No lock serialization - multiple tasks can acquire simultaneously
    - Supports bursts up to semaphore limit while maintaining average rate
    - Lock only used for token refill calculation, not for waiting
    """

    def __init__(self, requests_per_minute: int, burst_size: int = None):
        self.rate = requests_per_minute / 60.0  # tokens per second
        self.burst_size = burst_size or requests_per_minute  # max bucket capacity
        self.tokens = float(self.burst_size)  # start with full bucket
        self.last_refill = time.time()
        self._lock = asyncio.Lock()  # Only for token refill calculation

    async def acquire(self):
        """
        Acquire a token to make a request.
        Uses lock ONLY for refill calculation, not for waiting.
        Multiple tasks can wait concurrently without blocking each other.
        """
        while True:
            async with self._lock:
                now = time.time()
                # Refill tokens based on time elapsed
                elapsed = now - self.last_refill
                self.tokens = min(self.burst_size, self.tokens + elapsed * self.rate)
                self.last_refill = now

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return  # Token acquired, exit immediately

                # Calculate how long to wait for next token
                wait_time = (1.0 - self.tokens) / self.rate

            # Sleep OUTSIDE the lock so other tasks can check bucket
            await asyncio.sleep(wait_time)


def load_completed_audit_ids(csv_path: str = "unarchive_results.csv") -> set:
    """
    Load already-processed audit IDs from previous runs.
    Returns set of audit_ids that were successfully processed or errored.

    Both SUCCESS and ERROR are considered "processed" to avoid duplicate attempts.
    User can filter errors from CSV and retry them separately if needed.
    """
    if not os.path.exists(csv_path):
        return set()

    try:
        df = pd.read_csv(csv_path)

        if "audit_id" not in df.columns:
            print(f"⚠️  Warning: {csv_path} missing audit_id column")
            return set()

        # Consider both SUCCESS and ERROR as "processed"
        completed_ids = set(df["audit_id"].astype(str).str.strip())
        print(f"📋 Resuming: Found {len(completed_ids)} already-processed IDs")
        return completed_ids

    except Exception as error:
        print(f"⚠️  Warning: Could not read {csv_path}: {error}")
        print("Starting fresh...")
        return set()


def load_input_csv() -> List[str]:
    input_file = "input.csv"

    if not os.path.exists(input_file):
        print(f"❌ Error: {input_file} not found")
        print("Please create input.csv with column: audit_id")
        return []

    try:
        df = pd.read_csv(input_file)

        if "audit_id" not in df.columns:
            print("❌ Error: input.csv missing required column: audit_id")
            return []

        df = df.dropna(subset=["audit_id"])
        df["audit_id"] = df["audit_id"].astype(str).str.strip()

        audit_ids = df["audit_id"].tolist()

        if not audit_ids:
            print("❌ Error: No valid audit IDs found in input.csv")
            return []

        print(f"📋 Loaded {len(audit_ids)} inspection IDs from {input_file}")
        return audit_ids

    except Exception as error:
        print(f"❌ Error reading {input_file}: {error}")
        return []


async def main():
    print("=" * 80)
    print("📂 SafetyCulture Inspection Bulk Unarchiver")
    print("=" * 80)

    if not TOKEN:
        print("\n❌ Error: TOKEN not set in script")
        print("Please set your API token in the TOKEN variable at the top of main.py")
        return 1

    # Load all audit IDs from input
    all_audit_ids = load_input_csv()
    if not all_audit_ids:
        return 1

    # Load completed IDs and filter for resume capability
    completed_ids = load_completed_audit_ids()

    if completed_ids:
        original_count = len(all_audit_ids)
        audit_ids = [aid for aid in all_audit_ids if aid not in completed_ids]
        skipped = original_count - len(audit_ids)
        print(f"✅ Skipping {skipped} already-processed inspections")
        print(f"📋 Remaining to process: {len(audit_ids)}")

        if not audit_ids:
            print("\n🎉 All inspections already processed!")
            return 0
    else:
        audit_ids = all_audit_ids

    print("\n" + "=" * 80)

    async with InspectionUnarchiver() as unarchiver:
        results = await unarchiver.unarchive_all_inspections(audit_ids)

    print("\n" + "=" * 80)
    print("📊 UNARCHIVE SUMMARY")
    print("=" * 80)
    print(f"✅ Successful: {results['success']}")
    print(f"❌ Errors: {results['error']}")
    print(f"📝 Total: {results['total']}")

    if results["total"] > 0:
        success_rate = results["success"] / results["total"] * 100
        print(f"📈 Success Rate: {success_rate:.1f}%")
    else:
        print("📈 Success Rate: N/A")

    total_time = results.get("total_time_seconds", 0)
    minutes = int(total_time // 60)
    seconds = int(total_time % 60)
    print(f"⏱️  Total Time: {minutes}m {seconds}s")

    if results["total"] > 0:
        avg_time = total_time / results["total"]
        print(f"⚡ Average: {avg_time:.2f}s per inspection")

    print(f"\n💾 Results log: {os.path.abspath('unarchive_results.csv')}")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    asyncio.run(main())
