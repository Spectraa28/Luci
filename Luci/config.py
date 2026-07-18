from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # --- LLM
    provider: str = field(default_factory=lambda: os.getenv("LUCI_PROVIDER", "anthropic"))
    api_key: str = field(default_factory=lambda: os.getenv("LUCI_API_KEY", ""))
    base_url: str | None = field(default_factory=lambda: os.getenv("LUCI_BASE_URL") or None)
    model: str = field(default_factory=lambda: os.getenv("LUCI_MODEL", ""))
    small_model: str = field(default_factory=lambda: os.getenv("LUCI_SMALL_MODEL", ""))

    # --- Home: where Luci keeps its state (memory DB, calendar, outbox, traces).
    home: Path = field(default_factory=lambda: Path(os.getenv("LUCI_HOME", ".luci")))

    # --- Loop guardrails
    max_iterations: int = field(default_factory=lambda: int(os.getenv("LUCI_MAX_ITERATIONS", "10")))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("LUCI_MAX_TOKENS", "2048")))

    # --- Memory
    consolidate_every: int = field(default_factory=lambda: int(os.getenv("LUCI_CONSOLIDATE_EVERY", "6")))
    retrieval_top_k: int = field(default_factory=lambda: int(os.getenv("LUCI_RETRIEVAL_TOP_K", "4")))
    semantic_store: str = field(default_factory=lambda: os.getenv("LUCI_SEMANTIC_STORE", "sqlite"))

    # --- Tools
    apple_calendar: bool = field(
        default_factory=lambda: os.getenv("LUCI_APPLE_CALENDAR", "") in ("1", "true", "yes")
    )
    apple_tools: bool = field(
        default_factory=lambda: os.getenv("LUCI_APPLE_TOOLS", "") in ("1", "true", "yes")
    )
    google_calendar: bool = field(
        default_factory=lambda: os.getenv("LUCI_GOOGLE_CALENDAR", "") in ("1", "true", "yes")
    )
    google_calendar_credentials: Path = field(
        default_factory=lambda: Path(
            os.getenv("LUCI_GOOGLE_CREDENTIALS", "")
            or (os.getenv("LUCI_HOME", ".luci") + "/google_credentials.json")
        )
    )

    # --- Optional gateway
    telegram_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))

    # --- Tracing
    otel_endpoint: str = field(
        default_factory=lambda: os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    )

    def ensure_home(self) -> Path:
        self.home.mkdir(parents=True, exist_ok=True)
        (self.home / "traces").mkdir(exist_ok=True)
        (self.home / "outbox").mkdir(exist_ok=True)
        return self.home


def load_settings() -> Settings:
    return Settings()
