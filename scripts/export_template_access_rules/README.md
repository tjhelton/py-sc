# Export Template Access Rules

High-performance async exporter for SafetyCulture template permission assignments. Uses parallel API calls with rate limiting to quickly fetch template access data and generate CSV output.

## Quick Start

1. **Install dependencies**: `pip install -r ../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Run script**: `python main.py`
4. **Check output**: Find `template_access_rules.csv` file

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- API access to template permissions

## Input Format

No input file required - fetches all template access rules from organization.

## Output

Generates `template_access_rules.csv` with:
- `template_id`: Template identifier
- `name`: Template name
- `permission`: Permission level
- `assignee_type`: User or group assignment
- `assignee_id`: Assignee identifier
- `assignee_name`: Assignee display name

## API Reference

- Endpoint: Template permissions API
- [Documentation](https://developer.safetyculture.com/reference/)

## Performance Features

- **Async I/O**: Uses aiohttp for non-blocking parallel requests
- **Rate limiting**: Automatically maintains 80% of API rate limit (640 req/60s)
- **Connection pooling**: Optimized TCP connection reuse
- **Progress tracking**: Real-time progress bars with rate statistics
- **Batch processing**: Fetches templates in parallel batches for maximum speed

## Notes

- Exports complete permission matrix for all templates
- Optimized for large datasets - processes hundreds of templates in seconds
- Automatically respects API rate limits with 429 retry handling
- Uses owner_name from feed/templates for accurate template ownership
- Useful for access auditing and compliance
- Keep API tokens secure
