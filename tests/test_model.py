import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import model  # noqa: E402


def make_df(n=400, seed=0):
    rng = np.random.default_rng(seed)
    mmse = rng.uniform(0, 30, n)
    diagnosis = (mmse + rng.normal(0, 6, n) < 14).astype(int)  # le MMSE porte le signal
    return pd.DataFrame({
        "patient_id": np.arange(n),
        "age": rng.integers(60, 95, n),
        "gender": rng.integers(0, 2, n),
        "bmi": rng.normal(27, 4, n),
        "hypertension": rng.integers(0, 2, n),
        "systolic_bp": rng.integers(100, 180, n),
        "diastolic_bp": rng.integers(60, 99, n),
        "cholesterol_total": rng.normal(225, 40, n),
        "mmse": mmse,
        "memory_complaints": rng.integers(0, 2, n),
        "diagnosis": diagnosis,
        "diagnosis_label": np.where(diagnosis == 1, "Alzheimer", "Non-Alzheimer"),
    })


def test_model_uses_only_clinical_features():
    result = model.train_and_evaluate(make_df())
    for forbidden in ("diagnosis", "diagnosis_label", "patient_id", "source_file", "age_group"):
        assert forbidden not in result["features"]


def test_model_beats_baseline_and_finds_mmse():
    result = model.train_and_evaluate(make_df())
    best = result["selected_model"]
    assert result["metrics"][best]["test_roc_auc"] > result["metrics"][model.BASELINE]["test_roc_auc"]
    assert result["permutation_importance_test"][0]["indicateur"] == "mmse"


def test_model_rejects_missing_columns():
    with pytest.raises(ValueError):
        model.train_and_evaluate(make_df().drop(columns=["mmse"]))