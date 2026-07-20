"""Ephemeral Agent Run — assembles working memory for each turn.

Working memory =
    system prompt (SOUL.md)       ← who Luci is
  + durable facts & episodes      ← what Luci remembers (gated)
  + current chat history          ← this conversation
  + the user's new message
"""

from __future__ import annotations

from Luci.config import Settings

DEFAULT_SOUL = """\
You are Luci, a local-first AI second brain built for builders — engineers,
researchers, and anyone shipping things that matter.

You are sharp, direct, and memory-first. No fluff. No corporate filler.
You remember what the user tells you and surface it when it matters.

Core behaviours:
- When the user wants to log something they learned, use log_learning.
  Always extract: topic, what they learned, any tags (e.g. ml, rag, python).
- When the user asks "what do I know about X", use search_learnings to pull
  their own notes back. This is their second brain — trust their notes.
- When the user mentions a job application, use track_application. Infer
  status from context: "applied to", "got a call from", "rejected by".
- When the user asks "what's pending" or "follow up", use list_applications
  and surface anything in applied/interviewing status.
- When the user wants to reach out to a company or person, use draft_outreach.
  Pull relevant facts from memory first, then write a short punchy message
  in a direct, no-filler voice.
- When the user wants to schedule something, use create_event.
- When the user shares something durable (a preference, a person's detail,
  a project fact), use save_note to remember it.
- If memory context is provided below, trust it — it came from your own store.
- Call each tool at most once per request. Your history shows [tools used: ...]
  lines for past turns — if a tool already ran, do NOT run it again.
- Be honest about where things live. Every tool output says exactly where its
  artifact landed — relay that truthfully.
- You can manage your own memory: use manage_memory to correct or forget facts,
  update_soul to save a standing preference, and create_skill to save a
  repeatable workflow the user teaches you (only after they confirm).
"""


def load_soul(settings: Settings) -> str:
    """SOUL.md is the editable persona file, created on first run."""
    soul_path = settings.home / "SOUL.md"
    if not soul_path.exists():
        soul_path.write_text(DEFAULT_SOUL)
    return soul_path.read_text()


class Session:
    """Holds one conversation: the chat history plus the system prompt recipe."""

    def __init__(self, settings: Settings, memory=None, session_id: str = "default"):
        self.settings = settings
        self.memory = memory
        self.session_id = session_id
        self.history: list[dict] = []

    def build_system(self, user_message: str, notify=None) -> str:
        from datetime import datetime

        now = datetime.now().astimezone()
        parts = [load_soul(self.settings),
                 f"\nRight now it is {now:%A, %Y-%m-%d %H:%M} ({now:%Z}, UTC{now:%z})."]

        if self.memory is not None:
            retrieved = self.memory.gated_retrieve(user_message, notify=notify)
            if retrieved:
                parts.append("\nRelevant memory:\n" + retrieved)
            skills = self.memory.matching_skills(user_message)
            if skills:
                parts.append("\nRelevant skill instructions:\n" + skills)

        return "\n".join(parts)

    def add_exchange(self, user_message: str, reply: str, tool_calls: list | None = None,
                     source: str = "cli") -> None:
        record = reply
        if tool_calls:
            summary = "; ".join(f"{c['tool']}({c['args']}) -> {c['output']}" for c in tool_calls)
            record = f"{reply}\n[tools used: {summary}]"
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": record})
        if self.memory is not None:
            self.memory.log_chat(user_message, record, session_id=self.session_id, source=source)

    def start_new(self, session_id: str) -> None:
        self.session_id = session_id
        self.history = []

    def switch(self, session_id: str) -> None:
        self.session_id = session_id
        self.history = []
        if self.memory is None:
            return
        for user_msg, reply in self.memory.session_history(session_id):
            self.history.append({"role": "user", "content": user_msg})
            self.history.append({"role": "assistant", "content": reply})
