# Create Groups

Creates SafetyCulture groups in bulk via API. Reads group names from CSV input and logs results to CSV output.

## Quick Start

1. **Install dependencies**: `pip install -r ../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Prepare input**: Create `input.csv` with `name` column
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- Input CSV with group names to create

## Input Format

Create `input.csv` with group names:
```csv
name
Engineering Team
Safety Inspectors
Management Group
```

## Output

Generates `output.csv` with:
- `name`: Group name processed
- `status`: Group ID on success or error message

## API Reference

- Endpoint: `POST /groups/v1/groups`
- [Documentation](https://developer.safetyculture.com/reference/groupsservice_creategroup)

## Notes

- Group names must be unique within organization
- Test with small input file first
- Keep API tokens secure
