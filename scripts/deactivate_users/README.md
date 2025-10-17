# Deactivate Users

Deactivates SafetyCulture users in bulk via API using the user upsert job system. Supports deactivation by user_id or email with validation mode and chunked processing.

## Quick Start

1. **Install dependencies**: `pip install -r ../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Prepare input**: Create `input.csv` with user_id or email column
4. **Run script**: `python main.py`
5. **Follow prompts**:
   - Choose identifier type: `user_id` or `email`
   - Choose validation mode: `true` (validate only) or `false` (execute)

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token with user management permissions
- Input CSV with user identifiers (user_id or email)

## Input Format

Create `input.csv` with **either** user_id **or** email column:

### Option 1: Using user_id
```csv
user_id
user_123abc
user_456def
user_789ghi
```

### Option 2: Using email
```csv
email
john.doe@company.com
jane.smith@company.com
bob.wilson@company.com
```

**Note**: The script will prompt you to choose which column to use.

## Output

Generates timestamped JSON file `deactivation_results_{timestamp}.json` with:
- Processing timestamp and configuration
- Results for each chunk processed
- Job IDs and status for each batch
- Complete API response data for auditing

Example output structure:
```json
{
  "timestamp": "20250108_143022",
  "identifier_type": "email",
  "validate_only": false,
  "total_chunks": 2,
  "chunks": [
    {
      "chunk": 1,
      "status": "success",
      "job_id": "job_abc123",
      "users_processed": 2000,
      "results": { ... }
    }
  ]
}
```

## Interactive Prompts

The script will ask for:

1. **Identifier type**:
   - `user_id` - Uses user_id field from CSV
   - `email` - Uses email field from CSV (sent as username)

2. **Validation mode**:
   - `true` - Validates users without deactivating (dry run)
   - `false` - Actually deactivates users

## Processing Details

- **Chunking**: Automatically splits users into batches of 2000 (API limit)
- **Status**: Sets user status to "deactivated" for each user
- **Progress**: Shows real-time progress for each chunk
- **Error handling**: Continues processing remaining chunks if one fails
- **Results**: All API responses saved to timestamped JSON file

## API Reference

- Initialize: `POST /users/v1/users/upsert/jobs`
- Start: `POST /users/v1/users/upsert/jobs/{job_id}`
- Get Results: `GET /users/v1/users/upsert/jobs/{job_id}`
- [Documentation](https://developer.safetyculture.com/reference/usersservice_createupsertjob)

## Notes

- Validation mode (`validate_only: true`) is recommended for first run
- Script validates CSV has the correct column before processing
- Each chunk is processed sequentially: initialize → start → get results
- Maximum 2000 users per batch to comply with API limits
- Failed chunks are logged but don't stop processing
- All results include complete API response for audit trail

## Example Usage

```bash
$ python main.py
🚀 Starting bulk user deactivation process...

Use user_id or email? (user_id/email): email
Validate only? (true/false): true

📋 Configuration:
  - Identifier type: email
  - Validate only: True

📂 Reading input.csv...
  Found 5000 rows

🔄 Mapping users for deactivation...
  Mapped 5000 users

📦 Split into 3 chunks (max 2000 users per chunk)

============================================================
Processing chunks...
============================================================

[CHUNK 1/3] Processing 2000 users...
  ✅ Initialized job: job_abc123
  ✅ Started job: job_abc123
  ✅ Retrieved job results
[CHUNK 1/3] Progress: 1/3 chunks completed (33.3%)

...

============================================================
✅ Bulk deactivation process completed!
============================================================

📊 Results saved to: deactivation_results_20250108_143022.json

📈 Summary:
  - Total users processed: 5000
  - Successful chunks: 3/3
  - Failed chunks: 0/3
  - Output file: deactivation_results_20250108_143022.json
```
