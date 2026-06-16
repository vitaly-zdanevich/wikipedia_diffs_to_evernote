"""Tests for the MediaWiki client (HTTP mocked)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import requests

from wikisync import wikipedia as wp
from wikisync.wikipedia import Wikipedia
from tests.support import FakeResp, FakeSession, make_edit


def _uc(revid, parentid, ts, **extra):
    item = dict(user="Tester", revid=revid, parentid=parentid, ns=0,
                title="P", timestamp=ts, comment="c", sizediff=1)
    item.update(extra)
    return item


def _wiki(responses):
    return Wikipedia("en.wikipedia.org", "ua/1.0", session=FakeSession(responses))


def test_iter_paginates_across_continue():
    page1 = {"query": {"usercontribs": [_uc(10, 9, "2026-06-10T00:00:00Z"),
                                        _uc(9, 8, "2026-06-09T00:00:00Z")]},
             "continue": {"uccontinue": "TOKEN"}}
    page2 = {"query": {"usercontribs": [_uc(8, 7, "2026-06-08T00:00:00Z")]}}
    edits = list(_wiki([FakeResp(page1), FakeResp(page2)]).iter_contributions("Tester"))
    assert [e.revid for e in edits] == [10, 9, 8]


def test_iter_stops_at_since_revid():
    page = {"query": {"usercontribs": [_uc(10, 9, "2026-06-10T00:00:00Z"),
                                       _uc(9, 8, "2026-06-09T00:00:00Z"),
                                       _uc(8, 7, "2026-06-08T00:00:00Z")]}}
    edits = list(_wiki([FakeResp(page)]).iter_contributions("Tester", since_revid=9))
    assert [e.revid for e in edits] == [10]


def test_iter_stops_at_cutoff():
    page = {"query": {"usercontribs": [_uc(10, 9, "2026-06-10T00:00:00Z"),
                                       _uc(9, 8, "2026-06-01T00:00:00Z")]}}
    cutoff = datetime(2026, 6, 5, tzinfo=timezone.utc)
    edits = list(_wiki([FakeResp(page)]).iter_contributions("Tester", cutoff=cutoff))
    assert [e.revid for e in edits] == [10]


def test_iter_respects_hard_cap(monkeypatch):
    monkeypatch.setattr(wp, "_HARD_CAP", 2)
    page = {"query": {"usercontribs": [_uc(10, 9, "2026-06-10T00:00:00Z"),
                                       _uc(9, 8, "2026-06-09T00:00:00Z"),
                                       _uc(8, 7, "2026-06-08T00:00:00Z")]}}
    edits = list(_wiki([FakeResp(page)]).iter_contributions("Tester"))
    assert len(edits) == 2


def test_get_raises_on_api_error():
    with pytest.raises(RuntimeError):
        list(_wiki([FakeResp({"error": {"code": "x", "info": "bad"}})]).iter_contributions("Tester"))


def test_fetch_diff_with_parent():
    body = "<tr><td>x</td></tr>"
    diff = _wiki([FakeResp({"compare": {"body": body}})]).fetch_diff(make_edit(parentid=99, is_new=False))
    assert diff.kind == "diff" and diff.html == body


def test_fetch_diff_empty_body_is_unavailable():
    diff = _wiki([FakeResp({"compare": {}})]).fetch_diff(make_edit(parentid=99))
    assert diff.kind == "unavailable"


def test_fetch_diff_new_page():
    diff = _wiki([FakeResp({"parse": {"wikitext": "== Heading =="}})]).fetch_diff(
        make_edit(parentid=0, is_new=True))
    assert diff.kind == "newpage" and "Heading" in diff.html


def test_fetch_diff_unavailable_on_network_error():
    class Boom(FakeSession):
        def get(self, *a, **k):
            raise requests.ConnectionError("boom")

    w = Wikipedia("h", "ua", session=Boom([]))
    assert w.fetch_diff(make_edit()).kind == "unavailable"
