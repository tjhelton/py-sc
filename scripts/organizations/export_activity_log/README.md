# Export Activity Log Events

Exports all organisation activity log events from SafetyCulture using the **Feed Activity Log Events** endpoint, using parallel async requests for high-throughput extraction.

## Quick Start

1. **Install dependencies**: `pip install -r ../../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` with your SafetyCulture API token in `main.py`
3. **Configure filters** *(optional)*: Set `TRIGGERED_AFTER`, `MODIFIED_AFTER`, or `MODIFIED_BEFORE` in `main.py`
4. **Navigate to script folder**: `cd scripts/organizations/export_activity_log`
5. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- `aiohttp` installed (included in `requirements.txt`)

## Configuration

All configuration is at the top of `main.py`:

| Variable | Default | Description |
|---|---|---|
| `TOKEN` | `""` | Your SafetyCulture API token |
| `LIMIT` | `250` | Events per request (API max is 250) |
| `MAX_CONCURRENT_REQUESTS` | `20` | Number of parallel requests |
| `TRIGGERED_AFTER` | `""` | Export events triggered after this timestamp (ISO 8601) |
| `MODIFIED_AFTER` | `""` | Export events modified after this timestamp (ISO 8601) |
| `MODIFIED_BEFORE` | `""` | Export events modified before this timestamp (ISO 8601) |

**Date filter format**: `"2024-01-01T00:00:00.000Z"` — leave as `""` to export all events.

## Output

Generates `activity_log_YYYYMMDD_HHMMSS.csv` with one row per event:

| Column | Description |
|---|---|
| `id` | Unique event ID |
| `event_at` | Timestamp when the event was captured |
| `type` | Event type (e.g. login, inspection created) |
| `user_id` | ID of the user who initiated the event |
| `organisation_id` | Organisation where the event occurred |
| `client_class` | Client type that initiated the event (web, mobile, etc.) |
| `agent` | User agent string |
| `metadata` | Additional event metadata |
| `remote_ip` | IP address the event originated from |
| `initiator` | Initiator type (user, system, etc.) |

## How It Works

1. Makes an initial request to discover the total event count from `remaining_records`
2. Calculates all remaining page offsets (`LIMIT` = 250 per page)
3. Fires up to `MAX_CONCURRENT_REQUESTS` parallel requests using `aiohttp`
4. Streams results to CSV in batches — memory usage stays flat regardless of total size
5. Reports progress (pages, event count, rate, ETA) after each batch

## API Reference

- Endpoint: `GET https://api.safetyculture.io/feed/activity_log_events`
- [Documentation](https://developer.safetyculture.com/reference/thepubservice_feedactivitylogevents)

## Notes

- Read-only operation — no data is modified
- The API caps `limit` at 250 events per request
- For large organisations, exports can contain millions of rows; the script handles this with streaming CSV writes
- Adjust `MAX_CONCURRENT_REQUESTS` down if you encounter rate-limiting (429 responses)
