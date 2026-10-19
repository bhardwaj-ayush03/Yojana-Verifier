import json
import hashlib
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from src.models import EligibilityRule, Scheme, StudentProfile
from src.tinyfish_client import TinyFishClient


def load_seed_schemes(path: str | Path = "data/seed_sources.json") -> list[Scheme]:
    entries = json.loads(Path(path).read_text())
    return [_demo_scheme(entry) for entry in entries]


def discover_schemes(query: str, *, mock_mode: bool = True) -> list[Scheme]:
    """Return the curated official seed set in mock mode.

    Live TinyFish discovery is intentionally wired separately so the demo remains reliable.
    """
    if mock_mode:
        return load_seed_schemes()
    raise ValueError("Use discover_live_schemes() with TinyFish credentials for live discovery")


def build_discovery_queries(profile: StudentProfile) -> list[str]:
    level = {"UG": "undergraduate", "PG": "postgraduate"}.get(profile.course_level, profile.course_level)
    return [
        f"{profile.domicile_state} {profile.category} {level} post matric scholarship official",
        f"site:scholarships.gov.in/public/schemeGuidelines {profile.category} {level} scholarship",
        f"site:myscheme.gov.in/schemes {profile.domicile_state} {profile.category} scholarship",
        f'"{profile.course_name}" {profile.domicile_state} scholarship official',
    ]


def discover_live_schemes(query: str | list[str], client: TinyFishClient, groq_api_key: str | None = None,
                          groq_model: str = "openai/gpt-oss-120b", profile: StudentProfile | None = None,
                          diagnostics: dict | None = None) -> list[Scheme]:
    """Search live official sources with TinyFish, fetch content, and normalize rules."""
    from src.extraction import extract_scheme

    queries = [query] if isinstance(query, str) else query
    if not queries:
        return []
    with ThreadPoolExecutor(max_workers=min(3, len(queries))) as executor:
        search_payloads = list(executor.map(client.search, queries))
    candidates = [candidate for payload in search_payloads if isinstance(payload, dict)
                  for candidate in (payload.get("results") or []) if isinstance(candidate, dict)]
    if diagnostics is not None:
        diagnostics["search_hits"] = len(candidates)
    trusted, seen = [], set()
    for candidate in candidates:
        url = candidate.get("url", "")
        if isinstance(url, str) and _is_trusted_url(url) and _is_relevant_candidate(candidate, profile) and url not in seen:
            trusted.append(candidate)
            seen.add(url)
    if diagnostics is not None:
        diagnostics["relevant_official_hits"] = len(trusted)
    if not trusted:
        return []
    trusted.sort(key=lambda item: _source_priority(item, profile), reverse=True)
    trusted = trusted[:8]
    fetched = client.fetch([candidate["url"] for candidate in trusted])
    fetch_results = fetched.get("results", []) if isinstance(fetched, dict) else []
    fetched_by_url = {content.get("url"): content for content in (fetch_results or [])
                      if isinstance(content, dict) and isinstance(content.get("url"), str)}
    jobs = [(candidate, fetched_by_url[candidate["url"]]) for candidate in trusted
            if candidate["url"] in fetched_by_url and len(_content_text(fetched_by_url[candidate["url"]])) >= 500]
    if diagnostics is not None:
        diagnostics["fetched_with_text"] = len(jobs)
    if not groq_api_key:
        if diagnostics is not None:
            diagnostics["extraction_error"] = "GROQ_API_KEY is required to extract scholarship details."
        return []
    from src.knowledge import store_evidence
    # A portal shell may contain only a footer; spending Groq tokens on it
    # crowds out the actual scheme PDF under the provider's token quota.
    jobs = jobs[:2]
    with ThreadPoolExecutor(max_workers=min(2, len(jobs) or 1)) as executor:
        extracted = list(executor.map(lambda job: _extract_candidate(job, extract_scheme, groq_api_key, groq_model), jobs))
    schemes = []
    for (candidate, content), scheme in zip(jobs, extracted, strict=True):
        if isinstance(scheme, Exception):
            if diagnostics is not None:
                diagnostics["extraction_error"] = f"Extraction service returned {type(scheme).__name__}; retry the search later."
            continue
        if scheme and _has_usable_details(scheme) and _is_relevant_scheme(scheme, candidate, profile):
            schemes.append(scheme)
            store_evidence(scheme, _content_text(content))
    if diagnostics is not None:
        diagnostics["extracted_schemes"] = len(schemes)
    return schemes


def _extract_candidate(job: tuple[dict, dict], extractor, groq_api_key: str | None, groq_model: str) -> Scheme | Exception:
    candidate, content = job
    base = _candidate_scheme(candidate)
    try:
        return extractor(_content_text(content), base, groq_api_key, groq_model)
    except Exception as error:
        return error


def _content_text(content: object) -> str:
    """Return usable fetched text without trusting the provider's nullable payload."""
    if not isinstance(content, dict):
        return ""
    text = content.get("text")
    return text.strip() if isinstance(text, str) else ""


def _has_usable_details(scheme: Scheme) -> bool:
    return bool(scheme.eligibility_rules or scheme.required_documents or scheme.award_amount or scheme.deadline)


def _is_trusted_url(url: str) -> bool:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (hostname.endswith(".gov.in") or hostname.endswith(".nic.in"))


def _source_priority(candidate: dict, profile: StudentProfile | None = None) -> int:
    url = str(candidate.get("url") or "").lower()
    title = str(candidate.get("title") or "").lower()
    score = 0
    if "scholarship" in title or "scheme" in title:
        score += 3
    if profile and profile.category.lower() in re.findall(r"\b(?:sc|st|obc|general)\b", title):
        score += 3
    if profile and profile.domicile_state.lower() in title:
        score += 3
    if "schemeguidelines" in url:
        score += 8
    elif "myscheme.gov.in/schemes/" in url or "india.gov.in/services/" in url:
        score -= 3  # These portals currently return only navigation/footer text from Fetch.
    return score


_INDIAN_STATES = {
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh", "goa", "gujarat",
    "haryana", "himachal pradesh", "jharkhand", "karnataka", "kerala", "madhya pradesh",
    "maharashtra", "manipur", "meghalaya", "mizoram", "nagaland", "odisha", "punjab",
    "rajasthan", "sikkim", "tamil nadu", "telangana", "tripura", "uttar pradesh", "uttarakhand",
    "west bengal", "delhi", "jammu and kashmir", "ladakh", "puducherry",
}


def _is_relevant_candidate(candidate: dict, profile: StudentProfile | None) -> bool:
    from urllib.parse import urlparse

    url = str(candidate.get("url") or "")
    host = (urlparse(url).hostname or "").lower()
    path = urlparse(url).path.lower()
    title = str(candidate.get("title") or "").lower()
    snippet = str(candidate.get("snippet") or "").lower()
    if not re.search(r"\b(scholarships?|fellowships?|students? scheme|post.matric)\b", f"{title} {snippet} {path}"):
        return False
    if any(term in title for term in ("approval process", "handbook", "tender", "annual report", "faq")):
        return False
    if len(url) > 500 or (profile and profile.course_level in {"UG", "PG", "Diploma"}
                          and re.search(r"\bpre.matric\b", f"{title} {path}")):
        return False
    if profile and profile.course_level == "UG" and re.search(r"\b(post.graduate|postgraduate)\b", title):
        return False
    if path.rstrip("/") in {"", "/students", "/all-scholarships", "/schemes"}:
        return False
    if profile is None:
        return True
    north_east = {"arunachal pradesh", "assam", "manipur", "meghalaya", "mizoram", "nagaland", "sikkim", "tripura"}
    if profile.domicile_state.lower() not in north_east and re.search(r"\b(nec|north.east(?:ern)?)\b", title):
        return False
    categories = set(re.findall(r"\b(?:sc|st|obc)\b", title))
    if categories and profile.category.lower() not in categories:
        return False
    state = profile.domicile_state.lower()
    context = f"{host} {path} {title}".replace("-", " ").replace("_", " ")
    if any(other != state and re.search(rf"\b{re.escape(other)}\b", context)
           for other in _INDIAN_STATES):
        return False
    if host.endswith("scholarships.gov.in") or host.endswith("myscheme.gov.in"):
        return True
    if state not in context and state.replace(" ", "") not in host:
        return False
    return True


def _is_relevant_scheme(scheme: Scheme, candidate: dict, profile: StudentProfile | None) -> bool:
    if profile is None:
        return True
    if not _is_relevant_candidate({**candidate, "title": scheme.name}, profile):
        return False
    categories = set(re.findall(r"\b(?:sc|st|obc)\b", scheme.name.lower()))
    return not categories or profile.category.lower() in categories


def _candidate_scheme(candidate: dict) -> Scheme:
    from urllib.parse import urlparse
    url = candidate["url"]
    host = urlparse(url).hostname or "official source"
    return Scheme(id="live-" + hashlib.sha256(url.encode()).hexdigest()[:16],
                  name=candidate.get("title") or "Official scholarship opportunity",
                  official_url=url, source_urls=[url], provider=host, academic_year="Unconfirmed",
                  deadline=None,
                  description="Official source fetched; current application cycle requires verification.",
                  last_checked_at=datetime.now(timezone.utc))


def _demo_scheme(entry: dict) -> Scheme:
    url = entry["official_url"]
    common = [{"field": "annual_family_income", "operator": "lte", "value": 800000,
               "source_text": "Family income must be within the scheme's notified limit.", "source_url": url}]
    if entry["id"] == "post-matric-sc-scholarship":
        common += [{"field": "category", "operator": "eq", "value": "SC",
                    "source_text": "The scheme is for SC students.", "source_url": url}]
    if entry["id"] == "minority-post-matric":
        common += [{"field": "minority_status", "operator": "eq", "value": True,
                    "source_text": "The scheme is for students belonging to minority communities.", "source_url": url}]
    common += [{"field": "course_level", "operator": "in", "value": ["UG", "PG", "Diploma"],
                "source_text": "Post-secondary courses are covered by the scheme.", "source_url": url}]
    return Scheme(**entry, eligibility_rules=[EligibilityRule(**rule) for rule in common],
                  required_documents=["income_certificate", "marksheet", "bank_account_proof"],
                  last_checked_at=datetime.now(timezone.utc),
                  description="Seeded from the official National Scholarship Portal; confirm the live notification before applying.")
