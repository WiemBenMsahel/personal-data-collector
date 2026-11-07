# Lineage : de la source à l'indicateur

## Flux patients

```mermaid
flowchart LR
    K[Kaggle CSV] --> R[data/raw/alzheimers_horodate.csv<br/>sha256]
    R --> V{Validation<br/>contrat v1.2}
    V -->|rejetees| J[data/rejected/rejected_rows.csv<br/>reject_reason]
    V -->|acceptees| C[data/curated/dataset.csv]
    C --> P[(Table patients<br/>source_file, loaded_run_id)]
    P --> G[Vues KPI v_kpi_by_diagnosis<br/>v_kpi_by_age_group]
    G --> M[Metabase]
    C --> ML[model.py] --> MR[reports/model_report.json<br/>curated_sha256]
    V --> RP[reports/runs/run_ID.json<br/>+ table runs]
```

## Flux PubMed

```mermaid
flowchart LR
    A[API PubMed] --> X[data/raw/pubmed_horodate.xml]
    X --> W{Validation<br/>5 regles}
    W -->|rejetes| Y[data/rejected/pubmed_rejected.jsonl]
    W -->|acceptes| Z[data/curated/pubmed_articles.jsonl]
    Z --> D[(MongoDB Atlas<br/>articles, searches)]
    W --> Q[reports/runs/pubmed_ID.json]
```

## Identifiants conservés à chaque étape

| Étape | Sortie | Identifiants qui permettent de remonter à la source |
|---|---|---|
| Collecte | copie raw horodatée | horodatage dans le nom, hash SHA-256 |
| Validation | rejets | `reject_reason` (règle en cause) |
| Publication | table `patients`, collection `articles` | `source_file` (fichier raw d'origine), `loaded_run_id` |
| Exécution | rapport JSON, table `runs` | `run_id` |
| Modèle | `model_report.json` | `curated_sha256` (hash du curated lu) |

## Remonter d'un KPI à sa source

```sql
SELECT DISTINCT source_file, loaded_run_id FROM patients;
```

Le résultat donne le fichier raw d'origine (`data/raw/<source_file>`) et le rapport du run qui l'a chargé (`reports/runs/run_<loaded_run_id>.json`).