"""Environment-driven configuration for the core pipeline.

Only *core* settings live here. Each sink reads its own credentials from the
environment in its ``from_env`` classmethod, so this stays destination-agnostic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def env_bool(value: str | None, default: bool = False) -> bool:
    """Parse a truthy environment string."""
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on", "y")


def _int(value: str | None, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


# Default User-Agent. The Wikimedia API policy asks for a descriptive UA with a
# contact; override via WIKIPEDIA_USER_AGENT to point at your own repo/email.
_DEFAULT_UA = (
    "wikisync/1.0 (https://github.com/; diffs_to_evernote) python-requests"
)

# Default note title, formatted with .format(title=, date=, sizediff=, revid=, user=, host=, lang=).
# The [lang] prefix distinguishes wikis when syncing several at once.
_DEFAULT_TITLE = "[{lang}] {title} — {date:%Y-%m-%d %H:%M} ({sizediff:+d} B)"


@dataclass
class Config:
    username: str
    hosts: list[str]
    targets: list[str]
    dedup: bool
    max_edits: int
    first_run_lookback_days: int
    state_file: str
    user_agent: str
    note_title_template: str
    log_level: str

    @classmethod
    def from_env(cls, env: "os._Environ[str] | dict[str, str]") -> "Config":
        username = (env.get("WIKIPEDIA_USERNAME") or "").strip()
        if not username:
            raise SystemExit("WIKIPEDIA_USERNAME is required (the Wikipedia user whose edits to sync).")

        # WIKIPEDIA_LANG is a comma-separated list of language editions ("en,ru,be,be-tarask").
        # WIKIPEDIA_HOST (also comma-separated) overrides it for non-Wikipedia wikis.
        langs = [s.strip() for s in (env.get("WIKIPEDIA_LANG") or "en").split(",") if s.strip()] or ["en"]
        explicit_hosts = [s.strip() for s in (env.get("WIKIPEDIA_HOST") or "").split(",") if s.strip()]
        hosts = explicit_hosts or [f"{lang}.wikipedia.org" for lang in langs]
        hosts = list(dict.fromkeys(hosts))  # de-dupe, preserve order

        targets = [t.strip().lower() for t in (env.get("EXPORT_TARGETS") or "evernote").split(",") if t.strip()]
        if not targets:
            targets = ["evernote"]

        return cls(
            username=username,
            hosts=hosts,
            targets=targets,
            dedup=env_bool(env.get("EXPORT_DEDUP"), default=True),
            max_edits=_int(env.get("MAX_EDITS_PER_RUN"), 50),
            first_run_lookback_days=_int(env.get("FIRST_RUN_LOOKBACK_DAYS"), 7),
            state_file=(env.get("STATE_FILE") or "state.json").strip(),
            user_agent=(env.get("WIKIPEDIA_USER_AGENT") or "").strip() or _DEFAULT_UA,
            note_title_template=(env.get("NOTE_TITLE_TEMPLATE") or "").strip() or _DEFAULT_TITLE,
            log_level=(env.get("LOG_LEVEL") or "INFO").strip().upper(),
        )
