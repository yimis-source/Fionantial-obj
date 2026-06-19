from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class WhatsAppMessage(BaseModel):
    From: str
    Body: str
    MessageSid: Optional[str] = None
    ProfileName: Optional[str] = None


class WebhookRequest(BaseModel):
    Body: Optional[str] = None
    From: Optional[str] = None
    To: Optional[str] = None
    MessageSid: Optional[str] = None
    ProfileName: Optional[str] = None


class WebhookResponse(BaseModel):
    status: str = "ok"


class HealthResponse(BaseModel):
    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.now)


class GraphState(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    messages: list = []
    usuario_id: str = ""
    usuario_nombre: str = ""
    conversacion_id: int = 0
    intencion: str = ""
    escalar: bool = False
    motivo_escalado: str = ""
    respuesta: str = ""
    tokens_usados: int = 0
    tiempo_ms: int = 0
    error: Optional[str] = None
    faq_match: Optional[dict] = None
