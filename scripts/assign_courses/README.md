# Assign Courses to Sites

Assigns SafetyCulture training courses to sites in bulk using the Training API.

## Quick Start

1. **Install dependencies**: `pip install -r ../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` with your SafetyCulture API token in `main.py`
3. **Prepare input**: Create `input.csv` with course-site assignments (one per row)
4. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token with training permissions
- Input CSV with course and site IDs

## Input Format

Create `input.csv` with:
```csv
course_id,site_id
course_abc123,site_xyz789
course_abc123,site_def456
course_ghi789,site_xyz789
```

**Note**: The script automatically batches all sites per course, so multiple rows with the same `course_id` will be grouped into a single API call for efficiency.

## Output

Generates `output.csv` with:
- `course_id`: The training course ID
- `site_ids`: Comma-separated list of sites assigned to the course
- `status`: Success message or error details

## API Reference

- Endpoint: `PUT /training/courses/v1/{course_id}/assignments`
- [Documentation](https://developer.safetyculture.com/reference/trainingcoursesservice_updatecourseassignments)

## Notes

- The script batches all sites for each course into a single API call for efficiency
- Each course processes independently - if one fails, others continue
- Real-time progress is logged to the terminal
- Existing course assignments are replaced with the new assignments from your CSV
