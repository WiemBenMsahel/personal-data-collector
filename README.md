# AlzheimerDataHub : pipeline de collecte et de fiabilisation de données cliniques

Projet personnel de collecte de données (TP séances 1 et 2), module **Architectures BD et collecte de données**, ESEO 2026-2027.
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
Source (Kaggle) -> Collecteur -> RAW -> Validation -> Transformation -> CURATED -> Analyse
                                           |
                                           +-> REJECTED (lignes invalides + cause)
                                           +-> run_report.json
```

**Grain :** une ligne représente un patient (identifié par `PatientID`) avec son bilan clinique et son diagnostic.
**Clé métier :** `patient_id`.
**Contrat de données :** [config/data_contract.yaml](config/data_contract.yaml)

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
2. Lancer le pipeline complet :

```bash
python src/pipeline.py
```

Autre fichier source : `python src/pipeline.py --source chemin/vers/fichier.csv`

3. Lancer l'analyse (tableaux + graphique dans `reports/`) :

```bash
python src/analysis.py
```

4. Lancer les tests :

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

## 7. Arborescence

```
personal-data-collector/
├── README.md
├── requirements.txt
├── .gitignore
├── make_dirty.py                données de test invalides
├── explore.py                   exploration initiale du CSV
├── config/
│   └── data_contract.yaml       contrat de données v1
├── data/
│   ├── raw/                     copie non modifiée de la source (horodatée + hash)
│   │   └── sample_source.csv    échantillon de 150 lignes
│   ├── curated/dataset.csv      données validées et transformées
│   ├── rejected/rejected_rows.csv   lignes rejetées avec la cause
│   └── source_download/         fichier téléchargé (ignoré par Git)
├── docs/
│   ├── architecture.png
│   └── source_assessment.md
├── reports/
│   ├── run_report.json          rapport d'exécution
│   ├── run_report_dirty_demo.json   rapport de la démo de rejets
│   ├── profile.json             profilage initial
│   └── mmse_by_diagnosis.png
├── src/
│   ├── collect.py               collecte + copie raw horodatée + hash SHA-256
│   ├── validate.py              profilage + règles qualité + rejets
│   ├── transform.py             renommage, typage, variables calculées
│   ├── pipeline.py              orchestration, idempotence, rapport
│   └── analysis.py              statistiques par diagnostic
└── tests/
    └── test_quality.py
```

## 8. Règles de qualité

| Règle | Condition | Action en cas d'échec |
|---|---|---|
| `patient_id_present` | `PatientID` renseigné | Rejet |
| `age_valid` | âge entre 0 et 120 | Rejet |
| `mmse_range` | MMSE entre 0 et 30 | Rejet |
| `diagnosis_domain` | `Diagnosis` vaut 0 ou 1 | Rejet |
| `bp_coherent` | tension diastolique < systolique | Rejet |
| `cholesterol_plausible` | cholestérol total entre 100 et 400 | Signalement |
| `duplicate_patient_id` | `PatientID` unique | Dédoublonnage et comptage |

Chaque ligne rejetée est conservée dans `data/rejected/rejected_rows.csv` avec la colonne `reject_reason`. Le pipeline ne supprime jamais de lignes silencieusement.

## 9. Résultats sur le jeu Kaggle

| Indicateur | Valeur |
|---|---|
| Lignes en entrée | 2149 |
| Lignes acceptées (curated) | 1963 |
| Lignes rejetées | 186 (8,7 %), toutes par la règle `bp_coherent` |
| Statut qualité | PASS_WITH_WARNINGS |

### Analyse (KPI)

| Diagnostic | MMSE moyen | Tension systolique | Cholestérol total | Âge moyen |
|---|---|---|---|---|
| Alzheimer | 12,0 | 137,1 | 225,7 | 74,9 |
| Non-Alzheimer | 16,2 | 137,9 | 224,8 | 74,9 |

Sur ce jeu, le MMSE est l'indicateur qui diffère le plus entre les deux groupes. La tension, le cholestérol et l'âge moyens sont quasiment identiques. La part de patients diagnostiqués Alzheimer varie peu selon la tranche d'âge (33 % à 38 %).

Ces résultats concernent un jeu synthétique : ils illustrent le fonctionnement du pipeline et ne constituent pas des conclusions médicales.

## 10. Idempotence

- Le fichier source est identifié par son hash SHA-256 : un contenu déjà collecté n'est pas recopié dans `data/raw/` (le terminal affiche « Deja collecte »).
- Le curated est mis à jour par UPSERT sur `patient_id`, avec écriture atomique (fichier temporaire puis remplacement).
- Relancer le pipeline avec la même entrée laisse donc `curated_total_rows` inchangé (1963).

## 11. Limites connues

- Jeu synthétique : pas de valeur médicale.
- Téléchargement Kaggle manuel (pas d'API automatisée).
- Pas de lien patient-à-patient avec les images IRM, qui ne sont pas intégrées.
- Stockage en fichiers CSV, sans base de données.
- Pas de planification automatique.

## 12. Améliorations futures

- Intégrer les images IRM (OASIS ou Kaggle) avec un stockage objet séparé.
- Charger le curated dans PostgreSQL avec une contrainte `UNIQUE (patient_id)`.
- Automatiser l'exécution (cron ou workflow CI) et alerter en cas d'échec qualité.
- Ajouter la validation du schéma d'entrée avec le contrat YAML.