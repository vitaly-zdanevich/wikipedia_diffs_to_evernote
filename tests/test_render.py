"""Tests for the shared diff renderer (no network, no credentials)."""

from __future__ import annotations

from datetime import UTC, datetime
from xml.etree import ElementTree as ET

from tests.support import SAMPLE_ROWS
from wikisync import render
from wikisync.models import Edit


def test_xhtml_is_well_formed_and_inline_styled():
    xhtml = render.diff_rows_to_xhtml(SAMPLE_ROWS)
    # Must parse as XML (ENML requires well-formed XML).
    ET.fromstring(xhtml)
    # ENML keeps style, not class/data-*.
    assert 'class=' not in xhtml
    assert 'data-marker' not in xhtml
    assert 'style=' in xhtml
    # Added/removed lines are colour-coded; inline changes highlighted.
    assert '#d6f5d6' in xhtml  # added line background
    assert '#ffe0e0' in xhtml  # deleted line background
    # The +/- marker glyphs survive as text.
    assert '−' in xhtml and '+' in xhtml


def test_text_diff_has_unified_markers():
    text = render.diff_rows_to_text(SAMPLE_ROWS)
    lines = text.splitlines()
    assert any(line.startswith('@@') for line in lines)
    assert any(line.startswith('-') for line in lines)
    assert any(line.startswith('+') for line in lines)


def _edit(**kw):
    base = {
        'host': 'en.wikipedia.org',
        'username': 'Jimbo Wales',
        'revid': 42,
        'parentid': 41,
        'title': 'Foo Bar',
        'timestamp': datetime(2026, 6, 12, 22, 0, tzinfo=UTC),
        'comment': '',
        'sizediff': -1234,
        'is_new': False,
        'is_minor': False,
        'is_top': True,
    }
    base.update(kw)
    return Edit(**base)


def test_title_default_and_clamping():
    title = render.format_title(_edit(), '{title} — {date:%Y-%m-%d} ({sizediff:+d} B)')
    assert title == 'Foo Bar — 2026-06-12 (-1234 B)'
    long_title = render.format_title(_edit(title='x' * 400), '{title}')
    assert len(long_title) == 255


def test_urls():
    e = _edit()
    assert e.diff_url == 'https://en.wikipedia.org/w/index.php?title=Foo+Bar&diff=42&oldid=41'
    assert e.user_contribs_url.endswith('/wiki/Special:Contributions/Jimbo_Wales')
    assert e.page_url.endswith('/wiki/Foo_Bar')
