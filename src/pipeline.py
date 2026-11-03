import argparse, json, logging, sys, time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from collect import collect
from validate import profile, validate, check_schema
from transform import transform
from publish import publish_db, log_run

CURATED = Path("data/curated/dataset.csv")
REJECTED = Path("data/rejected/rejected_rows.csv")
REPORT = Path("reports/run_report.json")
RUNS_DIR = Path("reports/runs")
LOG_FILE = Path("reports/pipeline.log")
CONTRACT_VERSION = "1.0"
MAX_REJECT_RATE = 0.20   # au-dela, la publication est bloquee

log = logging.getLogger("pipeline")

def setup_logging(run_id: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s | {run_id} | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
        force=True,
    )

def write_report(report: dict) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    REPORT.write_text(text, encoding="utf-8")
    (RUNS_DIR / f"run_{report['run_id']}.json").write_text(text, encoding="utf-8")

def main(source: str) -> int:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    setup_logging(run_id)
    t0 = time.time()
    for d in (CURATED.parent, REJECTED.parent, REPORT.parent):
        d.mkdir(parents=True, exist_ok=True)

    report = {"pipeline": "alzheimer-data-collector", "run_id": run_id,
              "contract_version": CONTRACT_VERSION, "source_requested": source}
    try:
        log.info("Debut du run, source demandee : %s", source)
        raw_path = collect(source)
        meta = json.loads(raw_path.with_suffix(".meta.json").read_text(encoding="utf-8"))
        collected = datetime.strptime(meta["collected_at"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        raw_age_h = round((datetime.now(timezone.utc) - collected).total_seconds() / 3600, 2)
        log.info("Raw : %s (age %s h, sha256 %s...)", raw_path.name, raw_age_h, meta["sha256"][:12])

        df = pd.read_csv(raw_path)
        check_schema(df)
        Path("reports/profile.json").write_text(
            json.dumps(profile(df), indent=2, default=str), encoding="utf-8")

        accepted, rejected, stats = validate(df)
        rejected.to_csv(REJECTED, index=False)
        rate = len(rejected) / len(df)
        log.info("Validation : %d acceptees, %d rejetees (%.1f %%)", len(accepted), len(rejected), rate * 100)
        for rule, n in stats.items():
            if n:
                log.warning("Regle %s : %d echecs", rule, n)

        if rate > MAX_REJECT_RATE:
            raise RuntimeError(f"Taux de rejet {rate:.1%} > seuil {MAX_REJECT_RATE:.0%} : publication bloquee")

        new = transform(accepted, raw_path.name)
        if CURATED.exists():   # UPSERT par cle metier
            new = pd.concat([pd.read_csv(CURATED), new]).drop_duplicates("patient_id", keep="last")
        tmp = CURATED.with_suffix(".tmp")   # ecriture atomique
        new.sort_values("patient_id").to_csv(tmp, index=False)
        tmp.replace(CURATED)
        log.info("Curated publie : %d lignes", len(new))

        n_db = publish_db(new, run_id)
        report["db_rows"] = n_db
        log.info("Base SQLite mise a jour : %d patients", n_db)

        report.update({
            "source_file": raw_path.name, "raw_age_hours": raw_age_h,
            "input_rows": len(df), "accepted_rows": len(accepted), "rejected_rows": len(rejected),
            "reject_rate": round(rate, 4), "duplicates_removed": stats["duplicate_patient_id"],
            "curated_total_rows": len(new), "rule_failures": stats,
            "status": "PASS_WITH_WARNINGS" if (len(rejected) or stats.get("cholesterol_plausible")) else "PASS",
        })
        code = 0
    except Exception as exc:
        log.error("INCIDENT : %s", exc)
        report.update({"status": "FAIL", "error": str(exc)})
        code = 1

    report["duration_seconds"] = round(time.time() - t0, 2)
    write_report(report)

    try:
        log_run(report)
    except Exception as exc:
        log.error("Journal des runs en base impossible : %s", exc)
        
    log.info("Fin du run : %s en %.2f s", report["status"], report["duration_seconds"])
    return code

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", default="data/source_download/alzheimers_disease_data.csv")
    sys.exit(main(p.parse_args().source))