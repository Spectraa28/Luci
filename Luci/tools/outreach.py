"""draft_outreach — cold outreach drafter.

Pulls relevant facts from memory (saved notes + learnings), then writes
a short punchy cold DM in the user's voice. Saves the draft to outreach_drafts
so there's a record of what was sent.

No extra API call — the loop handles the reasoning. This tool just:
1. Queries the DB for relevant context about the company/contact
2. Returns that context + a prompt for Luci to write the message
3. Luci writes the draft in the same loop iteration
"""

from __future__ import annotations

import re
import sqlite3

from Luci.tools.registry import Tool


def _fts_query(text: str) -> str:
    words = re.findall(r"[a-zA-Z0-9]{2,}", text.lower())
    return " OR ".join(dict.fromkeys(words)) if words else ""

def make_tool(conn: sqlite3.Connection) -> Tool:
    def draft_outreach(company: str, contact: str = "", purpose: str = "") -> str:
        if not company:
            return "draft_outreach needs at least a company name."

        # Pull relevant facts from memory
        context_lines = []
        fts = _fts_query(company + " " + contact)
        if fts:
            fact_rows = conn.execute(
                "SELECT f.subject, f.content FROM facts_fts JOIN facts f ON f.id = facts_fts.rowid "
                "WHERE facts_fts MATCH ? ORDER BY rank LIMIT 5",
                (fts,),
            ).fetchall()
            for r in fact_rows:
                context_lines.append(f"[fact] {r['subject']}: {r['content']}")

            learn_rows = conn.execute(
                "SELECT l.topic, l.content FROM learnings_fts JOIN learnings l ON l.id = learnings_fts.rowid "
                "WHERE learnings_fts MATCH ? ORDER BY rank LIMIT 3",
                (fts,),
            ).fetchall()
            for r in learn_rows:
                context_lines.append(f"[learning] {r['topic']}: {r['content']}")

        context_str = "\n".join(context_lines) if context_lines else "No prior context found for this company."
        purpose_str = f"Purpose: {purpose}" if purpose else "Purpose: general outreach / introduce myself"

        # Save draft slot — actual draft text written by Luci in the reply
        conn.execute(
            "INSERT INTO outreach_drafts (company, contact, draft, context) VALUES (?, ?, ?, ?)",
            (company.strip(), contact.strip(), "[draft pending — see Luci reply]", context_str),
        )
        conn.commit()

        return (
            f"Context pulled for outreach to {company}"
            + (f" ({contact})" if contact else "")
            + f":\n{context_str}\n\n{purpose_str}\n\n"
            "Now write a short cold outreach message (3-5 sentences max). "
            "Direct voice, no em dashes, no corporate filler. "
            "Lead with a specific hook from the context above if available. "
            "End with one clear ask."
        )

    return Tool(
        name="draft_outreach",
        description=(
            "Draft a cold outreach message to a company or contact. Pulls relevant saved facts "
            "and learnings from memory to personalise the message. "
            "Use when the user says 'draft a message to X', 'write a cold DM to Y', "
            "'help me reach out to Z'. "
            "company: company name. contact: person's name/role if known. "
            "purpose: what the user wants (default: general intro)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "company": {"type": "string", "description": "Company to reach out to"},
                "contact": {"type": "string", "description": "Person's name or role, if known"},
                "purpose": {"type": "string", "description": "What you want — e.g. 'discuss ML role', 'share my RAG project'"},
            },
            "required": ["company"],
        },
        fn=draft_outreach,
    )