# Export Asset Types

Exports all SafetyCulture asset types via API. Fetches asset type information and generates timestamped CSV output.

## Quick Start

1. **Install dependencies**: `pip install -r ../../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Run script**: `python main.py`
4. **Check output**: Find `asset_types.csv` in the script directory

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- API access to asset types

## Input Format

No input file required - fetches all asset types from organization.

## Output

Generates `asset_types.csv` with:
- `id`: Asset type unique identifier
- `name`: Asset type name
- `type`: Asset type classification

## API Reference

- Endpoint: `GET /assets/v1/types/list`
- [Documentation](https://developer.safetyculture.com/)

## Notes

- Handles pagination automatically (100 items per call)
- Output written to `asset_types.csv`
- Keep API tokens secure
