import asyncio
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiohttp

TOKEN = ""  # Set your SafetyCulture API token here

BASE_URL = "https://api.safetyculture.io"
DELETE_SCHEDULE_URL = f"{BASE_URL}/tasks/v1/actions:DeleteActionSchedule"

CONCURRENCY = 12
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
INPUT_CSV_NAME = "input.csv"

ActionSchedulePair = Tuple[str, str]


async def delete_action_schedule(
    session: aiohttp.ClientSession,
    action_id: str,
    schedule_id: str,
    semaphore: asyncio.Semaphore,
) -> Dict[str, Optional[str]]:
    """Delete a single action schedule."""
    payload = {"schedule_id": schedule_id, "action_id": action_id}

    async with semaphore:
        for attempt in range(1, 4):
            try:
                async with session.post(DELETE_SCHEDULE_URL, json=payload) as response:
                    text = await response.text()
                    if response.status in (200, 204):
                        return {
                            "action_id": action_id,
                            "schedule_id": schedule_id,
                            "status": "success",
                            "status_code": str(response.status),
                            "message": "",
                        }

                    if response.status in RETRY_STATUS_CODES and attempt < 3:
                        await asyncio.sleep(2**attempt)
                        continue

                    return {
                        "action_id": action_id,
                        "schedule_id": schedule_id,
                        "status": "error",
                        "status_code": str(response.status),
                        "message": text or response.reason,
                    }

            except aiohttp.ClientError as error:
                if attempt < 3:
                    await asyncio.sleep(2**attempt)
                    continue
                return {
                    "action_id": action_id,
                    "schedule_id": schedule_id,
                    "status": "error",
                    "status_code": None,
                    "message": str(error),
                }

    return {
        "action_id": action_id,
        "schedule_id": schedule_id,
        "status": "error",
        "status_code": None,
        "message": "Max retries exceeded",
    }


def load_pairs_from_csv(csv_path: Path) -> List[ActionSchedulePair]:
    """Load action_id and schedule_id pairs from input CSV."""
    if not csv_path.exists():
        print(f"Error: {csv_path} not found.")
        return []

    with csv_path.open(newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)
        required = {"action_id", "schedule_id"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            print(f"Error: {csv_path} must include columns: " "action_id, schedule_id")
            return []

        pairs: List[ActionSchedulePair] = []
        for row in reader:
            action_id = (row.get("action_id") or "").strip()
            schedule_id = (row.get("schedule_id") or "").strip()
            if action_id and schedule_id:
                pairs.append((action_id, schedule_id))

    if not pairs:
        print("Error: No valid pairs found in input CSV.")
    else:
        print(f"Loaded {len(pairs)} schedule pairs from {csv_path.name}.")

    return pairs


async def main() -> int:
    if not TOKEN:
        print("Error: set TOKEN at the top of main.py before running.")
        return 1

    script_dir = Path(__file__).parent
    csv_path = script_dir / INPUT_CSV_NAME

    pairs = load_pairs_from_csv(csv_path)
    if not pairs:
        return 1

    # Deduplicate while preserving order
    seen = set()
    unique_pairs: List[ActionSchedulePair] = []
    for pair in pairs:
        if pair not in seen:
            seen.add(pair)
            unique_pairs.append(pair)
    if len(unique_pairs) < len(pairs):
        print(f"Deduplicated: {len(pairs)} -> {len(unique_pairs)} pairs.")
    pairs = unique_pairs

    connector = aiohttp.TCPConnector(
        limit=CONCURRENCY * 2,
        limit_per_host=CONCURRENCY,
        ttl_dns_cache=300,
        use_dns_cache=True,
    )
    timeout = aiohttp.ClientTimeout(total=60, connect=10)
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {TOKEN}",
    }

    async with aiohttp.ClientSession(
        connector=connector, timeout=timeout, headers=headers
    ) as session:
        semaphore = asyncio.Semaphore(CONCURRENCY)

        print(f"\nDeleting {len(pairs)} schedules " f"(concurrency: {CONCURRENCY})...")

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        log_path = script_dir / f"stop_recurrence_log_{timestamp}.csv"
        fieldnames = [
            "action_id",
            "schedule_id",
            "status",
            "status_code",
            "message",
        ]

        successes = 0
        failures = 0

        with log_path.open("w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for start in range(0, len(pairs), 200):
                chunk = pairs[start : start + 200]
                tasks = [
                    delete_action_schedule(session, aid, sid, semaphore)
                    for aid, sid in chunk
                ]
                results = await asyncio.gather(*tasks)

                for result in results:
                    writer.writerow(result)
                    if result["status"] == "success":
                        successes += 1
                    else:
                        failures += 1

                processed = start + len(chunk)
                print(f"  Processed {processed}/{len(pairs)} schedules...")
                csvfile.flush()

        print(f"\nDone. Schedules removed: {successes}, Failed: {failures}")
        print(f"Log written to: {log_path.name}")

    return 0


if __name__ == "__main__":
    asyncio.run(main())
