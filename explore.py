import pandas as pd
df = pd.read_csv("data/source_download/alzheimers_disease_data.csv")
print(df.shape)
print(df.columns.tolist())
print(df.head())