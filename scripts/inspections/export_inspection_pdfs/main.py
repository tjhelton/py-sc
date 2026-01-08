import asyncio
import csv
import os
import re
import time
from datetime import datetime
from typing import Dict, List

import aiohttp
import pandas as pd
from tqdm.asyncio import tqdm

TOKEN = ""  # Set your SafetyCulture API token here
BASE_URL = "https://api.safetyculture.io"

MAX_REQUESTS_PER_MINUTE = 500
SEMAPHORE_VALUE = 12

INITIAL_POLL_INTERVAL = 2
MAX_POLL_INTERVAL = 30
MAX_POLL_DURATION = 600

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


def sanitize_filename(text: str) -> str:
    # First replace forward slashes with hyphens
    sanitized = text.replace('/', '-')
    # Then replace other invalid characters with underscores
    invalid_chars = r'[\\:*?"<>|]'
    sanitized = re.sub(invalid_chars, '_', sanitized)
    sanitized = re.sub(r'[\s_]+', ' ', sanitized)
    sanitized = sanitized.strip()
    max_len = 200
    if len(sanitized) > max_len:
        sanitized = sanitized[:max_len].strip()
    return sanitized


def get_timestamped_output_dir() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"exports_{timestamp}"
    os.makedirs(dir_name, exist_ok=True)
    return dir_name


class InspectionPDFExporter:

    def __init__(self):
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {TOKEN}",
        }
        self.session = None
        self.semaphore = None
        self.output_dir = None
        self.csv_file_handle = None
        self.csv_writer = None

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=100, limit_per_host=50, ttl_dns_cache=300, use_dns_cache=True
        )
        timeout = aiohttp.ClientTimeout(total=120, connect=10)
        self.session = aiohttp.ClientSession(
            headers=self.headers, connector=connector, timeout=timeout
        )
        self.semaphore = asyncio.Semaphore(SEMAPHORE_VALUE)

        self.output_dir = get_timestamped_output_dir()

        csv_filename = "exports_log.csv"
        self.csv_file_handle = open(csv_filename, "w", newline="", encoding="utf-8")
        self.csv_writer = csv.DictWriter(
            self.csv_file_handle,
            fieldnames=[
                "audit_id",
                "audit_title",
                "template_name",
                "status",
                "error_message",
                "file_path",
                "export_time_seconds",
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

    def _build_pdf_filename(
        self, audit_title: str, template_name: str, audit_id: str
    ) -> str:
        safe_title = sanitize_filename(audit_title)
        safe_template = sanitize_filename(template_name)
        safe_id = sanitize_filename(audit_id)
        filename = f"{safe_title} ; {safe_template} ; {safe_id}.pdf"
        return filename

    def _write_result_to_csv(self, result: Dict):
        self.csv_writer.writerow(result)
        self.csv_file_handle.flush()

    def _extract_error_message(self, info_list: List[Dict]) -> str:
        if not info_list:
            return "Unknown error"
        messages = []
        for info_item in info_list:
            if isinstance(info_item, dict):
                subject = info_item.get("subject", "")
                details = info_item.get("details", "")
                if subject or details:
                    messages.append(f"{subject}: {details}".strip(": "))
        return "; ".join(messages) if messages else "Export failed"

    async def submit_export_request(self, audit_id: str) -> Dict[str, any]:
        url = f"{BASE_URL}/inspection/v1/export"
        request_body = {
            "export_data": [{"inspection_id": audit_id, "lang": "en"}],
            "type": "DOCUMENT_TYPE_PDF",
            "timezone": "UTC",
            "regenerate": False,
        }

        for attempt in range(MAX_RETRIES):
            try:
                async with self.session.post(url, json=request_body) as response:
                    response_data = await response.json()

                    if response.status == 200:
                        return {
                            "success": True,
                            "audit_id": audit_id,
                            "response": response_data,
                        }

                    if (
                        response.status in RETRY_STATUS_CODES
                        and attempt < MAX_RETRIES - 1
                    ):
                        delay = RETRY_BASE_DELAY * (2**attempt)
                        await asyncio.sleep(delay)
                        continue

                    error_text = await response.text()
                    return {
                        "success": False,
                        "audit_id": audit_id,
                        "error": f"HTTP {response.status}: {error_text[:200]}",
                    }

            except (aiohttp.ClientError, asyncio.TimeoutError) as error:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2**attempt)
                    await asyncio.sleep(delay)
                    continue

                return {
                    "success": False,
                    "audit_id": audit_id,
                    "error": f"{type(error).__name__}: {str(error)}",
                }

        return {"success": False, "audit_id": audit_id, "error": "Max retries exceeded"}

    async def poll_export_status(
        self, audit_id: str, initial_response: Dict
    ) -> Dict[str, any]:
        url = f"{BASE_URL}/inspection/v1/export"
        request_body = {
            "export_data": [{"inspection_id": audit_id, "lang": "en"}],
            "type": "DOCUMENT_TYPE_PDF",
            "timezone": "UTC",
            "regenerate": False,
        }

        start_time = time.time()
        poll_interval = INITIAL_POLL_INTERVAL
        status = initial_response.get("status", "")
        url_field = initial_response.get("url", "")

        if status == "STATUS_DONE" and url_field:
            return {"success": True, "url": url_field}

        if status == "STATUS_FAILED":
            error_info = initial_response.get("info", [])
            error_msg = self._extract_error_message(error_info)
            return {"success": False, "error": f"Export failed: {error_msg}"}

        while True:
            elapsed = time.time() - start_time

            if elapsed > MAX_POLL_DURATION:
                return {
                    "success": False,
                    "error": "Export timeout after 10 minutes",
                }

            await asyncio.sleep(poll_interval)

            try:
                async with self.session.post(url, json=request_body) as response:
                    if response.status != 200:
                        poll_interval = min(poll_interval * 2, MAX_POLL_INTERVAL)
                        continue

                    response_data = await response.json()
                    status = response_data.get("status", "")
                    url_field = response_data.get("url", "")

                    if status == "STATUS_DONE" and url_field:
                        return {"success": True, "url": url_field}

                    if status == "STATUS_FAILED":
                        error_info = response_data.get("info", [])
                        error_msg = self._extract_error_message(error_info)
                        return {
                            "success": False,
                            "error": f"Export failed: {error_msg}",
                        }

                    poll_interval = min(poll_interval * 2, MAX_POLL_INTERVAL)

            except (aiohttp.ClientError, asyncio.TimeoutError):
                poll_interval = min(poll_interval * 2, MAX_POLL_INTERVAL)
                continue

    async def download_pdf_from_s3(self, url: str, filepath: str) -> Dict[str, any]:
        try:
            async with self.session.get(url, headers={}) as response:
                if response.status != 200:
                    return {
                        "success": False,
                        "error": f"S3 download failed: HTTP {response.status}",
                    }

                pdf_bytes = await response.read()
                full_path = os.path.join(self.output_dir, filepath)
                with open(full_path, "wb") as f:
                    f.write(pdf_bytes)

                return {"success": True, "filepath": full_path}

        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            return {
                "success": False,
                "error": f"Download error: {type(error).__name__}: {str(error)}",
            }
        except IOError as error:
            return {"success": False, "error": f"File write error: {str(error)}"}

    async def export_single_inspection_async(self, row: Dict, progress_bar) -> Dict:
        audit_id = row.get("audit_id", "").strip()
        audit_title = row.get("audit_title", "Unknown").strip()
        template_name = row.get("template_name", "Unknown").strip()
        start_time = time.time()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        async with self.semaphore:
            submit_result = await self.submit_export_request(audit_id)

            if not submit_result["success"]:
                error_msg = submit_result.get("error", "Unknown error")
                result = {
                    "audit_id": audit_id,
                    "audit_title": audit_title,
                    "template_name": template_name,
                    "status": "ERROR",
                    "error_message": f"Submit failed: {error_msg}",
                    "file_path": "",
                    "export_time_seconds": round(time.time() - start_time, 2),
                    "timestamp": timestamp,
                }

                log_msg = f"❌ Error: {audit_id} - {error_msg}"
                if progress_bar:
                    progress_bar.write(log_msg)
                    progress_bar.update(1)

                self._write_result_to_csv(result)
                return result

            poll_result = await self.poll_export_status(
                audit_id, submit_result["response"]
            )

            if not poll_result["success"]:
                error_msg = poll_result.get("error", "Unknown error")
                result = {
                    "audit_id": audit_id,
                    "audit_title": audit_title,
                    "template_name": template_name,
                    "status": "ERROR",
                    "error_message": error_msg,
                    "file_path": "",
                    "export_time_seconds": round(time.time() - start_time, 2),
                    "timestamp": timestamp,
                }

                log_msg = f"❌ Error: {audit_id} - {error_msg}"
                if progress_bar:
                    progress_bar.write(log_msg)
                    progress_bar.update(1)

                self._write_result_to_csv(result)
                return result

            s3_url = poll_result["url"]
            pdf_filename = self._build_pdf_filename(
                audit_title, template_name, audit_id
            )
            download_result = await self.download_pdf_from_s3(s3_url, pdf_filename)

            if not download_result["success"]:
                error_msg = download_result.get("error", "Unknown error")
                result = {
                    "audit_id": audit_id,
                    "audit_title": audit_title,
                    "template_name": template_name,
                    "status": "ERROR",
                    "error_message": f"Download failed: {error_msg}",
                    "file_path": "",
                    "export_time_seconds": round(time.time() - start_time, 2),
                    "timestamp": timestamp,
                }

                log_msg = f"❌ Error: {audit_id} - Download failed"
                if progress_bar:
                    progress_bar.write(log_msg)
                    progress_bar.update(1)

                self._write_result_to_csv(result)
                return result

            result = {
                "audit_id": audit_id,
                "audit_title": audit_title,
                "template_name": template_name,
                "status": "SUCCESS",
                "error_message": "",
                "file_path": os.path.join(self.output_dir, pdf_filename),
                "export_time_seconds": round(time.time() - start_time, 2),
                "timestamp": timestamp,
            }

            log_msg = f"✅ Exported: {pdf_filename}"
            if progress_bar:
                progress_bar.write(log_msg)
                progress_bar.update(1)

            self._write_result_to_csv(result)
            return result

    async def export_all_inspections(self, rows: List[Dict]) -> Dict:
        print(f"\n🚀 Starting bulk export for {len(rows)} inspections...")
        print(f"⚡ Rate limit: {MAX_REQUESTS_PER_MINUTE} requests per minute")
        print(f"📁 Output directory: {self.output_dir}/")
        print("📊 Live results: exports_log.csv\n")

        results = {"success": 0, "error": 0, "total": len(rows)}
        start_time = time.time()

        with tqdm(total=len(rows), desc="Exporting PDFs", unit="inspection") as pbar:
            tasks = [self.export_single_inspection_async(row, pbar) for row in rows]
            completed_results = await asyncio.gather(*tasks)

        for result in completed_results:
            if result["status"] == "SUCCESS":
                results["success"] += 1
            else:
                results["error"] += 1

        results["total_time_seconds"] = round(time.time() - start_time, 2)
        return results


def load_input_csv() -> List[Dict]:
    input_file = "input.csv"

    if not os.path.exists(input_file):
        print(f"❌ Error: {input_file} not found")
        print(
            "Please create input.csv with columns: audit_id, audit_title, template_name"
        )
        return []

    try:
        df = pd.read_csv(input_file)

        required_columns = ["audit_id", "audit_title", "template_name"]
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            print(f"❌ Error: input.csv missing required columns: {missing_columns}")
            print(f"Required columns: {required_columns}")
            return []

        df = df.dropna(subset=["audit_id"])
        df["audit_title"] = df["audit_title"].fillna("Unknown")
        df["template_name"] = df["template_name"].fillna("Unknown")
        df["audit_id"] = df["audit_id"].astype(str)
        df["audit_title"] = df["audit_title"].astype(str)
        df["template_name"] = df["template_name"].astype(str)

        rows = df.to_dict("records")

        if not rows:
            print("❌ Error: No valid rows found in input.csv")
            return []

        print(f"📋 Loaded {len(rows)} inspections from {input_file}")
        return rows

    except Exception as error:
        print(f"❌ Error reading {input_file}: {error}")
        return []


async def main():
    print("=" * 80)
    print("🚀 SafetyCulture Inspection PDF Exporter")
    print("=" * 80)

    if not TOKEN:
        print("\n❌ Error: TOKEN not set in script")
        print("Please set your API token in the TOKEN variable at the top of main.py")
        return 1

    rows = load_input_csv()
    if not rows:
        return 1

    print("\n" + "=" * 80)

    async with InspectionPDFExporter() as exporter:
        results = await exporter.export_all_inspections(rows)

    print("\n" + "=" * 80)
    print("📊 EXPORT SUMMARY")
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

    print(f"\n💾 PDFs saved to: {os.path.abspath(exporter.output_dir)}/")
    print(f"💾 Results log: {os.path.abspath('exports_log.csv')}")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    asyncio.run(main())
