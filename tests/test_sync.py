"""Tests for the orchestrator (Wikipedia + sinks mocked)."""

from __future__ import annotations

from tests.support import make_edit
from wikisync import state, sync
from wikisync.config import Config
from wikisync.models import DiffContent


class FakeWiki:
    edits_by_host: dict = {}

    def __init__(self, host, user_agent):
        self.host = host

    def iter_contributions(self, username, since_revid=None, cutoff=None):
        return list(FakeWiki.edits_by_host.get(self.host, []))

    def fetch_diff(self, edit):
        return DiffContent('diff', '<tr><td>x</td></tr>')


class RecordingSink:
    name = 'rec'

    def __init__(self):
        self.exported = []
        self.exists_returns = False
        self.fail_on = set()

    def exists(self, edit):
        return self.exists_returns

    def export(self, edit, diff, title):
        if edit.revid in self.fail_on:
            raise RuntimeError('boom')
        self.exported.append((edit.revid, title))


def _cfg(tmp_path, hosts=('en.wikipedia.org',), max_edits=50, dedup=True):
    return Config(
        username='Tester',
        hosts=list(hosts),
        targets=['rec'],
        dedup=dedup,
        max_edits=max_edits,
        first_run_lookback_days=7,
        state_file=str(tmp_path / 'state.json'),
        user_agent='ua',
        note_title_template='{title}',
        log_level='INFO',
    )


def _patch(monkeypatch, sink, edits_by_host):
    FakeWiki.edits_by_host = edits_by_host
    monkeypatch.setattr(sync, 'Wikipedia', FakeWiki)
    monkeypatch.setattr(sync, 'build_sinks', lambda targets, env, dedup: [sink])


def test_run_creates_notes_and_saves_state(tmp_path, monkeypatch):
    sink = RecordingSink()
    edits = [make_edit(revid=10, parentid=9), make_edit(revid=11, parentid=10)]
    _patch(monkeypatch, sink, {'en.wikipedia.org': edits})
    cfg = _cfg(tmp_path)

    assert sync.run(cfg, {}) == 0
    assert sorted(r for r, _ in sink.exported) == [10, 11]
    st = state.load(cfg.state_file)
    assert state.get(st, 'en.wikipedia.org', 'Tester')[0] == 11


def test_run_no_edits(tmp_path, monkeypatch):
    sink = RecordingSink()
    _patch(monkeypatch, sink, {'en.wikipedia.org': []})
    assert sync.run(_cfg(tmp_path), {}) == 0
    assert sink.exported == []


def test_run_dedup_skips_but_advances_state(tmp_path, monkeypatch):
    sink = RecordingSink()
    sink.exists_returns = True
    _patch(monkeypatch, sink, {'en.wikipedia.org': [make_edit(revid=10)]})
    cfg = _cfg(tmp_path)

    assert sync.run(cfg, {}) == 0
    assert sink.exported == []
    assert state.get(state.load(cfg.state_file), 'en.wikipedia.org', 'Tester')[0] == 10


def test_run_failure_blocks_highwater(tmp_path, monkeypatch):
    sink = RecordingSink()
    sink.fail_on = {11}
    edits = [make_edit(revid=r, parentid=r - 1) for r in (10, 11, 12)]
    _patch(monkeypatch, sink, {'en.wikipedia.org': edits})
    cfg = _cfg(tmp_path)

    assert sync.run(cfg, {}) == 1
    # 10 succeeded, 11 failed (blocks), 12 still attempted
    assert 10 in [r for r, _ in sink.exported]
    assert state.get(state.load(cfg.state_file), 'en.wikipedia.org', 'Tester')[0] == 10


def test_run_caps_batch_to_max_edits(tmp_path, monkeypatch):
    sink = RecordingSink()
    edits = [make_edit(revid=r, parentid=r - 1) for r in (10, 11, 12, 13, 14)]
    _patch(monkeypatch, sink, {'en.wikipedia.org': edits})
    cfg = _cfg(tmp_path, max_edits=2)

    sync.run(cfg, {})
    assert sorted(r for r, _ in sink.exported) == [10, 11]  # oldest two
    assert state.get(state.load(cfg.state_file), 'en.wikipedia.org', 'Tester')[0] == 11


def test_run_multi_host_independent_state(tmp_path, monkeypatch):
    sink = RecordingSink()
    _patch(
        monkeypatch,
        sink,
        {
            'en.wikipedia.org': [make_edit(revid=10, host='en.wikipedia.org')],
            'ru.wikipedia.org': [make_edit(revid=20, host='ru.wikipedia.org')],
        },
    )
    cfg = _cfg(tmp_path, hosts=('en.wikipedia.org', 'ru.wikipedia.org'))

    sync.run(cfg, {})
    st = state.load(cfg.state_file)
    assert state.get(st, 'en.wikipedia.org', 'Tester')[0] == 10
    assert state.get(st, 'ru.wikipedia.org', 'Tester')[0] == 20
    assert len(sink.exported) == 2
