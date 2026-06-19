import os
from google import genai

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    API_KEY = input("Introduce tu GOOGLE_API_KEY: ").strip()
    if not API_KEY:
        print("ERROR: Se requiere una API key.")
        exit(1)

client = genai.Client(api_key=API_KEY)
model = "gemini-2.0-flash"

chat = client.chats.create(model=model)

print(f"\nChat con Gemini ({model}) — escribe 'salir' para terminar\n")

while True:
    try:
        user_input = input("Tú: ")
    except (EOFError, KeyboardInterrupt):
        print()
        break

    if not user_input.strip():
        continue
    if user_input.lower() in ("salir", "exit", "quit"):
        break

    response = chat.send_message(user_input)
    print(f"Gemini: {response.text}\n")
