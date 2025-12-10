# Update User Sites

Updates user site access for SafetyCulture users in bulk via API. Uses user upsert job system to remove site access from users based on CSV input.

## Quick Start

1. **Install dependencies**: `pip install -r ../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Prepare input**: Create `input.csv` with user emails and site IDs
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- Input CSV with user emails and site IDs to remove access from

## Input Format

Create `input.csv` with user-site pairs:
```csv
email,site_id
john.doe@company.com,f47ac10b-58cc-4372-a567-0e02b2c3d479
jane.smith@company.com,f47ac10b-58cc-4372-a567-0e02b2c3d480
```

## Output

Displays job results in terminal with:
- Job ID and validation status
- Success/error messages for bulk operation
- No CSV output file generated

## API Reference

- Endpoint: `POST /users/v1/users/upsert/job`
- [Documentation](https://developer.safetyculture.com/reference/usersservice_createupsertjob)

## Notes

- Runs in validation mode by default (validate_only: True)
- Uses bulk job system for efficient processing
- Removes user access from specified sites only
