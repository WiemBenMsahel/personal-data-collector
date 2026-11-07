import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import stream_demo  # noqa: E402


def event(i, **overrides):
    row = {"PatientID": str(i), "Age": "75", "MMSE": "15", "Diagnosis": "0",
           "SystolicBP": "130", "DiastolicBP": "80", "CholesterolTotal": "220"}
    row.update(overrides)
    return row


def test_valid_events_are_accepted():
    report = stream_demo.process_stream([event(i) for i in range(300)])
    assert report["accepted"] == 300 and report["rejected"] == 0 and report["alerts"] == []


def test_each_rule_rejects_with_its_name():
    cases = {"age_valid": {"Age": "200"}, "mmse_range": {"MMSE": "99"}, "diagnosis_domain": {"Diagnosis": "2"},
             "bp_coherent": {"DiastolicBP": "140"}, "patient_id_present": {"PatientID": ""}}
    for rule, change in cases.items():
        reasons, _ = stream_demo.check_event(event(1, **change), set())
        assert rule in reasons


def test_duplicate_and_cholesterol_warning():
    report = stream_demo.process_stream([event(1), event(1), event(2, CholesterolTotal="50")])
    assert report["rule_failures"] == {"duplicate_patient_id": 1}
    assert report["warnings"] == {"cholesterol_plausible": 1}
    assert report["accepted"] == 2  # un avertissement ne rejette pas


def test_drift_raises_alert_then_recovers():
    events = [event(i) for i in range(200)] + [event(1000 + i, MMSE="99") for i in range(100)] \
             + [event(2000 + i) for i in range(300)]
    alerts = []
    report = stream_demo.process_stream(events, on_alert=alerts.append)
    kinds = [a["type"] for a in report["alerts"]]
    assert kinds == ["ALERTE", "RETOUR_NORMAL"] and alerts == report["alerts"]
    assert report["rejected"] == 100


def test_stream_matches_batch_logic_on_a_csv(tmp_path):
    path = tmp_path / "src.csv"
    rows = [event(i) for i in range(50)] + [event(100 + i, DiastolicBP="200") for i in range(5)]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    import queue
    q = queue.Queue()
    stream_demo.produce(path, q, rate=0, limit=None, inject_drift=False)
    report = stream_demo.process_stream(stream_demo.stream_events(q))
    assert (report["events"], report["accepted"], report["rejected"]) == (55, 50, 5)