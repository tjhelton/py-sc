import asyncio
import json
from typing import Any, Dict, List

import aiohttp
import pandas as pd
from tqdm.asyncio import tqdm

TOKEN = ""


async def list_user_fields(session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    """Fetch all available user field definitions."""
    url = "https://api.safetyculture.io/users/v1/fields/list"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {TOKEN}",
    }

    try:
        async with session.post(url, headers=headers, json={}) as response:
            response.raise_for_status()
            data = await response.json()
            fields = data.get("fields", [])
            print(f"✅ Found {len(fields)} custom user fields")
            return fields
    except aiohttp.ClientError as error:
        print(f"❌ ERROR fetching user fields - {error}")
        return []


async def fetch_users_from_feed(
    session: aiohttp.ClientSession,
) -> List[Dict[str, Any]]:
    """Fetch all users from the users datafeed with pagination."""
    url = "https://api.safetyculture.io/feed/users"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {TOKEN}",
    }

    all_users = []
    next_page_url = None

    print("📥 Fetching users from datafeed...")

    while True:
        # Use next_page URL if available, otherwise use base URL
        current_url = next_page_url if next_page_url else url

        try:
            async with session.get(current_url, headers=headers) as response:
                response.raise_for_status()
                response_data = await response.json()

                # Extract users from 'data' field
                users = response_data.get("data", [])
                all_users.extend(users)
                print(f"  Fetched {len(users)} users (total: {len(all_users)})")

                # Check for next page in metadata
                metadata = response_data.get("metadata", {})
                next_page_path = metadata.get("next_page")

                # Stop if no more pages
                if not next_page_path:
                    break

                # Prepend base URL if next_page is a relative path
                if next_page_path.startswith("/"):
                    next_page_url = f"https://api.safetyculture.io{next_page_path}"
                else:
                    next_page_url = next_page_path

        except aiohttp.ClientError as error:
            print(f"❌ ERROR fetching users - {error}")
            break

    print(f"✅ Total users fetched: {len(all_users)}")
    return all_users


async def fetch_user_attributes(
    session: aiohttp.ClientSession,
    user_id: str,
    semaphore: asyncio.Semaphore,
    user_email: str = "",
    progress_bar=None,
) -> Dict[str, Any]:
    """Fetch custom field values for a specific user."""
    # Strip 'user_' prefix if present - attributes endpoint needs UUID only
    uuid_only = user_id.replace("user_", "") if user_id.startswith("user_") else user_id
    url = f"https://api.safetyculture.io/users/v1/users/{uuid_only}/attributes"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {TOKEN}",
    }

    async with semaphore:
        try:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()
                result = {"user_id": user_id, "attributes": data.get("attributes", [])}
                if progress_bar:
                    progress_bar.update(1)
                return result
        except aiohttp.ClientError as error:
            # Print errors above the progress bar
            if progress_bar:
                progress_bar.write(
                    f"  ⚠️  Warning: Could not fetch attributes for {user_email or user_id} - {error}"
                )
            else:
                print(
                    f"  ⚠️  Warning: Could not fetch attributes for {user_email or user_id} - {error}"
                )
            result = {"user_id": user_id, "attributes": []}
            if progress_bar:
                progress_bar.update(1)
            return result


async def fetch_all_user_attributes(
    session: aiohttp.ClientSession, users: List[Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    """Fetch custom field values for all users concurrently."""
    print(f"\n📊 Fetching custom field values for {len(users)} users...")
    print("   Rate limit: 5 requests per second\n")

    # Limit concurrent requests to 5 per second
    semaphore = asyncio.Semaphore(10)

    # Create progress bar
    with tqdm(total=len(users), desc="Fetching user attributes", unit="user") as pbar:
        tasks = [
            fetch_user_attributes(
                session,
                user.get("id", user.get("user_id")),
                semaphore,
                user.get("email", ""),
                pbar,
            )
            for user in users
            if user.get("id") or user.get("user_id")
        ]

        results = await asyncio.gather(*tasks)

    # Convert to dictionary keyed by user_id
    attributes_by_user = {}
    for result in results:
        user_id = result["user_id"]
        # Convert attributes list to dict for easier lookup
        attrs_dict = {}
        for attr in result["attributes"]:
            field_id = attr.get("field_id")
            # Extract value from attribute_values array
            attribute_values = attr.get("attribute_values", [])
            value = ""
            if attribute_values and len(attribute_values) > 0:
                attr_val = attribute_values[0]
                # Try different value types
                value = (
                    attr_val.get("string_value")
                    or attr_val.get("number_value")
                    or attr_val.get("bool_value")
                    or attr_val.get("date_value")
                    or ""
                )
            if field_id:
                attrs_dict[field_id] = value
        attributes_by_user[user_id] = attrs_dict

    print(f"✅ Fetched attributes for {len(attributes_by_user)} users")
    return attributes_by_user


def create_output_csv(
    users: List[Dict[str, Any]],
    custom_fields: List[Dict[str, Any]],
    attributes_by_user: Dict[str, Dict[str, Any]],
) -> None:
    """Create output CSV with all user fields and custom field columns."""
    print("\n📝 Creating output CSV...")

    rows = []

    for user in users:
        user_id = user.get("id", user.get("user_id"))

        # Start with all standard user fields
        row = {}

        # Add all fields from the user object
        for key, value in user.items():
            # Handle nested objects by converting to JSON string
            if isinstance(value, (dict, list)):
                row[key] = json.dumps(value)
            else:
                row[key] = value

        # Add custom field columns
        user_attrs = attributes_by_user.get(user_id, {})

        for field in custom_fields:
            field_id = field.get("id")
            field_name = field.get("name", field_id)

            # Get value for this custom field, or blank if not set
            field_value = user_attrs.get(field_id, "")

            # Handle different value types
            if isinstance(field_value, (dict, list)):
                field_value = json.dumps(field_value)

            row[field_name] = field_value

        rows.append(row)

    # Create DataFrame and save to CSV
    df = pd.DataFrame(rows)

    # Get unique filename if output.csv already exists
    import os

    base_name = "output"
    extension = ".csv"
    output_file = f"{base_name}{extension}"
    counter = 1

    while os.path.exists(output_file):
        output_file = f"{base_name}_{counter}{extension}"
        counter += 1

    df.to_csv(output_file, index=False)

    # Get absolute path for display
    absolute_path = os.path.abspath(output_file)

    print(f"✅ Output saved to: {absolute_path}")
    print(f"   - Total users: {len(rows)}")
    print(f"   - Total columns: {len(df.columns)}")
    print(f"   - Standard fields: {len(df.columns) - len(custom_fields)}")
    print(f"   - Custom fields: {len(custom_fields)}")


async def main():
    """Main execution flow."""
    print("🚀 Starting user custom fields export...\n")

    # Validate API token
    if not TOKEN:
        print("❌ Error: TOKEN not set in script")
        print("Please set your token in the TOKEN variable at the top of main.py")
        return 1

    async with aiohttp.ClientSession() as session:
        # Step 1: List available custom user fields
        print("Step 1: Fetching available custom user fields...")
        custom_fields = await list_user_fields(session)

        if not custom_fields:
            print("\n⚠️  No custom user fields found.")
            print("Continuing with standard user fields only...")

        # Display custom fields to user
        if custom_fields:
            print("\n📋 Available custom fields:")
            for i, field in enumerate(custom_fields, 1):
                field_id = field.get("id")
                field_name = field.get("name", "N/A")
                field_type = field.get("data_type", "N/A")
                print(f"   {i}. {field_name} (ID: {field_id}, Type: {field_type})")

        # Step 2: Fetch all users from datafeed
        print("\n" + "=" * 60)
        print("Step 2: Fetching users from datafeed...")
        print("=" * 60)
        users = await fetch_users_from_feed(session)

        if not users:
            print("❌ Error: No users found")
            return 1

        # Step 3: Fetch custom field values for each user
        print("=" * 60)
        print("Step 3: Fetching custom field values...")
        print("=" * 60)
        attributes_by_user = await fetch_all_user_attributes(session, users)

        # Step 4: Create output CSV
        print("=" * 60)
        print("Step 4: Creating output CSV...")
        print("=" * 60)
        create_output_csv(users, custom_fields, attributes_by_user)

    print("\n" + "=" * 60)
    print("✅ Export completed successfully!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    asyncio.run(main())
