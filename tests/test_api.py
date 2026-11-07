import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import dbaccess  # noqa: E402
import api  # noqa: E402

SCHEMA = """
CREATE TABLE patients (patient_id INTEGER PRIMARY KEY, age INTEGER, gender TEXT, bmi REAL, hypertension INTEGER,
  systolic_bp INTEGER, diastolic_bp INTEGER, cholesterol_total REAL, mmse REAL, memory_complaints INTEGER,
  diagnosis INTEGER, diagnosis_label TEXT, age_group TEXT, source_file TEXT, loaded_run_id TEXT);
CREATE TABLE runs (run_id TEXT PRIMARY KEY, status TEXT, source_file TEXT, input_rows INTEGER, accepted_rows INTEGER,
  rejected_rows INTEGER, reject_rate REAL, duration_seconds REAL, error TEXT);
CREATE VIEW v_kpi_by_diagnosis AS SELECT diagnosis_label, COUNT(*) AS patients, ROUND(AVG(mmse), 1) AS mmse_moyen
  FROM patients GROUP BY diagnosis_label;
CREATE VIEW v_kpi_by_age_group AS SELECT age_group, COUNT(*) AS patients, SUM(diagnosis) AS diagnostiques
  FROM patients GROUP BY age_group;
"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO patients VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        (1, 70, "Male", 25.0, 0, 130, 80, 200.0, 12.0, 1, 1, "Alzheimer", "65-74", "f.csv", "r1"),
        (2, 80, "Female", 27.0, 1, 140, 85, 220.0, 20.0, 0, 0, "Non-Alzheimer", "75-84", "f.csv", "r1"),
        (3, 60, "Female", 22.0, 0, 120, 75, 190.0, 25.0, 0, 0, "Non-Alzheimer", "<65", "f.csv", "r1"),
    ])
    con.executemany("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?)", [
        ("20261107T090000Z", "PASS_WITH_WARNINGS", "f.csv", 4, 3, 1, 0.25, 0.2, None),
        ("20261107T100000Z", "FAIL", "g.csv", None, None, None, None, 0.1, "Source introuvable"),
    ])
    con.commit()
    con.close()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(dbaccess, "SQLITE_PATH", db)
    return TestClient(api.app)


def test_health_and_kpis(client):
    assert client.get("/health").json() == {"status": "ok", "backend": "sqlite", "patients": 3}
    kpi = {r["diagnosis_label"]: r["mmse_moyen"] for r in client.get("/kpi/diagnosis").json()}
    assert kpi == {"Alzheimer": 12.0, "Non-Alzheimer": 22.5}
    assert len(client.get("/kpi/age-groups").json()) == 3


def test_patients_filters_and_pagination(client):
    body = client.get("/patients", params={"diagnosis": 0, "min_age": 61}).json()
    assert body["total"] == 1 and body["items"][0]["patient_id"] == 2
    assert len(client.get("/patients", params={"limit": 2}).json()["items"]) == 2
    assert client.get("/patients", params={"diagnosis": 5}).status_code == 422  # validation des entrees


def test_unknown_patient_and_injection_attempt(client):
    assert client.get("/patients/999").status_code == 404
    assert client.get("/patients", params={"min_age": "1; DROP TABLE patients"}).status_code == 422
    assert client.get("/health").json()["patients"] == 3  # la table est intacte


def test_quality_and_runs(client):
    summary = client.get("/quality/summary").json()
    assert summary["last_valid_run"]["run_id"] == "20261107T090000Z"
    assert {r["status"]: r["runs"] for r in summary["runs_by_status"]} == {"FAIL": 1, "PASS_WITH_WARNINGS": 1}
    assert client.get("/runs", params={"status": "FAIL"}).json()[0]["error"] == "Source introuvable"


def test_api_is_read_only(client):
    assert client.post("/patients", json={}).status_code == 405
    assert client.delete("/patients/1").status_code == 405


def test_database_unavailable_returns_503(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(dbaccess, "SQLITE_PATH", tmp_path / "absente.db")
    assert TestClient(api.app).get("/health").status_code == 503