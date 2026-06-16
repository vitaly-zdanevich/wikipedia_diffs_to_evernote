"""Notion sink — one database page per edit (REST API, no SDK).

REFERENCE IMPLEMENTATION (not exercised in CI; verify against your workspace).
It demonstrates how little is needed to add a destination: read credentials in
``from_env``, optionally dedup in ``exists``, and create the record in ``export``.

Expects a Notion database shared with your integration, with these properties:
    Name (title) · Editor (rich_text) · Date (date) · Size (number) · Diff URL (url)

Set NOTION_TOKEN (integration secret) and NOTION_DATABASE_ID, and add "notion"
to EXPORT_TARGETS.
"""

from __future__ import annotations

import logging

import requests

from .. import render
from ..models import DiffContent, Edit
from .base import Sink

log = logging.getLogger(__name__)

_NOTION_VERSION = '2022-06-28'
_CODE_CHUNK = 1900  # Notion rich_text hard limit is 2000 chars per item.


class NotionSink(Sink):
    name = 'notion'

    def __init__(self, token: str, database_id: str, dedup: bool = True):
        self.database_id = database_id
        self.dedup = dedup
        self.session = requests.Session()
        self.session.headers.update(
            {
                'Authorization': f'Bearer {token}',
                'Notion-Version': _NOTION_VERSION,
                'Content-Type': 'application/json',
            }
        )

    @classmethod
    def from_env(cls, env, dedup):
        token = (env.get('NOTION_TOKEN') or '').strip()
        database_id = (env.get('NOTION_DATABASE_ID') or '').strip()
        if not token or not database_id:
            raise SystemExit("NOTION_TOKEN and NOTION_DATABASE_ID are required for the 'notion' sink.")
        return cls(token, database_id, dedup)

    def exists(self, edit: Edit) -> bool:
        if not self.dedup:
            return False
        resp = self.session.post(
            f'https://api.notion.com/v1/databases/{self.database_id}/query',
            json={'filter': {'property': 'Diff URL', 'url': {'equals': edit.diff_url}}, 'page_size': 1},
            timeout=30,
        )
        if resp.status_code != 200:
            log.warning('Notion dedup query failed (%s); will create anyway.', resp.status_code)
            return False
        return bool(resp.json().get('results'))

    def export(self, edit: Edit, diff: DiffContent, title: str) -> None:
        children = [
            {
                'object': 'block',
                'type': 'paragraph',
                'paragraph': {
                    'rich_text': [
                        {'type': 'text', 'text': {'content': 'View diff on Wikipedia', 'link': {'url': edit.diff_url}}}
                    ]
                },
            }
        ]
        children += self._diff_blocks(diff)

        payload = {
            'parent': {'database_id': self.database_id},
            'properties': {
                'Name': {'title': [{'text': {'content': title[:2000]}}]},
                'Editor': {
                    'rich_text': [{'text': {'content': edit.username, 'link': {'url': edit.user_contribs_url}}}]
                },
                'Date': {'date': {'start': edit.timestamp.isoformat()}},
                'Size': {'number': edit.sizediff},
                'Diff URL': {'url': edit.diff_url},
            },
            'children': children,
        }
        resp = self.session.post('https://api.notion.com/v1/pages', json=payload, timeout=30)
        if resp.status_code >= 300:
            raise RuntimeError(f'Notion createPage failed: {resp.status_code} {resp.text[:300]}')

    def _diff_blocks(self, diff: DiffContent) -> list[dict]:
        if diff.kind == 'diff' and diff.html:
            text = render.diff_rows_to_text(diff.html)
        elif diff.kind == 'newpage' and diff.html:
            text = diff.html
        else:
            text = '(diff unavailable — use the link above)'
        return [self._code_block(chunk) for chunk in _chunks(text, _CODE_CHUNK)] or [self._code_block('')]

    @staticmethod
    def _code_block(content: str) -> dict:
        return {
            'object': 'block',
            'type': 'code',
            'code': {'language': 'diff', 'rich_text': [{'type': 'text', 'text': {'content': content}}]},
        }


def _chunks(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] if text else []
