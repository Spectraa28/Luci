"""Google Calendar sync — the cross-platform counterpart to Apple Calendar.

Where events land (same shape as calendar.py's Apple path):
  always      state.db (the eval asserts here) + calendar.ics (importable file)
  opt-in      the user's real Google Calendar, via OAuth — set LUCI_GOOGLE_CALENDAR=1.
              First use opens a browser for a one-time consent screen; the
              refreshable token is cached at .luci/google_token.json so every
              call after that is silent.

Deliberately dependency-light (this repo's whole ethos): no google-api-python-client.
Auth uses google-auth-oauthlib (just the browser-consent dance) and everything
after that is a couple of plain REST calls via `requests`. Both are optional —
pip install -e '.[google]' — so people who don't use this tool pay nothing.

The tool's return string always says exactly where the event went, same
contract as the Apple path — the model relays it, never over-claims.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


def _load_credentials(home: Path, credentials_path: Path):
    """Return a valid google.oauth2.credentials.Credentials, refreshing or
    running the one-time browser consent flow as needed. Raises RuntimeError
    with a human-readable message on any setup problem — never a raw
    traceback the model would have to guess at."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError(
            "Google Calendar sync needs an extra: pip install -e '.[google]' "
            f"(missing: {exc.name})."
        ) from exc

    token_path = home / "google_token.json"
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), _SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds or not creds.valid:
        if not credentials_path.exists():
            raise RuntimeError(
                f"no OAuth client file at {credentials_path}. In Google Cloud Console: "
                "enable the Calendar API, create an OAuth client ID (type 'Desktop app'), "
                f"and save the downloaded JSON to {credentials_path}."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), _SCOPES)
        # Opens a browser once; blocks until the user finishes the consent screen.
        creds = flow.run_local_server(port=0)

    token_path.write_text(creds.to_json())
    return creds


def sync_to_google_calendar(
    home: Path, credentials_path: Path, title: str, start: str, end: str,
    notes: str = "", attendees: str = "",
) -> str:
    """Create the event on the user's primary Google Calendar. Returns a short
    human-readable outcome for the tool output, mirroring sync_to_apple_calendar."""
    try:
        import requests
    except ImportError:
        return "Google Calendar sync skipped (missing dependency: pip install -e '.[google]')."

    try:
        creds = _load_credentials(home, credentials_path)
    except RuntimeError as exc:
        return f"Google Calendar sync FAILED ({exc}) — the event is still saved locally."

    body = {
        "summary": title,
        "description": notes or None,
        "start": {"dateTime": _rfc3339(start)},
        "end": {"dateTime": _rfc3339(end)},
    }
    if attendees:
        # Only real-looking emails; a bare name would make the API reject the
        # whole request, and the model shouldn't have to know that.
        body["attendees"] = [{"email": a.strip()} for a in attendees.split(",") if "@" in a]
    body = {k: v for k, v in body.items() if v is not None}

    try:
        resp = requests.post(
            _EVENTS_URL,
            headers={"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"},
            data=json.dumps(body),
            timeout=15,
        )
    except requests.RequestException as exc:
        return f"Google Calendar sync FAILED (network error: {exc}) — the event is still saved locally."

    if resp.status_code >= 300:
        detail = (resp.text or "")[:160]
        return f"Google Calendar sync FAILED ({resp.status_code}: {detail}) — the event is still saved locally."

    link = (resp.json() or {}).get("htmlLink", "")
    return "Also added to Google Calendar (primary)." + (f" {link}" if link else "")


def _rfc3339(iso_minute: str) -> str:
    """'2026-07-14T09:00' -> '2026-07-14T09:00:00' (Google requires seconds;
    timezone is left off on purpose — the API then assumes the calendar's
    own timezone, which matches what the user meant when they said '9am')."""
    dt = datetime.fromisoformat(iso_minute)
    return dt.isoformat(timespec="seconds")


def is_available() -> bool:
    """Cheap check used by the dashboard to render setup status without
    doing a real OAuth round-trip on every 5s poll."""
    try:
        import google_auth_oauthlib  # noqa: F401
        import requests  # noqa: F401
    except ImportError:
        return False
    return sys.version_info >= (3, 11)
