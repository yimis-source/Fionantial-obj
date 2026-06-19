import json

from tools.google_sheets_client import get_sheets_service, get_sheet_error_message


def read_sheet(spreadsheet_id: str, range_name: str):
    try:
        service = get_sheets_service()
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=range_name)
            .execute()
        )
        return result.get("values", [])
    except Exception as e:
        raise type(e)(f"Error en read_sheet: {get_sheet_error_message(e)}") from e


def read_google_sheet(spreadsheet_id: str, range_name: str) -> str:
    try:
        values = read_sheet(spreadsheet_id, range_name)
        if not values:
            return "No se encontraron datos en el rango solicitado."
        return json.dumps(values, ensure_ascii=False)
    except Exception as e:
        return f"Error leyendo Google Sheet: {e}"
