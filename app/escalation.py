TOOL_ESCALATION_NAME = "request_escalation"


def extraer_motivo_escalado(messages: list, tool_calls: list) -> str | None:
    for tc in tool_calls:
        if tc["function"]["name"] == TOOL_ESCALATION_NAME:
            import json
            try:
                args = json.loads(tc["function"]["arguments"])
                return args.get("motivo", "No especificado")
            except (json.JSONDecodeError, KeyError):
                return "No especificado"
    return None
