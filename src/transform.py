import pandas as pd

COLS = {"PatientID": "patient_id", "Age": "age", "Gender": "gender", "BMI": "bmi",
        "Hypertension": "hypertension", "SystolicBP": "systolic_bp", "DiastolicBP": "diastolic_bp",
        "CholesterolTotal": "cholesterol_total", "MMSE": "mmse",
        "MemoryComplaints": "memory_complaints", "Diagnosis": "diagnosis"}

def transform(df: pd.DataFrame, source_file: str) -> pd.DataFrame:
    out = df[list(COLS)].rename(columns=COLS)   # DoctorInCharge exclu
    out["patient_id"] = out["patient_id"].astype(int)
    out["diagnosis"] = out["diagnosis"].astype(int)
    out["gender"] = out["gender"].map({0: "Male", 1: "Female"})
    out["diagnosis_label"] = out["diagnosis"].map({0: "Non-Alzheimer", 1: "Alzheimer"})
    out["age_group"] = pd.cut(out["age"], [0, 64, 74, 84, 200],
                              labels=["<65", "65-74", "75-84", "85+"]).astype(str)
    out["source_file"] = source_file
    return out