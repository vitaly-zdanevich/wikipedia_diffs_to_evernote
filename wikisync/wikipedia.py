"""Thin MediaWiki API client: list a user's contributions and fetch diffs.

No authentication required. Uses formatversion=2 for clean JSON shapes.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime

import requests

from .models import DiffContent, Edit

log = logging.getLogger(__name__)

# Safety valve: never page through more than this many contributions in one run.
_HARD_CAP = 5000
_PAGE_SIZE = 500


def _past_boundary(edit: Edit, since_revid: int | None, cutoff: datetime | None) -> bool:
    """True once a newest-first scan has passed the caller's stop conditions."""
    if since_revid is not None and edit.revid <= since_revid:
        return True
    return cutoff is not None and edit.timestamp < cutoff


class Wikipedia:
    def __init__(self, host: str, user_agent: str, session: requests.Session | None = None, timeout: int = 30):
        self.host = host
        self.api_url = f'https://{host}/w/api.php'
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({'User-Agent': user_agent})

    def _get(self, params: dict) -> dict:
        params = {**params, 'format': 'json', 'formatversion': '2'}
        resp = self.session.get(self.api_url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        if 'error' in data:
            raise RuntimeError(f'MediaWiki API error: {data["error"]}')
        return data

    def iter_contributions(
        self,
        username: str,
        since_revid: int | None = None,
        cutoff: datetime | None = None,
    ) -> Iterator[Edit]:
        """Yield the user's edits newest-first.

        Stops at (and excludes) ``since_revid``, or once edits are older than
        ``cutoff``, or after the hard cap. The caller decides ordering/batching.
        """
        for item in self._iter_raw_contributions(username):
            edit = Edit.from_api(item, self.host)
            if _past_boundary(edit, since_revid, cutoff):
                return
            yield edit

    def _iter_raw_contributions(self, username: str) -> Iterator[dict]:
        """Page through raw usercontribs items, newest-first, bounded by the hard cap."""
        params = {
            'action': 'query',
            'list': 'usercontribs',
            'ucuser': username,
            'ucprop': 'ids|title|timestamp|comment|sizediff|flags',
            'uclimit': str(_PAGE_SIZE),
        }
        seen = 0
        uccontinue: str | None = None
        while True:
            page_params = dict(params)
            if uccontinue:
                page_params['uccontinue'] = uccontinue
            data = self._get(page_params)
            for item in data.get('query', {}).get('usercontribs', []):
                yield item
                seen += 1
                if seen >= _HARD_CAP:
                    log.warning('Hit hard cap of %d contributions; stopping pagination.', _HARD_CAP)
                    return
            cont = data.get('continue')
            uccontinue = cont.get('uccontinue') if cont else None
            if not uccontinue:
                return

    def fetch_diff(self, edit: Edit) -> DiffContent:
        """Fetch the change for an edit. Never raises — degrades to 'unavailable'."""
        try:
            if edit.parentid and not edit.is_new:
                data = self._get(
                    {
                        'action': 'compare',
                        'fromrev': edit.parentid,
                        'torev': edit.revid,
                        'prop': 'diff',
                    }
                )
                body = data.get('compare', {}).get('body')
                return DiffContent('diff', body) if body else DiffContent('unavailable')

            # New page (no parent revision): show the created wikitext as added content.
            data = self._get(
                {
                    'action': 'parse',
                    'oldid': edit.revid,
                    'prop': 'wikitext',
                }
            )
            wikitext = data.get('parse', {}).get('wikitext')
            return DiffContent('newpage', wikitext) if wikitext else DiffContent('unavailable')
        except Exception as exc:  # network / API hiccup must not abort the run
            log.warning('Could not fetch diff for revid %s (%s): %s', edit.revid, edit.title, exc)
            return DiffContent('unavailable')
