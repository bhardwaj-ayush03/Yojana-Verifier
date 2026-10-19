from datetime import date

import streamlit as st

from src.config import get_settings
from src.chat import answer_scheme_question
from src.discovery import build_discovery_queries, discover_schemes, discover_live_schemes
from src.knowledge import store_evidence
from src.models import StudentProfile
from src.ranking import rank_schemes
from src.tinyfish_client import TinyFishClient
from src.verification import verify_scheme_live


st.set_page_config(page_title="Yojana Verifier", page_icon="🎓", layout="wide")
settings = get_settings()

INDIAN_STATES_AND_UTS = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
]

st.title("🎓 Yojana Verifier")
st.caption("Scholarship guidance grounded in official sources — not official approval.")

with st.sidebar:
    with st.form("student_profile"):
        st.header("Student profile")
        state = st.selectbox("Domicile state / UT", INDIAN_STATES_AND_UTS, index=25)
        category = st.selectbox("Category", ["General", "SC", "ST", "OBC"])
        gender = st.selectbox("Gender", ["Female", "Male", "Other"])
        course_level = st.selectbox("Course level", ["UG", "PG", "Diploma"])
        course_name = st.text_input("Course name", "B.Tech")
        institution_type = st.selectbox("Institution", ["Government", "Private", "Other"])
        marks = st.number_input("Marks percentage", 0.0, 100.0, 75.0)
        income = st.number_input("Annual family income (₹)", 0, 5000000, 250000, step=10000)
        year = st.number_input("Year of study", 1, 10, 1)
        entry_type = st.selectbox("Course entry", ["First year", "Second year through lateral entry", "Continuing student"])
        twelfth_marks = st.number_input("Class 12 marks percentage", 0.0, 100.0, 75.0)
        aicte_approved = st.checkbox("Institution is AICTE-approved", value=True)
        girl_children = st.number_input("Girl children in family", 1, 10, 1)
        other_scholarship = st.checkbox("Already receiving another scholarship")
        minority = st.checkbox("Belong to a minority community")
        disability = st.checkbox("Person with disability")
        first_gen = st.checkbox("First-generation student")
        run = st.form_submit_button("Find scholarships", type="primary", use_container_width=True)

if run:
    profile = StudentProfile(state=state, domicile_state=state, category=category, gender=gender,
                             course_level=course_level, course_name=course_name,
                             institution_type=institution_type, marks_percentage=marks,
                             annual_family_income=income, year_of_study=year,
                             minority_status=minority, disability_status=disability,
                             first_generation_student=first_gen, entry_type=entry_type,
                             twelfth_marks_percentage=twelfth_marks,
                             institution_aicte_approved=aicte_approved,
                             girl_children_in_family=girl_children,
                             receives_other_scholarship=other_scholarship)
    st.session_state.profile = profile
    st.session_state.pop("ranked", None)
    st.session_state.discovery_diagnostics = {}
    with st.spinner("Checking the official scholarship sources…"):
        queries = build_discovery_queries(profile)
        if settings.yojana_mock_mode:
            schemes = discover_schemes(queries[0], mock_mode=True)
        elif not settings.tinyfish_api_key:
            st.error("Set TINYFISH_API_KEY in .env before using live mode.")
            schemes = []
        else:
            client = TinyFishClient(settings.tinyfish_api_key, settings.tinyfish_search_url,
                                    settings.tinyfish_fetch_url, settings.tinyfish_agent_url)
            try:
                schemes = discover_live_schemes(queries, client, settings.effective_llm_key,
                                                settings.effective_llm_model, profile=profile,
                                                diagnostics=st.session_state.discovery_diagnostics)
            except Exception as error:
                st.session_state.discovery_diagnostics["service_error"] = f"{type(error).__name__}: {error}"
                schemes = []
        st.session_state.ranked = rank_schemes(profile, schemes, today=date.today())
        for item in st.session_state.ranked:
            facts = [item.scheme.description, *item.result.evidence]
            facts.extend(f"Required document: {document}" for document in item.scheme.required_documents)
            store_evidence(item.scheme, "\n".join(facts))

ranked = st.session_state.get("ranked")
profile = st.session_state.get("profile")
if ranked is None:
    st.info("Complete the profile and click **Find scholarships** to start a live check.")
elif not ranked:
    st.warning("No relevant scholarship could be confirmed from the fetched sources for this profile. This does not mean you are ineligible.")
elif any(item.result.status.value != "likely_ineligible" for item in ranked):
    st.subheader("Scholarships from official sources")
    st.caption("Application availability and eligibility require confirmation on the linked official page.")
else:
    st.warning("Official scholarships were found, but the extracted eligibility checks do not match this profile. Review them below.")
diagnostics = st.session_state.get("discovery_diagnostics")
if diagnostics and not settings.yojana_mock_mode:
    with st.expander("Search details"):
        st.write(f"Search hits: {diagnostics.get('search_hits', 0)} · Relevant official sources: {diagnostics.get('relevant_official_hits', 0)} · Fetched pages: {diagnostics.get('fetched_with_text', 0)} · Extracted schemes: {diagnostics.get('extracted_schemes', 0)}")
        if diagnostics.get("service_error") or diagnostics.get("extraction_error"):
            st.error(diagnostics.get("service_error") or diagnostics.get("extraction_error"))
visible = [item for item in (ranked or []) if item.result.status.value != "likely_ineligible"]
for item in visible[:3]:
    result = item.result
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"### {item.scheme.name}")
            award = f"₹{item.scheme.award_amount:,}" if item.scheme.award_amount is not None else "Check official notification"
            st.write(f"**Provider:** {item.scheme.provider}  ·  **Award:** {award}")
            st.write(f"**Deadline:** {item.scheme.deadline or 'Current cycle not confirmed'}")
            st.write(item.scheme.description)
        with col2:
            status_label = result.status.value.replace("_", " ").title()
            if result.status.value == "likely_eligible":
                st.success(status_label)
            else:
                st.warning(status_label)
        st.write("**Why:** " + ("; ".join(result.passed_rules) if result.passed_rules else "Needs more information"))
        if result.failed_rules:
            st.error("Failed checks: " + "; ".join(result.failed_rules))
        st.write("**Documents:** " + (", ".join(item.scheme.required_documents) or "Check official notification"))
        st.link_button("Open official source", str(item.scheme.official_url))
        if not settings.yojana_mock_mode and settings.tinyfish_api_key:
            if st.button("Verify on official portal with TinyFish", key=f"verify-{item.scheme.id}"):
                with st.spinner("TinyFish Agent is checking the public portal…"):
                    try:
                        client = TinyFishClient(settings.tinyfish_api_key, settings.tinyfish_search_url,
                                                settings.tinyfish_fetch_url, settings.tinyfish_agent_url)
                        st.session_state[f"verification-{item.scheme.id}"] = verify_scheme_live(profile, item.scheme, client)
                    except Exception as error:
                        st.error(f"TinyFish verification failed: {error}")
            verification = st.session_state.get(f"verification-{item.scheme.id}")
            if verification:
                st.info("TinyFish Agent evidence")
                st.json(verification["result"])

        st.markdown("#### Ask about this scholarship")
        question = st.text_input("Ask a question", placeholder="What documents do I need?", key=f"question-{item.scheme.id}")
        if st.button("Ask", key=f"ask-{item.scheme.id}") and question.strip():
            with st.spinner("Searching stored evidence…"):
                try:
                    client = None
                    if settings.tinyfish_api_key:
                        client = TinyFishClient(settings.tinyfish_api_key, settings.tinyfish_search_url,
                                                settings.tinyfish_fetch_url, settings.tinyfish_agent_url)
                    answer, evidence, refreshed = answer_scheme_question(
                        question, item.scheme, profile, settings.effective_llm_key,
                        settings.effective_llm_model, client if not settings.yojana_mock_mode else None,
                    )
                    st.session_state[f"answer-{item.scheme.id}"] = {
                        "answer": answer, "evidence": evidence, "refreshed": refreshed,
                    }
                except Exception as error:
                    st.error(f"Could not answer that question: {error}")
        saved_answer = st.session_state.get(f"answer-{item.scheme.id}")
        if saved_answer:
            st.info(saved_answer["answer"])
            if saved_answer["refreshed"]:
                st.caption("TinyFish refreshed this answer from the official source.")

excluded = [item for item in (ranked or []) if item.result.status.value == "likely_ineligible"]
if excluded:
    with st.expander(f"Other official schemes with failed checks ({len(excluded)})"):
        for item in excluded:
            st.write(f"{item.scheme.name}: {'; '.join(item.result.failed_rules)}")
            st.link_button("Open official source", str(item.scheme.official_url), key=f"excluded-{item.scheme.id}")

st.divider()
st.caption(f"Mode: {'MOCK / curated seed data' if settings.yojana_mock_mode else 'LIVE adapters enabled'} · Results are guidance, not a guarantee of approval.")
