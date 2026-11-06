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
MAX_PER_INDICATOR = 50
DB_NAME = "alzheimer_hub"

INDICATORS = {
    "mmse": '"Alzheimer Disease"[MeSH Terms] AND ("Mini-Mental State"[Title/Abstract] OR MMSE[Title/Abstract])',
    "blood_pressure": '"Alzheimer Disease"[MeSH Terms] AND ("blood pressure"[Title/Abstract] OR hypertension[MeSH Terms])',
    "cholesterol": '"Alzheimer Disease"[MeSH Terms] AND cholesterol[Title/Abstract]',
    "age": '"Alzheimer Disease"[MeSH Terms] AND "Age Factors"[MeSH Terms]',
}

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


def search(term: str):
    """Retourne (nombre total de resultats PubMed, liste des PMID les plus recents)."""
    res = _get("esearch.fcgi", db="pubmed", term=term, retmax=MAX_PER_INDICATOR,
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
def validate(rows: list):
    """Regles : pmid_present, title_present, year_valid, duplicate_pmid (rejet) ; abstract_present (signalement)."""
    max_year = datetime.now(timezone.utc).year + 1
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
        if r["year"] is None or not (1900 <= r["year"] <= max_year):
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


# ---------- Publication ----------
def _db():
    from pymongo import MongoClient
    uri = os.getenv("MONGODB_URI")
    if not uri:
        return None, None
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
        for name in INDICATORS:
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
        searches, pmid_to_ind = [], {}
        for name, term in INDICATORS.items():
            total, ids = search(term)
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
        accepted, rejected, failures = validate(rows)
        log.info("%s | Validation : %d acceptes, %d rejetes", run_id, len(accepted), len(rejected))
        for rule, n in failures.items():
            if n:
                log.warning("%s | Regle %s : %d echecs", run_id, rule, n)

        CURATED_FILE.parent.mkdir(parents=True, exist_ok=True)
        REJECTED_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CURATED_FILE.open("w", encoding="utf-8") as f:
            for d in accepted:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        with REJECTED_FILE.open("w", encoding="utf-8") as f:
            for d in rejected:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")

        n_mongo = publish_mongo(accepted, searches, run_id)
        report.update({
            "input_rows": len(rows), "accepted_rows": len(accepted), "rejected_rows": len(rejected),
            "rule_failures": failures, "mongo_documents": n_mongo, "source_file": raw_path.name,
            "status": "PASS_WITH_WARNINGS" if (rejected or failures["abstract_present"]) else "PASS",
        })
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