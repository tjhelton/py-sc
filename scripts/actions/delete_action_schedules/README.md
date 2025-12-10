# Delete Action Schedules

Bulk deletes recurring action schedules. Accepts a CSV of `action_id` and `schedule_id` pairs or, if the CSV is absent/empty, it fetches all actions with schedules via `/tasks/v1/actions/list` and removes their schedules with `/tasks/v1/actions:DeleteActionSchedule`. Requests run asynchronously with a conservative concurrency limit.

## Quick start
- Install deps: `pip install -r ../../requirements.txt`
- Set your API token in `main.py` (`TOKEN = ""`)
- Option A: populate `input.csv` with `action_id,schedule_id`; Option B: leave it empty to auto-discover schedules
- Run: `python main.py`

## Input options
- CSV mode: `input.csv` with headers `action_id,schedule_id`
- Auto-discovery: If CSV is missing or empty, the script pages through `/tasks/v1/actions/list` (`page_size=100`, `without_count=true`) using offset-based parallel requests, extracts `references` of type `SCHEDULE`, and deletes them.

Example CSV:
```csv
action_id,schedule_id
c390db3b-24d8-4a7f-ab91-7d81a0d5faa9,88250caa-36e5-410c-bb1a-c3aa09b5edd6
```

## Behavior
- Async pagination with offset-based prefetch to keep the pipeline warm
- Async deletions with concurrency defaulted to 10 (about half typical limits) plus light retry on 429/5xx
- Deduplicates schedule/action pairs before deletion
- Writes a log CSV (`delete_action_schedules_log_YYYYMMDD_HHMMSS.csv`) containing `action_id`, `schedule_id`, `status`, `status_code`, and `message`

## Configuration
- `PAGE_SIZE` (default 100) for listing actions
- `DELETE_CONCURRENCY` (default 10) for delete calls; adjust if your org limits differ
- `INPUT_CSV_NAME` for custom CSV name/location

## API reference
- List actions: `POST /tasks/v1/actions/list`
- Delete action schedule: `POST /tasks/v1/actions:DeleteActionSchedule`

## Notes
- The script ignores actions without a `SCHEDULE` reference
- TOKEN is required; the script exits early if it is not set
- Logs are written to the script directory
