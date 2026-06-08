import os
import uuid

import psycopg2
import psycopg2.extras
import psycopg2.pool

DATABASE_URL = os.getenv("DATABASE_URL")
SESSION_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".session_id"
)

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL no configurada. "
                "Agrégala en el archivo .env"
            )
        _pool = psycopg2.pool.SimpleConnectionPool(
            1, 5, dsn=DATABASE_URL
        )
    return _pool


def get_connection():
    return _get_pool().getconn()


def put_connection(conn):
    _get_pool().putconn(conn)


def init_db():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id UUID PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id BIGSERIAL PRIMARY KEY,
                    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT,
                    tool_calls JSONB,
                    tool_call_id TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session_id
                ON messages(session_id, created_at)
            """)
        conn.commit()
    finally:
        put_connection(conn)


def get_or_create_session() -> str:
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE) as f:
            sid = f.read().strip()
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM sessions WHERE id = %s",
                    (sid,)
                )
                if cur.fetchone():
                    return sid
        finally:
            put_connection(conn)

    sid = str(uuid.uuid4())
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sessions (id) VALUES (%s)",
                (sid,)
            )
        conn.commit()
    finally:
        put_connection(conn)

    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        f.write(sid)

    return sid


def load_history(session_id: str, limit: int = 20) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT role, content, tool_calls, tool_call_id
                FROM messages
                WHERE session_id = %s
                ORDER BY created_at ASC
                LIMIT %s
            """, (session_id, limit))
            rows = cur.fetchall()
    finally:
        put_connection(conn)

    history = []
    for row in rows:
        msg = {"role": row["role"]}
        if row["content"]:
            msg["content"] = row["content"]
        if row["tool_calls"]:
            msg["tool_calls"] = row["tool_calls"]
        if row["tool_call_id"]:
            msg["tool_call_id"] = row["tool_call_id"]
        history.append(msg)
    return history


def save_message(session_id: str, role: str, content: str | None = None,
                 tool_calls: list | None = None,
                 tool_call_id: str | None = None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO messages (session_id, role, content, tool_calls, tool_call_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                session_id, role, content,
                psycopg2.extras.Json(tool_calls) if tool_calls else None,
                tool_call_id
            ))
        conn.commit()
    finally:
        put_connection(conn)
