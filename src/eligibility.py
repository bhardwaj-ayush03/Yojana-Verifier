from src.models import EligibilityResult, EligibilityStatus, Scheme, StudentProfile


def evaluate_scheme(profile: StudentProfile, scheme: Scheme) -> EligibilityResult:
    passed, failed, unknown, evidence = [], [], [], []
    for rule in scheme.eligibility_rules:
        actual = getattr(profile, rule.field, None)
        label = f"{rule.field} {rule.operator} {rule.value}"
        if actual is None:
            unknown.append(label)
            continue
        try:
            ok = _matches(actual, rule.operator, rule.value, field=rule.field)
        except (TypeError, ValueError):
            unknown.append(label)
            continue
        (passed if ok else failed).append(label)
        evidence.append(rule.source_text)
    total = len(passed) + len(failed) + len(unknown)
    confidence = round(len(passed) / total, 2) if total else 0.0
    if failed:
        status = EligibilityStatus.LIKELY_INELIGIBLE
    elif unknown or not passed or scheme.id.startswith("live-"):
        status = EligibilityStatus.NEEDS_VERIFICATION
    else:
        status = EligibilityStatus.LIKELY_ELIGIBLE
    return EligibilityResult(scheme_id=scheme.id, status=status, confidence=confidence,
                             passed_rules=passed, failed_rules=failed,
                             unknown_rules=unknown, evidence=evidence)


_CATEGORY_ALIASES = {
    "scheduled tribe": "st", "scheduled tribes": "st", "s t": "st",
    "scheduled caste": "sc", "scheduled castes": "sc", "s c": "sc",
    "other backward class": "obc", "other backward classes": "obc", "o b c": "obc",
}
_POST_SECONDARY = {"post matric", "post matriculation", "post secondary", "post secondary education"}


def _matches(actual: object, operator: str, expected: object, *, field: str = "") -> bool:
    def normalize(value: object) -> str:
        text = str(value).strip().casefold().replace("-", " ")
        if field == "category":
            return _CATEGORY_ALIASES.get(text, text)
        return text

    if operator == "lte":
        return float(actual) <= float(expected)
    if operator == "gte":
        return float(actual) >= float(expected)
    if operator == "eq":
        return normalize(actual) == normalize(expected)
    if operator == "in":
        if field == "course_level" and normalize(actual) in {"ug", "pg", "diploma"}:
            if any(normalize(item) in _POST_SECONDARY for item in expected):
                return True
        return normalize(actual) in {normalize(item) for item in expected}  # type: ignore[union-attr]
    if operator == "contains":
        return str(expected).lower() in str(actual).lower()
    return False
