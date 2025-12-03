import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

# Set your SafetyCulture API token here
TOKEN = ''

BASE_URL = "https://api.safetyculture.io"
LIST_COMPANIES_ENDPOINT = f"{BASE_URL}/companies/v1beta/companies"
PAGE_SIZE = 100  # As per OpenAPI spec: page_size + page_token pagination
OPENAPI_SPEC_PATH = Path(__file__).resolve().parents[2] / "apidocs.openapi.json"


def _collect_schema_fields(
    schema: Dict[str, Any],
    components: Dict[str, Any],
    prefix: str = "",
    stack: Optional[List[str]] = None,
) -> List[str]:
    """Collect dotted field paths from a schema (follows $ref entries)."""
    stack = stack or []
    if not schema:
        return [prefix] if prefix else []

    if "$ref" in schema:
        ref_name = schema["$ref"].split("/")[-1]
        if ref_name in stack:
            return [prefix] if prefix else []
        referenced_schema = components.get(ref_name, {})
        return _collect_schema_fields(
            referenced_schema, components, prefix, stack + [ref_name]
        )

    schema_type = schema.get("type")
    properties = schema.get("properties", {})

    if properties:
        fields: List[str] = []
        for name, subschema in properties.items():
            nested_prefix = f"{prefix}.{name}" if prefix else name
            fields.extend(
                _collect_schema_fields(subschema, components, nested_prefix, stack)
            )
        return fields

    if schema_type == "array":
        items = schema.get("items", {})
        nested_prefix = f"{prefix}[]" if prefix else "[]"
        nested_fields = _collect_schema_fields(items, components, nested_prefix, stack)
        return nested_fields or [nested_prefix]

    return [prefix] if prefix else []


def load_spec_fieldnames() -> List[str]:
    """Use the OpenAPI spec to pre-seed CSV column order for ContractorCompany."""
    if not OPENAPI_SPEC_PATH.exists():
        print("⚠️  OpenAPI spec not found; deriving columns from API data only.")
        return []

    try:
        with OPENAPI_SPEC_PATH.open(encoding="utf-8") as spec_file:
            spec = json.load(spec_file)
        components = spec.get("components", {}).get("schemas", {})
    except Exception as exc:  # pragma: no cover - defensive for runtime use
        print(f"⚠️  Unable to read OpenAPI spec ({exc}); deriving columns from data.")
        return []

    fields = _collect_schema_fields(
        {"$ref": "#/components/schemas/s12.contractors.v1.ContractorCompany"},
        components,
    )
    return list(dict.fromkeys(fields))  # preserve order, drop duplicates


def flatten_record(data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Flatten nested dictionaries into dot-notation keys for CSV writing."""
    flattened: Dict[str, Any] = {}

    for key, value in data.items():
        new_prefix = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):
            flattened.update(flatten_record(value, new_prefix))
        elif isinstance(value, list):
            if value and all(isinstance(item, dict) for item in value):
                for index, item in enumerate(value):
                    flattened.update(flatten_record(item, f"{new_prefix}[{index}]"))
            else:
                flattened[new_prefix] = "|".join(
                    "" if item is None else str(item) for item in value
                )
        else:
            flattened[new_prefix] = "" if value is None else value

    return flattened


def fetch_contractor_companies(token: str) -> List[Dict[str, Any]]:
    """Call the List Companies endpoint with page_size/page_token pagination."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    session = requests.Session()
    page_token = None
    companies: List[Dict[str, Any]] = []
    page = 1
    total_count = None

    while True:
        payload = {"page_size": PAGE_SIZE}
        if page_token:
            payload["page_token"] = page_token

        response = session.post(
            LIST_COMPANIES_ENDPOINT, headers=headers, json=payload, timeout=30
        )
        response.raise_for_status()

        body = response.json()
        if total_count is None:
            total_count = body.get("total_count")

        page_companies = body.get("contractor_company_list", [])
        companies.extend(page_companies)

        print(
            f"📄 Page {page}: {len(page_companies)} companies "
            f"(total so far: {len(companies)})"
        )

        page_token = body.get("next_page_token")
        if not page_token:
            break
        page += 1

    if total_count is not None and len(companies) != total_count:
        print(
            f"⚠️  Warning: API total_count={total_count} but fetched {len(companies)}."
        )

    return companies


def prepare_rows(
    companies: List[Dict[str, Any]], base_fieldnames: List[str]
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Flatten all companies and assemble the full CSV header."""
    fieldnames = list(base_fieldnames)
    rows: List[Dict[str, Any]] = []

    for company in companies:
        flat = flatten_record(company)
        for key in flat:
            if key not in fieldnames:
                fieldnames.append(key)
        rows.append(flat)

    return fieldnames, rows


def write_csv(rows: List[Dict[str, Any]], fieldnames: List[str], output_path: Path):
    """Write flattened company rows to CSV."""
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def output_filename() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(f"contractor_companies_{timestamp}.csv")


def main() -> int:
    token = TOKEN or os.getenv("SC_API_TOKEN", "")
    if not token:
        print(
            "❌ Error: Please set your SafetyCulture API token in TOKEN or SC_API_TOKEN."
        )
        return 1

    print("🚀 Exporting contractor companies via /companies/v1beta/companies")
    print(f"🔎 Using OpenAPI spec at: {OPENAPI_SPEC_PATH}")

    spec_fieldnames = load_spec_fieldnames()

    try:
        companies = fetch_contractor_companies(token)
    except requests.exceptions.HTTPError as http_err:
        print(f"❌ HTTP error: {http_err}")
        return 1
    except requests.exceptions.RequestException as req_err:
        print(f"❌ Request error: {req_err}")
        return 1

    if not companies:
        print("No contractor companies returned by the API.")
        return 0

    fieldnames, rows = prepare_rows(companies, spec_fieldnames)
    outfile = output_filename()

    write_csv(rows, fieldnames, outfile)

    print(f"✅ Export complete. {len(companies)} companies saved to {outfile}")
    print(f"🧾 Columns included: {len(fieldnames)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
