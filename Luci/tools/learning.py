"""log_learning / search_learnings — Luci's learning journal.

log_learning: store what the user learned today (concept, paper, bug fix,
              anything worth keeping). Writes to the learnings table with FTS5.

search_learnings: surface the user's own notes. This is the "second brain"
                  retrieval moment — BM25 keyword search, same SQLite FTS5
                  pattern as facts.
"""

from __future__ import annotations

import sqlite3

from Luci.tools.registry import Tool


def make_log_tool(conn: sqlite3.Connection) -> Tool:
    def log_learning(topic: str, content: str, tags: str = "", source: str = "") -> str:
        if not topic or not content:
            return "log_learning needs at least a topic and content."
        conn.execute(
            "INSERT INTO learnings (topic, content, tags, source) VALUES (?, ?, ?, ?)",
            (topic.lower().strip(), content.strip(), tags.lower().strip(), source.strip()),
        )
        conn.commit()
        tag_str = f" [tags: {tags}]" if tags else ""
        src_str = f" (from: {source})" if source else ""
        return f"Logged under '{topic}'{tag_str}{src_str}: {content}"

    return Tool(
        name="log_learning",
        description=(
            "Log something the user learned — a concept, a paper, a bug fix, a technique. "
            "Use whenever the user says 'I learned', 'I read', 'I figured out', 'note that', "
            "or teaches you something worth keeping in their second brain. "
            "topic: short label (e.g. 'RAG reranking', 'attention'). "
            "tags: comma-separated keywords (e.g. 'ml,nlp,paper'). "
            "source: optional origin (paper title, URL, book, course)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Short topic label, e.g. 'RAG reranking'"},
                "content": {"type": "string", "description": "What was learned, one or a few sentences"},
                "tags": {"type": "string", "description": "Comma-separated keywords, e.g. 'ml,rag,python'"},
                "source": {"type": "string", "description": "Where this came from: paper title, URL, book"},
            },
            "required": ["topic", "content"],
        },
        fn=log_learning,
    )


def make_search_tool(conn: sqlite3.Connection) -> Tool:
    def search_learnings(query: str, limit: int = 8) -> str:
        import re
        words = re.findall(r"[a-zA-Z0-9]{2,}", query.lower())
        fts = " OR ".join(dict.fromkeys(words)) if words else ""

        if fts:
            rows = conn.execute(
                "SELECT l.topic, l.content, l.tags, l.source, l.learned_at "
                "FROM learnings_fts JOIN learnings l ON l.id = learnings_fts.rowid "
                "WHERE learnings_fts MATCH ? ORDER BY rank LIMIT ?",
                (fts, max(1, min(int(limit), 20))),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT topic, content, tags, source, learned_at FROM learnings "
                "ORDER BY learned_at DESC LIMIT ?",
                (max(1, min(int(limit), 20)),),
            ).fetchall()

        if not rows:
            return f"No learnings found matching '{query}'. Try a broader query or log something first."

        lines = [f"Learnings matching '{query}':"]
        for r in rows:
            tag_str = f" [{r['tags']}]" if r["tags"] else ""
            src_str = f" — {r['source']}" if r["source"] else ""
            date_str = (r["learned_at"] or "")[:10]
            lines.append(f"• [{date_str}] {r['topic']}{tag_str}{src_str}: {r['content']}")
        return "\n".join(lines)

    return Tool(
        name="search_learnings",
        description=(
            "Search the user's personal learning journal. Use when they ask 'what do I know about X', "
            "'what have I learned about Y', 'recall my notes on Z', or want to review past study. "
            "Returns their own logged notes, ranked by relevance."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for, e.g. 'RAG reranking' or 'attention mechanism'"},
                "limit": {"type": "integer", "description": "Max results to return (default 8)"},
            },
            "required": ["query"],
        },
        fn=search_learnings,
    )
