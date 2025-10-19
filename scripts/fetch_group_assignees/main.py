import asyncio
import csv
import time
from datetime import datetime
from typing import Dict, List

import aiohttp

TOKEN = ''
BASE_URL = 'https://api.safetyculture.io'


class SafetyCultureAPI:
    """SafetyCulture API client for fetching groups and group assignees."""

    def __init__(self, max_concurrent_requests=25):
        self.headers = {
            'accept': 'application/json',
            'authorization': f'Bearer {TOKEN}',
        }
        self.max_concurrent_requests = max_concurrent_requests
        self.session = None
        self.semaphore = None

    async def __aenter__(self):
        # Create session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=100, limit_per_host=30, ttl_dns_cache=300, use_dns_cache=True
        )
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        self.session = aiohttp.ClientSession(
            headers=self.headers, connector=connector, timeout=timeout
        )
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def fetch_page(self, url: str) -> Dict:
        """Fetch a single page from the API with rate limiting"""
        async with self.semaphore:
            try:
                async with self.session.get(url) as response:
                    response.raise_for_status()
                    return await response.json()
            except Exception as e:
                print(f'❌ Error fetching {url}: {e}')
                raise

    async def fetch_all_groups(self) -> List[Dict]:
        """Fetch all groups from the organization"""
        url = f'{BASE_URL}/groups'
        print('🚀 Fetching all groups...')

        all_groups = []
        page_count = 0
        start_time = time.time()

        try:
            response = await self.fetch_page(url)
            groups = response.get('groups', [])
            all_groups.extend(groups)
            page_count = 1

            elapsed = time.time() - start_time
            print(
                f'✅ Fetched {len(all_groups)} groups in {elapsed:.1f}s ({page_count} page)'
            )

        except Exception as e:
            print(f'❌ Error fetching groups: {e}')

        return all_groups

    async def fetch_group_users(self, group_id: str, group_name: str) -> List[Dict]:
        """Fetch all users for a specific group with pagination"""
        all_users = []
        offset = 0
        limit = 1000  # Max batch size
        page_count = 0

        while True:
            url = f'{BASE_URL}/groups/{group_id}/users?limit={limit}&offset={offset}'

            try:
                response = await self.fetch_page(url)
                users = response.get('users', [])

                if not users:
                    break

                # Add group_id to each user record
                for user in users:
                    user['group_id'] = group_id
                    user['group_name'] = group_name

                all_users.extend(users)
                page_count += 1
                offset += limit

                # If we got fewer results than the limit, we're done
                if len(users) < limit:
                    break

            except Exception as e:
                print(
                    f'❌ Error fetching users for group {group_name} ({group_id}): {e}'
                )
                break

        return all_users

    async def fetch_all_group_assignees(self) -> List[Dict]:
        """Fetch all groups and their assignees concurrently"""
        print('🔄 Starting group assignee fetch...\n')
        start_time = time.time()

        # Step 1: Fetch all groups
        groups = await self.fetch_all_groups()

        if not groups:
            print('⚠️  No groups found')
            return []

        print(f'\n📊 Found {len(groups)} groups. Fetching assignees...\n')

        # Step 2: Fetch users for all groups concurrently
        tasks = [
            self.fetch_group_users(group['id'], group.get('name', 'Unknown'))
            for group in groups
        ]

        # Execute all fetch tasks concurrently with progress tracking
        results = []
        completed = 0

        for coro in asyncio.as_completed(tasks):
            users = await coro
            results.extend(users)
            completed += 1
            print(
                f'  ✓ Progress: {completed}/{len(groups)} groups processed ({len(users)} users found)'
            )

        elapsed = time.time() - start_time
        print(
            f'\n🎉 Completed: {len(results)} total assignees from {len(groups)} groups in {elapsed:.1f}s'
        )

        return results


def format_output(assignees: List[Dict]) -> List[Dict]:
    """Format assignee data to include only requested fields"""
    formatted = []

    for assignee in assignees:
        formatted_record = {
            'group_id': assignee.get('group_id', ''),
            'user_id': assignee.get('user_id', ''),
            'user_uuid': assignee.get('id', ''),  # 'id' field is the user UUID
            'user_firstname': assignee.get('firstname', ''),
            'user_lastname': assignee.get('lastname', ''),
            'user_email': assignee.get('email', ''),
        }
        formatted.append(formatted_record)

    return formatted


def write_csv(data: List[Dict], filename: str):
    """Write data to CSV file"""
    if not data:
        print(f'⚠️  No data to write to {filename}')
        return

    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'group_id',
            'user_id',
            'user_uuid',
            'user_firstname',
            'user_lastname',
            'user_email',
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    print(f'💾 Saved {len(data)} records to {filename}')


async def main():
    """Main execution function"""
    if not TOKEN:
        print('❌ Error: TOKEN not set in script')
        print('Please set your token in the TOKEN variable at the top of main.py')
        return

    print('🚀 Starting SafetyCulture Group Assignees Fetch')
    print('=' * 80)

    start_time = datetime.now()

    async with SafetyCultureAPI(max_concurrent_requests=25) as api:
        # Fetch all groups and their assignees
        assignees = await api.fetch_all_group_assignees()

    # Format the output to include only requested fields
    print('\n📋 Formatting output data...')
    formatted_data = format_output(assignees)

    # Write results to CSV
    print('\n💾 Saving results...')
    write_csv(formatted_data, 'output.csv')

    # Summary
    end_time = datetime.now()
    duration = end_time - start_time

    print('\n' + '=' * 80)
    print('📋 SUMMARY')
    print('=' * 80)
    print(f'📊 Total Group Assignees: {len(formatted_data):,}')
    print(f'⏱️  Total Runtime: {duration.total_seconds():.1f}s')
    print('=' * 80)


if __name__ == '__main__':
    asyncio.run(main())
