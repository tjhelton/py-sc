# Complete Inspections (Bulk)

**⚠️ PRIVATE ENDPOINT - NOT FOR PUBLIC DISTRIBUTION**

Completes SafetyCulture inspections in bulk using a private API endpoint. Processes up to 500 inspections per minute with real-time progress tracking and live CSV output.

## Quick Start

1. **Install dependencies**: `pip install -r ../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Prepare input**: Create `input.csv` with inspection audit IDs
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- Input CSV with audit IDs to complete

## Input Format

Create `input.csv` with single column for audit IDs:
```csv
audit_id
audit_abc123def456
audit_def456ghi789
audit_ghi789jkl012
```

## Output

Generates `output.csv` (or `output_1.csv`, etc.) with real-time results:
- `audit_id`: The inspection audit ID
- `status`: SUCCESS or ERROR
- `error_message`: Error details if completion failed (empty on success)
- `completion_timestamp`: Timestamp when API call was made

## API Reference

- **Endpoint**: `POST /inspections/v1/inspections/{audit_id}/complete`
- **Request Body**: `{"timestamp": "YYYY-MM-DDTHH:MM:SSZ"}` (auto-generated with current date at midnight UTC)
- **Example**: `{"timestamp": "2025-10-21T00:00:00Z"}`
- **Note**: This is a PRIVATE endpoint not documented in public API docs

## Features

- **Asynchronous processing**: Up to 500 requests per minute
- **Progress bar**: Real-time console progress with tqdm
- **Live logging**: Each completion/error logged to console as it happens
- **Live CSV output**: Results written immediately (not batched at end)
- **Error resilience**: Continues processing remaining inspections on errors
- **Timestamps**: Records exact time each API call was made
- **Rate limiting**: Automatic semaphore-based rate control

## Important Notes

- **Completion timestamp**: Automatically set to current date at midnight UTC in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)
- **Irreversible**: Inspection completion cannot be undone
- **Private API**: This endpoint is not publicly documented
- **Not tracked in Git**: This directory is excluded from version control
- **Error handling**: Script continues on errors and logs them to output CSV
- **Output safety**: Generates unique filenames (output.csv, output_1.csv, etc.) to avoid overwriting

## Example Usage

```bash
# Navigate to script directory
cd scripts/complete_inspections/

# Install dependencies (if not already installed)
pip install -r ../../requirements.txt

# Edit main.py to add your API token
# Create input.csv with audit IDs

# Run the script
python main.py
```

## Console Output Example

```
================================================================================
🚀 SafetyCulture Bulk Inspection Completion Tool
================================================================================
📋 Loaded 150 audit IDs from input.csv

================================================================================

📅 Completion timestamp set to: 2025-10-21T00:00:00Z
🚀 Starting bulk completion for 150 inspections...
⚡ Rate limit: 500 requests per minute
📊 Live results writing to: output.csv

Completing inspections: 100%|██████████| 150/150 [00:18<00:00,  8.33 inspections/s]
✅ Completed: audit_abc123def456
✅ Completed: audit_def456ghi789
❌ Error: audit_ghi789jkl012 - 404: Not Found
...

================================================================================
📊 COMPLETION SUMMARY
================================================================================
✅ Successful: 148
❌ Errors: 2
📝 Total: 150
📈 Success Rate: 98.7%

💾 Full results saved to: /path/to/scripts/complete_inspections/output.csv
================================================================================
```

## Troubleshooting

**Error: TOKEN not set**
- Edit `main.py` and replace `TOKEN = ""` with your API token

**Error: input.csv not found**
- Create `input.csv` in the same directory as `main.py`
- Ensure it has an `audit_id` column header

**Error: input.csv must have an 'audit_id' column**
- Check column header spelling (must be exactly `audit_id`)
- Ensure CSV is properly formatted

**Rate limit errors**
- Script automatically handles rate limiting
- If you see consistent 429 errors, reduce `max_requests_per_minute` in code

**404 errors on valid audit IDs**
- Verify the audit ID exists in your organization
- Check that the inspection hasn't already been completed
- Ensure your API token has appropriate permissions
