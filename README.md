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
| Décider si le jeu est exploitable | Taux de lignes rejetées |

## 2. Source et conditions d'utilisation

- Jeu de données : *Alzheimer's Disease Dataset*, par Rabie El Kharoua (Kaggle)
- URL : https://www.kaggle.com/datasets/rabieelkharoua/alzheimers-disease-dataset
- Licence : [Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)
- Date d'accès : 03/11/2026
- Fréquence de mise à jour de la source : jamais (jeu figé)
- Données synthétiques (tag « Synthetic » sur Kaggle) : aucune donnée personnelle de tiers. La colonne `DoctorInCharge` (masquée `XXXConfid`) est exclue de la zone curated.
- Attribution : données de Rabie El Kharoua, licence CC BY 4.0, modifiées par ce projet (sélection de colonnes, renommage, rejet des lignes invalides, variables calculées).
- Évaluation détaillée des sources : [docs/source_assessment.md](docs/source_assessment.md)

## 3. Architecture

![Architecture](docs/architecture.png)

```
Source (Kaggle) -> Collecteur -> RAW -> Validation -> Transformation -> CURATED (CSV)
                                           |                               |
                                           |                               +-> Base SQLite (table patients)
                                           |                                        |
                                           |                                        +-> Vues KPI -> Tableau de bord Streamlit
                                           +-> REJECTED (lignes invalides + cause)
                                           +-> Rapport d'exécution (JSON + table runs)
```

**Grain :** une ligne représente un patient (identifié par `PatientID`) avec son bilan clinique et son diagnostic.
**Clé métier :** `patient_id`.
**Contrat de données :** [config/data_contract.yaml](config/data_contract.yaml)

**Couches :**

| Couche | Rôle dans le projet |
|---|---|
| Raw | Copie brute horodatée de chaque fichier reçu, avec hash SHA-256 (rejouable) |
| Curated | `data/curated/dataset.csv` et table `patients` de SQLite : données validées et typées |
| Mart | Vues SQL `v_kpi_by_diagnosis` et `v_kpi_by_age_group` : indicateurs prêts à interroger |

## 4. Prérequis

- Python 3.11 ou supérieur
- Un compte Kaggle (gratuit) pour télécharger le fichier source

## 5. Installation

```bash
python -m venv .venv
# Activation
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux / macOS
pip install -r requirements.txt
```

## 6. Exécution

1. Télécharger `alzheimers_disease_data.csv` depuis Kaggle et le placer dans `data/source_download/`.
2. Lancer le pipeline complet (collecte, validation, transformation, curated, base SQLite) :

```bash
python src/pipeline.py
```

Autre fichier source : `python src/pipeline.py --source chemin/vers/fichier.csv`

La base `data/curated/alzheimer.db` est générée par le pipeline (elle n'est pas versionnée dans Git).

3. Consulter le résultat dans le tableau de bord :

```bash
streamlit run src/app.py
```

4. Lancer l'analyse (tableaux + graphique dans `reports/`) :

```bash
python src/analysis.py
```

5. Lancer les tests :

```bash
pytest -q
```

### Démonstration d'une donnée invalide

```bash
python make_dirty.py
python src/pipeline.py --source data/source_download/dirty.csv
```

`make_dirty.py` injecte un MMSE hors plage, un âge impossible et un doublon de `PatientID`.
Le rapport obtenu est conservé dans `reports/run_report_dirty_demo.json`. Il faut ensuite relancer `python src/pipeline.py` sur le fichier propre.

### Démonstration des incidents

```bash
python make_incidents.py
python src/pipeline.py --source data/source_download/incident_schema.csv
python src/pipeline.py --source data/source_download/incident_empty.csv
python src/pipeline.py --source data/source_download/incident_all_invalid.csv
python src/pipeline.py --source data/source_download/fichier_inexistant.csv
python src/pipeline.py        # reprise sur le fichier valide
```

## 7. Arborescence

```
personal-data-collector/
├── README.md
├── requirements.txt
├── .gitignore
├── make_dirty.py                données de test invalides
├── make_incidents.py            fichiers d'incident (schéma, vide, valeurs impossibles)
├── explore.py                   exploration initiale du CSV
├── config/
│   └── data_contract.yaml       contrat de données v1
├── data/
│   ├── raw/                     copies non modifiées de la source (horodatées + hash)
│   │   └── sample_source.csv    échantillon de 150 lignes
│   ├── curated/
│   │   ├── dataset.csv          données validées et transformées
│   │   └── alzheimer.db         base SQLite (générée, ignorée par Git)
│   ├── rejected/rejected_rows.csv   lignes rejetées avec la cause
│   └── source_download/         fichiers téléchargés ou simulés (ignorés par Git)
├── docs/
│   ├── architecture.png
│   ├── incident_test.md         test d'incident et reprise
│   └── source_assessment.md
├── reports/
│   ├── run_report.json          dernier rapport d'exécution
│   ├── run_report_dirty_demo.json   rapport de la démo de rejets
│   ├── runs/                    un rapport JSON par exécution (run_<run_id>.json)
│   ├── profile.json             profilage initial
│   └── mmse_by_diagnosis.png
├── src/
│   ├── collect.py               collecte + copie raw horodatée + hash SHA-256
│   ├── validate.py              profilage + règles qualité + rejets
│   ├── transform.py             renommage, typage, variables calculées
│   ├── publish.py               publication SQLite (UPSERT), vues KPI, journal des runs
│   ├── pipeline.py              orchestration, idempotence, rapport, gestion des incidents
│   ├── analysis.py              statistiques par diagnostic
│   └── app.py                   tableau de bord Streamlit
└── tests/
    └── test_quality.py
```

## 8. Règles de qualité

| Règle | Dimension | Condition | Action en cas d'échec |
|---|---|---|---|
| `patient_id_present` | Complétude | `PatientID` renseigné | Rejet |
| `age_valid` | Validité | âge entre 0 et 120 | Rejet |
| `mmse_range` | Validité | MMSE entre 0 et 30 | Rejet |
| `diagnosis_domain` | Validité | `Diagnosis` vaut 0 ou 1 | Rejet |
| `bp_coherent` | Cohérence | tension diastolique < systolique | Rejet |
| `cholesterol_plausible` | Validité | cholestérol total entre 100 et 400 | Signalement |
| `duplicate_patient_id` | Unicité | `PatientID` unique | Dédoublonnage et comptage |

Contrôles bloquants au niveau du fichier :

- **Schéma** : si une colonne attendue manque, le run échoue (FAIL).
- **Taux de rejet** : au-delà de 20 % de lignes rejetées, la publication est bloquée (FAIL).

Chaque ligne rejetée est conservée dans `data/rejected/rejected_rows.csv` avec la colonne `reject_reason`. Le pipeline ne supprime jamais de lignes silencieusement.

## 9. Résultats sur le jeu Kaggle

| Indicateur | Valeur |
|---|---|
| Lignes en entrée | 2149 |
| Lignes acceptées (curated) | 1963 |
| Lignes rejetées | 186 (8,7 %), toutes par la règle `bp_coherent` |
| Statut qualité | PASS_WITH_WARNINGS |

### Analyse (KPI)

Les KPI sont interrogeables directement en SQL (vues `v_kpi_by_diagnosis` et `v_kpi_by_age_group`) et affichés dans le tableau de bord Streamlit.

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

Sur ce jeu, le MMSE est l'indicateur qui diffère le plus entre les deux groupes. La tension, le cholestérol et l'âge moyens sont quasiment identiques. La part de patients diagnostiqués Alzheimer varie peu selon la tranche d'âge (33 % à 38 %).

Ces résultats concernent un jeu synthétique : ils illustrent le fonctionnement du pipeline et ne constituent pas des conclusions médicales.

## 10. Idempotence

- Le fichier source est identifié par son hash SHA-256 : un contenu déjà collecté n'est pas recopié dans `data/raw/` (le terminal affiche « Deja collecte »).
- Le curated CSV est mis à jour par UPSERT sur `patient_id`, avec écriture atomique (fichier temporaire puis remplacement).
- La base SQLite est mise à jour par UPSERT (`ON CONFLICT(patient_id) DO UPDATE`) dans une transaction unique : tout ou rien.
- Relancer le pipeline avec la même entrée laisse donc `curated_total_rows` et le nombre de patients en base inchangés (1963).

## 11. Observabilité, incidents et reprise

Chaque exécution reçoit un `run_id` (horodatage UTC) présent dans les logs, dans le rapport `reports/runs/run_<run_id>.json` et dans la table `runs` de la base.

Le rapport contient : lignes reçues, acceptées et rejetées, doublons retirés, échecs par règle, statut (`PASS`, `PASS_WITH_WARNINGS`, `FAIL`) et durée.

Quatre incidents sont simulés avec `make_incidents.py` : changement de schéma, fichier vide, valeurs impossibles (100 % de rejets) et source introuvable. Dans chaque cas, le pipeline journalise une ligne `INCIDENT`, passe en FAIL, retourne le code de sortie 1 et ne modifie pas le curated (hash SHA-256 identique avant et après). La reprise consiste à relancer `python src/pipeline.py` sur le fichier valide : le run repasse en PASS_WITH_WARNINGS avec 1963 lignes.

Détail et preuves : [docs/incident_test.md](docs/incident_test.md).

## 12. Gouvernance

- **Responsable du dataset :** Wiem Ben M'sahel (auteure du projet).
- **Rétention :** le raw et les rapports sont conservés pendant la durée du module et de la correction. Le curated et la base sont reconstructibles à tout moment depuis le raw (`python src/pipeline.py`).
- **Données personnelles :** aucune (jeu synthétique, colonne `DoctorInCharge` exclue).
- **Traçabilité :** chaque ligne de la table `patients` conserve `source_file` et `loaded_run_id`.

## 13. Limites connues

- Jeu synthétique : pas de valeur médicale.
- Téléchargement Kaggle manuel (pas d'API automatisée).
- Pas de lien patient-à-patient avec les images IRM, qui ne sont pas intégrées.
- SQLite est une base locale monoutilisateur : pas d'accès concurrent ni de gestion de droits.
- Le seuil de rejet (20 %) est fixé dans le code et non dans le contrat de données.
- Aucune alerte envoyée en cas d'incident : seuls les logs et le code de sortie le signalent.
- Pas de planification automatique, ni de purge des anciens rapports et fichiers raw.
- La fraîcheur de la donnée n'est pas contrôlée : la source est figée.

## 14. Choix écartés

- **PostgreSQL** : plus adapté à plusieurs utilisateurs et à un volume croissant, mais inutile ici (2149 lignes, un seul utilisateur) et demande une installation que le correcteur devrait refaire.
- **MongoDB** : les données sont tabulaires et à schéma fixe, donc aucun besoin de souplesse documentaire.
- **Fichiers CSV seuls** : conservés pour le curated, mais sans contrainte de clé ni requêtes KPI en SQL.
- **Data Lake, Warehouse, streaming, orchestrateur (Airflow, etc.)** : une seule source figée, traitée à la demande. Ces briques ne répondraient à aucun besoin mesurable.

## 15. Améliorations futures

### Court terme (renforcent le pipeline actuel)

| Amélioration | Limite traitée |
|---|---|
| Valider le schéma d'entrée à partir du contrat YAML (colonnes, types, domaines), au lieu d'une liste codée en dur | Contrat et code peuvent diverger |
| Mettre le seuil de rejet (20 %) dans le contrat de données | Seuil fixé dans le code |
| Automatiser les tests d'incident dans `pytest` (schéma, fichier vide, 100 % de rejets, source absente) | Les incidents sont aujourd'hui joués à la main |
| Télécharger la source via l'API Kaggle, avec le jeton dans une variable d'environnement | Téléchargement manuel |
| Ajouter une métrique de fraîcheur (âge du fichier source) avec un seuil d'alerte | La fraîcheur n'est pas contrôlée |
| Purger automatiquement les anciens rapports et fichiers raw selon une durée de rétention | Accumulation de fichiers |

### Moyen terme (changement d'échelle ou d'usage)

| Amélioration | Limite traitée |
|---|---|
| Charger le curated dans PostgreSQL avec `UNIQUE (patient_id)` | SQLite est monoutilisateur, sans droits d'accès |
| Automatiser l'exécution (cron ou workflow GitHub Actions) avec `pytest` en intégration continue | Pas de planification ni de contrôle automatique |
| Alerter en cas d'échec (e-mail ou webhook de messagerie) | Seuls les logs signalent un incident |
| Conteneuriser avec Docker | Reproductibilité sur une autre machine |
| Exposer les KPI par une API (FastAPI) | Usage limité au tableau de bord |
| Exporter le curated en Parquet | Échanges avec d'autres outils d'analyse |

### Long terme (seulement si un besoin apparaît)

| Amélioration | Condition de mise en œuvre |
|---|---|
| Intégrer les images IRM (OASIS ou Kaggle) avec un stockage objet séparé, relié par une clé patient | Disponibilité d'une source autorisée avec lien patient-à-patient |
| Ajouter une seconde source pour croiser les analyses | Question métier qui l'exige |
| Orchestrer avec un DAG (Airflow ou Prefect) | Plusieurs sources et dépendances entre tâches |
| Historiser les modifications de la base (versions des lignes) | Source qui évolue dans le temps |
| Utiliser un outil de qualité dédié (Great Expectations, Pandera) | Nombre de règles difficile à maintenir à la main |

## 16. Usage d'outils d'IA

- Outil utilisé : Claude (Anthropic).
- Tâches assistées : structuration du projet, squelettes de code (`publish.py`, `app.py`, `make_incidents.py`), rédaction et relecture de la documentation.
- Vérifications réalisées : exécution du pipeline et des tests, contrôle des KPI contre `analysis.py`, test des quatre incidents avec code de sortie, comparaison du hash du curated avant et après les incidents, relance du pipeline pour vérifier l'idempotence (1963 lignes en base).
- Parties retravaillées personnellement : [à compléter par toi, par exemple le choix du sujet et de la source, les règles de qualité, le contrat de données]