import json

from tools.google_sheets_client import get_sheets_service


def read_sheet(spreadsheet_id: str, range_name: str):
    service = get_sheets_service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_name)
        .execute()
    )
    return result.get("values", [])


def read_google_sheet(spreadsheet_id: str, range_name: str) -> str:
    values = read_sheet(spreadsheet_id, range_name)
    if not values:
        return "No se encontraron datos en el rango solicitado."

    return json.dumps(values, ensure_ascii=False)
