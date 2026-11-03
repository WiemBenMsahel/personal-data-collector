import hashlib, json, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

RAW_DIR = Path("data/raw")
SOURCE_URL = "https://www.kaggle.com/datasets/rabieelkharoua/alzheimers-disease-dataset"

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def collect(src: str) -> Path:
    src_path = Path(src)
    if not src_path.exists():
        raise FileNotFoundError(f"Source introuvable : {src_path}")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    digest = sha256(src_path)
    # idempotence : meme contenu deja collecte -> on reutilise le fichier raw
    for f in RAW_DIR.glob("alzheimers_*.csv"):
        if sha256(f) == digest:
            print(f"Deja collecte : {f.name}")
            return f
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RAW_DIR / f"alzheimers_{stamp}.csv"
    shutil.copy2(src_path, out)  # copie NON modifiee
    meta = {"source_url": SOURCE_URL, "collected_at": stamp, "sha256": digest}
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return out

if __name__ == "__main__":
    print(collect(sys.argv[1] if len(sys.argv) > 1 else "data/source_download/alzheimers_disease_data.csv"))