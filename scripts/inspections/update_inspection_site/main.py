import asyncio
import csv
import os

import aiohttp
import pandas as pd

TOKEN = ""  # Set your SafetyCulture API token here

CONCURRENCY = 20
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
BASE_URL = "https://api.safetyculture.io"


async def set_inspection_site(
    session: aiohttp.ClientSession,
    audit_id: str,
    site_id: str,
    semaphore: asyncio.Semaphore,
    index: int,
    total: int,
) -> dict:
    url = f"{BASE_URL}/inspections/v1/inspections/{audit_id}/site"
    payload = {"site_id": site_id}

    async with semaphore:
        for attempt in range(1, 4):
            try:
                async with session.put(url, json=payload) as response:
                    if response.status in (200, 204):
                        print(f"[{index}/{total}] OK  {audit_id} -> {site_id}")
                        return {
                            "audit_id": audit_id,
                            "site_id": site_id,
                            "status": "success",
                        }

                    if response.status in RETRY_STATUS_CODES and attempt < 3:
                        await asyncio.sleep(2**attempt)
                        continue

                    text = await response.text()
                    print(f"[{index}/{total}] ERR {audit_id}: HTTP {response.status}")
                    return {
                        "audit_id": audit_id,
                        "site_id": site_id,
                        "status": f"ERROR {response.status}: {text}",
                    }
            except aiohttp.ClientError as error:
                if attempt < 3:
                    await asyncio.sleep(2**attempt)
                    continue
                print(f"[{index}/{total}] ERR {audit_id}: {error}")
                return {
                    "audit_id": audit_id,
                    "site_id": site_id,
                    "status": f"ERROR: {error}",
                }


async def main():
    if not TOKEN:
        print("Error: set TOKEN at the top of main.py before running.")
        return

    df = pd.read_csv("input.csv").fillna("")
    rows = df.to_dict("records")

    if not rows:
        print("No rows found in input.csv.")
        return

    total = len(rows)
    print(f"Processing {total} inspections with concurrency={CONCURRENCY}...")

    semaphore = asyncio.Semaphore(CONCURRENCY)
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
        tasks = [
            set_inspection_site(
                session, row["audit_id"], row["site_id"], semaphore, i + 1, total
            )
            for i, row in enumerate(rows)
        ]
        results = await asyncio.gather(*tasks)

    fieldnames = ["audit_id", "site_id", "status"]
    write_header = not os.path.exists("output.csv")
    with open("output.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerows(results)

    successes = sum(1 for r in results if r["status"] == "success")
    failures = total - successes
    print(f"\nDone. {successes} succeeded, {failures} failed. Results in output.csv")


if __name__ == "__main__":
    asyncio.run(main())
