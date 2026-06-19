# Arquitectura del Agente: Financial-Agent-obj

## Stack tecnológico
- **Lenguaje:** Python 3.12
- **Framework web:** FastAPI + Uvicorn
- **Orquestación del agente:** LangGraph (máquina de estados)
- **LLMs:** Multi-proveedor (Anthropic, Groq, OpenAI) vía `LLMClient`
- **Base de datos:** SQLite
- **Mensajería:** Twilio WhatsApp API
- **Observabilidad:** LangSmith (`@traceable`)
- **Tools:** Decorator-based registry

---

## Estructura del proyecto

```
Financial-Agent-obj/
  main.py                    # Entry point global
  .env                       # Secrets/config
  test.py                    # Tests

  app/                       # Core aplicación (FastAPI + LangGraph)
    main.py                  # FastAPI endpoints
    config.py                # Config variables
    database.py              # SQLite DB layer
    models.py                # Pydantic models
    graph.py                 # LangGraph state machine
    llm_client.py            # Multi-provider LLM client
    whatsapp.py              # Twilio WhatsApp integration
    escalation.py            # Escalation detection
    faq.py                   # FAQ matching
    seed.py                  # Demo data seeder

  tools/                     # Definiciones e implementaciones de tools
    registry.py              # @tool decorator, registro, TOOLS + FUNCTION_MAP
    analyze_document.py      # Analizador CSV/Excel/SQLite
    read_google_sheet.py     # Lector Google Sheets
    write_google_sheet.py    # Escritor Google Sheets
    google_sheets_client.py  # Auth Google API
    google_sheets_table.py   # Operaciones avanzadas Sheets
    list_directory.py        # Listado de directorios
    execute_python.py        # Ejecución Python en sandbox

  prompts/                   # System prompts
    system_prompt.py         # Prompt general
    financial_prompt.py      # Prompt financiero

  utils/
    messages.py              # Truncador de historial
```

---

## Flujo completo de datos

```
Usuario (WhatsApp)
  → POST /webhook/whatsapp (app/main.py:84)
    → procesar_mensaje() (app/graph.py:164)
      → agent_graph.invoke()
        → NODO 1: consultar_llm
            → Carga historial de DB (últimos 20 mensajes)
            → Busca FAQs similares (SequenceMatcher + Jaccard)
            → Construye prompt: system_prompt + financial_prompt + FAQs + historial
            → LLMClient.generate(prompt, tools=TOOLS)
                → LLMClient.chat() → LLM externo
                → Si hay tool_calls → process_tools()
                    → Recupera FUNCTION_MAP[name]
                    → Ejecuta tool con args parseados
                    → Re-chat() con resultado del tool
                    → Hasta MAX_TOOL_ITERATIONS (10) o sin más tool_calls
            → Retorna (respuesta, tokens, tiempo_ms)
        → NODO 2: evaluar_escalado
            → Detección por keywords: frustración, fuera-de-alcance, pide humano
        → NODO 3 (si escalado): ejecutar_escalado
            → Guarda en DB, responde con mensaje de handoff
        → NODO 4: guardar_respuesta
            → Persiste user_message + assistant_message en DB
    → Retorna state["respuesta"]
  → enviar_mensaje_whatsapp() (app/whatsapp.py:20)
    → Extrae URLs mermaid.ink → envía como media
    → Envía imágenes pendientes de _IMAGES_TO_SEND
    → Limpia texto (remove IMAGEN_GENERADA:, IMAGEN_PATH:, URLs)
    → Envía texto vía Twilio API
```

---

## Sistema de Tools

### Registro
Decorador `@tool(name, desc, parameters, required)` en `tools/registry.py`

Cada tool se registra en:
- `_REGISTRY` → lista en formato OpenAI tool
- `_FUNCTION_MAP` → dict name→function

Exportado como `TOOLS` y `FUNCTION_MAP`

### Tools disponibles (14)

| Tool | Descripción |
|------|-------------|
| `list_directory` | Lista archivos en directorio |
| `read_google_sheet` | Lee rango de Google Sheets |
| `write_google_sheet` | Escribe valores a Google Sheets |
| `get_google_sheet_metadata` | Metadatos del spreadsheet |
| `get_google_sheet_names` | Nombres de hojas |
| `detect_google_sheet_used_range` | Rango usado |
| `read_google_sheet_preview` | Primeras N filas |
| `read_google_sheet_all` | Lee toda la hoja (hasta 1000 rows) |
| `search_google_sheet_rows` | Búsqueda por texto en filas |
| `summarize_google_sheet` | Resumen estadístico |
| `execute_python` | Ejecuta Python en sandbox (restricted imports) |
| `analyze_document` | Analiza CSV/Excel/SQLite |
| `search_web` | DuckDuckGo search |
| `generate_mermaid_chart` | Genera diagrama Mermaid → imagen |

### Invocación (`process_tools()` en llm_client.py:197)

1. Recibe `tool_calls` del LLM
2. Itera hasta `MAX_TOOL_ITERATIONS` (10)
3. Por cada tool call: `FUNCTION_MAP[name](**args)` → str(resultado)
4. Appends mensaje assistant con `tool_calls` + mensaje tool con resultado
5. Llama `chat()` de nuevo con mensajes actualizados + tools
6. Break cuando no hay más tool_calls
7. Retorna el último texto generado

### Estado global compartido
`_IMAGES_TO_SEND` es una lista global que acumula imágenes a enviar por WhatsApp.

---

## Gestión de Estado (LangGraph)

### Estado (`AgentState`) - TypedDict

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `messages` | list | Mensajes de la conversación |
| `usuario_id` | str | ID del usuario (teléfono) |
| `usuario_nombre` | str | Nombre del usuario |
| `conversacion_id` | int | ID de conversación en DB |
| `escalar` | bool | ¿Debe escalar a humano? |
| `motivo_escalado` | str | Razón del escalado |
| `respuesta` | str | Texto final de respuesta |
| `tokens_usados` | int | Conteo de tokens |
| `tiempo_ms` | int | Tiempo de respuesta |
| `error` | str | Mensajes de error |

### Grafo de nodos

```
consultar_llm → evaluar_escalado
  → [escalar=True]  → ejecutar_escalado → guardar_respuesta → END
  → [escalar=False] → guardar_respuesta → END
```

---

## Comunicación de respuestas

### Canal primario: Twilio WhatsApp
- Webhook recibe `form-urlencoded` con `Body`, `From`, `ProfileName`
- `enviar_mensaje_whatsapp()`:
  - Extrae URLs mermaid.ink → envía como media messages
  - Vacía `_IMAGES_TO_SEND` (imágenes generadas por tools)
  - Limpia texto: elimina `IMAGEN_GENERADA:`, `IMAGEN_PATH:`, URLs mermaid
  - Colapsa nuevoslines múltiples
  - Envía texto vía Twilio Messages API
- Fallback a stdout si no hay Twilio configurado

### Canal API REST
- `POST /api/chat` → JSON `{"respuesta": string, "imagenes": [urls]}`
- `POST /api/chat/con-documento` → file upload + mensaje → `{"respuesta": string}`
- `POST /webhook/whatsapp/json` → variante JSON del webhook

### Formato de respuesta
El LLM genera texto plano. Las imágenes se envían como media messages separados. El texto se limpia de artefactos internos antes de enviar al usuario.

---

## Gestión de Memoria

### Persistencia (SQLite)
| Tabla | Propósito |
|-------|-----------|
| `tenants` | Entidades de negocio |
| `conversaciones` | Sesiones activas/finalizadas |
| `mensajes` | Mensajes individuales (rol, contenido, tokens, timing) |
| `logs_actividad` | Logs de actividad/error |
| `escalados` | Registros de escalado a humano |
| `faqs` | Entradas FAQ |

### Contexto conversacional
- `MAX_HISTORY = 20` mensajes cargados desde DB
- `trim_messages()` trunca para mantener espacio para system prompts
- FAQs similares se inyectan como contexto adicional en el prompt

### Sistema FAQ
- `buscar_faq_similar(mensaje, umbral=0.3)` en `faq.py`
- Usa `SequenceMatcher` ratio + Jaccard similarity
- Retorna hasta 3 FAQs con mejor match

---

## Sistema de Escalado

### Detectores
1. **Frustración** - Keywords: queja, molesto, insatisfecho, no sirve, etc.
2. **Fuera de alcance** - Keywords: asesoria legal, declaracion de renta, visa, etc.
3. **Solicitud de humano** - Regex patterns para pedir agente humano

### Evaluación combinada
`evaluar_escalado(texto, faq_match, tiene_info)` en `escalation.py:59`
- Activa escalado si: frustración detectada, fuera de alcance, pide humano, o no hay info disponible

---

## Configuración clave

| Variable (app/config.py) | Default | Impacto |
|--------------------------|---------|---------|
| `LLM_PROVIDER` | `anthropic` | Proveedor LLM activo |
| `DEFAULT_MODEL` | `claude-sonnet-4-20250514` | Modelo principal |
| `FALLBACK_MODEL` | `llama-3.3-70b-versatile` | Fallback si falla primario |
| `MAX_HISTORY` | `20` | Profundidad del contexto conversacional |
| `MAX_TOOL_ITERATIONS` | `10` | Límite de loop de tool calls |

Variables de `.env` sobrescriben defaults.

---

## LLM Client (Multi-Provider)

`LLMClient` en `app/llm_client.py`

### Inicialización
1. **Primary:** Anthropic (si `ANTHROPIC_API_KEY` set)
2. **Fallback:** Groq (si `GROQ_API_KEY` set)
3. **Last resort:** OpenAI (si `OPENAI_API_KEY` set)
4. Provider elegido por `LLM_PROVIDER` env var

### Métodos core
- `chat(messages, tools, max_tokens)` → rutea a provider específico
- `generate(system_prompt, messages, tools)` → entry point con tracing
- `process_tools(messages, response)` → loop de ejecución de tools

### Implementaciones por provider
- **Anthropic** (`_chat_anthropic`): Mapeo de roles, conversión tool format, parsing `tool_use`
- **OpenAI** (`_chat_openai`): Formato nativo, parsing `tool_calls`
- **Groq** (`_chat_groq`): OpenAI-compatible con retry (3 intentos, exponential backoff para 429)

---

## Puntos clave de ineficiencia y mejora potencial

1. **Tool loop secuencial:** `process_tools()` ejecuta tools uno por uno, cada uno requiere un round-trip al LLM. Sin paralelización ni caching de resultados.
2. **Sin verificación de tool outputs:** El resultado del tool se pasa directo al LLM sin validación de calidad/errores.
3. **Contexto plano:** Todo el historial + FAQs + prompts se concatena como texto. Sin RAG, sin embeddings, sin ranking semántico.
4. **Sin caché de tools:** Si dos usuarios preguntan lo mismo, `search_web` o `read_google_sheet_all` se ejecutan de nuevo.
5. **FAQs por similitud textual:** SequenceMatcher + Jaccard, sin embeddings.
6. **MAX_TOOL_ITERATIONS fijo:** Siempre 10, sin early stopping dinámico.
7. **Sin streaming:** La respuesta completa se genera antes de enviar.
8. **Tokens no optimizados:** Los `TOOLS` completos (14 tools con schemas grandes) se envían en cada llamada al LLM, incluso cuando solo 2-3 son relevantes.
9. **Sin rate limiting interno:** Solo hay retry en Groq por 429, no hay control de concurrencia.
10. **Imágenes como side-channel:** `_IMAGES_TO_SEND` es un global mutable que podría tener race conditions.
