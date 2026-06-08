import os

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

DEFAULT_MODEL = "llama-3.3-70b-versatile"

MAX_HISTORY = 20

MAX_TOOL_ITERATIONS = 10

EXIT_COMMANDS = {
    "salir",
    "exit",
    "quit"
}
