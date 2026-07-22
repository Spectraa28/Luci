"""Memory facade — three pillars behind one small interface.

    procedural  SKILL.md files      how to act
    semantic    facts table (FTS5)  what is durably true
    episodic    episodes table      what happened, when

Plus:
    retrieval_gate   decides IF a turn needs memory
    consolidation    distils chats into facts, every N exchanges
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import anthropic

from luci.config import Settings
from luci.memory import consolidation, retrieval_gate
from luci.memory.episodic.store import SqliteEpisodeStore
from luci.memory.procedural.loader import SkillLoader
from luci.memory.semantic.store import SqliteFactStore

REPO_SKILLS = Path(__file__).resolve().parents[2] / "skills"


class Memory:
    def __init__(self, conn: sqlite3.Connection, settings: Settings, client: anthropic.Anthropic):
        self.conn = conn
        self.settings = settings
        self.client = client
        self.facts = self._make_fact_store(conn, settings)
        self.episodes = SqliteEpisodeStore(conn)
        self.skills = SkillLoader([REPO_SKILLS, settings.home / "skills"])

    @staticmethod
    def _make_fact_store(conn, settings):
        if settings.semantic_store == "supabase":
            from luci.memory.semantic.supabase_store import SupabaseFactStore
            return SupabaseFactStore(settings)
        return SqliteFactStore(conn)

    def gated_retrieve(self, message: str, notify=None) -> str:
        retrieve, query, reason = retrieval_gate.should_retrieve(
            self.client, self.settings.small_model, message
        )
        if notify:
            notify("gate", {"decision": "retrieve" if retrieve else "skip", "reason": reason})
        if not retrieve:
            return ""
        found = self.facts.search(query, self.settings.retrieval_top_k)
        found += self.episodes.search(query, top_k=3)
        return "\n".join(found)

    def matching_skills(self, message: str) -> str:
        matched = self.skills.match(message)
        return "\n\n".join(f"### {s.name}\n{s.body}" for s in matched)

    def log_chat(self, user_message: str, reply: str, session_id: str = "default",
                 source: str = "cli") -> None:
        self.conn.execute(
            "INSERT INTO chat_log (role, content, session_id, source) VALUES ('user', ?, ?, ?)",
            (user_message, session_id, source),
        )
        self.conn.execute(
            "INSERT INTO chat_log (role, content, session_id, source) VALUES ('assistant', ?, ?, ?)",
            (reply, session_id, source),
        )
        self.conn.commit()

    def session_history(self, session_id: str) -> list[tuple[str, str]]:
        rows = self.conn.execute(
            "SELECT role, content FROM chat_log WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        pairs, pending = [], None
        for r in rows:
            if r["role"] == "user":
                pending = r["content"]
            elif pending is not None:
                pairs.append((pending, r["content"]))
                pending = None
        return pairs

    def list_sessions(self) -> list[dict]:
        rows = self.conn.execute(
            """SELECT session_id,
                      COUNT(*) AS messages,
                      MIN(created_at) AS started_at,
                      MAX(created_at) AS last_at
               FROM chat_log GROUP BY session_id ORDER BY last_at DESC"""
        ).fetchall()
        out = []
        for r in rows:
            first = self.conn.execute(
                "SELECT content FROM chat_log WHERE session_id = ? AND role = 'user' ORDER BY id LIMIT 1",
                (r["session_id"],),
            ).fetchone()
            out.append({
                "id": r["session_id"],
                "title": (first["content"][:60] if first else "(empty)"),
                "messages": r["messages"],
                "started_at": r["started_at"],
                "last_at": r["last_at"],
            })
        return out

    def export_markdown(self) -> None:
        """Mirror memory to MEMORY.md — human-readable, always in sync."""
        facts = self.conn.execute(
            "SELECT subject, content FROM facts ORDER BY subject, id"
        ).fetchall()
        eps = self.conn.execute(
            "SELECT happened_at, summary FROM episodes ORDER BY happened_at DESC, id DESC"
        ).fetchall()
        learnings = self.conn.execute(
            "SELECT topic, content, tags, learned_at FROM learnings ORDER BY learned_at DESC LIMIT 50"
        ).fetchall()
        lines = [
            "# Luci memory",
            "",
            "_Human-readable mirror of what Luci remembers. Source of truth is `state.db`._",
            "",
            f"## Facts — semantic memory ({len(facts)})",
            "",
        ]
        lines += [f"- **{f['subject']}** — {f['content']}" for f in facts] or ["_none yet_"]
        lines += ["", f"## Episodes — episodic memory ({len(eps)})", ""]
        lines += [f"- **{e['happened_at']}** — {e['summary']}" for e in eps] or ["_none yet_"]
        lines += ["", f"## Learnings ({len(learnings)})", ""]
        for l in learnings:
            tag_str = f" [{l['tags']}]" if l["tags"] else ""
            lines.append(f"- **{l['topic']}**{tag_str} — {l['content']}")
        if not learnings:
            lines.append("_none yet_")
        (self.settings.home / "MEMORY.md").write_text("\n".join(lines) + "\n")

    def maybe_consolidate(self, notify=None) -> None:
        new_facts = consolidation.consolidate_if_due(
            self.conn,
            self.client,
            self.settings.small_model,
            self.settings.consolidate_every,
            self.facts,
            self.episodes,
        )
        if new_facts and notify:
            notify("consolidation", {"new_facts": new_facts})
