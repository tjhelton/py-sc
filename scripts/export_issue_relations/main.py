import csv

import requests

TOKEN = ""  # Set your SafetyCulture API token here


def fetch_issue_relations():
    base_url = "https://api.safetyculture.io"
    relative_url = "/feed/issue_relations"
    items = []
    count = 0

    while relative_url:
        url = base_url + relative_url

        headers = {"accept": "application/json", "authorization": f"Bearer {TOKEN}"}

        response = requests.get(url, headers=headers).json()

        data = response.get("data", [])
        items.extend(data)
        count += 1

        print(
            f"Fetched page {count}, page items: {len(data)}, total items: {len(items)}"
        )

        relative_url = response.get("metadata", {}).get("next_page")

    return items


def save_to_csv(items, filename="issue_relations.csv"):
    if not items:
        print("No data available to write.")
        return

    headers = items[0].keys()

    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        writer.writerows(items)

    print(f"Saved {len(items)} records to {filename}")


if __name__ == "__main__":
    items = fetch_issue_relations()
    save_to_csv(items)
