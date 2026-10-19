from datetime import datetime, timezone

from src.knowledge import search_evidence, store_evidence
from src.models import Scheme, StudentProfile
from src.tinyfish_client import TinyFishClient


def answer_scheme_question(question: str, scheme: Scheme, profile: StudentProfile,
                           groq_api_key: str | None, groq_model: str,
                           tinyfish: TinyFishClient | None = None) -> tuple[str, list[dict], bool]:
    evidence = search_evidence(scheme.id, question)
    freshness_sensitive = any(word in question.lower() for word in ("current", "today", "deadline", "open", "close", "latest"))
    refreshed = False
    if tinyfish and (not evidence or freshness_sensitive):
        fetched = tinyfish.fetch([str(scheme.official_url)])
        results = fetched.get("results", [])
        if results and isinstance(results[0], dict) and isinstance(results[0].get("text"), str) and results[0]["text"].strip():
            store_evidence(scheme, results[0]["text"])
            fresh_evidence = [{
                "title": scheme.name, "text": results[0]["text"],
                "source_url": str(scheme.official_url),
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }]
            evidence = fresh_evidence if freshness_sensitive else search_evidence(scheme.id, question) or fresh_evidence
            refreshed = True
    if not evidence:
        return "I could not find supporting evidence for that question yet. I need to re-check the official portal.", [], refreshed
    context = "\n\n".join(f"SOURCE: {item['source_url']}\n{item['text'][:6000]}" for item in evidence)
    if not groq_api_key:
        return f"I found supporting information in the official source:\n\n{context[:3000]}", evidence, refreshed
    from groq import Groq
    response = Groq(api_key=groq_api_key).chat.completions.create(
        model=groq_model, temperature=0, max_tokens=700,
        messages=[
            {"role": "system", "content": "Answer only from the supplied evidence. If it does not answer the question, say that clearly. Include the official source URL and a short evidence quote. Do not claim approval."},
            {"role": "user", "content": f"Scholarship: {scheme.name}\nStudent profile: {profile.model_dump_json()}\nQuestion: {question}\nEvidence:\n{context}"},
        ],
    )
    return response.choices[0].message.content, evidence, refreshed
