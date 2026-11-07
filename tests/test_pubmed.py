import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pubmed  # noqa: E402

XML = b"""<PubmedArticleSet>
<PubmedArticle><MedlineCitation><PMID>111</PMID><Article><Journal><JournalIssue><PubDate><Year>2023</Year></PubDate></JournalIssue><Title>J Test</Title></Journal><ArticleTitle>MMSE and <i>APOE</i> study</ArticleTitle><Abstract><AbstractText>x</AbstractText></Abstract></Article><MeshHeadingList><MeshHeading><DescriptorName>Humans</DescriptorName></MeshHeading></MeshHeadingList></MedlineCitation></PubmedArticle>
<PubmedArticle><MedlineCitation><PMID>222</PMID><Article><Journal><JournalIssue><PubDate><MedlineDate>2021 Jan-Feb</MedlineDate></PubDate></JournalIssue><Title>J2</Title></Journal><ArticleTitle>No abstract</ArticleTitle></Article></MedlineCitation></PubmedArticle>
<PubmedArticle><MedlineCitation><PMID>333</PMID><Article><Journal><JournalIssue><PubDate></PubDate></JournalIssue></Journal><ArticleTitle></ArticleTitle></Article></MedlineCitation></PubmedArticle>
<PubmedArticle><MedlineCitation><PMID>111</PMID><Article><Journal><JournalIssue><PubDate><Year>2023</Year></PubDate></JournalIssue></Journal><ArticleTitle>dup</ArticleTitle><Abstract><AbstractText>x</AbstractText></Abstract></Article></MedlineCitation></PubmedArticle>
</PubmedArticleSet>"""


def test_parse_extracts_fields():
    rows = pubmed.parse(XML)
    assert len(rows) == 4
    assert rows[0]["title"] == "MMSE and APOE study"  # balises internes retirees
    assert rows[0]["mesh_terms"] == ["Humans"]
    assert rows[1]["year"] == 2021  # annee lue dans MedlineDate


def test_validate_rejects_and_flags():
    accepted, rejected, failures = pubmed.validate(pubmed.parse(XML))
    assert [r["pmid"] for r in accepted] == ["111", "222"]
    assert failures["title_present"] == 1
    assert failures["year_valid"] == 1
    assert failures["duplicate_pmid"] == 1
    assert failures["abstract_present"] == 2  # signalement, pas un rejet
    assert len(accepted) + len(rejected) == 4  # aucune ligne perdue en silence


def test_sample_file_is_valid():
    sample = Path(__file__).resolve().parents[1] / "data" / "raw" / "sample_pubmed.xml"
    if not sample.exists():
        return
    accepted, rejected, _ = pubmed.validate(pubmed.parse(sample.read_bytes()))
    assert accepted and not rejected


def make_xml(pmid, year, title="Titre"):
    return (f"<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>{pmid}</PMID><Article><Journal><JournalIssue>"
            f"<PubDate><Year>{year}</Year></PubDate></JournalIssue><Title>J</Title></Journal>"
            f"<ArticleTitle>{title}</ArticleTitle><Abstract><AbstractText>x</AbstractText></Abstract>"
            f"</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>").encode()


def test_contract_drives_year_bounds():
    contract = pubmed.load_contract()
    contract["rules"]["year_min"] = 2022  # un contrat plus strict change le comportement
    accepted, rejected, _ = pubmed.validate(pubmed.parse(make_xml("1", 2021)), contract)
    assert not accepted and rejected[0]["reject_reason"] == "year_valid"


def test_reject_rate_above_threshold_blocks_publication():
    with pytest.raises(ValueError, match="publication bloquee"):
        pubmed.check_reject_rate(5, 10)
    assert pubmed.check_reject_rate(1, 10) == 0.1


def test_freshness_flags_old_literature():
    now = datetime.now(timezone.utc).year
    recent = [{"year": now}]
    old = [{"year": now - 5}]
    assert pubmed.check_freshness(recent)[1] == "OK"
    assert pubmed.check_freshness(old)[1] == "STALE"
    assert pubmed.check_freshness([])[1] == "UNKNOWN"


def run_main(tmp_path, monkeypatch, xml):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.setattr(pubmed, "search", lambda term, retmax: (10, ["1"]))
    monkeypatch.setattr(pubmed, "fetch_xml", lambda pmids: xml)
    code = pubmed.main()
    report = json.loads(next((tmp_path / "reports" / "runs").glob("pubmed_*.json")).read_text("utf-8"))
    return code, report


def test_pubmed_run_passes_and_writes_curated(tmp_path, monkeypatch):
    code, report = run_main(tmp_path, monkeypatch, make_xml("1", datetime.now(timezone.utc).year))
    assert code == 0 and report["status"] == "PASS" and report["freshness"] == "OK"
    assert (tmp_path / "data" / "curated" / "pubmed_articles.jsonl").exists()


def test_pubmed_incident_keeps_evidence_and_blocks_curated(tmp_path, monkeypatch):
    code, report = run_main(tmp_path, monkeypatch, make_xml("1", 1800))  # annee impossible : 100 % de rejets
    assert code == 1 and report["status"] == "FAIL"
    assert "publication bloquee" in report["error"]
    assert list((tmp_path / "data" / "raw").glob("pubmed_*.xml"))            # raw conserve
    assert (tmp_path / "data" / "rejected" / "pubmed_rejected.jsonl").read_text("utf-8").strip()
    assert not (tmp_path / "data" / "curated" / "pubmed_articles.jsonl").exists()  # curated intact