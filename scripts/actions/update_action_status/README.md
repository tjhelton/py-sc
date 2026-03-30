# Update Action Status

Bulk update action statuses in SafetyCulture using async API calls with live Rich console output.

## Quick Start

1. **Install dependencies**: `pip install -r ../../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` with your SafetyCulture API token in `main.py`
3. **Prepare input**: Create `input.csv` with required format
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- Input CSV with action IDs and target status IDs

## Input Format

Create `input.csv` with:

```csv
action_id,status_id
audit_abc123,7223d809-553e-4714-a038-62dc98f3fbf3
audit_def456,17e793a1-26a3-4ecd-99ca-f38ecc6eaa2e
```

### Valid Action Status IDs

| Status      | ID                                     |
|-------------|----------------------------------------|
| To do       | `17e793a1-26a3-4ecd-99ca-f38ecc6eaa2e` |
| In progress | `20ce0cb1-387a-47d4-8c34-bc6fd3be0e27` |
| Complete    | `7223d809-553e-4714-a038-62dc98f3fbf3` |
| Can't do    | `06308884-41c2-4ee0-9da7-5676647d3d75` |

## Output

Generates `output.csv` with:

- `action_id` - The action that was updated
- `status_id` - The target status ID
- `status_name` - Human-readable status name
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

- Endpoint: `PUT /tasks/v1/actions/{task_id}/status`
- [SafetyCulture API Documentation](https://developer.safetyculture.com/reference)

## Notes

- The script validates status IDs against known values but will send unrecognised IDs as-is
- Rate limit is configurable via `MAX_REQUESTS_PER_SECOND` (default: 400)
- Concurrency is configurable via `SEMAPHORE_VALUE` (default: 100)
- Output CSV supports append mode for resume capability across runs
