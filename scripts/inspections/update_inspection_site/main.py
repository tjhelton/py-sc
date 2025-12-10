import os

import pandas as pd
import requests

TOKEN = ""  # Set your SafetyCulture API token here


def read_csv():
    df = pd.read_csv('input.csv').fillna('')
    csv = df.to_dict('records')
    return csv


def set_inspection_site(audit_id, site_id, count):
    try:
        url = f"https://api.safetyculture.io/inspections/v1/inspections/{audit_id}/site"
        payload = {"site_id": site_id}
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {TOKEN}",
        }
        response = requests.put(url, json=payload, headers=headers)
        response.raise_for_status()
        status = f"#{count} - Successfully assigned {site_id} to {audit_id}"
        print(status)
        return status
    except requests.exceptions.RequestException as error:
        status = f"#{count} - ERROR assigning {site_id} to {audit_id}: {error}"
        print(status)
        return status


def main():
    csv = read_csv()
    count = 0
    for row in csv:
        audit_id = row['audit_id']
        site_id = row['site_id']
        status = set_inspection_site(audit_id, site_id, count)
        df = pd.DataFrame(
            {"audit_id": [audit_id], "site_id": [site_id], "status": [status]}
        )
        df.to_csv(
            'output.csv', mode='a', header=not os.path.exists('output.csv'), index=False
        )
        count += 1


main()
