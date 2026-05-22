# Generate Random Inspections

Generates synthetic inspections in bulk against your SafetyCulture org. For each iteration, the script picks a random template, fetches its definition via the integration API, fills each answerable item with a random value, creates the inspection, then immediately marks it complete.

Useful for seeding demo orgs, load-testing dashboards/exports, or stress-testing downstream integrations.

## Quick Start

1. **Install dependencies**: `pip install -r ../../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Run script**: `python main.py`
4. **Enter count**: When prompted, type how many inspections to generate

No `input.csv` is required — templates are pulled directly from your org.

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token with permission to read templates and create/complete inspections
- At least one active (non-archived) template in the org

## Input Format

None. The script:
1. Prompts for a count.
2. Pulls all active templates from `/feed/templates`.
3. Randomly selects from that pool for each generated inspection.

## Output

Generates `output.csv` (or `output_1.csv`, etc.) with one row per attempted generation:

| Column | Description |
| --- | --- |
| `run_index` | Sequence number of the generation attempt |
| `template_id` | ID of the randomly chosen template |
| `template_name` | Template display name |
| `inspection_id` | ID of the created inspection (blank on create failure) |
| `items_filled` | Number of items populated with random data |
| `create_status` | `SUCCESS` or `ERROR` |
| `complete_status` | `SUCCESS`, `ERROR`, or blank if create failed |
| `error_message` | Failure detail (blank on full success) |
| `timestamp` | Time the attempt was logged |

## API Reference

- **List templates**: `GET /feed/templates` (paginated via `metadata.next_page`)
- **List sites**: `GET /feed/sites`
- **List assets**: `GET /feed/assets`
- **List companies**: `GET /companies/v1/feed/companies`
- **Get global response set**: `GET /response_sets/{id}` (only when a question references a `responseset_*` ID not inlined in the template)
- **Get template definition**: `GET /templates/integration/v1/templates/{template_id}/definition`
- **Create inspection**: `POST /inspections/integration/v1/inspections`
- **Complete inspection**: `POST /inspections/integration/v1/inspections/{inspection_id}/complete`

## Randomization Rules

The script populates items of these types with random values:

| Template item type | Random value strategy |
| --- | --- |
| `ITEM_TYPE_TEXT` | 2–5 lorem-ipsum words |
| `ITEM_TYPE_PARAGRAPH` | 2–4 random lorem sentences |
| `ITEM_TYPE_NUMBER` | Float in `[0, 1000]`, 2 decimal places |
| `ITEM_TYPE_SLIDER` | Float in `[0, 100]`, 2 decimal places |
| `ITEM_TYPE_TEMPERATURE` | Float in `[-10, 40]` with `recorded_at` |
| `ITEM_TYPE_DATETIME` | Random timestamp within the last 7 days |
| `ITEM_TYPE_CHECKBOX` | Random `true`/`false` |
| `ITEM_TYPE_LOCATION` | Random `label` (no geocode lookup) |
| `ITEM_TYPE_QUESTION` | Random response from inline template response sets, falling back to fetching the global response set when the ID is `responseset_*` |
| `ITEM_TYPE_SITE` | Random `site_uuid` from `/feed/sites` (UUIDv4 required by the integration API) |
| `ITEM_TYPE_ASSET` | Random `id` from `/feed/assets` |
| `ITEM_TYPE_COMPANY` | Random `company_id` from `/companies/v1/feed/companies` |

Items left empty (the API allows empty values for non-mandatory items):
- Structural items (pages, sections, repeated sections, logic, table pages)
- Media, drawing, signature (no public upload API on integration v1)
- Tables (require explicit line creation via `AddTableLine`)
- Question items whose response set ID can't be resolved (legacy/private global sets)
- Site/asset/company items when the org has none of those resources

If an inspection has *mandatory* media/drawing/signature/table items it will create but the complete call will return a validation error and the row's `complete_status` will be `ERROR`.

## Calculation/Autofill Number Items

The integration template definition reports calculation cells as plain `ITEM_TYPE_NUMBER` but the create API rejects values for them with code `InvalidArgument` ("Calculation questions cannot be answered directly"). The script handles this by parsing the offending `item_id` out of the error response, dropping that item, and retrying the create — up to 15 retries per inspection. The dropped count is reflected in the CSV's `items_filled` column.

## Transient Error Retries

Every HTTP call (sync template/site/asset/company fetches and async create/complete/definition calls) goes through a retry wrapper that handles:

- **Retryable HTTP statuses**: `408`, `425`, `429`, `500`, `502`, `503`, `504`
- **Network errors**: `aiohttp.ClientError`, `asyncio.TimeoutError`, `requests.RequestException`

Up to **5 retries** with exponential backoff (1s → 2s → 4s → 8s → 16s, capped at 30s) and 0–25% jitter. Each retry logs a one-line message:

```
  ⟳ retry 2/5 POST /inspections/integration/v1/inspections: HTTP 503
```

If all retries are exhausted the row is recorded with the final error in `error_message`; one bad inspection never aborts the run. The InvalidArgument item-drop loop sits *outside* this wrapper, so a 500 during an `invalid item` retry still gets its own 5 retry attempts at the HTTP level.

## Features

- **Interactive count**: Prompts for the number of inspections to generate
- **Auto template discovery**: Pulls all active templates from `/feed/templates`
- **Org-wide reference preload**: Sites, assets, and companies are loaded once at startup and reused for every inspection
- **Template definition cache**: Each template is fetched at most once, even when picked multiple times
- **Global response set cache**: Each external response set is fetched at most once
- **Self-healing creates**: Items the API rejects (e.g., calculation questions) are removed and the create retries automatically
- **Async + rate limited**: Defaults to ~300 req/min via semaphore (≈100 inspections in ~35 s)
- **Live CSV output**: Each result is flushed immediately
- **Progress bar**: tqdm progress with per-row status messages

## Example Run

```bash
cd scripts/inspections/generate_random_inspections/
# Edit main.py to set your token
python main.py
```

```
================================================================================
🎲 SafetyCulture Random Inspection Generator
================================================================================
How many inspections to generate? 25
📋 Fetching templates from datafeed...
  Fetched 87 templates so far...
✅ Total templates: 87 | Active: 81

================================================================================
🚀 Generating 25 random inspections...
⚡ Concurrency: 7 (target ~300 req/min)
📊 Live results writing to: output.csv

Generating inspections: 100%|██████████| 25/25 [00:11<00:00,  2.21 inspection/s]
✅ #1 Daily Safety Check → audit_abc123...
✅ #2 Equipment Inspection → audit_def456...
...

================================================================================
📊 GENERATION SUMMARY
================================================================================
📝 Total requested: 25
✅ Created:         25
✅ Completed:       25
❌ Errors:          0
📈 Success rate:    100.0%

💾 Full results saved to: /.../output.csv
================================================================================
```

## Notes

- Generated inspections are real records in your org. Don't run this against production.
- Templates with only media/signature mandatory items will create but can't complete — the row will show `create_status=SUCCESS` and `complete_status=ERROR` with the validation reason.
- If your org has no sites/assets/companies, items of those types are left empty; that's only a problem if the template marks them as mandatory.
- If you hit rate limits, lower `max_requests_per_minute` in the `InspectionGenerator` constructor call inside `main`.
