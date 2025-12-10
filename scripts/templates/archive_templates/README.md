# Archive Templates

Archives SafetyCulture templates in bulk via API. Reads template IDs from CSV input and logs results to CSV output.

## Quick Start

1. **Install dependencies**: `pip install -r ../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Prepare input**: Create `input.csv` with `template_id` column
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- Input CSV with template IDs to archive

## Input Format

Create `input.csv` with template IDs:
```csv
template_id
template_123456
template_789012
```

## Output

Generates `log_output.csv` with:
- `template_id`: Processed template ID
- `result`: API response for each archive request

## API Reference

- Endpoint: `POST /templates/v1/templates/{id}/archive`
- [Documentation](https://developer.safetyculture.com/reference/templatesservice_archivetemplate)

## Notes

- Test with a small input file first
- Keep API tokens secure
- Archive operations are typically irreversible
