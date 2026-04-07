# Export Schedule Items

Fetches all schedule items from a SafetyCulture organisation and exports them to a timestamped CSV file. Supports filtering by schedule status via command-line arguments.

## Quick Start

1. **Install dependencies**: `pip install -r ../../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` with your SafetyCulture API token
3. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token

## Usage

```bash
# Export all schedules (no filter)
python main.py

# Export only active schedules
python main.py --status ACTIVE

# Export active and paused schedules
python main.py --status ACTIVE PAUSED
```

### Status Filter Options

| Status     | Description                  |
|------------|------------------------------|
| `ACTIVE`   | Currently active schedules   |
| `PAUSED`   | Paused schedules             |
| `ARCHIVED` | Archived schedules           |

## Output

Generates a timestamped CSV file (e.g., `schedules_export_20260406_143000.csv`) with the following columns:

- `id` - Schedule item ID
- `status` - Current status (ACTIVE, PAUSED, ARCHIVED)
- `description` - Schedule description
- `recurrence` - Recurrence rule (RRULE format)
- `start_time_hour`, `start_time_minute` - Scheduled start time
- `duration` - Duration (ISO 8601)
- `timezone` - Schedule timezone
- `from_date`, `to_date` - Active date range
- `can_late_submit`, `must_complete` - Completion settings
- `site_based_assignment_enabled` - Site-based assignment flag
- `location_id`, `asset_id` - Associated location/asset
- `document_id`, `document_type` - Associated template/document
- `creator_name` - Schedule creator
- `created_at`, `modified_at` - Timestamps
- `next_occurrence_start`, `next_occurrence_due` - Next scheduled occurrence
- `assignees` - JSON array of assignees
- `reminders` - JSON array of reminders

## API Reference

- Endpoint: `GET /schedules/v1/schedule_items`
- [Documentation](https://developer.safetyculture.com/reference/schedulesservice_listscheduleitems)

## Notes

- Pagination is handled automatically (fetches all pages)
- Multiple status values can be passed to filter by more than one status at a time
- Output filenames are timestamped to avoid overwriting previous exports
