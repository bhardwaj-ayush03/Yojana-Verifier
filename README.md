# Yojana Verifier

Yojana Verifier helps Indian students discover scholarships relevant to their profile and inspect the official evidence behind an eligibility assessment. A student enters their domicile, category, course, income, marks, and other details; the app searches official sources, extracts scheme information, checks rules against the profile, and links back to the source. It is a decision-support demo, not a scholarship application portal or an approval decision.

## What the app does

- Builds search queries from the submitted student profile. Nothing is fetched until **Find scholarships** is clicked.
- Uses **TinyFish Search** to discover sources and **TinyFish Fetch** to retrieve readable official pages or guideline PDFs. Results from unrelated states, generic portal pages, handbooks, and irrelevant courses are filtered out.
- Uses **Groq** to turn fetched text into structured scheme fields and eligibility rules. Rules need a supporting quote from the fetched source; missing details remain unknown.
- Evaluates the extracted rules against the profile with deterministic Python code. Expired deadlines are excluded. Live candidates with incomplete information show **Needs verification**, and failed checks are listed separately.
- Provides an **Open official source** link, a per-scheme evidence-based question box, and an optional **Verify on official portal with TinyFish** action. The verification agent is instructed not to log in, enter personal data, bypass CAPTCHA, or submit an application.
- Shows search counts and service errors in **Search details** so an empty result is distinguishable from a provider or extraction failure.

## How it works

```text
Student profile + Find scholarships
    → profile-derived TinyFish Search queries
    → official-source and relevance filtering
    → TinyFish Fetch of selected pages/PDFs
    → Groq extraction with source quotes
    → deterministic eligibility checks and ranking
    → scheme cards, source links, and optional verification/chat
```

The interface is built with Streamlit. Pydantic validates profiles, schemes, and extracted rules. Fetched evidence is stored locally in SQLite with FTS5 for scholarship-specific questions. TinyFish handles live web retrieval and optional portal verification; Groq handles structured extraction and evidence-grounded answers.

## Run locally

Requirements: Python 3.11 or newer and `uv`. Live mode also requires working TinyFish and Groq API keys.

```bash
cp .env.example .env
uv sync
uv run streamlit run app.py
```

Open the local URL printed by Streamlit. Edit `.env` to choose a mode:

```dotenv
TINYFISH_API_KEY=your_tinyfish_key
GROQ_API_KEY=your_groq_key
YOJANA_MOCK_MODE=false
```

The other endpoint and model settings are documented in `.env.example`. Do not commit `.env` or share real keys in screenshots. If you edit `.env` while the server is running, restart Streamlit.

### Demo modes

| Mode | Setting | Behavior |
| --- | --- | --- |
| Live | `YOJANA_MOCK_MODE=false` | Searches and fetches official sources with TinyFish, then extracts details with Groq. Requires both keys and network access. |
| Mock | `YOJANA_MOCK_MODE=true` | Uses the local illustrative entries in `data/seed_sources.json`. No live discovery occurs; seeded dates and amounts must not be presented as current facts. |

Live mode is the default. The example `.env.example` also starts in live mode; missing keys produce a visible configuration error, not sample results. Set `YOJANA_MOCK_MODE=true` only when you intentionally want the fixed, offline demo data.

For Streamlit Community Cloud, put `TINYFISH_API_KEY`, `GROQ_API_KEY`, and `YOJANA_MOCK_MODE = false` at the root of **App settings → Secrets** (not under a TOML section). Save and restart the app. Check that the footer says **LIVE adapters enabled** before showing the judges; **MOCK / curated seed data** means no TinyFish call was made. Do not commit keys to GitHub.

## Suggested demo

1. Set live mode and start the app. Select a domicile, category, course level, and course name in the sidebar.
2. Click **Find scholarships**. Show the source link and expand **Search details** to explain how many search hits became readable, relevant schemes.
3. Explain **Needs verification** when the official document does not state a current application deadline or enough eligibility conditions. Open the linked source to confirm the current cycle.
4. Ask a scheme-specific question, such as “What documents are required?” Optionally use **Verify on official portal with TinyFish** to request an additional public-page check.

Live results change as official pages, search indexes, and provider quotas change. A blank result is not proof that a student is ineligible; inspect **Search details** for missing source text, extraction errors, or rate limits. The app never submits an application.

## Project structure

| Path | Purpose |
| --- | --- |
| `app.py` | Streamlit profile form, results, search diagnostics, chat, and verification controls |
| `src/discovery.py` | Profile queries, source filtering, fetching, and candidate extraction |
| `src/tinyfish_client.py` | TinyFish Search, Fetch, and Agent HTTP adapters |
| `src/extraction.py` | Groq extraction and validation of source-backed rules |
| `src/eligibility.py`, `src/ranking.py` | Deterministic profile checks, expiry exclusion, and result ordering |
| `src/knowledge.py`, `src/chat.py` | Local evidence store and evidence-grounded Q&A |
| `src/verification.py` | Constrained public-page verification request |
| `tests/` | Unit and pipeline regression tests |

## Tests and limitations

Run the automated checks with:

```bash
uv run pytest -q
uv run python -m compileall -q app.py src tests
```

The tests cover source filtering, Fetch result pairing, rule extraction safeguards, eligibility comparisons, ranking, and evidence storage. Live searches were also exercised with Bihar ST undergraduate and Kerala OBC postgraduate profiles; both produced relevant official scheme guidelines, with application-cycle verification still required.

This is a prototype. Search coverage is bounded, some official portals return only navigation text to Fetch, and Groq/TinyFish can fail or rate-limit a request. A guideline may describe a scheme without confirming that applications are open today. Missing deadlines, awards, or documents are shown as unconfirmed rather than filled with guesses. Always confirm the latest notification and eligibility on the linked official portal before applying.
