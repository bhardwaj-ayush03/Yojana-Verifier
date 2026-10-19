"""Persistent local evidence retrieval for scholarship conversations."""

import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src.models import Scheme

DB_PATH = Path("data/cache/knowledge.db")


def _connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("""CREATE TABLE IF NOT EXISTS evidence (
        id INTEGER PRIMARY KEY, scheme_id TEXT NOT NULL, title TEXT NOT NULL,
        text TEXT NOT NULL, source_url TEXT NOT NULL, retrieved_at TEXT NOT NULL,
        content_hash TEXT NOT NULL UNIQUE
    )""")
    connection.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts USING fts5(
        title, text, content='evidence', content_rowid='id'
    )""")
    connection.commit()
    return connection


def store_evidence(scheme: Scheme, text: str, retrieved_at: datetime | None = None) -> None:
    if not text.strip():
        return
    timestamp = (retrieved_at or datetime.now(timezone.utc)).isoformat()
    # The same portal text can support different schemes; keep each scheme's
    # evidence separate so chat and freshness checks do not silently miss it.
    digest = hashlib.sha256(f"{scheme.id}\0{scheme.official_url}\0{text}".encode()).hexdigest()
    with _connect() as connection:
        if connection.execute("SELECT id FROM evidence WHERE content_hash = ?", (digest,)).fetchone():
            return
        cursor = connection.execute(
            "INSERT INTO evidence (scheme_id, title, text, source_url, retrieved_at, content_hash) VALUES (?, ?, ?, ?, ?, ?)",
            (scheme.id, scheme.name, text, str(scheme.official_url), timestamp, digest),
        )
        connection.execute("INSERT INTO evidence_fts(rowid, title, text) VALUES (?, ?, ?)",
                           (cursor.lastrowid, scheme.name, text))
        connection.commit()


def search_evidence(scheme_id: str, question: str, limit: int = 5) -> list[dict]:
    terms = re.findall(r"[A-Za-z0-9]{3,}", question.lower())
    query = " OR ".join(f'"{term}"' for term in terms[:12]) or '"scholarship"'
    with _connect() as connection:
        rows = connection.execute(
            """SELECT e.title, e.text, e.source_url, e.retrieved_at
               FROM evidence_fts f JOIN evidence e ON e.id = f.rowid
               WHERE e.scheme_id = ? AND evidence_fts MATCH ?
               ORDER BY bm25(evidence_fts) LIMIT ?""",
            (scheme_id, query, limit),
        ).fetchall()
    return [{"title": r[0], "text": r[1], "source_url": r[2], "retrieved_at": r[3]} for r in rows]


def latest_evidence_time(scheme_id: str) -> datetime | None:
    with _connect() as connection:
        row = connection.execute("SELECT MAX(retrieved_at) FROM evidence WHERE scheme_id = ?", (scheme_id,)).fetchone()
    return datetime.fromisoformat(row[0]) if row and row[0] else None
