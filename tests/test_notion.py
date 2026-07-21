"""Tests for the Notion sink (HTTP mocked)."""

from __future__ import annotations

import pytest

from tests.support import SAMPLE_ROWS, FakeResp, FakeSession, make_edit
from wikisync.models import DiffContent
from wikisync.sinks.notion import NotionSink, _chunks


def _sink(responses, dedup=True):
    sink = NotionSink(token='t', database_id='db', dedup=dedup)
    sink.session = FakeSession(responses)
    return sink


def test_from_env_requires_both():
    with pytest.raises(SystemExit):
        NotionSink.from_env({'NOTION_TOKEN': 't'}, True)
    with pytest.raises(SystemExit):
        NotionSink.from_env({'NOTION_DATABASE_ID': 'd'}, True)
    sink = NotionSink.from_env({'NOTION_TOKEN': 't', 'NOTION_DATABASE_ID': 'd'}, True)
    assert sink.database_id == 'd'


def test_exists_true_false_and_error():
    edit = make_edit(title='AT&T')
    found = _sink([FakeResp({'results': [{'id': 'x'}]})])
    assert found.exists(edit) is True
    filters = found.session.calls[0][2]['filter']['or']
    assert [item['url']['equals'] for item in filters] == list(edit.dedup_urls)
    assert _sink([FakeResp({'results': []})]).exists(make_edit()) is False
    assert _sink([FakeResp({}, status_code=400, text='bad')]).exists(make_edit()) is False


def test_exists_disabled_makes_no_call():
    sink = _sink([], dedup=False)
    assert sink.exists(make_edit()) is False
    assert sink.session.calls == []


def test_export_posts_page():
    sink = _sink([FakeResp({'id': 'page1'}, status_code=200)])
    sink.export(make_edit(), DiffContent('diff', SAMPLE_ROWS), 'Title')

    method, url, payload = sink.session.calls[-1]
    assert method == 'POST' and url.endswith('/v1/pages')
    assert payload['properties']['Name']['title'][0]['text']['content'] == 'Title'
    assert payload['properties']['Diff URL']['url'].startswith('https://')
    assert payload['children']  # at least the link block + code block(s)


def test_export_new_page_links_created_revision():
    sink = _sink([FakeResp({'id': 'page1'}, status_code=200)])
    edit = make_edit(revid=77, parentid=0, is_new=True)
    sink.export(edit, DiffContent('newpage', 'created'), 'Title')

    link = sink.session.calls[-1][2]['children'][0]['paragraph']['rich_text'][0]['text']
    assert link == {
        'content': 'View revision on Wikipedia',
        'link': {'url': 'https://en.wikipedia.org/w/index.php?oldid=77'},
    }


def test_export_raises_on_api_error():
    sink = _sink([FakeResp({}, status_code=500, text='err')])
    with pytest.raises(RuntimeError):
        sink.export(make_edit(), DiffContent('unavailable'), 'T')


def test_diff_blocks_chunk_long_text():
    sink = _sink([])
    blocks = sink._diff_blocks(DiffContent('newpage', 'x' * 4000))
    assert blocks and all(b['type'] == 'code' for b in blocks)
    assert len(blocks) >= 3  # 4000 chars / 1900-char chunks


def test_diff_blocks_unavailable():
    sink = _sink([])
    blocks = sink._diff_blocks(DiffContent('unavailable'))
    assert blocks[0]['code']['rich_text'][0]['text']['content'].startswith('(diff unavailable')


def test_chunks_helper():
    assert _chunks('', 5) == []
    assert _chunks('abcdef', 2) == ['ab', 'cd', 'ef']
