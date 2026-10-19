from src.models import Scheme, StudentProfile
from src.tinyfish_client import TinyFishClient


def verify_scheme_live(profile: StudentProfile, scheme: Scheme, client: TinyFishClient) -> dict:
    goal = f"""Open the official scholarship page and verify this synthetic student profile against visible eligibility information.
Do not log in, enter personal data, submit any form, bypass CAPTCHA, or continue into application submission.
Profile: state={profile.state}; domicile_state={profile.domicile_state}; category={profile.category}; gender={profile.gender};
course_level={profile.course_level}; course_name={profile.course_name}; marks_percentage={profile.marks_percentage};
annual_family_income={profile.annual_family_income}; disability_status={profile.disability_status};
minority_status={profile.minority_status}; year_of_study={profile.year_of_study}; entry_type={profile.entry_type};
twelfth_marks_percentage={profile.twelfth_marks_percentage}; institution_aicte_approved={profile.institution_aicte_approved};
girl_children_in_family={profile.girl_children_in_family}; receives_other_scholarship={profile.receives_other_scholarship}.
Return JSON with fields: status, deadline, required_documents, visible_rules, evidence_urls, notes.
Use only information visible on the official site and report unknown fields as unknown."""
    result = client.run_agent(str(scheme.official_url), goal)
    return {"scheme_id": scheme.id, "official_url": str(scheme.official_url), "result": result}
