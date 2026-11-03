import sqlite3
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

DB_PATH = Path("data/curated/alzheimer.db")

st.set_page_config(page_title="AlzheimerDataHub", layout="wide")
st.title("AlzheimerDataHub")
st.caption("Quels indicateurs cliniques distinguent les patients diagnostiqués Alzheimer des autres ?")

if not DB_PATH.exists():
    st.error("Base introuvable. Lancez d'abord : python src/pipeline.py")
    st.stop()


@st.cache_data(ttl=30)
def query(sql: str) -> pd.DataFrame:
    con = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(sql, con)
    finally:
        con.close()


diag = query("SELECT * FROM v_kpi_by_diagnosis")
ages = query("SELECT * FROM v_kpi_by_age_group")
runs = query("SELECT * FROM runs ORDER BY run_id DESC")

# --- Indicateurs clés ---
mmse = dict(zip(diag["diagnosis_label"], diag["mmse_moyen"]))

col1, col2, col3, col4 = st.columns(4)
col1.metric("Patients en base", int(diag["patients"].sum()))

if "Alzheimer" in mmse:
    col2.metric("MMSE moyen : Alzheimer", float(mmse["Alzheimer"]))
if "Non-Alzheimer" in mmse:
    col3.metric("MMSE moyen : Non-Alzheimer", float(mmse["Non-Alzheimer"]))

ok_runs = runs[runs["status"].isin(["PASS", "PASS_WITH_WARNINGS"])]
if not ok_runs.empty:
    last = ok_runs.iloc[0]
    rate = 100 * float(last["rejected_rows"]) / float(last["input_rows"])
    col4.metric("Taux de rejet (dernier run valide)", f"{rate:.1f} %")

# --- KPI 1 : MMSE par diagnostic ---
st.subheader("1. MMSE moyen selon le diagnostic")
left, right = st.columns(2)
left.dataframe(diag, hide_index=True)
right.bar_chart(diag.set_index("diagnosis_label")["mmse_moyen"])

# --- KPI 2 : part de diagnostiqués par tranche d'âge ---
st.subheader("2. Part de patients diagnostiqués par tranche d'âge")
left, right = st.columns(2)
left.dataframe(ages, hide_index=True)
chart = alt.Chart(ages).mark_bar().encode(
    x=alt.X("age_group", sort=None, title="Tranche d'âge"),
    y=alt.Y("pct_diagnostiques", title="% diagnostiqués"),
)
right.altair_chart(chart)

# --- KPI 3 : journal des exécutions ---
st.subheader("3. Journal des exécutions du pipeline")
st.dataframe(runs, hide_index=True)

st.caption("Jeu de données synthétique (Kaggle, CC BY 4.0) : aucune conclusion médicale.")