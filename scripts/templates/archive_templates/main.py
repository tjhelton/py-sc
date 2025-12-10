import pandas as pd
import requests

TOKEN = ""  # Set your SafetyCulture API token here


def archive_template(template_id):
    url = f"https://api.safetyculture.io/templates/v1/templates/{template_id}/archive"
    headers = {"authorization": f"Bearer {TOKEN}"}
    return requests.post(url, headers=headers).text


def main():
    templates = pd.read_csv('input.csv').fillna('').to_dict('records')
    output = [
        {
            "template_id": row.get('template_id', row),
            "result": archive_template(row.get('template_id', row)),
        }
        for row in templates
    ]
    pd.DataFrame(output).to_csv('log_output.csv', index=False)


main()
