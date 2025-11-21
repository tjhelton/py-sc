import os

import pandas as pd
import requests

TOKEN = "38bc6f0787a370c972fc42efcd419c380048910aa4d0452df7485d679e8fc2eb"  # INSERT API TOKEN HERE, NOTHING ELSE IS NEEDED


def assign_course_to_sites(course_id, site_ids, count):
    try:
        url = (
            f"https://api.safetyculture.io/training/courses/v1/{course_id}/assignments"
        )
        assignments = [
            {"type": "ASSIGNMENT_TYPE_SITE", "id": site_id} for site_id in site_ids
        ]
        payload = {"assignments": assignments}
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {TOKEN}",
        }
        response = requests.put(url, json=payload, headers=headers)
        response.raise_for_status()
        status = f"#{count} - Successfully assigned {len(site_ids)} site(s) to course {course_id}"
        print(status)
        return status
    except requests.exceptions.RequestException as error:
        status = f"#{count} - ERROR assigning sites to course {course_id}: {error}"
        print(status)
        return status


def main():
    csv_data = pd.read_csv("input.csv").fillna("").to_dict("records")

    course_sites = {}
    for row in csv_data:
        course_id = row["course_id"]
        site_id = row["site_id"]
        if course_id not in course_sites:
            course_sites[course_id] = []
        course_sites[course_id].append(site_id)

    count = 0
    for course_id, site_ids in course_sites.items():
        status = assign_course_to_sites(course_id, site_ids, count)
        pd.DataFrame(
            {
                "course_id": [course_id],
                "site_ids": [", ".join(site_ids)],
                "status": [status],
            }
        ).to_csv(
            "output.csv",
            mode="a",
            header=not os.path.exists("output.csv"),
            index=False,
        )
        count += 1


main()
