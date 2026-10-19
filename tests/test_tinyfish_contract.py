from src.discovery import _is_trusted_url, build_discovery_queries
from src.models import StudentProfile


def test_only_official_domains_are_trusted():
    assert _is_trusted_url("https://scholarships.gov.in/All-Scholarships")
    assert _is_trusted_url("https://example.nic.in/scholarships")
    assert not _is_trusted_url("https://example.com/scholarship")


def test_discovery_queries_are_built_from_profile():
    profile = StudentProfile(state="Kerala", domicile_state="Kerala", category="OBC", gender="Male",
                             course_level="PG", course_name="M.Tech", institution_type="Government",
                             marks_percentage=80, annual_family_income=300000, year_of_study=1)
    queries = build_discovery_queries(profile)
    combined = " ".join(queries)
    assert "Kerala" in combined
    assert "M.Tech" in combined
    assert "OBC" in combined
    assert "Pragati" not in combined
