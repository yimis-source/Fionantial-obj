import sys
import subprocess
import tempfile
import os

_TIMEOUT_SECONDS = 10
_MAX_OUTPUT_LINES = 50


def execute_python(code: str) -> str:
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("import math, statistics, decimal, datetime, json\n")
            f.write("import builtins as _b\n")
            f.write("__builtins__ = {\n")
            for name in ["abs","all","any","bool","chr","complex","dict","divmod",
                         "enumerate","Exception","float","format","frozenset","hex","int",
                         "isinstance","issubclass","iter","len","list","map","max",
                         "min","next","object","oct","ord","pow","print","range",
                         "repr","reversed","round","set","slice","sorted","str",
                         "sum","tuple","type","ValueError","zip",
                         "True","False","None"]:
                f.write(f"  '{name}': getattr(_b, '{name}'),\n")
            f.write("}\n")
            f.write("exec(" + repr(code) + ")\n")
            tmp_path = f.name

        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return f"Error: El código excedió el límite de {_TIMEOUT_SECONDS} segundos."
    except Exception as e:
        return f"Error ejecutando código: {e}"
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    output = result.stdout or ""
    error = result.stderr or ""

    if error:
        lines = error.splitlines()
        if len(lines) > _MAX_OUTPUT_LINES:
            error = "\n".join(lines[:_MAX_OUTPUT_LINES]) + f"\n[... {len(lines) - _MAX_OUTPUT_LINES} líneas más]"

    if output:
        lines = output.splitlines()
        if len(lines) > _MAX_OUTPUT_LINES:
            output = "\n".join(lines[:_MAX_OUTPUT_LINES]) + f"\n[... {len(lines) - _MAX_OUTPUT_LINES} líneas más]"

    if error and not output:
        return f"Error de ejecución:\n{error}"
    if output and error:
        return f"{output}\n\n(Advertencias/errores):\n{error}"
    return output or "Código ejecutado correctamente (sin salida)."
