import sys
from pathlib import Path

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