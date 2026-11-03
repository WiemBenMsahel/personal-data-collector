import sys; sys.path.insert(0, "src")
import pandas as pd
from validate import validate

def make(**over):
    base = dict(PatientID=1, Age=70, MMSE=20, Diagnosis=1, SystolicBP=130, DiastolicBP=80, CholesterolTotal=200)
    base.update(over); return base

def test_rejects_invalid_rows():
    df = pd.DataFrame([make(), make(PatientID=2, MMSE=45), make(PatientID=3, DiastolicBP=150),
                       make(PatientID=4, Diagnosis=5), make(PatientID=1)])
    accepted, rejected, stats = validate(df)
    assert len(accepted) == 1
    assert stats["mmse_range"] == 1 and stats["bp_coherent"] == 1
    assert stats["diagnosis_domain"] == 1 and stats["duplicate_patient_id"] == 1