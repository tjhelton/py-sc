# Stop Action Recurrence

Removes recurring schedules from actions without deleting the actions themselves. Provide a CSV of `action_id` and `schedule_id` pairs and the script will delete each schedule, stopping future recurrences while keeping the action record intact.

## Quick Start

1. **Install dependencies**: `pip install -r ../../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` with your SafetyCulture API token
3. **Prepare input**: Create `input.csv` with required format
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- Input CSV with action and schedule ID pairs

## Input Format

Create `input.csv` with:
```csv
action_id,schedule_id
c390db3b-24d8-4a7f-ab91-7d81a0d5faa9,88250caa-36e5-410c-bb1a-c3aa09b5edd6
a1b2c3d4-5678-90ab-cdef-1234567890ab,f9e8d7c6-5432-10ab-cdef-fedcba987654
```

## Output

Generates `stop_recurrence_log_YYYYMMDD_HHMMSS.csv` with:
- `action_id` - The action whose schedule was removed
- `schedule_id` - The deleted schedule ID
- `status` - `success` or `error`
- `status_code` - HTTP status code
- `message` - Error details (empty on success)

## API Reference

- Delete action schedule: `POST /tasks/v1/actions:DeleteActionSchedule`

## Notes

- Duplicate pairs in the CSV are automatically deduplicated
- Requests retry up to 3 times on 429/5xx errors with exponential backoff
- The action record itself is never modified or deleted
