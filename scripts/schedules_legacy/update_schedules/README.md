# Update Schedules

Exports all schedule items to a CSV, lets you edit the fields you want to change, then applies updates via bulk PUT requests. Only rows with actual changes are sent to the API.

## Quick Start

1. **Install dependencies**: `pip install -r ../../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` with your SafetyCulture API token
3. **Run script**: `python main.py`
4. **Edit the exported CSV**: The script opens `schedules_export.csv` automatically
5. **Confirm changes**: Press Enter when done editing — the script applies only changed rows

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token

## Usage

```bash
# Export and update all schedule items
python main.py

# Export only schedules with specific statuses
python main.py --status active paused
```

**Available status filters**: `active`, `paused`, `no_template`, `no_assignee`, `finished`, `subscription_inactive`, `no_site`

## Editable CSV Columns

After export, you can modify any of these columns:

| Column | Description |
|--------|-------------|
| `description` | Schedule name/description |
| `recurrence` | iCal RRULE string (e.g. `FREQ=WEEKLY;BYDAY=MO`) |
| `start_time_hour` | Hour of day (0–23) |
| `start_time_minute` | Minute of hour (0–59) |
| `duration` | ISO 8601 duration (e.g. `PT1H`) |
| `timezone` | IANA timezone name (e.g. `America/New_York`) |
| `from_date` | Schedule start date (YYYY-MM-DD) |
| `to_date` | Schedule end date (YYYY-MM-DD) |
| `can_late_submit` | Allow late submissions (`true`/`false`) |
| `must_complete` | Require completion (`true`/`false`) |
| `site_based_assignment_enabled` | Enable site-based assignment (`true`/`false`) |
| `location_id` | Site/location ID |
| `asset_id` | Asset ID |
| `document_id` | Template or document ID |
| `document_type` | Document type (e.g. `TEMPLATE`) |
| `assignees` | JSON array: `[{"id": "...", "type": "USER"}]` |
| `reminders` | JSON array: `[{"event": "START", "duration": "PT5M"}]` |

**Read-only columns** (changes are ignored): `id`, `status`, `creator_name`, `created_at`, `modified_at`, `next_occurrence_start`, `next_occurrence_due`

## Output

Generates `schedules_export.csv` with all schedule items. After confirming, the script logs success/error counts to the terminal. No output CSV is written — the export file serves as both input and working copy.

## API Reference

- List schedules: `GET /schedules/v1/schedule_items`
- Update schedule: `PUT /schedules/v1/schedule_items/{id}`
- [SafetyCulture Schedules API](https://developer.safetyculture.com/reference/schedulesservice_listscheduleitems)

## Notes

- Up to 20 concurrent requests with automatic retry on 429/5xx errors (exponential backoff, 3 attempts)
- `assignees` and `reminders` must be valid JSON arrays — invalid JSON is skipped with a warning
- Only changed rows are sent to the API; unchanged rows are ignored
