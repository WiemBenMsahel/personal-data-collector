import pandas as pd


def profile(df: pd.DataFrame) -> dict:
    return {
        "rows": int(df.shape[0]), "columns": int(df.shape[1]),
        "dtypes": {c: str(t) for c, t in df.dtypes.items()},
        "missing_rate": df.isna().mean().round(4).to_dict(),
        "duplicates": int(df.duplicated().sum()),
        "min_max": {c: [float(df[c].min()), float(df[c].max())]
                    for c in ["Age", "MMSE", "SystolicBP", "DiastolicBP", "CholesterolTotal"] if c in df},
        "diagnosis_counts": df["Diagnosis"].value_counts(dropna=False).to_dict(),
    }


num = lambda s: pd.to_numeric(s, errors="coerce")


def build_condition(rule: dict, src: dict):
    """Transforme une regle du contrat en fonction qui renvoie True si la ligne est valide."""
    col, t = src[rule["column"]], rule["type"]
    if t == "not_null":
        return lambda d: d[col].notna()
    if t == "range":
        return lambda d: num(d[col]).between(rule["min"], rule["max"])
    if t == "domain":
        return lambda d: num(d[col]).isin(rule["values"])
    if t == "less_than":
        other = src[rule["other"]]
        return lambda d: num(d[col]) < num(d[other])
    raise ValueError(f"Type de regle inconnu dans le contrat : {t}")


def validate(df: pd.DataFrame, contract: dict):
    src = contract["_src"]
    key = src[contract["business_key"]]
    df = df.copy()
    df["reject_reason"] = ""
    stats = {}
    for rule in contract["quality_rules"]:
        if rule["type"] == "unique":
            fail = df.duplicated(src[rule["column"]], keep="first") & df[key].notna()
        else:
            fail = ~build_condition(rule, src)(df)
        stats[rule["name"]] = int(fail.sum())
        if rule["action"] == "reject":
            df.loc[fail, "reject_reason"] += rule["name"] + ";"
    rejected = df[df["reject_reason"] != ""]
    accepted = df[df["reject_reason"] == ""].drop(columns="reject_reason")
    return accepted, rejected, stats


def check_schema(df: pd.DataFrame, contract: dict) -> None:
    if df.empty:
        raise ValueError("Fichier vide : aucune ligne a traiter")
    missing = [c["source"] for c in contract["columns"] if c["source"] not in df.columns]
    if missing:
        raise ValueError(f"Changement de schema : colonnes manquantes {missing}")
    for c in contract["columns"]:
        if c["type"] in ("integer", "float"):
            values = df[c["source"]].dropna()
            if len(values) and num(values).isna().all():
                raise ValueError(f"Changement de schema : colonne {c['source']} non numerique")