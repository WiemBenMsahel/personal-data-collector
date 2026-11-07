"""Acces en lecture seule a la base, partage par l'API et le tableau de bord.

PostgreSQL si la variable d'environnement DATABASE_URL est definie, sinon SQLite
(data/curated/alzheimer.db, ouverte en lecture seule). Les parametres s'ecrivent avec ?.
"""
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQLITE_PATH = ROOT / "data" / "curated" / "alzheimer.db"


class DatabaseUnavailable(RuntimeError):
    pass


def backend() -> str:
    return "postgresql" if os.getenv("DATABASE_URL") else "sqlite"


def query(sql: str, params: tuple = ()) -> list:
    """Execute un SELECT et retourne une liste de dictionnaires."""
    if backend() == "postgresql":
        import psycopg
        from psycopg.rows import dict_row
        try:
            with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as con:
                return list(con.execute(sql.replace("?", "%s"), params).fetchall())
        except psycopg.OperationalError as exc:
            raise DatabaseUnavailable(str(exc)) from exc
    if not SQLITE_PATH.exists():
        raise DatabaseUnavailable(f"{SQLITE_PATH} introuvable : lancez python src/pipeline.py")
    con = sqlite3.connect(f"file:{SQLITE_PATH.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in con.execute(sql, params).fetchall()]
    finally:
        con.close()