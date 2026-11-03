import pandas as pd
df = pd.read_csv("data/source_download/alzheimers_disease_data.csv")
df.loc[0, "MMSE"] = 99          # hors plage 0-30
df.loc[1, "Age"] = 250          # age impossible
df = pd.concat([df, df.iloc[[2]]])   # doublon de PatientID
df.to_csv("data/source_download/dirty.csv", index=False)