# Delete Inspections (Bulk)

Permanently deletes SafetyCulture inspections in bulk using async deletion pattern. Processes high-volume deletions with intelligent retry logic, real-time progress tracking, and live CSV output logging.

## Quick Start

1. **Install dependencies**: `pip install -r ../../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Prepare input**: Create `input.csv` with inspection audit IDs
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token with deletion permissions
- Input CSV with inspection audit IDs to delete

## Input Format

Create `input.csv` with inspection audit IDs:
```csv
audit_id
audit_abc123def456
audit_def456ghi789
audit_ghi789jkl012
```

**Column Descriptions:**
- `audit_id` (required): The inspection audit ID to delete

## Output

Generates `output.csv` with real-time deletion results:
- `audit_id`: The inspection audit ID
- `status`: SUCCESS or ERROR
- `error_message`: Error details if deletion failed (empty on success)
- `timestamp`: When the deletion completed/failed

## API Reference

- **Endpoint**: `DELETE /inspections/v1/inspections/{id}`
- **Method**: DELETE
- **Path Parameter**: `id` - The inspection identifier to delete
- **Response**: 200 on successful deletion
- **Documentation**: [Delete Inspection API](https://developer.safetyculture.com/reference/inspectionservice_deleteinspection)

## Features

- **Async processing**: High-speed concurrent deletions
- **Automatic retry logic**: Up to 3 attempts with exponential backoff for failed requests
- **Rate limiting**: Processes up to 500 requests per minute safely
- **Progress bar**: Real-time console progress with tqdm
- **Live logging**: Each deletion/error logged to console as it happens
- **Live CSV output**: Results written immediately (not batched at end)
- **Error resilience**: Continues processing remaining inspections on errors
- **Confirmation prompt**: Requires typing "DELETE" to prevent accidental execution
- **High-volume capable**: Designed to handle 100,000+ deletions efficiently

## Safety Features

- **Confirmation required**: Must type "DELETE" to proceed with bulk deletion
- **Permanent operation**: Inspections cannot be recovered after deletion
- **Warning message**: Clear indication of total inspections to be deleted
- **Live logging**: Immediate feedback on what has been deleted
- **Error tracking**: Failed deletions are logged for retry

## Important Notes

- **Permanent deletion**: This operation cannot be undone - deleted inspections are unrecoverable
- **Permissions**: API token must have deletion permissions for inspections
- **CSV encoding**: UTF-8 encoding for international characters
- **Concurrent processing**: Processes up to 12 inspections simultaneously
- **Rate limits**: Automatically handles SafetyCulture API rate limits with retry logic
- **High volume**: Optimized for processing 100,000+ records efficiently

## Example Usage

```bash
# Navigate to script directory
cd scripts/inspections/delete_inspections/

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
🚀 SafetyCulture Inspection Bulk Deleter
================================================================================
📋 Loaded 1000 inspection IDs from input.csv

⚠️  WARNING: This will permanently delete all inspections in input.csv
⚠️  Total inspections to delete: 1000

Type "DELETE" to confirm: DELETE

================================================================================

🚀 Starting bulk deletion for 1000 inspections...
⚡ Rate limit: 500 requests per minute
📊 Live results: output.csv

Deleting inspections: 100%|██████████| 1000/1000 [03:25<00:00,  4.87 inspections/s]
✅ Deleted: audit_abc123def456
✅ Deleted: audit_def456ghi789
✅ Deleted: audit_ghi789jkl012
❌ Error: audit_invalid123 - HTTP 404: Inspection not found
✅ Deleted: audit_jkl012mno345
...

================================================================================
📊 DELETION SUMMARY
================================================================================
✅ Successful: 998
❌ Errors: 2
📝 Total: 1000
📈 Success Rate: 99.8%
⏱️  Total Time: 3m 25s

💾 Results log: /path/to/scripts/inspections/delete_inspections/output.csv
================================================================================
```

## Troubleshooting

**Error: TOKEN not set**
- Edit `main.py` and replace `TOKEN = ''` with your API token

**Error: input.csv not found**
- Create `input.csv` in the same directory as `main.py`
- Ensure it has the required column header: `audit_id`

**Error: input.csv missing required column**
- Check that CSV has `audit_id` column
- Column name must match exactly (case-sensitive)

**404 errors on valid audit IDs**
- Verify the audit ID exists in your organization
- Check that your API token has appropriate permissions
- Ensure the inspection hasn't already been deleted

**403 Permission errors**
- Verify your API token has deletion permissions for inspections
- Check organization-level permissions
- Some inspections may have restricted deletion based on ownership

**Rate limit errors (429)**
- Script automatically handles rate limiting with retries
- Exponential backoff delays between retry attempts
- If persistent, API limits may have changed - contact SafetyCulture support

**Deletion cancelled**
- Confirmation prompt was not answered with "DELETE" (case-sensitive)
- Re-run script and type "DELETE" exactly when prompted

## Performance Tips

- **Batch size**: Script handles 100,000+ inspections efficiently
- **Network**: Stable internet connection recommended
- **Concurrent limit**: Default 12 concurrent deletions balances speed and API limits
- **Rate limiting**: Automatically throttled to 500 requests per minute
- **Retry logic**: Failed requests automatically retried up to 3 times

## API Behavior Notes

- **Immediate deletion**: No polling required - deletion is synchronous
- **Response codes**:
  - 200: Successful deletion
  - 404: Inspection not found
  - 403: Permission denied
  - 429: Rate limit exceeded (auto-retried)
- **Idempotent**: Deleting already-deleted inspection returns 404
- **Permanent**: No recovery mechanism available

## Use Cases

- **Bulk cleanup**: Remove test or demo inspections
- **Data management**: Delete outdated inspections before archival cutoff
- **Compliance**: Remove inspections for data retention requirements
- **Migration**: Clean up after data migration projects
- **Testing**: Delete large volumes of test data

## Warning

This script performs permanent, irreversible deletions. Always:
1. Verify `input.csv` contains only inspections you want to delete
2. Back up important data before running
3. Test with a small batch first
4. Review the confirmation prompt carefully
5. Monitor the output CSV for unexpected errors
