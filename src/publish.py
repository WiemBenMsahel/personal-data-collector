import sqlite3
from pathlib import Path
import pandas as pd

DB_PATH = Path("data/curated/alzheimer.db")

COLS = ["patient_id", "age", "gender", "bmi", "hypertension", "systolic_bp", "diastolic_bp",
        "cholesterol_total", "mmse", "memory_complaints", "diagnosis", "diagnosis_label",
        "age_group", "source_file"]

SCHEMA = """
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

def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    return con

def publish_db(df: pd.DataFrame, run_id: str) -> int:
    """UPSERT du curated dans SQLite (transaction unique : tout ou rien)."""
    data = df[COLS].astype(object).where(df[COLS].notna(), None).values.tolist()
    rows = [r + [run_id] for r in data]
    updates = ", ".join(f"{c}=excluded.{c}" for c in COLS if c != "patient_id")
    sql = (f"INSERT INTO patients ({', '.join(COLS)}, loaded_run_id) "
           f"VALUES ({','.join('?' * (len(COLS) + 1))}) "
           f"ON CONFLICT(patient_id) DO UPDATE SET {updates}, loaded_run_id=excluded.loaded_run_id")
    con = _connect()
    try:
        with con:
            con.executemany(sql, rows)
        return con.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    finally:
        con.close()

def log_run(report: dict) -> None:
    con = _connect()
    try:
        with con:
            con.execute(
                "INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?,?)",
                (report["run_id"], report.get("status"), report.get("source_file"),
                 report.get("input_rows"), report.get("accepted_rows"), report.get("rejected_rows"),
                 report.get("reject_rate"), report.get("duration_seconds"), report.get("error")))
    finally:
        con.close()