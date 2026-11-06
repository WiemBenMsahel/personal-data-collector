import sys
sys.path.insert(0, "src")
from datetime import datetime, timezone
from purge import select_purge

CONTRACT = {"retention": {"raw_days": 90, "reports_days": 90, "keep_last_runs": 2}}
NOW = datetime(2026, 11, 8, tzinfo=timezone.utc)


def touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x")


def test_purge_selection(tmp_path):
    raw, runs = tmp_path / "raw", tmp_path / "runs"
    for name in ["alzheimers_20260101T000000Z.csv", "alzheimers_20260101T000000Z.meta.json",
                 "alzheimers_20260201T000000Z.csv", "alzheimers_20261105T000000Z.csv",
                 "sample_source.csv"]:
        touch(raw / name)
    for name in ["run_20260101T000000Z.json", "run_20260102T000000Z.json",
                 "run_20261105T000000Z.json", "run_20261106T000000Z.json"]:
        touch(runs / name)

    victims = {p.name for p in select_purge(CONTRACT, NOW, raw, runs)}

    assert "alzheimers_20260101T000000Z.csv" in victims
    assert "alzheimers_20260101T000000Z.meta.json" in victims      # le meta suit son csv
    assert "alzheimers_20260201T000000Z.csv" in victims            # plus de 90 jours
    assert "alzheimers_20261105T000000Z.csv" not in victims        # le plus recent est conserve
    assert "sample_source.csv" not in victims                      # echantillon jamais touche
    assert {"run_20260101T000000Z.json", "run_20260102T000000Z.json"} <= victims
    assert "run_20261106T000000Z.json" not in victims              # derniers rapports conserves