import argparse, json, time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from collect import collect
from validate import profile, validate
from transform import transform

CURATED = Path("data/curated/dataset.csv")
REJECTED = Path("data/rejected/rejected_rows.csv")
REPORT = Path("reports/run_report.json")

def main(source: str):
    t0 = time.time()
    for d in (CURATED.parent, REJECTED.parent, REPORT.parent):
        d.mkdir(parents=True, exist_ok=True)

    raw_path = collect(source)
    df = pd.read_csv(raw_path)
    Path("reports/profile.json").write_text(json.dumps(profile(df), indent=2, default=str), encoding="utf-8")

    accepted, rejected, stats = validate(df)
    new = transform(accepted, raw_path.name)

    # UPSERT par cle metier -> rejeu sans duplication
    if CURATED.exists():
        new = pd.concat([pd.read_csv(CURATED), new]).drop_duplicates("patient_id", keep="last")
    tmp = CURATED.with_suffix(".tmp")           # ecriture atomique
    new.sort_values("patient_id").to_csv(tmp, index=False)
    tmp.replace(CURATED)

    rejected.to_csv(REJECTED, index=False)

    flags = stats.get("cholesterol_plausible", 0)
    rate = len(rejected) / len(df)
    status = "FAIL" if rate > 0.2 else ("PASS_WITH_WARNINGS" if len(rejected) or flags else "PASS")
    report = {
        "pipeline": "alzheimer-data-collector",
        "executed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_file": raw_path.name,
        "input_rows": len(df), "accepted_rows": len(accepted), "rejected_rows": len(rejected),
        "duplicates_removed": stats["duplicate_patient_id"],
        "curated_total_rows": len(new),
        "rule_failures": stats, "quality_status": status,
        "duration_seconds": round(time.time() - t0, 2),
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", default="data/source_download/alzheimers_disease_data.csv")
    main(p.parse_args().source)