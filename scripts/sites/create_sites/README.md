# Create Sites

Creates SafetyCulture sites in bulk via API. Reads site details from CSV input and logs results to CSV output.

## Quick Start

1. **Install dependencies**: `pip install -r ../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Prepare input**: Create `input.csv` with site details
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- Input CSV with site names, levels, and optional parent IDs

## Input Format

Create `input.csv` with site details:
```csv
name,meta_label,parent
Site A,area,
Site B,location,site_123456
Site C,location,site_789012
```

## Output

Generates `output.csv` with:
- `count`: Processing order
- `site_name`: Site name
- `meta_label`: Site level
- `status`: Site ID on success or error message

## API Reference

- Endpoint: `POST /directory/v1/folder`
- [Documentation](https://developer.safetyculture.com/reference/directory_createfolder)

## Notes

- Parent IDs must reference existing sites
- Test with small input file first
- Keep API tokens secure
