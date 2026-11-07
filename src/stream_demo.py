"""Preuve de concept : les regles de qualite appliquees a un flux d'evenements.

La source Kaggle est figee, donc le flux est SIMULE : le fichier est rejoue ligne par ligne
(un evenement = un patient) a une cadence reglable. Chaque evenement est controle a l'arrivee ;
une alerte part si le taux de rejet sur une fenetre glissante depasse le seuil. Cela montre ce
qu'un traitement en continu ajouterait (detection precoce) sans changer la decision d'architecture :
le produit de donnees reste alimente par le pipeline batch.

Regles identiques au contrat de donnees (README, section 8). Verification de coherence :
sans derive, le flux doit retrouver les memes volumes que le batch (1963 acceptes, 186 rejetes).

Usage : python src/stream_demo.py --rate 0                      (vitesse maximale)
        python src/stream_demo.py --rate 200 --inject-drift     (200 evenements/s, panne simulee)
"""
import argparse
import csv
import json
import queue
import sys
import threading
import time
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "source_download" / "alzheimers_disease_data.csv"
REPORT = ROOT / "reports" / "stream_report.json"
WINDOW = 100          # nombre d'evenements de la fenetre glissante
ALERT_RATE = 0.20     # meme seuil que thresholds.max_reject_rate du contrat patients
DRIFT = range(600, 800)   # evenements corrompus quand --inject-drift est utilise


def num(row: dict, key: str):
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError):
        return None


def check_event(row: dict, seen: set):
    """Retourne (regles violees, avertissements). Liste vide = evenement accepte."""
    reasons, warnings = [], []
    pid = (row.get("PatientID") or "").strip()
    if not pid:
        reasons.append("patient_id_present")
    elif pid in seen:
        reasons.append("duplicate_patient_id")
    age, mmse, diag = num(row, "Age"), num(row, "MMSE"), num(row, "Diagnosis")
    sys_bp, dia_bp, chol = num(row, "SystolicBP"), num(row, "DiastolicBP"), num(row, "CholesterolTotal")
    if age is None or not 0 <= age <= 120:
        reasons.append("age_valid")
    if mmse is None or not 0 <= mmse <= 30:
        reasons.append("mmse_range")
    if diag not in (0.0, 1.0):
        reasons.append("diagnosis_domain")
    if sys_bp is None or dia_bp is None or not dia_bp < sys_bp:
        reasons.append("bp_coherent")
    if chol is not None and not 100 <= chol <= 400:
        warnings.append("cholesterol_plausible")
    return reasons, warnings


def process_stream(events, window: int = WINDOW, alert_rate: float = ALERT_RATE, on_alert=None):
    """Consomme un flux d'evenements et retourne un rapport (volumes, regles, alertes)."""
    seen, recent = set(), deque(maxlen=window)
    failures, warnings_count = Counter(), Counter()
    accepted = rejected = 0
    alerts, alerting = [], False
    n = 0
    for n, row in enumerate(events, start=1):
        reasons, warns = check_event(row, seen)
        warnings_count.update(warns)
        if reasons:
            rejected += 1
            failures.update(reasons)
        else:
            accepted += 1
            seen.add(row["PatientID"].strip())
        recent.append(1 if reasons else 0)
        if len(recent) == window:
            rate = sum(recent) / window
            if rate > alert_rate and not alerting:
                alerting = True
                alert = {"at_event": n, "window_reject_rate": round(rate, 3), "type": "ALERTE"}
                alerts.append(alert)
                if on_alert:
                    on_alert(alert)
            elif rate <= alert_rate and alerting:
                alerting = False
                alert = {"at_event": n, "window_reject_rate": round(rate, 3), "type": "RETOUR_NORMAL"}
                alerts.append(alert)
                if on_alert:
                    on_alert(alert)
    return {"events": n, "accepted": accepted, "rejected": rejected,
            "reject_rate": round(rejected / n, 4) if n else None,
            "rule_failures": dict(failures), "warnings": dict(warnings_count), "alerts": alerts}


def produce(source: Path, out: queue.Queue, rate: float, limit, inject_drift: bool):
    """Producteur : rejoue le fichier comme un flux, a `rate` evenements par seconde (0 = sans pause)."""
    with source.open(encoding="utf-8", newline="") as f:
        for i, row in enumerate(csv.DictReader(f), start=1):
            if limit and i > limit:
                break
            if inject_drift and i in DRIFT:
                row["MMSE"] = "99"   # valeur impossible, comme l'incident des 100 % de rejets
            out.put(row)
            if rate > 0:
                time.sleep(1 / rate)
    out.put(None)  # fin du flux


def stream_events(q: queue.Queue):
    while (row := q.get()) is not None:
        yield row


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulation de flux : controle qualite en continu")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--rate", type=float, default=0, help="evenements par seconde (0 = vitesse maximale)")
    parser.add_argument("--limit", type=int, default=None, help="nombre maximal d'evenements")
    parser.add_argument("--inject-drift", action="store_true", help="corrompt les evenements 600 a 799")
    args = parser.parse_args()
    if not args.source.exists():
        sys.exit(f"{args.source} introuvable")

    q = queue.Queue(maxsize=200)
    threading.Thread(target=produce, args=(args.source, q, args.rate, args.limit, args.inject_drift),
                     daemon=True).start()
    t0 = time.time()
    report = process_stream(
        stream_events(q),
        on_alert=lambda a: print(f"  [{a['type']}] evenement {a['at_event']} : "
                                 f"taux de rejet glissant {a['window_reject_rate'] * 100:.0f} %"))
    duration = time.time() - t0
    report.update({"pipeline": "stream-demo", "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
                   "source": args.source.name, "drift_injected": args.inject_drift, "window": WINDOW,
                   "alert_rate": ALERT_RATE, "duration_seconds": round(duration, 2),
                   "events_per_second": round(report["events"] / duration, 1) if duration else None,
                   "note": "Flux simule a partir d'une source figee : preuve de concept, hors chaine principale."})
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Evenements : {report['events']} | acceptes : {report['accepted']} | rejetes : {report['rejected']} "
          f"({(report['reject_rate'] or 0) * 100:.1f} %) | alertes : "
          f"{sum(a['type'] == 'ALERTE' for a in report['alerts'])}")
    print(f"Regles en echec : {report['rule_failures']}")
    print(f"Rapport : {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())