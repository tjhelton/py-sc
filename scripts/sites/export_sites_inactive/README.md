# Get Sites Without Activity

Identifies SafetyCulture sites with **zero** records tied to them across inspections, actions, and issues. For each site, the script makes the same three checks the companion Workato recipe function performs, then exports a CSV containing only sites whose combined record count is `0`.

## Quick Start

1. **Install dependencies**: `pip install -r ../../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **(Optional) Provide `input.csv`** in this directory with the specific sites to check
4. **Run script**: `python main.py`
5. **Check output**: Find the generated CSV in the next available `output/` directory

## Prerequisites

- Python 3.8+ with asyncio support
- Valid SafetyCulture API token with access to inspections, actions, issues, and folders

## Input Format

`input.csv` is optional.

- **No `input.csv`**: The script fetches every leaf site via `POST /directory/v1/folders/search` with `only_leaf_nodes: true` and `limit: 1500` (the max).
- **With `input.csv`**: Only the listed sites are checked. The CSV must contain a `site_id` column (an `id` column is also accepted). A `site_name` (or `name`) column is optional and will be passed through to the output.

```csv
site_id,site_name
abc123,Warehouse North
def456,Warehouse South
```

## Output

Creates indexed output directories:

- First run: `output/sites_without_activity.csv`
- Second run: `output_1/sites_without_activity.csv`
- (and so on)

The CSV contains only sites with `total_count == 0` and these columns:

| Column | Description |
| --- | --- |
| `site_id` | SafetyCulture folder/site UUID |
| `site_name` | Site name |
| `action_count` | Total actions filed against the site |
| `issue_count` | Total issues filed against the site |
| `inspection_count` | Total non-archived inspections (synced + pending-sync) at the site |
| `total_count` | Sum of the three counts above (always `0` in this output) |

## API Reference

The script mirrors the Workato recipe function in `workato_function_check_site_for_activity.recipe.json`.

Per site, it makes four parallel calls:

- `POST /inspections/v1/inspection:GetInspections` with `query.location_ids=[site_id]`, `is_archived=false`, `is_not_sync=false`
- `POST /inspections/v1/inspection:GetInspections` with `query.location_ids=[site_id]`, `is_archived=false`, `is_not_sync=true`
- `POST /tasks/v1/actions/list` with `task_filters.site_id` set to `FILTER_OPERATOR_IN` `[site_id]`
- `POST /tasks/v1/incidents/list` with `filters.site_id` set to `IN` `[site_id]`

Each call uses `page_size: 1` and `suppress_total: false` so the `total` field returns the exact record count without paginating.

Folder enumeration uses:

- `POST /directory/v1/folders/search` with `{"limit": 1500, "only_leaf_nodes": true}`, paginated by `next_page_token`

[Documentation](https://developer.safetyculture.com/reference/)

## Notes

- Throughput is capped by a token bucket at `MAX_REQUESTS_PER_MINUTE = 200` with `MAX_CONCURRENT = 20` in-flight requests. Tune both at the top of `main.py` if the org allows more.
- 429 responses honor the `Retry-After` header and retry with exponential backoff (up to 5 attempts).
- The two inspection calls (sync + non-sync) match the recipe exactly so totals stay aligned with what users see in-app.
- Leaf-node detection is delegated to the API via `only_leaf_nodes: true`. If you need to override (e.g. include branch folders or hand-pick sites), pass them via `input.csv`.
