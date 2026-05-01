# Update Site Names

Bulk update site (folder) names in SafetyCulture using async concurrent API calls.

## Quick Start

1. **Install dependencies**: `pip install -r ../../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` with your SafetyCulture API token
3. **Prepare input**: Create `input.csv` with required format (see below)
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- Input CSV with site IDs and new names

## Input Format

Create `input.csv` with:

```csv
site_id,new_name
share_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX,New Site Name
share_YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY,Another Site Name
```

| Column | Required | Description |
|--------|----------|-------------|
| `site_id` | Yes | SafetyCulture site/folder ID (e.g. `share_abc123...`) |
| `new_name` | Yes | The new name to apply to the site (max 250 characters) |

## Output

Generates `output.csv` with one row per site:

| Column | Description |
|--------|-------------|
| `site_id` | The site ID from the input |
| `new_name` | The new name that was applied |
| `status` | `success` or `error` |
| `status_code` | HTTP response code from the API |
| `error` | Error message if the update failed, otherwise blank |

## API Reference

- Endpoint: `PATCH https://api.safetyculture.io/directory/v1/folder/{id}`
- [Documentation](https://developer.safetyculture.com/reference/directory_updatefolderproperties)

## Notes

- Runs up to 10 concurrent API requests by default; adjust `max_concurrent_requests` in `main()` if needed
- Rows missing `site_id` or `new_name` are skipped and logged to the console
- Failed updates are included in `output.csv` with the error details for easy review
