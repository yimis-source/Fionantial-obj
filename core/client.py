from groq import Groq

from core.config import GROQ_API_KEY

if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY no configurada. "
        "Agrégala en el archivo .env"
    )

client = Groq(api_key=GROQ_API_KEY)
