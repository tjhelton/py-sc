# Delete Sites

Deletes SafetyCulture sites in bulk via API. Reads site IDs from CSV input and logs results to CSV output.

## Quick Start

1. **Install dependencies**: `pip install -r ../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Prepare input**: Create `input.csv` with `siteId` column
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- Input CSV with site IDs to delete

## Input Format

Create `input.csv` with site IDs:
```csv
siteId
f47ac10b-58cc-4372-a567-0e02b2c3d479
f47ac10b-58cc-4372-a567-0e02b2c3d480
```

## Output

Generates `output.csv` with:
- `count`: Processing order
- `SiteID`: Site ID processed
- `Status`: Success confirmation or error message

## API Reference

- Endpoint: `DELETE /directory/v1/folders`
- [Documentation](https://developer.safetyculture.com/reference/directoryservice_deletefolders)

## Notes

- Deletion is irreversible - use with caution
- Uses cascade_up=true which may delete empty parent folders
- Test with small input file first
