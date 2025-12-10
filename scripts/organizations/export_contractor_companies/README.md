# Export Contractor Companies

Exports all contractor company records from SafetyCulture using the **List Companies** endpoint and flattens every JSON field into CSV columns.

## Quick Start
1. Install dependencies: `pip install -r ../../requirements.txt`
2. Set API token: `export SC_API_TOKEN="scapi_your_token_here"` (or edit `TOKEN` in `main.py`)
3. Use CD to navigate to the script folder directory (`cd scripts/export_contractor_companies`)
3. Run the export: `python main.py`
4. Find the output: `contractor_companies_YYYYMMDD_HHMMSS.csv`

## How It Works
- Calls `POST /companies/v1beta/companies` with `page_size` + `page_token` pagination defined in `apidocs.openapi.json`
- Uses the `ContractorCompany` schema from the OpenAPI file to pre-seed column order
- Adds any additional keys seen at runtime so every field in the JSON response becomes a CSV column
- Flattens nested objects into dot-notation (e.g., `attributes.contact_details.address.street`); list primitives are `|`-joined; missing values become blanks

## Configuration
- `PAGE_SIZE`: Default `100`; increase/decrease if needed
- `OPENAPI_SPEC_PATH`: Points to the repo root `apidocs.openapi.json`
- `OUTPUT_FILENAME`: Timestamped automatically (no overwrite)

## Notes
- Read-only operation
- Warns if `total_count` from the API does not match the rows fetched
- CSV saved alongside the script unless you provide an absolute path in `OUTPUT_FILENAME`
