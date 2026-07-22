"""One SQLite file (state.db) holds everything luci remembers and does.

Open it yourself anytime:  sqlite3 .luci/state.db '.tables'
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
-- Calendar
CREATE TABLE IF NOT EXISTS calendar_events (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    start TEXT NOT NULL,
    "end" TEXT,
    attendees TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

-- Semantic memory: durable facts
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY,
    subject TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT 'user',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    subject, content, content=facts, content_rowid=id
);
CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, subject, content) VALUES (new.id, new.subject, new.content);
END;
CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, subject, content) VALUES ('delete', old.id, old.subject, old.content);
END;
CREATE TRIGGER IF NOT EXISTS facts_au AFTER UPDATE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, subject, content) VALUES ('delete', old.id, old.subject, old.content);
    INSERT INTO facts_fts(rowid, subject, content) VALUES (new.id, new.subject, new.content);
END;

-- Episodic memory: dated events
CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY,
    happened_at TEXT NOT NULL,
    summary TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(
    summary, content=episodes, content_rowid=id
);
CREATE TRIGGER IF NOT EXISTS episodes_ai AFTER INSERT ON episodes BEGIN
    INSERT INTO episodes_fts(rowid, summary) VALUES (new.id, new.summary);
END;
CREATE TRIGGER IF NOT EXISTS episodes_ad AFTER DELETE ON episodes BEGIN
    INSERT INTO episodes_fts(episodes_fts, rowid, summary) VALUES ('delete', old.id, old.summary);
END;

-- Raw chat log
CREATE TABLE IF NOT EXISTS chat_log (
    id INTEGER PRIMARY KEY,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    consolidated INTEGER DEFAULT 0,
    session_id TEXT DEFAULT 'default',
    source TEXT DEFAULT 'cli',
    created_at TEXT DEFAULT (datetime('now'))
);

-- ── luci-specific tables ──────────────────────────────────────────────────────

-- Learning journal: concepts, papers, bug fixes, anything worth keeping
CREATE TABLE IF NOT EXISTS learnings (
    id INTEGER PRIMARY KEY,
    topic TEXT NOT NULL,           -- e.g. 'RAG', 'attention mechanism'
    content TEXT NOT NULL,         -- what was learned
    tags TEXT DEFAULT '',          -- comma-separated, e.g. 'ml,nlp,paper'
    source TEXT DEFAULT '',        -- optional: paper title, URL, book name
    learned_at TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE VIRTUAL TABLE IF NOT EXISTS learnings_fts USING fts5(
    topic, content, tags, content=learnings, content_rowid=id
);
CREATE TRIGGER IF NOT EXISTS learnings_ai AFTER INSERT ON learnings BEGIN
    INSERT INTO learnings_fts(rowid, topic, content, tags) VALUES (new.id, new.topic, new.content, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS learnings_ad AFTER DELETE ON learnings BEGIN
    INSERT INTO learnings_fts(learnings_fts, rowid, topic, content, tags) VALUES ('delete', old.id, old.topic, old.content, old.tags);
END;
CREATE TRIGGER IF NOT EXISTS learnings_au AFTER UPDATE ON learnings BEGIN
    INSERT INTO learnings_fts(learnings_fts, rowid, topic, content, tags) VALUES ('delete', old.id, old.topic, old.content, old.tags);
    INSERT INTO learnings_fts(rowid, topic, content, tags) VALUES (new.id, new.topic, new.content, new.tags);
END;

-- Job application tracker
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY,
    company TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT DEFAULT 'applied',     -- applied | interviewing | offer | rejected | closed
    notes TEXT DEFAULT '',
    applied_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- Outreach drafts log (company, message drafted, context used)
CREATE TABLE IF NOT EXISTS outreach_drafts (
    id INTEGER PRIMARY KEY,
    company TEXT NOT NULL,
    contact TEXT DEFAULT '',
    draft TEXT NOT NULL,
    context TEXT DEFAULT '',           -- what memory facts were used
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive, idempotent column upgrades."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(chat_log)").fetchall()}
    if "session_id" not in cols:
        conn.execute("ALTER TABLE chat_log ADD COLUMN session_id TEXT DEFAULT 'default'")
        conn.commit()
    if "source" not in cols:
        conn.execute("ALTER TABLE chat_log ADD COLUMN source TEXT DEFAULT 'cli'")
        conn.commit()


def connect(home: Path, check_same_thread: bool = True) -> sqlite3.Connection:
    conn = sqlite3.connect(home / "state.db", check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=3000")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn
