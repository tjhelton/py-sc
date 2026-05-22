import asyncio
import csv
import json
import os
import random
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import requests
from tqdm.asyncio import tqdm

TOKEN = ""  # Set your SafetyCulture API token here
BASE_URL = "https://api.safetyculture.io"

HEADERS = {
    "accept": "application/json",
    "content-type": "application/json",
    "authorization": f"Bearer {TOKEN}",
}

CREATE_ITEM_ERROR_RE = re.compile(r'item\s+\\?"([0-9a-fA-F-]{36})\\?"')
MAX_CREATE_RETRIES = 15

RETRYABLE_STATUSES = {408, 425, 429, 500, 502, 503, 504}
MAX_HTTP_RETRIES = 5
RETRY_BASE_DELAY = 1.0
RETRY_MAX_DELAY = 30.0


def _backoff_delay(attempt: int) -> float:
    base = min(RETRY_BASE_DELAY * (2**attempt), RETRY_MAX_DELAY)
    return base + random.uniform(0, base * 0.25)


def _log_retry(method: str, url: str, attempt: int, reason: str) -> None:
    pbar = tqdm.write if tqdm else print
    short_url = url.replace(BASE_URL, "")
    pbar(f"  ⟳ retry {attempt}/{MAX_HTTP_RETRIES} {method} {short_url}: {reason[:120]}")


def sync_request_with_retry(
    method: str,
    url: str,
    *,
    json_body: Optional[Any] = None,
    max_retries: int = MAX_HTTP_RETRIES,
) -> requests.Response:
    """Synchronous request with retries on 5xx/429/network errors."""
    last_exc: Optional[BaseException] = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.request(
                method, url, headers=HEADERS, json=json_body, timeout=30
            )
            if response.status_code in RETRYABLE_STATUSES and attempt < max_retries:
                _log_retry(method, url, attempt + 1, f"HTTP {response.status_code}")
                time.sleep(_backoff_delay(attempt))
                continue
            return response
        except requests.RequestException as exc:
            last_exc = exc
            if attempt >= max_retries:
                raise
            _log_retry(method, url, attempt + 1, str(exc))
            time.sleep(_backoff_delay(attempt))

    raise last_exc if last_exc else RuntimeError("exhausted retries")


async def async_request_with_retry(
    session: aiohttp.ClientSession,
    method: str,
    url: str,
    *,
    json_body: Optional[Any] = None,
    max_retries: int = MAX_HTTP_RETRIES,
) -> Tuple[Optional[int], str]:
    """Async request with retries on 5xx/429/network errors.

    Returns (status, body_text). status=None means the request never
    completed (all attempts raised exceptions); body holds the last error.
    """
    last_error = "exhausted retries"
    for attempt in range(max_retries + 1):
        try:
            kwargs: Dict[str, Any] = {}
            if json_body is not None:
                kwargs["json"] = json_body
            async with session.request(method, url, **kwargs) as response:
                status = response.status
                body = await response.text()

                if status in RETRYABLE_STATUSES and attempt < max_retries:
                    _log_retry(method, url, attempt + 1, f"HTTP {status}")
                    await asyncio.sleep(_backoff_delay(attempt))
                    continue

                return status, body
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt >= max_retries:
                return None, last_error
            _log_retry(method, url, attempt + 1, last_error)
            await asyncio.sleep(_backoff_delay(attempt))

    return None, last_error


def parse_offending_item_id(error_text: str) -> Optional[str]:
    """Pull the rejected item_id out of a create-inspection error body."""
    if not error_text:
        return None

    try:
        body = json.loads(error_text)
        message = body.get("message", "")
        match = CREATE_ITEM_ERROR_RE.search(message)
        if match:
            return match.group(1)
        for detail in body.get("details", []) or []:
            for value in (detail or {}).values():
                if isinstance(value, str):
                    match = CREATE_ITEM_ERROR_RE.search(value)
                    if match:
                        return match.group(1)
    except (ValueError, AttributeError):
        pass

    match = CREATE_ITEM_ERROR_RE.search(error_text)
    return match.group(1) if match else None


ANSWERABLE_TYPES = {
    "ITEM_TYPE_TEXT",
    "ITEM_TYPE_NUMBER",
    "ITEM_TYPE_PARAGRAPH",
    "ITEM_TYPE_DATETIME",
    "ITEM_TYPE_LOCATION",
    "ITEM_TYPE_CHECKBOX",
    "ITEM_TYPE_QUESTION",
    "ITEM_TYPE_TEMPERATURE",
    "ITEM_TYPE_SLIDER",
    "ITEM_TYPE_ASSET",
    "ITEM_TYPE_SITE",
    "ITEM_TYPE_COMPANY",
}

UNFILLABLE_TYPES = {
    "ITEM_TYPE_MEDIA",
    "ITEM_TYPE_DRAWING",
    "ITEM_TYPE_SIGNATURE",
    "ITEM_TYPE_TABLE",
}

LOREM_WORDS = [
    "lorem",
    "ipsum",
    "dolor",
    "sit",
    "amet",
    "consectetur",
    "adipiscing",
    "elit",
    "sed",
    "do",
    "eiusmod",
    "tempor",
    "incididunt",
    "ut",
    "labore",
    "magna",
    "aliqua",
    "enim",
    "minim",
    "veniam",
    "quis",
    "nostrud",
]


def random_text(min_words: int = 2, max_words: int = 5) -> str:
    count = random.randint(min_words, max_words)
    return " ".join(random.choices(LOREM_WORDS, k=count)).capitalize()


def random_paragraph() -> str:
    return ". ".join(random_text(4, 8) for _ in range(random.randint(2, 4))) + "."


def random_iso_datetime() -> str:
    offset_minutes = random.randint(0, 60 * 24 * 7)
    dt = datetime.now(timezone.utc) - timedelta(minutes=offset_minutes)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_paginated(path: str, label: str, page_limit: int = 100) -> List[Dict]:
    items: List[Dict] = []
    url: Optional[str] = f"{BASE_URL}{path}"

    print(f"📋 Fetching {label}...")
    while url:
        sep = "&" if "?" in url else "?"
        page_url = url if "limit=" in url else f"{url}{sep}limit={page_limit}"
        try:
            response = sync_request_with_retry("GET", page_url)
            response.raise_for_status()
        except requests.RequestException as error:
            print(f"  ⚠️  {label} fetch failed (after retries): {error}")
            break

        data = response.json()
        page_items = data.get("data", [])
        items.extend(page_items)
        print(f"  Fetched {len(items)} {label} so far...")

        next_page = data.get("metadata", {}).get("next_page")
        if not next_page:
            break
        url = next_page if next_page.startswith("http") else f"{BASE_URL}{next_page}"

    print(f"  ✅ {label}: {len(items)} total\n")
    return items


def fetch_all_templates() -> List[Dict]:
    templates = fetch_paginated("/feed/templates?archived=false", "active templates")
    return [t for t in templates if not t.get("archived", False)]


def fetch_all_sites() -> List[str]:
    sites = fetch_paginated("/feed/sites", "sites")
    return [
        s["site_uuid"] for s in sites if s.get("site_uuid") and not s.get("deleted")
    ]


def fetch_all_assets() -> List[str]:
    assets = fetch_paginated("/feed/assets", "assets")
    return [a["id"] for a in assets if a.get("id")]


def fetch_all_companies() -> List[str]:
    companies = fetch_paginated("/companies/v1/feed/companies", "companies")
    return [c["company_id"] for c in companies if c.get("company_id")]


def build_template_response_set_lookup(template_def: Dict) -> Dict[str, List[str]]:
    """Inline template response sets only. Global sets are fetched on demand."""
    lookup: Dict[str, List[str]] = {}
    response_sets = template_def.get("response_sets") or {}

    for rs in response_sets.get("template_response_sets") or []:
        rs_id = rs.get("response_set_id")
        ids = [
            r.get("response_id")
            for r in (rs.get("responses") or [])
            if r.get("response_id")
        ]
        if rs_id and ids:
            lookup[rs_id] = ids

    return lookup


class OrgContext:
    """Org-wide references (sites, assets, companies, global response sets)."""

    def __init__(self):
        self.site_ids: List[str] = []
        self.asset_ids: List[str] = []
        self.company_ids: List[str] = []
        self.global_response_set_cache: Dict[str, List[str]] = {}
        self._grs_lock = asyncio.Lock()

    def preload_org_references(self):
        self.site_ids = fetch_all_sites()
        self.asset_ids = fetch_all_assets()
        try:
            self.company_ids = fetch_all_companies()
        except Exception as error:
            print(f"  ⚠️  Skipping companies (fetch failed): {error}\n")
            self.company_ids = []

    async def get_global_response_ids(
        self, session: aiohttp.ClientSession, response_set_id: str
    ) -> List[str]:
        async with self._grs_lock:
            if response_set_id in self.global_response_set_cache:
                return self.global_response_set_cache[response_set_id]

        url = f"{BASE_URL}/response_sets/{response_set_id}"
        ids: List[str] = []
        status, body = await async_request_with_retry(session, "GET", url)
        if status == 200:
            try:
                payload = json.loads(body)
                ids = [r["id"] for r in (payload.get("responses") or []) if r.get("id")]
            except (ValueError, TypeError):
                ids = []

        async with self._grs_lock:
            self.global_response_set_cache[response_set_id] = ids

        return ids


def random_location_value() -> Dict:
    return {"label": random_text(2, 4)}


async def build_random_item(
    template_item: Dict,
    template_response_set_lookup: Dict[str, List[str]],
    org_context: OrgContext,
    session: aiohttp.ClientSession,
) -> Optional[Dict]:
    """Build an InspectionItem payload with a random value for a template item."""
    item_type = template_item.get("type")
    item_id = template_item.get("item_id")

    if not item_id or item_type not in ANSWERABLE_TYPES:
        return None

    item: Dict = {"item_id": item_id, "item_type": item_type}

    if item_type == "ITEM_TYPE_TEXT":
        item["text_item"] = {"value": random_text()}
    elif item_type == "ITEM_TYPE_NUMBER":
        item["number_item"] = {"value": round(random.uniform(0, 1000), 2)}
    elif item_type == "ITEM_TYPE_PARAGRAPH":
        item["paragraph_item"] = {"value": random_paragraph()}
    elif item_type == "ITEM_TYPE_DATETIME":
        item["datetime_item"] = {"value": random_iso_datetime()}
    elif item_type == "ITEM_TYPE_LOCATION":
        item["location_item"] = random_location_value()
    elif item_type == "ITEM_TYPE_CHECKBOX":
        item["checkbox_item"] = {"value": random.choice([True, False])}
    elif item_type == "ITEM_TYPE_QUESTION":
        question_def = template_item.get("question_item") or {}
        rs_id = question_def.get("response_set_id")
        if not rs_id:
            return None
        response_ids = template_response_set_lookup.get(rs_id)
        if not response_ids:
            response_ids = await org_context.get_global_response_ids(session, rs_id)
        if not response_ids:
            return None
        item["question_item"] = {"response_ids": [random.choice(response_ids)]}
    elif item_type == "ITEM_TYPE_TEMPERATURE":
        item["temperature_item"] = {
            "value": round(random.uniform(-10, 40), 1),
            "recorded_at": random_iso_datetime(),
        }
    elif item_type == "ITEM_TYPE_SLIDER":
        item["slider_item"] = {"value": round(random.uniform(0, 100), 2)}
    elif item_type == "ITEM_TYPE_SITE":
        if not org_context.site_ids:
            return None
        item["site_item"] = {"site_id": random.choice(org_context.site_ids)}
    elif item_type == "ITEM_TYPE_ASSET":
        if not org_context.asset_ids:
            return None
        item["asset_item"] = {"asset_id": random.choice(org_context.asset_ids)}
    elif item_type == "ITEM_TYPE_COMPANY":
        if not org_context.company_ids:
            return None
        item["company_item"] = {"company_id": random.choice(org_context.company_ids)}

    return item


async def build_inspection_items(
    template_def: Dict,
    org_context: OrgContext,
    session: aiohttp.ClientSession,
) -> Tuple[List[Dict], Dict[str, int]]:
    template_response_set_lookup = build_template_response_set_lookup(template_def)
    items_out: List[Dict] = []
    stats = {"filled": 0, "unfillable_mandatory_risk": 0}

    for template_item in template_def.get("items") or []:
        if template_item.get("type") in UNFILLABLE_TYPES:
            stats["unfillable_mandatory_risk"] += 1
            continue
        built = await build_random_item(
            template_item, template_response_set_lookup, org_context, session
        )
        if built is not None:
            items_out.append(built)

    stats["filled"] = len(items_out)
    return items_out, stats


class InspectionGenerator:
    def __init__(
        self,
        org_context: OrgContext,
        max_requests_per_minute: int = 300,
    ):
        self.org_context = org_context
        self.max_requests_per_minute = max_requests_per_minute
        self.semaphore_value = max(1, int(max_requests_per_minute / 60 * 1.5))
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore: Optional[asyncio.Semaphore] = None
        self.template_def_cache: Dict[str, Optional[Dict]] = {}
        self.template_def_lock = asyncio.Lock()
        self.csv_writer = None
        self.csv_file_handle = None
        self.output_file: Optional[str] = None

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=100, limit_per_host=50, ttl_dns_cache=300, use_dns_cache=True
        )
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        self.session = aiohttp.ClientSession(
            headers=HEADERS, connector=connector, timeout=timeout
        )
        self.semaphore = asyncio.Semaphore(self.semaphore_value)

        self.output_file = self._get_output_filename()
        self.csv_file_handle = open(self.output_file, "w", newline="", encoding="utf-8")
        self.csv_writer = csv.DictWriter(
            self.csv_file_handle,
            fieldnames=[
                "run_index",
                "template_id",
                "template_name",
                "inspection_id",
                "items_filled",
                "create_status",
                "complete_status",
                "error_message",
                "timestamp",
            ],
        )
        self.csv_writer.writeheader()
        self.csv_file_handle.flush()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.csv_file_handle:
            self.csv_file_handle.close()
        if self.session:
            await self.session.close()

    def _get_output_filename(self) -> str:
        base = "output"
        candidate = f"{base}.csv"
        counter = 1
        while os.path.exists(candidate):
            candidate = f"{base}_{counter}.csv"
            counter += 1
        return candidate

    def _write_row(self, row: Dict) -> None:
        self.csv_writer.writerow(row)
        self.csv_file_handle.flush()

    async def _get_template_definition(self, template_id: str) -> Optional[Dict]:
        async with self.template_def_lock:
            if template_id in self.template_def_cache:
                return self.template_def_cache[template_id]

        url = f"{BASE_URL}/templates/integration/v1/templates/{template_id}/definition"
        template_def: Optional[Dict] = None
        status, body = await async_request_with_retry(self.session, "GET", url)
        if status == 200:
            try:
                payload = json.loads(body)
                template_def = payload.get("template")
            except (ValueError, TypeError):
                template_def = None

        async with self.template_def_lock:
            self.template_def_cache[template_id] = template_def

        return template_def

    async def _create_inspection(
        self, template_id: str, items: List[Dict]
    ) -> Tuple[Optional[str], Optional[str], int]:
        """Create inspection, retrying after dropping any item the API rejects.

        Returns (inspection_id, error, dropped_count). HTTP-layer transient
        errors (5xx, 429, network) are already retried inside
        async_request_with_retry; this loop handles 4xx rejections that name
        a specific offending item_id.
        """
        url = f"{BASE_URL}/inspections/integration/v1/inspections"
        current_items = list(items)
        dropped = 0
        last_error: Optional[str] = None

        for _ in range(MAX_CREATE_RETRIES + 1):
            body = {"template_id": template_id, "items": current_items}
            status, response_body = await async_request_with_retry(
                self.session, "POST", url, json_body=body
            )

            if status is None:
                return None, response_body, dropped

            if status == 200:
                try:
                    payload = json.loads(response_body)
                except (ValueError, TypeError):
                    return None, "Invalid JSON in create response", dropped
                inspection_id = payload.get("inspection_identity", {}).get(
                    "inspection_id"
                )
                return inspection_id, None, dropped

            last_error = f"{status}: {response_body[:300]}"
            offending_id = parse_offending_item_id(response_body)
            if not offending_id:
                return None, last_error, dropped

            before = len(current_items)
            current_items = [
                item for item in current_items if item.get("item_id") != offending_id
            ]
            if len(current_items) == before:
                return None, last_error, dropped
            dropped += before - len(current_items)

        return None, last_error or "Exceeded create retry limit", dropped

    async def _complete_inspection(self, inspection_id: str) -> Optional[str]:
        url = (
            f"{BASE_URL}/inspections/integration/v1/inspections/"
            f"{inspection_id}/complete"
        )
        status, body = await async_request_with_retry(
            self.session, "POST", url, json_body={}
        )
        if status is None:
            return body
        if status != 200:
            return f"{status}: {body[:250]}"
        return None

    async def generate_one(
        self,
        run_index: int,
        templates: List[Dict],
        progress_bar=None,
    ) -> Dict:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        template = random.choice(templates)
        template_id = template.get("id") or template.get("template_id") or ""
        template_name = template.get("name", "")

        result = {
            "run_index": run_index,
            "template_id": template_id,
            "template_name": template_name,
            "inspection_id": "",
            "items_filled": 0,
            "create_status": "",
            "complete_status": "",
            "error_message": "",
            "timestamp": timestamp,
        }

        async with self.semaphore:
            template_def = await self._get_template_definition(template_id)
            if template_def is None:
                result["create_status"] = "ERROR"
                result["error_message"] = "Failed to fetch template definition"
                self._write_row(result)
                if progress_bar:
                    progress_bar.write(
                        f"❌ #{run_index} {template_name} - no definition"
                    )
                    progress_bar.update(1)
                return result

            items, item_stats = await build_inspection_items(
                template_def, self.org_context, self.session
            )
            result["items_filled"] = item_stats["filled"]

            inspection_id, create_err, dropped = await self._create_inspection(
                template_id, items
            )
            if not inspection_id:
                result["create_status"] = "ERROR"
                result["error_message"] = create_err or "Unknown error"
                self._write_row(result)
                if progress_bar:
                    progress_bar.write(
                        f"❌ #{run_index} create failed "
                        f"({template_name}): {create_err}"
                    )
                    progress_bar.update(1)
                return result

            result["inspection_id"] = inspection_id
            result["create_status"] = "SUCCESS"
            if dropped:
                result["items_filled"] = max(0, result["items_filled"] - dropped)

            complete_err = await self._complete_inspection(inspection_id)
            if complete_err:
                result["complete_status"] = "ERROR"
                if item_stats["unfillable_mandatory_risk"]:
                    complete_err = (
                        f"{complete_err} "
                        f"(template has {item_stats['unfillable_mandatory_risk']} "
                        f"media/drawing/signature/table items "
                        f"that cannot be filled via public API)"
                    )
                result["error_message"] = complete_err
                if progress_bar:
                    progress_bar.write(
                        f"⚠️  #{run_index} created {inspection_id} but complete "
                        f"failed: {complete_err[:150]}"
                    )
            else:
                result["complete_status"] = "SUCCESS"
                if progress_bar:
                    progress_bar.write(
                        f"✅ #{run_index} {template_name} → {inspection_id}"
                    )

            self._write_row(result)
            if progress_bar:
                progress_bar.update(1)
            return result

    async def run(self, count: int, templates: List[Dict]) -> Dict[str, int]:
        print(f"🚀 Generating {count} random inspections...")
        print(
            f"⚡ Concurrency: {self.semaphore_value} "
            f"(target ~{self.max_requests_per_minute} req/min)"
        )
        print(f"📊 Live results writing to: {self.output_file}\n")

        results = {"created": 0, "completed": 0, "errors": 0, "total": count}

        with tqdm(
            total=count, desc="Generating inspections", unit="inspection"
        ) as pbar:
            tasks = [self.generate_one(i + 1, templates, pbar) for i in range(count)]
            done = await asyncio.gather(*tasks)

        for row in done:
            if row["create_status"] == "SUCCESS":
                results["created"] += 1
            if row["complete_status"] == "SUCCESS":
                results["completed"] += 1
            if row["create_status"] != "SUCCESS" or (
                row["create_status"] == "SUCCESS"
                and row["complete_status"] != "SUCCESS"
            ):
                results["errors"] += 1

        return results


def prompt_count() -> int:
    while True:
        raw = input("How many inspections to generate? ").strip()
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        print("  Please enter a positive integer.")


async def main():
    print("=" * 80)
    print("🎲 SafetyCulture Random Inspection Generator")
    print("=" * 80)

    if not TOKEN:
        print("\n❌ Error: TOKEN not set in script")
        print("Please set your API token in the TOKEN variable at the top of main.py")
        return 1

    count = prompt_count()
    print()

    templates = fetch_all_templates()
    if not templates:
        print("❌ No active templates found in the organization.")
        return 1

    org_context = OrgContext()
    org_context.preload_org_references()

    print("=" * 80)

    async with InspectionGenerator(org_context, max_requests_per_minute=300) as gen:
        results = await gen.run(count, templates)

    print("\n" + "=" * 80)
    print("📊 GENERATION SUMMARY")
    print("=" * 80)
    print(f"📝 Total requested: {results['total']}")
    print(f"✅ Created:         {results['created']}")
    print(f"✅ Completed:       {results['completed']}")
    print(f"❌ Errors:          {results['errors']}")
    if results["total"] > 0:
        print(
            f"📈 Success rate:    "
            f"{(results['completed'] / results['total'] * 100):.1f}%"
        )
    print(f"\n💾 Full results saved to: {os.path.abspath(gen.output_file)}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    asyncio.run(main())
