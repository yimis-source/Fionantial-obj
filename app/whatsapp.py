import re
import os
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

from app.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER
from app.database import guardar_log
from tools.registry import _IMAGES_TO_SEND

_twilio_client = None


def get_twilio_client():
    global _twilio_client
    if _twilio_client is None and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        _twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    return _twilio_client


def enviar_mensaje_whatsapp(destino: str, mensaje: str) -> bool:
    client = get_twilio_client()

    # Scan response for mermaid.ink URLs
    mermaid_urls = re.findall(r'https://mermaid\.ink/img/[^\s\)]+', mensaje)
    for url in mermaid_urls:
        if url not in _IMAGES_TO_SEND:
            _IMAGES_TO_SEND.append(url)

    # Send pending images
    for img in list(_IMAGES_TO_SEND):
        try:
            if client:
                client.messages.create(
                    from_=f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
                    to=f"whatsapp:{destino}",
                    media_url=[img] if img.startswith("http") else [],
                )
            else:
                print(f"[WhatsApp Simulado] Imagen: {img}")
        except Exception as e:
            guardar_log(0, "whatsapp_media_error", str(e), "error")
        finally:
            _IMAGES_TO_SEND.remove(img)
            if not img.startswith("http"):
                try:
                    os.unlink(img)
                except Exception:
                    pass

    # Clean image markers from response text
    texto_limpio = re.sub(r'IMAGEN_GENERADA:\S+', '', mensaje)
    texto_limpio = re.sub(r'IMAGEN_PATH:\S+', '', texto_limpio)
    texto_limpio = re.sub(r'https://mermaid\.ink/img/\S+', '📊', texto_limpio)
    texto_limpio = re.sub(r'\n{3,}', '\n\n', texto_limpio).strip()

    if not texto_limpio:
        texto_limpio = "📊"

    if not client:
        print(f"[WhatsApp Simulado] Enviando a {destino}: {texto_limpio[:100]}...")
        return True

    try:
        client.messages.create(
            body=texto_limpio,
            from_=f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
            to=f"whatsapp:{destino}"
        )
        return True
    except Exception as e:
        guardar_log(0, "whatsapp_error", str(e), "error")
        return False


def generar_respuesta_twiml(mensaje: str) -> str:
    texto_limpio = re.sub(r'IMAGEN_GENERADA:\S+', '', mensaje)
    texto_limpio = re.sub(r'IMAGEN_PATH:\S+', '', texto_limpio)
    texto_limpio = re.sub(r'https://mermaid\.ink/img/\S+', '📊', texto_limpio)
    texto_limpio = re.sub(r'\n{3,}', '\n\n', texto_limpio).strip()
    if not texto_limpio:
        texto_limpio = "📊"
    resp = MessagingResponse()
    resp.message(texto_limpio)
    return str(resp)
