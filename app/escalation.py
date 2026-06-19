import re


FRUSTRACION_KEYWORDS = [
    "queja", "molesto", "insatisfecho", "pésimo", "terrible", "horrible",
    "pésimo servicio", "mal servicio", "incompetente", "ineficiente",
    "no sirve", "no funciona", "me estresas", "me enfadas",
    "habla con humano", "representante", "asesor humano",
    "quiero hablar con alguien", "me comunico con un superior",
    "gerente", "supervisor", "pongo queja", "formal complaint",
    "abogado", "demanda", "pérdida de tiempo", "pésima atención",
    "pésima experiencia", "estoy cansado", "estoy harto", "basta ya",
    "no me sirves", "eres inútil", "no sabes nada",
    "pasa con un agente", "persona real", "ser humano",
]

FUERA_ALCANCE_KEYWORDS = [
    "asesoría legal", "asesoría contable", "declaración de renta",
    "constituir empresa", "créame una empresa",
    "visa", "pasaporte", "cita médica", "consulta médica",
    "receta médica", "problemas técnicos de celular",
    "arreglar mi computador", "clases de inglés",
    "receta de cocina", "clima de hoy",
]


def detectar_frustracion(texto):
    texto_lower = texto.lower()
    for keyword in FRUSTRACION_KEYWORDS:
        if keyword in texto_lower:
            return True, f"Palabra clave detectada: '{keyword}'"
    return False, ""


def detectar_fuera_alcance(texto):
    texto_lower = texto.lower()
    for keyword in FUERA_ALCANCE_KEYWORDS:
        if keyword in texto_lower:
            return True, f"Tema fuera de alcance: '{keyword}'"
    return False, ""


def detectar_solicitud_humano(texto):
    patrones = [
        r"\b(habla|comunica|pasa|transferir|derivar|conectar)\s*(con|al|a|me)\s*(un|el)\s*(humano|agente|asesor|persona|representante|operador)\b",
        r"\b(quiero|necesito|requiero|puedo)\s*(hablar|comunicar|contactar|hablar|hablar)\s*(con|al)\s*(un|el)\s*(humano|agente|asesor|persona)\b",
        r"\b(me\s*comunica|me\s*pasa|me\s*transfiere)\s*(con|al)\s*(un|el)\s*(humano|agente)\b",
        r"\b(atención\s*humana|agente\s*humano|asesor\s*humano)\b",
        r"\b(por\s*favor\s*ayuda\s*humana)\b",
        r"\bno\s*(me|puedes|sabes|sirves)\s*(ayudas|resolver|entender|servir)\b",
        r"\besto\s*(no|es)\s*(es|una)\s*(pierdes|pérdida)\s*(de|del)\s*tiempo\b",
    ]
    for patron in patrones:
        if re.search(patron, texto.lower()):
            return True
    return False


def evaluar_escalado(texto, faq_match=None, tiene_info=True):
    razones = []

    es_frustracion, motivo_f = detectar_frustracion(texto)
    if es_frustracion:
        razones.append(motivo_f)

    es_fuera, motivo_fa = detectar_fuera_alcance(texto)
    if es_fuera:
        razones.append(motivo_fa)

    es_humano = detectar_solicitud_humano(texto)
    if es_humano:
        razones.append("El usuario solicita explícitamente hablar con un humano")

    if not tiene_info and not faq_match:
        razones.append("No se encontró información relevante para responder")

    debe_escalar = len(razones) > 0
    return debe_escalar, "; ".join(razones) if razones else ""
