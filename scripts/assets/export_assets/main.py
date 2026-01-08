import ast
import asyncio
import csv
import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

TOKEN = ""  # Set your SafetyCulture API token here
BASE_URL = "https://api.safetyculture.io"


class SafetyCultureAssetFetcher:
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
        if self.session:
            await self.session.close()

    async def fetch_page(self, url: str) -> Dict:
        try:
            async with self.session.get(url) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            print(f"❌ Error fetching {url}: {e}")
            raise

    async def fetch_all_assets(self, output_file: str):
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
            csv_file = open(output_file, "w", newline="", encoding="utf-8")

            while url:
                page_start = time.time()

                response = await self.fetch_page(url)
                data = response.get("data", [])
                page_count += 1
                total_assets += len(data)

                if csv_writer is None and data:
                    fieldnames = data[0].keys()
                    csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                    csv_writer.writeheader()

                if csv_writer and data:
                    csv_writer.writerows(data)
                    csv_file.flush()

                page_time = time.time() - page_start
                elapsed = time.time() - start_time
                rate = page_count / elapsed if elapsed > 0 else 0

                metadata = response.get("metadata", {})
                remaining_records = metadata.get("remaining_records", 0)

                if remaining_records > 0 and rate > 0:
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

                print(
                    f"📄 Page {page_count}: {len(data)} assets | "
                    f"Total: {total_assets:,} | "
                    f"Remaining: {remaining_records:,} | "
                    f"Rate: {rate:.2f} pages/sec | "
                    f"Page time: {page_time:.2f}s | "
                    f"ETA: {eta_str}"
                )

                next_url = metadata.get("next_page")
                if next_url:
                    if not next_url.startswith("http"):
                        next_url = f"{BASE_URL}{next_url}"
                    url = next_url
                else:
                    url = None

        except Exception as e:
            print(f"❌ Error during asset fetch: {e}")
            raise

        finally:
            if csv_file:
                csv_file.close()

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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"assets_{timestamp}"
    extension = ".csv"
    output_file = f"{base_name}{extension}"

    counter = 1
    while os.path.exists(output_file):
        output_file = f"{base_name}_{counter}{extension}"
        counter += 1

    return output_file


def parse_detail_fields(raw_fields: Any) -> Dict[str, str]:
    if raw_fields in (None, "", []):
        return {}

    parsed_items: List[Dict[str, Any]] = []

    if isinstance(raw_fields, list):
        parsed_items = raw_fields
    elif isinstance(raw_fields, dict):
        parsed_items = [raw_fields]
    else:
        text = str(raw_fields).strip()
        if not text:
            return {}

        attempts: List[str] = [text, f"[{text}]"]

        if "|" in text:
            pipe_to_comma = text.replace("|", ",")
            attempts.extend([pipe_to_comma, f"[{pipe_to_comma}]"])

        for candidate in attempts:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    parsed_items = [parsed]
                elif isinstance(parsed, list):
                    parsed_items = parsed
                if parsed_items:
                    break
            except json.JSONDecodeError:
                continue

        if not parsed_items:
            try:
                parsed_literal = ast.literal_eval(text)
                if isinstance(parsed_literal, dict):
                    parsed_items = [parsed_literal]
                elif isinstance(parsed_literal, list):
                    parsed_items = parsed_literal
            except (ValueError, SyntaxError):
                parsed_items = []

    detail_values: Dict[str, str] = {}

    for item in parsed_items:
        if not isinstance(item, dict):
            continue

        name = str(
            item.get("name") or item.get("label") or item.get("field_id") or ""
        ).strip()

        if not name:
            continue

        value = item.get("value", "")
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        elif value is None:
            value = ""
        else:
            value = str(value)

        detail_values[name] = value

    return detail_values


def get_flattened_output_file(raw_output_file: str) -> str:
    base, ext = os.path.splitext(raw_output_file)
    output_file = f"{base}_flattened{ext}"

    counter = 1
    while os.path.exists(output_file):
        output_file = f"{base}_flattened_{counter}{ext}"
        counter += 1

    return output_file


def flatten_asset_fields(
    raw_csv_path: str, output_path: Optional[str] = None
) -> Tuple[str, List[str], int]:
    print("\n🧮 Expanding asset detail fields into columns...")

    if not os.path.exists(raw_csv_path):
        raise FileNotFoundError(f"Raw asset file not found: {raw_csv_path}")

    detail_columns: List[str] = []
    name_to_column: Dict[str, str] = {}
    base_columns: List[str] = []
    total_assets = 0

    with open(raw_csv_path, newline="", encoding="utf-8") as raw_file:
        reader = csv.DictReader(raw_file)
        if not reader.fieldnames:
            print("⚠️  No data found to flatten.")
            return raw_csv_path, [], 0

        base_columns = [col for col in reader.fieldnames if col != "fields"]

        for row in reader:
            total_assets += 1
            parsed_details = parse_detail_fields(row.get("fields", ""))

            for original_name in parsed_details.keys():
                if not original_name:
                    continue

                if original_name in name_to_column:
                    continue

                column_name = original_name
                suffix = 1

                while column_name in base_columns or column_name in detail_columns:
                    column_name = f"{original_name}_{suffix}"
                    suffix += 1

                name_to_column[original_name] = column_name
                detail_columns.append(column_name)

    output_file = output_path or get_flattened_output_file(raw_csv_path)

    with open(raw_csv_path, newline="", encoding="utf-8") as raw_file, open(
        output_file, "w", newline="", encoding="utf-8"
    ) as flat_file:
        reader = csv.DictReader(raw_file)
        fieldnames = base_columns + detail_columns
        writer = csv.DictWriter(flat_file, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            details = parse_detail_fields(row.get("fields", ""))
            output_row = {col: row.get(col, "") for col in base_columns}

            for original_name, column_name in name_to_column.items():
                output_row[column_name] = details.get(original_name, "")

            writer.writerow(output_row)

    return output_file, detail_columns, total_assets


async def main():
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

    output_file = get_next_output_file()

    start_time = datetime.now()

    async with SafetyCultureAssetFetcher() as fetcher:
        await fetcher.fetch_all_assets(output_file)

    flattened_file, detail_fields, asset_count = flatten_asset_fields(output_file)

    end_time = datetime.now()
    duration = end_time - start_time

    print("\n✅ Script completed successfully!")
    print(f"📅 Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📅 End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️  Duration: {duration}")
    print(f"🧭 Assets processed: {asset_count}")
    print(f"🧩 Detail fields expanded: {len(detail_fields)}")
    if detail_fields:
        print("📑 Detail columns added:")
        for name in detail_fields:
            print(f"   - {name}")
    print(f"💾 Flattened output saved to: {flattened_file}")

    return 0


if __name__ == "__main__":
    asyncio.run(main())
