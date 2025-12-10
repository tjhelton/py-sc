import os

import pandas as pd
import requests

TOKEN = ""  # Set your SafetyCulture API token here


def import_csv():
    df = pd.read_csv('input.csv')
    csv = df.to_dict('records')
    return csv


def create_group(name, count):
    count += 1
    try:
        url = "https://api.safetyculture.io/groups"

        payload = {"name": name}
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {TOKEN}",
        }
        response = requests.post(url, json=payload, headers=headers).json()
        status = response['id']
        print(f'#{count} SUCCESS Creating Group: {name} - {status}')
    except requests.exceptions.RequestException as err:
        status = f'#{count} ERROR Creating Group: {name} - {err}'
        print(status)
    return status


def main():
    data = import_csv()
    count = 0
    for row in data:
        name = row['name']
        response = create_group(name, count)
        df = pd.DataFrame({"name": [name], "status": [response]})
        df.to_csv(
            'output.csv', mode='a', header=not os.path.exists('output.csv'), index=False
        )


main()
