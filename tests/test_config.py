"""Tests for multi-wiki configuration parsing (no network)."""

from __future__ import annotations

from datetime import datetime, timezone

from wikisync.config import Config
from wikisync.models import Edit


def _cfg(**env) -> Config:
    base = {"WIKIPEDIA_USERNAME": "Foo"}
    base.update(env)
    return Config.from_env(base)


def test_default_is_english():
    assert _cfg().hosts == ["en.wikipedia.org"]


def test_comma_separated_langs_become_hosts():
    cfg = _cfg(WIKIPEDIA_LANG="en, ru ,be,be-tarask")
    assert cfg.hosts == [
        "en.wikipedia.org",
        "ru.wikipedia.org",
        "be.wikipedia.org",
        "be-tarask.wikipedia.org",
    ]


def test_host_override_wins_and_dedupes():
    cfg = _cfg(WIKIPEDIA_LANG="en,ru", WIKIPEDIA_HOST="commons.wikimedia.org, commons.wikimedia.org")
    assert cfg.hosts == ["commons.wikimedia.org"]


def test_edit_lang_label_keeps_hyphen():
    edit = Edit(
        host="be-tarask.wikipedia.org", username="U", revid=1, parentid=0, title="T",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), comment="", sizediff=0,
        is_new=True, is_minor=False, is_top=True,
    )
    assert edit.lang == "be-tarask"
