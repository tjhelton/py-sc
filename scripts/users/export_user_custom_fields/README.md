# Fetch User Custom Fields

Exports all SafetyCulture users with their custom field values to CSV. Uses async API calls for fast processing with progress bars and automatic pagination.

## Quick Start

1. **Install dependencies**: `pip install -r ../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Run script**: `python main.py`
4. **View output**: Check generated `output.csv` (or `output_1.csv`, etc.)

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token with user and custom fields permissions
- No input file required (fetches all users automatically)

## Input Format

**No input file required.** The script automatically:
1. Fetches all available custom user field definitions
2. Fetches all users from the organization via datafeed
3. Fetches custom field values for each user concurrently

## Output

Generates `output.csv` (or numbered variant if file exists) with:
- All standard user fields (id, email, firstname, lastname, etc.)
- One column per custom user field
- Custom field columns use field names as headers
- Blank values for users without specific custom fields set

Example output structure:
```csv
id,email,firstname,lastname,Department,Employee ID,Location
user_123,john@company.com,John,Doe,Engineering,EMP001,New York
user_456,jane@company.com,Jane,Smith,Sales,,San Francisco
```

## Processing Details

- **Step 1**: Fetches available custom user field definitions from API
- **Step 2**: Fetches all users via paginated datafeed
- **Step 3**: Concurrently fetches custom field values for all users (rate limited to 10 concurrent requests)
- **Step 4**: Generates comprehensive CSV with all fields
- **Progress bars**: Shows real-time progress during user attribute fetching
- **Error handling**: Warns about users that fail but continues processing
- **Output safety**: Auto-increments filename if output.csv exists

## API Reference

- List Fields: `POST /users/v1/fields/list`
- Users Feed: `GET /feed/users` (with pagination)
- User Attributes: `GET /users/v1/users/{uuid}/attributes`
- [Documentation](https://developer.safetyculture.com/reference/usersservice_listfields)

## Notes

- Rate limited to 10 concurrent attribute requests to avoid API throttling
- Handles paginated datafeed automatically
- Preserves all user fields as separate columns
- Nested objects (like permissions) are serialized to JSON strings
- Custom field values support: string, number, boolean, and date types
- Script handles missing custom fields gracefully (blank values)
- UUID conversion handled automatically (strips `user_` prefix for attributes endpoint)

## Example Usage

```bash
$ python main.py
🚀 Starting user custom fields export...

Step 1: Fetching available custom user fields...
✅ Found 5 custom user fields

📋 Available custom fields:
   1. Department (ID: field_abc123, Type: STRING)
   2. Employee ID (ID: field_def456, Type: STRING)
   3. Location (ID: field_ghi789, Type: STRING)
   4. Start Date (ID: field_jkl012, Type: DATE)
   5. Manager (ID: field_mno345, Type: STRING)

============================================================
Step 2: Fetching users from datafeed...
============================================================
📥 Fetching users from datafeed...
  Fetched 1000 users (total: 1000)
  Fetched 1000 users (total: 2000)
  Fetched 456 users (total: 2456)
✅ Total users fetched: 2456

============================================================
Step 3: Fetching custom field values...
============================================================

📊 Fetching custom field values for 2456 users...
   Rate limit: 5 requests per second

Fetching user attributes: 100%|███████████████| 2456/2456 [02:15<00:00, 18.12user/s]
✅ Fetched attributes for 2456 users

============================================================
Step 4: Creating output CSV...
============================================================

📝 Creating output CSV...
✅ Output saved to: /Users/tj.helton/Documents/GitHub/py-sc/scripts/fetch_user_custom_fields/output.csv
   - Total users: 2456
   - Total columns: 42
   - Standard fields: 37
   - Custom fields: 5

============================================================
✅ Export completed successfully!
============================================================
```
