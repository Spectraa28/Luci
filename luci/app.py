"""Wiring — builds one luci from its parts. Gateways call `respond()`.

config → db → tools → memory → session → loop
"""

from __future__ import annotations

from luci.config import Settings, load_settings
from luci.db import connect
from luci.loop.agent import LoopResult, Observer, run_loop
from luci.loop.models import get_client
from luci.ops.tracing import Tracer, compose
from luci.runtime.session import Session
from luci.tools import build_registry


class luci:
    def __init__(self, settings: Settings | None = None, client=None, conn=None):
        self.settings = settings or load_settings()
        self.settings.ensure_home()
        self.conn = conn or connect(self.settings.home)
        self.client = client or get_client(self.settings)

        from luci.memory import Memory
        self.memory = Memory(self.conn, self.settings, self.client)
        self.tools = build_registry(self.conn, self.settings, self.memory)
        self.mcp_bridge = getattr(self.tools, "mcp_bridge", None)
        self.session = Session(self.settings, memory=self.memory)
        self.tracer = Tracer(self.settings)

    def close(self) -> None:
        if self.mcp_bridge is not None:
            self.mcp_bridge.close()

    def respond(self, user_message: str, observer: Observer | None = None,
                source: str = "cli", stream: bool = False) -> LoopResult:
        """One full turn: assemble working memory → run the loop → persist."""
        notify = compose(observer, self.tracer.event)

        with self.tracer.turn(user_message):
            system = self.session.build_system(user_message, notify=notify)
            messages = list(self.session.history) + [{"role": "user", "content": user_message}]

            result = run_loop(
                client=self.client,
                model=self.settings.model,
                system=system,
                messages=messages,
                tools=self.tools,
                max_iterations=self.settings.max_iterations,
                max_tokens=self.settings.max_tokens,
                observer=notify,
                stream=stream,
            )

            self.session.add_exchange(user_message, result.reply, tool_calls=result.tool_calls,
                                      source=source)
            if self.memory is not None:
                self.memory.maybe_consolidate(notify=notify)
                self.memory.export_markdown()

        self.tracer.end_turn(result.reply, result.iterations)
        return result
