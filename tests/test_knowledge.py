from src.knowledge import search_evidence, store_evidence
from src.models import Scheme


def test_evidence_store_retrieves_by_scheme(monkeypatch, tmp_path):
    import src.knowledge as knowledge
    monkeypatch.setattr(knowledge, "DB_PATH", tmp_path / "knowledge.db")
    scheme = Scheme(id="scheme-1", name="Test Scholarship", official_url="https://scholarships.gov.in/",
                    provider="NSP", academic_year="2026-27")
    store_evidence(scheme, "Income certificate is required. The application deadline is 31 October 2026.")
    results = search_evidence("scheme-1", "What documents are required?")
    assert results
    assert "Income certificate" in results[0]["text"]


def test_identical_evidence_is_kept_for_each_scheme(monkeypatch, tmp_path):
    import src.knowledge as knowledge
    monkeypatch.setattr(knowledge, "DB_PATH", tmp_path / "knowledge.db")
    first = Scheme(id="first", name="First", official_url="https://scholarships.gov.in/first",
                   provider="NSP", academic_year="2026-27")
    second = first.model_copy(update={"id": "second", "name": "Second"})
    store_evidence(first, "Income certificate required")
    store_evidence(second, "Income certificate required")
    assert search_evidence("first", "income certificate")
    assert search_evidence("second", "income certificate")
