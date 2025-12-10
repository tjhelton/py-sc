import time
from urllib.parse import urlencode

import pandas as pd
import requests

TOKEN = ""  # Set your SafetyCulture API token here


def delete_sites_batch(site_ids, batch_number, total_batches):
    try:
        base_url = "https://api.safetyculture.io/directory/v1/folders"
        params = [("folder_ids", site_id) for site_id in site_ids]
        params.append(("cascade_up", "true"))
        query_string = urlencode(params)
        url = f"{base_url}?{query_string}"
        headers = {
            "authorization": f"Bearer {TOKEN}",
            "accept": "application/json",
        }
        response = requests.delete(url, headers=headers)
        response.raise_for_status()
        status = f"Batch {batch_number}/{total_batches} - Deleted {len(site_ids)} sites"
        print(status)
        return status, site_ids, None
    except requests.exceptions.RequestException as error:
        error_detail = ""
        if hasattr(error, "response") and hasattr(error.response, "text"):
            error_detail = f" - Response: {error.response.text}"
        status = f"Batch {batch_number}/{total_batches} - Error: {error}{error_detail}"
        print(status)
        return status, site_ids, error


def chunk_list(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i : i + chunk_size]


def main():
    csv_data = pd.read_csv("input.csv")
    site_ids = csv_data["siteId"].tolist()
    total_sites = len(site_ids)
    batch_size = 50
    batches = list(chunk_list(site_ids, batch_size))
    total_batches = len(batches)

    print(f"Total sites to delete: {total_sites}")
    print(f"Batch size: {batch_size}")
    print(f"Total batches: {total_batches}")
    print("-" * 50)

    output_file = "output.csv"
    results = []

    for batch_number, batch in enumerate(batches, start=1):
        status, deleted_ids, error = delete_sites_batch(
            batch, batch_number, total_batches
        )
        for site_id in deleted_ids:
            results.append(
                {
                    "SiteID": site_id,
                    "Batch": batch_number,
                    "Status": "Deleted" if error is None else "Failed",
                    "Details": status,
                }
            )
        time.sleep(0.2)

    pd.DataFrame(results).to_csv(output_file, index=False)
    print("-" * 50)
    print(f"Results saved to {output_file}")


main()
