# Dictionnaire de données

Projet AlzheimerDataHub, module Architectures BD et collecte de données (ESEO 2026-2027).
Responsable : Wiem Ben M'sahel. Contrat de données : `config/data_contract.yaml` (version 1.2).

## 1. Patients : zone curated

- **Fichiers :** `data/curated/dataset.csv` et table `patients` (PostgreSQL ou SQLite).
- **Grain :** une ligne représente un patient avec son bilan clinique et son diagnostic.
- **Clé métier :** `patient_id` (clé primaire dans la table `patients`).
- **Source :** *Alzheimer's Disease Dataset* (Kaggle, Rabie El Kharoua, CC BY 4.0), jeu synthétique, 2149 lignes en entrée, 1963 lignes après validation.

| Champ | Type | Oblig. | Description | Valeurs et règles | Exemple | Origine |
|---|---|---|---|---|---|---|
| `patient_id` | entier | Oui | Identifiant unique du patient | non vide, unique (`patient_id_present`, `duplicate_patient_id`) | 4751 | `PatientID` |
| `age` | entier | Oui | Âge en années | entre 0 et 120 (`age_valid`) | 73 | `Age` |
| `gender` | texte | Oui | Sexe | `Male` ou `Female` (codes source : 0 = Male, 1 = Female) | Female | `Gender` (recodé) |
| `bmi` | décimal | Oui | Indice de masse corporelle (kg/m²) | aucune règle | 22.93 | `BMI` |
| `hypertension` | entier | Oui | Antécédent d'hypertension | 0 = non, 1 = oui | 0 | `Hypertension` |
| `systolic_bp` | entier | Oui | Tension artérielle systolique (mmHg) | strictement supérieure à `diastolic_bp` (`bp_coherent`) | 142 | `SystolicBP` |
| `diastolic_bp` | entier | Oui | Tension artérielle diastolique (mmHg) | strictement inférieure à `systolic_bp` (`bp_coherent`) | 72 | `DiastolicBP` |
| `cholesterol_total` | décimal | Oui | Cholestérol total (mg/dL) | entre 100 et 400, sinon signalement (`cholesterol_plausible`) | 242.37 | `CholesterolTotal` |
| `mmse` | décimal | Oui | Score MMSE (Mini-Mental State Examination) | entre 0 et 30 (`mmse_range`) | 21.46 | `MMSE` |
| `memory_complaints` | entier | Oui | Plaintes de mémoire | 0 = non, 1 = oui | 0 | `MemoryComplaints` |
| `diagnosis` | entier | Oui | Diagnostic de la maladie d'Alzheimer | 0 = non, 1 = oui (`diagnosis_domain`) | 0 | `Diagnosis` |
| `diagnosis_label` | texte | Oui | Libellé du diagnostic | `Alzheimer` ou `Non-Alzheimer` | Non-Alzheimer | calculé depuis `diagnosis` |
| `age_group` | texte | Oui | Tranche d'âge | `<65` (64 ans ou moins), `65-74`, `75-84`, `85+` | 65-74 | calculé depuis `age` |
| `source_file` | texte | Oui | Fichier raw d'où provient la ligne (traçabilité) | nom horodaté dans `data/raw/` | alzheimers_20261103T112421Z.csv | ajouté par le pipeline |
| `loaded_run_id` | texte | Oui | Exécution qui a chargé la ligne (table `patients` uniquement, absent du CSV) | horodatage UTC du run | 20261107T084809Z | ajouté par la publication |

### Colonnes de la source non conservées dans le curated

Le fichier source contient 35 colonnes ; seules 11 sont conservées dans le curated, les autres étant hors du périmètre de la question centrale (minimisation). Exemples : `Ethnicity` (donnée sensible) et `DoctorInCharge` (valeur masquée `XXXConfid`, exclue explicitement par le contrat, `excluded_fields`).

Exception : `data/rejected/rejected_rows.csv` conserve la ligne source complète (35 colonnes) pour permettre le diagnostic des rejets, donc aussi ces colonnes. C'est acceptable ici car le jeu est synthétique ; sur des données réelles, ces colonnes seraient retirées du fichier des rejets.

## 2. Patients : zone rejected

- **Fichier :** `data/rejected/rejected_rows.csv`.
- **Contenu :** les lignes invalides telles que reçues de la source (les 35 colonnes d'origine, avec les noms de la source, par exemple `PatientID` et non `patient_id`), plus une colonne `reject_reason`.
- **`reject_reason` :** noms des règles échouées, séparés par `;` (par exemple `bp_coherent;`). Une ligne peut échouer à plusieurs règles.
- Le fichier est réécrit à chaque run ; l'historique est dans les rapports `reports/runs/`.

## 3. Journal des exécutions (table `runs`)

Une ligne par exécution du pipeline patients (échecs inclus).

| Champ | Type | Description |
|---|---|---|
| `run_id` | texte (clé primaire) | Horodatage UTC de l'exécution |
| `status` | texte | `PASS`, `PASS_WITH_WARNINGS` ou `FAIL` |
| `source_file` | texte | Fichier raw traité (vide en cas d'échec avant la collecte) |
| `input_rows` | entier | Lignes reçues |
| `accepted_rows` | entier | Lignes acceptées |
| `rejected_rows` | entier | Lignes rejetées |
| `reject_rate` | décimal | Part de lignes rejetées (0 à 1) |
| `duration_seconds` | décimal | Durée de l'exécution |
| `error` | texte | Message d'erreur en cas de FAIL |

## 4. Rapport d'exécution JSON

Fichiers : `reports/run_report.json` (dernier run) et `reports/runs/run_<run_id>.json` (un par run).

| Champ | Description |
|---|---|
| `pipeline`, `run_id` | Nom du pipeline et identifiant de l'exécution |
| `source_requested` | Chemin de la source demandée |
| `contract_version` | Version du contrat appliquée (1.2) |
| `source_file` | Fichier raw traité |
| `raw_age_hours` | Âge de la copie raw depuis sa collecte |
| `source_age_days` | Âge du fichier source (date de modification) |
| `freshness` | `OK` ou `STALE` (au-delà de `freshness.max_source_age_days`) |
| `input_rows`, `accepted_rows`, `rejected_rows`, `reject_rate` | Volumes et taux de rejet |
| `duplicates_removed` | Doublons de `patient_id` |
| `curated_total_rows`, `db_rows`, `db_backend` | Lignes en curated, en base, et base utilisée |
| `rule_failures` | Nombre d'échecs par règle |
| `status`, `error` | Statut final et message d'erreur éventuel |
| `duration_seconds` | Durée |

## 5. Indicateurs (couche gold)

| Vue | Champs | Rôle |
|---|---|---|
| `v_kpi_by_diagnosis` | `diagnosis_label`, `patients`, `mmse_moyen`, `systolique_moyenne`, `cholesterol_moyen`, `age_moyen` | KPI 1 : MMSE moyen par diagnostic |
| `v_kpi_by_age_group` | `age_group`, `patients`, `diagnostiques`, `pct_diagnostiques` | KPI 2 : part de patients diagnostiqués par tranche d'âge |

Le KPI 3 (taux de lignes rejetées) se lit dans la table `runs` (`reject_rate`).

## 6. Articles PubMed : collection `articles`

- **Fichiers :** `data/curated/pubmed_articles.jsonl` (une ligne JSON par article) et collection MongoDB `articles` (base `alzheimer_hub`).
- **Grain :** un document représente un article scientifique.
- **Clé métier :** `pmid` (identifiant PubMed). Dans MongoDB, `_id` vaut `pmid`.
- **Source :** PubMed, API NCBI E-utilities. Seules les métadonnées sont conservées (pas le texte des résumés).

| Champ | Type | Oblig. | Description | Règle | Exemple |
|---|---|---|---|---|---|
| `pmid` | texte | Oui | Identifiant PubMed | non vide, unique (`pmid_present`, `duplicate_pmid`) | 39950934 |
| `title` | texte | Oui | Titre de l'article | non vide (`title_present`) | Safety issues of Donepezil combined with Memantine in Alzheimer's disease population: real-world pharmacovigilance. |
| `journal` | texte | Non | Titre de la revue | aucune | Expert opinion on drug safety |
| `year` | entier | Oui | Année de publication | entre 1900 et l'année suivante (`year_valid`) | 2026 |
| `has_abstract` | booléen | Oui | Un résumé existe dans PubMed (le texte n'est pas conservé) | signalement si faux (`abstract_present`) | true |
| `mesh_terms` | liste de textes | Non | Termes MeSH (vocabulaire médical contrôlé), nombre variable | aucune | `["Humans", "Donepezil", "Alzheimer Disease", ...]` |
| `indicators` | liste de textes | Oui | Indicateurs pour lesquels l'article a été trouvé : `mmse`, `blood_pressure`, `cholesterol`, `age` | un article peut en avoir plusieurs | `["age"]` |
| `collected_at` | texte (date ISO 8601, UTC) | Oui | Date de collecte | aucune | 2026-11-06T19:00:43.985171+00:00 |
| `source_file` | texte | Oui | Fichier raw XML d'origine | nom horodaté dans `data/raw/` | pubmed_20261106T190037Z.xml |
| `loaded_run_id` | texte | Oui | Exécution qui a chargé le document (MongoDB uniquement, absent du JSONL) | horodatage UTC | 20261106T190037Z |

Les articles rejetés sont dans `data/rejected/pubmed_rejected.jsonl` (mêmes champs et `reject_reason`).

## 7. Historique des recherches : collection `searches`

Un document par indicateur et par exécution (historique conservé, contrairement à `articles`).

| Champ | Type | Description |
|---|---|---|
| `_id` | texte | `<run_id>:<indicateur>` |
| `indicator` | texte | `mmse`, `blood_pressure`, `cholesterol` ou `age` |
| `query` | texte | Requête PubMed utilisée |
| `pubmed_total` | entier | Nombre total d'articles correspondant dans PubMed |
| `retrieved` | entier | Nombre d'articles récupérés (50 au maximum) |
| `run_id` | texte | Exécution |

## 8. Lineage

| Étape | Patients | Articles |
|---|---|---|
| Source | Kaggle, `alzheimers_disease_data.csv` | PubMed, API E-utilities |
| Raw | `data/raw/alzheimers_<run_id>.csv` + `.meta.json` (SHA-256) | `data/raw/pubmed_<run_id>.xml` |
| Validation | 7 règles du contrat, schéma, seuil de rejet, fraîcheur | 4 règles de rejet + 1 signalement |
| Rejected | `data/rejected/rejected_rows.csv` | `data/rejected/pubmed_rejected.jsonl` |
| Curated | `data/curated/dataset.csv` puis table `patients` | `data/curated/pubmed_articles.jsonl` puis collection `articles` |
| Gold | vues `v_kpi_by_diagnosis` et `v_kpi_by_age_group` | compteurs par indicateur (`pubmed.py --kpi`) |
| Usage | Metabase (et Streamlit de secours) | comparaison avec les KPI, par indicateur |
| Observabilité | `reports/pipeline.log`, `reports/runs/`, table `runs` | `reports/runs/pubmed_<run_id>.json` |

Exemple de lineage d'un KPI : `Age` (source) → `age` (curated) → `age_group` (calculé) → `v_kpi_by_age_group.pct_diagnostiques` → tableau de bord Metabase.

## 9. Gouvernance

- **Responsable :** Wiem Ben M'sahel.
- **Rétention :** raw et rapports 90 jours, au moins les 20 derniers rapports (contrat, section `retention`).
- **Données personnelles :** aucune. Jeu patients synthétique ; PubMed : métadonnées d'articles publiés.
- **Licence :** patients en CC BY 4.0 (attribution à Rabie El Kharoua) ; PubMed selon la politique de données du NCBI.