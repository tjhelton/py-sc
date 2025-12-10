# Get Sites Without Activity

Identifies SafetyCulture sites with no inspection activity via API. Compares all sites against inspection records using concurrent processing.

## Quick Start

1. **Install dependencies**: `pip install -r ../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Run script**: `python main.py`
4. **Check output**: Find timestamped CSV files in `output/` directory

## Prerequisites

- Python 3.8+ with asyncio support
- Valid SafetyCulture API token
- API access to inspections and sites feeds

## Input Format

No input file required - fetches all organizational data using API token configured in script.

## Output

Creates indexed output directories with simple CSV filenames:
- First run: `output/sites_without_activity.csv`, `output/all_inspections.csv`, `output/all_sites.csv`
- Second run: `output_1/sites_without_activity.csv`, `output_1/all_inspections.csv`, `output_1/all_sites.csv`
- Third run: `output_2/` (and so on...)

Each directory contains:
- `sites_without_activity.csv`: Sites with no inspection activity
- `all_inspections.csv`: Complete inspections data
- `all_sites.csv`: Complete sites data

## API Reference

- Endpoints:
  - `/feed/inspections` - Fetch all inspections (~25 records/page, default pagination)
  - `/directory/v1/folders` - Fetch all folders/sites (1500 records/page)
- [Documentation](https://developer.safetyculture.com/reference/)

## Notes

- Uses async/await for concurrent data fetching with optimized batching
- Fetches folders (sites) using high-capacity directory API (1500 records/page)
- Fetches inspections using feed API (25 records/page default)
- Concurrent fetching of inspections and sites for maximum speed
- Provides detailed console logging with progress tracking and performance metrics
- Folders API significantly reduces network requests vs legacy sites feed
