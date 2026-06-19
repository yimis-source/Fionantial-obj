import json
import os
from pathlib import Path
from dotenv import load_dotenv

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import GoogleAuthError


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_dotenv_loaded = False


def _ensure_env():
    global _dotenv_loaded
    if not _dotenv_loaded:
        dotenv_path = Path(__file__).resolve().parent.parent / ".env"
        load_dotenv(dotenv_path=dotenv_path)
        _dotenv_loaded = True


def get_sheets_service():
    _ensure_env()
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise ValueError(
            "GOOGLE_SERVICE_ACCOUNT_JSON no está configurado en .env. "
            "Debes agregar el JSON del service account de Google Cloud."
        )
    try:
        creds_json = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"GOOGLE_SERVICE_ACCOUNT_JSON no es un JSON válido: {e}"
        )
    try:
        creds = service_account.Credentials.from_service_account_info(
            creds_json,
            scopes=SCOPES,
        )
    except Exception as e:
        raise ValueError(
            f"Error con las credenciales del service account: {e}"
        )
    return build("sheets", "v4", credentials=creds)


def get_sheet_error_message(e: Exception) -> str:
    if isinstance(e, HttpError):
        status = e.status_code
        if status == 403:
            return "Acceso denegado. La service account no tiene acceso al spreadsheet. Comparte el documento con el email del service account (termina en @gserviceaccount.com) como editor."
        if status == 404:
            return "Spreadsheet no encontrado. Verifica que el ID del documento sea correcto."
        if status == 429:
            return "Límite de cuota de API de Google excedido. Intenta de nuevo en unos minutos."
        return f"Error de API de Google (HTTP {status}): {e}"
    if isinstance(e, GoogleAuthError):
        return f"Error de autenticación con Google: {e}"
    return str(e)
