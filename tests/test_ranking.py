from datetime import date

from src.discovery import load_seed_schemes
from src.models import StudentProfile
from src.ranking import rank_schemes


def test_ranking_is_sorted_and_explainable():
    profile = StudentProfile(state="Delhi", domicile_state="Delhi", category="SC", gender="Male",
                             course_level="UG", course_name="B.Tech", institution_type="Government",
                             marks_percentage=80, annual_family_income=300000, year_of_study=1,
                             minority_status=True)
    ranked = rank_schemes(profile, load_seed_schemes(), today=date(2025, 1, 1))
    assert len(ranked) == 3
    assert [item.rank_score for item in ranked] == sorted((item.rank_score for item in ranked), reverse=True)
    assert set(ranked[0].score_breakdown) == {"eligibility_confidence", "deadline_urgency", "normalized_award", "source_quality"}


def test_expired_schemes_are_not_ranked():
    profile = StudentProfile(state="Delhi", domicile_state="Delhi", category="General", gender="Male",
                             course_level="UG", course_name="B.Tech", institution_type="Government",
                             marks_percentage=80, annual_family_income=300000, year_of_study=1)
    ranked = rank_schemes(profile, load_seed_schemes(), today=date(2026, 10, 18))
    assert all(item.scheme.deadline >= date(2026, 10, 18) for item in ranked)
    assert all(item.scheme.id == "central-sector-scholarship" for item in ranked)


def test_current_ineligible_scheme_remains_visible_with_failed_checks():
    profile = StudentProfile(state="Delhi", domicile_state="Delhi", category="General", gender="Male",
                             course_level="UG", course_name="B.Tech", institution_type="Government",
                             marks_percentage=80, annual_family_income=300000, year_of_study=1)
    scheme = next(s for s in load_seed_schemes() if s.id == "post-matric-sc-scholarship")
    ranked = rank_schemes(profile, [scheme], today=date(2025, 1, 1))
    assert len(ranked) == 1
    assert ranked[0].result.failed_rules
