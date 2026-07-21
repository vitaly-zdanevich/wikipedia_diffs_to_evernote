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
from copy import deepcopy

from lxml import etree
from lxml import html as lhtml

from .models import Edit

log = logging.getLogger(__name__)

_INLINE_STYLES = {
    'del': 'background:#ffacac;text-decoration:none;',
    'ins': 'background:#8ef58e;text-decoration:none;',
}
_DIFF_STYLE = 'font-family:monospace;font-size:12px;line-height:1.45;'
_LINE_BASE_STYLE = 'margin:0;padding:1px 6px;white-space:pre-wrap;word-break:break-word;'
_LINE_STYLES = {
    'header': 'margin:0;color:#54595d;font-weight:bold;padding:6px 4px 2px;',
    'deleted': _LINE_BASE_STYLE + 'background:#ffe0e0;color:#202122;',
    'added': _LINE_BASE_STYLE + 'background:#d6f5d6;color:#202122;',
    'context': _LINE_BASE_STYLE + 'background:#ffffff;color:#202122;',
}
_MARKER_STYLE = 'display:inline-block;width:1.4em;color:#777777;font-weight:bold;vertical-align:top;'

# Attributes ENML permits that we want to keep; everything else is dropped.
_KEEP_ATTRS = {'style'}


def _classes(el) -> list[str]:
    return (el.get('class') or '').split()


def _strip_foreign_attrs(el) -> None:
    """Remove every attribute ENML won't keep (class, data-*, ...)."""
    for attr in [a for a in el.attrib if a not in _KEEP_ATTRS]:
        del el.attrib[attr]


def _cell_content(td):
    """Return the inline content wrapper inside a MediaWiki diff cell."""
    children = [child for child in td if isinstance(child.tag, str)]
    if len(children) == 1 and children[0].tag.lower() == 'div' and not (td.text or '').strip():
        return children[0]
    return td


def _append_cell_content(target, td) -> None:
    """Copy a cell's contents without its block-level wrapper."""
    source = _cell_content(td)
    target.text = source.text
    for child in source:
        target.append(deepcopy(child))


def _append_diff_line(root, td, kind: str, marker: str) -> None:
    line = etree.SubElement(root, 'div', style=_LINE_STYLES[kind])
    marker_el = etree.SubElement(line, 'span', style=_MARKER_STYLE)
    marker_el.text = marker
    content = etree.SubElement(line, 'span')
    _append_cell_content(content, td)


def _append_header(root, cells: list) -> None:
    labels = list(dict.fromkeys(cell.text_content().strip() for cell in cells))
    header = etree.SubElement(root, 'div', style=_LINE_STYLES['header'])
    header.text = '@@ ' + ' → '.join(labels) + ' @@'


def diff_rows_to_xhtml(rows_html: str) -> str:
    """Convert a MediaWiki ``compare`` body into inline-styled, well-formed XHTML.

    MediaWiki's duplicated left/right cells become a unified, single-column
    sequence of removed, added, and context lines. The result uses inline styles
    (the mechanism ENML keeps) and is serialized as well-formed XML.
    """
    table = lhtml.fragment_fromstring(f'<table>{rows_html}</table>')
    root = etree.Element('div', style=_DIFF_STYLE)
    for tr in table.iter('tr'):
        cells = tr.findall('./td')
        headers = _tds_with(cells, 'diff-lineno')
        deleted = _tds_with(cells, 'diff-deletedline')
        added = _tds_with(cells, 'diff-addedline')
        context = _tds_with(cells, 'diff-context')

        if headers:
            _append_header(root, headers)
        for td in deleted:
            _append_diff_line(root, td, 'deleted', '−')
        for td in added:
            _append_diff_line(root, td, 'added', '+')
        if not (headers or deleted or added) and context:
            _append_diff_line(root, context[0], 'context', ' ')

    for el in root.iter():
        if isinstance(el.tag, str):  # skip comments / processing instructions
            tag = el.tag.lower()
            if tag in _INLINE_STYLES:
                el.set('style', _INLINE_STYLES[tag])
            _strip_foreign_attrs(el)
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
        title = f'[{edit.lang}] {edit.title} ({edit.sizediff:+d} B)'
    title = _WS.sub(' ', title).strip()[:255]
    return title or 'Wikipedia edit'
