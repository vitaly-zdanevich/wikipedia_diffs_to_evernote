"""Tests for the module entry point."""

from __future__ import annotations

import pytest

from wikisync import __main__


def test_main_builds_config_and_calls_run(monkeypatch):
    captured = {}
    monkeypatch.setenv('WIKIPEDIA_USERNAME', 'Tester')
    monkeypatch.setenv('EXPORT_TARGETS', 'stdout')
    monkeypatch.setenv('WIKIPEDIA_LANG', 'en,ru')

    def fake_run(config, env):
        captured['config'] = config
        return 0

    monkeypatch.setattr(__main__, 'run', fake_run)

    with pytest.raises(SystemExit) as exc:
        __main__.main()

    assert exc.value.code == 0
    assert captured['config'].username == 'Tester'
    assert captured['config'].hosts == ['en.wikipedia.org', 'ru.wikipedia.org']
