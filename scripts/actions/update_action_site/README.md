# Update Action Site

Bulk update the site assigned to actions in SafetyCulture using async API calls with live Rich console output.

## Quick Start

1. **Install dependencies**: `pip install -r ../../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` with your SafetyCulture API token in `main.py`
3. **Prepare input**: Create `input.csv` with required format
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- Input CSV with action IDs and target site IDs

## Input Format

Create `input.csv` with:

```csv
action_id,site_id
action_abc123,site_uuid-1234-5678-abcd-ef0123456789
action_def456,site_uuid-9876-5432-abcd-ef0123456789
```

## Output

Generates `output.csv` with:

- `action_id` - The action that was updated
- `site_id` - The target site ID
- `result` - SUCCESS or ERROR
- `error_message` - Error details (empty on success)
- `timestamp` - When the request was made

## Features

- **Async execution**: Up to 400 requests/second with token bucket rate limiting
- **Live console**: Rich live display showing progress, rate, ETA, and recent activity
- **Resume support**: Re-run safely; already-processed actions are skipped automatically
- **Retry logic**: Automatic retries with exponential backoff for transient errors (429, 5xx)
- **Batch processing**: Processes records in chunks of 5000 to manage memory
- **CSV logging**: Real-time output CSV updated as each record is processed

## API Reference

- Endpoint: `PUT /tasks/v1/actions/{task_id}/site`
- [SafetyCulture API Documentation](https://developer.safetyculture.com/reference/actionsservice_updatesite)

## Notes

- Rate limit is configurable via `MAX_REQUESTS_PER_SECOND` (default: 400)
- Concurrency is configurable via `SEMAPHORE_VALUE` (default: 100)
- Output CSV supports append mode for resume capability across runs
