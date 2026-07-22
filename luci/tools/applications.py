"""track_application / list_applications — job application tracker.

track_application: log or update an application (company, role, status).
list_applications: surface what's pending, filtering by status.
"""

from __future__ import annotations

import sqlite3

from luci.tools.registry import Tool

VALID_STATUSES = {"applied", "interviewing", "offer", "rejected", "closed"}


def make_track_tool(conn: sqlite3.Connection) -> Tool:
    def track_application(company: str, role: str, status: str = "applied", notes: str = "") -> str:
        if not company or not role:
            return "track_application needs at least a company and role."
        status = status.lower().strip()
        if status not in VALID_STATUSES:
            status = "applied"

        existing = conn.execute(
            "SELECT id FROM applications WHERE lower(company)=lower(?) AND lower(role)=lower(?)",
            (company, role),
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE applications SET status=?, notes=?, updated_at=datetime('now','localtime') WHERE id=?",
                (status, notes, existing["id"]),
            )
            conn.commit()
            return f"Updated '{role}' at {company} → status: {status}." + (f" Notes: {notes}" if notes else "")
        else:
            conn.execute(
                "INSERT INTO applications (company, role, status, notes) VALUES (?, ?, ?, ?)",
                (company.strip(), role.strip(), status, notes.strip()),
            )
            conn.commit()
            return f"Logged application: '{role}' at {company} (status: {status})." + (f" Notes: {notes}" if notes else "")

    return Tool(
        name="track_application",
        description=(
            "Log or update a job application. Use when the user mentions applying to a company, "
            "getting a call, receiving an offer, or being rejected. "
            "status must be one of: applied, interviewing, offer, rejected, closed. "
            "If an entry for the same company+role exists, it updates instead of duplicating."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "company": {"type": "string", "description": "Company name, e.g. 'Setu'"},
                "role": {"type": "string", "description": "Role title, e.g. 'ML Engineer'"},
                "status": {"type": "string", "description": "applied | interviewing | offer | rejected | closed"},
                "notes": {"type": "string", "description": "Any context — recruiter name, next step, salary, etc."},
            },
            "required": ["company", "role"],
        },
        fn=track_application,
    )


def make_list_tool(conn: sqlite3.Connection) -> Tool:
    def list_applications(status: str = "", limit: int = 20) -> str:
        query = "SELECT company, role, status, notes, applied_at, updated_at FROM applications"
        params: list = []
        if status:
            status = status.lower().strip()
            query += " WHERE status=?"
            params.append(status)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 100)))

        rows = conn.execute(query, params).fetchall()
        if not rows:
            label = f" with status '{status}'" if status else ""
            return f"No applications found{label}. Start tracking with track_application."

        lines = ["Applications:"]
        for r in rows:
            note_str = f" — {r['notes']}" if r["notes"] else ""
            date_str = (r["updated_at"] or r["applied_at"] or "")[:10]
            lines.append(f"• [{r['status'].upper()}] {r['role']} @ {r['company']} ({date_str}){note_str}")
        return "\n".join(lines)

    return Tool(
        name="list_applications",
        description=(
            "List tracked job applications. Use when the user asks what's pending, "
            "what needs follow-up, or wants a status overview. "
            "Filter by status (applied, interviewing, offer, rejected, closed) or leave blank for all."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by status, e.g. 'applied'. Leave blank for all."},
                "limit": {"type": "integer", "description": "Max results (default 20)"},
            },
            "required": [],
        },
        fn=list_applications,
    )
