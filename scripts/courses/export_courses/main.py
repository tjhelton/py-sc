import csv
import time
from datetime import datetime

import requests

TOKEN = ""  # Set your SafetyCulture API token here
BASE_URL = "https://api.safetyculture.io"
PAGE_SIZE = 100


def fetch_all_courses():
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {TOKEN}",
    }

    all_courses = []
    page = 1
    total_count = None

    print("Fetching courses...")

    while True:
        url = f"{BASE_URL}/training/courses/v1"
        params = {"page_size": PAGE_SIZE, "page": page}

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
        except requests.exceptions.RequestException as error:
            print(f"Error fetching page {page}: {error}")
            break

        data = response.json()
        courses = data.get("items", [])

        if total_count is None:
            total_count = data.get("total_count")
            if total_count is not None:
                print(f"Total courses found: {total_count}")

        if not courses:
            break

        all_courses.extend(courses)
        print(f"  Fetched page {page} ({len(all_courses)} courses so far)")

        if total_count is not None and len(all_courses) >= total_count:
            break

        if len(courses) < PAGE_SIZE:
            break

        page += 1
        time.sleep(0.1)

    return all_courses


def format_duration(seconds):
    if seconds is None:
        return ""
    minutes, secs = divmod(int(seconds), 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes}m {secs}s"
    return f"{minutes}m {secs}s"


def write_csv(courses, filename):
    if not courses:
        print("No courses to export.")
        return

    fieldnames = [
        "id",
        "external_id",
        "title",
        "description",
        "status",
        "locale",
        "is_mandatory",
        "is_published",
        "due_by",
        "duration_seconds",
        "duration_formatted",
        "lesson_count",
        "created_datetime",
        "modified_datetime",
        "thumbnail_url",
        "logo_url",
        "branding_image_url",
    ]

    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for course in courses:
            writer.writerow(
                {
                    "id": course.get("id", ""),
                    "external_id": course.get("externalId", ""),
                    "title": course.get("title", ""),
                    "description": course.get("description", ""),
                    "status": course.get("status", ""),
                    "locale": course.get("locale", ""),
                    "is_mandatory": course.get("isMandatory", ""),
                    "is_published": course.get("isPublished", ""),
                    "due_by": course.get("dueBy", ""),
                    "duration_seconds": course.get("duration", ""),
                    "duration_formatted": format_duration(course.get("duration")),
                    "lesson_count": course.get("LessonCount", ""),
                    "created_datetime": course.get("createdDatetime", ""),
                    "modified_datetime": course.get("modifiedDatetime", ""),
                    "thumbnail_url": course.get("thumbnailUrl", ""),
                    "logo_url": course.get("logoUrl", ""),
                    "branding_image_url": course.get("brandingImageUrl", ""),
                }
            )

    print(f"Saved {len(courses)} courses to {filename}")


def main():
    if not TOKEN:
        print("Error: TOKEN not set in script")
        print("Please set your token in the TOKEN variable at the top of main.py")
        return

    start_time = datetime.now()
    print("SafetyCulture Course Export")
    print("=" * 60)

    courses = fetch_all_courses()

    output_file = "output.csv"
    write_csv(courses, output_file)

    duration = datetime.now() - start_time
    print("=" * 60)
    print(f"Total courses exported: {len(courses):,}")
    print(f"Runtime: {duration.total_seconds():.1f}s")
    print("=" * 60)


main()
