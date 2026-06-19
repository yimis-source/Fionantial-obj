_REGISTRY = []
_FUNCTION_MAP = {}
_IMAGES_TO_SEND = []


def tool(name: str, description: str, parameters: dict,
         required: list[str] | None = None):
    def decorator(func):
        _REGISTRY.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": parameters,
                    **({"required": required} if required else {})
                }
            }
        })
        _FUNCTION_MAP[name] = func
        return func
    return decorator


@tool(
    name="list_directory",
    description="Lista archivos y carpetas.",
    parameters={
        "path": {"type": "string"}
    }
)
def list_directory(path: str = ".") -> str:
    import os
    try:
        items = os.listdir(path)
        if not items:
            return "Directorio vacío"
        return "\n".join(items)
    except Exception as e:
        return str(e)


@tool(
    name="read_google_sheet",
    description="Lee datos de un rango de Google Sheets.",
    parameters={
        "spreadsheet_id": {
            "type": "string",
            "description": "ID del documento de Google Sheets."
        },
        "range_name": {
            "type": "string",
            "description": "Rango A1, por ejemplo 'Hoja1!A1:D20'."
        }
    },
    required=["spreadsheet_id", "range_name"]
)
def read_google_sheet(spreadsheet_id: str, range_name: str) -> str:
    from tools.read_google_sheet import read_google_sheet as _run
    return _run(spreadsheet_id, range_name)


@tool(
    name="write_google_sheet",
    description="Escribe valores en un rango de Google Sheets.",
    parameters={
        "spreadsheet_id": {
            "type": "string",
            "description": "ID del documento de Google Sheets."
        },
        "range_name": {
            "type": "string",
            "description": "Rango A1, por ejemplo 'Hoja1!A1:D20'."
        },
        "values": {
            "type": "array",
            "description": "Filas a escribir, por ejemplo [[1, 2], [3, 4]].",
            "items": {
                "type": "array",
                "items": {
                    "type": ["string", "number", "boolean", "null"]
                }
            }
        }
    },
    required=["spreadsheet_id", "range_name", "values"]
)
def write_google_sheet(
    spreadsheet_id: str,
    range_name: str,
    values: list,
) -> str:
    from tools.write_google_sheet import write_google_sheet as _run
    return _run(spreadsheet_id, range_name, values)


@tool(
    name="get_google_sheet_metadata",
    description="Obtiene metadata del documento: título, hojas, filas y columnas.",
    parameters={
        "spreadsheet_id": {
            "type": "string",
            "description": "ID del documento de Google Sheets."
        }
    },
    required=["spreadsheet_id"]
)
def get_google_sheet_metadata(spreadsheet_id: str) -> str:
    from tools.google_sheets_table import get_google_sheet_metadata as _run
    return _run(spreadsheet_id)


@tool(
    name="get_google_sheet_names",
    description="Lista los nombres de las hojas dentro de un Google Sheet.",
    parameters={
        "spreadsheet_id": {
            "type": "string",
            "description": "ID del documento de Google Sheets."
        }
    },
    required=["spreadsheet_id"]
)
def get_google_sheet_names(spreadsheet_id: str) -> str:
    from tools.google_sheets_table import get_google_sheet_names as _run
    return _run(spreadsheet_id)


@tool(
    name="detect_google_sheet_used_range",
    description="Detecta el rango usado de una hoja leyendo desde A hasta ZZ.",
    parameters={
        "spreadsheet_id": {
            "type": "string",
            "description": "ID del documento de Google Sheets."
        },
        "sheet_name": {
            "type": "string",
            "description": "Nombre exacto de la hoja."
        }
    },
    required=["spreadsheet_id", "sheet_name"]
)
def detect_google_sheet_used_range(
    spreadsheet_id: str,
    sheet_name: str,
) -> str:
    from tools.google_sheets_table import detect_google_sheet_used_range as _run
    return _run(spreadsheet_id, sheet_name)


@tool(
    name="read_google_sheet_preview",
    description="Lee las primeras filas de una hoja para entender su estructura.",
    parameters={
        "spreadsheet_id": {
            "type": "string",
            "description": "ID del documento de Google Sheets."
        },
        "sheet_name": {
            "type": "string",
            "description": "Nombre exacto de la hoja."
        },
        "rows": {
            "type": "number",
            "description": "Cantidad de filas a leer. Máximo 100."
        }
    },
    required=["spreadsheet_id", "sheet_name"]
)
def read_google_sheet_preview(
    spreadsheet_id: str,
    sheet_name: str,
    rows: int = 20,
) -> str:
    from tools.google_sheets_table import read_google_sheet_preview as _run
    return _run(spreadsheet_id, sheet_name, int(rows))


@tool(
    name="read_google_sheet_all",
    description="Lee una hoja completa con límite de filas para evitar exceso de contexto.",
    parameters={
        "spreadsheet_id": {
            "type": "string",
            "description": "ID del documento de Google Sheets."
        },
        "sheet_name": {
            "type": "string",
            "description": "Nombre exacto de la hoja."
        },
        "max_rows": {
            "type": "number",
            "description": "Máximo de filas a leer. Límite interno: 1000."
        }
    },
    required=["spreadsheet_id", "sheet_name"]
)
def read_google_sheet_all(
    spreadsheet_id: str,
    sheet_name: str,
    max_rows: int = 1000,
) -> str:
    from tools.google_sheets_table import read_google_sheet_all as _run
    return _run(spreadsheet_id, sheet_name, int(max_rows))


@tool(
    name="search_google_sheet_rows",
    description="Busca filas que contengan un texto dentro de una hoja.",
    parameters={
        "spreadsheet_id": {
            "type": "string",
            "description": "ID del documento de Google Sheets."
        },
        "sheet_name": {
            "type": "string",
            "description": "Nombre exacto de la hoja."
        },
        "query": {
            "type": "string",
            "description": "Texto a buscar en las filas."
        },
        "max_results": {
            "type": "number",
            "description": "Máximo de resultados. Límite interno: 25."
        }
    },
    required=["spreadsheet_id", "sheet_name", "query"]
)
def search_google_sheet_rows(
    spreadsheet_id: str,
    sheet_name: str,
    query: str,
    max_results: int = 25,
) -> str:
    from tools.google_sheets_table import search_google_sheet_rows as _run
    return _run(spreadsheet_id, sheet_name, query, int(max_results))


@tool(
    name="summarize_google_sheet",
    description="Resume una hoja: columnas, conteos, valores principales y métricas numéricas.",
    parameters={
        "spreadsheet_id": {
            "type": "string",
            "description": "ID del documento de Google Sheets."
        },
        "sheet_name": {
            "type": "string",
            "description": "Nombre exacto de la hoja."
        },
        "max_rows": {
            "type": "number",
            "description": "Máximo de filas a analizar. Límite interno: 1000."
        }
    },
    required=["spreadsheet_id", "sheet_name"]
)
def summarize_google_sheet(
    spreadsheet_id: str,
    sheet_name: str,
    max_rows: int = 1000,
) -> str:
    from tools.google_sheets_table import summarize_google_sheet as _run
    return _run(spreadsheet_id, sheet_name, int(max_rows))


@tool(
    name="execute_python",
    description="Ejecuta código Python en un entorno seguro.",
    parameters={
        "code": {"type": "string"}
    },
    required=["code"]
)
def execute_python(code: str) -> str:
    from tools.execute_python import execute_python as _run
    return _run(code)


@tool(
    name="analyze_document",
    description="Analiza archivos de datos: CSV, Excel (.xlsx/.xls) o bases SQLite (.db/.sqlite). "
                "Muestra estructura, columnas, tipos, estadísticas y preview.",
    parameters={
        "path": {
            "type": "string",
            "description": "Ruta al archivo"
        },
        "sheet": {
            "type": "string",
            "description": "Nombre de la hoja (solo Excel). Opcional."
        }
    },
    required=["path"]
)
def analyze_document(path: str, sheet: str | None = None) -> str:
    from tools.analyze_document import analyze_document as _run
    return _run(path, sheet)




@tool(
    name="search_web",
    description="Busca información actualizada en internet. Úsalo cuando necesites datos recientes, "
                "noticias financieras, TRM del dólar, o cualquier información que no tengas en tu base local.",
    parameters={
        "query": {
            "type": "string",
            "description": "La consulta de búsqueda"
        },
        "max_results": {
            "type": "number",
            "description": "Cantidad máxima de resultados (máx 10)"
        }
    },
    required=["query"]
)
def search_web(query: str, max_results: int = 5) -> str:
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            raw = ddgs.text(query)
        results = []
        for r in raw[:min(int(max_results), 10)]:
            title = r.get('title', '')
            body = r.get('body', '')[:200]
            results.append(f"• {title}: {body}")
        if not results:
            return "No se encontraron resultados."
        return "\n".join(results)
    except Exception as e:
        return f"Error en búsqueda web: {e}"


@tool(
    name="generate_mermaid_chart",
    description="Genera un gráfico Mermaid y lo envía como imagen. "
                "Úsalo para gráficos de pastel, barras, flujo, gantt, timeline, etc.",
    parameters={
        "code": {
            "type": "string",
            "description": "Código Mermaid. Ej: 'pie title Gastos\\n\"Proveedores\": 40\\n\"Nomina\": 30'"
        },
        "title": {
            "type": "string",
            "description": "Título del gráfico (breve)"
        },
        "chart_type": {
            "type": "string",
            "description": "'pie', 'flowchart', 'gantt', 'timeline', 'bar'"
        }
    },
    required=["code"]
)
def generate_mermaid_chart(code: str, title: str = "", chart_type: str = "flowchart") -> str:
    import base64, os, tempfile, requests

    full_code = code.strip()
    if not full_code.startswith(("graph", "flowchart", "pie", "gantt", "timeline", "mindmap", "git", "sequenceDiagram", "classDiagram", "stateDiagram", "erDiagram", "journey", "xychart")):
        if chart_type == "pie":
            full_code = f"pie title {title}\n{full_code}" if title else f"pie\n{full_code}"
        elif chart_type in ("bar", "flowchart"):
            full_code = f"graph TD\n{full_code}"
        elif chart_type == "gantt":
            full_code = f"gantt\ntitle {title}\ndateFormat YYYY-MM-DD\n{full_code}" if title else f"gantt\n{full_code}"
        elif chart_type == "timeline":
            full_code = f"timeline\ntitle {title}\n{full_code}" if title else f"timeline\n{full_code}"

    encoded = base64.urlsafe_b64encode(full_code.encode()).decode()
    img_url = f"https://mermaid.ink/img/{encoded}?type=png"

    # Download the image
    img_path = None
    try:
        resp = requests.get(img_url, timeout=15)
        if resp.status_code == 200:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp.write(resp.content)
            tmp.close()
            img_path = tmp.name
            _IMAGES_TO_SEND.append(img_path)
    except Exception as e:
        pass

    label = f"📊 {title}" if title else "📊 Gráfico"
    result = f"{label}\n\nIMAGEN_GENERADA:{img_url}"
    if img_path:
        result += f"\nIMAGEN_PATH:{img_path}"

    return result


TOOLS = list(_REGISTRY)
FUNCTION_MAP = dict(_FUNCTION_MAP)
