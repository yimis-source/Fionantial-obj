def trim_messages(messages: list[dict], max_history: int = 20) -> list[dict]:
    system = [
        m for m in messages
        if m["role"] == "system"
    ]
    rest = [
        m for m in messages
        if m["role"] != "system"
    ]
    return system + rest[-max_history:]
