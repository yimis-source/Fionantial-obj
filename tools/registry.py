import json
import os

_REGISTRY = []
_FUNCTION_MAP = {}
_TOOL_METRICS = {}

MAX_OUTPUT_CHARS = 3000


def _sanitize_output(output: str, tool_name: str = "") -> str:
    if not isinstance(output, str):
        output = str(output)
    if len(output) > MAX_OUTPUT_CHARS:
        output = output[:MAX_OUTPUT_CHARS] + f"\n[... output truncado a {MAX_OUTPUT_CHARS} caracteres]"
    return output


def _track_metrics(tool_name: str, tokens_in: int, tokens_out: int, duration_ms: int, success: bool):
    if tool_name not in _TOOL_METRICS:
        _TOOL_METRICS[tool_name] = {
            "calls": 0,
            "errors": 0,
            "total_tokens_in": 0,
            "total_tokens_out": 0,
            "total_duration_ms": 0,
        }
    m = _TOOL_METRICS[tool_name]
    m["calls"] += 1
    m["total_tokens_in"] += tokens_in
    m["total_tokens_out"] += tokens_out
    m["total_duration_ms"] += duration_ms
    if not success:
        m["errors"] += 1


def get_tool_metrics():
    return dict(_TOOL_METRICS)


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
    name="read_google_sheet",
    description="Lee datos de Google Sheets. Decide automáticamente cuántas filas leer según el tamaño de la hoja. "
                "Usa sheet_name y opcionalmente el rango específico. Si no especificas rango, lee preview + resumen.",
    parameters={
        "spreadsheet_id": {
            "type": "string",
            "description": "ID del documento de Google Sheets."
        },
        "sheet_name": {
            "type": "string",
            "description": "Nombre exacto de la hoja (ej: 'Hoja1')."
        },
        "range": {
            "type": "string",
            "description": "Rango opcional A1 (ej: 'A1:D50'). Si se omite, lee inteligentemente."
        }
    },
    required=["spreadsheet_id", "sheet_name"]
)
def read_google_sheet(spreadsheet_id: str, sheet_name: str, range: str | None = None) -> str:
    from tools.google_sheets_table import (
        get_google_sheet_metadata, read_google_sheet_all,
        read_google_sheet_preview, summarize_google_sheet,
        _read_values
    )
    try:
        if range:
            values = _read_values(spreadsheet_id, f"'{sheet_name}'!{range}")
            return json.dumps({"sheet": sheet_name, "range": range, "rows": len(values), "values": values},
                              ensure_ascii=False, indent=2)

        metadata = json.loads(get_google_sheet_metadata(spreadsheet_id))
        sheets = metadata.get("sheets", [])
        target = next((s for s in sheets if s["title"] == sheet_name), None)
        if not target:
            return json.dumps({"error": f"Hoja '{sheet_name}' no encontrada"})

        total_rows = target.get("rows", 1000)
        if total_rows <= 30:
            return read_google_sheet_all(spreadsheet_id, sheet_name, max_rows=total_rows)
        else:
            preview = json.loads(read_google_sheet_preview(spreadsheet_id, sheet_name, rows=20))
            summary = json.loads(summarize_google_sheet(spreadsheet_id, sheet_name, max_rows=100))
            return json.dumps({
                "sheet": sheet_name,
                "total_rows": total_rows,
                "preview": preview.get("values", []),
                "summary": summary.get("column_summaries", []),
                "note": "La hoja tiene más de 30 filas. Usa 'range' si necesitas un subconjunto específico."
            }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error leyendo Google Sheet: {e}"


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
def write_google_sheet(spreadsheet_id: str, range_name: str, values: list) -> str:
    from tools.write_google_sheet import write_google_sheet as _run
    return _sanitize_output(_run(spreadsheet_id, range_name, values), "write_google_sheet")


@tool(
    name="search_google_sheet_rows",
    description="Busca filas que contengan un texto dentro de una hoja de Google Sheets.",
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
        }
    },
    required=["spreadsheet_id", "sheet_name", "query"]
)
def search_google_sheet_rows(spreadsheet_id: str, sheet_name: str, query: str) -> str:
    from tools.google_sheets_table import search_google_sheet_rows as _run
    return _sanitize_output(_run(spreadsheet_id, sheet_name, query, 25), "search_google_sheet_rows")


@tool(
    name="execute_python",
    description="Ejecuta código Python en un entorno seguro con bibliotecas financieras restrictivas "
                "(math, statistics, decimal, datetime, json, numpy). Sin acceso a red ni sistema de archivos.",
    parameters={
        "code": {"type": "string"}
    },
    required=["code"]
)
def execute_python(code: str) -> str:
    from tools.execute_python import execute_python as _run
    return _sanitize_output(_run(code), "execute_python")


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
    return _sanitize_output(_run(path, sheet), "analyze_document")


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
            "description": "Cantidad máxima de resultados (máx 5)"
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
        for r in raw[:min(int(max_results), 5)]:
            title = r.get('title', '')[:100]
            snippet = r.get('body', '')[:200]
            results.append(f"• {title}: {snippet}")
        if not results:
            return "No se encontraron resultados."
        return "\n".join(results)
    except Exception as e:
        return f"Error en búsqueda web: {e}"


@tool(
    name="generate_mermaid_chart",
    description="Genera un diagrama Mermaid. Devuelve el código del diagrama formateado. "
                "Úsalo para gráficos de pastel, barras, flujo, gantt, timeline, etc.",
    parameters={
        "code": {
            "type": "string",
            "description": "Código Mermaid. Ej: 'pie title Gastos\\n\"Proveedores\": 40\\n\"Nomina\": 30'"
        },
        "title": {
            "type": "string",
            "description": "Título del gráfico (breve)"
        }
    },
    required=["code"]
)
def generate_mermaid_chart(code: str, title: str = "") -> str:
    label = f"📊 {title}" if title else "📊 Gráfico"
    return f"{label}\n\n```mermaid\n{code}\n```"


@tool(
    name="calculate_financial",
    description="Realiza cálculos financieros: interés compuesto, amortización de préstamos, conversión de divisas. "
                "Usa tasas en porcentaje anual (ej: 5 para 5%).",
    parameters={
        "tipo": {
            "type": "string",
            "enum": ["interes_compuesto", "amortizacion", "conversion"],
            "description": "Tipo de cálculo: interes_compuesto, amortizacion, conversion"
        },
        "monto": {
            "type": "number",
            "description": "Monto principal o capital inicial"
        },
        "tasa_anual": {
            "type": "number",
            "description": "Tasa de interés anual en porcentaje (ej: 5.5 para 5.5%)"
        },
        "plazo_meses": {
            "type": "number",
            "description": "Plazo en meses (para interés compuesto y amortización)"
        },
        "tasa_cambio": {
            "type": "number",
            "description": "Tasa de cambio para conversión de divisas"
        }
    },
    required=["tipo", "monto"]
)
def calculate_financial(tipo: str, monto: float, tasa_anual: float = 0,
                        plazo_meses: int = 1, tasa_cambio: float = 1) -> str:
    from tools.financial_calc import (
        calcular_interes_compuesto, calcular_amortizacion, convertir_division
    )
    try:
        if tipo == "interes_compuesto":
            r = calcular_interes_compuesto(monto, tasa_anual, plazo_meses)
        elif tipo == "amortizacion":
            r = calcular_amortizacion(monto, tasa_anual, plazo_meses)
        elif tipo == "conversion":
            r = convertir_division(monto, tasa_cambio)
        else:
            return f"Tipo '{tipo}' no válido. Usa: interes_compuesto, amortizacion, conversion"
        return json.dumps(r, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error en cálculo financiero: {e}"


@tool(
    name="get_current_datetime",
    description="Obtiene la fecha y hora actual en Colombia.",
    parameters={
        "zona": {
            "type": "string",
            "enum": ["colombia"],
            "description": "Zona horaria (solo Colombia por ahora)"
        }
    }
)
def get_current_datetime_tool(zona: str = "colombia") -> str:
    from tools.get_datetime import get_current_datetime
    try:
        r = get_current_datetime(zona)
        return json.dumps(r, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error obteniendo fecha/hora: {e}"


@tool(
    name="format_currency_cop",
    description="Formatea un número a moneda colombiana (COP) con puntos de miles y símbolo $.",
    parameters={
        "valor": {
            "type": "number",
            "description": "Valor numérico a formatear"
        }
    },
    required=["valor"]
)
def format_currency_cop(valor: float) -> str:
    from tools.financial_calc import formatear_cop
    return formatear_cop(valor)


@tool(
    name="request_escalation",
    description="SOLO ÚSALA cuando el usuario lo pida explícitamente: solicita hablar con un humano, "
                "pide un supervisor, o muestra frustración clara e irresoluble que no puedes manejar. "
                "NO la uses para preguntas normales o dudas financieras que puedas resolver.",
    parameters={
        "motivo": {
            "type": "string",
            "description": "Razón detallada por la que se necesita escalar a un humano"
        }
    },
    required=["motivo"]
)
def request_escalation(motivo: str) -> str:
    return f"ESCALAR_A_HUMANO:{motivo}"


TOOLS = list(_REGISTRY)
FUNCTION_MAP = dict(_FUNCTION_MAP)
