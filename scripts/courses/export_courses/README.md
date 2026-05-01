# Export Courses

Exports all courses from SafetyCulture to a CSV file, including basic course metadata.

## Quick Start

1. **Install dependencies**: `pip install -r ../../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` with your SafetyCulture API token
3. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token

## Output

Generates `output.csv` with:

| Column | Description |
|--------|-------------|
| `id` | Unique course ID |
| `external_id` | External/integration ID |
| `title` | Course title |
| `description` | Course description |
| `status` | Draft, Scheduled, Published, or Archived |
| `locale` | Course language/locale |
| `is_mandatory` | Whether course is mandatory for users |
| `is_published` | Whether course is currently published |
| `due_by` | Due date type (notSpecified, static, relative) |
| `duration_seconds` | Duration in seconds |
| `duration_formatted` | Human-readable duration (e.g. `1h 30m 0s`) |
| `lesson_count` | Number of lessons in the course |
| `created_datetime` | ISO 8601 creation timestamp |
| `modified_datetime` | ISO 8601 last-modified timestamp |
| `thumbnail_url` | Thumbnail image URL |
| `logo_url` | Logo image URL |
| `branding_image_url` | Branding image URL |

## API Reference

- Endpoint: `GET /training/courses/v1`
- [Documentation](https://developer.safetyculture.com)

## Notes

- Fetches all courses across all publication statuses
- Paginated at 100 courses per request
