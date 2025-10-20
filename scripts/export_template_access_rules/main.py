import csv
import sys

import requests
from tqdm import tqdm

TOKEN = ""  # Add your API token here
BASE_URL = "https://api.safetyculture.io"


class SafetyCultureClient:
    """Client for interacting with SafetyCulture API."""

    def __init__(self, base_url, api_token):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_token}"})

    def _make_request(self, url):
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def transform_feed_id(self, feed_id):
        if "_" not in feed_id:
            return feed_id
        uuid_part = feed_id.split("_")[1]
        if len(uuid_part) == 32:
            return f"{uuid_part[:8]}-{uuid_part[8:12]}-{uuid_part[12:16]}-{uuid_part[16:20]}-{uuid_part[20:]}"
        return uuid_part

    def fetch_paginated_feed(self, endpoint):
        url = f"{self.base_url}{endpoint}"
        while url:
            response = self._make_request(url)
            yield from response.get("data", [])
            metadata = response.get("metadata", {})
            next_page = metadata.get("next_page")
            url = f"{self.base_url}{next_page}" if next_page else None

    def get_template_by_id(self, template_id):
        try:
            response = self._make_request(
                f"{self.base_url}/templates/v1/templates/{template_id}"
            )
            return response.get("template")
        except requests.RequestException:
            return None


def process_template_permissions(template, users_lookup, groups_lookup):
    records = []
    template_id, template_name = template.get("id", ""), template.get("name", "")
    owner_data = template.get("owner", {})
    owner_id = owner_data.get("id", "") if isinstance(owner_data, dict) else owner_data
    owner_name = users_lookup.get(owner_id, f"Unknown User ({owner_id})")
    permissions = template.get("permissions", {})

    for permission_type, permission_list in permissions.items():
        if not isinstance(permission_list, list):
            continue
        for permission_entry in permission_list:
            assignee_id = permission_entry.get("id", "")
            permission_obj_type = permission_entry.get("type", "USER")
            if permission_obj_type == "ROLE":
                assignee_type, assignee_name = "group", groups_lookup.get(
                    assignee_id, f"Unknown Group ({assignee_id})"
                )
            else:
                assignee_type, assignee_name = "user", users_lookup.get(
                    assignee_id, f"Unknown User ({assignee_id})"
                )
            records.append(
                {
                    "template_id": template_id,
                    "name": template_name,
                    "template_owner": owner_name,
                    "permission": permission_type,
                    "assignee_type": assignee_type,
                    "assignee_id": assignee_id,
                    "assignee_name": assignee_name,
                }
            )
    return records


def fetch_users_lookup(client):
    print("Fetching users...")
    users_lookup = {}
    with tqdm(desc="Users", unit="user") as pbar:
        for user in client.fetch_paginated_feed("/feed/users"):
            user_id = user.get("id", "")
            user_name = (
                f"{user.get('firstname', '')} {user.get('lastname', '')}".strip()
                or user.get("email", "Unknown User")
            )
            users_lookup[client.transform_feed_id(user_id)] = user_name
            pbar.update(1)
    print(f"✓ Loaded {len(users_lookup)} users\n")
    return users_lookup


def fetch_groups_lookup(client):
    print("Fetching groups...")
    groups_lookup = {}
    with tqdm(desc="Groups", unit="group") as pbar:
        for group in client.fetch_paginated_feed("/feed/groups"):
            group_id = group.get("id", "")
            groups_lookup[client.transform_feed_id(group_id)] = group.get(
                "name", "Unknown Group"
            )
            pbar.update(1)
    print(f"✓ Loaded {len(groups_lookup)} groups\n")
    return groups_lookup


def main():
    if not TOKEN:
        print("Error: Please set your SafetyCulture API token in the TOKEN variable")
        return 1

    client = SafetyCultureClient(BASE_URL, TOKEN)
    with open(
        "template_access_rules.csv", "w", newline="", encoding="utf-8"
    ) as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(
            [
                "template_id",
                "name",
                "template_owner",
                "permission",
                "assignee_type",
                "assignee_id",
                "assignee_name",
            ]
        )

        users_lookup = fetch_users_lookup(client)
        groups_lookup = fetch_groups_lookup(client)

        print("Processing templates...")
        records_written = 0
        with tqdm(desc="Templates", unit="template") as pbar:
            for template_summary in client.fetch_paginated_feed("/feed/templates"):
                if template_summary.get("archived", False):
                    continue
                template_detail = client.get_template_by_id(
                    template_summary.get("id", "")
                )
                if template_detail:
                    for record in process_template_permissions(
                        template_detail, users_lookup, groups_lookup
                    ):
                        csv_writer.writerow(
                            [
                                record["template_id"],
                                record["name"],
                                record["template_owner"],
                                record["permission"],
                                record["assignee_type"],
                                record["assignee_id"],
                                record["assignee_name"],
                            ]
                        )
                        records_written += 1
                pbar.update(1)
        print(
            f"✓ Completed! Wrote {records_written} access rules to template_access_rules.csv"
        )


if __name__ == "__main__":
    sys.exit(main())
