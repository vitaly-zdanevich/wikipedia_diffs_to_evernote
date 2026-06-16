"""Sink registry.

To add a new export destination, implement a ``Sink`` subclass in its own module
and add ONE line to ``_BUILDERS`` below.
"""

from __future__ import annotations

from .base import Sink
from .evernote import EvernoteSink
from .notion import NotionSink
from .stdout import StdoutSink

# name -> builder(env, dedup) -> Sink
_BUILDERS = {
    EvernoteSink.name: EvernoteSink.from_env,
    NotionSink.name: NotionSink.from_env,
    StdoutSink.name: StdoutSink.from_env,
}


def build_sinks(targets: list[str], env, dedup: bool) -> list[Sink]:
    sinks: list[Sink] = []
    for name in targets:
        builder = _BUILDERS.get(name)
        if builder is None:
            known = ', '.join(sorted(_BUILDERS))
            raise SystemExit(f'Unknown export target {name!r}. Known targets: {known}.')
        sinks.append(builder(env, dedup))
    return sinks


__all__ = ['Sink', 'build_sinks']
