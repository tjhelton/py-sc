# Delete Actions

Deletes SafetyCulture actions in bulk via API. Processes actions in chunks of 300 and logs detailed results to CSV output.

## Quick Start

1. **Install dependencies**: `pip install -r ../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Prepare input**: Create `input.csv` with action IDs
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- Input CSV with action IDs to delete

## Input Format

Create `input.csv` with action IDs:
```csv
id
action_abc123def456
action_def456ghi789
action_ghi789jkl012
```

## Output

Generates timestamped `deletion_log_YYYYMMDD_HHMMSS.csv` with:
- `timestamp`: Processing timestamp
- `chunk_number`: Chunk sequence number
- `chunk_size`: Number of actions in chunk (max 300)
- `status_code`: HTTP response status
- `success`: Boolean deletion success
- `error_message`: Error details if failed
- `action_ids`: JSON array of processed action IDs

## API Reference

- Endpoint: `POST /tasks/v1/actions/delete`
- [Documentation](https://developer.safetyculture.com/reference/)

## Notes

- Processes actions in batches of 300 for optimal performance
- Deletion is irreversible - use with caution
- Provides real-time progress tracking and detailed logging
