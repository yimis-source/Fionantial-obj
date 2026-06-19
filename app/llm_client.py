import time
import json
import threading
from typing import Optional

from app.config import (
    ANTHROPIC_API_KEY, GROQ_API_KEY, OPENAI_API_KEY,
    LLM_PROVIDER, DEFAULT_MODEL, FALLBACK_MODEL,
    MAX_TOOL_ITERATIONS, PROVIDER_TIMEOUT,
    CIRCUIT_BREAKER_THRESHOLD, CIRCUIT_BREAKER_RESET_SECONDS,
)
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
from tools.registry import TOOLS, FUNCTION_MAP, _track_metrics


_INTENT_TOOL_MAP = {
    "saludo": [],
    "pregunta_simple": [],
    "analisis_datos": ["read_google_sheet", "search_google_sheet_rows", "analyze_document", "execute_python"],
    "busqueda_web": ["search_web"],
    "grafico": ["generate_mermaid_chart"],
    "calculo_financiero": ["calculate_financial", "format_currency_cop"],
    "sheets": ["read_google_sheet", "write_google_sheet", "search_google_sheet_rows"],
    "codigo": ["execute_python"],
    "fecha": ["get_current_datetime"],
    "documento": ["analyze_document"],
    "escalar": ["request_escalation"],
    "general": None,
}

_INTENT_KEYWORDS = {
    "saludo": ["hola", "buenos días", "buenas tardes", "buenas noches", "qué tal", "hey", "saludos"],
    "pregunta_simple": ["horario", "horarios", "dirección", "teléfono", "contacto", "faq"],
    "busqueda_web": ["buscar", "internet", "googlea", "noticias", "TRM", "dólar hoy", "clima", "últimas"],
    "grafico": ["gráfico", "graficar", "grafica", "diagrama", "mermaid", "pastel", "barras", "chart", "/graficar"],
    "calculo_financiero": ["interés", "interes", "amortización", "amortizacion", "cuota", "préstamo", "prestamo"],
    "sheets": ["pedido", "orden", "pedido id", "id pedido", "cliente", "sheet", "hoja", "excel", "google sheet", "spreadsheet", "tabla", "venta", "buscar", "consultar", "producto", "zona", "país"],
    "codigo": ["ejecuta", "ejecutar", "python", "código", "codigo", "calcula"],
    "fecha": ["fecha", "hora", "qué día", "qué hora"],
    "documento": ["analiza", "analizar", "archivo", "csv", "documento"],
    "escalar": ["humano", "asesor", "persona", "supervisor", "queja", "molesto"],
}


def clasificar_intencion(mensaje: str) -> str:
    msg = mensaje.lower().strip()
    for intent, keywords in _INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in msg:
                return intent
    return "general"


def _filtrar_tools_por_intencion(intencion: str) -> list:
    names = _INTENT_TOOL_MAP.get(intencion)
    if names is None:
        return TOOLS
    if not names:
        return []
    return [t for t in TOOLS if t["function"]["name"] in names]


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


class CircuitBreaker:
    def __init__(self, name: str, threshold: int, reset_seconds: int):
        self.name = name
        self.threshold = threshold
        self.reset_seconds = reset_seconds
        self.failures = 0
        self.last_failure_time = 0.0
        self.state = "closed"
        self._lock = threading.Lock()

    def record_success(self):
        with self._lock:
            self.failures = 0
            self.state = "closed"

    def record_failure(self):
        with self._lock:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= self.threshold:
                self.state = "open"

    def is_open(self) -> bool:
        with self._lock:
            if self.state == "open":
                if time.time() - self.last_failure_time > self.reset_seconds:
                    self.state = "half-open"
                    return False
                return True
            return False


class LLMClient:
    def __init__(self):
        self.provider = LLM_PROVIDER
        self.model = DEFAULT_MODEL
        self.fallback_model = FALLBACK_MODEL
        self.client = None
        self.fallback_client = None
        self.circuit_breaker = CircuitBreaker(
            "primary_provider", CIRCUIT_BREAKER_THRESHOLD, CIRCUIT_BREAKER_RESET_SECONDS
        )
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
    def chat(self, messages, tools=None, max_tokens=512):
        if self.circuit_breaker.is_open():
            if self.fallback_client:
                return self._chat_groq(messages, tools, max_tokens)
            raise RuntimeError("Primary provider is down (circuit breaker) and no fallback available")

        if self.provider == "anthropic" and self.client:
            try:
                result = self._chat_anthropic(messages, tools, max_tokens)
                self.circuit_breaker.record_success()
                return result
            except Exception as e:
                self.circuit_breaker.record_failure()
                if self.fallback_client:
                    return self._chat_groq(messages, tools, max_tokens)
                raise
        elif self.client and self.provider == "openai":
            return self._chat_openai(messages, tools, max_tokens)
        elif self.fallback_client:
            return self._chat_groq(messages, tools, max_tokens)
        raise RuntimeError("No LLM client available")

    def _chat_anthropic(self, messages, tools=None, max_tokens=512):
        system = ""
        anthropic_messages = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            elif m["role"] == "user":
                anthropic_messages.append({"role": "user", "content": m["content"]})
            elif m["role"] == "assistant":
                content = m.get("content", "") or ""
                tc = m.get("tool_calls")
                if tc:
                    content_blocks = [{"type": "text", "text": content}] if content else []
                    for t in tc:
                        try:
                            inp = json.loads(t["function"]["arguments"])
                        except json.JSONDecodeError:
                            inp = {}
                        content_blocks.append({
                            "type": "tool_use",
                            "id": t["id"],
                            "name": t["function"]["name"],
                            "input": inp,
                        })
                    anthropic_messages.append({"role": "assistant", "content": content_blocks})
                elif content:
                    anthropic_messages.append({"role": "assistant", "content": content})
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

    def _chat_openai(self, messages, tools=None, max_tokens=512):
        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "timeout": PROVIDER_TIMEOUT,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        response = self.client.chat.completions.create(**kwargs)
        result = self._parse_openai_response(response)
        usage = result.get("usage", {})
        _update_run_tokens(usage.get("input_tokens", 0), usage.get("output_tokens", 0))
        return result

    def _chat_groq(self, messages, tools=None, max_tokens=512):
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
                        time.sleep(2 ** (attempt + 1))
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

    def _parse_text_function_calls(self, text: str) -> list[dict]:
        import re
        pattern = r'<function=(\w+)>(.*?)</function>'
        calls = []
        for match in re.finditer(pattern, text, re.DOTALL):
            name = match.group(1)
            args_raw = match.group(2).strip()
            try:
                args = json.loads(args_raw)
            except json.JSONDecodeError:
                args = {"raw": args_raw}
            calls.append({
                "id": f"txt_{name}_{hash(args_raw) % 100000}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)}
            })
        return calls

    @traceable(name="process-tools", run_type="chain")
    def process_tools(self, messages, response, current_tools):
        tool_calls = response.get("tool_calls", [])

        if not tool_calls:
            content = response.get("content", "")
            parsed = self._parse_text_function_calls(content)
            if parsed:
                tool_calls = parsed
                response["tool_calls"] = parsed

        if not tool_calls:
            return response.get("content", "")

        current_messages = list(messages)

        for iteration in range(MAX_TOOL_ITERATIONS):
            content_text = response.get("content", "") or ""
            assistant_msg = {"role": "assistant", "content": content_text}
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
                start_ts = time.time()
                if func:
                    try:
                        result = func(**args)
                        success = True
                    except Exception as e:
                        result = f"Error ejecutando {func_name}: {str(e)}"
                        success = False
                else:
                    result = f"Tool '{func_name}' no encontrada"
                    success = False
                duration_ms = int((time.time() - start_ts) * 1000)
                _track_metrics(func_name, 0, len(str(result)), duration_ms, success)
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": str(result)
                })

            response = self.chat(current_messages, tools=current_tools)
            tool_calls = response.get("tool_calls", [])

            if not tool_calls:
                parsed = self._parse_text_function_calls(response.get("content", ""))
                if parsed:
                    tool_calls = parsed
                    response["tool_calls"] = parsed
                else:
                    break

        return response.get("content", "")

    @traceable(name="generate-response", run_type="llm")
    def generate(self, system_prompt, messages, tools=None, intencion="general"):
        full_messages = [{"role": "system", "content": system_prompt}]
        full_messages.extend(messages)

        filtered_tools = _filtrar_tools_por_intencion(intencion) if tools else None

        start = time.time()
        try:
            response = self.chat(full_messages, tools=filtered_tools)
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
                content = self.process_tools(full_messages, response, filtered_tools)
            except Exception as e:
                content = f"No pude completar la acción solicitada. Error: {e}"

        usage = response.get("usage", {})
        total_tokens = (usage.get("input_tokens", 0) or 0) + (usage.get("output_tokens", 0) or 0)

        run = get_current_run_tree()
        if run:
            try:
                run.add_metadata({
                    "total_tokens": total_tokens,
                    "response_time_ms": elapsed,
                    "tool_calls_count": len(tool_calls),
                    "intencion": intencion,
                    "filtered_tools": len(filtered_tools) if filtered_tools else 0,
                })
            except Exception:
                pass

        return content, total_tokens, elapsed


llm_client = LLMClient()
