"""Edge-case coverage for models, render, and config helpers."""

from __future__ import annotations

from wikisync import render
from wikisync.config import Config, _int, env_bool
from tests.support import SAMPLE_ROWS, make_edit


# --- models URL builders ----------------------------------------------------
def test_model_urls_and_lang():
    edit = make_edit(host="be-tarask.wikipedia.org", title="Фоо Бар", revid=5, parentid=4)
    assert edit.lang == "be-tarask"
    assert edit.page_url.startswith("https://be-tarask.wikipedia.org/wiki/")
    assert "diff=5" in edit.diff_url and "oldid=4" in edit.diff_url
    assert edit.permalink.endswith("oldid=5")
    assert edit.user_url.endswith("/wiki/User:Tester")
    assert edit.user_contribs_url.endswith("/wiki/Special:Contributions/Tester")


def test_new_page_diff_url_uses_own_revid_as_oldid():
    edit = make_edit(revid=77, parentid=0, is_new=True)
    assert "diff=77" in edit.diff_url and "oldid=77" in edit.diff_url


# --- render -----------------------------------------------------------------
def test_format_title_default_and_clamp():
    title = render.format_title(make_edit(title="Foo", sizediff=-3), "[{lang}] {title} ({sizediff:+d})")
    assert title == "[en] Foo (-3)"
    assert len(render.format_title(make_edit(title="x" * 400), "{title}")) == 255


def test_format_title_bad_template_falls_back():
    # Unknown placeholder triggers the fallback path.
    title = render.format_title(make_edit(title="Foo"), "{nope}")
    assert title.startswith("[en] Foo")


def test_diff_text_truncates():
    text = render.diff_rows_to_text(SAMPLE_ROWS, max_lines=1)
    assert "truncated" in text


# --- config helpers ---------------------------------------------------------
def test_int_helper_default_on_garbage():
    assert _int("abc", 50) == 50
    assert _int("7", 0) == 7
    assert _int(None, 9) == 9


def test_env_bool_variants():
    assert env_bool("yes") is True
    assert env_bool("0") is False
    assert env_bool("", default=True) is True
    assert env_bool(None, default=False) is False


def test_config_int_fallback_from_env():
    cfg = Config.from_env({"WIKIPEDIA_USERNAME": "U", "MAX_EDITS_PER_RUN": "notanumber"})
    assert cfg.max_edits == 50
