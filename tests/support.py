"""Shared test helpers and fakes (no network, no credentials)."""

from __future__ import annotations

from datetime import datetime, timezone

import requests

from wikisync.models import Edit

# A real MediaWiki ``compare`` body excerpt: a line-number header, a changed line
# (with inline del/ins), and a context line.
SAMPLE_ROWS = """
<tr>
  <td colspan="2" class="diff-lineno">Line 1:</td>
  <td colspan="2" class="diff-lineno">Line 1:</td>
</tr>
<tr>
  <td class="diff-marker" data-marker="−"></td>
  <td class="diff-deletedline diff-side-deleted"><div>foo <del class="diffchange diffchange-inline">old</del></div></td>
  <td class="diff-marker" data-marker="+"></td>
  <td class="diff-addedline diff-side-added"><div>foo <ins class="diffchange diffchange-inline">new</ins></div></td>
</tr>
<tr>
  <td class="diff-marker"></td>
  <td class="diff-context diff-side-deleted"><div>unchanged</div></td>
  <td class="diff-marker"></td>
  <td class="diff-context diff-side-added"><div>unchanged</div></td>
</tr>
"""


def make_edit(**kw) -> Edit:
    base = dict(
        host="en.wikipedia.org", username="Tester", revid=100, parentid=99,
        title="Test Page", timestamp=datetime(2026, 6, 12, 22, 0, tzinfo=timezone.utc),
        comment="a comment", sizediff=42, is_new=False, is_minor=False, is_top=True,
    )
    base.update(kw)
    return Edit(**base)


class FakeResp:
    """Stand-in for a requests.Response."""

    def __init__(self, json_data=None, status_code=200, text=""):
        self._json = {} if json_data is None else json_data
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._json


class FakeSession:
    """Returns queued FakeResp objects (a list) or computes one via callable(payload)."""

    def __init__(self, responses):
        self._responses = responses
        self.calls = []
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        self.calls.append(("GET", url, params))
        return self._next(params)

    def post(self, url, json=None, timeout=None):
        self.calls.append(("POST", url, json))
        return self._next(json)

    def _next(self, payload):
        if callable(self._responses):
            return self._responses(payload)
        return self._responses.pop(0)


class FakeNoteStore:
    """Stand-in for the Evernote Thrift NoteStore client."""

    def __init__(self, total_notes=0, notebooks=None, raise_on_find=None):
        self.created = []
        self.created_notebooks = []
        self.notebooks = list(notebooks or [])
        self.total_notes = total_notes
        self.raise_on_find = raise_on_find

    def createNote(self, token, note):
        self.created.append((token, note))
        return note

    def findNotesMetadata(self, token, note_filter, offset, max_notes, spec):
        if self.raise_on_find:
            raise self.raise_on_find

        class _Result:
            pass

        result = _Result()
        result.totalNotes = self.total_notes
        return result

    def listNotebooks(self, token):
        return self.notebooks

    def createNotebook(self, token, notebook):
        notebook.guid = "nb-guid"
        self.created_notebooks.append(notebook)
        self.notebooks.append(notebook)
        return notebook
