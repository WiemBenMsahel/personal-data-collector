"""Orchestration minimale : un DAG explicite de taches, sans orchestrateur externe.

Chaque tache est une commande existante du projet. Une tache ne demarre que si ses
dependances ont reussi ; si une tache echoue, ses descendantes sont ignorees
(UPSTREAM_FAILED) mais les taches independantes continuent. --resume rejoue seulement
ce qui n'avait pas reussi lors de la derniere execution.
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from graphlib import TopologicalSorter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = ROOT / "reports" / "dag_last_run.json"
PY = sys.executable

TASKS = {
    "patients":       {"cmd": [PY, "src/pipeline.py"],       "deps": []},
    "pubmed":         {"cmd": [PY, "src/pubmed.py"],         "deps": []},
    "export_parquet": {"cmd": [PY, "src/export_parquet.py"], "deps": ["patients"]},
    "model":          {"cmd": [PY, "src/model.py"],          "deps": ["patients"]},
    "purge_dry_run":  {"cmd": [PY, "src/purge.py"],          "deps": ["patients", "pubmed"]},
}
OK = ("SUCCESS", "SKIPPED_OK")


def default_runner(cmd: list) -> int:
    return subprocess.run(cmd, cwd=ROOT).returncode


def run_dag(tasks: dict, runner=default_runner, previous: dict = None, resume: bool = False):
    """Retourne (statuts, durees). Les taches sont executees dans l'ordre topologique."""
    order = TopologicalSorter({name: t["deps"] for name, t in tasks.items()}).static_order()
    status, durations = {}, {}
    for name in order:
        if any(status[dep] not in OK for dep in tasks[name]["deps"]):
            status[name] = "UPSTREAM_FAILED"
            continue
        if resume and previous and previous.get(name) == "SUCCESS":
            status[name] = "SKIPPED_OK"
            continue
        t0 = time.time()
        code = runner(tasks[name]["cmd"])
        durations[name] = round(time.time() - t0, 2)
        status[name] = "SUCCESS" if code == 0 else "FAILED"
    return status, durations


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute le DAG du projet")
    parser.add_argument("--resume", action="store_true", help="rejouer seulement les taches non reussies")
    parser.add_argument("--dry-run", action="store_true", help="afficher l'ordre sans rien executer")
    args = parser.parse_args()

    if args.dry_run:
        order = TopologicalSorter({n: t["deps"] for n, t in TASKS.items()}).static_order()
        for name in order:
            print(f"{name:<16} depend de : {', '.join(TASKS[name]['deps']) or '-'}")
        return 0

    previous = None
    if args.resume and STATE_FILE.exists():
        previous = {n: t["status"] for n, t in json.loads(STATE_FILE.read_text("utf-8"))["tasks"].items()}

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    status, durations = run_dag(TASKS, previous=previous, resume=args.resume)
    overall = "PASS" if all(s in OK for s in status.values()) else "FAIL"

    # SKIPPED_OK est memorise comme SUCCESS : la tache a bien reussi lors d'un run precedent.
    saved = {n: {"status": "SUCCESS" if s == "SKIPPED_OK" else s,
                 "duration_seconds": durations.get(n), "deps": TASKS[n]["deps"]}
             for n, s in status.items()}
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"run_id": run_id, "status": overall, "tasks": saved},
                                     indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDAG {run_id} : {overall}")
    for name, s in status.items():
        print(f"  {name:<16}{s:<18}{durations.get(name, '-')}")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())