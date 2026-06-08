import sys
from dotenv import load_dotenv

load_dotenv()

from core.config import GROQ_API_KEY
from core.config import EXIT_COMMANDS
from core.config import MAX_HISTORY

from prompts.system_prompt import SYSTEM_PROMPT

from core.chat import chat
from core.chat import process_tools

from utils.messages import trim_messages
from utils.database import init_db
from utils.database import get_or_create_session
from utils.database import load_history
from utils.database import save_message

_REQUIRED_ENV = {
    "GROQ_API_KEY": GROQ_API_KEY,
}

for _name, _value in _REQUIRED_ENV.items():
    if not _value:
        print(
            f"ERROR: {_name} no configurada. "
            "Agrégala en el archivo .env",
            file=sys.stderr
        )
        sys.exit(1)


def main():
    try:
        init_db()
    except Exception as e:
        print(f"ERROR conectando a la BD: {e}", file=sys.stderr)
        sys.exit(1)

    session_id = get_or_create_session()

    print(f"\nSesión: {session_id[:8]}...")

    history = load_history(session_id, limit=MAX_HISTORY)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    messages.extend(history)

    while True:
        try:
            user_input = input("\nUsuario: ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input.strip():
            continue

        if user_input.lower() in EXIT_COMMANDS:
            break

        messages.append({"role": "user", "content": user_input})
        save_message(session_id, "user", content=user_input)

        messages = trim_messages(messages, max_history=MAX_HISTORY)

        try:
            response = chat(messages)
            assistant_reply = process_tools(
                messages,
                response,
                session_id=session_id,
                save_fn=save_message
            )
        except Exception as e:
            print(f"\nError en la consulta: {e}")
            continue

        messages.append({"role": "assistant", "content": assistant_reply})
        save_message(session_id, "assistant", content=assistant_reply)

        print(f"\nAsistente:\n{assistant_reply}")


if __name__ == "__main__":
    main()
