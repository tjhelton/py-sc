import datetime
import json

import pandas as pd
import requests

TOKEN = ""


def read_csv():
    """Read input CSV and return as list of dictionaries."""
    df = pd.read_csv("input.csv").fillna("")
    csv = df.to_dict("records")
    return csv


def get_user_identifier():
    """Prompt user to choose between user_id or email."""
    while True:
        choice = input("Use user_id or email? (user_id/email): ").strip().lower()
        if choice in ["user_id", "email"]:
            return choice
        print('Invalid choice. Please enter "user_id" or "email".')


def get_validate_only():
    """Prompt user to choose validation mode."""
    while True:
        choice = input("Validate only? (true/false): ").strip().lower()
        if choice in ["true", "false"]:
            return choice == "true"
        print('Invalid choice. Please enter "true" or "false".')


def map_users_for_deactivation(csv, identifier_type):
    """Map CSV data to user deactivation payloads."""
    mapped = []
    for row in csv:
        if identifier_type == "user_id":
            if not row.get("user_id"):
                print(f"Warning: Skipping row with missing user_id: {row}")
                continue
            user_obj = {"user_id": row["user_id"], "status": "deactivated"}
        else:  # email
            if not row.get("email"):
                print(f"Warning: Skipping row with missing email: {row}")
                continue
            user_obj = {"username": row["email"], "status": "deactivated"}

        mapped.append({"user": user_obj})
    return mapped


def chunk_users(users, chunk_size=2000):
    """Split users into chunks of specified size."""
    for i in range(0, len(users), chunk_size):
        yield users[i : i + chunk_size]


def initialize_bulk_job(users):
    """Initialize a bulk user upsert job."""
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
        job_id = response.json()["job_id"]
        print(f"  ✅ Initialized job: {job_id}")
        return job_id
    except requests.exceptions.RequestException as error:
        print(f"  ❌ ERROR initializing job - {error}")
        if hasattr(error, "response") and error.response is not None:
            print(f"  Response: {error.response.text}")
        return None


def start_bulk_job(job_id, validate_only):
    """Start a bulk user upsert job."""
    try:
        url = f"https://api.safetyculture.io/users/v1/users/upsert/jobs/{job_id}"
        payload = {
            "origin": {"source": "SOURCE_UNSPECIFIED"},
            "validate_only": validate_only,
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {TOKEN}",
        }
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        result_job_id = response.json()["job_id"]
        print(f"  ✅ Started job: {result_job_id}")
        return result_job_id
    except requests.exceptions.RequestException as error:
        print(f"  ❌ ERROR starting job - {error}")
        if hasattr(error, "response") and error.response is not None:
            print(f"  Response: {error.response.text}")
        return None


def get_job_results(job_id):
    """Get results of a bulk user upsert job."""
    try:
        url = f"https://api.safetyculture.io/users/v1/users/upsert/jobs/{job_id}"
        headers = {"accept": "application/json", "authorization": f"Bearer {TOKEN}"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        result = response.json()
        print("  ✅ Retrieved job results")
        return result
    except requests.exceptions.RequestException as error:
        print(f"  ❌ ERROR getting job results - {error}")
        if hasattr(error, "response") and error.response is not None:
            print(f"  Response: {error.response.text}")
        return {"error": str(error), "job_id": job_id}


def process_chunk(chunk, chunk_num, total_chunks, validate_only):
    """Process a single chunk of users."""
    print(f"\n[CHUNK {chunk_num}/{total_chunks}] Processing {len(chunk)} users...")

    # Initialize job
    job_id = initialize_bulk_job(chunk)
    if not job_id:
        return {
            "chunk": chunk_num,
            "status": "failed",
            "error": "Failed to initialize job",
        }

    # Start job
    result_job_id = start_bulk_job(job_id, validate_only)
    if not result_job_id:
        return {
            "chunk": chunk_num,
            "status": "failed",
            "error": "Failed to start job",
            "job_id": job_id,
        }

    # Get results
    results = get_job_results(result_job_id)

    return {
        "chunk": chunk_num,
        "status": "success",
        "job_id": result_job_id,
        "users_processed": len(chunk),
        "results": results,
    }


def save_results_to_json(all_results, identifier_type, validate_only):
    """Save all results to a timestamped JSON file."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"deactivation_results_{timestamp}.json"

    output = {
        "timestamp": timestamp,
        "identifier_type": identifier_type,
        "validate_only": validate_only,
        "total_chunks": len(all_results),
        "chunks": all_results,
    }

    with open(filename, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n📊 Results saved to: {filename}")
    return filename


def main():
    print("🚀 Starting bulk user deactivation process...\n")

    # Validate API token
    if not TOKEN:
        print("❌ Error: TOKEN not set in script")
        print("Please set your token in the TOKEN variable at the top of main.py")
        return 1

    # Get user preferences
    identifier_type = get_user_identifier()
    validate_only = get_validate_only()

    print("\n📋 Configuration:")
    print(f"  - Identifier type: {identifier_type}")
    print(f"  - Validate only: {validate_only}")

    # Read and map CSV data
    print("\n📂 Reading input.csv...")
    csv_data = read_csv()
    print(f"  Found {len(csv_data)} rows")

    # Validate CSV has required column
    if identifier_type == "user_id" and "user_id" not in csv_data[0]:
        print('❌ Error: input.csv must have a "user_id" column')
        return 1
    if identifier_type == "email" and "email" not in csv_data[0]:
        print('❌ Error: input.csv must have an "email" column')
        return 1

    print("\n🔄 Mapping users for deactivation...")
    mapped_users = map_users_for_deactivation(csv_data, identifier_type)
    print(f"  Mapped {len(mapped_users)} users")

    if not mapped_users:
        print("❌ Error: No valid users to process")
        return 1

    # Chunk users
    chunks = list(chunk_users(mapped_users, 2000))
    total_chunks = len(chunks)
    print(f"\n📦 Split into {total_chunks} chunks (max 2000 users per chunk)")

    # Process each chunk
    print("\n" + "=" * 60)
    print("Processing chunks...")
    print("=" * 60)

    all_results = []
    for i, chunk in enumerate(chunks, 1):
        result = process_chunk(chunk, i, total_chunks, validate_only)
        all_results.append(result)

        # Show progress
        print(
            f"[CHUNK {i}/{total_chunks}] Progress: {i}/{total_chunks} chunks completed ({(i / total_chunks) * 100:.1f}%)"
        )

    # Save results
    print("\n" + "=" * 60)
    print("✅ Bulk deactivation process completed!")
    print("=" * 60)

    output_file = save_results_to_json(all_results, identifier_type, validate_only)

    # Summary
    successful_chunks = sum(1 for r in all_results if r["status"] == "success")
    total_users = sum(r.get("users_processed", 0) for r in all_results)

    print("\n📈 Summary:")
    print(f"  - Total users processed: {total_users}")
    print(f"  - Successful chunks: {successful_chunks}/{total_chunks}")
    print(f"  - Failed chunks: {total_chunks - successful_chunks}/{total_chunks}")
    print(f"  - Output file: {output_file}")

    return 0


if __name__ == "__main__":
    main()
