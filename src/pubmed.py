"""Seconde source : litterature PubMed (API NCBI E-utilities).

Chaine : recherche par indicateur -> raw XML horodate -> parsing -> validation (rejets)
         -> curated JSONL -> publication MongoDB Atlas (UPSERT sur le pmid).
Un document = un article (cle metier : pmid). Un article peut concerner plusieurs indicateurs.
Minimisation : on ne conserve que des metadonnees (pas le texte des resumes).
"""
import argparse
import json
import logging
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
RAW_DIR = Path("data/raw")
CURATED_FILE = Path("data/curated/pubmed_articles.jsonl")
REJECTED_FILE = Path("data/rejected/pubmed_rejected.jsonl")
REPORT_DIR = Path("reports/runs")
DB_NAME = "alzheimer_hub"
CONTRACT_FILE = Path(__file__).resolve().parents[1] / "config" / "pubmed_contract.yaml"


def load_contract() -> dict:
    """Le contrat est la source de verite : requetes, regles, seuils, fraicheur."""
    with CONTRACT_FILE.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("pubmed")


# ---------- Collecte ----------
def _get(path: str, **params) -> requests.Response:
    params["tool"] = "alzheimer-data-hub"
    if os.getenv("NCBI_EMAIL"):
        params["email"] = os.getenv("NCBI_EMAIL")
    time.sleep(0.4)  # politesse : 3 requetes par seconde maximum sans cle API
    resp = requests.get(f"{EUTILS}/{path}", params=params, timeout=30)
    resp.raise_for_status()
    return resp


def search(term: str, retmax: int):
    """Retourne (nombre total de resultats PubMed, liste des PMID les plus recents)."""
    res = _get("esearch.fcgi", db="pubmed", term=term, retmax=retmax,
               retmode="json", sort="pub_date").json()["esearchresult"]
    return int(res["count"]), res["idlist"]


def fetch_xml(pmids: list) -> bytes:
    return _get("efetch.fcgi", db="pubmed", id=",".join(pmids), retmode="xml").content


# ---------- Transformation ----------
def parse(xml_bytes: bytes) -> list:
    root = ET.fromstring(xml_bytes)
    rows = []
    for art in root.findall(".//PubmedArticle"):
        title_el = art.find(".//ArticleTitle")
        title = "".join(title_el.itertext()).strip() if title_el is not None else ""
        year = art.findtext(".//JournalIssue/PubDate/Year")
        if not year:
            medline_date = art.findtext(".//JournalIssue/PubDate/MedlineDate")
            year = medline_date[:4] if medline_date else None
        rows.append({
            "pmid": art.findtext("MedlineCitation/PMID"),
            "title": title,
            "journal": art.findtext(".//Journal/Title"),
            "year": int(year) if year and year.isdigit() else None,
            "has_abstract": art.find(".//Abstract/AbstractText") is not None,
            "mesh_terms": [m.text for m in art.findall(".//MeshHeading/DescriptorName") if m.text],
        })
    return rows


# ---------- Validation ----------
def validate(rows: list, contract: dict = None):
    """Regles : pmid_present, title_present, year_valid, duplicate_pmid (rejet) ; abstract_present (signalement).
    Les bornes de l'annee viennent du contrat."""
    contract = contract or load_contract()
    min_year = contract["rules"]["year_min"]
    max_year = datetime.now(timezone.utc).year + contract["rules"]["year_max_offset"]
    accepted, rejected, seen = [], [], set()
    failures = {"pmid_present": 0, "title_present": 0, "year_valid": 0,
                "duplicate_pmid": 0, "abstract_present": 0}
    for r in rows:
        reasons = []
        if not r["pmid"]:
            reasons.append("pmid_present")
        elif r["pmid"] in seen:
            reasons.append("duplicate_pmid")
        if not r["title"]:
            reasons.append("title_present")
        if r["year"] is None or not (min_year <= r["year"] <= max_year):
            reasons.append("year_valid")
        if not r["has_abstract"]:
            failures["abstract_present"] += 1  # signalement seulement
        if reasons:
            for reason in reasons:
                failures[reason] += 1
            rejected.append({**r, "reject_reason": ";".join(reasons)})
        else:
            seen.add(r["pmid"])
            accepted.append(r)
    return accepted, rejected, failures


def check_reject_rate(n_rejected: int, n_total: int, contract: dict = None) -> float:
    """Bloque la publication si trop d'articles sont rejetes (meme logique que pour les patients)."""
    contract = contract or load_contract()
    rate = n_rejected / n_total if n_total else 1.0
    limit = contract["thresholds"]["max_reject_rate"]
    if rate > limit:
        raise ValueError(f"Taux de rejet {rate * 100:.1f}% > seuil {limit * 100:.0f}% : publication bloquee")
    return rate


def check_freshness(accepted: list, contract: dict = None):
    """Age de la donnee la plus recente : annee du dernier article, comparee au seuil du contrat."""
    contract = contract or load_contract()
    years = [r["year"] for r in accepted if r["year"]]
    if not years:
        return None, "UNKNOWN"
    newest = max(years)
    age = datetime.now(timezone.utc).year - newest
    limit = contract["freshness"]["max_newest_article_age_years"]
    return newest, ("STALE" if age > limit else "OK")


# ---------- Publication ----------
def _db():
    uri = os.getenv("MONGODB_URI")
    if not uri:
        return None, None
    from pymongo import MongoClient
    client = MongoClient(uri, serverSelectionTimeoutMS=8000)
    return client, client[DB_NAME]


def publish_mongo(docs: list, searches: list, run_id: str):
    client, db = _db()
    if db is None:
        log.warning("MONGODB_URI absente : publication MongoDB ignoree (curated JSONL seulement)")
        return None
    from pymongo import ReplaceOne, UpdateOne
    try:
        if docs:
            db["articles"].bulk_write(
                [UpdateOne({"_id": d["pmid"]}, {"$set": {**d, "loaded_run_id": run_id}}, upsert=True)
                 for d in docs])
        db["searches"].bulk_write(
            [ReplaceOne({"_id": f"{run_id}:{s['indicator']}"}, {**s, "run_id": run_id}, upsert=True)
             for s in searches])
        return db["articles"].count_documents({})
    finally:
        client.close()


def kpi():
    client, db = _db()
    if db is None:
        sys.exit("MONGODB_URI absente : renseignez-la dans .env")
    try:
        last = {}
        for s in db["searches"].find().sort("run_id", -1):
            last.setdefault(s["indicator"], s)
        stored = {r["_id"]: r for r in db["articles"].aggregate([
            {"$unwind": "$indicators"},
            {"$group": {"_id": "$indicators", "articles_stockes": {"$sum": 1}}}])}
        print(f"{'indicateur':<16}{'articles PubMed (total)':>26}{'articles stockes':>20}")
        for name in load_contract()["indicators"]:
            total = last.get(name, {}).get("pubmed_total")
            print(f"{name:<16}{str(total):>26}{stored.get(name, {}).get('articles_stockes', 0):>20}")
        print("Documents dans la collection articles :", db["articles"].count_documents({}))
    finally:
        client.close()


# ---------- Orchestration ----------
def main() -> int:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    t0 = time.time()
    report = {"pipeline": "pubmed-literature", "run_id": run_id, "status": "FAIL"}
    try:
        contract = load_contract()
        report["contract_version"] = contract["version"]
        retmax = contract["collection"]["max_articles_per_indicator"]
        searches, pmid_to_ind = [], {}
        for name, term in contract["indicators"].items():
            total, ids = search(term, retmax)
            searches.append({"indicator": name, "query": term, "pubmed_total": total,
                             "retrieved": len(ids)})
            for pmid in ids:
                pmid_to_ind.setdefault(pmid, set()).add(name)
            log.info("%s | %s | %d articles PubMed, %d recuperes", run_id, name, total, len(ids))
        if not pmid_to_ind:
            raise RuntimeError("Aucun article retourne par PubMed")

        xml_bytes = fetch_xml(sorted(pmid_to_ind))
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        raw_path = RAW_DIR / f"pubmed_{run_id}.xml"
        raw_path.write_bytes(xml_bytes)
        log.info("%s | Raw : %s", run_id, raw_path.name)

        rows = parse(xml_bytes)
        for r in rows:
            r["indicators"] = sorted(pmid_to_ind.get(r["pmid"], []))
            r["collected_at"] = datetime.now(timezone.utc).isoformat()
            r["source_file"] = raw_path.name
        accepted, rejected, failures = validate(rows, contract)
        log.info("%s | Validation : %d acceptes, %d rejetes", run_id, len(accepted), len(rejected))
        for rule, n in failures.items():
            if n:
                log.warning("%s | Regle %s : %d echecs", run_id, rule, n)

        # Les rejets sont toujours conserves, meme si la publication est ensuite bloquee.
        REJECTED_FILE.parent.mkdir(parents=True, exist_ok=True)
        with REJECTED_FILE.open("w", encoding="utf-8") as f:
            for d in rejected:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        report.update({"input_rows": len(rows), "accepted_rows": len(accepted),
                       "rejected_rows": len(rejected), "rule_failures": failures,
                       "source_file": raw_path.name})
        report["reject_rate"] = round(check_reject_rate(len(rejected), len(rows), contract), 4)

        newest_year, freshness = check_freshness(accepted, contract)
        report.update({"newest_article_year": newest_year, "freshness": freshness})
        if freshness == "STALE":
            log.warning("%s | Fraicheur : article le plus recent de %s (seuil %d an)",
                        run_id, newest_year, contract["freshness"]["max_newest_article_age_years"])

        CURATED_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CURATED_FILE.open("w", encoding="utf-8") as f:
            for d in accepted:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")

        n_mongo = publish_mongo(accepted, searches, run_id)
        report["mongo_documents"] = n_mongo
        warned = bool(rejected) or failures["abstract_present"] or freshness == "STALE"
        report["status"] = "PASS_WITH_WARNINGS" if warned else "PASS"
        if n_mongo is not None:
            log.info("%s | MongoDB Atlas mis a jour : %d articles", run_id, n_mongo)
    except Exception as exc:  # incident : on journalise, on garde la preuve, on sort en erreur
        report["error"] = str(exc)
        log.error("%s | INCIDENT : %s", run_id, exc)
    report["duration_seconds"] = round(time.time() - t0, 2)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / f"pubmed_{run_id}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("%s | Fin du run : %s en %.2f s", run_id, report["status"], report["duration_seconds"])
    return 0 if report["status"] != "FAIL" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collecte PubMed vers MongoDB Atlas")
    parser.add_argument("--kpi", action="store_true", help="afficher les compteurs depuis MongoDB")
    args = parser.parse_args()
    if args.kpi:
        kpi()
    else:
        sys.exit(main())