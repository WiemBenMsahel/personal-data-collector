import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd
import pytest
from contract import load_contract
from validate import validate, check_schema

VALID = {"PatientID": 1, "Age": 70, "Gender": 0, "BMI": 25.0, "Hypertension": 0,
         "SystolicBP": 130, "DiastolicBP": 80, "CholesterolTotal": 200.0,
         "MMSE": 20.0, "MemoryComplaints": 0, "Diagnosis": 0}

def df_of(*overrides):
    rows = []
    for i, o in enumerate(overrides, start=1):
        rows.append({**VALID, "PatientID": i, **o})
    return pd.DataFrame(rows)

@pytest.fixture
def contract():
    return load_contract()

def test_threshold_comes_from_contract(contract):
    assert contract["thresholds"]["max_reject_rate"] == 0.20

def test_missing_column_fails_schema(contract):
    df = df_of({}).drop(columns=["MMSE"])
    with pytest.raises(ValueError, match="colonnes manquantes"):
        check_schema(df, contract)

def test_empty_file_fails_schema(contract):
    with pytest.raises(ValueError, match="vide"):
        check_schema(df_of({}).iloc[0:0], contract)

def test_rules_are_applied_from_contract(contract):
    df = df_of({}, {"MMSE": 45.0}, {"DiastolicBP": 150})
    accepted, rejected, stats = validate(df, contract)
    assert len(accepted) == 1
    assert stats["mmse_range"] == 1 and stats["bp_coherent"] == 1

def test_changing_contract_changes_behavior(contract):
    df = df_of({"MMSE": 25.0})
    assert len(validate(df, contract)[0]) == 1
    for r in contract["quality_rules"]:
        if r["name"] == "mmse_range":
            r["max"] = 20
    assert len(validate(df, contract)[0]) == 0   # pas de divergence code/contrat