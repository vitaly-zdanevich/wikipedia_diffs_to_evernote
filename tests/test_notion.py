"""Tests for the Notion sink (HTTP mocked)."""

from __future__ import annotations

import pytest

from wikisync.sinks.notion import NotionSink, _chunks
from wikisync.models import DiffContent
from tests.support import FakeResp, FakeSession, SAMPLE_ROWS, make_edit


def _sink(responses, dedup=True):
    sink = NotionSink(token="t", database_id="db", dedup=dedup)
    sink.session = FakeSession(responses)
    return sink


def test_from_env_requires_both():
    with pytest.raises(SystemExit):
        NotionSink.from_env({"NOTION_TOKEN": "t"}, True)
    with pytest.raises(SystemExit):
        NotionSink.from_env({"NOTION_DATABASE_ID": "d"}, True)
    sink = NotionSink.from_env({"NOTION_TOKEN": "t", "NOTION_DATABASE_ID": "d"}, True)
    assert sink.database_id == "d"


def test_exists_true_false_and_error():
    assert _sink([FakeResp({"results": [{"id": "x"}]})]).exists(make_edit()) is True
    assert _sink([FakeResp({"results": []})]).exists(make_edit()) is False
    assert _sink([FakeResp({}, status_code=400, text="bad")]).exists(make_edit()) is False


def test_exists_disabled_makes_no_call():
    sink = _sink([], dedup=False)
    assert sink.exists(make_edit()) is False
    assert sink.session.calls == []


def test_export_posts_page():
    sink = _sink([FakeResp({"id": "page1"}, status_code=200)])
    sink.export(make_edit(), DiffContent("diff", SAMPLE_ROWS), "Title")

    method, url, payload = sink.session.calls[-1]
    assert method == "POST" and url.endswith("/v1/pages")
    assert payload["properties"]["Name"]["title"][0]["text"]["content"] == "Title"
    assert payload["properties"]["Diff URL"]["url"].startswith("https://")
    assert payload["children"]  # at least the link block + code block(s)


def test_export_raises_on_api_error():
    sink = _sink([FakeResp({}, status_code=500, text="err")])
    with pytest.raises(RuntimeError):
        sink.export(make_edit(), DiffContent("unavailable"), "T")


def test_diff_blocks_chunk_long_text():
    sink = _sink([])
    blocks = sink._diff_blocks(DiffContent("newpage", "x" * 4000))
    assert blocks and all(b["type"] == "code" for b in blocks)
    assert len(blocks) >= 3  # 4000 chars / 1900-char chunks


def test_diff_blocks_unavailable():
    sink = _sink([])
    blocks = sink._diff_blocks(DiffContent("unavailable"))
    assert blocks[0]["code"]["rich_text"][0]["text"]["content"].startswith("(diff unavailable")


def test_chunks_helper():
    assert _chunks("", 5) == []
    assert _chunks("abcdef", 2) == ["ab", "cd", "ef"]
