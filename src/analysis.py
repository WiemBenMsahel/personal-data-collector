import pandas as pd
import matplotlib.pyplot as plt

d = pd.read_csv("data/curated/dataset.csv")

print("Moyennes par diagnostic :")
print(d.groupby("diagnosis_label")[["mmse", "systolic_bp", "cholesterol_total", "age"]].mean().round(1))
print("\nRepartition diagnostic par tranche d'age :")
print(pd.crosstab(d["age_group"], d["diagnosis_label"], normalize="index").round(2))

d.groupby("diagnosis_label")["mmse"].mean().plot(kind="bar", title="MMSE moyen par diagnostic")
plt.ylabel("MMSE")
plt.tight_layout()
plt.savefig("reports/mmse_by_diagnosis.png")