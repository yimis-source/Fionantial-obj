import time
import json
from typing import Optional

from app.config import (
    ANTHROPIC_API_KEY, GROQ_API_KEY, OPENAI_API_KEY,
    LLM_PROVIDER, DEFAULT_MODEL, FALLBACK_MODEL,
    MAX_TOOL_ITERATIONS
)
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
from tools.registry import TOOLS, FUNCTION_MAP


def _update_run_tokens(input_tokens: int, output_tokens: int):
    run = get_current_run_tree()
    if run:
        try:
            run.add_metadata({
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            })
        except Exception:
            pass


class LLMClient:
    def __init__(self):
        self.provider = LLM_PROVIDER
        self.model = DEFAULT_MODEL
        self.fallback_model = FALLBACK_MODEL
        self.client = None
        self.fallback_client = None
        self._init_clients()

    def _init_clients(self):
        if self.provider == "anthropic" and ANTHROPIC_API_KEY:
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            except Exception as e:
                print(f"Error initializing Anthropic: {e}")

        if GROQ_API_KEY:
            try:
                from groq import Groq
                self.fallback_client = Groq(api_key=GROQ_API_KEY)
            except Exception as e:
                print(f"Error initializing Groq fallback: {e}")

        if not self.client and not self.fallback_client:
            if OPENAI_API_KEY:
                try:
                    from openai import OpenAI
                    self.client = OpenAI(api_key=OPENAI_API_KEY)
                    self.provider = "openai"
                except Exception as e:
                    print(f"Error initializing OpenAI: {e}")

    @traceable(name="llm-chat", run_type="llm")
    def chat(self, messages, tools=None, max_tokens=256):
        if self.provider == "anthropic" and self.client:
            return self._chat_anthropic(messages, tools, max_tokens)
        elif self.client and self.provider == "openai":
            return self._chat_openai(messages, tools, max_tokens)
        elif self.fallback_client:
            return self._chat_groq(messages, tools, max_tokens)
        raise RuntimeError("No LLM client available")

    def _chat_anthropic(self, messages, tools=None, max_tokens=256):
        system = ""
        anthropic_messages = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            elif m["role"] == "user":
                anthropic_messages.append({"role": "user", "content": m["content"]})
            elif m["role"] == "assistant":
                anthropic_messages.append({"role": "assistant", "content": m["content"]})
            elif m["role"] == "tool":
                anthropic_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": m.get("tool_call_id", ""),
                        "content": m["content"]
                    }]
                })

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": anthropic_messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            anthropic_tools = []
            for t in tools:
                at = {
                    "name": t["function"]["name"],
                    "description": t["function"]["description"],
                    "input_schema": t["function"]["parameters"],
                }
                anthropic_tools.append(at)
            kwargs["tools"] = anthropic_tools

        response = self.client.messages.create(**kwargs)
        result = self._parse_anthropic_response(response)
        usage = result.get("usage", {})
        _update_run_tokens(usage.get("input_tokens", 0), usage.get("output_tokens", 0))
        return result

    def _parse_anthropic_response(self, response):
        result = {"content": "", "tool_calls": [], "usage": {}}
        for block in response.content:
            if block.type == "text":
                result["content"] = block.text
            elif block.type == "tool_use":
                result["tool_calls"].append({
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(block.input)
                    }
                })
        if hasattr(response, "usage"):
            result["usage"] = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        return result

    def _chat_openai(self, messages, tools=None, max_tokens=256):
        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        response = self.client.chat.completions.create(**kwargs)
        result = self._parse_openai_response(response)
        usage = result.get("usage", {})
        _update_run_tokens(usage.get("input_tokens", 0), usage.get("output_tokens", 0))
        return result

    def _chat_groq(self, messages, tools=None, max_tokens=256):
        import time as _time
        kwargs = {
            "model": self.fallback_model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        for attempt in range(3):
            try:
                response = self.fallback_client.chat.completions.create(**kwargs)
                result = self._parse_openai_response(response)
                usage = result.get("usage", {})
                _update_run_tokens(usage.get("input_tokens", 0), usage.get("output_tokens", 0))
                return result
            except Exception as e:
                if "429" in str(e) or "rate limit" in str(e).lower():
                    if attempt < 2:
                        _time.sleep(2 ** (attempt + 1))
                        continue
                raise
        raise RuntimeError("Max retries exceeded for Groq API")

    def _parse_openai_response(self, response):
        message = response.choices[0].message
        result = {"content": message.content or "", "tool_calls": [], "usage": {}}
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tc in message.tool_calls:
                result["tool_calls"].append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                })
        if hasattr(response, "usage") and response.usage:
            result["usage"] = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            }
        return result

    @traceable(name="process-tools", run_type="chain")
    def process_tools(self, messages, response):
        if not response.get("tool_calls"):
            return response["content"]

        current_messages = list(messages)
        tool_calls = response["tool_calls"]

        for _ in range(MAX_TOOL_ITERATIONS):
            assistant_msg = {"role": "assistant", "content": response.get("content", "") or ""}
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}
                    }
                    for tc in tool_calls
                ]
            current_messages.append(assistant_msg)

            for tc in tool_calls:
                func_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}
                func = FUNCTION_MAP.get(func_name)
                if func:
                    try:
                        result = func(**args)
                    except Exception as e:
                        result = f"Error ejecutando {func_name}: {str(e)}"
                else:
                    result = f"Tool '{func_name}' no encontrada"
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": str(result)
                })

            response = self.chat(current_messages, tools=TOOLS)
            tool_calls = response.get("tool_calls", [])

            if not tool_calls:
                break

        return response.get("content", "")

    @traceable(name="generate-response", run_type="llm")
    def generate(self, system_prompt, messages, tools=None):
        full_messages = [{"role": "system", "content": system_prompt}]
        full_messages.extend(messages)

        start = time.time()
        try:
            response = self.chat(full_messages, tools=tools)
        except Exception as e:
            error_msg = str(e)
            if "tool_use_failed" in error_msg or "Failed to call a function" in error_msg:
                response = self.chat(full_messages, tools=None)
            else:
                raise

        elapsed = int((time.time() - start) * 1000)

        content = response.get("content", "")
        tool_calls = response.get("tool_calls", [])

        if tool_calls:
            try:
                content = self.process_tools(full_messages, response)
            except Exception as e:
                content = f"No pude completar la acción solicitada, pero aquí tienes lo que encontré. Error: {e}"

        usage = response.get("usage", {})
        total_tokens = (usage.get("input_tokens", 0) or 0) + (usage.get("output_tokens", 0) or 0)

        run = get_current_run_tree()
        if run:
            try:
                run.add_metadata({
                    "total_tokens": total_tokens,
                    "response_time_ms": elapsed,
                    "tool_calls_count": len(tool_calls),
                })
            except Exception:
                pass

        return content, total_tokens, elapsed


llm_client = LLMClient()
