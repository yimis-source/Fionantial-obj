import os
from pathlib import Path
from dotenv import load_dotenv

dotenv_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
DEFAULT_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "llama-3.3-70b-versatile")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./financial_agent.db")

LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "true")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "Financial Agent")

MAX_HISTORY = int(os.getenv("MAX_HISTORY", "20"))
MAX_TOOL_ITERATIONS = int(os.getenv("MAX_TOOL_ITERATIONS", "10"))
MAX_RESPONSE_TIME = int(os.getenv("MAX_RESPONSE_TIME", "5"))

SUMMARY_TRIGGER = int(os.getenv("SUMMARY_TRIGGER", "6"))
MAX_ACTIVE_MESSAGES = int(os.getenv("MAX_ACTIVE_MESSAGES", "6"))

GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")

PROVIDER_TIMEOUT = int(os.getenv("PROVIDER_TIMEOUT", "15"))
CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "3"))
CIRCUIT_BREAKER_RESET_SECONDS = int(os.getenv("CIRCUIT_BREAKER_RESET_SECONDS", "120"))

RATE_LIMIT_MAX_PER_MINUTE = int(os.getenv("RATE_LIMIT_MAX_PER_MINUTE", "20"))
