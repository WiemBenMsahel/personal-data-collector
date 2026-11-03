import pandas as pd
from pathlib import Path

d = Path("data/source_download")
df = pd.read_csv(d / "alzheimers_disease_data.csv")

(d / "incident_empty.csv").write_text("", encoding="utf-8")                       # fichier vide
df.rename(columns={"MMSE": "MMSE_score"}).to_csv(d / "incident_schema.csv", index=False)   # schema change
bad = df.copy(); bad["MMSE"] = 99
bad.to_csv(d / "incident_all_invalid.csv", index=False)                           # valeurs impossibles
print("Fichiers d'incident crees dans", d)