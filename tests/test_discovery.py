from src.discovery import _content_text, _has_usable_details, _is_relevant_candidate, discover_live_schemes
from src.models import Scheme, StudentProfile


def test_content_text_handles_missing_and_nullable_provider_text() -> None:
    assert _content_text({"text": "  official content  "}) == "official content"
    assert _content_text({"text": None}) == ""
    assert _content_text({}) == ""
    assert _content_text(None) == ""


def test_fetched_candidate_without_normalized_rules_is_not_presented_as_scholarship() -> None:
    scheme = Scheme(id="live-1", name="Official source", official_url="https://scholarships.gov.in/",
                    provider="scholarships.gov.in", academic_year="Current",
                    description="Discovered live by TinyFish Search and fetched by TinyFish Fetch.")
    assert not _has_usable_details(scheme)


def test_relevance_filter_rejects_other_state_handbook() -> None:
    profile = StudentProfile(state="Bihar", domicile_state="Bihar", category="ST", gender="Female",
                             course_level="UG", course_name="B.Tech", institution_type="Government",
                             marks_percentage=95, annual_family_income=250000, year_of_study=1)
    candidate = {"title": "A Handbook of Scholarship Schemes", "snippet": "Meghalaya scholarship handbook",
                 "url": "https://meghalaya.gov.in/handbook.pdf"}
    assert not _is_relevant_candidate(candidate, profile)


def test_relevance_filter_rejects_generic_central_portal() -> None:
    profile = StudentProfile(state="Bihar", domicile_state="Bihar", category="ST", gender="Female",
                             course_level="UG", course_name="B.Tech", institution_type="Government",
                             marks_percentage=95, annual_family_income=250000, year_of_study=1)
    candidate = {"title": "National Scholarship Portal", "snippet": "Current scholarship schemes",
                 "url": "https://scholarships.gov.in/"}
    assert not _is_relevant_candidate(candidate, profile)


def test_fetch_results_are_matched_by_url_and_other_states_are_excluded(monkeypatch):
    import src.extraction as extraction
    import src.knowledge as knowledge

    profile = StudentProfile(state="Bihar", domicile_state="Bihar", category="ST", gender="Female",
                             course_level="UG", course_name="B.Tech", institution_type="Government",
                             marks_percentage=95, annual_family_income=250000, year_of_study=1)
    bihar_url = "https://pmsonline.bihar.gov.in/scholarship/st"
    central_url = "https://scholarships.gov.in/public/schemeGuidelines/ST.pdf"
    other_url = "https://meghalaya.gov.in/scholarship/st"

    class Client:
        def search(self, _query):
            return {"results": [{"url": other_url, "title": "Meghalaya ST Scholarship"},
                                {"url": bihar_url, "title": "Bihar ST Scholarship"},
                                {"url": central_url, "title": "Post Matric ST Scholarship"}]}

        def fetch(self, urls):
            assert other_url not in urls
            return {"results": [{"url": central_url, "text": "CENTRAL " * 100},
                                {"url": bihar_url, "text": "BIHAR " * 100}]}

    monkeypatch.setattr(extraction, "extract_scheme", lambda text, base, *_: base.model_copy(
        update={"required_documents": [text]}))
    monkeypatch.setattr(knowledge, "store_evidence", lambda *_: None)
    report = {}
    schemes = discover_live_schemes("query", Client(), "test-key", profile=profile, diagnostics=report)
    assert len(schemes) == 2
    assert {str(s.official_url): s.required_documents[0].split()[0] for s in schemes} == {
        bihar_url: "BIHAR", central_url: "CENTRAL"}
    assert report["relevant_official_hits"] == 2
