import asyncio
import csv
import math
import time

import aiohttp

TOKEN = ""  # Set your SafetyCulture API token here

BASE_URL = "https://api.safetyculture.io"
PAGE_SIZE = 1000
MAX_CONCURRENT = 10

# Default priority IDs from the SafetyCulture OpenAPI spec
PRIORITY_MAP = {
    "58941717-817f-4c7c-a6f6-5cd05e2bbfde": "None",
    "16ba4717-adc9-4d48-bf7c-044cfe0d2727": "Low",
    "ce87c58a-eeb2-4fde-9dc4-c6e85f1f4055": "Medium",
    "02eb40c1-4f46-40c5-be16-d32941c96ec9": "High",
}

CSV_HEADERS = [
    "action_id",
    "unique_id",
    "creator_name",
    "creator_id",
    "title",
    "description",
    "created_at",
    "due_at",
    "priority",
    "status",
    "assignees",
    "template_id",
    "inspection_id",
    "item_id",
    "item_label",
    "site_id",
    "site_name",
    "modified_at",
    "completed_at",
    "action_type",
    "schedule_id",
]


def parse_action(action):
    task = action.get("task", {})
    creator = task.get("creator", {})
    inspection = task.get("inspection", {})
    inspection_item = task.get("inspection_item", {})
    site = task.get("site", {})
    status = task.get("status", {})
    action_type = action.get("type", {})

    # Build assignees from collaborators
    assignee_names = []
    for collab in task.get("collaborators", []):
        if collab.get("collaborator_type") == "GROUP":
            group = collab.get("group", {})
            name = group.get("name", "")
            if name:
                assignee_names.append(name)
        else:
            user = collab.get("user", {})
            first = user.get("firstname", "")
            last = user.get("lastname", "")
            full = f"{first} {last}".strip()
            if full:
                assignee_names.append(full)

    # Extract schedule_id from references
    schedule_id = ""
    for ref in task.get("references", []):
        if ref.get("type") == "SCHEDULE":
            schedule_id = ref.get("id", "")
            break

    return {
        "action_id": task.get("task_id", ""),
        "unique_id": task.get("unique_id", ""),
        "creator_name": f"{creator.get('firstname', '')} {creator.get('lastname', '')}".strip(),
        "creator_id": creator.get("user_id", ""),
        "title": task.get("title", ""),
        "description": task.get("description", ""),
        "created_at": task.get("created_at", ""),
        "due_at": task.get("due_at", ""),
        "priority": PRIORITY_MAP.get(task.get("priority_id", ""), "Unknown"),
        "status": status.get("label", ""),
        "assignees": ", ".join(assignee_names),
        "template_id": task.get("template_id", ""),
        "inspection_id": inspection.get("inspection_id", ""),
        "item_id": inspection_item.get("inspection_item_id", ""),
        "item_label": inspection_item.get("inspection_item_name", ""),
        "site_id": site.get("id", ""),
        "site_name": site.get("name", ""),
        "modified_at": task.get("modified_at", ""),
        "completed_at": task.get("completed_at", ""),
        "action_type": action_type.get("name", ""),
        "schedule_id": schedule_id,
    }


async def fetch_page(session, semaphore, offset):
    url = f"{BASE_URL}/tasks/v1/actions/list"
    payload = {"page_size": PAGE_SIZE, "offset": offset}

    async with semaphore:
        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                print(f"  Error at offset {offset}: {resp.status} - {text[:200]}")
                return []
            data = await resp.json()
            return data.get("actions", [])


async def get_total(session):
    url = f"{BASE_URL}/tasks/v1/actions/list"
    payload = {"page_size": 1, "offset": 0}

    async with session.post(url, json=payload) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise RuntimeError(f"Failed to get total: {resp.status} - {text[:200]}")
        data = await resp.json()
        return data.get("total", 0)


async def main():
    if not TOKEN:
        print(
            "Error: TOKEN not set. Set your SafetyCulture API token at the top of main.py"
        )
        return

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {TOKEN}",
    }
    connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
    timeout = aiohttp.ClientTimeout(total=120, connect=10)

    async with aiohttp.ClientSession(
        headers=headers, connector=connector, timeout=timeout
    ) as session:
        print("Fetching total action count...")
        total = await get_total(session)
        print(f"Total actions: {total:,}")

        if total == 0:
            print("No actions found.")
            return

        total_pages = math.ceil(total / PAGE_SIZE)
        offsets = [i * PAGE_SIZE for i in range(total_pages)]
        print(f"Pages to fetch: {total_pages} ({PAGE_SIZE} per page)")

        semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        start = time.time()

        tasks = [fetch_page(session, semaphore, offset) for offset in offsets]
        results = await asyncio.gather(*tasks)

        elapsed = time.time() - start
        all_actions = [action for page in results for action in page]
        print(f"Fetched {len(all_actions):,} actions in {elapsed:.1f}s")

        print("Writing output.csv...")
        rows = [parse_action(a) for a in all_actions]
        with open("output.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()
            writer.writerows(rows)

        print(f"Done. Exported {len(rows):,} actions to output.csv")


asyncio.run(main())
