import asyncio
import csv
import os
import time
from datetime import datetime
from typing import Dict, List

import aiohttp
import pandas as pd
from tqdm.asyncio import tqdm

TOKEN = ''  # Set your SafetyCulture API token here
BASE_URL = 'https://api.safetyculture.io'

MAX_REQUESTS_PER_MINUTE = 500
SEMAPHORE_VALUE = 12

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class InspectionDeleter:

    def __init__(self):
        self.headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
            'authorization': f'Bearer {TOKEN}',
        }
        self.session = None
        self.semaphore = None
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

        csv_filename = 'output.csv'
        self.csv_file_handle = open(csv_filename, 'w', newline='', encoding='utf-8')
        self.csv_writer = csv.DictWriter(
            self.csv_file_handle,
            fieldnames=[
                'audit_id',
                'status',
                'error_message',
                'timestamp',
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

    def _write_result_to_csv(self, result: Dict):
        self.csv_writer.writerow(result)
        self.csv_file_handle.flush()

    async def delete_inspection(self, audit_id: str) -> Dict[str, any]:
        url = f'{BASE_URL}/inspections/v1/inspections/{audit_id}'

        for attempt in range(MAX_RETRIES):
            try:
                async with self.session.delete(url) as response:
                    if response.status == 200:
                        return {
                            'success': True,
                            'audit_id': audit_id,
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
                        'success': False,
                        'audit_id': audit_id,
                        'error': f'HTTP {response.status}: {error_text[:200]}',
                    }

            except (aiohttp.ClientError, asyncio.TimeoutError) as error:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2**attempt)
                    await asyncio.sleep(delay)
                    continue

                return {
                    'success': False,
                    'audit_id': audit_id,
                    'error': f'{type(error).__name__}: {str(error)}',
                }

        return {'success': False, 'audit_id': audit_id, 'error': 'Max retries exceeded'}

    async def delete_single_inspection_async(self, audit_id: str, progress_bar) -> Dict:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        async with self.semaphore:
            delete_result = await self.delete_inspection(audit_id)

            if delete_result['success']:
                result = {
                    'audit_id': audit_id,
                    'status': 'SUCCESS',
                    'error_message': '',
                    'timestamp': timestamp,
                }

                log_msg = f'✅ Deleted: {audit_id}'
                if progress_bar:
                    progress_bar.write(log_msg)
                    progress_bar.update(1)

                self._write_result_to_csv(result)
                return result

            error_msg = delete_result.get('error', 'Unknown error')
            result = {
                'audit_id': audit_id,
                'status': 'ERROR',
                'error_message': error_msg,
                'timestamp': timestamp,
            }

            log_msg = f'❌ Error: {audit_id} - {error_msg}'
            if progress_bar:
                progress_bar.write(log_msg)
                progress_bar.update(1)

            self._write_result_to_csv(result)
            return result

    async def delete_all_inspections(self, audit_ids: List[str]) -> Dict:
        print(f'\n🚀 Starting bulk deletion for {len(audit_ids)} inspections...')
        print(f'⚡ Rate limit: {MAX_REQUESTS_PER_MINUTE} requests per minute')
        print('📊 Live results: output.csv\n')

        results = {'success': 0, 'error': 0, 'total': len(audit_ids)}
        start_time = time.time()

        with tqdm(
            total=len(audit_ids), desc='Deleting inspections', unit='inspection'
        ) as pbar:
            tasks = [
                self.delete_single_inspection_async(audit_id, pbar)
                for audit_id in audit_ids
            ]
            completed_results = await asyncio.gather(*tasks)

        for result in completed_results:
            if result['status'] == 'SUCCESS':
                results['success'] += 1
            else:
                results['error'] += 1

        results['total_time_seconds'] = round(time.time() - start_time, 2)
        return results


def load_input_csv() -> List[str]:
    input_file = 'input.csv'

    if not os.path.exists(input_file):
        print(f'❌ Error: {input_file} not found')
        print('Please create input.csv with column: audit_id')
        return []

    try:
        df = pd.read_csv(input_file)

        if 'audit_id' not in df.columns:
            print("❌ Error: input.csv missing required column 'audit_id'")
            return []

        df = df.dropna(subset=['audit_id'])
        df['audit_id'] = df['audit_id'].astype(str)

        audit_ids = df['audit_id'].tolist()

        if not audit_ids:
            print('❌ Error: No valid audit_ids found in input.csv')
            return []

        print(f'📋 Loaded {len(audit_ids)} inspection IDs from {input_file}')
        return audit_ids

    except Exception as error:
        print(f'❌ Error reading {input_file}: {error}')
        return []


async def main():
    print('=' * 80)
    print('🚀 SafetyCulture Inspection Bulk Deleter')
    print('=' * 80)

    if not TOKEN:
        print('\n❌ Error: TOKEN not set in script')
        print('Please set your API token in the TOKEN variable at the top of main.py')
        return 1

    audit_ids = load_input_csv()
    if not audit_ids:
        return 1

    print('\n⚠️  WARNING: This will permanently delete all inspections in input.csv')
    print(f'⚠️  Total inspections to delete: {len(audit_ids)}')
    user_input = input('\nType "DELETE" to confirm: ')

    if user_input != 'DELETE':
        print('\n❌ Deletion cancelled')
        return 1

    print('\n' + '=' * 80)

    async with InspectionDeleter() as deleter:
        results = await deleter.delete_all_inspections(audit_ids)

    print('\n' + '=' * 80)
    print('📊 DELETION SUMMARY')
    print('=' * 80)
    print(f'✅ Successful: {results["success"]}')
    print(f'❌ Errors: {results["error"]}')
    print(f'📝 Total: {results["total"]}')

    if results['total'] > 0:
        success_rate = results['success'] / results['total'] * 100
        print(f'📈 Success Rate: {success_rate:.1f}%')
    else:
        print('📈 Success Rate: N/A')

    total_time = results.get('total_time_seconds', 0)
    minutes = int(total_time // 60)
    seconds = int(total_time % 60)
    print(f'⏱️  Total Time: {minutes}m {seconds}s')

    print(f'\n💾 Results log: {os.path.abspath("output.csv")}')
    print('=' * 80)

    return 0


if __name__ == '__main__':
    asyncio.run(main())
