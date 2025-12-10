import pandas as pd
import requests

TOKEN = ""  # Set your SafetyCulture API token here


def read_csv():
    df = pd.read_csv('input.csv').fillna('')
    csv = df.to_dict('records')
    return csv


def map_csv(csv):
    mapped = []
    for row in csv:
        email = row['email']
        site = row['site_id']
        mapping = {
            "user": {
                "sites": {"remove": [{"name": "*"}, {"id": site}]},
                "username": email,
            }
        }
        mapped.append(mapping)
    return mapped


def initialize_update(users):
    try:
        url = "https://api.safetyculture.io/users/v1/users/upsert/jobs"
        payload = {"users": users}
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {TOKEN}",
        }
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        job_id = response.json()['job_id']
        print(f"Successfully Initialized {job_id}")
        return job_id
    except requests.exceptions.RequestException as error:
        print(f'ERROR - {error}')
        return None


def start_update(job):
    url = f"https://api.safetyculture.io/users/v1/users/upsert/jobs/{job}"
    payload = {"origin": {"source": "SOURCE_UNSPECIFIED"}, "validate_only": True}
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {TOKEN}",
    }
    response = requests.post(url, json=payload, headers=headers)
    job_id = response.json()['job_id']
    return job_id


def get_job(job_id):
    url = f"https://api.safetyculture.io/users/v1/users/upsert/jobs/{job_id}"
    headers = {"accept": "application/json", "authorization": f"Bearer {TOKEN}"}
    response = requests.get(url, headers=headers)
    print(response.text)


def main():
    csv = read_csv()
    mapped = list(map_csv(csv))
    print(mapped[0])
    job = initialize_update(mapped)
    result_id = start_update(job)
    get_job(result_id)


main()
