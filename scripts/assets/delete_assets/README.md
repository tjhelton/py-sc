# Delete Assets

Archives SafetyCulture assets in bulk via API. Processes assets individually with comprehensive logging and rate limiting.

## Quick Start

1. **Install dependencies**: `pip install -r ../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Prepare input**: Create `input.csv` with asset IDs
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- Input CSV with asset IDs to archive

## Input Format

Create `input.csv` with asset IDs (supports multiple column names):
```csv
asset_id
abc123-def456-ghi789
def456-ghi789-jkl012
ghi789-jkl012-mno345
```

Accepted column names: `asset_id`, `id`, or `uuid`

## Output

Generates `archive_results.csv` with:
- `asset_id`: Asset ID processed
- `timestamp`: Processing timestamp
- `success`: Boolean archive success
- `status_code`: HTTP response status
- `error_message`: Error details if failed
- `response_body`: API response content

## API Reference

- Endpoint: `PATCH /assets/v1/assets/{id}/archive`
- [Documentation](https://developer.safetyculture.com/reference/)

## Notes

- Assets are archived (not permanently deleted)
- Includes rate limiting with 0.1s delay between requests
- Provides detailed console logging and comprehensive error handling
