"""Tableau de bord AlzheimerDataHub (Streamlit) : indicateurs, qualite, litterature, modele, pipeline.

Lecture seule. Base : PostgreSQL si DATABASE_URL est definie, sinon SQLite (data/curated/alzheimer.db).
Lancer : streamlit run src/app.py
"""
import json
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dbaccess  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
PUBMED_FILE = ROOT / "data" / "curated" / "pubmed_articles.jsonl"
AGE_ORDER = ["<65", "65-74", "75-84", "85+"]
LABEL_COLORS = {"Alzheimer": "#E4572E", "Non-Alzheimer": "#2A9D8F"}
STATUS_ICON = {"PASS": "🟢", "PASS_WITH_WARNINGS": "🟠", "FAIL": "🔴"}
STATUS_COLOR = {"SUCCESS": "#2A9D8F", "FAILED": "#E4572E", "UPSTREAM_FAILED": "#F4A261", "NONE": "#94A3B8"}
INDICATOR_LABELS = {"mmse": "MMSE", "blood_pressure": "Tension", "cholesterol": "Cholestérol", "age": "Âge"}
GENERIC_MESH = {"Humans", "Alzheimer Disease", "Female", "Male", "Aged", "Aged, 80 and over", "Middle Aged",
                "Adult", "Animals", "Mice", "Risk Factors", "Age Factors"}

st.set_page_config(page_title="AlzheimerDataHub", page_icon="🧠", layout="wide")

st.markdown("""
<style>
#MainMenu, footer {visibility: hidden;}
.block-container {padding-top: 1.6rem; max-width: 1250px;}
.hero {background: linear-gradient(135deg, #1e3a8a 0%, #4f46e5 55%, #06b6d4 100%);
       padding: 1.7rem 2rem; border-radius: 18px; color: #fff; margin-bottom: 1.2rem;
       box-shadow: 0 10px 30px rgba(79,70,229,.25);}
.hero h1 {margin: 0; font-size: 2rem; color: #fff;}
.hero p {margin: .35rem 0 0 0; opacity: .92; font-size: 1.02rem;}
.badge {display: inline-block; padding: .2rem .7rem; border-radius: 999px; font-size: .8rem; font-weight: 600;
        background: rgba(255,255,255,.18); margin-right: .45rem; margin-top: .7rem;}
div[data-testid="stMetric"] {background: rgba(128,128,128,.08); border: 1px solid rgba(128,128,128,.22);
       border-radius: 14px; padding: .8rem 1rem; box-shadow: 0 2px 8px rgba(0,0,0,.05);}
div[data-testid="stMetricLabel"] p {font-size: .85rem; opacity: .8;}
button[data-baseweb="tab"] {font-weight: 600; font-size: 1rem;}
.note {border-left: 4px solid #4f46e5; background: rgba(79,70,229,.08); padding: .6rem 1rem;
       border-radius: 6px; margin: .5rem 0 1rem 0;}
</style>
""", unsafe_allow_html=True)


# ---------- Chargement des donnees ----------
def to_frame(rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in df.columns:  # PostgreSQL renvoie des Decimal : on les convertit en nombres
        try:
            df[col] = pd.to_numeric(df[col])
        except (ValueError, TypeError):
            pass
    return df


@st.cache_data(ttl=60)
def load_table(sql: str) -> pd.DataFrame:
    return to_frame(dbaccess.query(sql))


def read_json(path: Path):
    return json.loads(path.read_text("utf-8")) if path.exists() else None


@st.cache_data(ttl=60)
def load_articles() -> pd.DataFrame:
    if not PUBMED_FILE.exists():
        return pd.DataFrame()
    lines = [json.loads(x) for x in PUBMED_FILE.read_text("utf-8").splitlines() if x.strip()]
    return pd.DataFrame(lines)


try:
    patients = load_table("SELECT * FROM patients")
    runs = load_table("SELECT * FROM runs ORDER BY run_id DESC")
except dbaccess.DatabaseUnavailable as exc:
    st.error(f"Base indisponible : {exc}")
    st.info("Lancez d'abord `python src/pipeline.py` (SQLite) ou démarrez PostgreSQL (`docker compose up -d postgres`).")
    st.stop()

valid_runs = runs[runs["status"].isin(["PASS", "PASS_WITH_WARNINGS"])] if not runs.empty else runs
last_run = valid_runs.iloc[0] if not valid_runs.empty else None

# ---------- En-tete ----------
st.markdown(f"""
<div class="hero">
  <h1>🧠 AlzheimerDataHub</h1>
  <p>Quels indicateurs cliniques distinguent les patients diagnostiqués Alzheimer des autres ?</p>
  <span class="badge">Base : {dbaccess.backend()}</span>
  <span class="badge">{len(patients):,} patients fiabilisés</span>
  <span class="badge">{len(runs)} exécutions tracées</span>
  <span class="badge">Données synthétiques</span>
</div>
""".replace(",", " "), unsafe_allow_html=True)

# ---------- Filtres ----------
st.sidebar.header("Filtres")
age_min, age_max = int(patients["age"].min()), int(patients["age"].max())
age_range = st.sidebar.slider("Âge", age_min, age_max, (age_min, age_max))
labels = sorted(patients["diagnosis_label"].dropna().unique())
chosen_labels = st.sidebar.multiselect("Diagnostic", labels, default=labels)
genders = sorted(patients["gender"].dropna().astype(str).unique())
chosen_genders = st.sidebar.multiselect("Genre", genders, default=genders)
st.sidebar.caption("Les filtres s'appliquent à l'onglet Indicateurs et aux cartes du haut.")

df = patients[patients["age"].between(*age_range)
              & patients["diagnosis_label"].isin(chosen_labels)
              & patients["gender"].astype(str).isin(chosen_genders)]

# ---------- Cartes ----------
alz = df[df["diagnosis_label"] == "Alzheimer"]
non = df[df["diagnosis_label"] == "Non-Alzheimer"]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Patients (filtre)", f"{len(df):,}".replace(",", " "))
c2.metric("Part diagnostiquée", f"{100 * df['diagnosis'].mean():.1f} %" if len(df) else "n/a")
c3.metric("MMSE moyen Alzheimer", f"{alz['mmse'].mean():.1f}" if len(alz) else "n/a")
c4.metric("MMSE moyen Non-Alzheimer", f"{non['mmse'].mean():.1f}" if len(non) else "n/a")
if last_run is not None and pd.notna(last_run.get("reject_rate")):
    c5.metric("Taux de rejet (dernier run)", f"{100 * last_run['reject_rate']:.1f} %")
else:
    c5.metric("Taux de rejet (dernier run)", "n/a")

tab_kpi, tab_quality, tab_lit, tab_model, tab_pipe = st.tabs(
    ["📊 Indicateurs", "🛡️ Qualité & incidents", "📚 Littérature", "🤖 Modèle", "⚙️ Pipeline"])

# ---------- Onglet 1 : indicateurs ----------
with tab_kpi:
    if df.empty:
        st.warning("Aucun patient avec ces filtres.")
    else:
        colors = alt.Scale(domain=list(LABEL_COLORS), range=list(LABEL_COLORS.values()))
        left, right = st.columns(2)
        with left:
            st.subheader("MMSE selon le diagnostic")
            hist = alt.Chart(df).mark_bar(opacity=0.75, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                x=alt.X("mmse:Q", bin=alt.Bin(maxbins=20), title="MMSE"),
                y=alt.Y("count()", stack=None, title="Patients"),
                color=alt.Color("diagnosis_label:N", scale=colors, title="Diagnostic"),
                tooltip=["diagnosis_label:N", "count()"]).properties(height=320)
            st.altair_chart(hist)
        with right:
            st.subheader("Part diagnostiquée par tranche d'âge")
            by_age = (df.groupby("age_group")["diagnosis"].agg(["mean", "count"]).reset_index()
                      .rename(columns={"mean": "part", "count": "patients"}))
            by_age["part_pct"] = (100 * by_age["part"]).round(1)
            bars = alt.Chart(by_age).mark_bar(color="#4f46e5", cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                x=alt.X("age_group:N", sort=AGE_ORDER, title="Tranche d'âge"),
                y=alt.Y("part_pct:Q", title="% diagnostiqués"),
                tooltip=["age_group", "patients", "part_pct"])
            labels_ = bars.mark_text(dy=-8, fontWeight="bold").encode(text="part_pct:Q")
            st.altair_chart((bars + labels_).properties(height=320))

        st.subheader("Quel indicateur distingue le mieux les deux groupes ?")
        numeric = [c for c in ["age", "bmi", "systolic_bp", "diastolic_bp", "cholesterol_total", "mmse"]
                   if c in df.columns]
        if len(alz) > 1 and len(non) > 1:
            effects = []
            for col in numeric:
                pooled = (((len(alz) - 1) * alz[col].var() + (len(non) - 1) * non[col].var())
                          / (len(alz) + len(non) - 2)) ** 0.5
                effects.append({"indicateur": col, "écart standardisé": (alz[col].mean() - non[col].mean()) / pooled})
            eff = pd.DataFrame(effects)
            eff["intensité"] = eff["écart standardisé"].abs()
            chart = alt.Chart(eff).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4).encode(
                y=alt.Y("indicateur:N", sort="-x", title=None),
                x=alt.X("intensité:Q", title="Écart standardisé entre Alzheimer et Non-Alzheimer (valeur absolue)"),
                color=alt.condition(alt.datum.intensité == eff["intensité"].max(),
                                    alt.value("#E4572E"), alt.value("#94A3B8")),
                tooltip=["indicateur", alt.Tooltip("écart standardisé:Q", format=".2f")]).properties(height=240)
            st.altair_chart(chart)
            st.markdown('<div class="note">Plus la barre est longue, plus l\'indicateur sépare les deux groupes. '
                        'Jeu synthétique : à lire comme une démonstration, pas comme un résultat médical.</div>',
                        unsafe_allow_html=True)
        means = df.groupby("diagnosis_label")[numeric].mean().round(1)
        st.dataframe(means)

# ---------- Onglet 2 : qualité ----------
with tab_quality:
    q1, q2, q3 = st.columns(3)
    q1.metric("Exécutions", len(runs))
    q2.metric("Échecs (FAIL)", int((runs["status"] == "FAIL").sum()))
    q3.metric("Dernier run valide", last_run["run_id"] if last_run is not None else "n/a")

    st.subheader("Taux de rejet par exécution")
    with_rate = runs.dropna(subset=["reject_rate"]).copy()
    if not with_rate.empty:
        with_rate["taux_rejet_pct"] = 100 * with_rate["reject_rate"]
        pts = alt.Chart(with_rate).mark_line(point=True, color="#4f46e5").encode(
            x=alt.X("run_id:N", title="Exécution", sort=None, axis=alt.Axis(labels=False)),
            y=alt.Y("taux_rejet_pct:Q", title="% rejeté"),
            tooltip=["run_id", "status", alt.Tooltip("taux_rejet_pct:Q", format=".1f")])
        limit = alt.Chart(pd.DataFrame({"y": [20]})).mark_rule(strokeDash=[6, 4], color="#E4572E").encode(y="y:Q")
        st.altair_chart((pts + limit).properties(height=260))
        st.caption("Ligne rouge : seuil de blocage de la publication (20 %, défini dans le contrat).")

    last_report = read_json(REPORTS / "run_report.json")
    if last_report and last_report.get("rule_failures"):
        st.subheader("Échecs par règle (dernier rapport)")
        rf = pd.DataFrame({"règle": list(last_report["rule_failures"]),
                           "lignes": list(last_report["rule_failures"].values())})
        st.altair_chart(alt.Chart(rf).mark_bar(color="#F4A261", cornerRadiusTopRight=4,
                                               cornerRadiusBottomRight=4).encode(
            y=alt.Y("règle:N", sort="-x", title=None), x=alt.X("lignes:Q", title="Lignes en échec"),
            tooltip=["règle", "lignes"]).properties(height=250))

    st.subheader("Journal des exécutions")
    log = runs.copy()
    log.insert(0, " ", log["status"].map(STATUS_ICON).fillna("⚪"))
    st.dataframe(log, hide_index=True)
    fails = runs[runs["status"] == "FAIL"]
    if not fails.empty:
        st.subheader("Incidents détectés")
        for _, row in fails.head(8).iterrows():
            st.error(f"**{row['run_id']}** : {row.get('error') or 'erreur non renseignée'}")

# ---------- Onglet 3 : littérature ----------
with tab_lit:
    articles = load_articles()
    if articles.empty:
        st.info("Aucun article : lancez `python src/pubmed.py` pour collecter la littérature PubMed.")
    else:
        st.markdown('<div class="note">Seconde source : métadonnées d\'articles PubMed (stockées dans MongoDB Atlas, '
                    'affichées ici depuis le curated JSONL). Le recoupement avec les patients se fait par '
                    '<b>indicateur</b>, pas par patient.</div>', unsafe_allow_html=True)
        exploded = articles.explode("indicators")
        exploded["indicateur"] = exploded["indicators"].map(INDICATOR_LABELS).fillna(exploded["indicators"])
        l1, l2 = st.columns(2)
        with l1:
            st.subheader("Articles par indicateur")
            by_ind = exploded.groupby("indicateur").size().reset_index(name="articles")
            st.altair_chart(alt.Chart(by_ind).mark_bar(color="#06b6d4", cornerRadiusTopLeft=4,
                                                       cornerRadiusTopRight=4).encode(
                x=alt.X("indicateur:N", sort="-y", title=None), y=alt.Y("articles:Q"),
                tooltip=["indicateur", "articles"]).properties(height=280))
        with l2:
            st.subheader("Articles par année")
            by_year = articles.groupby("year").size().reset_index(name="articles")
            st.altair_chart(alt.Chart(by_year).mark_area(color="#4f46e5", opacity=0.5, line=True).encode(
                x=alt.X("year:O", title="Année"), y=alt.Y("articles:Q"),
                tooltip=["year", "articles"]).properties(height=280))
        mesh = pd.Series([m for terms in articles["mesh_terms"] for m in terms if m not in GENERIC_MESH])
        if not mesh.empty:
            st.subheader("Termes MeSH les plus fréquents")
            top = mesh.value_counts().head(12).rename_axis("terme").reset_index(name="articles")
            st.altair_chart(alt.Chart(top).mark_bar(color="#2A9D8F", cornerRadiusTopRight=4,
                                                    cornerRadiusBottomRight=4).encode(
                y=alt.Y("terme:N", sort="-x", title=None), x=alt.X("articles:Q"),
                tooltip=["terme", "articles"]).properties(height=330))
        st.subheader("Explorer les articles")
        search = st.text_input("Filtrer par mot du titre")
        view = articles[["pmid", "title", "journal", "year", "indicators"]].copy()
        view["indicators"] = view["indicators"].map(lambda xs: ", ".join(xs))
        if search:
            view = view[view["title"].str.contains(search, case=False, na=False)]
        st.dataframe(view.sort_values("year", ascending=False), hide_index=True)

# ---------- Onglet 4 : modèle ----------
with tab_model:
    report = read_json(REPORTS / "model_report.json")
    if not report:
        st.info("Aucun rapport : lancez `python src/model.py`.")
    else:
        st.markdown(f'<div class="note">Démonstration d\'usage de la couche silver ({report["n_rows"]} patients, '
                    f'graine {report["seed"]}). Aucune valeur médicale : {report["avertissement"]}</div>',
                    unsafe_allow_html=True)
        metrics = pd.DataFrame(report["metrics"]).T.reset_index().rename(columns={"index": "modèle"})
        st.subheader("Comparaison des modèles")
        st.dataframe(metrics, hide_index=True)
        st.caption(f"Modèle retenu sur la validation croisée : **{report['selected_model']}**. "
                   "L'accuracy est trompeuse (classes déséquilibrées) : on lit l'AUC et le rappel.")
        imp = pd.DataFrame(report["permutation_importance_test"])
        st.subheader("Importance des indicateurs (permutation)")
        st.altair_chart(alt.Chart(imp).mark_bar(color="#E4572E", cornerRadiusTopRight=4,
                                                cornerRadiusBottomRight=4).encode(
            y=alt.Y("indicateur:N", sort="-x", title=None),
            x=alt.X("baisse_auc_moyenne:Q", title="Baisse d'AUC quand l'indicateur est mélangé"),
            tooltip=["indicateur", "baisse_auc_moyenne"]).properties(height=320))
        st.caption(f"Traçabilité : hash du curated lu `{report['curated_sha256'][:16]}…`")

# ---------- Onglet 5 : pipeline ----------
with tab_pipe:
    dag = read_json(REPORTS / "dag_last_run.json")
    tasks = dag["tasks"] if dag else {}
    graph_tasks = tasks or {"patients": {"deps": []}, "pubmed": {"deps": []},
                            "export_parquet": {"deps": ["patients"]}, "model": {"deps": ["patients"]},
                            "purge_dry_run": {"deps": ["patients", "pubmed"]}}
    dot = ["digraph G {", "rankdir=LR;", 'node [shape=box, style="rounded,filled", fontname="Helvetica", '
           'fontcolor="white", color="#334155"];']
    for name, info in graph_tasks.items():
        color = STATUS_COLOR.get(info.get("status", "NONE"), STATUS_COLOR["NONE"])
        dot.append(f'"{name}" [fillcolor="{color}"];')
        for dep in info["deps"]:
            dot.append(f'"{dep}" -> "{name}";')
    dot.append("}")
    st.subheader("Orchestration (DAG)")
    st.graphviz_chart("\n".join(dot))
    if dag:
        st.caption(f"Dernière exécution : {dag['run_id']} → {dag['status']} (vert : réussi, rouge : échec, "
                   "orange : tâche ignorée car une dépendance a échoué).")
    else:
        st.caption("Aucune exécution du DAG enregistrée (`python src/run_all.py`).")

    stream = read_json(REPORTS / "stream_report.json")
    if stream:
        st.subheader("Simulation de flux (preuve de concept)")
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Événements", stream["events"])
        s2.metric("Rejetés", f"{stream['rejected']} ({100 * (stream['reject_rate'] or 0):.1f} %)")
        s3.metric("Alertes", sum(a["type"] == "ALERTE" for a in stream["alerts"]))
        s4.metric("Débit", f"{stream['events_per_second']} évén./s")
        st.caption(stream["note"])
    image = ROOT / "docs" / "architecture_v2.png"
    if image.exists():
        st.subheader("Architecture finale")
        st.image(str(image))

st.caption("AlzheimerDataHub · projet final ESEO 2026-2027 · données synthétiques (Kaggle, CC BY 4.0) et métadonnées PubMed")