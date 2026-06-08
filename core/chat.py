import json

from groq.types.chat import ChatCompletion

from langsmith import traceable

from core.client import client
from core.config import DEFAULT_MODEL
from core.config import MAX_TOOL_ITERATIONS
from tools.registry import TOOLS
from tools.registry import FUNCTION_MAP


@traceable(name="groq-chat", run_type="llm")
def chat(messages: list[dict]) -> ChatCompletion:
    return client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto"
    )


def process_tools(messages, response, session_id=None, save_fn=None):
    message = response.choices[0].message
    iterations = 0

    while message.tool_calls:
        iterations += 1
        if iterations > MAX_TOOL_ITERATIONS:
            message.content = (
                message.content or ""
                + "\n\n(Límite de herramientas alcanzado)"
            )
            break

        assistant_msg = {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                tc.model_dump()
                for tc in message.tool_calls
            ]
        }
        messages.append(assistant_msg)

        if session_id and save_fn:
            save_fn(
                session_id, "assistant",
                content=assistant_msg["content"],
                tool_calls=assistant_msg["tool_calls"]
            )

        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            try:
                tool_result = FUNCTION_MAP[tool_name](**args)
            except Exception as e:
                tool_result = f"Error ejecutando {tool_name}: {e}"

            tool_msg = {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(tool_result)
            }
            messages.append(tool_msg)

            if session_id and save_fn:
                save_fn(
                    session_id, "tool",
                    content=tool_msg["content"],
                    tool_call_id=tool_msg["tool_call_id"]
                )

        response = chat(messages)
        message = response.choices[0].message

    return message.content
