import os


def list_directory(path: str = ".") -> str:

    try:
        items = os.listdir(path)

        if not items:
            return "Directorio vacío"

        return "\n".join(items)

    except Exception as e:
        return str(e)