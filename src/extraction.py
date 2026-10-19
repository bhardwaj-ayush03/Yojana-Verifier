import json
import re

from src.models import EligibilityRule, Scheme, StudentProfile


FIELD_ALIASES = {
    "income": "annual_family_income", "family_income": "annual_family_income",
    "annual_income": "annual_family_income", "domicile": "domicile_state",
    "state": "domicile_state", "marks": "marks_percentage",
    "class_12_marks": "twelfth_marks_percentage", "aicte_approved": "institution_aicte_approved",
    "other_scholarship": "receives_other_scholarship", "girl_children": "girl_children_in_family",
}
ALLOWED_FIELDS = set(StudentProfile.model_fields)
ALLOWED_OPERATORS = {"eq", "lte", "gte", "in", "contains"}


def extract_scheme(text: str, base: Scheme, groq_api_key: str | None = None, model: str = "openai/gpt-oss-120b") -> Scheme:
    if not groq_api_key:
        return base
    from groq import Groq
    client = Groq(api_key=groq_api_key)
    allowed = ", ".join(sorted(ALLOWED_FIELDS))
    prompt = f"""Extract only one specific scholarship described by this source as a JSON object with name, provider, academic_year, award_amount, deadline,
required_documents and eligibility_rules.
If the page is a general portal, handbook, or list of multiple schemes, return null fields and no rules. Do not combine details from different schemes.
Use null when award_amount or deadline is not explicitly present. A published guideline date is not an application deadline.
Every eligibility rule must be an object with exactly these useful fields: field, operator, value, source_text, source_url.
Allowed field values are only: {allowed}.
Allowed operators are only: eq, lte, gte, in, contains.
Only emit a rule when its exact supporting sentence is copied from the supplied source. Use deadline format YYYY-MM-DD.
Never invent a threshold and never return prose outside the JSON object."""
    messages = [{"role": "system", "content": prompt},
                {"role": "user", "content": f"Official source URL: {base.official_url}\n\n{text[:6000]}"}]
    try:
        response = client.chat.completions.create(model=model, temperature=0,
                                                  response_format={"type": "json_object"}, messages=messages)
    except Exception as error:
        if getattr(error, "status_code", None) != 400 or "json_validate_failed" not in str(error):
            raise
        response = client.chat.completions.create(model=model, temperature=0, messages=messages)
    raw = response.choices[0].message.content or ""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        payload = json.loads(raw[start:end + 1]) if start >= 0 and end > start else {}
    if not isinstance(payload, dict):
        return base
    payload = {key: value for key, value in payload.items() if key in {
        "name", "provider", "academic_year", "award_amount", "deadline", "required_documents", "eligibility_rules"}}
    payload["eligibility_rules"] = _validated_rules(payload.get("eligibility_rules", []), base, text)
    payload["required_documents"] = _string_list(payload.get("required_documents"))
    payload["award_amount"] = _integer_or_none(payload.get("award_amount"))
    deadline = payload.get("deadline")
    if deadline and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(deadline)):
        payload["deadline"] = None
    merged = base.model_dump(mode="json")
    for field in ("name", "provider", "academic_year"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            payload.pop(field, None)
    merged.update(payload)
    return Scheme.model_validate(merged)


def _string_list(value: object) -> list[str]:
    """Normalize nullable or loosely formatted model output into a safe list."""
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _validated_rules(raw_rules: object, base: Scheme, text: str = "") -> list[EligibilityRule]:
    rules = []
    if not isinstance(raw_rules, list):
        return rules
    for raw in raw_rules:
        if not isinstance(raw, dict):
            continue
        field = FIELD_ALIASES.get(str(raw.get("field", "")).lower(), str(raw.get("field", "")))
        operator = str(raw.get("operator", "")).lower()
        source_text = raw.get("source_text")
        if not isinstance(source_text, str):
            continue
        source_text = source_text.strip()
        if (field not in ALLOWED_FIELDS or operator not in ALLOWED_OPERATORS or not source_text
                or (text and _normalized(source_text) not in _normalized(text))):
            continue
        value = raw.get("value")
        if operator == "in" and (not isinstance(value, list) or not value or
                                 not all(isinstance(item, str) for item in value)):
            continue
        if operator in {"lte", "gte"} and (isinstance(value, bool) or not isinstance(value, (int, float))):
            continue
        # A model can invert an exclusion ("correspondence courses are not
        # eligible") into a positive equality. Leave such text for manual
        # verification rather than using it to fail a profile.
        if re.search(r"\b(not|no|except|excluded|ineligible|other than|shall not)\b", source_text, re.I):
            continue
        try:
            rules.append(EligibilityRule(field=field, operator=operator, value=value,
                                         source_text=source_text, source_url=base.official_url))
        except Exception:
            continue
    return rules


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _integer_or_none(value: object) -> int | None:
    if value is None:
        return None
    digits = re.sub(r"[^0-9]", "", str(value))
    return int(digits) if digits else None
