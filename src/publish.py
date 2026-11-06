import os
import sqlite3
from pathlib import Path
import pandas as pd

DB_PATH = Path("data/curated/alzheimer.db")   # backend de secours (sans Docker)

COLS = ["patient_id", "age", "gender", "bmi", "hypertension", "systolic_bp", "diastolic_bp",
        "cholesterol_total", "mmse", "memory_complaints", "diagnosis", "diagnosis_label",
        "age_group", "source_file"]

RUN_COLS = ["run_id", "status", "source_file", "input_rows", "accepted_rows",
            "rejected_rows", "reject_rate", "duration_seconds", "error"]

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    patient_id INTEGER PRIMARY KEY,
    age INTEGER NOT NULL,
    gender TEXT,
    bmi REAL,
    hypertension INTEGER,
    systolic_bp INTEGER NOT NULL,
    diastolic_bp INTEGER NOT NULL,
    cholesterol_total REAL NOT NULL,
    mmse REAL NOT NULL,
    memory_complaints INTEGER,
    diagnosis INTEGER NOT NULL CHECK (diagnosis IN (0, 1)),
    diagnosis_label TEXT NOT NULL,
    age_group TEXT NOT NULL,
    source_file TEXT NOT NULL,
    loaded_run_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    status TEXT,
    source_file TEXT,
    input_rows INTEGER,
    accepted_rows INTEGER,
    rejected_rows INTEGER,
    reject_rate REAL,
    duration_seconds REAL,
    error TEXT
);
DROP VIEW IF EXISTS v_kpi_by_diagnosis;
CREATE VIEW v_kpi_by_diagnosis AS
SELECT diagnosis_label,
       COUNT(*) AS patients,
       ROUND(AVG(mmse), 1) AS mmse_moyen,
       ROUND(AVG(systolic_bp), 1) AS systolique_moyenne,
       ROUND(AVG(cholesterol_total), 1) AS cholesterol_moyen,
       ROUND(AVG(age), 1) AS age_moyen
FROM patients GROUP BY diagnosis_label;
DROP VIEW IF EXISTS v_kpi_by_age_group;
CREATE VIEW v_kpi_by_age_group AS
SELECT age_group,
       COUNT(*) AS patients,
       SUM(diagnosis) AS diagnostiques,
       ROUND(100.0 * SUM(diagnosis) / COUNT(*), 1) AS pct_diagnostiques
FROM patients GROUP BY age_group
ORDER BY CASE age_group WHEN '<65' THEN 1 WHEN '65-74' THEN 2 WHEN '75-84' THEN 3 ELSE 4 END;
"""

PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    patient_id INTEGER PRIMARY KEY,
    age INTEGER NOT NULL CHECK (age BETWEEN 0 AND 120),
    gender TEXT,
    bmi REAL,
    hypertension INTEGER,
    systolic_bp INTEGER NOT NULL,
    diastolic_bp INTEGER NOT NULL,
    cholesterol_total REAL NOT NULL,
    mmse REAL NOT NULL CHECK (mmse BETWEEN 0 AND 30),
    memory_complaints INTEGER,
    diagnosis INTEGER NOT NULL CHECK (diagnosis IN (0, 1)),
    diagnosis_label TEXT NOT NULL,
    age_group TEXT NOT NULL,
    source_file TEXT NOT NULL,
    loaded_run_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    status TEXT,
    source_file TEXT,
    input_rows INTEGER,
    accepted_rows INTEGER,
    rejected_rows INTEGER,
    reject_rate REAL,
    duration_seconds REAL,
    error TEXT
);
DROP VIEW IF EXISTS v_kpi_by_diagnosis;
CREATE VIEW v_kpi_by_diagnosis AS
SELECT diagnosis_label,
       COUNT(*) AS patients,
       ROUND(AVG(mmse)::numeric, 1) AS mmse_moyen,
       ROUND(AVG(systolic_bp)::numeric, 1) AS systolique_moyenne,
       ROUND(AVG(cholesterol_total)::numeric, 1) AS cholesterol_moyen,
       ROUND(AVG(age)::numeric, 1) AS age_moyen
FROM patients GROUP BY diagnosis_label;
DROP VIEW IF EXISTS v_kpi_by_age_group;
CREATE VIEW v_kpi_by_age_group AS
SELECT age_group,
       COUNT(*) AS patients,
       SUM(diagnosis) AS diagnostiques,
       ROUND(100.0 * SUM(diagnosis) / COUNT(*), 1) AS pct_diagnostiques
FROM patients GROUP BY age_group
ORDER BY CASE age_group WHEN '<65' THEN 1 WHEN '65-74' THEN 2 WHEN '75-84' THEN 3 ELSE 4 END;
"""


def _use_pg() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


def backend() -> str:
    return "postgresql" if _use_pg() else "sqlite"


def _sqlite_connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(SQLITE_SCHEMA)
    return con


def _pg_connect():
    import psycopg   # import ici : inutile en mode SQLite
    con = psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=10)
    con.execute(PG_SCHEMA)
    con.commit()
    return con


def _rows(df: pd.DataFrame, run_id: str) -> list:
    data = df[COLS].astype(object).where(df[COLS].notna(), None).values.tolist()
    return [r + [run_id] for r in data]


def _upsert_sql(ph: str) -> str:
    updates = ", ".join(f"{c}=excluded.{c}" for c in COLS if c != "patient_id")
    return (f"INSERT INTO patients ({', '.join(COLS)}, loaded_run_id) "
            f"VALUES ({','.join([ph] * (len(COLS) + 1))}) "
            f"ON CONFLICT(patient_id) DO UPDATE SET {updates}, loaded_run_id=excluded.loaded_run_id")


def publish_db(df: pd.DataFrame, run_id: str) -> int:
    """UPSERT du curated (transaction unique : tout ou rien)."""
    rows = _rows(df, run_id)
    if _use_pg():
        with _pg_connect() as con:            # commit si OK, rollback si erreur
            with con.cursor() as cur:
                cur.executemany(_upsert_sql("%s"), rows)
                cur.execute("SELECT COUNT(*) FROM patients")
                return cur.fetchone()[0]
    con = _sqlite_connect()
    try:
        with con:
            con.executemany(_upsert_sql("?"), rows)
        return con.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    finally:
        con.close()


def log_run(report: dict) -> None:
    values = [report.get(c) for c in RUN_COLS[:1]] + [report.get(c) for c in RUN_COLS[1:]]
    if _use_pg():
        updates = ", ".join(f"{c}=excluded.{c}" for c in RUN_COLS if c != "run_id")
        sql = (f"INSERT INTO runs ({', '.join(RUN_COLS)}) VALUES ({','.join(['%s'] * len(RUN_COLS))}) "
               f"ON CONFLICT (run_id) DO UPDATE SET {updates}")
        with _pg_connect() as con:
            con.execute(sql, values)
        return
    con = _sqlite_connect()
    try:
        with con:
            con.execute(f"INSERT OR REPLACE INTO runs VALUES ({','.join('?' * len(RUN_COLS))})", values)
    finally:
        con.close()