import asyncio
import csv
import os
from datetime import datetime
from typing import Dict, List

import aiohttp
import pandas as pd
from tqdm.asyncio import tqdm

TOKEN = ""  # Set your SafetyCulture API token here
BASE_URL = "https://api.safetyculture.io"


class InspectionCompleter:
    def __init__(self, max_requests_per_minute=500):
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {TOKEN}",
        }
        self.max_requests_per_minute = max_requests_per_minute
        self.semaphore_value = int(max_requests_per_minute / 60 * 1.5)
        self.session = None
        self.semaphore = None
        self.output_file = None
        self.csv_writer = None
        self.csv_file_handle = None

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=100, limit_per_host=50, ttl_dns_cache=300, use_dns_cache=True
        )
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        self.session = aiohttp.ClientSession(
            headers=self.headers, connector=connector, timeout=timeout
        )
        self.semaphore = asyncio.Semaphore(self.semaphore_value)

        self.output_file = self._get_output_filename()
        self.csv_file_handle = open(self.output_file, "w", newline="", encoding="utf-8")
        self.csv_writer = csv.DictWriter(
            self.csv_file_handle,
            fieldnames=["audit_id", "status", "error_message", "completion_timestamp"],
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
        base_name = "output"
        extension = ".csv"
        output_file = f"{base_name}{extension}"
        counter = 1

        while os.path.exists(output_file):
            output_file = f"{base_name}_{counter}{extension}"
            counter += 1

        return output_file

    def _write_result_to_csv(self, result: Dict):
        self.csv_writer.writerow(result)
        self.csv_file_handle.flush()

    async def complete_inspection(
        self, audit_id: str, completion_date: str, progress_bar=None
    ) -> Dict:
        url = f"{BASE_URL}/inspections/v1/inspections/{audit_id}/complete"
        request_body = {"timestamp": completion_date}
        completion_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        async with self.semaphore:
            try:
                async with self.session.post(url, json=request_body) as response:
                    response.raise_for_status()

                    result = {
                        "audit_id": audit_id,
                        "status": "SUCCESS",
                        "error_message": "",
                        "completion_timestamp": completion_timestamp,
                    }

                    log_msg = f"✅ Completed: {audit_id}"
                    if progress_bar:
                        progress_bar.write(log_msg)
                        progress_bar.update(1)
                    else:
                        print(log_msg)

                    self._write_result_to_csv(result)
                    return result

            except aiohttp.ClientError as error:
                error_message = str(error)
                result = {
                    "audit_id": audit_id,
                    "status": "ERROR",
                    "error_message": error_message,
                    "completion_timestamp": completion_timestamp,
                }

                log_msg = f"❌ Error: {audit_id} - {error_message}"
                if progress_bar:
                    progress_bar.write(log_msg)
                    progress_bar.update(1)
                else:
                    print(log_msg)

                self._write_result_to_csv(result)
                return result

    async def complete_all_inspections(self, audit_ids: List[str]) -> Dict:
        completion_date = datetime.now().strftime("%Y-%m-%dT00:00:00Z")

        print(f"\n📅 Completion timestamp set to: {completion_date}")
        print(f"🚀 Starting bulk completion for {len(audit_ids)} inspections...")
        print(f"⚡ Rate limit: {self.max_requests_per_minute} requests per minute")
        print(f"📊 Live results writing to: {self.output_file}\n")

        results = {"success": 0, "error": 0, "total": len(audit_ids)}

        with tqdm(
            total=len(audit_ids), desc="Completing inspections", unit="inspection"
        ) as pbar:
            tasks = [
                self.complete_inspection(audit_id, completion_date, pbar)
                for audit_id in audit_ids
            ]

            completed_results = await asyncio.gather(*tasks)

        for result in completed_results:
            if result["status"] == "SUCCESS":
                results["success"] += 1
            else:
                results["error"] += 1

        return results


def load_input_csv() -> List[str]:
    input_file = "input.csv"

    if not os.path.exists(input_file):
        print(f"❌ Error: {input_file} not found")
        print("Please create input.csv with a single 'audit_id' column")
        return []

    try:
        df = pd.read_csv(input_file)

        if "audit_id" not in df.columns:
            print("❌ Error: input.csv must have an 'audit_id' column")
            return []

        audit_ids = df["audit_id"].dropna().astype(str).tolist()

        if not audit_ids:
            print("❌ Error: No audit IDs found in input.csv")
            return []

        print(f"📋 Loaded {len(audit_ids)} audit IDs from {input_file}")
        return audit_ids

    except Exception as error:
        print(f"❌ Error reading {input_file}: {error}")
        return []


async def main():
    print("=" * 80)
    print("🚀 SafetyCulture Bulk Inspection Completion Tool")
    print("=" * 80)

    if not TOKEN:
        print("\n❌ Error: TOKEN not set in script")
        print("Please set your API token in the TOKEN variable at the top of main.py")
        return 1

    audit_ids = load_input_csv()
    if not audit_ids:
        return 1

    print("\n" + "=" * 80)

    async with InspectionCompleter(max_requests_per_minute=500) as completer:
        results = await completer.complete_all_inspections(audit_ids)

    print("\n" + "=" * 80)
    print("📊 COMPLETION SUMMARY")
    print("=" * 80)
    print(f"✅ Successful: {results['success']}")
    print(f"❌ Errors: {results['error']}")
    print(f"📝 Total: {results['total']}")
    print(
        f"📈 Success Rate: {(results['success']/results['total']*100):.1f}%"
        if results["total"] > 0
        else "N/A"
    )
    print(f"\n💾 Full results saved to: {os.path.abspath(completer.output_file)}")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    asyncio.run(main())
