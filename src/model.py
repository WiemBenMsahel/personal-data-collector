"""Usage de la base : classification du diagnostic a partir de la couche silver (curated).

Objectif : verifier quels indicateurs portent un signal, pas faire de la prediction clinique.
Donnees synthetiques : aucune valeur medicale. Le modele lit uniquement le curated valide
(donc des lignes qui ont passe les regles de qualite) et le rapport garde le hash du fichier lu.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

CURATED = Path("data/curated/dataset.csv")
REPORT = Path("reports/model_report.json")
TARGET = "diagnosis"
# Seulement des indicateurs cliniques. Exclus : identifiants, source_file, diagnosis_label
# (copie de la cible) et age_group (derive de age).
FEATURES = ["age", "gender", "bmi", "hypertension", "systolic_bp", "diastolic_bp",
            "cholesterol_total", "mmse", "memory_complaints"]
SEED = 42
BASELINE = "baseline_majoritaire"


def build_models() -> dict:
    imputer = lambda: SimpleImputer(strategy="median")  # noqa: E731
    return {
        BASELINE: make_pipeline(imputer(), DummyClassifier(strategy="most_frequent")),
        "regression_logistique": make_pipeline(
            imputer(), StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced")),
        "foret_aleatoire": make_pipeline(
            imputer(), RandomForestClassifier(n_estimators=200, max_depth=6, min_samples_leaf=10,
                                              class_weight="balanced", random_state=SEED)),
    }


def train_and_evaluate(df: pd.DataFrame) -> dict:
    missing = [c for c in FEATURES + [TARGET] if c not in df.columns]
    if missing:
        raise ValueError(f"Colonnes absentes du curated : {missing}")
    df = df.dropna(subset=[TARGET])
    y = df[TARGET].astype(int)
    X = pd.get_dummies(df[FEATURES], drop_first=True).astype(float)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=SEED)

    metrics, fitted = {}, {}
    for name, model in build_models().items():
        cv_auc = cross_val_score(model, X_tr, y_tr, cv=5, scoring="roc_auc")
        model.fit(X_tr, y_tr)
        pred = model.predict(X_te)
        proba = model.predict_proba(X_te)[:, 1]
        metrics[name] = {
            "cv_roc_auc_mean": round(float(cv_auc.mean()), 3),
            "cv_roc_auc_std": round(float(cv_auc.std()), 3),
            "test_accuracy": round(float(accuracy_score(y_te, pred)), 3),
            "test_precision": round(float(precision_score(y_te, pred, zero_division=0)), 3),
            "test_recall": round(float(recall_score(y_te, pred, zero_division=0)), 3),
            "test_f1": round(float(f1_score(y_te, pred, zero_division=0)), 3),
            "test_roc_auc": round(float(roc_auc_score(y_te, proba)), 3),
        }
        fitted[name] = model

    # Le modele retenu est choisi sur la validation croisee (train), jamais sur le jeu de test.
    best = max((n for n in metrics if n != BASELINE), key=lambda n: metrics[n]["cv_roc_auc_mean"])
    imp = permutation_importance(fitted[best], X_te, y_te, scoring="roc_auc",
                                 n_repeats=10, random_state=SEED)
    importances = sorted(
        ({"indicateur": c, "baisse_auc_moyenne": round(float(m), 4)}
         for c, m in zip(X.columns, imp.importances_mean)),
        key=lambda d: -d["baisse_auc_moyenne"])
    return {
        "n_rows": int(len(df)),
        "n_train": int(len(X_tr)),
        "n_test": int(len(X_te)),
        "positive_rate": round(float(y.mean()), 3),
        "features": list(X.columns),
        "metrics": metrics,
        "selected_model": best,
        "permutation_importance_test": importances,
    }


def main() -> int:
    if not CURATED.exists():
        sys.exit(f"{CURATED} introuvable : lancez d'abord python src/pipeline.py")
    sha256 = hashlib.sha256(CURATED.read_bytes()).hexdigest()
    result = train_and_evaluate(pd.read_csv(CURATED))
    report = {
        "pipeline": "diagnosis-classifier",
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "curated_file": str(CURATED),
        "curated_sha256": sha256,
        "seed": SEED,
        **result,
        "avertissement": "Donnees synthetiques : resultat sans valeur medicale.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Lignes : {result['n_rows']} (train {result['n_train']}, test {result['n_test']}), "
          f"part de diagnostiques : {result['positive_rate']}")
    print(f"{'modele':<24}{'AUC CV':>9}{'AUC test':>10}{'accuracy':>10}{'rappel':>9}{'F1':>7}")
    for name, m in result["metrics"].items():
        print(f"{name:<24}{m['cv_roc_auc_mean']:>9}{m['test_roc_auc']:>10}"
              f"{m['test_accuracy']:>10}{m['test_recall']:>9}{m['test_f1']:>7}")
    print(f"Modele retenu (AUC CV) : {result['selected_model']}")
    print("Importance par permutation (baisse d'AUC sur le test) :")
    for row in result["permutation_importance_test"]:
        print(f"  {row['indicateur']:<20}{row['baisse_auc_moyenne']:>8}")
    print(f"Rapport : {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())