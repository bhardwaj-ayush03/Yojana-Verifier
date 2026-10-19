from datetime import date

from src.models import RankedScheme, Scheme, StudentProfile
from src.eligibility import evaluate_scheme


def rank_schemes(profile: StudentProfile, schemes: list[Scheme], today: date | None = None) -> list[RankedScheme]:
    today = today or date.today()
    ranked = []
    for scheme in schemes:
        # Expired opportunities must never be shown as current matches.
        if scheme.is_expired(today):
            continue
        result = evaluate_scheme(profile, scheme)
        urgency = _deadline_urgency(scheme, today)
        award = min((scheme.award_amount or 0) / 50000, 1)
        quality = 1.0 if ".gov.in" in str(scheme.official_url) else 0.7
        # Keep current candidates visible even when one extracted rule fails. The UI
        # labels these as likely ineligible and shows the failed checks; hiding them
        # made every live-search problem look like "no scholarships found".
        eligibility_score = result.confidence if result.status.value != "likely_ineligible" else 0.0
        score = round(0.50 * eligibility_score + 0.20 * urgency + 0.20 * award + 0.10 * quality, 3)
        ranked.append(RankedScheme(scheme=scheme, result=result, rank_score=score,
                                   score_breakdown={"eligibility_confidence": result.confidence,
                                                    "deadline_urgency": urgency,
                                                    "normalized_award": award,
                                                    "source_quality": quality}))
    return sorted(ranked, key=lambda item: item.rank_score, reverse=True)


def _deadline_urgency(scheme: Scheme, today: date) -> float:
    if not scheme.deadline:
        return 0.2
    days = (scheme.deadline - today).days
    if days < 0:
        return 0.0
    return round(max(0.1, min(1.0, 1 - days / 365)), 3)
