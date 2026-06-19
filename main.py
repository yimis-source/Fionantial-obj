import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.database import init_db
from app.seed import seed_demo_data

init_db()
seed_demo_data()

if __name__ == "__main__":
    import uvicorn
    print("""
    ╔══════════════════════════════════════════╗
    ║     Financial Agent - WhatsApp MVP       ║
    ║                                          ║
    ║  Endpoints:                              ║
    ║  • Health:  http://localhost:8000/health  ║
    ║  • Webhook: /webhook/whatsapp (POST)     ║
    ║  • API:     /api/chat (POST)             ║
    ╚══════════════════════════════════════════╝
    """)
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
