import json
from collections import Counter

from tools.google_sheets_client import get_sheets_service


MAX_READ_ROWS = 1000
MAX_SEARCH_RESULTS = 25


def _quote_sheet_name(sheet_name: str) -> str:
    escaped = sheet_name.replace("'", "''")
    return f"'{escaped}'"


def _read_values(spreadsheet_id: str, range_name: str) -> list[list]:
    service = get_sheets_service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_name)
        .execute()
    )
    return result.get("values", [])


def _rows_to_dicts(values: list[list]) -> list[dict]:
    if not values:
        return []

    headers = [str(value) for value in values[0]]
    rows = []

    for row in values[1:]:
        item = {}
        for index, header in enumerate(headers):
            item[header] = row[index] if index < len(row) else ""
        rows.append(item)

    return rows


def _format_json(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def get_google_sheet_metadata(spreadsheet_id: str) -> str:
    service = get_sheets_service()
    result = (
        service.spreadsheets()
        .get(
            spreadsheetId=spreadsheet_id,
            fields=(
                "spreadsheetId,properties.title,"
                "sheets.properties(title,sheetId,index,gridProperties)"
            ),
        )
        .execute()
    )

    sheets = []
    for sheet in result.get("sheets", []):
        props = sheet.get("properties", {})
        grid = props.get("gridProperties", {})
        sheets.append({
            "title": props.get("title"),
            "sheet_id": props.get("sheetId"),
            "index": props.get("index"),
            "rows": grid.get("rowCount"),
            "columns": grid.get("columnCount"),
        })

    return _format_json({
        "spreadsheet_id": result.get("spreadsheetId"),
        "title": result.get("properties", {}).get("title"),
        "sheets": sheets,
    })


def get_google_sheet_names(spreadsheet_id: str) -> str:
    metadata = json.loads(get_google_sheet_metadata(spreadsheet_id))
    return _format_json([sheet["title"] for sheet in metadata["sheets"]])


def detect_google_sheet_used_range(spreadsheet_id: str, sheet_name: str) -> str:
    range_name = f"{_quote_sheet_name(sheet_name)}!A:ZZ"
    values = _read_values(spreadsheet_id, range_name)

    if not values:
        return _format_json({
            "sheet_name": sheet_name,
            "used_range": None,
            "rows": 0,
            "columns": 0,
        })

    row_count = len(values)
    column_count = max((len(row) for row in values), default=0)
    last_column = _column_number_to_name(column_count)

    return _format_json({
        "sheet_name": sheet_name,
        "used_range": f"{sheet_name}!A1:{last_column}{row_count}",
        "rows": row_count,
        "columns": column_count,
    })


def _column_number_to_name(number: int) -> str:
    name = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        name = chr(65 + remainder) + name
    return name or "A"


def read_google_sheet_preview(
    spreadsheet_id: str,
    sheet_name: str,
    rows: int = 20,
) -> str:
    rows = max(1, min(rows, 100))
    range_name = f"{_quote_sheet_name(sheet_name)}!A1:ZZ{rows}"
    values = _read_values(spreadsheet_id, range_name)

    return _format_json({
        "sheet_name": sheet_name,
        "requested_rows": rows,
        "returned_rows": len(values),
        "values": values,
    })


def read_google_sheet_all(
    spreadsheet_id: str,
    sheet_name: str,
    max_rows: int = MAX_READ_ROWS,
) -> str:
    max_rows = max(1, min(max_rows, MAX_READ_ROWS))
    range_name = f"{_quote_sheet_name(sheet_name)}!A1:ZZ{max_rows}"
    values = _read_values(spreadsheet_id, range_name)

    return _format_json({
        "sheet_name": sheet_name,
        "max_rows": max_rows,
        "returned_rows": len(values),
        "truncated": len(values) >= max_rows,
        "values": values,
    })


def search_google_sheet_rows(
    spreadsheet_id: str,
    sheet_name: str,
    query: str,
    max_results: int = MAX_SEARCH_RESULTS,
) -> str:
    max_results = max(1, min(max_results, MAX_SEARCH_RESULTS))
    values = _read_values(
        spreadsheet_id,
        f"{_quote_sheet_name(sheet_name)}!A1:ZZ{MAX_READ_ROWS}",
    )
    rows = _rows_to_dicts(values)
    query_normalized = query.lower()

    matches = []
    for row_index, row in enumerate(rows, start=2):
        haystack = " ".join(str(value) for value in row.values()).lower()
        if query_normalized in haystack:
            matches.append({
                "row_number": row_index,
                "row": row,
            })

        if len(matches) >= max_results:
            break

    return _format_json({
        "sheet_name": sheet_name,
        "query": query,
        "matches": matches,
        "returned": len(matches),
    })


def summarize_google_sheet(
    spreadsheet_id: str,
    sheet_name: str,
    max_rows: int = MAX_READ_ROWS,
) -> str:
    max_rows = max(1, min(max_rows, MAX_READ_ROWS))
    values = _read_values(
        spreadsheet_id,
        f"{_quote_sheet_name(sheet_name)}!A1:ZZ{max_rows}",
    )

    if not values:
        return _format_json({
            "sheet_name": sheet_name,
            "rows": 0,
            "columns": 0,
            "message": "No se encontraron datos.",
        })

    headers = [str(value) for value in values[0]]
    data_rows = values[1:]
    column_summaries = []

    for index, header in enumerate(headers):
        column_values = [
            row[index]
            for row in data_rows
            if index < len(row) and row[index] not in ("", None)
        ]
        numeric_values = []
        for value in column_values:
            try:
                numeric_values.append(float(str(value).replace(",", "")))
            except ValueError:
                pass

        summary = {
            "column": header,
            "non_empty": len(column_values),
            "empty": len(data_rows) - len(column_values),
        }

        if numeric_values and len(numeric_values) == len(column_values):
            summary.update({
                "type": "number",
                "min": min(numeric_values),
                "max": max(numeric_values),
                "sum": sum(numeric_values),
                "average": sum(numeric_values) / len(numeric_values),
            })
        else:
            top_values = Counter(str(value) for value in column_values).most_common(5)
            summary.update({
                "type": "text",
                "unique": len(set(str(value) for value in column_values)),
                "top_values": [
                    {"value": value, "count": count}
                    for value, count in top_values
                ],
            })

        column_summaries.append(summary)

    return _format_json({
        "sheet_name": sheet_name,
        "rows": len(data_rows),
        "columns": len(headers),
        "headers": headers,
        "truncated": len(values) >= max_rows,
        "column_summaries": column_summaries,
    })
