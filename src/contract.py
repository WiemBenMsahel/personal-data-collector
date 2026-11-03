from pathlib import Path
import yaml

CONTRACT_PATH = Path("config/data_contract.yaml")

def load_contract(path: Path = CONTRACT_PATH) -> dict:
    contract = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    contract["_src"] = {c["name"]: c["source"] for c in contract["columns"]}
    return contract