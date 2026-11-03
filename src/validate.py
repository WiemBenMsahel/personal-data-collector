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

# (nom, condition de validite, action)
RULES = [
    ("patient_id_present",    lambda d: d["PatientID"].notna(),                        "reject"),
    ("age_valid",             lambda d: num(d["Age"]).between(0, 120),                 "reject"),
    ("mmse_range",            lambda d: num(d["MMSE"]).between(0, 30),                 "reject"),
    ("diagnosis_domain",      lambda d: num(d["Diagnosis"]).isin([0, 1]),              "reject"),
    ("bp_coherent",           lambda d: num(d["DiastolicBP"]) < num(d["SystolicBP"]),  "reject"),
    ("cholesterol_plausible", lambda d: num(d["CholesterolTotal"]).between(100, 400),  "flag"),
]

def validate(df: pd.DataFrame):
    df = df.copy()
    df["reject_reason"] = ""
    stats = {}
    dup = df.duplicated("PatientID", keep="first") & df["PatientID"].notna()
    stats["duplicate_patient_id"] = int(dup.sum())
    df.loc[dup, "reject_reason"] += "duplicate_patient_id;"
    for name, cond, action in RULES:
        fail = ~cond(df)
        stats[name] = int(fail.sum())
        if action == "reject":
            df.loc[fail, "reject_reason"] += name + ";"
    rejected = df[df["reject_reason"] != ""]
    accepted = df[df["reject_reason"] == ""].drop(columns="reject_reason")
    return accepted, rejected, stats