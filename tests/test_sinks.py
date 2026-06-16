"""Tests for the sink registry, the stdout sink, and the base default."""

from __future__ import annotations

import pytest

from tests.support import SAMPLE_ROWS, make_edit
from wikisync.models import DiffContent
from wikisync.sinks import build_sinks
from wikisync.sinks.stdout import StdoutSink


def test_build_sinks_known():
    sinks = build_sinks(['stdout'], {}, dedup=True)
    assert len(sinks) == 1 and sinks[0].name == 'stdout'


def test_build_sinks_unknown_raises():
    with pytest.raises(SystemExit):
        build_sinks(['telegram'], {}, dedup=True)


def test_stdout_export_diff(capsys):
    StdoutSink().export(make_edit(), DiffContent('diff', SAMPLE_ROWS), 'Title')
    out = capsys.readouterr().out
    assert 'Title' in out and 'Tester' in out and 'DIFF' in out


def test_stdout_export_newpage_and_unavailable(capsys):
    sink = StdoutSink()
    sink.export(make_edit(is_new=True, parentid=0), DiffContent('newpage', 'WIKITEXT-HERE'), 'T')
    sink.export(make_edit(), DiffContent('unavailable'), 'T')
    out = capsys.readouterr().out
    assert 'WIKITEXT-HERE' in out and 'unavailable' in out


def test_base_exists_default_is_false():
    # StdoutSink doesn't override exists(), so this exercises Sink.exists default.
    assert StdoutSink().exists(make_edit()) is False
