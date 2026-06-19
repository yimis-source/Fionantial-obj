from typing import TypedDict, Literal

from langgraph.graph import StateGraph, END
from langsmith import traceable
from langsmith.run_trees import RunTree

from app.config import MAX_HISTORY
from app.database import (
    crear_conversacion, guardar_mensaje, obtener_historial,
    guardar_log, crear_escalado
)
from app.faq import buscar_faq_similar, cargar_faqs
from app.escalation import evaluar_escalado
from app.llm_client import llm_client
from prompts.system_prompt import SYSTEM_PROMPT
from prompts.financial_prompt import FINANCIAL_SYSTEM_PROMPT
from tools.registry import TOOLS


class AgentState(TypedDict):
    messages: list
    usuario_id: str
    usuario_nombre: str
    conversacion_id: int
    escalar: bool
    motivo_escalado: str
    respuesta: str
    tokens_usados: int
    tiempo_ms: int
    error: str


def _construir_prompt_con_contexto(historial: list, mensaje_actual: str) -> str:
    faqs = buscar_faq_similar(mensaje_actual)
    contexto_extra = ""

    if faqs:
        contexto_extra = "\n\nPREGUNTAS FRECUENTES RELACIONADAS (úsalas como referencia si aplican):\n"
        for i, faq in enumerate(faqs[:3], 1):
            contexto_extra += f"{i}. P: {faq['pregunta']}\n   R: {faq['respuesta']}\n"

    prompt_base = SYSTEM_PROMPT + "\n\n" + FINANCIAL_SYSTEM_PROMPT
    if contexto_extra:
        prompt_base += contexto_extra

    return prompt_base


@traceable(name="consultar_llm", run_type="chain")
def consultar_llm(state: AgentState) -> AgentState:
    mensaje_usuario = state["messages"][-1]["content"] if state["messages"] else ""
    historial = obtener_historial(state["conversacion_id"], MAX_HISTORY)

    messages_context = []
    for msg in historial:
        messages_context.append({
            "role": "user" if msg["rol"] == "usuario" else "assistant",
            "content": msg["contenido"]
        })
    messages_context.append({"role": "user", "content": mensaje_usuario})

    prompt = _construir_prompt_con_contexto(historial, mensaje_usuario)

    try:
        contenido, tokens, tiempo = llm_client.generate(prompt, messages_context, tools=TOOLS)
        state["respuesta"] = contenido
        state["tokens_usados"] = state.get("tokens_usados", 0) + tokens
        state["tiempo_ms"] = state.get("tiempo_ms", 0) + tiempo
    except Exception as e:
        state["error"] = str(e)
        state["respuesta"] = (
            "Lo siento, tuve un problema al procesar tu consulta. "
            "Un asesor te contactará pronto."
        )
        guardar_log(state["conversacion_id"], "llm_error", str(e), "error")

    return state


@traceable(name="evaluar_escalado", run_type="chain")
def evaluar_escalado_nodo(state: AgentState) -> AgentState:
    mensaje = state["messages"][-1]["content"] if state["messages"] else ""

    debe_escalar, motivo = evaluar_escalado(mensaje)

    if not debe_escalar and state.get("error"):
        debe_escalar = True
        motivo = f"Error en el sistema: {state['error']}"

    state["escalar"] = debe_escalar
    state["motivo_escalado"] = motivo
    return state


@traceable(name="ejecutar_escalado", run_type="chain")
def ejecutar_escalado(state: AgentState) -> AgentState:
    historial = obtener_historial(state["conversacion_id"], 10)
    resumen = "\n".join([f"{m['rol']}: {m['contenido'][:200]}" for m in historial[-5:]])

    crear_escalado(
        conversacion_id=state["conversacion_id"],
        usuario_id=state["usuario_id"],
        motivo=state["motivo_escalado"],
        resumen=resumen,
        historial=str(historial),
        usuario_nombre=state["usuario_nombre"],
        usuario_telefono=state["usuario_id"],
    )

    state["respuesta"] = (
        "He transferido tu caso a un asesor humano que te atenderá en breve. "
        "Gracias por tu paciencia."
    )
    guardar_log(state["conversacion_id"], "escalado", state["motivo_escalado"])
    return state


@traceable(name="guardar_respuesta", run_type="chain")
def guardar_respuesta(state: AgentState) -> AgentState:
    guardar_mensaje(
        state["conversacion_id"],
        "usuario",
        state["messages"][-1]["content"],
    )
    guardar_mensaje(
        state["conversacion_id"],
        "asistente",
        state["respuesta"],
        tokens=state.get("tokens_usados", 0),
        tiempo_ms=state.get("tiempo_ms", 0),
    )
    return state


def decidir_escalado(state: AgentState) -> Literal["ejecutar_escalado", "guardar_respuesta"]:
    if state["escalar"]:
        return "ejecutar_escalado"
    return "guardar_respuesta"


def construir_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("consultar_llm", consultar_llm)
    workflow.add_node("evaluar_escalado", evaluar_escalado_nodo)
    workflow.add_node("ejecutar_escalado", ejecutar_escalado)
    workflow.add_node("guardar_respuesta", guardar_respuesta)

    workflow.set_entry_point("consultar_llm")
    workflow.add_edge("consultar_llm", "evaluar_escalado")
    workflow.add_conditional_edges(
        "evaluar_escalado",
        decidir_escalado,
    )
    workflow.add_edge("ejecutar_escalado", "guardar_respuesta")
    workflow.add_edge("guardar_respuesta", END)

    return workflow.compile()


agent_graph = construir_graph()


@traceable(name="procesar_mensaje_whatsapp", run_type="chain")
def procesar_mensaje(usuario_id: str, mensaje: str, usuario_nombre: str = "") -> str:
    conversacion_id = None
    try:
        conversacion_id = crear_conversacion(usuario_id, usuario_nombre)
        guardar_log(conversacion_id, "mensaje_recibido", mensaje[:200])

        initial_state: AgentState = {
            "messages": [{"role": "user", "content": mensaje}],
            "usuario_id": usuario_id,
            "usuario_nombre": usuario_nombre,
            "conversacion_id": conversacion_id,
            "escalar": False,
            "motivo_escalado": "",
            "respuesta": "",
            "tokens_usados": 0,
            "tiempo_ms": 0,
            "error": "",
        }

        result = agent_graph.invoke(initial_state)
        return result.get("respuesta", "Lo siento, no pude procesar tu mensaje.")

    except Exception as e:
        try:
            cid = conversacion_id if conversacion_id else 1
            guardar_log(cid, "error_general", str(e), "error")
        except Exception:
            pass
        return (
            "Lo siento, ocurrió un error inesperado. Ya notificamos a nuestro equipo. "
            "Por favor, intenta de nuevo en minutos."
        )
