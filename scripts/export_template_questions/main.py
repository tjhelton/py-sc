import asyncio
import csv

import aiohttp
import requests

TOKEN = ""

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}


def fetch_all_templates():
    """Fetch all templates using the paginated datafeed API."""
    templates = []
    url = "https://api.safetyculture.io/feed/templates"

    print("Fetching templates from datafeed...")

    while url:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        data = response.json()

        templates.extend(data.get("data", []))
        print(f"  Fetched {len(templates)} templates so far...")

        url = data.get("metadata", {}).get("next_page")

    print(f"Total templates fetched: {len(templates)}")

    # Filter out archived templates
    active_templates = [t for t in templates if not t.get("archived", False)]
    archived_count = len(templates) - len(active_templates)
    print(f"Filtered out {archived_count} archived templates")
    print(f"Active templates to process: {len(active_templates)}\n")

    return active_templates


def fetch_template_json(template_id):
    """Fetch the full JSON structure for a specific template."""
    url = f"https://api.safetyculture.io/templates/v1/templates/{template_id}"
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


async def fetch_template_json_async(session, template_id, template_name, semaphore):
    """Async fetch the full JSON structure for a specific template with retry logic."""
    url = f"https://api.safetyculture.io/templates/v1/templates/{template_id}"
    max_retries = 3
    base_delay = 2  # seconds

    async with semaphore:
        for attempt in range(max_retries):
            try:
                print(
                    f"  Fetching: {template_name} (ID: {template_id}) - Attempt {attempt + 1}/{max_retries}"
                )

                async with session.get(url, timeout=30) as response:
                    status_code = response.status

                    if status_code == 200:
                        json_data = await response.json()
                        # Extract actual template name from response
                        actual_name = json_data.get("template", {}).get(
                            "name", template_name
                        )
                        print(f"  ✓ Success: {actual_name} (Status: {status_code})")
                        return {
                            "success": True,
                            "template_id": template_id,
                            "template_name": actual_name,
                            "data": json_data,
                        }
                    else:
                        # Try to get response body for error details
                        try:
                            error_body = await response.text()
                        except Exception:
                            error_body = "Could not read response body"

                        error_msg = f"HTTP {status_code}: {error_body[:200]}"
                        print(f"  ✗ Failed: {template_name} - {error_msg}")

                        # If not the last attempt, wait and retry
                        if attempt < max_retries - 1:
                            delay = base_delay * (2**attempt)  # Exponential backoff
                            print(f"    Retrying in {delay}s...")
                            await asyncio.sleep(delay)
                            continue

                        # Last attempt failed
                        return {
                            "success": False,
                            "template_id": template_id,
                            "template_name": template_name,
                            "error": error_msg,
                        }

            except asyncio.TimeoutError:
                error_msg = "Request timeout (30s)"
                print(f"  ✗ Timeout: {template_name}")

                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    print(f"    Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue

                return {
                    "success": False,
                    "template_id": template_id,
                    "template_name": template_name,
                    "error": error_msg,
                }

            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)}"
                print(f"  ✗ Error: {template_name} - {error_msg}")

                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    print(f"    Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue

                return {
                    "success": False,
                    "template_id": template_id,
                    "template_name": template_name,
                    "error": error_msg,
                }


def extract_questions(
    items,
    response_sets=None,
    page_id=None,
    page_label=None,
    section_id=None,
    section_label=None,
    template_id="",
    template_name="",
):
    """
    Recursively extract all questions from template items.

    Args:
        items: List of template items to process
        response_sets: Dictionary of response sets from template (keyed by response set ID)
        page_id: ID of the page (section item type)
        page_label: Label of the page
        section_id: ID of the section (category item type)
        section_label: Label of the section
        template_id: ID of the template
        template_name: Name of the template

    Returns:
        List of question dictionaries with required fields
    """
    if response_sets is None:
        response_sets = {}
    questions = []

    for item in items:
        item_id = item.get("id", "")
        item_label = item.get("label", "")
        children = item.get("children", [])

        item_type = None
        for key in item.keys():
            if key not in ["id", "label", "children"]:
                item_type = key
                break

        if item_type == "logicfield":
            questions.extend(
                extract_questions(
                    children,
                    response_sets,
                    page_id,
                    page_label,
                    section_id,
                    section_label,
                    template_id,
                    template_name,
                )
            )
            continue

        # Extract possible responses for list and question types
        possible_responses = ""
        if item_type and item_type in item:
            type_data = item[item_type]
            if isinstance(type_data, dict):
                # First try to get response_set_id and look it up
                response_set_id = type_data.get("response_set_id")
                if response_set_id and response_set_id in response_sets:
                    response_set = response_sets[response_set_id]
                    responses = response_set.get("responses", [])
                    response_labels = [
                        r.get("label", "") for r in responses if isinstance(r, dict)
                    ]
                    possible_responses = "; ".join(response_labels)
                # Fallback to inline responses if no response_set_id
                elif "responses" in type_data:
                    responses = type_data.get("responses", [])
                    response_labels = [
                        r.get("label", "") for r in responses if isinstance(r, dict)
                    ]
                    possible_responses = "; ".join(response_labels)

        if item_type:
            # Skip page and section items themselves (we only want actual questions)
            # but we'll still process their children for hierarchy tracking
            if item_type not in ["section", "category"]:
                # Map item types to more descriptive names
                display_type = item_type

                questions.append(
                    {
                        "item_id": item_id,
                        "item_label": item_label,
                        "possible_responses": possible_responses,
                        "item_type": display_type,
                        "page_id": page_id or "",
                        "page_label": page_label or "",
                        "section_id": section_id or "",
                        "section_label": section_label or "",
                        "template_id": template_id,
                        "template_name": template_name,
                    }
                )

        if children:
            # Determine page and section context for children based on current item type
            if item_type == "section":
                # Current item is a page, pass it as page context
                child_page_id = item_id
                child_page_label = item_label
                child_section_id = None
                child_section_label = None
            elif item_type == "category":
                # Current item is a section, pass it as section context
                child_page_id = page_id
                child_page_label = page_label
                child_section_id = item_id
                child_section_label = item_label
            else:
                # For all other types, pass through current context
                child_page_id = page_id
                child_page_label = page_label
                child_section_id = section_id
                child_section_label = section_label

            questions.extend(
                extract_questions(
                    children,
                    response_sets,
                    child_page_id,
                    child_page_label,
                    child_section_id,
                    child_section_label,
                    template_id,
                    template_name,
                )
            )

    return questions


async def main():
    """Main function to fetch templates and export questions to CSV."""
    print("Starting template questions export...\n")

    # Prompt user for template selection
    print("=" * 60)
    user_input = input(
        "Enter template IDs (comma-separated) or 'all' to fetch everything: "
    ).strip()
    print("=" * 60 + "\n")

    # Determine which templates to fetch
    if user_input.lower() == "all":
        print("Fetching all templates from feed...\n")
        templates = fetch_all_templates()
    else:
        # Parse comma-separated template IDs
        template_ids = [tid.strip() for tid in user_input.split(",") if tid.strip()]
        if not template_ids:
            print("Error: No template IDs provided. Exiting.")
            return

        print(f"Using {len(template_ids)} specified template ID(s)...\n")
        # Create template objects with just IDs (names will be populated during fetch)
        templates = [{"id": tid, "name": f"Template {tid}"} for tid in template_ids]

    # Fetch all templates asynchronously with rate limiting
    max_concurrent = 10  # Limit concurrent requests to avoid overwhelming API
    print(
        f"Fetching {len(templates)} template JSONs (max {max_concurrent} concurrent)...\n"
    )

    semaphore = asyncio.Semaphore(max_concurrent)

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        tasks = [
            fetch_template_json_async(
                session, template.get("id", ""), template.get("name", ""), semaphore
            )
            for template in templates
        ]
        results = await asyncio.gather(*tasks)

    print("\n" + "=" * 60)
    print("FETCHING COMPLETE - Processing results...")
    print("=" * 60 + "\n")

    # Process results and extract questions
    all_questions = []
    failed_templates = []
    successful_count = 0

    for idx, result in enumerate(results, 1):
        template_id = result["template_id"]
        template_name = result["template_name"]

        if not result["success"]:
            error_msg = result["error"]
            print(f"[{idx}/{len(results)}] FAILED: {template_name} - {error_msg}")
            failed_templates.append(
                {
                    "template_id": template_id,
                    "template_name": template_name,
                    "error": error_msg,
                }
            )
            continue

        print(f"[{idx}/{len(results)}] Processing: {template_name}")

        try:
            template_data = result["data"].get("template", {})
            items = template_data.get("items", [])

            # Extract response_sets as a dictionary keyed by response set ID
            response_sets_list = template_data.get("response_sets", [])
            response_sets = {
                rs.get("id"): rs for rs in response_sets_list if isinstance(rs, dict)
            }

            questions = extract_questions(
                items,
                response_sets=response_sets,
                page_id=None,
                page_label=None,
                section_id=None,
                section_label=None,
                template_id=template_id,
                template_name=template_name,
            )

            for question_idx, question in enumerate(questions):
                question["item_index"] = question_idx

            all_questions.extend(questions)
            successful_count += 1
            print(f"  Extracted {len(questions)} questions\n")

        except Exception as e:
            print(f"  Error extracting questions: {e}\n")
            failed_templates.append(
                {
                    "template_id": template_id,
                    "template_name": template_name,
                    "error": f"Question extraction error: {str(e)}",
                }
            )
            continue

    output_file = "output.csv"
    print(f"Writing {len(all_questions)} questions to {output_file}...")

    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "item_index",
            "item_label",
            "item_type",
            "possible_responses",
            "page_label",
            "section_label",
            "item_id",
            "page_id",
            "section_id",
            "template_id",
            "template_name",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_questions)

    print(f"\nExport complete! {len(all_questions)} questions written to {output_file}")

    # Print success report
    print("\n" + "=" * 60)
    print("EXPORT SUMMARY")
    print("=" * 60)
    print(f"Total templates processed: {len(results)}")
    print(f"Successful: {successful_count}")
    print(f"Failed: {len(failed_templates)}")
    print(f"Total questions exported: {len(all_questions)}")

    if failed_templates:
        print("\n" + "-" * 60)
        print("FAILED TEMPLATES:")
        print("-" * 60)
        for failed in failed_templates:
            print(f"  • {failed['template_name']}")
            print(f"    ID: {failed['template_id']}")
            print(f"    Error: {failed['error']}")
            print()
    else:
        print("\n✓ All templates processed successfully!")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
