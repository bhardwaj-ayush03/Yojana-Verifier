from src.extraction import _string_list, _validated_rules
from src.models import Scheme


def test_string_list_handles_nullable_model_output() -> None:
    assert _string_list(None) == []
    assert _string_list("income certificate") == []
    assert _string_list([" income certificate ", None, 42, ""]) == ["income certificate"]


def test_rules_require_source_quote_and_skip_negated_exclusions():
    base = Scheme(id="live-1", name="ST Scholarship", official_url="https://scholarships.gov.in/st",
                  provider="NSP", academic_year="Unconfirmed")
    rules = [
        {"field": "category", "operator": "eq", "value": "Scheduled Tribe",
         "source_text": "The scholarship is for Scheduled Tribe students."},
        {"field": "entry_type", "operator": "eq", "value": "correspondence",
         "source_text": "Correspondence courses are not eligible."},
        {"field": "annual_family_income", "operator": "lte", "value": 250000,
         "source_text": "Families must earn below 250000."},
    ]
    text = "The scholarship is for Scheduled Tribe students. Correspondence courses are not eligible."
    validated = _validated_rules(rules, base, text)
    assert [rule.field for rule in validated] == ["category"]
