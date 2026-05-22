# Move Sites

Bulk move SafetyCulture sites (folders) under new parents — or to the root — from a CSV. Runs requests concurrently for throughput.

## Quick Start

1. **Install dependencies**: `pip install -r ../../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` with your SafetyCulture API token
3. **Prepare input**: Create `input.csv` with required format (see below)
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token with **Platform management: Sites** permission
- Input CSV with site IDs and target parent IDs

## Input Format

Create `input.csv` with:

```csv
site_id,parent_id
share_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX,share_PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP
share_YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY,
```

| Column | Required | Description |
|--------|----------|-------------|
| `site_id` | Yes | SafetyCulture site/folder ID to move (e.g. `share_abc123...`) |
| `parent_id` | Yes (column) | New parent folder ID. Leave **blank** to move the site to the root. |

## Output

Generates `output.csv` with one row per site:

| Column | Description |
|--------|-------------|
| `site_id` | The site ID from the input |
| `parent_id` | The target parent ID from the input (blank = root) |
| `new_parent_id` | The new parent ID returned by the API (blank = root) |
| `status` | `moved` or `error` |
| `error` | Error message if the move failed, otherwise blank |
| `timestamp` | When the move was processed |

## API Reference

- Endpoint: `POST https://api.safetyculture.io/directory/v1/folders/move`
- [Documentation](https://developer.safetyculture.com/reference/directory_movefolders)

## Notes

- Up to 10 moves run concurrently; adjust `MAX_CONCURRENT` if needed
- Each request moves a single site; descendants follow automatically
- Folder hierarchies support up to **five levels** — moves that would exceed this will return an error
- The destination parent must be at the **same label level** as the current parent (unless moving to root)
- Moves that create a circular relationship (under a descendant) will return an error
- Failed moves are included in `output.csv` with error details for review
