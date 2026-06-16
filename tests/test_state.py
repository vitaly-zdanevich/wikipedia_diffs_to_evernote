"""Tests for state persistence."""

from __future__ import annotations

from wikisync import state


def test_load_missing_file(tmp_path):
    assert state.load(str(tmp_path / "nope.json")) == {}


def test_load_empty_file(tmp_path):
    p = tmp_path / "empty.json"
    p.write_text("")
    assert state.load(str(p)) == {}


def test_load_corrupt_file(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{ not json")
    assert state.load(str(p)) == {}


def test_load_null_becomes_empty(tmp_path):
    p = tmp_path / "null.json"
    p.write_text("null")
    assert state.load(str(p)) == {}


def test_roundtrip_and_get_update(tmp_path):
    path = str(tmp_path / "state.json")
    st = {}
    state.update(st, "en.wikipedia.org", "User One", 12345, "2026-06-12T22:00:00Z")
    state.save(path, st)

    loaded = state.load(path)
    assert loaded == st
    assert state.get(loaded, "en.wikipedia.org", "User One") == (12345, "2026-06-12T22:00:00Z")


def test_get_unknown_returns_none_pair():
    assert state.get({}, "h", "u") == (None, None)
