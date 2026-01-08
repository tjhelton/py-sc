#!/usr/bin/env python3
import asyncio
import csv
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import aiohttp

BASE_URL = "https://api.safetyculture.io"
BULK_UPDATE_URL = f"{BASE_URL}/assets/v1/assets/bulk"
LIST_FIELDS_URL = f"{BASE_URL}/assets/v1/fields/list"

TOKEN = ""  # Set your SafetyCulture API token here

# Performance configuration
CHUNK_SIZE = 100  # Assets per bulk request
CONCURRENCY = 3  # Concurrent bulk requests (900 assets in flight max)
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
TIMEOUT = 60

# Standard field aliases
ID_ALIASES = ["internal id", "asset id", "id"]
CODE_ALIASES = ["unique id", "code", "asset code", "unique code"]
SITE_ALIASES = ["site id", "site", "site_id"]
TYPE_ID_ALIASES = ["type id", "type_id", "asset type id"]
TYPE_NAME_ALIASES = ["type", "asset type", "asset type name"]


# ANSI colors
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


# ═══════════════════════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class AssetFieldDefinition:
    id: str
    name: str
    value_type: str
    select_options: List[str]


@dataclass
class MappingResult:
    id_col: str
    code_col: Optional[str]
    site_col: Optional[str]
    type_id_col: Optional[str]
    type_name_col: Optional[str]
    field_columns: Dict[str, AssetFieldDefinition]
    unmatched_columns: List[str]
    ambiguous_columns: Dict[str, List[AssetFieldDefinition]]


@dataclass
class RunStats:
    total_rows: int = 0
    prepared_assets: int = 0
    successes: int = 0
    failures: int = 0
    skipped_no_id: int = 0
    skipped_empty_payload: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════════════════


def normalize_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.strip().lower())


def chunked(iterable: Sequence, size: int) -> Iterable[List]:
    for idx in range(0, len(iterable), size):
        yield list(iterable[idx : idx + size])


def match_header(fieldnames: List[str], aliases: List[str]) -> Optional[str]:
    normalized = {normalize_key(name): name for name in fieldnames}
    for alias in aliases:
        key = normalize_key(alias)
        if key in normalized:
            return normalized[key]
    return None


def build_field_maps(
    fields: List[AssetFieldDefinition],
) -> Tuple[Dict[str, List[AssetFieldDefinition]], Dict[str, AssetFieldDefinition]]:
    by_name: Dict[str, List[AssetFieldDefinition]] = {}
    by_id: Dict[str, AssetFieldDefinition] = {}

    for field in fields:
        norm = normalize_key(field.name)
        by_name.setdefault(norm, []).append(field)
        by_id[field.id] = field

    return by_name, by_id


def map_columns_to_fields(
    fieldnames: List[str], fields: List[AssetFieldDefinition], used_columns: List[str]
) -> MappingResult:
    by_name, by_id = build_field_maps(fields)
    unmatched: List[str] = []
    ambiguous: Dict[str, List[AssetFieldDefinition]] = {}
    field_columns: Dict[str, AssetFieldDefinition] = {}

    # Find standard columns
    id_col = match_header(fieldnames, ID_ALIASES)
    if not id_col:
        raise ValueError("No ID column found. Add one of: " + ", ".join(ID_ALIASES))

    code_col = match_header(fieldnames, CODE_ALIASES)
    site_col = match_header(fieldnames, SITE_ALIASES)
    type_id_col = match_header(fieldnames, TYPE_ID_ALIASES)
    type_name_col = None if type_id_col else match_header(fieldnames, TYPE_NAME_ALIASES)

    used = {id_col}
    used.update([c for c in (code_col, site_col, type_id_col, type_name_col) if c])
    used.update(used_columns)

    for column in fieldnames:
        if column in used:
            continue

        norm = normalize_key(column)
        match: Optional[AssetFieldDefinition] = None

        if column in by_id:
            match = by_id[column]
        elif norm in by_name:
            options = by_name[norm]
            if len(options) == 1:
                match = options[0]
            else:
                ambiguous[column] = options

        if match:
            field_columns[column] = match
        else:
            unmatched.append(column)

    return MappingResult(
        id_col=id_col,
        code_col=code_col,
        site_col=site_col,
        type_id_col=type_id_col,
        type_name_col=type_name_col,
        field_columns=field_columns,
        unmatched_columns=unmatched,
        ambiguous_columns=ambiguous,
    )


def normalize_timestamp(value: str) -> str:
    text = value.strip()
    if not text:
        return ""

    candidate = text.replace("Z", "+00:00")
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(candidate, fmt)
            return dt.isoformat()
        except ValueError:
            continue

    try:
        dt = datetime.fromisoformat(candidate)
        return dt.isoformat()
    except ValueError:
        return text


def build_money_value(
    value: str, default_currency: str = "USD"
) -> Optional[Dict[str, object]]:
    text = value.strip()
    if not text:
        return None

    pattern = re.compile(
        r"^(?P<prefix>[A-Za-z]{3})?\s*(?P<amount>-?[0-9][0-9,\.]*)\s*(?P<suffix>[A-Za-z]{3})?$"
    )
    match = pattern.match(text)
    if not match:
        return None

    currency = match.group("prefix") or match.group("suffix") or default_currency
    amount_raw = match.group("amount").replace(",", "")

    try:
        amount = Decimal(amount_raw)
    except InvalidOperation:
        return None

    units = int(
        amount.to_integral_value(rounding=ROUND_FLOOR if amount >= 0 else ROUND_CEILING)
    )
    nanos = int((amount - Decimal(units)) * Decimal("1000000000"))

    return {"currency_code": currency.upper(), "units": str(units), "nanos": nanos}


def build_field_value(
    field_def: AssetFieldDefinition, raw_value: str
) -> Optional[Dict[str, object]]:
    value = (raw_value or "").strip()
    if value == "":
        return None

    value_type = field_def.value_type

    if value_type == "FIELD_VALUE_TYPE_TIMESTAMP":
        return {"field_id": field_def.id, "timestamp_value": normalize_timestamp(value)}

    if value_type == "FIELD_VALUE_TYPE_MONEY":
        money = build_money_value(value)
        if not money:
            return None
        return {"field_id": field_def.id, "money_value": money}

    return {"field_id": field_def.id, "string_value": value}


def build_asset_payload(
    row: Dict[str, str], mapping: MappingResult
) -> Optional[Dict[str, object]]:
    asset_id = (row.get(mapping.id_col, "") or "").strip()
    if not asset_id:
        return None

    asset: Dict[str, object] = {"id": asset_id}

    if mapping.code_col:
        code = (row.get(mapping.code_col, "") or "").strip()
        if code:
            asset["code"] = code

    if mapping.site_col:
        site_id = (row.get(mapping.site_col, "") or "").strip()
        if site_id:
            asset["site"] = {"id": site_id}

    asset_fields: List[Dict[str, object]] = []
    for column, field_def in mapping.field_columns.items():
        payload = build_field_value(field_def, row.get(column, ""))
        if payload:
            asset_fields.append(payload)

    if asset_fields:
        asset["fields"] = asset_fields

    return asset


def generate_update_mask(mapping: MappingResult) -> str:
    mask_parts = []

    if mapping.code_col:
        mask_parts.append("code")

    if mapping.site_col:
        mask_parts.append("site")

    if mapping.field_columns:
        mask_parts.append("fields")

    if not mask_parts:
        raise ValueError("No updatable fields found in CSV mapping")

    return ",".join(mask_parts)


def load_csv_rows(csv_path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)

        if not reader.fieldnames:
            raise ValueError("CSV has no headers")

        fieldnames = list(reader.fieldnames)
        rows = list(reader)

        if not rows:
            raise ValueError("CSV has no data rows")

    return fieldnames, rows


# ═══════════════════════════════════════════════════════════════════════════════
# Async client
# ═══════════════════════════════════════════════════════════════════════════════


class BulkUpdateAssetsClient:
    def __init__(self, token: str, chunk_size: int = CHUNK_SIZE):
        self.token = token
        self.chunk_size = chunk_size
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=CONCURRENCY * 2,
            limit_per_host=CONCURRENCY,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        timeout = aiohttp.ClientTimeout(total=TIMEOUT, connect=10)
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {self.token}",
        }
        self.session = aiohttp.ClientSession(
            connector=connector, timeout=timeout, headers=headers
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def fetch_asset_fields(self) -> List[AssetFieldDefinition]:
        if not self.session:
            raise RuntimeError("Session not initialized")

        async with self.session.post(LIST_FIELDS_URL, json={}) as response:
            if response.status != 200:
                text = await response.text()
                raise RuntimeError(
                    f"Failed to fetch fields (status {response.status}): {text}"
                )

            data = await response.json()
            results = data.get("result", []) or []

            return [
                AssetFieldDefinition(
                    id=str(field.get("id", "")),
                    name=str(field.get("name", "")),
                    value_type=str(field.get("value_type", "")),
                    select_options=[
                        opt.get("value", "")
                        for opt in field.get("select_options", []) or []
                    ],
                )
                for field in results
            ]

    async def bulk_update_chunk(
        self,
        chunk: List[Dict],
        update_mask: str,
        semaphore: asyncio.Semaphore,
        chunk_num: int,
        total_chunks: int,
    ) -> Dict:
        if not self.session:
            raise RuntimeError("Session not initialized")

        payload = {"assets": chunk, "update_mask": update_mask}

        async with semaphore:
            for attempt in range(1, 4):
                try:
                    async with self.session.put(
                        BULK_UPDATE_URL, json=payload
                    ) as response:
                        status = response.status

                        if status in (200, 201):
                            data = await response.json()
                            return {
                                'success': True,
                                'data': data,
                                'chunk_num': chunk_num,
                                'total_chunks': total_chunks,
                            }

                        if status in RETRY_STATUS_CODES and attempt < 3:
                            wait_time = 2**attempt
                            print(
                                f"{Colors.YELLOW}Chunk {chunk_num}: Retry {attempt}/3 (HTTP {status}), "
                                f"waiting {wait_time}s...{Colors.RESET}"
                            )
                            await asyncio.sleep(wait_time)
                            continue

                        text = await response.text()
                        return {
                            'success': False,
                            'error': f"HTTP {status}: {text}",
                            'chunk_num': chunk_num,
                            'total_chunks': total_chunks,
                        }

                except aiohttp.ClientError as error:
                    if attempt < 3:
                        wait_time = 2**attempt
                        print(
                            f"{Colors.YELLOW}Chunk {chunk_num}: Network error, "
                            f"retry {attempt}/3, waiting {wait_time}s...{Colors.RESET}"
                        )
                        await asyncio.sleep(wait_time)
                        continue

                    return {
                        'success': False,
                        'error': f"Network error: {error}",
                        'chunk_num': chunk_num,
                        'total_chunks': total_chunks,
                    }

            return {
                'success': False,
                'error': 'Max retries exceeded',
                'chunk_num': chunk_num,
                'total_chunks': total_chunks,
            }


# ═══════════════════════════════════════════════════════════════════════════════
# CSV logging
# ═══════════════════════════════════════════════════════════════════════════════


class CSVLogger:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.csvfile = None
        self.writer = None

    def __enter__(self):
        self.csvfile = self.log_path.open('w', newline='', encoding='utf-8')
        self.writer = csv.DictWriter(
            self.csvfile,
            fieldnames=['asset_id', 'asset_code', 'status', 'message', 'timestamp'],
        )
        self.writer.writeheader()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.csvfile:
            self.csvfile.close()

    def log_result(
        self, asset_id: str, asset_code: str, status: str, message: str = ''
    ):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.writer.writerow(
            {
                'asset_id': asset_id,
                'asset_code': asset_code,
                'status': status,
                'message': message,
                'timestamp': timestamp,
            }
        )
        self.csvfile.flush()


# ═══════════════════════════════════════════════════════════════════════════════
# Progress & summary functions
# ═══════════════════════════════════════════════════════════════════════════════


def print_mapping_summary(mapping: MappingResult, total_fields: int):
    print(f"\n{Colors.BOLD}Field Mapping Summary{Colors.RESET}")
    print("=" * 80)
    print(f"Total asset fields available: {total_fields}")

    print(
        f"\n{Colors.GREEN}Matched custom fields: {len(mapping.field_columns)}{Colors.RESET}"
    )
    for column, field_def in mapping.field_columns.items():
        print(
            f"  {column} → {field_def.name} (ID: {field_def.id}, Type: {field_def.value_type})"
        )

    standard_count = sum(
        [
            1
            for x in [
                mapping.code_col,
                mapping.site_col,
                mapping.type_id_col,
                mapping.type_name_col,
            ]
            if x
        ]
    )
    print(f"\n{Colors.GREEN}Matched standard fields: {standard_count}{Colors.RESET}")
    if mapping.code_col:
        print(f"  {mapping.code_col} → asset.code")
    if mapping.site_col:
        print(f"  {mapping.site_col} → asset.site.id")
    if mapping.type_name_col:
        print(f"  {mapping.type_name_col} → asset.type (reference)")

    if mapping.ambiguous_columns:
        print(
            f"\n{Colors.YELLOW}Ambiguous matches (skipped): {len(mapping.ambiguous_columns)}{Colors.RESET}"
        )
        for column, matches in mapping.ambiguous_columns.items():
            names = ", ".join([m.name for m in matches])
            print(f"  {column} → Multiple: {names}")

    if mapping.unmatched_columns:
        print(
            f"\n{Colors.YELLOW}Unmatched columns (ignored): {len(mapping.unmatched_columns)}{Colors.RESET}"
        )
        for column in mapping.unmatched_columns:
            print(f"  {column}")

    print("=" * 80)


def print_chunk_progress(chunk_num: int, total_chunks: int, stats: RunStats):
    total_processed = min(chunk_num * CHUNK_SIZE, stats.prepared_assets)
    percentage = (
        (total_processed / stats.prepared_assets) * 100
        if stats.prepared_assets > 0
        else 0
    )

    print(
        f"{Colors.BLUE}Chunk {chunk_num}/{total_chunks}{Colors.RESET} "
        f"({total_processed}/{stats.prepared_assets} assets, {percentage:.1f}%) | "
        f"{Colors.GREEN}✓ {stats.successes}{Colors.RESET} | "
        f"{Colors.RED}✗ {stats.failures}{Colors.RESET}"
    )


def print_final_summary(stats: RunStats, duration: float, log_path: Path):
    print(f"\n{Colors.BOLD}{'=' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}Bulk Update Complete{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 80}{Colors.RESET}")

    print(f"\n{Colors.BOLD}Input Statistics:{Colors.RESET}")
    print(f"  Total CSV rows: {stats.total_rows}")
    print(f"  Valid assets prepared: {stats.prepared_assets}")
    if stats.skipped_no_id > 0:
        print(
            f"  {Colors.YELLOW}Skipped (missing ID): {stats.skipped_no_id}{Colors.RESET}"
        )
    if stats.skipped_empty_payload > 0:
        print(
            f"  {Colors.YELLOW}Skipped (no updates): {stats.skipped_empty_payload}{Colors.RESET}"
        )

    print(f"\n{Colors.BOLD}Update Results:{Colors.RESET}")
    success_rate = (
        (stats.successes / stats.prepared_assets * 100)
        if stats.prepared_assets > 0
        else 0
    )

    if stats.successes > 0:
        print(
            f"  {Colors.GREEN}✓ Successfully updated: {stats.successes} ({success_rate:.1f}%){Colors.RESET}"
        )

    if stats.failures > 0:
        print(f"  {Colors.RED}✗ Failed updates: {stats.failures}{Colors.RESET}")

    print(f"\n{Colors.BOLD}Performance:{Colors.RESET}")
    print(f"  Total time: {duration:.1f}s ({duration/60:.1f} minutes)")

    if duration > 0:
        throughput = stats.prepared_assets / duration
        print(f"  Throughput: {throughput:.1f} assets/second")

    print(f"\n{Colors.BLUE}Log file: {log_path}{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 80}{Colors.RESET}\n")


# ═══════════════════════════════════════════════════════════════════════════════
# Main async workflow
# ═══════════════════════════════════════════════════════════════════════════════


async def main() -> int:
    if not TOKEN:
        print(f"{Colors.RED}Error: TOKEN not set in script{Colors.RESET}")
        print("Set TOKEN at the top of the file")
        return 1

    script_dir = Path(__file__).parent
    csv_path = script_dir / "input.csv"

    if not csv_path.exists():
        print(f"{Colors.RED}Error: Input CSV not found: {csv_path}{Colors.RESET}")
        return 1

    log_path = script_dir / f"bulk_update_log_{datetime.now():%Y%m%d_%H%M%S}.csv"
    stats = RunStats()

    print(f"{Colors.BOLD}{'=' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}SafetyCulture Bulk Asset Updater (Async){Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 80}{Colors.RESET}")
    print(f"Input: {csv_path}")
    print(f"Chunk size: {CHUNK_SIZE} assets/request")
    print(f"Concurrency: {CONCURRENCY} chunks in parallel")
    print(f"{Colors.BOLD}{'=' * 80}{Colors.RESET}\n")

    async with BulkUpdateAssetsClient(TOKEN, CHUNK_SIZE) as client:
        print(f"{Colors.BLUE}Step 1: Fetching asset fields...{Colors.RESET}")
        try:
            fields = await client.fetch_asset_fields()
            print(f"{Colors.GREEN}Found {len(fields)} asset fields{Colors.RESET}")
        except Exception as error:
            print(f"{Colors.RED}Failed to fetch fields: {error}{Colors.RESET}")
            return 1

        print(f"\n{Colors.BLUE}Step 2: Loading CSV...{Colors.RESET}")
        try:
            fieldnames, rows = load_csv_rows(csv_path)
            print(
                f"{Colors.GREEN}Loaded {len(rows)} rows with {len(fieldnames)} columns{Colors.RESET}"
            )
        except Exception as error:
            print(f"{Colors.RED}Failed to load CSV: {error}{Colors.RESET}")
            return 1

        print(f"\n{Colors.BLUE}Step 3: Mapping CSV columns to fields...{Colors.RESET}")
        try:
            mapping = map_columns_to_fields(fieldnames, fields, [])
            print_mapping_summary(mapping, len(fields))
        except Exception as error:
            print(f"{Colors.RED}Field mapping failed: {error}{Colors.RESET}")
            return 1

        print(f"\n{Colors.BLUE}Step 4: Building asset payloads...{Colors.RESET}")
        assets = []

        for row in rows:
            stats.total_rows += 1
            payload = build_asset_payload(row, mapping)

            if payload is None:
                stats.skipped_no_id += 1
                continue

            if not any(key in payload for key in ['code', 'site', 'fields']):
                stats.skipped_empty_payload += 1
                continue

            assets.append(payload)
            stats.prepared_assets += 1

        print(
            f"{Colors.GREEN}Prepared {stats.prepared_assets} assets for update{Colors.RESET}"
        )

        if stats.skipped_no_id > 0:
            print(
                f"{Colors.YELLOW}Skipped {stats.skipped_no_id} rows (missing ID){Colors.RESET}"
            )

        if stats.skipped_empty_payload > 0:
            print(
                f"{Colors.YELLOW}Skipped {stats.skipped_empty_payload} rows (no updates){Colors.RESET}"
            )

        if stats.prepared_assets == 0:
            print(f"{Colors.RED}No assets to update{Colors.RESET}")
            return 0

        update_mask = generate_update_mask(mapping)
        print(f"Update mask: {update_mask}")

        print(f"\n{Colors.BLUE}Step 5: Executing bulk updates...{Colors.RESET}")
        chunks = list(chunked(assets, CHUNK_SIZE))
        total_chunks = len(chunks)
        print(f"Split into {total_chunks} chunks\n")

        start_time = time.time()
        semaphore = asyncio.Semaphore(CONCURRENCY)

        with CSVLogger(log_path) as logger:
            for chunk_num, chunk in enumerate(chunks, start=1):
                result = await client.bulk_update_chunk(
                    chunk, update_mask, semaphore, chunk_num, total_chunks
                )

                if result['success']:
                    updated = result['data'].get('updated_assets', [])
                    failed = result['data'].get('failed_assets', [])

                    for asset in updated:
                        logger.log_result(
                            asset.get('id', ''), asset.get('code', ''), 'success'
                        )
                        stats.successes += 1

                    for asset in failed:
                        error_obj = asset.get('error', {})
                        error_msg = error_obj.get('message', str(error_obj))
                        logger.log_result(
                            asset.get('id', ''),
                            asset.get('code', ''),
                            'error',
                            error_msg,
                        )
                        stats.failures += 1
                else:
                    for asset in chunk:
                        logger.log_result(
                            asset.get('id', ''),
                            asset.get('code', ''),
                            'error',
                            result['error'],
                        )
                        stats.failures += 1

                print_chunk_progress(chunk_num, total_chunks, stats)

            duration = time.time() - start_time
            print_final_summary(stats, duration, log_path)

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
