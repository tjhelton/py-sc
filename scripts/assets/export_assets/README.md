# Fetch Assets - High-Performance Asset Retrieval

A high-performance script that fetches ALL assets from SafetyCulture as fast as possible and exports them to CSV.

## Features

- **Maximum Speed Optimization**:
  - Async I/O for non-blocking network operations
  - Connection pooling and TCP connection reuse
  - Incremental CSV writing (no memory accumulation)
  - Minimal processing overhead

- **Real-Time Progress Tracking**:
  - Live page-by-page progress updates
  - Fetch rate (pages/second)
  - Estimated time to completion (ETA)
  - Throughput metrics (assets/second)

- **Reliable Data Handling**:
  - Automatic pagination through all pages
  - Timestamped output files (no overwrites)
  - Comprehensive error handling
  - Performance statistics summary

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r ../../requirements.txt
   ```

2. **Set API token**:
   Open `main.py` and replace `TOKEN = ''` with your SafetyCulture API token:
   ```python
   TOKEN = 'scapi_your_token_here'
   ```

3. **Run script**:
   ```bash
   python main.py
   ```

4. **Output**:
   - CSV file named `assets_YYYYMMDD_HHMMSS.csv` with all asset data
   - Real-time console progress and final statistics

## Prerequisites

- Python 3.8+
- Valid SafetyCulture API token with assets read permissions
- Required packages (from `requirements.txt`):
  - `aiohttp` - Async HTTP client
  - `pandas` - Data manipulation (dependency only)
  - `requests` - HTTP library (not used but in requirements)

## Output Format

The script generates a CSV file with all asset fields returned by the API. Common fields include:

- `id` - Asset UUID
- `name` - Asset name
- `type` - Asset type
- `site_id` - Associated site ID
- `created_at` - Creation timestamp
- `modified_at` - Last modification timestamp
- `archived` - Archive status
- Additional custom fields specific to your account

**Output filename**: `assets_YYYYMMDD_HHMMSS.csv` (e.g., `assets_20250320_143045.csv`)

## API Reference

- **Endpoint**: `GET /feed/assets`
- **Documentation**: [SafetyCulture API - Data Feed for Assets](https://developer.safetyculture.com/reference/thepubservice_feedassets)

## Performance Details

### Speed Optimizations

1. **Async I/O**: Non-blocking HTTP requests using `aiohttp`
2. **Connection Pooling**: Reuse TCP connections (up to 100 connections, 30 per host)
3. **Incremental Writing**: Stream data directly to CSV as fetched (no memory accumulation)
4. **DNS Caching**: Cache DNS lookups for 300 seconds
5. **Zero Processing**: Write raw API response data immediately

### Limitations

- **Sequential Pagination Required**: The `/feed/assets` endpoint returns a `next_page` URL that must be used sequentially. Each page depends on the previous response, so pagination cannot be parallelized.
- **API Rate Limits**: The script respects SafetyCulture API rate limits automatically

### Typical Performance

Expected performance varies based on:
- Total number of assets in your account
- Network latency and bandwidth
- SafetyCulture API response times
- Number of fields per asset

**Example**: Fetching 10,000 assets typically takes 2-5 minutes depending on conditions.

## Real-Time Progress Example

```
🚀 Starting high-performance asset fetch...
💾 Streaming results to: assets_20250320_143045.csv
================================================================================
📄 Page 1: 25 assets | Total: 25 | Remaining: 9,975 | Rate: 2.1 pages/sec | Page time: 0.48s | ETA: 78m 45s
📄 Page 2: 25 assets | Total: 50 | Remaining: 9,950 | Rate: 2.3 pages/sec | Page time: 0.43s | ETA: 72m 10s
📄 Page 3: 25 assets | Total: 75 | Remaining: 9,925 | Rate: 2.5 pages/sec | Page time: 0.40s | ETA: 66m 20s
...
================================================================================
🎉 FETCH COMPLETE!
================================================================================
📊 Total Assets: 10,000
📄 Total Pages: 400
⏱️  Total Time: 180.45s (3.01 minutes)
⚡ Average Page Time: 0.451s
🚀 Throughput: 2.22 pages/sec | 55.4 assets/sec
💾 Output saved to: assets_20250320_143045.csv
================================================================================
```

## Troubleshooting

### Error: "TOKEN not set in script"

**Solution**: Open `main.py` and set your API token:
```python
TOKEN = 'scapi_your_token_here'
```

### Error: "ClientError" or connection issues

**Possible causes**:
- Invalid API token
- Network connectivity issues
- SafetyCulture API rate limiting

**Solutions**:
1. Verify your API token is valid
2. Check your internet connection
3. Wait a few minutes if rate limited and try again

### No data in CSV file

**Possible causes**:
- No assets in your SafetyCulture account
- Insufficient API permissions

**Solutions**:
1. Verify assets exist in your SafetyCulture account
2. Check API token has `assets:read` permission

## Advanced Usage

### Custom Output Location

Edit the `get_next_output_file()` function in `main.py` to change the output directory or filename pattern.

### Modify Connection Settings

Adjust connection pool settings in the `__aenter__` method:
```python
connector = aiohttp.TCPConnector(
    limit=100,              # Total connection limit
    limit_per_host=30,      # Connections per host
    ttl_dns_cache=300,      # DNS cache TTL in seconds
)
```

## Notes

- **Memory Efficient**: Data is streamed directly to CSV, so memory usage stays low regardless of dataset size
- **Interruptible**: Press Ctrl+C to stop the script (partial data will be saved)
- **Safe**: The script only reads data (no modifications to your SafetyCulture account)
- **Timestamped Files**: Each run creates a new timestamped file, preventing overwrites

## Security

- Never commit your API token to version control
- The `.gitignore` file excludes `*.csv` files by default
- Always clear the TOKEN variable before committing code changes

## Related Scripts

- `export_asset_types/` - Export asset type definitions
- `delete_assets/` - Archive assets in bulk
- `get_sites_without_activity/` - Analyze site activity (uses similar async patterns)
