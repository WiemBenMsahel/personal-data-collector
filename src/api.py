"""API REST en lecture seule sur le produit de donnees (patients, KPI, qualite, litterature).

Lancer : python -m uvicorn --app-dir src api:app --port 8000   puis ouvrir http://localhost:8000/docs
Aucune route d'ecriture : seul le pipeline ecrit dans la base.
"""
import json
from collections import Counter
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

import dbaccess

ROOT = Path(__file__).resolve().parents[1]
PUBMED_FILE = ROOT / "data" / "curated" / "pubmed_articles.jsonl"

app = FastAPI(
    title="AlzheimerDataHub API",
    version="1.0",
    description="Acces en lecture seule aux donnees fiabilisees : patients, indicateurs (KPI), "
                "qualite des executions et litterature PubMed. Jeu de donnees synthetique : "
                "aucune valeur medicale.",
)

PATIENT_COLUMNS = ("patient_id, age, gender, bmi, hypertension, systolic_bp, diastolic_bp, "
                   "cholesterol_total, mmse, memory_complaints, diagnosis, diagnosis_label, "
                   "age_group, source_file, loaded_run_id")


def run_query(sql: str, params: tuple = ()) -> list:
    try:
        return dbaccess.query(sql, params)
    except dbaccess.DatabaseUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"Base indisponible : {exc}")


@app.get("/health", tags=["service"])
def health():
    """Etat du service et de la base."""
    n = run_query("SELECT COUNT(*) AS n FROM patients")[0]["n"]
    return {"status": "ok", "backend": dbaccess.backend(), "patients": n}


@app.get("/kpi/diagnosis", tags=["indicateurs"])
def kpi_by_diagnosis():
    """KPI 1 : MMSE moyen et autres moyennes par diagnostic (vue v_kpi_by_diagnosis)."""
    return run_query("SELECT * FROM v_kpi_by_diagnosis")


@app.get("/kpi/age-groups", tags=["indicateurs"])
def kpi_by_age_group():
    """KPI 2 : part de patients diagnostiques par tranche d'age (vue v_kpi_by_age_group)."""
    return run_query("SELECT * FROM v_kpi_by_age_group")


@app.get("/patients", tags=["patients"])
def list_patients(
    diagnosis: Optional[int] = Query(None, ge=0, le=1, description="0 = non diagnostique, 1 = Alzheimer"),
    min_age: Optional[int] = Query(None, ge=0, le=120),
    max_age: Optional[int] = Query(None, ge=0, le=120),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Liste paginee des patients valides (couche curated)."""
    where, params = [], []
    if diagnosis is not None:
        where.append("diagnosis = ?")
        params.append(diagnosis)
    if min_age is not None:
        where.append("age >= ?")
        params.append(min_age)
    if max_age is not None:
        where.append("age <= ?")
        params.append(max_age)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    total = run_query(f"SELECT COUNT(*) AS n FROM patients {clause}", tuple(params))[0]["n"]
    items = run_query(f"SELECT {PATIENT_COLUMNS} FROM patients {clause} ORDER BY patient_id LIMIT ? OFFSET ?",
                      tuple(params + [limit, offset]))
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@app.get("/patients/{patient_id}", tags=["patients"])
def get_patient(patient_id: int):
    rows = run_query(f"SELECT {PATIENT_COLUMNS} FROM patients WHERE patient_id = ?", (patient_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Patient inconnu")
    return rows[0]


@app.get("/runs", tags=["qualite"])
def list_runs(limit: int = Query(20, ge=1, le=200), status: Optional[str] = None):
    """Journal des executions du pipeline (table runs), les plus recentes d'abord."""
    where, params = "", []
    if status:
        where, params = "WHERE status = ?", [status]
    return run_query("SELECT run_id, status, source_file, input_rows, accepted_rows, rejected_rows, "
                     f"reject_rate, duration_seconds, error FROM runs {where} ORDER BY run_id DESC LIMIT ?",
                     tuple(params + [limit]))


@app.get("/quality/summary", tags=["qualite"])
def quality_summary():
    """KPI 3 : taux de rejet du dernier run valide, et nombre d'executions par statut."""
    last_ok = run_query("SELECT run_id, status, input_rows, accepted_rows, rejected_rows, reject_rate "
                        "FROM runs WHERE status IN ('PASS', 'PASS_WITH_WARNINGS') "
                        "ORDER BY run_id DESC LIMIT 1")
    by_status = run_query("SELECT status, COUNT(*) AS runs FROM runs GROUP BY status ORDER BY status")
    return {"last_valid_run": last_ok[0] if last_ok else None, "runs_by_status": by_status}


@app.get("/literature/summary", tags=["litterature"])
def literature_summary():
    """Resume des articles PubMed collectes (fichier curated JSONL) : par indicateur et par annee."""
    if not PUBMED_FILE.exists():
        raise HTTPException(status_code=404, detail="Aucun curated PubMed : lancez python src/pubmed.py")
    articles = [json.loads(line) for line in PUBMED_FILE.read_text("utf-8").splitlines() if line.strip()]
    by_indicator = Counter(ind for a in articles for ind in a.get("indicators", []))
    by_year = Counter(a["year"] for a in articles if a.get("year"))
    return {"articles": len(articles), "by_indicator": dict(by_indicator),
            "by_year": dict(sorted(by_year.items()))}