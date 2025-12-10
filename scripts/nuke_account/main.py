import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import aiohttp
from tqdm import tqdm

TOKEN = ""  # Set your SafetyCulture API token here

DEFAULT_BASE_URL = "https://api.safetyculture.io"
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}

ACTION_PAGE_SIZE = 100
ACTION_DELETE_BATCH_SIZE = 300
ASSET_PAGE_SIZE = 100
INVESTIGATION_PAGE_SIZE = 100
COMPANY_PAGE_SIZE = 100
CREDENTIAL_PAGE_SIZE = 100
OSHA_PAGE_SIZE = 100
OSHA_MAX_PAGE_NUMBER = 95
SITE_PAGE_SIZE = 500
SITE_DELETE_BATCH_SIZE = 40
DELETE_CONCURRENCY = 16
LIST_CONCURRENCY = 8
DELETE_FLUSH_THRESHOLD = 400


@dataclass
class ResourceStats:
    name: str
    fetched: int = 0
    deleted: int = 0
    failed: int = 0
    batches: int = 0
    errors: List[str] = field(default_factory=list)

    def record_failure(self, message: str, count: int = 1) -> None:
        self.failed += count
        self.errors.append(message)


class ProgressTracker:
    def __init__(self, name: str) -> None:
        self._lock = asyncio.Lock()
        self.fetch_bar = tqdm(
            total=0,
            desc=f"{name} fetched",
            unit="item",
            dynamic_ncols=True,
            leave=False,
        )
        self.delete_bar = tqdm(
            total=0,
            desc=f"{name} deleted",
            unit="item",
            dynamic_ncols=True,
            leave=False,
        )

    async def add_fetched(self, count: int) -> None:
        if count <= 0:
            return
        async with self._lock:
            self.fetch_bar.update(count)
            self.delete_bar.total += count
            self.delete_bar.refresh()

    async def add_deleted(self, count: int) -> None:
        if count <= 0:
            return
        async with self._lock:
            self.delete_bar.update(count)

    def close(self) -> None:
        self.fetch_bar.close()
        self.delete_bar.close()


def chunked(items: Sequence[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(items), size):
        yield list(items[i : i + size])


def build_next_page(base_url: str, next_path: Optional[str]) -> Optional[str]:
    if not next_path:
        return None
    if next_path.startswith("http"):
        return next_path
    normalized = next_path if next_path.startswith("/") else f"/{next_path}"
    return f"{base_url}{normalized}"


class SafetyCultureNuker:
    def __init__(
        self,
        token: str,
        base_url: str,
        delete_concurrency: int = DELETE_CONCURRENCY,
        list_concurrency: int = LIST_CONCURRENCY,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.delete_sem = asyncio.Semaphore(delete_concurrency)
        self.list_concurrency = list_concurrency
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "SafetyCultureNuker":
        headers = {
            "authorization": f"Bearer {self.token}",
            "accept": "application/json",
            "content-type": "application/json",
        }
        connector = aiohttp.TCPConnector(
            limit=self.list_concurrency * 4,
            limit_per_host=self.list_concurrency * 2,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        timeout = aiohttp.ClientTimeout(total=120, connect=15)
        self.session = aiohttp.ClientSession(
            headers=headers, connector=connector, timeout=timeout
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.session:
            await self.session.close()

    def _url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        normalized = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url}{normalized}"

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Any] = None,
        json_body: Optional[Dict[str, Any]] = None,
        expected_status: Tuple[int, ...] = (200, 201, 202, 204),
    ) -> Dict[str, Any]:
        if not self.session:
            raise RuntimeError("HTTP session not initialized")

        url = self._url(path)
        for attempt in range(1, 5):
            try:
                async with self.session.request(
                    method, url, params=params, json=json_body
                ) as response:
                    text = await response.text()
                    if response.status in expected_status:
                        if not text:
                            return {}
                        try:
                            return await response.json()
                        except aiohttp.ContentTypeError:
                            try:
                                return json.loads(text)
                            except json.JSONDecodeError:
                                return {}
                    if response.status in RETRY_STATUS_CODES and attempt < 4:
                        await asyncio.sleep(2**attempt)
                        continue
                    raise RuntimeError(
                        f"{method} {url} failed ({response.status}): {text}"
                    )
            except aiohttp.ClientError as error:
                if attempt < 4:
                    await asyncio.sleep(2**attempt)
                    continue
                raise RuntimeError(f"{method} {url} failed: {error}") from error
        return {}

    async def delete_actions(self) -> ResourceStats:
        stats = ResourceStats("actions")
        delete_tasks: List[asyncio.Task] = []
        tracker = ProgressTracker("actions")

        async def fetch_actions_page(offset: int) -> List[Dict[str, Any]]:
            payload: Dict[str, Any] = {
                "page_size": ACTION_PAGE_SIZE,
                "offset": offset,
                "without_count": True,
            }
            data = await self._request_json(
                "POST", "/tasks/v1/actions/list", json_body=payload
            )
            return data.get("actions", []) or []

        offset = 0

        try:
            while True:
                actions = await fetch_actions_page(offset)
                offset += ACTION_PAGE_SIZE
                ids: List[str] = []
                for action in actions:
                    task_data = action.get("task", {})
                    action_id = (
                        task_data.get("task_id")
                        or action.get("task_id")
                        or action.get("id")
                    )
                    if action_id:
                        ids.append(action_id)

                stats.fetched += len(ids)
                await tracker.add_fetched(len(ids))

                for batch in chunked(ids, ACTION_DELETE_BATCH_SIZE):
                    delete_tasks.append(
                        asyncio.create_task(
                            self._delete_actions_batch(batch, stats, tracker)
                        )
                    )
                    stats.batches += 1
                if delete_tasks:
                    await asyncio.gather(*delete_tasks)
                    delete_tasks.clear()

                if len(actions) < ACTION_PAGE_SIZE:
                    break

            return stats
        finally:
            tracker.close()

    async def _delete_actions_batch(
        self, action_ids: List[str], stats: ResourceStats, tracker: Optional[ProgressTracker]
    ) -> None:
        if not action_ids:
            return
        async with self.delete_sem:
            try:
                await self._request_json(
                    "POST",
                    "/tasks/v1/actions/delete",
                    json_body={"ids": action_ids},
                    expected_status=(200, 204),
                )
                stats.deleted += len(action_ids)
                if tracker:
                    await tracker.add_deleted(len(action_ids))
            except Exception as error:  # noqa: BLE001
                stats.record_failure(f"actions {action_ids[:3]}...: {error}", len(action_ids))

    async def delete_investigations(self) -> ResourceStats:
        stats = ResourceStats("issues")
        page_token: Optional[str] = None
        delete_tasks: List[asyncio.Task] = []
        tracker = ProgressTracker("issues")

        try:
            while True:
                params: Dict[str, Any] = {"page_size": INVESTIGATION_PAGE_SIZE}
                if page_token:
                    params["page_token"] = page_token

                data = await self._request_json(
                    "GET", "/incidents/v1/investigations", params=params
                )
                results = data.get("results", []) or []
                ids = [
                    item.get("investigation_id")
                    for item in results
                    if item.get("investigation_id")
                ]
                stats.fetched += len(ids)
                await tracker.add_fetched(len(ids))

                for inv_id in ids:
                    delete_tasks.append(
                        asyncio.create_task(
                            self._delete_single(
                                f"/incidents/v1/investigations/{inv_id}",
                                stats,
                                label=f"investigation {inv_id}",
                                tracker=tracker,
                            )
                        )
                    )

                if len(delete_tasks) >= DELETE_FLUSH_THRESHOLD:
                    await asyncio.gather(*delete_tasks)
                    delete_tasks.clear()
                if delete_tasks:
                    await asyncio.gather(*delete_tasks)
                    delete_tasks.clear()

                page_token = data.get("next_page_token")
                if not page_token:
                    break

            return stats
        finally:
            tracker.close()

    async def delete_inspections(self) -> ResourceStats:
        stats = ResourceStats("inspections")
        delete_tasks: List[asyncio.Task] = []
        next_url: Optional[str] = f"{self.base_url}/feed/inspections"
        tracker = ProgressTracker("inspections")

        try:
            while next_url:
                data = await self._request_json("GET", next_url)
                inspections = data.get("data", []) or []
                stats.fetched += len(inspections)
                await tracker.add_fetched(len(inspections))

                for inspection in inspections:
                    inspection_id = inspection.get("id")
                    if not inspection_id:
                        continue
                    delete_tasks.append(
                        asyncio.create_task(
                            self._delete_single(
                                f"/inspections/v1/inspections/{inspection_id}",
                                stats,
                                label=f"inspection {inspection_id}",
                                tracker=tracker,
                                archive_path=f"/inspections/v1/inspections/{inspection_id}/archive",
                            )
                        )
                    )

                if delete_tasks:
                    await asyncio.gather(*delete_tasks)
                    delete_tasks.clear()

                metadata = data.get("metadata", {}) or {}
                next_url = build_next_page(self.base_url, metadata.get("next_page"))

            return stats
        finally:
            tracker.close()

    async def delete_assets(self) -> ResourceStats:
        stats = ResourceStats("assets")
        delete_tasks: List[asyncio.Task] = []
        tracker = ProgressTracker("assets")
        seen_ids: set[str] = set()
        in_progress: set[asyncio.Task] = set()

        try:
            for state_filter in (None, "ASSET_STATE_ARCHIVED"):
                page_token: Optional[str] = None
                while True:
                    payload: Dict[str, Any] = {"page_size": ASSET_PAGE_SIZE}
                    if page_token:
                        payload["page_token"] = page_token
                    if state_filter:
                        payload["asset_filters"] = [{"state": state_filter}]

                    data = await self._request_json(
                        "POST", "/assets/v1/assets/list", json_body=payload
                    )
                    assets = data.get("assets", []) or []
                    ids: List[str] = []
                    for asset in assets:
                        asset_id = asset.get("id")
                        if not asset_id or asset_id in seen_ids:
                            continue
                        seen_ids.add(asset_id)
                        ids.append(asset_id)

                    stats.fetched += len(ids)
                    await tracker.add_fetched(len(ids))

                    for asset_id in ids:
                        task = asyncio.create_task(
                            self._delete_single(
                                f"/assets/v1/assets/{asset_id}",
                                stats,
                                label=f"asset {asset_id}",
                                tracker=tracker,
                                archive_path=f"/assets/v1/assets/{asset_id}/archive",
                            )
                        )
                        delete_tasks.append(task)

                    if delete_tasks:
                        await asyncio.gather(*delete_tasks)
                        delete_tasks.clear()

                    page_token = data.get("next_page_token")
                    if not page_token:
                        break

            return stats
        finally:
            tracker.close()

    async def delete_credentials(self) -> ResourceStats:
        stats = ResourceStats("credentials")
        page_token: Optional[str] = None
        delete_tasks: List[asyncio.Task] = []
        tracker = ProgressTracker("credentials")

        try:
            while True:
                payload: Dict[str, Any] = {"page_size": CREDENTIAL_PAGE_SIZE}
                if page_token:
                    payload["page_token"] = page_token

                data = await self._request_json(
                    "POST", "/credentials/v1/credentials", json_body=payload
                )
                versions = data.get("latest_document_versions", []) or []
                stats.fetched += len(versions)
                await tracker.add_fetched(len(versions))

                for version in versions:
                    document_id = version.get("document_id")
                    doc_type = version.get("document_type_id") or version.get(
                        "document_type", {}
                    ).get("id")
                    user_info = version.get("subject_user") or {}
                    user_id = (
                        version.get("subject_user_id")
                        or user_info.get("id")
                        or user_info.get("user_id")
                    )
                    if not (document_id and doc_type and user_id):
                        stats.record_failure(
                            f"credential missing identifiers: doc={document_id}, type={doc_type}, user={user_id}"
                        )
                        continue
                    params = {
                        "document_id": document_id,
                        "document_type_id": doc_type,
                        "user_id": user_id,
                    }
                    delete_tasks.append(
                        asyncio.create_task(
                            self._delete_with_params(
                                "/credentials/v1/credential",
                                params,
                                stats,
                                label=f"credential {document_id}",
                                tracker=tracker,
                            )
                        )
                    )

                if delete_tasks:
                    await asyncio.gather(*delete_tasks)
                    delete_tasks.clear()

                page_token = data.get("next_page_token")
                if not page_token:
                    break

            return stats
        finally:
            tracker.close()

    async def delete_companies(self) -> ResourceStats:
        stats = ResourceStats("companies")
        page_token: Optional[str] = None
        delete_tasks: List[asyncio.Task] = []
        tracker = ProgressTracker("companies")

        try:
            while True:
                payload: Dict[str, Any] = {"page_size": COMPANY_PAGE_SIZE}
                if page_token:
                    payload["page_token"] = page_token

                data = await self._request_json(
                    "POST", "/companies/v1beta/companies", json_body=payload
                )
                companies = data.get("contractor_company_list", []) or []
                stats.fetched += len(companies)
                await tracker.add_fetched(len(companies))

                for company in companies:
                    company_id = company.get("company_id")
                    company_type = (
                        (company.get("company_type") or {}).get("id")
                        or company.get("company_type_id")
                    )
                    if not company_id:
                        continue
                    params = {"company_id": company_id}
                    if company_type:
                        params["company_type_id"] = company_type
                    delete_tasks.append(
                        asyncio.create_task(
                            self._delete_with_params(
                                "/companies/v1beta/company",
                                params,
                                stats,
                                label=f"company {company_id}",
                                tracker=tracker,
                            )
                        )
                    )

                if delete_tasks:
                    await asyncio.gather(*delete_tasks)
                    delete_tasks.clear()

                page_token = data.get("next_page_token")
                if not page_token:
                    break

            return stats
        finally:
            tracker.close()

    async def delete_osha_cases(self) -> ResourceStats:
        stats = ResourceStats("osha_cases")
        delete_tasks: List[asyncio.Task] = []
        tracker = ProgressTracker("osha cases")

        async def fetch_cases_page(
            page_number: Optional[int] = None, page_token: Optional[str] = None
        ) -> Dict[str, Any]:
            params: Dict[str, Any] = {"page_size": OSHA_PAGE_SIZE}
            if page_number is not None:
                params["page_number"] = page_number
            if page_token:
                params["page_token"] = page_token
            return await self._request_json(
                "GET", "/incidents/v1/osha/cases", params=params
            )

        page_number = 1
        in_flight: List[Tuple[int, asyncio.Task]] = []
        token_mode = False
        next_token: Optional[str] = None

        try:
            while True:
                while len(in_flight) < self.list_concurrency and not token_mode:
                    in_flight.append(
                        (
                            page_number,
                            asyncio.create_task(fetch_cases_page(page_number=page_number)),
                        )
                    )
                    page_number += 1

                if not in_flight and not token_mode:
                    break

                if in_flight:
                    current_page, task = in_flight.pop(0)
                    data = await task
                    cases = data.get("results", []) or []
                    stats.fetched += len(cases)
                    await tracker.add_fetched(len(cases))

                    for case in cases:
                        case_id = case.get("case_id") or case.get("id")
                        if not case_id:
                            continue
                        delete_tasks.append(
                            asyncio.create_task(
                                self._delete_single(
                                    f"/incidents/v1/osha/cases/{case_id}",
                                    stats,
                                    label=f"osha case {case_id}",
                                    tracker=tracker,
                                )
                            )
                        )
                    if delete_tasks:
                        await asyncio.gather(*delete_tasks)
                        delete_tasks.clear()

                    next_token = data.get("next_page_token") or next_token
                    if len(cases) < OSHA_PAGE_SIZE or current_page >= OSHA_MAX_PAGE_NUMBER:
                        token_mode = bool(next_token)
                        if not token_mode and len(cases) < OSHA_PAGE_SIZE:
                            break

                if token_mode and next_token:
                    data = await fetch_cases_page(page_token=next_token)
                    cases = data.get("results", []) or []
                    stats.fetched += len(cases)
                    await tracker.add_fetched(len(cases))
                    for case in cases:
                        case_id = case.get("case_id") or case.get("id")
                        if not case_id:
                            continue
                        delete_tasks.append(
                            asyncio.create_task(
                                self._delete_single(
                                    f"/incidents/v1/osha/cases/{case_id}",
                                    stats,
                                    label=f"osha case {case_id}",
                                    tracker=tracker,
                                )
                            )
                        )
                    if delete_tasks:
                        await asyncio.gather(*delete_tasks)
                        delete_tasks.clear()

                    next_token = data.get("next_page_token")
                    if not next_token:
                        break

            return stats
        finally:
            tracker.close()

    async def delete_templates(self) -> ResourceStats:
        stats = ResourceStats("templates")
        delete_tasks: List[asyncio.Task] = []
        next_url: Optional[str] = f"{self.base_url}/feed/templates"
        tracker = ProgressTracker("templates")

        try:
            while next_url:
                data = await self._request_json("GET", next_url)
                templates = data.get("data", []) or []
                stats.fetched += len(templates)
                await tracker.add_fetched(len(templates))

                for template in templates:
                    template_id = template.get("id")
                    if not template_id:
                        continue
                    delete_tasks.append(
                        asyncio.create_task(
                            self._delete_single(
                                f"/templates/v1/templates/{template_id}",
                                stats,
                                label=f"template {template_id}",
                                tracker=tracker,
                                archive_path=f"/templates/v1/templates/{template_id}/archive",
                            )
                        )
                    )

                if delete_tasks:
                    await asyncio.gather(*delete_tasks)
                    delete_tasks.clear()

                metadata = data.get("metadata", {}) or {}
                next_url = build_next_page(self.base_url, metadata.get("next_page"))

            return stats
        finally:
            tracker.close()

    async def delete_sites(self) -> ResourceStats:
        stats = ResourceStats("sites")
        page_token: Optional[str] = None
        delete_tasks: List[asyncio.Task] = []
        tracker = ProgressTracker("sites")

        try:
            while True:
                payload: Dict[str, Any] = {
                    "limit": SITE_PAGE_SIZE,
                    "include_deleted_folders": True,
                }
                if page_token:
                    payload["page_token"] = page_token

                data = await self._request_json(
                    "POST", "/directory/v1/folders/search", json_body=payload
                )
                folders = data.get("folders", []) or []
                ids: List[str] = []
                for folder_entry in folders:
                    folder_data = folder_entry.get("folder") or folder_entry
                    folder_id = folder_data.get("id")
                    ancestors = folder_entry.get("ancestors") or []
                    is_deleted = folder_data.get("deleted") is True
                    if folder_id and not is_deleted:
                        ids.append(folder_id)

                stats.fetched += len(ids)
                await tracker.add_fetched(len(ids))

                for batch in chunked(ids, SITE_DELETE_BATCH_SIZE):
                    delete_tasks.append(
                        asyncio.create_task(
                            self._delete_site_batch(
                                batch, stats, cascade_up=True, tracker=tracker
                            )
                        )
                    )
                    stats.batches += 1

                if delete_tasks:
                    await asyncio.gather(*delete_tasks)
                    delete_tasks.clear()

                page_token = data.get("next_page_token")
                if not page_token:
                    break

            return stats
        finally:
            tracker.close()

    async def _delete_site_batch(
        self,
        folder_ids: List[str],
        stats: ResourceStats,
        cascade_up: bool,
        tracker: Optional[ProgressTracker],
    ) -> None:
        if not folder_ids:
            return
        params: List[Tuple[str, str]] = [
            ("cascade_up", "true" if cascade_up else "false")
        ]
        params.extend([("folder_ids", folder_id) for folder_id in folder_ids])
        async with self.delete_sem:
            try:
                await self._request_json(
                    "DELETE",
                    "/directory/v1/folders",
                    params=params,
                    expected_status=(200, 204),
                )
                stats.deleted += len(folder_ids)
                if tracker:
                    await tracker.add_deleted(len(folder_ids))
            except Exception as error:  # noqa: BLE001
                stats.record_failure(f"sites {folder_ids[:3]}...: {error}", len(folder_ids))

    async def _delete_single(
        self,
        path: str,
        stats: ResourceStats,
        label: str,
        tracker: Optional[ProgressTracker],
        archive_path: Optional[str] = None,
    ) -> None:
        async with self.delete_sem:
            try:
                if archive_path:
                    # Some objects require an archive before delete
                    await self._request_json(
                        "POST", archive_path, expected_status=(200, 204)
                    )
                await self._request_json("DELETE", path, expected_status=(200, 204))
                stats.deleted += 1
                if tracker:
                    await tracker.add_deleted(1)
            except Exception as error:  # noqa: BLE001
                stats.record_failure(f"{label}: {error}")

    async def _delete_with_params(
        self,
        path: str,
        params: Dict[str, Any],
        stats: ResourceStats,
        label: str,
        tracker: Optional[ProgressTracker],
    ) -> None:
        async with self.delete_sem:
            try:
                await self._request_json(
                    "DELETE", path, params=params, expected_status=(200, 204)
                )
                stats.deleted += 1
                if tracker:
                    await tracker.add_deleted(1)
            except Exception as error:  # noqa: BLE001
                stats.record_failure(f"{label}: {error}")


async def run_nuke(args: argparse.Namespace) -> None:
    token = args.token or os.environ.get("SC_API_TOKEN") or TOKEN
    if not token:
        print("API token is required via --token or SC_API_TOKEN environment variable.")
        sys.exit(1)

    skip_resources = {item.strip().lower() for item in args.skip.split(",") if item}
    targets = [
        ("actions", SafetyCultureNuker.delete_actions),
        ("issues", SafetyCultureNuker.delete_investigations),
        ("inspections", SafetyCultureNuker.delete_inspections),
        ("assets", SafetyCultureNuker.delete_assets),
        ("credentials", SafetyCultureNuker.delete_credentials),
        ("companies", SafetyCultureNuker.delete_companies),
        ("osha_cases", SafetyCultureNuker.delete_osha_cases),
        ("templates", SafetyCultureNuker.delete_templates),
        ("sites", SafetyCultureNuker.delete_sites),
    ]

    planned = [name for name, _ in targets if name not in skip_resources]
    print("⚠️  This will delete all data for the following resources:")
    for name in planned:
        print(f" - {name}")
    print(f"API Base: {args.base_url}")

    if not args.yes:
        confirm = input('Type "NUKE" to continue: ').strip()
        if confirm.upper() != "NUKE":
            print("Aborted.")
            sys.exit(0)

    async with SafetyCultureNuker(
        token,
        base_url=args.base_url,
        delete_concurrency=args.delete_concurrency,
        list_concurrency=args.list_concurrency,
    ) as nuker:
        summaries: List[ResourceStats] = []
        for name, method in targets:
            if name in skip_resources:
                continue
            print(f"\n🚧 Deleting {name}...")
            stats: ResourceStats = await method(nuker)  # type: ignore[misc]
            summaries.append(stats)
            print(
                f"   -> {stats.deleted}/{stats.fetched} deleted "
                f"({stats.failed} failed)"
            )
            if stats.errors:
                for err in stats.errors[:5]:
                    print(f"      ⚠️  {err}")
                if len(stats.errors) > 5:
                    print(f"      ... {len(stats.errors) - 5} more errors not shown")

    print("\n✅ Nuke run finished")
    any_failed = any(s.failed > 0 for s in summaries)
    badge = "🔴" if any_failed else "🟢"
    for stats in summaries:
        if stats.fetched == 0:
            print(f"{badge} {stats.name}: no {stats.name} to delete")
            continue
        print(
            f"{badge} {stats.name}: deleted {stats.deleted}/{stats.fetched} "
            f"(failed {stats.failed}, batches {stats.batches})"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dangerous: delete all SafetyCulture resources in an org."
    )
    parser.add_argument(
        "--token",
        help="SafetyCulture API token (or set SC_API_TOKEN)",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"API base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--skip",
        default="",
        help="Comma separated list of resources to skip "
        "(actions,issues,inspections,assets,credentials,companies,osha_cases,templates,sites)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help='Skip interactive confirmation (otherwise type "NUKE" to proceed).',
    )
    parser.add_argument(
        "--delete-concurrency",
        type=int,
        default=DELETE_CONCURRENCY,
        help=f"Concurrent delete requests (default: {DELETE_CONCURRENCY})",
    )
    parser.add_argument(
        "--list-concurrency",
        type=int,
        default=LIST_CONCURRENCY,
        help=f"Concurrent list requests for offset-enabled endpoints (default: {LIST_CONCURRENCY})",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        asyncio.run(run_nuke(parse_args()))
    except KeyboardInterrupt:
        print("\nInterrupted by user")
