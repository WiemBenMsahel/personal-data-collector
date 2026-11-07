"""Export metier : curated patients au format Parquet (echange avec d'autres outils d'analyse)."""
import sys
from pathlib import Path

import pandas as pd

SRC = Path("data/curated/dataset.csv")
DST = Path("data/curated/dataset.parquet")


def export(src: Path = SRC, dst: Path = DST) -> int:
    df = pd.read_csv(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dst, index=False)
    return len(df)


def main() -> int:
    if not SRC.exists():
        sys.exit(f"{SRC} introuvable : lancez d'abord python src/pipeline.py")
    n = export()
    print(f"Export Parquet : {n} lignes -> {DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())