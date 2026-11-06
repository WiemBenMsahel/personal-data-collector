# AlzheimerDataHub : pipeline de collecte et de fiabilisation de données cliniques

Projet final du module **Architectures BD et collecte de données**, ESEO 2026-2027
(prolongement du projet personnel des TP des séances 1 à 3).
Auteure : Wiem Ben M'sahel.

## 1. Objectif de l'application

**Question centrale :** quels indicateurs cliniques (MMSE, tension, cholestérol, âge) distinguent les patients diagnostiqués Alzheimer des autres, dans un jeu de données fiabilisé ?

**Utilisateur :** un chercheur ou data analyst en santé.
**Décision rendue possible :** choisir les indicateurs cliniques à étudier en priorité.
**Fréquence :** ponctuelle (traitement batch lancé à la demande).

### Cas d'usage et KPI

| Cas d'usage | KPI |
|---|---|
| Comparer le MMSE selon le diagnostic | MMSE moyen par diagnostic |
| Cibler la population à étudier | Part de patients diagnostiqués par tranche d'âge |
| Décider si le jeu est exploitable | Taux de lignes rejetées (table `runs`) |

## 2. Source et conditions d'utilisation

- Jeu de données : *Alzheimer's Disease Dataset*, par Rabie El Kharoua (Kaggle)
- URL : https://www.kaggle.com/datasets/rabieelkharoua/alzheimers-disease-dataset
- Licence : [Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)
- Date d'accès : 03/11/2026
- Fréquence de mise à jour de la source : jamais (jeu figé)
- Données synthétiques (tag « Synthetic » sur Kaggle) : aucune donnée personnelle de tiers. La colonne `DoctorInCharge` (masquée `XXXConfid`) est exclue de la zone curated.
- Attribution : données de Rabie El Kharoua, licence CC BY 4.0, modifiées par ce projet (sélection de colonnes, renommage, rejet des lignes invalides, variables calculées).
- Évaluation détaillée des sources : [docs/source_assessment.md](docs/source_assessment.md)

> **À compléter après l'étape MongoDB :** seconde source (PubMed, API NCBI E-utilities), licence et conditions d'usage, date d'accès.

## 3. Architecture

![Architecture](docs/architecture.png)

```
Source (Kaggle) -> Collecteur -> RAW -> Validation -> Transformation -> CURATED (CSV)
                                           |                               |
                                           |                               +-> PostgreSQL (table patients)
                                           |                                        |
                                           |                                        +-> Vues KPI -> Metabase
                                           +-> REJECTED (lignes invalides + cause)
                                           +-> Rapport d'exécution (JSON + table runs)
```

**Grain :** une ligne représente un patient (identifié par `PatientID`) avec son bilan clinique et son diagnostic.
**Clé métier :** `patient_id`.
**Contrat de données :** [config/data_contract.yaml](config/data_contract.yaml) (version 1.1)

### Couches

| Couche (nom courant) | Équivalent dans le projet | Rôle |
|---|---|---|
| Bronze (raw) | `data/raw/` | Copie brute horodatée de chaque fichier reçu, avec hash SHA-256 (rejouable) |
| Silver (curated) | `data/curated/dataset.csv` et table `patients` | Données validées, typées, dédoublonnées |
| Gold (mart) | Vues SQL `v_kpi_by_diagnosis` et `v_kpi_by_age_group` | Indicateurs prêts à interroger |

Les lignes invalides sont conservées à part dans `data/rejected/rejected_rows.csv`.

### Services (Docker Compose)

| Service | Rôle |
|---|---|
| `postgres` | Base relationnelle (curated, vues KPI, journal des runs) |
| `metabase` | Tableau de bord (lecture des vues KPI et de la table `runs`) |
| `pipeline` | Exécution du pipeline à la demande (`docker compose run`) |

Le pipeline est le seul composant qui écrit dans la base. Metabase ne fait que lire.

**Choix du backend :** si la variable `DATABASE_URL` est définie, le pipeline publie dans PostgreSQL. Sinon, il publie dans SQLite (`data/curated/alzheimer.db`), ce qui permet de lancer le pipeline et les tests sans Docker.

## 4. Prérequis

- Python 3.11 ou supérieur
- Docker Desktop (pour PostgreSQL et Metabase)
- Un compte Kaggle (gratuit) pour télécharger le fichier source

## 5. Installation

```bash
python -m venv .venv
# Activation
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux / macOS
pip install -r requirements.txt
```

Configuration de l'environnement Docker :

```bash
cp .env.example .env            # Windows : Copy-Item .env.example .env
```

Puis éditer `.env` et remplacer `change_me` par un mot de passe de son choix (lettres et chiffres uniquement). Le fichier `.env` n'est pas versionné.

## 6. Exécution

1. Télécharger `alzheimers_disease_data.csv` depuis Kaggle et le placer dans `data/source_download/`.

### Mode Docker (PostgreSQL + Metabase)

```bash
docker compose up -d postgres metabase
docker compose build pipeline
docker compose run --rm pipeline
```

Autre fichier source : `docker compose run --rm pipeline --source data/source_download/autre.csv`

Vérifier la base :

```bash
docker compose exec postgres psql -U alzheimer -d alzheimer -c "SELECT * FROM v_kpi_by_diagnosis;"
docker compose exec postgres psql -U alzheimer -d alzheimer -c "SELECT run_id, status, error FROM runs ORDER BY run_id DESC LIMIT 5;"
```

Arrêter : `docker compose down` (conserve les données) ou `docker compose down -v` (supprime aussi les volumes, donc la base et la configuration de Metabase).

### Mode local (SQLite, sans Docker)

```bash
python src/pipeline.py
python src/analysis.py          # tableaux + graphique dans reports/
streamlit run src/app.py        # tableau de bord de secours (lit SQLite)
```

### Tableau de bord Metabase

1. Ouvrir http://localhost:3000 et créer le compte administrateur (local).
2. Ajouter une base PostgreSQL : hôte `postgres`, port `5432`, base, utilisateur et mot de passe de `.env`.
3. Les questions et le tableau de bord ne sont pas versionnés dans Git : voir la capture `docs/dashboard_metabase.png`.

Contenu du tableau de bord : nombre de patients, MMSE moyen par diagnostic, part diagnostiquée par tranche d'âge, journal des exécutions.

### Tests

```bash
pytest -q
```

Les tests tournent sur SQLite, dans un dossier temporaire : ils ne modifient ni le curated, ni le raw, ni la base.

### Démonstration d'une donnée invalide

```bash
python make_dirty.py
python src/pipeline.py --source data/source_download/dirty.csv
```

`make_dirty.py` injecte un MMSE hors plage, un âge impossible et un doublon de `PatientID`. Le rapport obtenu est conservé dans `reports/run_report_dirty_demo.json`. Il faut ensuite relancer le pipeline sur le fichier propre.

## 7. Arborescence

```
personal-data-collector/
├── README.md
├── requirements.txt             dépendances locales (pipeline, tests, Streamlit)
├── requirements-docker.txt      dépendances de l'image du pipeline
├── Dockerfile                   image du pipeline
├── docker-compose.yml           postgres, metabase, pipeline
├── .env.example                 modèle de configuration (sans secret)
├── .gitignore
├── make_dirty.py                données de test invalides
├── make_incidents.py            fichiers d'incident (démonstration manuelle)
├── explore.py                   exploration initiale du CSV
├── config/
│   └── data_contract.yaml       contrat de données v1.1 (colonnes, règles, seuil)
├── data/
│   ├── raw/                     copies non modifiées de la source (horodatées + hash)
│   │   └── sample_source.csv    échantillon de 150 lignes
│   ├── curated/
│   │   └── dataset.csv          données validées et transformées
│   ├── rejected/rejected_rows.csv   lignes rejetées avec la cause
│   └── source_download/         fichiers téléchargés ou simulés (ignorés par Git)
├── docs/
│   ├── architecture.png
│   ├── dashboard_metabase.png
│   ├── incident_test.md         test d'incident et reprise
│   └── source_assessment.md
├── reports/
│   ├── run_report.json          dernier rapport d'exécution
│   ├── run_report_dirty_demo.json
│   ├── runs/                    un rapport JSON par exécution
│   ├── profile.json             profilage initial
│   └── mmse_by_diagnosis.png
├── src/
│   ├── contract.py              chargement du contrat YAML
│   ├── collect.py               collecte + copie raw horodatée + hash SHA-256
│   ├── validate.py              profilage + règles du contrat + rejets
│   ├── transform.py             renommage, typage, variables calculées
│   ├── publish.py               publication PostgreSQL ou SQLite (UPSERT), vues KPI, journal des runs
│   ├── pipeline.py              orchestration, idempotence, rapport, gestion des incidents
│   ├── analysis.py              statistiques par diagnostic
│   └── app.py                   tableau de bord Streamlit (secours, SQLite)
└── tests/
    ├── test_quality.py          règles de qualité
    ├── test_contract.py         le contrat pilote le code
    └── test_incidents.py        incidents automatisés, idempotence, reprise
```

## 8. Contrat de données et règles de qualité

Le contrat `config/data_contract.yaml` est la **source de vérité** : colonnes attendues (nom source, nom curated, type), règles de qualité et seuil de rejet. Le code les lit au lieu de les dupliquer. Un test (`test_changing_contract_changes_behavior`) prouve qu'une modification du contrat change le comportement du pipeline.

| Règle | Dimension | Condition | Action en cas d'échec |
|---|---|---|---|
| `patient_id_present` | Complétude | `PatientID` renseigné | Rejet |
| `age_valid` | Validité | âge entre 0 et 120 | Rejet |
| `mmse_range` | Validité | MMSE entre 0 et 30 | Rejet |
| `diagnosis_domain` | Validité | `Diagnosis` vaut 0 ou 1 | Rejet |
| `bp_coherent` | Cohérence | tension diastolique < systolique | Rejet |
| `cholesterol_plausible` | Validité | cholestérol total entre 100 et 400 | Signalement |
| `duplicate_patient_id` | Unicité | `PatientID` unique | Rejet du doublon et comptage |

Contrôles bloquants au niveau du fichier :

- **Fichier vide** : le run échoue (FAIL).
- **Schéma** : colonne attendue manquante ou colonne numérique non numérique, le run échoue (FAIL).
- **Taux de rejet** : au-delà de `thresholds.max_reject_rate` (20 %, défini dans le contrat), la publication est bloquée (FAIL).

Chaque ligne rejetée est conservée dans `data/rejected/rejected_rows.csv` avec la colonne `reject_reason`. Le pipeline ne supprime jamais de lignes silencieusement.

## 9. Résultats sur le jeu Kaggle

| Indicateur | Valeur |
|---|---|
| Lignes en entrée | 2149 |
| Lignes acceptées (curated) | 1963 |
| Lignes rejetées | 186 (8,7 %), toutes par la règle `bp_coherent` |
| Statut qualité | PASS_WITH_WARNINGS |

### Analyse (KPI)

Les KPI sont interrogeables en SQL (vues `v_kpi_by_diagnosis` et `v_kpi_by_age_group`) et affichés dans Metabase.

| Diagnostic | Patients | MMSE moyen | Tension systolique | Cholestérol total | Âge moyen |
|---|---|---|---|---|---|
| Alzheimer | 694 | 12,0 | 137,1 | 225,7 | 74,9 |
| Non-Alzheimer | 1269 | 16,2 | 137,9 | 224,8 | 74,9 |

| Tranche d'âge | Patients | Diagnostiqués | Part diagnostiquée |
|---|---|---|---|
| < 65 | 314 | 119 | 37,9 % |
| 65-74 | 658 | 218 | 33,1 % |
| 75-84 | 615 | 223 | 36,3 % |
| 85+ | 376 | 134 | 35,6 % |

Sur ce jeu, le MMSE est l'indicateur qui diffère le plus entre les deux groupes. La tension, le cholestérol et l'âge moyens sont quasiment identiques. La part de patients diagnostiqués varie peu selon la tranche d'âge (33 % à 38 %).

Ces résultats concernent un jeu synthétique : ils illustrent le fonctionnement du pipeline et ne constituent pas des conclusions médicales.

> **À compléter après l'étape ML :** modèle de classification (données, méthode, métriques, limites).

## 10. Idempotence

- Le fichier source est identifié par son hash SHA-256 : un contenu déjà collecté n'est pas recopié dans `data/raw/` (le terminal affiche « Deja collecte »).
- Le curated CSV est mis à jour par UPSERT sur `patient_id`, avec écriture atomique (fichier temporaire puis remplacement).
- La base (PostgreSQL ou SQLite) est mise à jour par UPSERT (`ON CONFLICT (patient_id) DO UPDATE`) dans une transaction unique : tout ou rien. La clé primaire `patient_id` garantit l'unicité.
- Relancer le pipeline avec la même entrée laisse donc `curated_total_rows` et le nombre de patients en base inchangés (1963). Ce comportement est vérifié par `test_rerun_is_idempotent`.

## 11. Observabilité, incidents et reprise

Chaque exécution reçoit un `run_id` (horodatage UTC) présent dans les logs (`reports/pipeline.log`), dans le rapport `reports/runs/run_<run_id>.json` et dans la table `runs` de la base.

Le rapport contient : version du contrat, backend de base utilisé, lignes reçues, acceptées et rejetées, doublons, échecs par règle, âge du fichier raw, statut (`PASS`, `PASS_WITH_WARNINGS`, `FAIL`) et durée.

### Incidents testés automatiquement (`tests/test_incidents.py`)

| Incident | Détection | Résultat attendu |
|---|---|---|
| Colonne manquante | `check_schema` | FAIL, code 1 |
| Fichier vide | `check_schema` | FAIL, code 1 |
| 100 % de lignes invalides | seuil de rejet du contrat | FAIL, publication bloquée |
| Source introuvable | `collect` | FAIL, code 1 |

Dans chaque cas, le pipeline journalise une ligne `INCIDENT`, passe en FAIL, retourne le code de sortie 1, **ne modifie pas le curated** (hash SHA-256 identique avant et après) et **inscrit le FAIL dans la table `runs`**. La reprise consiste à relancer le pipeline sur le fichier valide : le run repasse en PASS_WITH_WARNINGS avec 1963 lignes (`test_recovery_after_incidents`).

Démonstration manuelle possible avec `make_incidents.py`. Détail et preuves : [docs/incident_test.md](docs/incident_test.md).

> **À compléter après l'étape fraîcheur :** contrôle de l'âge du fichier source et seuil d'alerte.

## 12. Gouvernance

- **Responsable du dataset :** Wiem Ben M'sahel (auteure du projet).
- **Rétention :** le raw et les rapports sont conservés pendant la durée du module et de la correction. Le curated et la base sont reconstructibles à tout moment depuis le raw.
- **Données personnelles :** aucune (jeu synthétique, colonne `DoctorInCharge` exclue).
- **Secrets :** mots de passe dans `.env` (non versionné), `.env.example` ne contient que des valeurs fictives.
- **Accès :** le pipeline écrit dans PostgreSQL, Metabase lit seulement (les actions d'écriture de Metabase sont désactivées).
- **Traçabilité :** chaque ligne de la table `patients` conserve `source_file` et `loaded_run_id`.

## 13. Limites connues

- Jeu synthétique : pas de valeur médicale.
- Téléchargement Kaggle manuel (pas d'API automatisée).
- Pas de lien patient-à-patient avec les images IRM, qui ne sont pas intégrées.
- Les questions et le tableau de bord Metabase ne sont pas versionnés dans Git (une capture est fournie).
- Metabase et PostgreSQL tournent avec une configuration locale simple, sans chiffrement ni gestion fine des droits.
- Aucune alerte envoyée en cas d'incident : seuls les logs, le code de sortie et la table `runs` le signalent.
- Pas de planification automatique, ni de purge des anciens rapports et fichiers raw.
- La fraîcheur de la donnée n'est pas contrôlée : la source est figée.

## 14. Choix et choix écartés

**Retenu**

- **PostgreSQL** pour les données patients : tabulaires, schéma fixe, clé métier, KPI en SQL, accès multi-utilisateur et droits (Metabase en lecture, pipeline en écriture).
- **SQLite** conservé en secours : lancer les tests et le pipeline sans Docker.
- **Docker Compose** : reproductibilité sur une autre machine en trois commandes.
- **Metabase** : outil de BI réel plutôt qu'une interface codée à la main.

**Écartés**

- **MongoDB pour les données patients** : elles sont tabulaires et à schéma fixe, donc aucun besoin de souplesse documentaire.
- **Fichiers CSV seuls** : conservés pour le curated, mais sans contrainte de clé ni requêtes KPI en SQL.
- **Streaming, orchestrateur (Airflow, etc.)** : une seule source figée, traitée à la demande.

> **À compléter après l'étape MongoDB :** rôle de MongoDB Atlas pour la seconde source, et lien vers `docs/ADR_001.md`.

## 15. Améliorations

### Réalisées pendant le projet final

| Amélioration | Limite traitée |
|---|---|
| Schéma d'entrée, règles et seuil de rejet lus dans le contrat YAML | Contrat et code pouvaient diverger |
| Tests d'incident automatisés dans `pytest` (schéma, fichier vide, 100 % de rejets, source absente) | Incidents joués à la main |
| Message explicite pour un fichier vide | Erreur pandas peu lisible |
| Publication dans PostgreSQL (clé primaire `patient_id`, UPSERT) avec SQLite en secours | Base monoutilisateur, sans droits d'accès |
| Docker et Docker Compose | Reproductibilité sur une autre machine |
| Metabase en lecture seule sur les vues KPI | Interface limitée à un Streamlit minimal |

### Restantes

| Amélioration | Limite traitée |
|---|---|
| Télécharger la source via l'API Kaggle (jeton en variable d'environnement) | Téléchargement manuel |
| Automatiser l'exécution (GitHub Actions + `pytest`) | Pas de planification ni de contrôle automatique |
| Alerter en cas d'échec (e-mail ou webhook) | Seuls les logs signalent un incident |
| Exposer les KPI par une API (FastAPI) | Usage limité au tableau de bord |
| Exporter le curated en Parquet | Échanges avec d'autres outils d'analyse |
| Orchestrer avec un DAG (Airflow ou Prefect) | Plusieurs sources et dépendances entre tâches |
| Historiser les modifications de la base | Source qui évolue dans le temps |
| Outil de qualité dédié (Great Expectations, Pandera) | Nombre de règles difficile à maintenir à la main |
| Intégrer les images IRM avec un stockage objet | Disponibilité d'une source avec lien patient-à-patient |

## 16. Usage d'outils d'IA

- **Outil utilisé :** Claude (Anthropic).
- **Tâches assistées :** structuration du projet, squelettes de code (`publish.py`, `app.py`, `make_incidents.py`), migration du contrat YAML, tests d'incident, configuration Docker Compose et Metabase, relecture de la documentation.
- **Vérifications réalisées :** exécution du pipeline et des tests (13 tests), contrôle des KPI dans PostgreSQL contre `analysis.py`, test des quatre incidents avec code de sortie et comparaison du hash du curated avant et après, relance du pipeline pour vérifier l'idempotence (1963 lignes en base), contrôle que `.env` n'est pas versionné.
- **Parties retravaillées personnellement :** [À COMPLÉTER PAR TOI avec ce que tu as réellement fait toi-même : choix du sujet et de la source, choix des règles de qualité et des seuils, lecture des KPI, décisions d'architecture, test sur environnement propre...]