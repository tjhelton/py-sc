# Get Public Issue Links

Generates shareable public links for SafetyCulture issues in bulk via API. Reads issue IDs from CSV input and logs results to CSV output.

## Quick Start

1. **Install dependencies**: `pip install -r ../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Prepare input**: Create `input.csv` with `issue_id` column
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- Input CSV with issue IDs to share publicly

## Input Format

Create `input.csv` with issue IDs:
```csv
issue_id
audit_f47ac10b58cc4372a5670e02b2c3d479
audit_f47ac10b58cc4372a5670e02b2c3d480
```

## Output

Generates `output.csv` with:
- `issue_id`: Issue ID processed
- `url`: Public share link or "N/A" if failed
- `status`: Success confirmation or error message

## API Reference

- Endpoint: `POST /tasks/v1/tasks/{id}/shared-links`
- [Documentation](https://developer.safetyculture.com/reference/tasksservice_createsharedlink)

## Notes

- Public links allow unauthenticated access to issue reports
- Useful for external stakeholder sharing and compliance
- Test with small input file first
