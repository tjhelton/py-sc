import os

import pandas as pd
import requests

TOKEN = ""  # Set your SafetyCulture API token here


def get_public_link(issue_id, count):
    try:
        url = f"https://api.safetyculture.io/tasks/v1/shared_link/{issue_id}/web_report"
        headers = {"authorization": f"Bearer {TOKEN}"}
        response = requests.post(url, headers=headers).json()
        status = f"#{count+1} SUCCESS Fetching Public Link For Issue: {issue_id}"
        log_row = {"issue_id": issue_id, "url": response['url'], "status": status}
        print(status)
        return log_row
    except requests.exceptions.RequestException as err:
        status = f"#{count+1} ERROR Fetching Public Link For Issue: {issue_id}, {err}"
        log_row = {"issue_id": issue_id, "url": "N/A", "status": status}
        print(status)
        return log_row


def main():
    data = pd.read_csv('input.csv').to_dict('records')
    for count, row in enumerate(data):
        response = get_public_link(row['issue_id'], count)
        pd.DataFrame([response]).to_csv(
            "output.csv", mode='a', header=not os.path.exists("output.csv"), index=False
        )


main()
