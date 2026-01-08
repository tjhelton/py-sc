# Export Inspection PDFs (Bulk)

Exports SafetyCulture inspection PDFs in bulk using async polling pattern. Processes inspections with intelligent retry logic, real-time progress tracking, and live CSV output logging.

## Quick Start

1. **Install dependencies**: `pip install -r ../../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Prepare input**: Create `input.csv` with inspection details
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- Input CSV with inspection audit IDs

## Input Format

Create `input.csv` with inspection details:
```csv
audit_id,audit_title,template_name
audit_abc123def456,Fire Safety Inspection,Fire Safety Template
audit_def456ghi789,Electrical Audit,Electrical Checklist
audit_ghi789jkl012,Building Inspection,Building Safety Template
```

**Column Descriptions:**
- `audit_id` (required): The inspection audit ID
- `audit_title` (optional): Human-readable inspection name (used in PDF filename)
- `template_name` (optional): Template name (used in PDF filename)

If `audit_title` or `template_name` are missing, they will default to "Unknown".

## Output

### PDFs Directory
PDFs are saved in a timestamped folder: `exports_YYYYMMDD_HHMMSS/`

Example: `exports_20251229_143022/`

**PDF Filenames:**
```
{audit_title} | {template_name} | {audit_id}.pdf
```

Example:
```
Fire Safety Inspection | Fire Safety Template | audit_abc123def456.pdf
```

Invalid filesystem characters (`/\:*?"<>|`) are automatically replaced with underscores.

### Results Log
Generates `exports_log.csv` with real-time export results:
- `audit_id`: The inspection audit ID
- `audit_title`: Inspection title from input
- `template_name`: Template name from input
- `status`: SUCCESS or ERROR
- `error_message`: Error details if export failed (empty on success)
- `file_path`: Full path to exported PDF (empty on error)
- `export_time_seconds`: Time taken to export this inspection
- `timestamp`: When the export completed/failed

## API Reference

- **Endpoint**: `POST /inspection/v1/export`
- **Request Body**:
  ```json
  {
    "export_data": [{
      "inspection_id": "audit_id_here",
      "lang": "en"
    }],
    "type": "DOCUMENT_TYPE_PDF",
    "timezone": "UTC",
    "regenerate": false
  }
  ```
- **Async Polling Pattern**:
  1. Initial POST returns immediately with status: `STATUS_IN_PROGRESS`, `STATUS_FAILED`, or `STATUS_DONE`
  2. Poll same endpoint until `status` = `STATUS_DONE`
  3. Download PDF from S3 URL in response
- **Polling Strategy**: Exponential backoff (2s, 4s, 8s, 15s, 30s) with 10-minute timeout

## Features

- **Async polling pattern**: Handles long-running PDF generation
- **Automatic retry logic**: Up to 3 attempts with exponential backoff for failed requests
- **Rate limiting**: Processes up to 500 requests per minute safely
- **Progress bar**: Real-time console progress with tqdm
- **Live logging**: Each export/error logged to console as it happens
- **Live CSV output**: Results written immediately (not batched at end)
- **Error resilience**: Continues processing remaining inspections on errors
- **Intelligent polling**: Exponential backoff reduces API load during generation
- **Timestamped output**: Unique output directories prevent overwriting
- **Filename sanitization**: Automatic cleanup of invalid filesystem characters

## Important Notes

- **Export generation time**: Large inspections with many media files may take several minutes to generate
- **Timeout**: Exports that take longer than 10 minutes will be marked as ERROR
- **S3 URLs**: Downloads use pre-signed S3 URLs (no authentication needed for download step)
- **Output safety**: Each run creates a new timestamped directory
- **CSV encoding**: UTF-8 encoding for international characters
- **Concurrent processing**: Processes up to 12 inspections simultaneously

## Example Usage

```bash
# Navigate to script directory
cd scripts/inspections/export_inspection_pdfs/

# Install dependencies (if not already installed)
pip install -r ../../../requirements.txt

# Edit main.py to add your API token
# Create input.csv with inspection details

# Run the script
python main.py
```

## Console Output Example

```
================================================================================
🚀 SafetyCulture Inspection PDF Exporter
================================================================================
📋 Loaded 25 inspections from input.csv

================================================================================

🚀 Starting bulk export for 25 inspections...
⚡ Rate limit: 500 requests per minute
📁 Output directory: exports_20251229_143022/
📊 Live results: exports_log.csv

Exporting PDFs: 100%|██████████| 25/25 [02:45<00:00,  6.61 seconds/inspection]
✅ Exported: Fire Safety Inspection | Fire Safety Template | audit_abc123.pdf
✅ Exported: Electrical Audit | Electrical Checklist | audit_def456.pdf
⚠️  Polling: Large Building Inspection (45s elapsed)...
✅ Exported: Large Building Inspection | Building Template | audit_ghi789.pdf
❌ Error: audit_invalid123 - 404: Inspection not found
...

================================================================================
📊 EXPORT SUMMARY
================================================================================
✅ Successful: 23
❌ Errors: 2
📝 Total: 25
📈 Success Rate: 92.0%
⏱️  Total Time: 2m 45s

💾 PDFs saved to: /path/to/scripts/inspections/export_inspection_pdfs/exports_20251229_143022/
💾 Results log: /path/to/scripts/inspections/export_inspection_pdfs/exports_log.csv
================================================================================
```

## Troubleshooting

**Error: TOKEN not set**
- Edit `main.py` and replace `TOKEN = ""` with your API token

**Error: input.csv not found**
- Create `input.csv` in the same directory as `main.py`
- Ensure it has the required column headers

**Error: input.csv missing required columns**
- Check that CSV has `audit_id`, `audit_title`, and `template_name` columns
- Column names must match exactly (case-sensitive)

**Export timeout after 10 minutes**
- Some very large inspections with extensive media may exceed the timeout
- These inspections may need to be exported individually or through the web interface
- Consider regenerating the export through SafetyCulture platform first

**404 errors on valid audit IDs**
- Verify the audit ID exists in your organization
- Check that your API token has appropriate permissions
- Ensure the inspection hasn't been deleted

**S3 download failures**
- S3 URLs are time-limited; script downloads immediately after generation
- Network issues during download will be retried once
- Check firewall settings if downloads consistently fail

**Rate limit errors (429)**
- Script automatically handles rate limiting with retries
- If you see persistent 429 errors, the API limits may have changed
- Reduce `MAX_REQUESTS_PER_MINUTE` in the script configuration

**Polling shows STATUS_IN_PROGRESS for extended periods**
- Normal for large inspections with many media attachments
- Script will continue polling up to 10 minutes
- Progress messages show elapsed time during polling

## Performance Tips

- **Batch size**: Script handles hundreds of inspections efficiently
- **Network**: Stable internet connection recommended for S3 downloads
- **Disk space**: Ensure sufficient space for PDFs (can be several MB each)
- **Concurrent limit**: Default 12 concurrent exports balances speed and API limits

## API Behavior Notes

- **Polling pattern**: Required because PDF generation is asynchronous
- **Status transitions**: IN_PROGRESS → DONE (or FAILED)
- **S3 URLs**: Temporary pre-signed URLs valid for limited time
- **Regeneration**: `regenerate: false` uses cached PDFs when available
- **Language**: Set to "en" for English; change `lang` parameter for other languages
