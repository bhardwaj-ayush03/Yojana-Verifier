from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class EligibilityStatus(StrEnum):
    LIKELY_ELIGIBLE = "likely_eligible"
    NEEDS_VERIFICATION = "needs_verification"
    LIKELY_INELIGIBLE = "likely_ineligible"


class StudentProfile(BaseModel):
    state: str
    domicile_state: str
    category: str
    gender: str
    course_level: str
    course_name: str
    institution_type: str
    marks_percentage: float = Field(ge=0, le=100)
    annual_family_income: int = Field(ge=0)
    disability_status: bool = False
    minority_status: bool = False
    first_generation_student: bool = False
    year_of_study: int = Field(ge=1, le=10)
    entry_type: str = "First year"
    twelfth_marks_percentage: float | None = Field(default=None, ge=0, le=100)
    institution_aicte_approved: bool | None = None
    girl_children_in_family: int | None = Field(default=None, ge=1, le=10)
    receives_other_scholarship: bool = False


class EligibilityRule(BaseModel):
    field: str
    operator: str
    value: str | int | float | bool | list[str]
    source_text: str
    source_url: HttpUrl


class Scheme(BaseModel):
    id: str
    name: str
    official_url: HttpUrl
    source_urls: list[HttpUrl] = []
    provider: str
    academic_year: str
    award_amount: int | None = None
    deadline: date | None = None
    eligibility_rules: list[EligibilityRule] = []
    required_documents: list[str] = []
    last_checked_at: datetime | None = None
    source_hash: str | None = None
    description: str = ""

    def is_expired(self, as_of: date | None = None) -> bool:
        return bool(self.deadline and self.deadline < (as_of or date.today()))


class EligibilityResult(BaseModel):
    scheme_id: str
    status: EligibilityStatus
    confidence: float = Field(ge=0, le=1)
    passed_rules: list[str] = []
    failed_rules: list[str] = []
    unknown_rules: list[str] = []
    evidence: list[str] = []


class RankedScheme(BaseModel):
    scheme: Scheme
    result: EligibilityResult
    rank_score: float
    score_breakdown: dict[str, float]
