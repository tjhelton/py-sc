# Nuke Account

Destroys all SafetyCulture data in an organization: inspections, actions, issues, sites, assets, credentials, contractor companies, OSHA cases, and templates. Uses fully async calls with paged deletes so progress is saved as it runs.

## Quick Start

1. **Install dependencies**: `pip install -r ../../requirements.txt`
2. **Set API token**: `export SC_API_TOKEN="your-api-token"` (or pass `--token`)
3. **Run**: `python main.py --yes` (requires Python 3.9+)
4. **Optional**: Skip resources with `--skip actions,sites` or tune concurrency with `--delete-concurrency 12`

## What It Deletes

- Inspections (`/feed/inspections` + `DELETE /inspections/v1/inspections/{id}`)
- Actions (`POST /tasks/v1/actions/list` with offset, `POST /tasks/v1/actions/delete`)
- Issues / investigations (`GET /incidents/v1/investigations`, `DELETE /incidents/v1/investigations/{id}`)
- Assets (`POST /assets/v1/assets/list`, `DELETE /assets/v1/assets/{id}`)
- Credentials (`POST /credentials/v1/credentials`, `DELETE /credentials/v1/credential`)
- Contractor companies (`POST /companies/v1beta/companies`, `DELETE /companies/v1beta/company`)
- OSHA cases (`GET /incidents/v1/osha/cases` with offset first, then page tokens)
- Templates (`/feed/templates`, `DELETE /templates/v1/templates/{id}`)
- Sites (`POST /directory/v1/folders/search`, batched `DELETE /directory/v1/folders`)

## Flags

- `--token`: SafetyCulture API token (or env `SC_API_TOKEN`)
- `--base-url`: API base (default `https://api.safetyculture.io`)
- `--skip`: Comma-separated resources to skip (e.g., `--skip inspections,templates`)
- `--delete-concurrency`: Parallel delete requests (default 16)
- `--list-concurrency`: Parallel list requests for offset endpoints (default 8)
- `--yes`: Bypass confirmation prompt

## Behavior Notes

- Uses offset-based paging for actions and OSHA cases so pages are fetched in parallel.
- Data feed endpoints follow `metadata.next_page` paths and start deletes as soon as each page arrives.
- Deletions run with a semaphore to stay under rate limits and flush in batches to keep memory low.
- The script skips the org root folder when deleting sites (cannot be removed by API).

## Safety

This script is destructive and irreversible. Run only against accounts you intend to wipe. Keep tokens out of version control.
