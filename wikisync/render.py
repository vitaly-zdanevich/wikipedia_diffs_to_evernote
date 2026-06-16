"""Shared rendering helpers reused by HTML- and text-based sinks.

MediaWiki's ``compare`` API returns a two-column diff as a run of ``<tr>`` rows
whose styling lives in external CSS. Note services strip ``class`` (Evernote's
ENML) or don't render arbitrary HTML at all (Notion), so we provide:

  * ``diff_rows_to_xhtml`` — inline-styled, ENML-safe XHTML (for HTML sinks).
  * ``diff_rows_to_text``  — a plain unified-style text diff (for text sinks).
  * ``format_title``       — the note title from a template.
"""

from __future__ import annotations

import logging
import re

from lxml import etree
from lxml import html as lhtml

from .models import Edit

log = logging.getLogger(__name__)

# Inline styles, keyed by the MediaWiki diff class found on a <td>.
_TD_STYLES = {
    'diff-lineno': 'color:#54595d;font-weight:bold;padding:6px 4px 2px;border-top:1px solid #eaecf0;',
    'diff-marker': 'width:1.4em;text-align:center;color:#777;font-weight:bold;vertical-align:top;padding:1px 2px;',
    'diff-deletedline': 'background:#ffe0e0;color:#202122;padding:1px 6px;vertical-align:top;',
    'diff-addedline': 'background:#d6f5d6;color:#202122;padding:1px 6px;vertical-align:top;',
    'diff-context': 'background:#ffffff;color:#202122;padding:1px 6px;vertical-align:top;',
    'diff-empty': 'background:#f8f9fa;padding:1px 6px;',
}
# Priority order: a changed line carries both diff-addedline/diff-deletedline and
# diff-side-*; check the specific classes before the generic context one.
_TD_PRIORITY = ('diff-lineno', 'diff-deletedline', 'diff-addedline', 'diff-context', 'diff-empty', 'diff-marker')

_INLINE_STYLES = {
    'del': 'background:#ffacac;text-decoration:none;',
    'ins': 'background:#8ef58e;text-decoration:none;',
}
_DIV_STYLE = 'margin:0;white-space:pre-wrap;word-break:break-word;'
_TABLE_STYLE = 'border-collapse:collapse;width:100%;font-family:monospace;font-size:12px;line-height:1.45;'

# Attributes ENML permits that we want to keep; everything else is dropped.
_KEEP_ATTRS = {'style', 'colspan', 'rowspan'}


def _classes(el) -> list[str]:
    return (el.get('class') or '').split()


def _style_element(el) -> None:
    """Apply the inline style for one diff element, based on its MediaWiki class."""
    classes = _classes(el)
    tag = el.tag.lower()
    if tag == 'td':
        # Preserve the +/- marker glyph that CSS would otherwise add.
        if 'diff-marker' in classes and el.get('data-marker'):
            el.text = el.get('data-marker')
        for key in _TD_PRIORITY:
            if key in classes:
                el.set('style', _TD_STYLES[key])
                break
    elif tag == 'div':
        el.set('style', _DIV_STYLE)
    elif tag in _INLINE_STYLES:
        el.set('style', _INLINE_STYLES[tag])


def _strip_foreign_attrs(el) -> None:
    """Remove every attribute ENML won't keep (class, data-*, ...)."""
    for attr in [a for a in el.attrib if a not in _KEEP_ATTRS]:
        del el.attrib[attr]


def diff_rows_to_xhtml(rows_html: str) -> str:
    """Convert a MediaWiki ``compare`` body into inline-styled, well-formed XHTML.

    The result is a ``<table>`` whose ``class``/``data-*`` attributes have been
    replaced with inline ``style`` (the only mechanism ENML keeps), serialized as
    XML so void elements are self-closed.
    """
    root = lhtml.fragment_fromstring(f'<table>{rows_html}</table>')
    for el in root.iter():
        if isinstance(el.tag, str):  # skip comments / processing instructions
            _style_element(el)
            _strip_foreign_attrs(el)
    root.set('style', _TABLE_STYLE)
    return etree.tostring(root, method='xml', encoding='unicode')


def _tds_with(tds: list, token: str) -> list:
    return [td for td in tds if token in _classes(td)]


def diff_rows_to_text(rows_html: str, max_lines: int = 400) -> str:
    """Render a MediaWiki ``compare`` body as a plain unified-style text diff."""
    root = lhtml.fragment_fromstring(f'<table>{rows_html}</table>')
    out: list[str] = []
    for tr in root.iter('tr'):
        tds = tr.findall('.//td')
        lineno = _tds_with(tds, 'diff-lineno')
        deleted = _tds_with(tds, 'diff-deletedline')
        added = _tds_with(tds, 'diff-addedline')
        context = _tds_with(tds, 'diff-context')

        if lineno:
            out.append(f'@@ {lineno[0].text_content().strip()} @@')
        for td in deleted:
            out.append('-' + td.text_content())
        for td in added:
            out.append('+' + td.text_content())
        if not (lineno or deleted or added) and context:
            out.append(' ' + context[0].text_content())

        if len(out) >= max_lines:
            out.append('… (diff truncated)')
            break
    return '\n'.join(out)


_WS = re.compile(r'\s+')


def format_title(edit: Edit, template: str) -> str:
    """Build a note title; always returns a non-empty string clamped to 255 chars."""
    try:
        title = template.format(
            title=edit.title,
            date=edit.timestamp,
            sizediff=edit.sizediff,
            revid=edit.revid,
            user=edit.username,
            host=edit.host,
            lang=edit.lang,
        )
    except Exception as exc:
        log.warning('Bad NOTE_TITLE_TEMPLATE (%s); using default.', exc)
        title = f'[{edit.lang}] {edit.title} ({edit.timestamp:%Y-%m-%d})'
    title = _WS.sub(' ', title).strip()[:255]
    return title or 'Wikipedia edit'
