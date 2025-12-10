import csv
import datetime
import json

import pandas as pd
import requests

TOKEN = ""  # Set your SafetyCulture API token here


def init_csv_log():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"deletion_log_{timestamp}.csv"

    with open(log_filename, "w", newline="") as csvfile:
        fieldnames = [
            "timestamp",
            "chunk_number",
            "chunk_size",
            "status_code",
            "success",
            "error_message",
            "action_ids",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

    return log_filename


def log_to_csv(
    log_filename,
    chunk_number,
    chunk_size,
    status_code,
    success,
    error_message,
    action_ids,
):
    timestamp = datetime.datetime.now().isoformat()

    with open(log_filename, "a", newline="") as csvfile:
        fieldnames = [
            "timestamp",
            "chunk_number",
            "chunk_size",
            "status_code",
            "success",
            "error_message",
            "action_ids",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writerow(
            {
                "timestamp": timestamp,
                "chunk_number": chunk_number,
                "chunk_size": chunk_size,
                "status_code": status_code,
                "success": success,
                "error_message": error_message,
                "action_ids": json.dumps(action_ids),
            }
        )


def read_csv():
    df = pd.read_csv("input.csv")
    csv = df.to_dict("records")
    return csv


def chunk_actions(actions):
    for i in range(0, len(actions), 300):
        yield actions[i : i + 300]


def delete_actions(actions, chunk_number, total_chunks, log_filename):
    url = "https://api.safetyculture.io/tasks/v1/actions/delete"
    payload = {"ids": actions}
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {TOKEN}",
    }

    print(f"\n[CHUNK {chunk_number}/{total_chunks}] Deleting {len(actions)} actions...")
    print(
        f"[CHUNK {chunk_number}/{total_chunks}] Action IDs: {actions[:3]}{'...' if len(actions) > 3 else ''}"
    )

    try:
        response = requests.post(url, json=payload, headers=headers)

        success = response.status_code == 200
        error_message = None if success else response.text

        if success:
            print(
                f"[CHUNK {chunk_number}/{total_chunks}] ✅ SUCCESS - Status: {response.status_code}"
            )
            print(f"[CHUNK {chunk_number}/{total_chunks}] Response: {response.text}")
        else:
            print(
                f"[CHUNK {chunk_number}/{total_chunks}] ❌ ERROR - Status: {response.status_code}"
            )
            print(
                f"[CHUNK {chunk_number}/{total_chunks}] Error Response: {response.text}"
            )

        log_to_csv(
            log_filename,
            chunk_number,
            len(actions),
            response.status_code,
            success,
            error_message,
            actions,
        )

    except Exception as e:
        error_message = str(e)
        print(f"[CHUNK {chunk_number}/{total_chunks}] ❌ EXCEPTION - {error_message}")
        log_to_csv(
            log_filename,
            chunk_number,
            len(actions),
            None,
            False,
            error_message,
            actions,
        )

    print(
        f"[CHUNK {chunk_number}/{total_chunks}] Progress: {chunk_number}/{total_chunks} chunks completed ({(chunk_number / total_chunks) * 100:.1f}%)"
    )


def main():
    print("🚀 Starting bulk action deletion process...")

    if not TOKEN:
        print("❌ Error: TOKEN not set in script")
        print("Please set your token in the TOKEN variable at the top of main.py")
        return 1

    log_filename = init_csv_log()
    print(f"📊 CSV log file created: {log_filename}")

    csv = read_csv()
    actions = [row["id"] for row in csv]
    chunked = list(chunk_actions(actions))

    total_actions = len(actions)
    total_chunks = len(chunked)

    print(f"📋 Total actions to delete: {total_actions}")
    print(f"📦 Total chunks (300 actions each): {total_chunks}")
    print(f"⏰ Started at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    for i, chunk in enumerate(chunked, 1):
        delete_actions(chunk, i, total_chunks, log_filename)

    print("\n" + "=" * 60)
    print("✅ Bulk deletion process completed!")
    print(f"📊 Results logged to: {log_filename}")
    print(f"⏰ Finished at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


main()
