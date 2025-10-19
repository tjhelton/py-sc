# Fetch Group Assignees

Fetches all group assignees from your SafetyCulture organization and exports them to CSV with specific user and group information.

## Quick Start

1. **Install dependencies**: `pip install -r ../../requirements.txt`
2. **Set API token**: Replace `TOKEN = ''` with your SafetyCulture API token in `main.py`
3. **Run script**: `python main.py`

## Prerequisites

- Python 3.8+ and pip
- Valid SafetyCulture API token with "Platform management: Groups" permission
- aiohttp library (included in requirements.txt)

## Output

Generates `output.csv` with the following columns:

- `group_id` - Unique identifier for the group
- `user_id` - Numeric user identifier
- `user_uuid` - User's UUID
- `user_firstname` - User's first name
- `user_lastname` - User's last name
- `user_email` - User's email address

## How It Works

The script uses asynchronous HTTP requests to efficiently fetch data:

1. **Fetch Groups**: Retrieves all groups in your organization
2. **Fetch Assignees**: Concurrently fetches all users for each group (up to 25 concurrent requests)
3. **Export**: Combines data and exports only the requested fields to CSV

## API Reference

- **Groups Endpoint**: `GET https://api.safetyculture.io/groups`
  - [Documentation](https://developer.safetyculture.com/reference/groups)
- **Group Users Endpoint**: `GET https://api.safetyculture.io/groups/{group_id}/users`
  - [Documentation](https://developer.safetyculture.com/reference/thepubservice_listusersingroup)

## Performance

- Uses async/await with aiohttp for concurrent API calls
- Rate limited to 25 concurrent requests for API stability
- Typical runtime: <1 minute for most organizations (depends on number of groups and members)

## Notes

- The script handles pagination automatically for groups with many members
- Progress is displayed in real-time as groups are processed
- All API errors are logged to the console
- The output file will be overwritten on each run
