# Test d'incident

Quatre incidents sont simulés avec `make_incidents.py`. Pour chacun, le pipeline doit détecter
l'incident, s'arrêter proprement (statut FAIL, code de sortie 1), conserver les preuves
(raw, rapport, logs) et ne pas modifier la zone curated.

## Commandes jouées

````powershell
python make_incidents.py
python src/pipeline.py --source data/source_download/incident_schema.csv
python src/pipeline.py --source data/source_download/incident_empty.csv
python src/pipeline.py --source data/source_download/incident_all_invalid.csv
python src/pipeline.py --source data/source_download/fichier_inexistant.csv
python src/pipeline.py          # reprise sur le fichier valide
````

## Résultats observés (03/11/2026)

| Incident | Fichier | Détection | Message journalisé | Statut | Code |
|---|---|---|---|---|---|
| Changement de schéma | `incident_schema.csv` (colonne MMSE renommée) | `check_schema` | `Changement de schema : colonnes manquantes ['MMSE']` | FAIL | 1 |
| Fichier vide | `incident_empty.csv` | erreur de lecture du CSV | `No columns to parse from file` | FAIL | 1 |
| Valeurs impossibles | `incident_all_invalid.csv` (MMSE = 99 partout) | règle `mmse_range` (2149 échecs) puis seuil de rejet | `Taux de rejet 100.0% > seuil 20% : publication bloquee` | FAIL | 1 |
| Source indisponible | `fichier_inexistant.csv` | `collect()` | `Source introuvable : data\source_download\fichier_inexistant.csv` | FAIL | 1 |

## Preuves conservées

- Rapport par exécution : `reports/runs/run_<run_id>.json` (statut FAIL et message d'erreur).
- Journal des runs en base : table `runs` de `data/curated/alzheimer.db`
  (3 FAIL et 3 PASS_WITH_WARNINGS à la date du test ; l'incident de schéma, joué avant le
  branchement de la base, n'a que son rapport JSON).
- Journal : `reports/pipeline.log` (lignes `INCIDENT`).
- Copie raw horodatée du fichier reçu dans `data/raw/`, conservée comme preuve pour les
  incidents de schéma, de fichier vide et de valeurs impossibles. Aucune copie pour la source
  introuvable : il n'y avait rien à copier.

## Preuve que le curated n'est pas modifié

Hash SHA-256 de `data/curated/dataset.csv` mesuré avant et après les incidents
(`Get-FileHash`) :

`8527CC8DFB31AC1D552BE3D90088B132C0AD0D0B92C60C132C8ECDBBDB4BDAB5` (identique).

## Reprise

Relance de `python src/pipeline.py` sur le fichier valide :

- statut `PASS_WITH_WARNINGS`, 1963 lignes en curated, 186 rejetées (8,7 %) ;
- base SQLite mise à jour : 1963 patients, sans doublon (UPSERT sur `patient_id`) ;
- `data/rejected/rejected_rows.csv` est réécrit par cette reprise (il avait été écrasé par
  l'incident à 100 % de rejets).

## Limites

- Aucune alerte n'est envoyée (e-mail ou chat) : seuls les logs et le code de sortie signalent
  l'incident.
- Le seuil de rejet (20 %) est fixé dans le code, pas dans le contrat de données.
- Les rapports d'incident et les fichiers raw s'accumulent : il n'y a pas encore de purge.