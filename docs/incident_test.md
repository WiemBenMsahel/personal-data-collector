# Test d'incident

Sept incidents sont documentés : quatre simulés sur le pipeline des patients avec `make_incidents.py`
(03/11/2026), un incident réel sur la seconde source MongoDB (06/11/2026), un incident PubMed à 100 %
de rejets (test automatisé) et une panne de la source des patients pendant le DAG (07/11/2026). Une
simulation de fraîcheur (avertissement, sans blocage) complète la liste.

Pour chaque incident bloquant, le système doit détecter l'incident, s'arrêter proprement (statut FAIL,
code de sortie 1), conserver les preuves (raw, rapport, logs) et ne pas corrompre les données déjà
publiées.

## 1. Incidents simulés (pipeline CSV Kaggle)

### Commandes jouées

```powershell
python make_incidents.py
python src/pipeline.py --source data/source_download/incident_schema.csv
python src/pipeline.py --source data/source_download/incident_empty.csv
python src/pipeline.py --source data/source_download/incident_all_invalid.csv
python src/pipeline.py --source data/source_download/fichier_inexistant.csv
python src/pipeline.py          # reprise sur le fichier valide
```

### Résultats observés (03/11/2026)

| Incident | Fichier | Détection | Message journalisé | Statut | Code |
|---|---|---|---|---|---|
| Changement de schéma | `incident_schema.csv` (colonne MMSE retirée) | `check_schema` | `Changement de schema : colonnes manquantes ['MMSE']` | FAIL | 1 |
| Fichier vide | `incident_empty.csv` | erreur de lecture du CSV | `No columns to parse from file` (depuis remplacé par le message explicite `Fichier vide : aucune ligne a traiter`) | FAIL | 1 |
| Valeurs impossibles | `incident_all_invalid.csv` (MMSE = 99 partout) | règle `mmse_range` (2149 échecs) puis seuil de rejet | `Taux de rejet 100.0% > seuil 20% : publication bloquee` | FAIL | 1 |
| Source indisponible | `fichier_inexistant.csv` | `collect()` | `Source introuvable : data\source_download\fichier_inexistant.csv` | FAIL | 1 |

### Preuves conservées

- Rapport par exécution : `reports/runs/run_<run_id>.json` (statut FAIL et message d'erreur).
- Journal des runs en base : table `runs` (à la date du test sur SQLite : 3 FAIL et
  3 PASS_WITH_WARNINGS ; l'incident de schéma, joué avant le branchement de la base, n'a que son
  rapport JSON). Depuis, chaque FAIL est inscrit dans la table `runs`.
- Journal : `reports/pipeline.log` (lignes `INCIDENT`).
- Copie raw horodatée du fichier reçu dans `data/raw/`, conservée comme preuve pour les incidents
  de schéma, de fichier vide et de valeurs impossibles. Aucune copie pour la source introuvable :
  il n'y avait rien à copier.

### Preuve que le curated n'est pas modifié

Hash SHA-256 de `data/curated/dataset.csv` mesuré avant et après l'incident du fichier vide
(`Get-FileHash`, 03/11/2026) :

`8527CC8DFB31AC1D552BE3D90088B132C0AD0D0B92C60C132C8ECDBBDB4BDAB5` (identique).

Cette vérification est maintenant automatisée (voir la section 6).

### Reprise

Relance de `python src/pipeline.py` sur le fichier valide :

- statut `PASS_WITH_WARNINGS`, 1963 lignes en curated, 186 rejetées (8,7 %) ;
- base mise à jour : 1963 patients, sans doublon (UPSERT sur `patient_id`) ;
- `data/rejected/rejected_rows.csv` est réécrit par cette reprise (il avait été écrasé par
  l'incident à 100 % de rejets).

## 2. Incident réel : publication MongoDB impossible (seconde source PubMed)

| Élément | Constat |
|---|---|
| Date | 06/11/2026 |
| Cause | `MONGODB_URI` contenait une adresse de cluster Atlas non renseignée (valeur factice) |
| Où | `src/pubmed.py`, étape de publication MongoDB (après collecte, validation et écriture du curated JSONL) |
| Détection | `pymongo.errors.ConfigurationError` : `The DNS query name does not exist: _mongodb._tcp.<cluster>.mongodb.net` |
| Journal | `INCIDENT : The DNS query name does not exist ...` puis `Fin du run : FAIL` |
| Statut et code | FAIL, code de sortie 1 (runs `20261106T185354Z` et `20261106T185401Z`) |
| Preuves conservées | raw XML `data/raw/pubmed_<run_id>.xml`, curated JSONL, rejets JSONL, rapport `reports/runs/pubmed_<run_id>.json` |
| Données publiées | MongoDB non modifié : la publication n'a pas eu lieu |

### Reprise

1. Création du cluster Atlas gratuit, d'un utilisateur de base et autorisation de l'adresse IP.
2. Correction de `MONGODB_URI` dans `.env` (fichier non versionné).
3. Relance de `python src/pubmed.py` : run `20261106T190025Z`, statut PASS, **195 articles** en base.
4. Seconde relance : toujours **195 documents** (UPSERT sur `pmid`, pas de doublon).

### Enseignements

- Le pipeline principal (CSV vers PostgreSQL ou SQLite) ne dépend pas de MongoDB : l'incident n'a
  pas affecté les patients.
- Sans `MONGODB_URI`, `pubmed.py` produit quand même le curated JSONL (mode dégradé documenté).
- Le secret n'apparaît ni dans le dépôt, ni dans ce document : il est uniquement dans `.env`.

## 3. Incident PubMed : 100 % d'articles invalides (test automatisé)

| Élément | Détail |
|---|---|
| Déclencheur | un XML dont tous les articles ont une année impossible (1800) |
| Détection | seuil `thresholds.max_reject_rate` (20 %) du contrat PubMed (`config/pubmed_contract.yaml`) |
| Message | `Taux de rejet 100.0% > seuil 20% : publication bloquee` |
| Résultat | statut FAIL, code de sortie 1 |
| Preuves conservées | raw XML, fichier de rejets `data/rejected/pubmed_rejected.jsonl`, rapport `reports/runs/pubmed_<run_id>.json` |
| Garantie | le curated `pubmed_articles.jsonl` n'est pas écrit |
| Test | `tests/test_pubmed.py::test_pubmed_incident_keeps_evidence_and_blocks_curated` |

Les rejets et le raw sont conservés même quand la publication est bloquée : on peut analyser la cause
après coup.

## 4. Incident DAG : panne de la source des patients

| Élément | Détail |
|---|---|
| Date | 07/11/2026 |
| Déclencheur | `alzheimers_disease_data.csv` renommé temporairement |
| Détection | la tâche `patients` retourne le code de sortie 1 (`Source introuvable`) |
| Résultat | `patients` FAILED ; `export_parquet`, `model` et `purge_dry_run` en `UPSTREAM_FAILED` ; `pubmed` réussit (tâche indépendante) ; DAG en FAIL |
| Preuve | `reports/dag_demo_failure.json` (run `20261107T103327Z`) |
| Reprise | fichier remis à son nom, puis `python src/run_all.py --resume` |
| Résultat de la reprise | `pubmed` en `SKIPPED_OK`, les 4 autres tâches rejouées en SUCCESS, DAG en PASS (run `20261107T162709Z`) |
| Test | `tests/test_dag.py` (propagation des échecs et reprise ciblée) |

La reprise ne rejoue que ce qui n'avait pas réussi. Le curated n'est pas modifié par la panne.

## 5. Simulation de fraîcheur (avertissement, sans blocage)

| Élément | Détail |
|---|---|
| Date | 06/11/2026 |
| Déclencheur | copie du CSV dont la date de modification est reculée de 45 jours |
| Détection | âge du fichier source (`source_age_days`) supérieur à `freshness.max_source_age_days` (30 jours) |
| Résultat | avertissement journalisé, `"freshness": "STALE"`, statut PASS_WITH_WARNINGS (pas de blocage) |
| Preuve | `reports/run_report_stale_demo.json` |

Pour PubMed, la fraîcheur compare l'année de l'article le plus récent au seuil du contrat (1 an) :
`test_freshness_flags_old_literature`.

## 6. Tests automatisés

30 tests au total (`pytest -q`). Ceux qui concernent les incidents :

| Fichier | Ce qu'il prouve |
|---|---|
| `tests/test_incidents.py` | 4 incidents patients (colonne manquante, fichier vide, 100 % de lignes invalides, source introuvable) : code 1, FAIL inscrit dans la table `runs`, curated inchangé (hash avant et après), nombre de patients inchangé ; reprise (`test_recovery_after_incidents`) ; idempotence (`test_rerun_is_idempotent`) |
| `tests/test_pubmed.py` | incident PubMed à 100 % de rejets : raw et rejets conservés, curated non écrit ; seuil de rejet ; fraîcheur |
| `tests/test_dag.py` | ordre des dépendances, propagation `UPSTREAM_FAILED`, reprise avec `--resume` |

Les tests tournent sur SQLite dans un dossier temporaire : ils ne modifient ni le curated, ni le raw,
ni la base.

```powershell
pytest -q
```

## Limites

- Aucune alerte n'est envoyée (e-mail ou chat) : seuls les logs, le code de sortie, les rapports et
  la table `runs` signalent l'incident.
- L'incident MongoDB n'est pas couvert par un test automatisé : il a été observé en conditions
  réelles. La commande `python src/pubmed.py --kpi` affiche encore une trace d'erreur brute si
  MongoDB est injoignable.
- Le DAG n'a ni planification ni relance automatique : la reprise se lance à la main
  (`run_all.py --resume`).
- Les rapports d'incident et les fichiers raw s'accumulent : la purge existe (`src/purge.py`,
  simulation par défaut, rétention 90 jours) mais se lance à la main.