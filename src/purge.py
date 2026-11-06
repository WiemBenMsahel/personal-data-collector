"""Purge selon la retention definie dans le contrat (simulation par defaut).

Regles :
- raw (alzheimers_*.csv + .meta.json, pubmed_*.xml) : suppression si plus ancien que raw_days,
  mais le fichier le plus recent de chaque type est TOUJOURS conserve.
- rapports (reports/runs/*.json) : suppression si plus anciens que reports_days,
  en conservant toujours les keep_last_runs derniers.
- les echantillons (sample_*) n'ont pas d'horodatage : ils ne sont jamais touches.
L'age est lu dans l'horodatage du NOM de fichier (le mtime est trompeur : copy2 le conserve).
"""
import argparse
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from contract import load_contract

RAW_DIR = Path("data/raw")
RUNS_DIR = Path("reports/runs")
STAMP = re.compile(r"(\d{8}T\d{6}Z)")
DEFAULTS = {"raw_days": 90, "reports_days": 90, "keep_last_runs": 20}

log = logging.getLogger("purge")


def _stamp(path: Path):
    m = STAMP.search(path.name)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def select_purge(contract: dict, now=None, raw_dir: Path = RAW_DIR, runs_dir: Path = RUNS_DIR) -> list:
    now = now or datetime.now(timezone.utc)
    ret = {**DEFAULTS, **contract.get("retention", {})}
    victims = []

    raw_cutoff = now - timedelta(days=ret["raw_days"])
    for pattern in ("alzheimers_*.csv", "pubmed_*.xml"):
        files = sorted((p for p in raw_dir.glob(pattern) if _stamp(p)), key=_stamp)
        for p in files[:-1]:                      # on garde toujours le plus recent
            if _stamp(p) < raw_cutoff:
                victims.append(p)
                meta = p.with_suffix(".meta.json")
                if meta.exists():
                    victims.append(meta)

    reports_cutoff = now - timedelta(days=ret["reports_days"])
    reports = sorted((p for p in runs_dir.glob("*.json") if _stamp(p)), key=_stamp)
    keep = ret["keep_last_runs"]
    older = reports[:-keep] if keep > 0 else reports
    victims += [p for p in older if _stamp(p) < reports_cutoff]
    return victims


def purge(apply: bool = False, contract: dict = None, now=None) -> list:
    contract = contract or load_contract()
    victims = select_purge(contract, now)
    if not victims:
        log.info("Rien a purger")
    for p in victims:
        if apply:
            p.unlink()
            log.info("Supprime : %s", p)
        else:
            log.info("[simulation] a supprimer : %s", p)
    return victims


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    parser = argparse.ArgumentParser(description="Purge selon la retention du contrat")
    parser.add_argument("--apply", action="store_true", help="supprimer reellement (sinon simulation)")
    args = parser.parse_args()
    purge(apply=args.apply)