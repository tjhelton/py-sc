import csv

import requests

TOKEN = ''


def fetch_asset_types():
    url = "https://api.safetyculture.io/assets/v1/types/list"
    headers = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}

    all_types = []
    page_token = None

    while True:
        payload = {'page_size': 100}

        if page_token:
            payload['page_token'] = page_token
        print(payload)
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()
            types = data.get('type_list', [])
            all_types.extend(types)

            page_token = data.get('page_token')
            if not page_token:
                break

        except requests.exceptions.RequestException as e:
            print(f"Error fetching asset types: {e}")
            return []

    return all_types


def write_to_csv(asset_types, filename='asset_types_output.csv'):
    if not asset_types:
        print("No asset types to write to CSV")
        return

    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['id', 'name', 'type']

        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for asset_type in asset_types:
            row = {
                'id': asset_type.get('id', ''),
                'name': asset_type.get('name', ''),
                'type': asset_type.get('type', ''),
            }
            writer.writerow(row)

    print(f"Asset types data written to {filename}")


def main():
    if not TOKEN:
        print("Error: Please set your SafetyCulture API token in the TOKEN variable")
        return

    print("Fetching asset types from SafetyCulture API...")
    asset_types = fetch_asset_types()

    if asset_types:
        print(f"Found {len(asset_types)} asset types")

        filename = "asset_types.csv"

        write_to_csv(asset_types, filename)
        print(f"Successfully exported {len(asset_types)} asset types to {filename}")
    else:
        print("No asset types found or error occurred")


if __name__ == "__main__":
    main()
