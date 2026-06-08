import io
import traceback

from contextlib import redirect_stdout

_SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "ascii": ascii, "bin": bin,
    "bool": bool, "bytearray": bytearray, "bytes": bytes, "chr": chr,
    "complex": complex, "dict": dict, "dir": dir, "divmod": divmod,
    "enumerate": enumerate, "float": float, "format": format,
    "frozenset": frozenset, "hex": hex, "id": id, "int": int,
    "isinstance": isinstance, "issubclass": issubclass, "iter": iter,
    "len": len, "list": list, "map": map, "max": max, "min": min,
    "next": next, "object": object, "oct": oct, "ord": ord, "pow": pow,
    "print": print, "range": range, "repr": repr, "reversed": reversed,
    "round": round, "set": set, "slice": slice, "sorted": sorted,
    "str": str, "sum": sum, "tuple": tuple, "type": type, "zip": zip,
    "True": True, "False": False, "None": None,
}


def execute_python(code: str) -> str:
    try:
        output = io.StringIO()
        restricted_globals = {"__builtins__": _SAFE_BUILTINS}

        with redirect_stdout(output):
            exec(code, restricted_globals)

        result = output.getvalue()
        return result or "Código ejecutado correctamente"

    except Exception:
        return traceback.format_exc()
