# Schedules (Legacy)

Scripts for managing SafetyCulture schedule items via the legacy Schedules API (`/schedules/v1/`).

## Available Scripts

| Script | Description |
|--------|-------------|
| [export_schedules](export_schedules/) | Export all schedule items to a timestamped CSV, with optional status filtering |
| [update_schedules](update_schedules/) | Export schedules to CSV, edit fields in-place, then bulk-apply only the changed rows |

## Quick Start

1. **Install dependencies**: `pip install -r ../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in the relevant `main.py` with your SafetyCulture API token
3. **Navigate to the script**: `cd export_schedules/` or `cd update_schedules/`
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token

## API Reference

- Base endpoint: `/schedules/v1/schedule_items`
- [SafetyCulture Schedules API Documentation](https://developer.safetyculture.com/reference/schedulesservice_listscheduleitems)

## Notes

- These scripts target the legacy `/schedules/v1/` API
- All scripts handle pagination automatically
- See each script's own README for full usage details
