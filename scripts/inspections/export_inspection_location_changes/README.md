# Export Inspection Location Changes

Exports location/address field changes from SafetyCulture inspection revision history with async parallel processing. Analyzes inspection history to identify when location fields were modified, excluding initial responses.

## Quick Start

1. **Install dependencies**: `pip install -r ../../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Prepare input**: Create `input.csv` with inspection audit IDs
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token with inspection read permissions
- Input CSV with inspection audit IDs

## Input Format

Create `input.csv` with a single column:
```csv
audit_id
audit_abc123def456
audit_def456ghi789
audit_ghi789jkl012
```

**Column Description:**
- `audit_id` (required): The inspection audit ID

## Output

Generates timestamped CSV: `location_changes_YYYYMMDD_HHMMSS.csv`

Example: `location_changes_20250107_143022.csv`

**CSV Columns:**
- `audit_id`: Inspection ID where the change occurred
- `user_id`: SafetyCulture user ID who made the change
- `user_name`: User's full name
- `old_location_text`: Previous address/location value
- `new_location_text`: New address/location value
- `timestamp`: When the change occurred (ISO 8601 format)
- `revision_id`: Revision ID for traceability

**Example Output:**
```csv
audit_id,user_id,user_name,old_location_text,new_location_text,timestamp,revision_id
audit_abc123,user_456,John Smith,123 Main St,456 Oak Ave,2025-01-07T14:30:00Z,rev_789
audit_def456,user_457,Jane Doe,Paris France,London UK,2025-01-06T09:15:00Z,rev_790
```

## API Reference

- **Endpoint**: `GET /inspections/history/{audit_id}/revisions`
- **Query Parameters**:
  - `offset`: Pagination offset (increments by 10)
  - `limit`: Results per page (set to 10)
- **Response Structure**:
  ```json
  {
    "results": [
      {
        "audit_id": "string",
        "author": "user_id",
        "author_name": "User Name",
        "modified_at": "2025-01-07T10:30:00Z",
        "revision_id": "rev_123",
        "changes": [
          {
            "field_type": "address",
            "label": "Location",
            "old_response": {
              "location_text": "123 Old St"
            },
            "new_response": {
              "location_text": "456 New Ave"
            }
          }
        ]
      }
    ],
    "results_count": 47
  }
  ```

## Business Logic: Location Change Detection

The script filters inspection revision history for actual location changes using these rules:

### Filtering Rules (Applied in Order):

1. **Field Type Filter**: Only includes changes where `field_type == "address"`
2. **Exclude Initial Responses**: Skips changes where `old_response.location_text == "N/A - Initial Response"`
3. **Exclude Unchanged Values**: Skips changes where old and new location text are identical

### Examples:

| Scenario | Old Value | New Value | Included? | Reason |
|----------|-----------|-----------|-----------|--------|
| Initial creation | N/A - Initial Response | "123 Main St" | ❌ No | Initial response, not a change |
| Location modified | "123 Main St" | "456 Oak Ave" | ✅ Yes | Actual location change |
| Location unchanged | "123 Main St" | "123 Main St" | ❌ No | Values are identical |
| Non-address field | "John Smith" | "Jane Doe" | ❌ No | Not an address field |

## Features

- **Two-level async parallelism**: Processes multiple inspections concurrently AND fetches history pages in parallel per inspection
- **Automatic pagination**: Fetches all revision history pages automatically
- **Intelligent retry logic**: Up to 3 attempts with exponential backoff for failed requests
- **Progress tracking**: Real-time console progress with tqdm
- **Streaming CSV output**: Results written immediately (not batched at end)
- **Error resilience**: Continues processing remaining inspections on errors
- **Memory efficient**: Streams data to disk, doesn't accumulate in memory
- **Timestamped output**: Unique output filenames prevent overwriting

## Important Notes

- **Revision history depth**: Script fetches up to 1000 revisions per inspection (100 pages × 10 results)
- **Address fields only**: Only tracks `field_type == "address"` changes; other field types are ignored
- **Initial responses excluded**: Setting an address for the first time is not considered a "change"
- **Concurrent processing**: Processes up to 12 inspections simultaneously
- **CSV encoding**: UTF-8 encoding for international characters
- **Empty results**: Inspections with no location changes will not appear in output CSV

## Example Usage

```bash
# Navigate to script directory
cd scripts/inspections/export_inspection_location_changes/

# Install dependencies (if not already installed)
pip install -r ../../../requirements.txt

# Edit main.py to add your API token
# Create input.csv with inspection audit IDs

# Run the script
python main.py
```

## Console Output Example

```
================================================================================
🚀 SafetyCulture Inspection Location Changes Exporter
================================================================================
📋 Loaded 50 inspections from input.csv

================================================================================

🚀 Starting location changes export for 50 inspections...
⚡ Concurrency: 12 parallel inspections
📊 Output file: location_changes_20250107_143022.csv

Processing inspections: 100%|██████████| 50/50 [00:08<00:00, 6.25 inspections/s]
✅ audit_abc123: Found 3 location changes
📝 audit_def456: No location changes found
✅ audit_ghi789: Found 7 location changes
⚠️  audit_invalid123: No history found or error fetching
✅ audit_jkl012: Found 1 location changes
...

================================================================================
📊 EXPORT SUMMARY
================================================================================
📝 Total Inspections: 50
✅ Processed: 50
📍 Total Location Changes: 127
⏱️  Total Time: 0m 8s

💾 Results saved to: /path/to/scripts/inspections/export_inspection_location_changes/location_changes_20250107_143022.csv
================================================================================
```

## Troubleshooting

**Error: TOKEN not set**
- Edit `main.py` and replace `TOKEN = ""` with your API token

**Error: input.csv not found**
- Create `input.csv` in the same directory as `main.py`
- Ensure it has the `audit_id` column header

**Error: input.csv missing required column: audit_id**
- Check that CSV has an `audit_id` column
- Column name must match exactly (case-sensitive)

**No location changes found for valid inspections**
- The inspection may not have any address field changes
- Only modifications to existing addresses are tracked (not initial settings)
- Check that the inspection actually has address/location fields
- Verify the location was changed after initial creation

**404 errors on valid audit IDs**
- Verify the audit ID exists in your organization
- Check that your API token has appropriate permissions
- Ensure the inspection hasn't been deleted

**No history found or error fetching**
- Some inspections may have no revision history
- Network errors during fetch will show this message
- Script will continue processing remaining inspections

**Rate limit errors (429)**
- Script automatically handles rate limiting with retries
- If you see persistent 429 errors, reduce `SEMAPHORE_VALUE` in the script

## Performance

### Expected Performance:

For 100 inspections with average 5 pages (50 revisions) each:
- **Two-level parallelism**: ~3-5 seconds
- **Parallel inspections only**: ~8 seconds
- **Sequential approach**: ~100 seconds

The two-level async parallelism achieves approximately **20-30x speedup** over sequential processing.

### Performance Factors:

- **Number of inspections**: Linear scaling with inspection count
- **Revision history depth**: More revisions = more pages to fetch
- **Network latency**: Affects page fetch times
- **Concurrent limit**: Default 12 parallel inspections balances speed and API limits

## Performance Tips

- **Batch size**: Script handles hundreds of inspections efficiently
- **Network**: Stable internet connection recommended
- **Concurrent limit**: Increase `SEMAPHORE_VALUE` (max 20) for faster processing if API allows
- **CSV streaming**: Results appear in CSV file as inspections complete

## API Behavior Notes

- **Pagination**: History endpoint returns 10 results per page
- **Parallel page fetching**: Script fetches all pages concurrently per inspection
- **Safety limit**: Maximum 100 pages (1000 revisions) per inspection
- **Empty pages**: Script stops fetching when empty page is encountered
- **Revision order**: API returns revisions in chronological order

## Use Cases

- **Compliance auditing**: Track when inspection locations were changed and by whom
- **Data quality**: Identify inspections with frequent location corrections
- **Audit trail**: Maintain history of location field modifications
- **Reporting**: Generate reports on location update patterns
- **Anomaly detection**: Identify unusual location change behavior
