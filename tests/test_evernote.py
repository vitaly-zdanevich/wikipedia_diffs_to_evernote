"""Tests for the Evernote sink (Thrift client mocked)."""

from __future__ import annotations

from xml.etree import ElementTree as ET

import pytest
from evernote.edam.error.ttypes import EDAMUserException

from wikisync.sinks import evernote as ev
from wikisync.sinks.evernote import EvernoteSink
from wikisync.models import DiffContent
from tests.support import FakeNoteStore, SAMPLE_ROWS, make_edit


def _sink(**kw):
    return EvernoteSink(token="tok", **kw)


# --- from_env ---------------------------------------------------------------
def test_from_env_requires_token():
    with pytest.raises(SystemExit):
        EvernoteSink.from_env({}, dedup=True)


def test_from_env_parses_options():
    sink = EvernoteSink.from_env(
        {"EVERNOTE_DEV_TOKEN": "t", "EVERNOTE_NOTEBOOK": "NB",
         "EVERNOTE_TAGS": "a, b", "EVERNOTE_SANDBOX": "true"},
        dedup=False,
    )
    assert sink.token == "t" and sink.notebook_name == "NB"
    assert sink.tags == ["a", "b"]
    assert sink.service_host == "sandbox.evernote.com"
    assert sink.dedup is False


# --- ENML construction ------------------------------------------------------
def test_build_enml_diff_is_wellformed_and_clean():
    enml = _sink()._build_enml(make_edit(comment='x & <y> "z"'), DiffContent("diff", SAMPLE_ROWS))
    ET.fromstring(enml.encode("utf-8"))  # raises if not well-formed XML
    assert "class=" not in enml and " id=" not in enml and "data-marker" not in enml
    assert "#d6f5d6" in enml and "#ffe0e0" in enml          # added/removed colours
    assert "Special:Contributions/Tester" in enml            # clickable editor
    assert "&amp;" in enml and "&lt;y&gt;" in enml            # escaped summary


def test_build_enml_newpage_and_unavailable_wellformed():
    sink = _sink()
    edit = make_edit(is_new=True, parentid=0)
    ET.fromstring(sink._build_enml(edit, DiffContent("newpage", "== H == <b> & x")).encode("utf-8"))
    ET.fromstring(sink._build_enml(edit, DiffContent("unavailable")).encode("utf-8"))


# --- export / exists / notebook (note store mocked) -------------------------
def test_export_creates_note():
    sink = _sink(tags=["wikipedia"])
    sink._note_store = FakeNoteStore()
    sink.export(make_edit(), DiffContent("diff", SAMPLE_ROWS), "My Title")

    assert len(sink._note_store.created) == 1
    token, note = sink._note_store.created[0]
    assert token == "tok" and note.title == "My Title"
    assert note.attributes.sourceURL.startswith("https://en.wikipedia.org/w/index.php")
    assert note.tagNames == ["wikipedia"]
    ET.fromstring(note.content.encode("utf-8"))


def test_exists_dedup():
    sink = _sink(dedup=True)
    sink._note_store = FakeNoteStore(total_notes=1)
    assert sink.exists(make_edit()) is True
    sink._note_store = FakeNoteStore(total_notes=0)
    assert sink.exists(make_edit()) is False


def test_exists_disabled_short_circuits():
    sink = _sink(dedup=False)
    sink._note_store = FakeNoteStore(total_notes=5)
    assert sink.exists(make_edit()) is False


def test_exists_swallows_edam_exception():
    sink = _sink(dedup=True)
    sink._note_store = FakeNoteStore(raise_on_find=EDAMUserException())
    assert sink.exists(make_edit()) is False


class _NB:
    def __init__(self, name, guid):
        self.name = name
        self.guid = guid


def test_resolve_existing_notebook():
    sink = _sink(notebook="Wiki")
    sink._note_store = FakeNoteStore(notebooks=[_NB("Wiki", "g1")])
    assert sink._resolve_notebook() == "g1"


def test_resolve_creates_missing_notebook():
    sink = _sink(notebook="New One")
    sink._note_store = FakeNoteStore(notebooks=[_NB("Other", "g2")])
    assert sink._resolve_notebook() == "nb-guid"
    assert sink._note_store.created_notebooks


def test_no_notebook_returns_none():
    sink = _sink(notebook=None)
    assert sink._resolve_notebook() is None


def test_store_builds_thrift_clients(monkeypatch):
    class FakeUserStoreClient:
        def __init__(self, proto):
            pass

        def getNoteStoreUrl(self, token):
            return "https://shard.example/edam/note"

    class FakeNoteStoreClient:
        def __init__(self, proto):
            pass

    monkeypatch.setattr(ev.UserStore, "Client", FakeUserStoreClient)
    monkeypatch.setattr(ev.NoteStore, "Client", FakeNoteStoreClient)
    monkeypatch.setattr(ev.THttpClient, "THttpClient", lambda uri: ("http", uri))
    monkeypatch.setattr(ev.TBinaryProtocol, "TBinaryProtocol", lambda http: ("proto", http))

    store = _sink()._store()
    assert isinstance(store, FakeNoteStoreClient)
