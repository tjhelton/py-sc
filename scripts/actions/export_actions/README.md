# Export Actions

Exports all SafetyCulture actions to CSV using high-performance async concurrent fetching. Retrieves action details including assignees, priorities, inspection links, and schedule references.

## Quick Start

1. **Install dependencies**: `pip install -r ../../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- Required package: `aiohttp`

## Output

Generates `output.csv` with the following columns:

| Column | Description |
|---|---|
| `action_id` | Unique action identifier |
| `unique_id` | Human-readable action ID |
| `creator_name` | Full name of the action creator |
| `creator_id` | User ID of the creator |
| `title` | Action title |
| `description` | Action description |
| `created_at` | Creation timestamp |
| `due_at` | Due date timestamp |
| `priority` | Priority label (None, Low, Medium, High) |
| `status` | Current action status |
| `assignees` | Comma-separated list of assigned users/groups |
| `template_id` | Associated template ID |
| `inspection_id` | Associated inspection ID |
| `item_id` | Associated inspection item ID |
| `item_label` | Inspection item label |
| `site_id` | Associated site ID |
| `site_name` | Associated site name |
| `modified_at` | Last modified timestamp |
| `completed_at` | Completion timestamp |
| `action_type` | Type of action |
| `schedule_id` | Associated schedule ID (if recurring) |

## API Reference

- Endpoint: `POST /tasks/v1/actions/list`
- [Documentation](https://developer.safetyculture.com/reference/)

## Performance

- Fetches pages concurrently using async I/O (up to 10 simultaneous requests)
- Pages of 1,000 actions each for minimal round trips
- Connection pooling with up to 100 TCP connections

## Notes

- No input file required - exports all actions in the account
- Priority IDs are automatically mapped to human-readable labels
- Assignees include both individual users and groups
- The script is read-only and does not modify any data
