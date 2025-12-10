import asyncio
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import aiohttp

TOKEN = ""  # Set your SafetyCulture API token here

BASE_URL = "https://api.safetyculture.io"
LIST_ACTIONS_URL = f"{BASE_URL}/tasks/v1/actions/list"
DELETE_ACTION_SCHEDULE_URL = f"{BASE_URL}/tasks/v1/actions:DeleteActionSchedule"

# Tweak these to suit your org's limits
PAGE_SIZE = 100  # Maximum allowed by the API
LIST_CONCURRENCY = 12  # Parallel list requests using offset paging
DELETE_CONCURRENCY = 12  # Run below rate limits (about half of typical limits)
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
INPUT_CSV_NAME = "input.csv"

ActionSchedulePair = Tuple[str, str]


class SafetyCultureActionsClient:
    def __init__(self, token: str) -> None:
        self.token = token
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "SafetyCultureActionsClient":
        connector = aiohttp.TCPConnector(
            limit=DELETE_CONCURRENCY * 2,
            limit_per_host=DELETE_CONCURRENCY,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {self.token}",
        }
        self.session = aiohttp.ClientSession(
            connector=connector, timeout=timeout, headers=headers
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.session:
            await self.session.close()

    async def fetch_actions_page(
        self, page_token: Optional[str] = None, offset: Optional[int] = None
    ) -> Dict:
        if not self.session:
            raise RuntimeError("Client session is not initialized")

        payload: Dict[str, object] = {"page_size": PAGE_SIZE, "without_count": True}
        if page_token:
            payload["page_token"] = page_token
        if offset is not None:
            payload["offset"] = offset

        async with self.session.post(LIST_ACTIONS_URL, json=payload) as response:
            text = await response.text()
            try:
                response.raise_for_status()
            except aiohttp.ClientResponseError as err:
                raise RuntimeError(
                    f"List actions failed (status {response.status}): {text}"
                ) from err
            return await response.json()

    async def stream_actions_offset(self) -> Iterable[Tuple[int, List[Dict]]]:
        """
        Generator yielding pages of actions using offset-based paging with
        parallel fetches to speed up discovery.
        """
        offset = 0
        in_flight: List[Tuple[int, asyncio.Task]] = []
        exhausted = False
        page_number = 0

        while True:
            # Keep the pipeline full
            while len(in_flight) < LIST_CONCURRENCY and not exhausted:
                task = asyncio.create_task(self.fetch_actions_page(offset=offset))
                in_flight.append((offset, task))
                offset += PAGE_SIZE

            if not in_flight:
                break

            current_offset, task = in_flight.pop(0)
            page_data = await task
            actions = page_data.get("actions", []) or []
            page_number += 1

            yield page_number, actions

            if len(actions) < PAGE_SIZE:
                exhausted = True

    async def delete_action_schedule(
        self,
        action_id: str,
        schedule_id: str,
        semaphore: asyncio.Semaphore,
    ) -> Dict[str, Optional[str]]:
        if not self.session:
            raise RuntimeError("Client session is not initialized")

        payload = {"schedule_id": schedule_id, "action_id": action_id}

        async with semaphore:
            for attempt in range(1, 4):
                try:
                    async with self.session.post(
                        DELETE_ACTION_SCHEDULE_URL, json=payload
                    ) as response:
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


def load_pairs_from_csv(csv_path: Path) -> List[ActionSchedulePair]:
    if not csv_path.exists():
        print(f"No CSV found at {csv_path}. Falling back to API fetch.")
        return []

    with csv_path.open(newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        required_fields = {"action_id", "schedule_id"}
        if not reader.fieldnames or not required_fields.issubset(reader.fieldnames):
            print(
                f"CSV at {csv_path} must include columns: action_id, schedule_id. "
                "No rows will be processed from this file."
            )
            return []

        rows: List[ActionSchedulePair] = []
        for row in reader:
            action_id = (row.get("action_id") or "").strip()
            schedule_id = (row.get("schedule_id") or "").strip()
            if action_id and schedule_id:
                rows.append((action_id, schedule_id))

        if not rows:
            print(f"CSV at {csv_path} is empty. Falling back to API fetch.")
        else:
            print(f"Loaded {len(rows)} schedule pairs from {csv_path}.")

        return rows


def extract_schedule_pairs(actions: List[Dict]) -> List[ActionSchedulePair]:
    pairs: List[ActionSchedulePair] = []
    for action in actions:
        task = action.get("task") or {}
        action_id = (
            task.get("task_id")
            or task.get("id")
            or action.get("task_id")
            or action.get("id")
        )
        references = task.get("references") or []

        schedule_id = None
        for reference in references:
            if reference.get("type") == "SCHEDULE":
                schedule_id = reference.get("id")
                break

        if action_id and schedule_id:
            pairs.append((str(action_id), str(schedule_id)))

    return pairs


def deduplicate_pairs(pairs: List[ActionSchedulePair]) -> List[ActionSchedulePair]:
    seen = set()
    unique_pairs = []
    for action_id, schedule_id in pairs:
        key = (action_id, schedule_id)
        if key in seen:
            continue
        seen.add(key)
        unique_pairs.append(key)
    return unique_pairs


async def collect_pairs_from_api(
    client: SafetyCultureActionsClient,
) -> Tuple[List[ActionSchedulePair], int]:
    pairs: List[ActionSchedulePair] = []
    total_actions = 0

    async for page_number, actions in client.stream_actions_offset():
        total_actions += len(actions)
        page_pairs = extract_schedule_pairs(actions)
        pairs.extend(page_pairs)
        print(
            f"Page {page_number}: {len(actions)} actions, "
            f"{len(page_pairs)} with schedules, "
            f"{len(pairs)} total schedule pairs collected so far."
        )

    return pairs, total_actions


async def delete_schedule_pairs(
    client: SafetyCultureActionsClient,
    pairs: List[ActionSchedulePair],
    log_path: Path,
) -> Dict[str, int]:
    semaphore = asyncio.Semaphore(DELETE_CONCURRENCY)
    successes = 0
    failures = 0

    fieldnames = ["action_id", "schedule_id", "status", "status_code", "message"]
    with log_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for start in range(0, len(pairs), 200):
            chunk = pairs[start : start + 200]
            tasks = [
                client.delete_action_schedule(action_id, schedule_id, semaphore)
                for action_id, schedule_id in chunk
            ]

            results = await asyncio.gather(*tasks)

            for result in results:
                writer.writerow(result)
                if result["status"] == "success":
                    successes += 1
                else:
                    failures += 1

            processed = start + len(chunk)
            print(f"Processed {processed}/{len(pairs)} schedules...")
            csvfile.flush()

    return {"successes": successes, "failures": failures}


def build_log_path(base_dir: Path) -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return base_dir / f"delete_action_schedules_log_{timestamp}.csv"


async def main() -> int:
    if not TOKEN:
        print("Error: set TOKEN at the top of main.py before running.")
        return 1

    script_dir = Path(__file__).parent
    csv_path = script_dir / INPUT_CSV_NAME

    csv_pairs = load_pairs_from_csv(csv_path)

    async with SafetyCultureActionsClient(TOKEN) as client:
        if csv_pairs:
            pairs = csv_pairs
            total_actions = len(pairs)
            source = "CSV"
        else:
            print("Fetching actions from API to find schedules...")
            pairs, total_actions = await collect_pairs_from_api(client)
            source = "API"

        if not pairs:
            print("No schedules found to delete. Exiting.")
            return 0

        unique_pairs = deduplicate_pairs(pairs)
        if len(unique_pairs) < len(pairs):
            print(f"Deduplicated schedule pairs: {len(pairs)} -> {len(unique_pairs)}.")
        pairs = unique_pairs

        print(
            f"Deleting {len(pairs)} action schedules "
            f"(source: {source}, actions scanned: {total_actions}) "
            f"with concurrency {DELETE_CONCURRENCY}."
        )

        log_path = build_log_path(script_dir)
        summary = await delete_schedule_pairs(client, pairs, log_path)

        print("Deletion complete.")
        print(f"Successful deletions: {summary['successes']}")
        print(f"Failed deletions: {summary['failures']}")
        print(f"Log written to: {log_path}")

    return 0


if __name__ == "__main__":
    asyncio.run(main())
