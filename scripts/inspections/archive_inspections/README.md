# Archive Inspections (Bulk)

Archives SafetyCulture inspections in bulk using async processing. Designed for high-volume operations processing up to hundreds of thousands of records with intelligent rate limiting, retry logic, and real-time progress tracking.

## Quick Start

1. **Install dependencies**: `pip install -r ../../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Prepare input**: Create `input.csv` with audit IDs
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- Input CSV with inspection audit IDs to archive

## Input Format

Create `input.csv` with a single column containing inspection audit IDs:

```csv
audit_id
audit_abc123def456
audit_def456ghi789
audit_ghi789jkl012
```

**Column Description:**
- `audit_id` (required): The inspection audit ID to archive

## Output

Generates `archive_results.csv` with real-time archiving results:
- `audit_id`: The inspection audit ID
- `status`: SUCCESS or ERROR
- `error_message`: Error details if archiving failed (empty on success)
- `timestamp`: When the archive operation completed/failed

## API Reference

- **Endpoint**: `POST /inspections/v1/inspections/{inspection_id}/archive`
- **Documentation**: [SafetyCulture API - Archive Inspection](https://developer.safetyculture.com/reference/inspectionservice_archiveinspection)
- **Request Body**: Empty JSON object `{}`
- **Response**: `{"inspection_id": "audit_id_here"}` on success

## Features

- **High-volume processing**: Optimized for 6+ figure record batches (100,000+ inspections)
- **Async processing**: Up to 50 concurrent requests for maximum speed
- **Rate limiting**: Automatically throttles to 500 requests/minute to stay within API limits
- **Automatic retry logic**: Up to 3 attempts with exponential backoff for failed requests
- **Progress tracking**: Real-time console progress bar with tqdm
- **Live logging**: Each archive/error logged to console as it happens
- **Live CSV output**: Results written immediately (not batched at end)
- **Error resilience**: Continues processing remaining inspections on errors

## Performance Configuration

The script includes optimized settings for bulk operations:

- **Rate limit**: 500 requests/minute (conservative, API allows ~1000/min)
- **Concurrent requests**: 50 simultaneous operations
- **Connection pooling**: Reuses HTTP connections for efficiency
- **Retry strategy**: Exponential backoff (2s, 4s, 8s) for transient errors

### Estimated Processing Times

Based on 500 requests/minute with 50 concurrent operations:

| Inspections | Estimated Time |
|-------------|----------------|
| 1,000       | ~2-3 minutes   |
| 10,000      | ~20-30 minutes |
| 100,000     | ~3-4 hours     |
| 500,000     | ~16-20 hours   |

Actual times may vary based on network conditions and API response times.

## Important Notes

- **Permanent action**: Archiving inspections can typically be reversed via API, but use caution
- **Permissions**: Ensure your API token has permission to archive inspections
- **Rate limits**: Script respects SafetyCulture API rate limits automatically
- **Large batches**: For 6-figure batches, consider running in stable environment (server, not laptop)
- **Resume capability**: Output CSV shows what's been processed; can filter and retry errors

## Example Usage

```bash
# Navigate to script directory
cd scripts/inspections/archive_inspections/

# Install dependencies (if not already installed)
pip install -r ../../../requirements.txt

# Edit main.py to add your API token
# Create input.csv with audit IDs

# Run the script
python main.py
```

## Console Output Example

```
================================================================================
🗄️  SafetyCulture Inspection Bulk Archiver
================================================================================
📋 Loaded 10000 inspection IDs from input.csv

================================================================================

🚀 Starting bulk archive for 10000 inspections...
⚡ Rate limit: 500 requests per minute
🔄 Concurrent requests: 50
📊 Live results: archive_results.csv

Archiving: 100%|██████████| 10000/10000 [22:15<00:00,  7.49 inspections/s]
✅ Archived: audit_abc123def456
✅ Archived: audit_def456ghi789
✅ Archived: audit_ghi789jkl012
❌ Error: audit_invalid123 - HTTP 404
...

================================================================================
📊 ARCHIVE SUMMARY
================================================================================
✅ Successful: 9987
❌ Errors: 13
📝 Total: 10000
📈 Success Rate: 99.9%
⏱️  Total Time: 22m 15s
⚡ Average: 0.13s per inspection

💾 Results log: /path/to/scripts/inspections/archive_inspections/archive_results.csv
================================================================================
```

## Troubleshooting

**Error: TOKEN not set**
- Edit `main.py` and replace `TOKEN = ""` with your API token

**Error: input.csv not found**
- Create `input.csv` in the same directory as `main.py`
- Ensure it has the required column header: `audit_id`

**Error: input.csv missing required column**
- Check that CSV has `audit_id` column header
- Column name must match exactly (case-sensitive)

**404 errors on valid audit IDs**
- Verify the audit ID exists in your organization
- Check that your API token has appropriate permissions
- Ensure the inspection hasn't been deleted

**Rate limit errors (429)**
- Script automatically handles rate limiting with retries
- If you see persistent 429 errors, reduce `MAX_REQUESTS_PER_MINUTE` in script
- Default 500/min is conservative; API typically allows up to 1000/min

**Connection timeout errors**
- Check your internet connection stability
- For very large batches (100k+), run on stable server connection
- Script will automatically retry transient network errors

**Slow processing**
- Verify network connection speed
- Check `SEMAPHORE_VALUE` (concurrent requests) - default is 50
- Can increase to 75-100 if network is stable, but monitor error rates

## Performance Tips for Large Batches

**For 100,000+ inspections:**
- Run on server or stable environment (not laptop that might sleep)
- Monitor the first 1,000 records to verify success rate
- Keep output CSV open in spreadsheet to monitor live progress
- Consider splitting into multiple batches if needed

**Network optimization:**
- Use wired connection for stability
- Avoid running during peak network hours
- Monitor error rate - consistent errors may indicate API issues

**Resuming after interruption:**
- Check `archive_results.csv` for what's been processed
- Filter out successful IDs from `input.csv`
- Rerun script with remaining IDs

## Safety Recommendations

1. **Test with small batch first**: Archive 10-100 inspections to verify everything works
2. **Verify permissions**: Ensure API token has archive permissions
3. **Check organization**: Confirm you're archiving from correct organization
4. **Monitor initial results**: Watch first few minutes to catch configuration issues
5. **Keep results**: Save `archive_results.csv` as audit trail

## API Behavior Notes

- **Idempotent**: Archiving an already-archived inspection typically returns success
- **Synchronous**: Unlike exports, archive operation completes immediately (no polling)
- **Reversible**: Inspections can be un-archived via API if needed
- **Permissions**: Requires appropriate user permissions for each inspection
- **Audit trail**: SafetyCulture maintains audit logs of archive operations
