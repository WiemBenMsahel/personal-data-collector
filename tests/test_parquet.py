import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import export_parquet  # noqa: E402


def test_parquet_export_keeps_all_rows_and_values(tmp_path):
    src, dst = tmp_path / "in.csv", tmp_path / "out.parquet"
    pd.DataFrame({"patient_id": [1, 2], "mmse": [12.5, 20.0], "diagnosis_label": ["A", "B"]}).to_csv(src, index=False)
    assert export_parquet.export(src, dst) == 2
    pd.testing.assert_frame_equal(pd.read_parquet(dst), pd.read_csv(src))