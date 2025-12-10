# Set Inspection Site

Assigns sites to SafetyCulture inspections in bulk via API. Reads audit and site ID pairs from CSV input and logs results to CSV output.

## Quick Start

1. **Install dependencies**: `pip install -r ../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Prepare input**: Create `input.csv` with audit and site ID pairs
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- Input CSV with existing audit IDs and site IDs

## Input Format

Create `input.csv` with audit-site pairs:
```csv
audit_id,site_id
audit_f47ac10b58cc4372a5670e02b2c3d479,f47ac10b-58cc-4372-a567-0e02b2c3d480
audit_f47ac10b58cc4372a5670e02b2c3d481,f47ac10b-58cc-4372-a567-0e02b2c3d482
```

## Output

Generates `output.csv` with:
- `audit_id`: Inspection ID processed
- `site_id`: Site ID assigned
- `status`: Success confirmation or error message

## API Reference

- Endpoint: `PUT /inspections/v1/inspections/{id}/site`
- [Documentation](https://developer.safetyculture.com/reference/inspectionsservice_setinspectionsite)

## Notes

- Both audit IDs and site IDs must already exist
- Useful for bulk location assignment and compliance setup
- Test with small input file first
