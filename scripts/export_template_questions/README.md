# Export Template Questions

Exports all questions from every SafetyCulture template in your organization to a single CSV file. Recursively parses template JSON structures to extract question metadata including parent relationships.

## Quick Start

1. **Install dependencies**: `pip install -r ../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` in `main.py` with your SafetyCulture API token
3. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token
- No input file required (fetches all templates automatically)

## Output

Generates `output.csv` with the following columns:

- `item_index`: Sequential index for questions within each template (starts at 0 per template)
- `item_id`: Unique ID of the question item
- `item_label`: Display label/text of the question
- `item_type`: Question type (e.g., textsingle, datetime, list, site, etc.)
- `parent_id`: ID of the immediate parent item (empty if no parent)
- `parent_label`: Label of the immediate parent item (empty if no parent)
- `template_id`: ID of the template containing this question
- `template_name`: Name of the template

## API Reference

- **Templates Datafeed**: `GET /feed/templates`
  - [Documentation](https://developer.safetyculture.com/reference/thepubservice_feedtemplates)
  - Used to fetch all templates with pagination

- **Get Template**: `GET /templates/v1/templates/{id}`
  - [Documentation](https://developer.safetyculture.com/reference/templatesservice_gettemplatebyid)
  - Used to fetch full JSON structure for each template

## Notes

- Script automatically handles pagination to fetch all templates
- Recursively parses nested template structures to find all questions
- Excludes `logicfield` items (conditional logic) from output
- Questions are indexed sequentially within each template (index resets per template)
- Parent ID and label refer to the immediate parent only (not full path)
- Processing time depends on number of templates in your organization
