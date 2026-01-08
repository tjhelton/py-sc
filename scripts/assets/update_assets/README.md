# Update Assets (Async)

Bulk-updates SafetyCulture assets from CSV using the bulk assets API. Maps CSV columns to asset fields automatically and sends updates in chunked async requests with retry logic.

## Quick Start

1. **Install dependencies**: `pip install -r ../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Prepare input**: Create `input.csv` with asset IDs and fields to update (see format below)
4. **Run script**: `python main.py`
5. **Check output**: Review `bulk_update_log_YYYYMMDD_HHMMSS.csv` for per-asset results

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token with assets write access
- Input CSV containing asset IDs and fields to change

## Input Format

The CSV must include an asset identifier column (any of: `internal id`, `asset id`, `id`). Optional columns are mapped automatically:

- Asset code: `unique id`, `code`, `asset code`, `unique code`
- Site ID: `site id`, `site`, `site_id`
- Custom fields: column header must match the field name or field ID in SafetyCulture

Example:
```csv
asset id,code,site id,Location,Cost
abc123-def456,ASSET-001,site-uuid-1,North Wing,USD 1250.50
ghi789-jkl012,ASSET-002,site-uuid-2,South Wing,875.25
```

Supported field handling:
- Timestamps are normalized to ISO-8601 when possible
- Money strings such as `USD 100.50` are parsed into currency/units/nanos
- Empty values are skipped; rows without an asset ID are ignored

## Behavior

- Fetches asset field definitions to map CSV headers to custom fields
- Builds bulk update payloads in chunks of 100 assets (configurable via `CHUNK_SIZE`)
- Uses async HTTP requests with retry-on-failure for transient status codes
- Update mask includes only the fields present in your CSV (code, site, custom fields)
- Skips ambiguous column matches to avoid incorrect updates

## Output

- Console progress with chunk counts, successes, and failures
- CSV log: `bulk_update_log_YYYYMMDD_HHMMSS.csv` with columns `asset_id`, `asset_code`, `status`, `message`, `timestamp`

## API Reference

- `POST /assets/v1/fields/list`
- `PUT /assets/v1/assets/bulk`
- [SafetyCulture API Docs](https://developer.safetyculture.com/reference/)
