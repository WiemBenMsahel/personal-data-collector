import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import run_all  # noqa: E402

TASKS = {
    "a": {"cmd": ["a"], "deps": []},
    "b": {"cmd": ["b"], "deps": ["a"]},
    "c": {"cmd": ["c"], "deps": []},
}


def test_dependencies_run_first():
    calls = []
    run_all.run_dag(TASKS, runner=lambda cmd: calls.append(cmd[0]) or 0)
    assert calls.index("a") < calls.index("b")


def test_failure_skips_descendants_but_not_independent_tasks():
    status, _ = run_all.run_dag(TASKS, runner=lambda cmd: 1 if cmd == ["a"] else 0)
    assert status == {"a": "FAILED", "b": "UPSTREAM_FAILED", "c": "SUCCESS"}


def test_resume_replays_only_what_did_not_succeed():
    calls = []
    previous = {"a": "SUCCESS", "b": "UPSTREAM_FAILED", "c": "SUCCESS"}
    status, _ = run_all.run_dag(TASKS, runner=lambda cmd: calls.append(cmd[0]) or 0,
                                previous=previous, resume=True)
    assert calls == ["b"]
    assert all(s in run_all.OK for s in status.values())


def test_project_dag_is_consistent():
    names = set(run_all.TASKS)
    for task in run_all.TASKS.values():
        assert set(task["deps"]) <= names