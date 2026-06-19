import sqlite3
import json
import os
from datetime import datetime, timedelta

from app.database import get_db, DB_PATH


def seed_demo_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as count FROM tenants")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    print("[Seed] Insertando datos demo...")

    cursor.execute("""
        INSERT INTO tenants (id, nombre, telefono, email, configuracion)
        VALUES (1, 'Finanzas PYME SAS', '+573001234567', 'contacto@finanzaspyme.co', '{}')
    """)

    for i in range(1, 11):
        cursor.execute("""
            INSERT INTO conversaciones (id, tenant_id, usuario_id, usuario_nombre, canal, estado, creado_en)
            VALUES (?, 1, ?, ?, 'whatsapp', 'finalizada', ?)
        """, (
            i,
            f"+57300{i:06d}",
            f"Cliente Demo {i}",
            (datetime.now() - timedelta(days=i)).isoformat()
        ))

    for i in range(1, 6):
        cursor.execute("""
            INSERT INTO escalados (id, conversacion_id, usuario_id, usuario_nombre, usuario_telefono, motivo, resumen, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pendiente')
        """, (
            i, i,
            f"+57300{i:06d}",
            f"Cliente Escalado {i}",
            f"+57300{i:06d}",
            ["Solicita hablar con un humano", "Consulta fuera de alcance",
             "Cliente frustrado por demora", "Problema con devolución",
             "Solicita información sobre inversiones"][i-1],
            f"Conversación de ejemplo para escalado #{i}",
        ))

    conn.commit()
    conn.close()
    print("[Seed] Datos demo insertados correctamente.")
