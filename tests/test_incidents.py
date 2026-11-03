import hashlib
import logging
import shutil
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pipeline import main  # noqa: E402

SAMPLE = ROOT / "data" / "raw" / "sample_source.csv"   # echantillon de 150 lignes, versionne


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Execute chaque test dans un dossier temporaire avec une copie du contrat."""
    shutil.copytree(ROOT / "config", tmp_path / "config")
    monkeypatch.chdir(tmp_path)
    yield tmp_path
    for h in list(logging.root.handlers):   # libere le fichier de log (Windows)
        h.close()
        logging.root.removeHandler(h)


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(source) -> tuple[int, dict]:
    import json
    code = main(str(source))
    report = json.loads(Path("reports/run_report.json").read_text(encoding="utf-8"))
    return code, report


def make_valid(env) -> Path:
    p = env / "valid.csv"
    shutil.copy(SAMPLE, p)
    return p


def make_schema(env) -> Path:
    p = env / "incident_schema.csv"
    pd.read_csv(SAMPLE).drop(columns=["MMSE"]).to_csv(p, index=False)
    return p


def make_empty(env) -> Path:
    p = env / "incident_empty.csv"
    p.write_bytes(b"")
    return p


def make_all_invalid(env) -> Path:
    p = env / "incident_all_invalid.csv"
    df = pd.read_csv(SAMPLE)
    df["MMSE"] = 99
    df.to_csv(p, index=False)
    return p


def make_missing(env) -> Path:
    return env / "fichier_inexistant.csv"


def test_valid_run_passes(env):
    code, report = run(make_valid(env))
    assert code == 0
    assert report["status"] in ("PASS", "PASS_WITH_WARNINGS")
    assert report["curated_total_rows"] == report["accepted_rows"] > 0


@pytest.mark.parametrize("maker, expected_error", [
    (make_schema, "colonnes manquantes"),
    (make_empty, "vide"),
    (make_all_invalid, "bloquee"),
    (make_missing, "Source introuvable"),
])
def test_incident_fails_and_keeps_curated_intact(env, maker, expected_error):
    # etat sain de reference
    code, ok = run(make_valid(env))
    assert code == 0
    curated_hash = sha("data/curated/dataset.csv")

    # incident
    code, report = run(maker(env))

    assert code == 1
    assert report["status"] == "FAIL"
    assert expected_error in report["error"]
    assert sha("data/curated/dataset.csv") == curated_hash   # curated inchange

    # le run en echec est journalise en base, et le nombre de patients n'a pas bouge
    con = sqlite3.connect("data/curated/alzheimer.db")
    try:
        status = con.execute("SELECT status FROM runs WHERE run_id = ?", (report["run_id"],)).fetchone()
        n_patients = con.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    finally:
        con.close()
    assert status == ("FAIL",)
    assert n_patients == ok["accepted_rows"]


def test_recovery_after_incidents(env):
    _, first = run(make_valid(env))
    for maker in (make_schema, make_empty, make_all_invalid, make_missing):
        assert run(maker(env))[0] == 1
    code, report = run(env / "valid.csv")
    assert code == 0
    assert report["curated_total_rows"] == first["curated_total_rows"]


def test_rerun_is_idempotent(env):
    valid = make_valid(env)
    _, first = run(valid)
    h1 = sha("data/curated/dataset.csv")
    _, second = run(valid)
    assert second["curated_total_rows"] == first["curated_total_rows"]
    assert sha("data/curated/dataset.csv") == h1
    assert len(list(Path("data/raw").glob("alzheimers_*.csv"))) == 1   # pas de re-copie du raw