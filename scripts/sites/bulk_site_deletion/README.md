# Bulk Site Deletion

Bulk delete SafetyCulture sites (folders) from a CSV. Supports cascading up the hierarchy — if a deleted site was the last child in a branch, its parent is deleted too (all the way to the root).

## Quick Start

1. **Install dependencies**: `pip install -r ../../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` with your SafetyCulture API token
3. **Prepare input**: Create `input.csv` with required format (see below)
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- Input CSV with site IDs to delete

## Input Format

Create `input.csv` with:

```csv
site_id
share_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
share_YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY
```

| Column | Required | Description |
|--------|----------|-------------|
| `site_id` | Yes | SafetyCulture site/folder ID (e.g. `share_abc123...`) |

## Output

Generates `output.csv` with one row per site:

| Column | Description |
|--------|-------------|
| `site_id` | The site ID from the input |
| `status` | `deleted` or `error` |
| `error` | Error message if deletion failed, otherwise blank |
| `timestamp` | When the deletion was processed |

## Cascade Behaviour

The script always runs with `cascade_up=true`. This means:

- **Cascade down** (always on): deleting a parent removes all its children.
- **Cascade up** (enabled): if the deleted site was the last child in its branch, the parent is also deleted — and this propagates all the way up the tree.

## API Reference

- Endpoint: `DELETE https://api.safetyculture.io/directory/v1/folders`
- [Documentation](https://developer.safetyculture.com/reference/directory_deletefolders)

## Notes

- Sites are deleted in batches of 100 per API call; adjust `BATCH_SIZE` if needed
- Up to 5 batches run concurrently; adjust `MAX_CONCURRENT_BATCHES` if needed
- Failed deletions are included in `output.csv` with error details for review
- **This operation is irreversible** — verify your input CSV before running
