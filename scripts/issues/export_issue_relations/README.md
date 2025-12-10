# Export Issue Relations

Exports all SafetyCulture issue relationship data to CSV. Fetches relationships between issues and other entities (inspections, actions, assets, etc.) using the Data Feed API.

## Quick Start

1. **Install dependencies**: `pip install -r ../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Run script**: `python main.py`
4. **Check output**: Find timestamped CSV file (e.g., `issue_relations_20241201_143022.csv`)

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token with issues read permissions
- Network access to SafetyCulture API

## Input Format

No input file required - fetches all issue relationships from your SafetyCulture account automatically.

## Output

Generates timestamped CSV file with the following fields:

- `id` - Composite relationship ID (unique identifier for the relationship)
- `from_id` - Source entity UUID (typically the issue ID)
- `to_id` - Target entity UUID (inspection, action, or asset ID)
- `rel_type` - Relationship type (e.g., ISSUE-INSPECTION, ISSUE-ACTION, ISSUE-ASSET)
- `rel_created_at` - Relationship creation timestamp (ISO 8601 format)

**Output filename format**: `issue_relations_YYYYMMDD_HHMMSS.csv`

**Example**: `issue_relations_20241201_143022.csv`

## Features

- **Sequential Pagination**: Automatically follows API pagination through all pages
- **Streaming CSV**: Memory-efficient writing (handles large datasets without memory issues)
- **Retry Logic**: 3 attempts with exponential backoff for transient network errors
- **Rate Limit Handling**: Automatically waits when API rate limits are hit
- **Progress Tracking**: Real-time page counts, throughput rate, and estimated time remaining
- **Timestamped Output**: Prevents overwriting previous exports
- **Error Recovery**: Partial data saved on failure (all successfully fetched pages preserved)

## Performance

**Typical Performance:**
- Small datasets (<100 relations): 2-5 seconds
- Medium datasets (100-1000 relations): 10-30 seconds
- Large datasets (>1000 relations): 1-3 minutes
- Rate: ~2-3 pages per second (network dependent)

**Limitations:**
- Sequential pagination required (API design - cannot parallelize)
- Rate limits enforced by SafetyCulture API (automatically handled)
- No parallel processing possible for this endpoint

## Progress Example

```
================================================================================
SafetyCulture Issue Relationships Exporter
================================================================================
This script will fetch ALL issue relationships from your account
================================================================================

📁 Output file: issue_relations_20241201_143022.csv

🚀 Starting export...

📄 Page 1: 5 relations | Total: 5 | Remaining: 42 | Rate: 2.1 pages/sec | Page time: 0.48s | ETA: 0m 20s
📄 Page 2: 5 relations | Total: 10 | Remaining: 37 | Rate: 2.3 pages/sec | Page time: 0.43s | ETA: 0m 16s
📄 Page 3: 5 relations | Total: 15 | Remaining: 32 | Rate: 2.2 pages/sec | Page time: 0.45s | ETA: 0m 14s
...

================================================================================
🎉 EXPORT COMPLETE!
================================================================================
📊 Total Relationships: 47
📄 Total Pages: 10
⏱️  Total Time: 4.52s (0.08 minutes)
⚡ Average Rate: 2.21 pages/sec
💾 Output saved to: issue_relations_20241201_143022.csv
================================================================================
```

## API Reference

- **Endpoint**: `GET /feed/issue_relations`
- **Documentation**: [SafetyCulture API - Data Feed for Issue Relations](https://developer.safetyculture.com/reference/thepubservice_feedissuerelationships)

## Troubleshooting

### Error: "TOKEN not set in script"

**Solution**: Open `main.py` and set your API token:
```python
TOKEN = 'scapi_your_token_here'
```

### Rate limit errors

**Solution**: Script automatically handles rate limits with retry logic. The script will wait for the duration specified by the API's `Retry-After` header before continuing.

### Empty CSV or no data

**Possible causes**:
- No issue relationships exist in your account
- Insufficient API permissions
- Issues not linked to any inspections, actions, or assets

**Solutions**:
1. Verify issues exist in your SafetyCulture account
2. Check that issues are linked to other entities (inspections, actions, assets)
3. Verify API token has `issues:read` permission
4. Check that the token is valid and not expired

### Connection timeout errors

**Possible causes**:
- Network connectivity issues
- SafetyCulture API downtime
- Firewall blocking outbound connections

**Solutions**:
1. Check your internet connection
2. Verify SafetyCulture API status at [status.safetyculture.com](https://status.safetyculture.com)
3. Check firewall settings allow HTTPS to api.safetyculture.io
4. Script will auto-retry 3 times with exponential backoff

### Partial data / Export interrupted

**What happens**: If the export fails mid-way, all successfully fetched pages are saved to the CSV file.

**Recovery**:
1. Check the partial CSV file to see how many relationships were fetched
2. Note the last relationship ID in the file
3. Re-run the script to fetch a complete dataset
4. You can manually merge or compare files if needed

## Notes

- **Read-only operation**: Script only reads data (no modifications to your account)
- **Memory efficient**: Streams data directly to CSV (no memory buildup)
- **Partial recovery**: On failure, partial data is automatically saved
- **Safe to re-run**: Creates new timestamped file each run (no overwriting)
- **Token security**: Never commit TOKEN to version control
- **Dynamic fields**: CSV headers adapt to API response structure

## Security

- Never commit your API token to version control
- The `.gitignore` file excludes `*.csv` files by default
- Always clear the TOKEN variable before committing code changes
- Store tokens securely (environment variables or secret management tools)

## Use Cases

This script is useful for:
- **Audit trails**: Track which issues are linked to which inspections
- **Analytics**: Analyze relationships between issues and actions
- **Compliance**: Document issue resolution workflows
- **Reporting**: Generate reports showing issue-to-asset mappings
- **Data migration**: Export relationship data for system migrations
- **Integration**: Feed data into BI tools or data warehouses

## Related Scripts

- **[fetch_issues/](../fetch_issues/)** - Export detailed issue data with full attributes
- **[delete_actions/](../delete_actions/)** - Bulk delete actions linked to issues
- **[get_public_issue_links/](../get_public_issue_links/)** - Generate public sharing links for issues
- **[set_inspection_site/](../set_inspection_site/)** - Update site associations for inspections
