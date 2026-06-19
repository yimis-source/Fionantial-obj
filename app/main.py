import os
import sys
import tempfile
import time
import threading
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from contextlib import asynccontextmanager

from app.config import (
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER,
    ANTHROPIC_API_KEY, GROQ_API_KEY, RATE_LIMIT_MAX_PER_MINUTE,
)
from app.database import init_db, guardar_log
from app.graph import procesar_mensaje
from app.whatsapp import enviar_mensaje_whatsapp, generar_respuesta_twiml, get_twilio_client
from app.seed import seed_demo_data
from tools.registry import get_tool_metrics


class RateLimiter:
    def __init__(self, max_per_minute: int = 20):
        self.max_per_minute = max_per_minute
        self._buckets: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check(self, user_id: str) -> bool:
        now = time.time()
        with self._lock:
            timestamps = self._buckets.get(user_id, [])
            timestamps = [t for t in timestamps if now - t < 60]
            if len(timestamps) >= self.max_per_minute:
                return False
            timestamps.append(now)
            self._buckets[user_id] = timestamps
            return True


rate_limiter = RateLimiter(RATE_LIMIT_MAX_PER_MINUTE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_demo_data()
    yield


app = FastAPI(
    title="Financial Agent API",
    description="Asistente financiero inteligente para PYME colombiana",
    version="2.1.0",
    lifespan=lifespan,
)


def handle_comandos(mensaje: str) -> str | None:
    cmd = mensaje.lower().strip()
    if cmd in ("/ayuda", "/comandos", "/help"):
        return (
            "📋 *Comandos disponibles:*\n\n"
            "• */graficar* [descripción] - Crear gráfico\n"
            "• */buscar* [consulta] - Buscar en internet\n"
            "• */faq* [pregunta] - Consultar FAQ\n"
            "• */analizar* [archivo] - Analizar documento\n"
            "• */sesion* [nombre] - Cambiar contexto\n"
            "• */metricas* - Ver métricas del sistema\n"
            "• */ayuda* - Esta lista\n\n"
            "O simplemente conversa normal, el asistente entiende tu intención."
        )
    if cmd == "/metricas":
        metrics = get_tool_metrics()
        if not metrics:
            return "No hay métricas disponibles aún."
        lines = ["📊 *Métricas del sistema:*"]
        for tool_name, data in metrics.items():
            avg_ms = data["total_duration_ms"] / data["calls"] if data["calls"] else 0
            lines.append(
                f"• {tool_name}: {data['calls']} llamadas, "
                f"{data['errors']} errores, "
                f"{avg_ms:.0f}ms promedio"
            )
        return "\n".join(lines)
    return None


async def descargar_media_twilio(media_url: str) -> str | None:
    client = get_twilio_client()
    if not client:
        return None
    try:
        import requests
        from app.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
        auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        resp = requests.get(media_url, auth=auth, timeout=30)
        if resp.status_code == 200:
            ext = Path(media_url).suffix or ".bin"
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as f:
                f.write(resp.content)
                return f.name
    except Exception as e:
        guardar_log(0, "media_download_error", str(e), "error")
    return None


def verificar_rate_limit(usuario_id: str):
    if not rate_limiter.check(usuario_id):
        raise HTTPException(
            status_code=429,
            detail="Demasiadas solicitudes. Espera un momento antes de enviar otro mensaje."
        )


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "2.1.0",
        "llm_configured": bool(ANTHROPIC_API_KEY or GROQ_API_KEY),
        "twilio_configured": bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN),
        "twilio_number": TWILIO_WHATSAPP_NUMBER or "no configurado",
    }


@app.post("/webhook/whatsapp")
async def webhook_whatsapp(request: Request):
    form = await request.form()
    mensaje = form.get("Body", "").strip()
    remitente = form.get("From", "").replace("whatsapp:", "")
    perfil = form.get("ProfileName", "")
    num_media = int(form.get("NumMedia", "0"))

    if not mensaje and num_media == 0:
        return PlainTextResponse(generar_respuesta_twiml(
            "Por favor envía un mensaje o archivo."
        ), media_type="application/xml")

    verificar_rate_limit(remitente)

    respuesta_comando = handle_comandos(mensaje)
    if respuesta_comando:
        enviar_mensaje_whatsapp(remitente, respuesta_comando)
        return PlainTextResponse(
            generar_respuesta_twiml(respuesta_comando),
            media_type="application/xml"
        )

    if num_media > 0:
        media_url = form.get("MediaUrl0")
        media_type = form.get("MediaContentType0", "")

        if media_type in ("text/csv", "text/plain", "application/vnd.ms-excel",
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"):
            archivo = await descargar_media_twilio(media_url)
            if archivo:
                from tools.registry import analyze_document
                resultado = analyze_document(archivo)
                mensaje = f"{mensaje}\n\n[ARCHIVO ADJUNTO: {form.get('MediaUrl0', '')}]\n\nAnálisis del archivo:\n{resultado}"
                try:
                    os.unlink(archivo)
                except Exception:
                    pass
            else:
                mensaje = f"{mensaje}\n\n[No se pudo descargar el archivo adjunto]"
        else:
            mensaje = f"{mensaje}\n\n[Archivo recibido: {media_type}]"

    if not mensaje or not remitente:
        return PlainTextResponse(generar_respuesta_twiml(
            "Por favor envía un mensaje de texto válido."
        ), media_type="application/xml")

    respuesta = procesar_mensaje(remitente, mensaje, perfil)
    enviar_mensaje_whatsapp(remitente, respuesta)
    return PlainTextResponse(generar_respuesta_twiml(respuesta), media_type="application/xml")


@app.post("/webhook/whatsapp/json")
async def webhook_whatsapp_json(request: Request):
    data = await request.json()
    mensaje = data.get("message", {}).get("text", {}).get("body", "")
    remitente = data.get("message", {}).get("from", "").replace("whatsapp:", "")
    perfil = data.get("message", {}).get("author", "")

    if not mensaje and not remitente:
        return JSONResponse({"error": "Mensaje o remitente inválido"}, status_code=400)

    verificar_rate_limit(remitente)

    respuesta_comando = handle_comandos(mensaje)
    if respuesta_comando:
        enviar_mensaje_whatsapp(remitente, respuesta_comando)
        return {"status": "ok", "respuesta": respuesta_comando}

    respuesta = procesar_mensaje(remitente, mensaje, perfil)
    enviar_mensaje_whatsapp(remitente, respuesta)
    return {"status": "ok", "respuesta": respuesta}


@app.post("/api/chat")
async def api_chat(request: Request):
    data = await request.json()
    mensaje = data.get("mensaje", "").strip()
    usuario_id = data.get("usuario_id", "api-user")
    usuario_nombre = data.get("usuario_nombre", "")

    if not mensaje:
        return JSONResponse({"error": "Mensaje requerido"}, status_code=400)

    verificar_rate_limit(usuario_id)

    respuesta_comando = handle_comandos(mensaje)
    if respuesta_comando:
        return {"respuesta": respuesta_comando}

    respuesta = procesar_mensaje(usuario_id, mensaje, usuario_nombre)

    return JSONResponse({"respuesta": respuesta})


@app.get("/")
async def root():
    return {
        "app": "Financial Agent v2.1 - Asistente Inteligente",
        "endpoints": {
            "health": "/health",
            "webhook_whatsapp": "/webhook/whatsapp (POST)",
            "api_chat": "/api/chat (POST)",
            "metrics": "/metrics",
        }
    }


@app.get("/metrics")
async def metrics():
    return get_tool_metrics()


@app.post("/api/chat/con-documento")
async def api_chat_con_documento(request: Request):
    import json as json_mod

    form = await request.form()
    mensaje = form.get("mensaje", "").strip()
    usuario_id = form.get("usuario_id", "api-user")
    usuario_nombre = form.get("usuario_nombre", "")

    archivo = form.get("archivo")
    if archivo and hasattr(archivo, "filename") and archivo.filename:
        ext = Path(archivo.filename).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            content = await archivo.read()
            tmp.write(content)
            tmp_path = tmp.name

        resultado = analyze_document(tmp_path)
        mensaje = f"{mensaje}\n\n[ARCHIVO: {archivo.filename}]\n\n{resultado}"
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    if not mensaje:
        return JSONResponse({"error": "Mensaje requerido"}, status_code=400)

    respuesta = procesar_mensaje(usuario_id, mensaje, usuario_nombre)
    return JSONResponse({"respuesta": respuesta})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
