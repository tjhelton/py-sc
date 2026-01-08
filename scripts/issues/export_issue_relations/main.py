import csv
import sys
import time

import requests

TOKEN = ""  # Set your SafetyCulture API token here

# Configuration
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30
BASE_BACKOFF = 1  # seconds


def fetch_and_stream_to_csv(filename="issue_relations.csv"):
    """Fetch issue relations with streaming CSV writes for maximum efficiency."""
    if not TOKEN:
        print("ERROR: TOKEN not set. Please set your API token in the script.")
        sys.exit(1)

    base_url = "https://api.safetyculture.io"
    # Use limit=100 to maximize items per page (fewer API calls)
    relative_url = "/feed/issue_relations?limit=100"

    page_count = 0
    total_items = 0
    csv_writer = None
    csvfile = None
    fieldnames = None

    try:
        csvfile = open(filename, "w", newline="", encoding="utf-8")

        while relative_url:
            url = base_url + relative_url
            headers = {"accept": "application/json", "authorization": f"Bearer {TOKEN}"}

            # Fetch page with retry logic
            data, next_page = fetch_page_with_retry(url, headers)

            if not data:
                break

            # Initialize CSV writer on first page (when we know the fields)
            if csv_writer is None:
                fieldnames = data[0].keys()
                csv_writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                csv_writer.writeheader()

            # Stream: write this page immediately to disk
            csv_writer.writerows(data)
            csvfile.flush()  # Ensure data is written to disk

            page_count += 1
            total_items += len(data)

            print(
                f"Fetched page {page_count}, page items: {len(data)}, total items: {total_items}"
            )

            relative_url = next_page

        print(f"\nSaved {total_items} records to {filename}")

    finally:
        if csvfile:
            csvfile.close()


def fetch_page_with_retry(url, headers):
    """Fetch a single page with exponential backoff retry logic."""
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                print(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                continue

            # Check for other HTTP errors
            if response.status_code != 200:
                print(f"HTTP {response.status_code}: {response.text}")
                if attempt < MAX_RETRIES - 1:
                    backoff = BASE_BACKOFF * (2**attempt)
                    print(
                        f"Retrying in {backoff} seconds... (attempt {attempt + 1}/{MAX_RETRIES})"
                    )
                    time.sleep(backoff)
                    continue
                else:
                    print("Max retries reached. Exiting.")
                    sys.exit(1)

            # Parse JSON response
            response_data = response.json()
            data = response_data.get("data", [])
            next_page = response_data.get("metadata", {}).get("next_page")

            return data, next_page

        except requests.exceptions.Timeout:
            print(f"Request timeout on attempt {attempt + 1}/{MAX_RETRIES}")
            if attempt < MAX_RETRIES - 1:
                backoff = BASE_BACKOFF * (2**attempt)
                print(f"Retrying in {backoff} seconds...")
                time.sleep(backoff)
            else:
                print("Max retries reached due to timeouts. Exiting.")
                sys.exit(1)

        except requests.exceptions.RequestException as e:
            print(f"Network error on attempt {attempt + 1}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES - 1:
                backoff = BASE_BACKOFF * (2**attempt)
                print(f"Retrying in {backoff} seconds...")
                time.sleep(backoff)
            else:
                print("Max retries reached due to network errors. Exiting.")
                sys.exit(1)

        except ValueError as e:
            print(f"JSON parsing error: {e}")
            print("Response content:", response.text[:500])
            sys.exit(1)

    return [], None


if __name__ == "__main__":
    fetch_and_stream_to_csv()
