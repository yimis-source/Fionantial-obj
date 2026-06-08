_REGISTRY = []
_FUNCTION_MAP = {}


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


TOOLS = list(_REGISTRY)
FUNCTION_MAP = dict(_FUNCTION_MAP)
