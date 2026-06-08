import os
import csv
import sqlite3
from pathlib import Path

import pandas as pd


def _detect_delimiter(path: str) -> str:
    with open(path) as f:
        first = f.read(4096)
    dialect = csv.Sniffer().sniff(first, delimiters=",;\t|")
    return dialect.delimiter


def _analyze_csv(path: str) -> str:
    delimiter = _detect_delimiter(path)
    df = pd.read_csv(path, delimiter=delimiter)
    return _format_dataframe_analysis(df)


def _analyze_excel(path: str) -> str:
    xls = pd.ExcelFile(path)
    sheets = xls.sheet_names
    parts = [f"Hojas: {len(sheets)} — {', '.join(sheets)}\n"]

    for sheet in sheets:
        df = pd.read_excel(path, sheet_name=sheet)
        parts.append(f"\n--- Hoja: {sheet} ---")
        parts.append(_format_dataframe_analysis(df))

    return "\n".join(parts)


def _analyze_sqlite(path: str) -> str:
    conn = sqlite3.connect(path)
    cur = conn.cursor()

    cur.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' ORDER BY name"
    )
    tables = [r[0] for r in cur.fetchall()]

    parts = [f"Tablas: {len(tables)} — {', '.join(tables)}\n"]

    for table in tables:
        cur.execute(f"SELECT sql FROM sqlite_master WHERE name = ?", (table,))
        schema = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM \"{table}\"")
        count = cur.fetchone()[0]

        parts.append(f"\n--- Tabla: {table} ---")
        parts.append(f"Filas: {count}")
        parts.append(f"Schema:\n{schema}")

        if count:
            cur.execute(f"SELECT * FROM \"{table}\" LIMIT 5")
            rows = cur.fetchall()
            colnames = [desc[0] for desc in cur.description]
            parts.append(f"Primeras {len(rows)} filas:")
            parts.append("  " + " | ".join(colnames))
            for row in rows:
                parts.append("  " + " | ".join(str(v)[:30] for v in row))

    conn.close()
    return "\n".join(parts)


def _format_dataframe_analysis(df: pd.DataFrame) -> str:
    n_rows, n_cols = df.shape
    lines = [
        f"Filas: {n_rows}  |  Columnas: {n_cols}",
        f"Memoria: {df.memory_usage(deep=True).sum() / 1024:.1f} KB",
        "",
        "Columnas:",
        f"  {'Columna':<25} {'Tipo':<15} {'No nulos':<10} {'Nulos':<6} {'Unicos':<8}",
        f"  {'-'*25} {'-'*15} {'-'*10} {'-'*6} {'-'*8}",
    ]
    for col in df.columns:
        dtype = str(df[col].dtype)
        non_null = df[col].notna().sum()
        nulls = df[col].isna().sum()
        uniques = df[col].nunique()
        lines.append(
            f"  {str(col):<25} {dtype:<15} {non_null:<10} {nulls:<6} {uniques:<8}"
        )

    num_cols = df.select_dtypes(include="number").columns
    if len(num_cols):
        lines.append("")
        lines.append("Estadísticas (columnas numéricas):")
        desc = df[num_cols].describe().to_string()
        for l in desc.split("\n"):
            lines.append(f"  {l}")

    cat_cols = df.select_dtypes(include="object").columns[:3]
    for col in cat_cols:
        lines.append("")
        lines.append(f"Top valores — {col}:")
        vc = df[col].value_counts().head(5)
        for val, cnt in vc.items():
            pct = cnt / n_rows * 100
            lines.append(f"  {str(val)[:40]:<42} {cnt:>6}  ({pct:.1f}%)")

    lines.append("")
    lines.append("Primeras 5 filas:")
    head_str = df.head().to_string(index=False)
    for l in head_str.split("\n"):
        lines.append(f"  {l}")

    return "\n".join(lines)


def analyze_document(path: str, sheet: str | None = None) -> str:
    if not os.path.exists(path):
        return f"Error: archivo no encontrado: {path}"

    if os.path.isdir(path):
        return f"Error: '{path}' es un directorio, no un archivo"

    size = os.path.getsize(path)
    ext = Path(path).suffix.lower()

    if size == 0:
        return f"Error: el archivo está vacío: {path}"

    if ext in (".csv", ".tsv"):
        try:
            return _analyze_csv(path)
        except Exception as e:
            return f"Error analizando CSV: {e}"

    elif ext in (".xlsx", ".xls"):
        try:
            return _analyze_excel(path)
        except Exception as e:
            return f"Error analizando Excel: {e}"

    elif ext in (".db", ".sqlite", ".sqlite3"):
        try:
            return _analyze_sqlite(path)
        except Exception as e:
            return f"Error analizando base de datos: {e}"

    else:
        return (
            f"Formato no soportado: {ext}\n\n"
            f"Formatos aceptados:\n"
            f"  .csv, .tsv  — Archivos de texto delimitados\n"
            f"  .xlsx, .xls — Archivos Excel\n"
            f"  .db, .sqlite, .sqlite3 — Bases de datos SQLite"
        )
