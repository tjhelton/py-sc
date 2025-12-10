import asyncio
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import aiohttp


# ANSI color codes for terminal output
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


TOKEN = "scapi_ox-Hz8CqXXqF1Q9jiiRFiv_0SrDiLUvT40El4Pjbn0P0fPaJFCIf4GQbSUm_tT67kUGwmV2zfevHqP5DnB-Z5YBsI4o-SyW2VjavNu6IudqeKxUykYAHxVDmE9mmwxE12bTC95J5HukYLTAgwdpD8QjlHb9TvKGmJTY2ZcKDbHk"  # Set your SafetyCulture API token here

BASE_URL = "https://api.safetyculture.io"
LIST_ASSETS_URL = f"{BASE_URL}/assets/v1/assets/list"
DELETE_ASSET_URL = f"{BASE_URL}/assets/v1/assets"
ARCHIVE_ASSET_URL = f"{BASE_URL}/assets/v1/assets"

# Tweak these to suit your org's limits
PAGE_SIZE = 100  # Maximum allowed by the API
DELETE_CONCURRENCY = 12  # Run below rate limits (about half of typical limits)
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
INPUT_CSV_NAME = "input.csv"
TEST_LIMIT = None  # Safety limit for testing - set to None for unlimited


class SafetyCultureAssetsClient:
    def __init__(self, token: str) -> None:
        self.token = token
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "SafetyCultureAssetsClient":
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

    async def fetch_assets_page(
        self, page_token: Optional[str] = None, state: Optional[str] = None
    ) -> Dict:
        if not self.session:
            raise RuntimeError("Client session is not initialized")

        payload: Dict[str, object] = {"page_size": PAGE_SIZE}
        if page_token:
            payload["page_token"] = page_token
        if state:
            payload["asset_filters"] = [{"state": state}]

        async with self.session.post(LIST_ASSETS_URL, json=payload) as response:
            text = await response.text()
            try:
                response.raise_for_status()
            except aiohttp.ClientResponseError as err:
                raise RuntimeError(
                    f"List assets failed (status {response.status}): {text}"
                ) from err
            data = await response.json()
            return data

    async def stream_assets_cursor(self) -> Iterable[Tuple[int, List[Dict]]]:
        """
        Generator yielding pages of assets using cursor-based pagination.
        Note: Cannot parallelize like actions since each page depends on
        the previous page's next_page_token.
        Fetches both ACTIVE and ARCHIVED assets.
        """
        page_number = 0

        # Fetch ACTIVE assets first
        page_token: Optional[str] = None
        while True:
            page_data = await self.fetch_assets_page(
                page_token=page_token, state="ASSET_STATE_ACTIVE"
            )
            assets = page_data.get("assets", []) or []
            if assets:
                page_number += 1
                yield page_number, assets

            page_token = page_data.get("next_page_token")
            if not page_token:
                break

        # Then fetch ARCHIVED assets
        page_token = None
        while True:
            page_data = await self.fetch_assets_page(
                page_token=page_token, state="ASSET_STATE_ARCHIVED"
            )
            assets = page_data.get("assets", []) or []
            if assets:
                page_number += 1
                yield page_number, assets

            page_token = page_data.get("next_page_token")
            if not page_token:
                break

    async def archive_asset(
        self,
        asset_id: str,
        semaphore: asyncio.Semaphore,
    ) -> Dict[str, Optional[str]]:
        if not self.session:
            raise RuntimeError("Client session is not initialized")

        url = f"{ARCHIVE_ASSET_URL}/{asset_id}/archive"

        async with semaphore:
            for attempt in range(1, 4):
                try:
                    async with self.session.patch(url, json={}) as response:
                        text = await response.text()
                        if response.status in (200, 204):
                            return {
                                "asset_id": asset_id,
                                "operation": "archive",
                                "status": "success",
                                "status_code": str(response.status),
                                "message": "",
                            }

                        if response.status in RETRY_STATUS_CODES and attempt < 3:
                            await asyncio.sleep(2**attempt)
                            continue

                        return {
                            "asset_id": asset_id,
                            "operation": "archive",
                            "status": "error",
                            "status_code": str(response.status),
                            "message": text or response.reason,
                        }
                except aiohttp.ClientError as error:
                    if attempt < 3:
                        await asyncio.sleep(2**attempt)
                        continue
                    return {
                        "asset_id": asset_id,
                        "operation": "archive",
                        "status": "error",
                        "status_code": None,
                        "message": str(error),
                    }

    async def delete_asset(
        self,
        asset_id: str,
        semaphore: asyncio.Semaphore,
    ) -> Dict[str, Optional[str]]:
        if not self.session:
            raise RuntimeError("Client session is not initialized")

        url = f"{DELETE_ASSET_URL}/{asset_id}"

        async with semaphore:
            for attempt in range(1, 4):
                try:
                    async with self.session.delete(url) as response:
                        text = await response.text()
                        if response.status in (200, 204):
                            return {
                                "asset_id": asset_id,
                                "operation": "delete",
                                "status": "success",
                                "status_code": str(response.status),
                                "message": "",
                            }

                        if response.status in RETRY_STATUS_CODES and attempt < 3:
                            await asyncio.sleep(2**attempt)
                            continue

                        return {
                            "asset_id": asset_id,
                            "operation": "delete",
                            "status": "error",
                            "status_code": str(response.status),
                            "message": text or response.reason,
                        }
                except aiohttp.ClientError as error:
                    if attempt < 3:
                        await asyncio.sleep(2**attempt)
                        continue
                    return {
                        "asset_id": asset_id,
                        "operation": "delete",
                        "status": "error",
                        "status_code": None,
                        "message": str(error),
                    }


def load_assets_from_csv(csv_path: Path) -> List[Dict]:
    if not csv_path.exists():
        print(f"No CSV found at {csv_path}. Falling back to API fetch.")
        return []

    with csv_path.open(newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        if not reader.fieldnames:
            print(f"CSV at {csv_path} has no headers. Falling back to API fetch.")
            return []

        # Look for common asset ID column names
        asset_id_column = None
        for col in reader.fieldnames:
            if col.lower() in ["asset_id", "id", "uuid"]:
                asset_id_column = col
                break

        if not asset_id_column:
            print(
                f"CSV at {csv_path} must include one of: asset_id, id, uuid. "
                "No rows will be processed from this file."
            )
            return []

        # Check for optional state column
        state_column = None
        for col in reader.fieldnames:
            if col.lower() == "state":
                state_column = col
                break

        rows: List[Dict] = []
        for row in reader:
            asset_id = (row.get(asset_id_column) or "").strip()
            if asset_id:
                asset_info = {"id": asset_id, "state": "ASSET_STATE_UNSPECIFIED"}
                if state_column:
                    state = (row.get(state_column) or "").strip()
                    if state:
                        asset_info["state"] = state
                rows.append(asset_info)

        if not rows:
            print(f"CSV at {csv_path} is empty. Falling back to API fetch.")
        else:
            print(f"Loaded {len(rows)} assets from {csv_path}.")

        return rows


async def collect_assets_from_api(
    client: SafetyCultureAssetsClient,
) -> Tuple[List[Dict], int]:
    assets_list: List[Dict] = []
    total_assets = 0

    async for page_number, assets in client.stream_assets_cursor():
        total_assets += len(assets)
        for asset in assets:
            if asset.get("id"):
                assets_list.append(
                    {
                        "id": asset.get("id"),
                        "state": asset.get("state", "ASSET_STATE_UNSPECIFIED"),
                    }
                )
        print(
            f"Page {page_number}: {len(assets)} assets, "
            f"{len(assets_list)} total collected so far."
        )

        # Safety limit for testing
        if TEST_LIMIT and len(assets_list) >= TEST_LIMIT:
            print(f"Reached test limit of {TEST_LIMIT} assets. Stopping collection.")
            break

    return assets_list, total_assets


def deduplicate_assets(assets: List[Dict]) -> List[Dict]:
    seen = set()
    unique_assets = []
    for asset in assets:
        asset_id = asset.get("id")
        if asset_id in seen:
            continue
        seen.add(asset_id)
        unique_assets.append(asset)
    return unique_assets


async def archive_and_delete_assets(
    client: SafetyCultureAssetsClient,
    assets: List[Dict],
    log_path: Path,
) -> Dict[str, int]:
    semaphore = asyncio.Semaphore(DELETE_CONCURRENCY)
    archive_successes = 0
    archive_skipped = 0
    delete_successes = 0
    total_failures = 0

    fieldnames = ["asset_id", "operation", "status", "status_code", "message"]
    with log_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for start in range(0, len(assets), 200):
            chunk = assets[start : start + 200]

            # Step 1: Archive non-archived assets
            archive_tasks = []
            for asset in chunk:
                if asset.get("state") != "ASSET_STATE_ARCHIVED":
                    archive_tasks.append(client.archive_asset(asset["id"], semaphore))
                else:
                    archive_skipped += 1

            if archive_tasks:
                print(
                    f"Archiving {len(archive_tasks)} active assets "
                    f"({archive_skipped} already archived)..."
                )
                archive_results = await asyncio.gather(*archive_tasks)

                for result in archive_results:
                    writer.writerow(result)
                    if result["status"] == "success":
                        archive_successes += 1
                    else:
                        total_failures += 1
                csvfile.flush()

            # Step 2: Delete all assets in chunk (now all should be archived)
            delete_tasks = [
                client.delete_asset(asset["id"], semaphore) for asset in chunk
            ]
            delete_results = await asyncio.gather(*delete_tasks)

            for result in delete_results:
                writer.writerow(result)
                if result["status"] == "success":
                    delete_successes += 1
                else:
                    total_failures += 1

            processed = start + len(chunk)
            print(f"Processed {processed}/{len(assets)} assets...")
            csvfile.flush()

    return {
        "archive_successes": archive_successes,
        "archive_skipped": archive_skipped,
        "delete_successes": delete_successes,
        "failures": total_failures,
    }


def build_log_path(base_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return base_dir / f"delete_assets_log_{timestamp}.csv"


async def main() -> int:
    if not TOKEN:
        print("Error: set TOKEN at the top of main.py before running.")
        return 1

    script_dir = Path(__file__).parent
    csv_path = script_dir / INPUT_CSV_NAME

    csv_assets = load_assets_from_csv(csv_path)

    async with SafetyCultureAssetsClient(TOKEN) as client:
        if csv_assets:
            assets = csv_assets
            total_assets = len(assets)
            source = "CSV"
        else:
            print("Fetching assets from API...")
            assets, total_assets = await collect_assets_from_api(client)
            source = "API"

        if not assets:
            print("No assets found to delete. Exiting.")
            return 0

        unique_assets = deduplicate_assets(assets)
        if len(unique_assets) < len(assets):
            print(f"Deduplicated assets: {len(assets)} -> {len(unique_assets)}.")
        assets = unique_assets

        # Count assets by state
        active_count = sum(
            1 for a in assets if a.get("state") != "ASSET_STATE_ARCHIVED"
        )
        archived_count = sum(
            1 for a in assets if a.get("state") == "ASSET_STATE_ARCHIVED"
        )

        print(
            f"Processing {len(assets)} assets "
            f"(source: {source}, total scanned: {total_assets})"
        )
        print(f"  - {active_count} active assets (will archive first)")
        print(f"  - {archived_count} already archived assets")
        print(f"Concurrency: {DELETE_CONCURRENCY}")

        log_path = build_log_path(script_dir)
        summary = await archive_and_delete_assets(client, assets, log_path)

        # Print summary with colors
        print(f"\n{Colors.BOLD}Operation complete.{Colors.RESET}")
        print(f"\n{Colors.BOLD}Archives:{Colors.RESET}")
        if summary["archive_successes"] > 0:
            print(
                f"  - {Colors.GREEN}Successfully archived: "
                f"{summary['archive_successes']}{Colors.RESET}"
            )
        if summary["archive_skipped"] > 0:
            print(
                f"  - {Colors.YELLOW}Already archived (skipped): "
                f"{summary['archive_skipped']}{Colors.RESET}"
            )

        print(f"\n{Colors.BOLD}Deletions:{Colors.RESET}")
        if summary["delete_successes"] > 0:
            print(
                f"  - {Colors.GREEN}Successfully deleted: "
                f"{summary['delete_successes']}{Colors.RESET}"
            )

        if summary["failures"] > 0:
            print(
                f"\n{Colors.RED}Total failures: " f"{summary['failures']}{Colors.RESET}"
            )
        else:
            print(f"\n{Colors.GREEN}Total failures: 0{Colors.RESET}")

        print(f"\n{Colors.BLUE}Log written to: {log_path}{Colors.RESET}")

    return 0


if __name__ == "__main__":
    asyncio.run(main())
