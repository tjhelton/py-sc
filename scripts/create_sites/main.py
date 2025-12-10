import os

import pandas as pd
import requests

TOKEN = ""  # Set your SafetyCulture API token here


def create_site(name, parent, meta_label, count):
    try:
        payload = {"meta_label": meta_label, "name": name}
        if parent:
            payload["parent_id"] = parent
        headers = {"authorization": f"Bearer {TOKEN}"}
        response = requests.post(
            "https://api.safetyculture.io/directory/v1/folder",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        status = f"#{count} - Successfully Created {name}"
        print(status)
        return status
    except requests.exceptions.RequestException as error:
        status = f"#{count} - ERROR creating {name}: {error}"
        print(status)
        return status


def main():
    csv_data = pd.read_csv('input.csv').fillna('').to_dict('records')
    output_file = 'output.csv'
    for count, row in enumerate(csv_data):
        name, parent, meta_label = row['name'], row.get('parent'), row.get('meta_label')
        status = create_site(name, parent, meta_label, count)
        pd.DataFrame(
            {
                'count': [count],
                'site_name': [name],
                'meta_label': [meta_label],
                'status': [status],
            }
        ).to_csv(
            output_file, mode='a', header=not os.path.exists(output_file), index=False
        )


main()
