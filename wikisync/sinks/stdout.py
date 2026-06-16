"""Stdout sink — prints each edit instead of exporting it.

Needs no credentials, so it's handy for a local dry run:
    EXPORT_TARGETS=stdout WIKIPEDIA_USERNAME=Jimbo_Wales python -m wikisync
It also doubles as the minimal example of how small a Sink can be.
"""

from __future__ import annotations

from .. import render
from ..models import DiffContent, Edit
from .base import Sink


class StdoutSink(Sink):
    name = 'stdout'

    @classmethod
    def from_env(cls, env, dedup):
        return cls()

    def export(self, edit: Edit, diff: DiffContent, title: str) -> None:
        print('=' * 80)
        print(f'TITLE : {title}')
        print(f'PAGE  : {edit.title}  ({edit.page_url})')
        print(f'EDITOR: {edit.username}  ({edit.user_contribs_url})')
        print(f'DATE  : {edit.timestamp:%Y-%m-%d %H:%M UTC}')
        print(f'SIZE  : {edit.sizediff:+d} bytes' + ('  [new page]' if edit.is_new else ''))
        print(f'DIFF  : {edit.diff_url}')
        if edit.comment:
            print(f'SUMMARY: {edit.comment}')
        print('-' * 80)
        if diff.kind == 'diff' and diff.html:
            print(render.diff_rows_to_text(diff.html, max_lines=60))
        elif diff.kind == 'newpage' and diff.html:
            print(diff.html[:2000])
        else:
            print('(diff unavailable)')
