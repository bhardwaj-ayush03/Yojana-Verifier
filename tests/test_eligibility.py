from src.discovery import load_seed_schemes
from src.eligibility import evaluate_scheme
from src.models import StudentProfile, EligibilityStatus
from src.eligibility import _matches


def test_sc_student_matches_post_matric_scheme():
    profile = StudentProfile(state="Bihar", domicile_state="Bihar", category="SC", gender="Female",
                             course_level="UG", course_name="B.A.", institution_type="Government",
                             marks_percentage=70, annual_family_income=200000, year_of_study=2)
    scheme = next(s for s in load_seed_schemes() if s.id == "post-matric-sc-scholarship")
    result = evaluate_scheme(profile, scheme)
    assert result.status == EligibilityStatus.LIKELY_ELIGIBLE
    assert not result.failed_rules


def test_general_student_does_not_match_sc_scheme():
    profile = StudentProfile(state="Bihar", domicile_state="Bihar", category="General", gender="Female",
                             course_level="UG", course_name="B.A.", institution_type="Government",
                             marks_percentage=70, annual_family_income=200000, year_of_study=2)
    scheme = next(s for s in load_seed_schemes() if s.id == "post-matric-sc-scholarship")
    assert evaluate_scheme(profile, scheme).status == EligibilityStatus.LIKELY_INELIGIBLE


def test_scheme_without_rules_needs_verification():
    profile = StudentProfile(state="Bihar", domicile_state="Bihar", category="General", gender="Female",
                             course_level="UG", course_name="B.A.", institution_type="Government",
                             marks_percentage=70, annual_family_income=200000, year_of_study=2)
    scheme = load_seed_schemes()[0].model_copy(update={"eligibility_rules": []})
    assert evaluate_scheme(profile, scheme).status == EligibilityStatus.NEEDS_VERIFICATION
    assert evaluate_scheme(profile, scheme).confidence == 0


def test_category_aliases_match_official_wording():
    assert _matches("ST", "eq", "Scheduled Tribe", field="category")
    assert _matches("SC", "in", ["Scheduled Castes", "Scheduled Tribes"], field="category")
    assert not _matches("General", "eq", "Scheduled Tribe", field="category")


def test_post_secondary_includes_undergraduate_study():
    assert _matches("UG", "in", ["post-matriculation", "post-secondary"], field="course_level")
