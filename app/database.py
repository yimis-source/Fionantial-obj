import sqlite3
import json
import os
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.getenv("DATABASE_URL", "sqlite:///./financial_agent.db").replace("sqlite:///", "")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS tenants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT,
            email TEXT,
            configuracion TEXT DEFAULT '{}',
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS conversaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER DEFAULT 1,
            usuario_id TEXT NOT NULL,
            usuario_nombre TEXT,
            canal TEXT DEFAULT 'whatsapp',
            estado TEXT DEFAULT 'activa',
            resumen TEXT,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id)
        );

        CREATE TABLE IF NOT EXISTS mensajes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversacion_id INTEGER NOT NULL,
            rol TEXT NOT NULL,
            contenido TEXT NOT NULL,
            tokens_usados INTEGER DEFAULT 0,
            tiempo_ms INTEGER DEFAULT 0,
            metadata TEXT DEFAULT '{}',
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversacion_id) REFERENCES conversaciones(id)
        );

        CREATE TABLE IF NOT EXISTS logs_actividad (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversacion_id INTEGER,
            tipo TEXT NOT NULL,
            detalle TEXT,
            nivel TEXT DEFAULT 'info',
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversacion_id) REFERENCES conversaciones(id)
        );

        CREATE TABLE IF NOT EXISTS escalados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversacion_id INTEGER NOT NULL,
            usuario_id TEXT NOT NULL,
            usuario_nombre TEXT,
            usuario_telefono TEXT,
            motivo TEXT NOT NULL,
            resumen TEXT,
            historial TEXT,
            estado TEXT DEFAULT 'pendiente',
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversacion_id) REFERENCES conversaciones(id)
        );

        CREATE TABLE IF NOT EXISTS faqs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pregunta TEXT NOT NULL,
            respuesta TEXT NOT NULL,
            categoria TEXT DEFAULT 'general',
            activo INTEGER DEFAULT 1,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id TEXT NOT NULL UNIQUE,
            usuario_nombre TEXT,
            preferencias TEXT DEFAULT '{}',
            metricas_interes TEXT DEFAULT '[]',
            moneda TEXT DEFAULT 'COP',
            modo_respuesta TEXT DEFAULT 'normal',
            datos_adicionales TEXT DEFAULT '{}',
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS metricas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversacion_id INTEGER,
            usuario_id TEXT,
            tipo TEXT NOT NULL,
            clave TEXT NOT NULL,
            valor TEXT,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    try:
        conn.execute("ALTER TABLE conversaciones ADD COLUMN resumen TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()

def crear_conversacion(usuario_id, usuario_nombre=None, canal="whatsapp"):
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id, estado FROM conversaciones WHERE usuario_id = ? AND estado = 'activa' ORDER BY creado_en DESC LIMIT 1",
            (usuario_id,)
        )
        existing = cursor.fetchone()
        if existing:
            return existing["id"]

        cursor = conn.execute(
            "INSERT INTO conversaciones (usuario_id, usuario_nombre, canal) VALUES (?, ?, ?)",
            (usuario_id, usuario_nombre, canal)
        )
        conn.commit()
        return cursor.lastrowid

def finalizar_conversacion(conversacion_id):
    with get_db() as conn:
        conn.execute(
            "UPDATE conversaciones SET estado = 'finalizada', actualizado_en = CURRENT_TIMESTAMP WHERE id = ?",
            (conversacion_id,)
        )
        conn.commit()

def guardar_mensaje(conversacion_id, rol, contenido, tokens=0, tiempo_ms=0, metadata=None):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO mensajes (conversacion_id, rol, contenido, tokens_usados, tiempo_ms, metadata)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (conversacion_id, rol, contenido, tokens, tiempo_ms, json.dumps(metadata or {}))
        )
        conn.execute(
            "UPDATE conversaciones SET actualizado_en = CURRENT_TIMESTAMP WHERE id = ?",
            (conversacion_id,)
        )
        conn.commit()

def obtener_historial(conversacion_id, limite=20):
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT rol, contenido, creado_en FROM mensajes WHERE conversacion_id = ? ORDER BY creado_en ASC LIMIT ?",
            (conversacion_id, limite)
        )
        return [dict(row) for row in cursor.fetchall()]

def guardar_log(conversacion_id, tipo, detalle, nivel="info"):
    if not conversacion_id or conversacion_id == 0:
        conversacion_id = 1
    with get_db() as conn:
        conn.execute(
            "INSERT INTO logs_actividad (conversacion_id, tipo, detalle, nivel) VALUES (?, ?, ?, ?)",
            (conversacion_id, tipo, detalle, nivel)
        )
        conn.commit()

def crear_escalado(conversacion_id, usuario_id, motivo, resumen, historial, usuario_nombre=None, usuario_telefono=None):
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO escalados (conversacion_id, usuario_id, usuario_nombre, usuario_telefono, motivo, resumen, historial)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (conversacion_id, usuario_id, usuario_nombre, usuario_telefono, motivo, resumen, historial)
        )
        conn.execute(
            "UPDATE conversaciones SET estado = 'escalada', actualizado_en = CURRENT_TIMESTAMP WHERE id = ?",
            (conversacion_id,)
        )
        conn.commit()
        return cursor.lastrowid

def obtener_faqs(activo=True):
    with get_db() as conn:
        if activo:
            cursor = conn.execute("SELECT id, pregunta, respuesta, categoria FROM faqs WHERE activo = 1 ORDER BY categoria, id")
        else:
            cursor = conn.execute("SELECT id, pregunta, respuesta, categoria FROM faqs ORDER BY categoria, id")
        return [dict(row) for row in cursor.fetchall()]

def buscar_faq(pregunta):
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id, pregunta, respuesta, categoria FROM faqs WHERE activo = 1 AND pregunta LIKE ? LIMIT 5",
            (f"%{pregunta}%",)
        )
        return [dict(row) for row in cursor.fetchall()]


def obtener_perfil_usuario(usuario_id: str) -> dict | None:
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT preferencias, metricas_interes, moneda, modo_respuesta FROM user_profiles WHERE usuario_id = ?",
            (usuario_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                "preferencias": json.loads(row["preferencias"]),
                "metricas_interes": json.loads(row["metricas_interes"]),
                "moneda": row["moneda"],
                "modo_respuesta": row["modo_respuesta"],
            }
    return None


def guardar_resumen_conversacion(conversacion_id: int, resumen: str):
    with get_db() as conn:
        conn.execute(
            "UPDATE conversaciones SET resumen = ? WHERE id = ?",
            (resumen, conversacion_id)
        )
        conn.commit()


def obtener_resumen_conversacion(conversacion_id: int) -> str | None:
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT resumen FROM conversaciones WHERE id = ?",
            (conversacion_id,)
        )
        row = cursor.fetchone()
        return row["resumen"] if row and row["resumen"] else None


def guardar_metrica(conversacion_id, usuario_id, tipo, clave, valor):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO metricas (conversacion_id, usuario_id, tipo, clave, valor) VALUES (?, ?, ?, ?, ?)",
            (conversacion_id, usuario_id, tipo, clave, str(valor))
        )
        conn.commit()
