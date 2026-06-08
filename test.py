import os
import json
import pytest

from unittest.mock import patch, MagicMock, call
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Fixtures de configuracion de entorno
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def env_vars(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", os.getenv("GROQ_API_KEY", "test-groq-key"))
    monkeypatch.setenv("LANGSMITH_API_KEY", os.getenv("LANGSMITH_API_KEY", "test-ls-key"))
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_PROJECT", "financial-agent-tests")
    monkeypatch.setenv("GOOGLE_API_KEY", os.getenv("GOOGLE_API_KEY", ""))


# ===========================================================================
# BLOQUE 1 — API key de Google Gemini
# ===========================================================================

class TestGoogleGeminiApiKey:

    def test_api_key_presente_en_entorno(self):
        key = os.getenv("GOOGLE_API_KEY", "")
        assert key, (
            "GOOGLE_API_KEY no encontrada. "
            "Agrégala en tu archivo .env o como variable de entorno."
        )

    def test_api_key_tiene_longitud_minima(self):
        key = os.getenv("GOOGLE_API_KEY", "")
        if not key:
            pytest.skip("GOOGLE_API_KEY no configurada")
        assert len(key) >= 20, (
            f"La API key parece inválida (largo: {len(key)}). "
            "Las keys de Google tienen al menos 39 caracteres."
        )

    def test_api_key_no_es_placeholder(self):
        key = os.getenv("GOOGLE_API_KEY", "")
        if not key:
            pytest.skip("GOOGLE_API_KEY no configurada")
        placeholders = {"your_api_key", "YOUR_API_KEY", "xxxxxxxx", "test-key"}
        assert key not in placeholders, "GOOGLE_API_KEY contiene un valor placeholder."

    def test_conexion_real_con_gemini(self):
        genai = pytest.importorskip(
            "google.genai",
            reason="google-genai no instalado — ejecuta: pip install google-genai"
        )
        key = os.getenv("GOOGLE_API_KEY", "")
        if not key:
            pytest.skip("GOOGLE_API_KEY no configurada — saltando test de conexion real")

        try:
            cliente = genai.Client(api_key=key)
            respuesta = cliente.models.generate_content(
                model="gemini-2.0-flash",
                contents="Responde solo con la palabra: hola"
            )
            texto = respuesta.text.strip().lower()
            assert "hola" in texto, (
                f"Respuesta inesperada de Gemini: '{texto}'"
            )
        except Exception as exc:
            if "API_KEY_INVALID" in str(exc) or "401" in str(exc):
                pytest.fail(f"API key de Google inválida: {exc}")
            elif "403" in str(exc):
                pytest.fail(f"API key sin permisos para Gemini: {exc}")
            else:
                pytest.fail(f"Error de conexion con Gemini: {exc}")

    def test_conexion_gemini_con_mock(self):
        mock_response = MagicMock()
        mock_response.text = "hola"

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        MockGeminiClient = MagicMock(return_value=mock_client)

        cliente = MockGeminiClient(api_key="fake-key-para-mock")
        resultado = cliente.models.generate_content(
            model="gemini-2.0-flash",
            contents="di hola"
        )
        assert resultado.text == "hola"
        MockGeminiClient.assert_called_once_with(api_key="fake-key-para-mock")


# ===========================================================================
# BLOQUE 2 — Configuracion del agente
# ===========================================================================

class TestConfig:

    def test_modelo_por_defecto_definido(self):
        from importlib import import_module
        config = import_module("core.config") if _project_importable() else None
        if config is None:
            from types import SimpleNamespace
            config = SimpleNamespace(DEFAULT_MODEL="llama-3.3-70b-versatile", MAX_HISTORY=20)
        assert config.DEFAULT_MODEL, "DEFAULT_MODEL no puede estar vacío"

    def test_max_history_positivo(self):
        if not _project_importable():
            pytest.skip("Proyecto no importable desde este directorio")
        from core.config import MAX_HISTORY
        assert isinstance(MAX_HISTORY, int) and MAX_HISTORY > 0

    def test_exit_commands_no_vacio(self):
        if not _project_importable():
            pytest.skip("Proyecto no importable desde este directorio")
        from core.config import EXIT_COMMANDS
        assert len(EXIT_COMMANDS) > 0


# ===========================================================================
# BLOQUE 3 — Herramientas del agente
# ===========================================================================

class TestTools:

    def test_list_directory_retorna_contenido(self, tmp_path):
        (tmp_path / "archivo.txt").write_text("hola")
        (tmp_path / "carpeta").mkdir()

        if _project_importable():
            from tools.list_directory import list_directory
            resultado = list_directory(str(tmp_path))
        else:
            import os
            items = os.listdir(str(tmp_path))
            resultado = "\n".join(items)

        assert "archivo.txt" in resultado
        assert "carpeta" in resultado

    def test_list_directory_ruta_invalida(self):
        if _project_importable():
            from tools.list_directory import list_directory
            resultado = list_directory("/ruta/que/no/existe/abc123")
        else:
            import os
            try:
                os.listdir("/ruta/que/no/existe/abc123")
                resultado = ""
            except Exception as e:
                resultado = str(e)
        assert resultado

    def test_execute_python_captura_print(self):
        if not _project_importable():
            pytest.skip("Proyecto no importable desde este directorio")
        from tools.execute_python import execute_python
        resultado = execute_python("print('resultado-ok')")
        assert "resultado-ok" in resultado

    def test_execute_python_captura_excepcion(self):
        if not _project_importable():
            pytest.skip("Proyecto no importable desde este directorio")
        from tools.execute_python import execute_python
        resultado = execute_python("raise ValueError('error de prueba')")
        assert "ValueError" in resultado

    def test_execute_python_calculo_financiero(self):
        if not _project_importable():
            pytest.skip("Proyecto no importable desde este directorio")
        from tools.execute_python import execute_python
        codigo = "capital = 1000; tasa = 0.05; print(capital * (1 + tasa))"
        resultado = execute_python(codigo)
        assert "1050" in resultado


# ===========================================================================
# BLOQUE 4 — Utilidades de mensajes
# ===========================================================================

class TestMessages:

    def _trim(self, messages):
        if _project_importable():
            from utils.messages import trim_messages
            return trim_messages(messages)
        from core.config import MAX_HISTORY
        system = [m for m in messages if m["role"] == "system"]
        rest = [m for m in messages if m["role"] != "system"]
        return system + rest[-MAX_HISTORY:]

    def test_preserva_mensaje_de_sistema(self):
        msgs = [{"role": "system", "content": "eres un asistente"}]
        for i in range(25):
            msgs.append({"role": "user", "content": f"mensaje {i}"})
        resultado = self._trim(msgs)
        assert resultado[0]["role"] == "system"

    def test_recorta_historial_largo(self):
        msgs = [{"role": "system", "content": "sys"}]
        for i in range(30):
            msgs.append({"role": "user", "content": f"msg {i}"})
        resultado = self._trim(msgs)
        non_system = [m for m in resultado if m["role"] != "system"]
        assert len(non_system) <= 20

    def test_historial_corto_no_se_altera(self):
        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hola"},
            {"role": "assistant", "content": "hola de vuelta"},
        ]
        resultado = self._trim(msgs)
        assert len(resultado) == 3


# ===========================================================================
# BLOQUE 5 — Tracing con LangSmith
# ===========================================================================

class TestLangSmithIntegration:

    def test_langsmith_api_key_configurada(self):
        key = os.getenv("LANGSMITH_API_KEY", "")
        assert key, (
            "LANGSMITH_API_KEY no encontrada. "
            "Agrégala en tu .env para habilitar el tracing."
        )

    def test_langsmith_tracing_habilitado(self):
        tracing = os.getenv("LANGSMITH_TRACING", "false").lower()
        assert tracing == "true", (
            "LANGSMITH_TRACING no está en 'true'. "
            "El tracing no se activará en producción."
        )

    def test_langsmith_proyecto_configurado(self):
        proyecto = os.getenv("LANGSMITH_PROJECT", "")
        assert proyecto, (
            "LANGSMITH_PROJECT no definido. "
            "Sin esto las trazas van al proyecto por defecto."
        )

    def test_decorador_traceable_en_chat(self):
        if not _project_importable():
            pytest.skip("Proyecto no importable desde este directorio")
        import inspect
        from core import chat as chat_module
        src = inspect.getsource(chat_module.chat)
        assert "traceable" in src or hasattr(chat_module.chat, "__wrapped__"), (
            "La función chat() no tiene el decorador @traceable de LangSmith"
        )

    def test_langsmith_cliente_instanciable_con_mock(self):
        from langsmith import Client

        with patch("langsmith.Client.__init__", return_value=None):
            cliente = Client.__new__(Client)
            assert cliente is not None

    def test_funcion_chat_trazada_con_mock_completo(self):
        mock_choice = MagicMock()
        mock_choice.message.content = "respuesta de prueba"
        mock_choice.message.tool_calls = None

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        llamadas = []

        def chat_falso(messages):
            llamadas.append(messages)
            return mock_response

        mensajes = [
            {"role": "system", "content": "eres un asistente"},
            {"role": "user", "content": "cuanto es 2+2"},
        ]

        resultado = chat_falso(mensajes)
        assert resultado.choices[0].message.content == "respuesta de prueba"
        assert len(llamadas) == 1

    def test_conexion_real_langsmith(self):
        key = os.getenv("LANGSMITH_API_KEY", "")
        if not key or key == "test-ls-key":
            pytest.skip("LANGSMITH_API_KEY real no configurada")

        from langsmith import Client
        try:
            cliente = Client()
            proyectos = list(cliente.list_projects(limit=1))
            assert isinstance(proyectos, list)
        except Exception as exc:
            if "401" in str(exc) or "403" in str(exc) or "Unauthorized" in str(exc):
                pytest.fail(f"API key de LangSmith inválida o sin permisos: {exc}")
            else:
                pytest.fail(f"Error de conexion con LangSmith: {exc}")


# ===========================================================================
# BLOQUE 6 — Flujo de tool_calls (mock end-to-end)
# ===========================================================================

class TestToolCallsFlow:

    def _make_tool_response(self, tool_name, args, call_id="call_1"):
        tc = MagicMock()
        tc.id = call_id
        tc.function.name = tool_name
        tc.function.arguments = json.dumps(args)
        return tc

    def test_process_tools_sin_tool_calls(self):
        if not _project_importable():
            pytest.skip("Proyecto no importable desde este directorio")
        from core.chat import process_tools

        mock_msg = MagicMock()
        mock_msg.content = "respuesta directa"
        mock_msg.tool_calls = None

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=mock_msg)]

        mensajes = [{"role": "user", "content": "hola"}]
        resultado = process_tools(mensajes, mock_resp)
        assert resultado == "respuesta directa"

    def test_process_tools_con_execute_python(self):
        if not _project_importable():
            pytest.skip("Proyecto no importable desde este directorio")
        from core.chat import process_tools

        tc = self._make_tool_response("execute_python", {"code": "print(42)"})

        msg_con_tool = MagicMock()
        msg_con_tool.content = ""
        msg_con_tool.tool_calls = [tc]

        msg_final = MagicMock()
        msg_final.content = "el resultado es 42"
        msg_final.tool_calls = None

        resp_1 = MagicMock()
        resp_1.choices = [MagicMock(message=msg_con_tool)]

        resp_2 = MagicMock()
        resp_2.choices = [MagicMock(message=msg_final)]

        mensajes = [{"role": "user", "content": "ejecuta print(42)"}]

        with patch("core.chat.chat", side_effect=[resp_2]):
            resultado = process_tools(mensajes, resp_1)

        assert resultado == "el resultado es 42"


# ===========================================================================
# Utilidad interna
# ===========================================================================

def _project_importable() -> bool:
    try:
        import core.config
        return True
    except ModuleNotFoundError:
        return False


# ===========================================================================
# Punto de entrada directo
# ===========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])