from tools.google_sheets_client import get_sheets_service


def write_sheet(spreadsheet_id: str, range_name: str, values: list):
    service = get_sheets_service()
    body = {"values": values}
    return (
        service.spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="RAW",
            body=body,
        )
        .execute()
    )


def write_google_sheet(
    spreadsheet_id: str,
    range_name: str,
    values: list,
) -> str:
    from tools.google_sheets_client import get_sheet_error_message
    try:
        result = write_sheet(spreadsheet_id, range_name, values)
        updated_cells = result.get("updatedCells", 0)
        updated_range = result.get("updatedRange", range_name)
        return (
            "Google Sheet actualizado correctamente. "
            f"Rango: {updated_range}. Celdas actualizadas: {updated_cells}."
        )
    except Exception as e:
        return f"Error escribiendo Google Sheet: {get_sheet_error_message(e)}"
