"""Edge-case coverage for models, render, and config helpers."""

from __future__ import annotations

import pytest

from tests.support import SAMPLE_ROWS, make_edit
from wikisync import render
from wikisync.config import Config, _int, env_bool


# --- models URL builders ----------------------------------------------------
def test_model_urls_and_lang():
    edit = make_edit(host='be-tarask.wikipedia.org', title='Фоо Бар', revid=5, parentid=4)
    assert edit.lang == 'be-tarask'
    assert edit.page_url.startswith('https://be-tarask.wikipedia.org/wiki/')
    assert 'diff=5' in edit.diff_url and 'oldid=4' in edit.diff_url
    assert edit.permalink.endswith('oldid=5')
    assert edit.user_url.endswith('/wiki/User:Tester')
    assert edit.user_contribs_url.endswith('/wiki/Special:Contributions/Tester')


@pytest.mark.parametrize(
    ('host', 'title'),
    [
        ('en.wikipedia.org', 'AT&T'),
        ('en.wikipedia.org', 'C++'),
        ('en.wikipedia.org', '99% Invisible'),
        ('en.wikipedia.org', '"Heroes" (album)'),
        ('en.wikipedia.org', "Schrödinger's cat"),
        ('ru.wikipedia.org', 'Пенья, Хосе Луис Хордан'),
    ],
)
def test_diff_url_uses_only_revision_ids_for_real_article_titles(host, title):
    edit = make_edit(
        host=host,
        title=title,
        revid=154036623,
        parentid=153423849,
    )
    assert edit.diff_url == f'https://{host}/w/index.php?diff=154036623&oldid=153423849'
    assert '%' not in edit.diff_url


def test_diff_url_is_stable_when_page_title_changes():
    before_move = make_edit(title='AT&T')
    after_move = make_edit(title='AT and T')
    assert before_move.diff_url == after_move.diff_url


def test_diff_url_distinguishes_edits_to_same_article():
    first = make_edit(title='AT&T', revid=100, parentid=99)
    second = make_edit(title='AT&T', revid=101, parentid=100)
    assert first.diff_url != second.diff_url


def test_dedup_urls_include_historical_title_formats():
    edit = make_edit(title='C++ & "More"')
    assert edit.dedup_urls == (
        'https://en.wikipedia.org/w/index.php?diff=100&oldid=99',
        'https://en.wikipedia.org/w/index.php?title=C++_&_"More"&diff=100&oldid=99',
        'https://en.wikipedia.org/w/index.php?title=C%2B%2B+%26+%22More%22&diff=100&oldid=99',
    )


@pytest.mark.parametrize('is_new', [False, True])
def test_zero_parent_links_created_revision_regardless_of_flag(is_new):
    edit = make_edit(revid=77, parentid=0, is_new=is_new)
    assert edit.diff_url == 'https://en.wikipedia.org/w/index.php?oldid=77'


# --- render -----------------------------------------------------------------
def test_format_title_default_and_clamp():
    title = render.format_title(make_edit(title='Foo', sizediff=-3), '[{lang}] {title} ({sizediff:+d})')
    assert title == '[en] Foo (-3)'
    assert len(render.format_title(make_edit(title='x' * 400), '{title}')) == 255


def test_format_title_bad_template_falls_back():
    # Unknown placeholder triggers the fallback path.
    title = render.format_title(make_edit(title='Foo'), '{nope}')
    assert title == '[en] Foo (+42 B)'


def test_diff_text_truncates():
    text = render.diff_rows_to_text(SAMPLE_ROWS, max_lines=1)
    assert 'truncated' in text


# --- config helpers ---------------------------------------------------------
def test_int_helper_default_on_garbage():
    assert _int('abc', 50) == 50
    assert _int('7', 0) == 7
    assert _int(None, 9) == 9


def test_env_bool_variants():
    assert env_bool('yes') is True
    assert env_bool('0') is False
    assert env_bool('', default=True) is True
    assert env_bool(None, default=False) is False


def test_config_int_fallback_from_env():
    cfg = Config.from_env({'WIKIPEDIA_USERNAME': 'U', 'MAX_EDITS_PER_RUN': 'notanumber'})
    assert cfg.max_edits == 50
