from typing import TypedDict, Literal
import json

from langgraph.graph import StateGraph, END
from langsmith import traceable

from app.config import MAX_HISTORY, SUMMARY_TRIGGER, MAX_ACTIVE_MESSAGES
from app.database import (
    crear_conversacion, guardar_mensaje, obtener_historial,
    guardar_log, crear_escalado, obtener_perfil_usuario,
    guardar_resumen_conversacion, obtener_resumen_conversacion,
)
from app.faq import buscar_faq_similar, cargar_faqs
from app.llm_client import llm_client, clasificar_intencion
from app.escalation import TOOL_ESCALATION_NAME, extraer_motivo_escalado
from prompts.system_prompt import SYSTEM_PROMPT
from prompts.financial_prompt import FINANCIAL_SYSTEM_PROMPT
from tools.registry import TOOLS, get_tool_metrics

TOOL_ESCALATION_RESULT_PREFIX = "ESCALAR_A_HUMANO:"


class AgentState(TypedDict):
    messages: list
    usuario_id: str
    usuario_nombre: str
    conversacion_id: int
    intencion: str
    escalar: bool
    motivo_escalado: str
    respuesta: str
    tokens_usados: int
    tiempo_ms: int
    error: str
    imagenes_pendientes: list


def _construir_prompt_con_contexto(historial: list, mensaje_actual: str, perfil: dict | None = None) -> str:
    faqs = buscar_faq_similar(mensaje_actual)
    contexto_piezas = []

    if perfil:
        pref = perfil.get("preferencias", {})
        if pref:
            pref_lineas = "\n".join(f"• {k}: {v}" for k, v in pref.items())
            contexto_piezas.append(f"PREFERENCIAS DEL USUARIO:\n{pref_lineas}")

    if faqs:
        faq = faqs[0]
        contexto_piezas.append(
            f"PREGUNTA FRECUENTE RELACIONADA:\nP: {faq['pregunta']}\nR: {faq['respuesta']}"
        )

    prompt_base = SYSTEM_PROMPT + "\n\n" + FINANCIAL_SYSTEM_PROMPT
    if contexto_piezas:
        prompt_base += "\n\n" + "\n\n".join(contexto_piezas)

    return prompt_base


@traceable(name="clasificar_intencion", run_type="chain")
def clasificar_intencion_nodo(state: AgentState) -> AgentState:
    mensaje = state["messages"][-1]["content"] if state["messages"] else ""
    state["intencion"] = clasificar_intencion(mensaje)
    return state


@traceable(name="resumir_historial", run_type="chain")
def resumir_historial_nodo(state: AgentState) -> AgentState:
    historial = obtener_historial(state["conversacion_id"], MAX_HISTORY)
    resumen_existente = obtener_resumen_conversacion(state["conversacion_id"])

    if len(historial) > SUMMARY_TRIGGER:
        ultimos = historial[-MAX_ACTIVE_MESSAGES:]
        viejos = historial[:-MAX_ACTIVE_MESSAGES]

        if viejos and not resumen_existente:
            texto_viejo = "\n".join(
                f"{'Usuario' if m['rol'] == 'usuario' else 'Asistente'}: {m['contenido'][:300]}"
                for m in viejos
            )
            prompt_resumen = (
                "Resume en 2-3 oraciones lo que se ha hablado en esta conversación, "
                "enfocándote en datos financieros, preferencias del usuario, y decisiones tomadas:\n\n"
            )
            try:
                resumen, _, _ = llm_client.generate(
                    prompt_resumen,
                    [{"role": "user", "content": texto_viejo}],
                    tools=None,
                )
                guardar_resumen_conversacion(state["conversacion_id"], resumen.strip())
            except Exception:
                resumen_existente = None

    return state


@traceable(name="consultar_llm", run_type="chain")
def consultar_llm(state: AgentState) -> AgentState:
    mensaje_usuario = state["messages"][-1]["content"] if state["messages"] else ""
    historial = obtener_historial(state["conversacion_id"], MAX_HISTORY)
    resumen = obtener_resumen_conversacion(state["conversacion_id"])
    perfil = obtener_perfil_usuario(state["usuario_id"])

    messages_context = []

    if resumen:
        messages_context.append({
            "role": "system",
            "content": f"[RESUMEN DE LA CONVERSACIÓN ANTERIOR]: {resumen}"
        })

    for msg in historial[-MAX_ACTIVE_MESSAGES:]:
        messages_context.append({
            "role": "user" if msg["rol"] == "usuario" else "assistant",
            "content": msg["contenido"]
        })
    messages_context.append({"role": "user", "content": mensaje_usuario})

    prompt = _construir_prompt_con_contexto(historial, mensaje_usuario, perfil)

    try:
        contenido, tokens, tiempo = llm_client.generate(
            prompt, messages_context, tools=TOOLS, intencion=state.get("intencion", "general")
        )
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
    respuesta = state.get("respuesta", "")

    if respuesta.startswith(TOOL_ESCALATION_RESULT_PREFIX):
        motivo = respuesta[len(TOOL_ESCALATION_RESULT_PREFIX):]
        state["escalar"] = True
        state["motivo_escalado"] = motivo
    elif state.get("error"):
        state["escalar"] = True
        state["motivo_escalado"] = f"Error en el sistema: {state['error']}"
    else:
        state["escalar"] = False
        state["motivo_escalado"] = ""

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

    workflow.add_node("clasificar_intencion", clasificar_intencion_nodo)
    workflow.add_node("resumir_historial", resumir_historial_nodo)
    workflow.add_node("consultar_llm", consultar_llm)
    workflow.add_node("evaluar_escalado", evaluar_escalado_nodo)
    workflow.add_node("ejecutar_escalado", ejecutar_escalado)
    workflow.add_node("guardar_respuesta", guardar_respuesta)

    workflow.set_entry_point("clasificar_intencion")
    workflow.add_edge("clasificar_intencion", "resumir_historial")
    workflow.add_edge("resumir_historial", "consultar_llm")
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
            "intencion": "",
            "escalar": False,
            "motivo_escalado": "",
            "respuesta": "",
            "tokens_usados": 0,
            "tiempo_ms": 0,
            "error": "",
            "imagenes_pendientes": [],
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
