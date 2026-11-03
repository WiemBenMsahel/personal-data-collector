# Test d'incident

Quatre incidents simulés avec `make_incidents.py`. Le pipeline doit détecter l'incident,
conserver les preuves (raw, rejets, rapport, logs) et ne pas modifier le curated.

| Incident | Fichier | Détection | Résultat |
|---|---|---|---|
| Changement de schéma | `incident_schema.csv` (colonne MMSE renommée) | `check_schema` : colonnes manquantes ['MMSE'] | FAIL, code 1 |
| Fichier vide | `incident_empty.csv` | erreur de lecture du CSV | FAIL, code 1 |
| Valeurs impossibles | `incident_all_invalid.csv` (MMSE = 99 partout) | règle `mmse_range` : 100 % de rejets > seuil 20 % | FAIL, publication bloquée |
| Source indisponible | `fichier_inexistant.csv` | `collect()` : FileNotFoundError | FAIL, code 1 |

## Preuves conservées
- Rapport par exécution : `reports/runs/run_<run_id>.json` (status FAIL + message d'erreur)
- Journal : `reports/pipeline.log` (lignes `INCIDENT`)
- Copie raw horodatée de chaque fichier reçu dans `data/raw/`
- Lignes rejetées : `data/rejected/rejected_rows.csv`

## Reprise
Relancer `python src/pipeline.py` sur le fichier valide : le curated n'ayant pas été modifié
pendant les incidents, le run repasse en PASS_WITH_WARNINGS avec 1963 lignes, sans doublon.

## Limites
- Pas d'alerte envoyée (e-mail ou chat) : seuls les logs et le code de sortie signalent l'incident.
- Le seuil de rejet (20 %) est fixé dans le code.