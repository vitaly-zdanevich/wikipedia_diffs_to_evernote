"""Evernote sink — one note per edit via the Evernote Cloud API.

Authenticates with a *developer token* (Premium accounts can mint one), so there
is no interactive OAuth at runtime. We drive the generated Thrift ``NoteStore``
client directly, which avoids the SDK's ``oauth2`` dependency and works on
modern Python.
"""

from __future__ import annotations

import logging
from xml.sax.saxutils import escape, quoteattr

import thrift.protocol.TBinaryProtocol as TBinaryProtocol
import thrift.transport.THttpClient as THttpClient
from evernote.edam.error.ttypes import EDAMUserException
from evernote.edam.notestore import NoteStore
from evernote.edam.notestore.ttypes import NoteFilter, NotesMetadataResultSpec
from evernote.edam.type.ttypes import Note, NoteAttributes, Notebook
from evernote.edam.userstore import UserStore

from .. import render
from ..config import env_bool
from ..models import DiffContent, Edit
from .base import Sink

log = logging.getLogger(__name__)

_ENML_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">\n'
)
# Keep notes comfortably under Evernote's 5 MB ENML limit.
_MAX_DIFF_CHARS = 400_000


def _esc(text: str) -> str:
    return escape(text or "")


def _attr(value: str) -> str:
    # quoteattr returns the value *with* surrounding quotes, XML-escaped.
    return quoteattr(value or "")


class EvernoteSink(Sink):
    name = "evernote"

    def __init__(self, token, notebook=None, service_host="www.evernote.com", dedup=True, tags=None):
        self.token = token
        self.notebook_name = notebook
        self.service_host = service_host
        self.dedup = dedup
        self.tags = tags or []
        self._note_store = None
        self._notebook_guid = None

    @classmethod
    def from_env(cls, env, dedup):
        token = (env.get("EVERNOTE_DEV_TOKEN") or "").strip()
        if not token:
            raise SystemExit("EVERNOTE_DEV_TOKEN is required for the 'evernote' sink.")
        if env_bool(env.get("EVERNOTE_SANDBOX")):
            service_host = "sandbox.evernote.com"
        else:
            service_host = (env.get("EVERNOTE_SERVICE_HOST") or "www.evernote.com").strip()
        tags = [t.strip() for t in (env.get("EVERNOTE_TAGS") or "").split(",") if t.strip()]
        return cls(
            token=token,
            notebook=(env.get("EVERNOTE_NOTEBOOK") or "").strip() or None,
            service_host=service_host,
            dedup=dedup,
            tags=tags,
        )

    # --- Thrift plumbing --------------------------------------------------
    def _store(self) -> "NoteStore.Client":
        if self._note_store is None:
            user_store_uri = f"https://{self.service_host}/edam/user"
            user_store = UserStore.Client(
                TBinaryProtocol.TBinaryProtocol(THttpClient.THttpClient(user_store_uri))
            )
            note_store_url = user_store.getNoteStoreUrl(self.token)
            self._note_store = NoteStore.Client(
                TBinaryProtocol.TBinaryProtocol(THttpClient.THttpClient(note_store_url))
            )
        return self._note_store

    def _resolve_notebook(self) -> str | None:
        if self.notebook_name is None:
            return None
        if self._notebook_guid is None:
            store = self._store()
            for notebook in store.listNotebooks(self.token):
                if notebook.name == self.notebook_name:
                    self._notebook_guid = notebook.guid
                    break
            else:
                created = store.createNotebook(self.token, Notebook(name=self.notebook_name))
                self._notebook_guid = created.guid
                log.info("Created Evernote notebook %r", self.notebook_name)
        return self._notebook_guid

    # --- Sink API ---------------------------------------------------------
    def exists(self, edit: Edit) -> bool:
        if not self.dedup:
            return False
        try:
            note_filter = NoteFilter(words=f'sourceURL:"{edit.diff_url}"')
            result = self._store().findNotesMetadata(
                self.token, note_filter, 0, 1, NotesMetadataResultSpec(includeTitle=False)
            )
            return (result.totalNotes or 0) > 0
        except EDAMUserException as exc:
            log.warning("Evernote dedup search failed (%s); will create anyway.", exc)
            return False

    def export(self, edit: Edit, diff: DiffContent, title: str) -> None:
        note = Note()
        note.title = title
        note.content = self._build_enml(edit, diff)
        attributes = NoteAttributes()
        attributes.sourceURL = edit.diff_url
        attributes.sourceApplication = "diffs_to_evernote"
        note.attributes = attributes
        notebook_guid = self._resolve_notebook()
        if notebook_guid:
            note.notebookGuid = notebook_guid
        if self.tags:
            note.tagNames = list(self.tags)
        self._store().createNote(self.token, note)

    # --- ENML construction ------------------------------------------------
    def _build_enml(self, edit: Edit, diff: DiffContent) -> str:
        sign_color = "#187a18" if edit.sizediff > 0 else ("#a11111" if edit.sizediff < 0 else "#555555")
        flags = []
        if edit.is_new:
            flags.append("new page")
        if edit.is_minor:
            flags.append("minor")
        flag_text = f" · {', '.join(flags)}" if flags else ""

        parts = [
            f'<div style="font-size:15px;margin-bottom:6px;">'
            f'<b><a href={_attr(edit.page_url)}>{_esc(edit.title)}</a></b></div>',
            '<div style="margin-bottom:4px;">'
            f'Editor: <a href={_attr(edit.user_contribs_url)}>{_esc(edit.username)}</a> · '
            f'{_esc(edit.timestamp.strftime("%Y-%m-%d %H:%M UTC"))} · '
            f'<span style="color:{sign_color};font-weight:bold;">{edit.sizediff:+d} bytes</span>'
            f'{_esc(flag_text)}</div>',
        ]
        if edit.comment:
            parts.append(
                f'<div style="margin-bottom:4px;color:#444444;">Summary: <i>{_esc(edit.comment)}</i></div>'
            )
        parts.append(
            f'<div style="margin-bottom:8px;"><a href={_attr(edit.diff_url)}>View diff on Wikipedia →</a></div>'
        )
        parts.append('<hr/>')
        parts.append(self._render_diff(diff))
        return _ENML_HEADER + "<en-note>" + "".join(parts) + "</en-note>"

    def _render_diff(self, diff: DiffContent) -> str:
        if diff.kind == "diff" and diff.html:
            try:
                xhtml = render.diff_rows_to_xhtml(diff.html)
            except Exception as exc:
                log.warning("Diff render failed (%s); linking instead.", exc)
                return '<div><i>Diff could not be rendered inline — use the link above.</i></div>'
            if len(xhtml) > _MAX_DIFF_CHARS:
                return '<div><i>Diff is too large to embed — use the link above to view it.</i></div>'
            return xhtml
        if diff.kind == "newpage" and diff.html:
            text = diff.html
            if len(text) > _MAX_DIFF_CHARS:
                text = text[:_MAX_DIFF_CHARS] + "\n… (truncated)"
            return (
                '<div style="background:#d6f5d6;border:1px solid #b5e6b5;padding:6px;'
                'white-space:pre-wrap;word-break:break-word;font-family:monospace;font-size:12px;">'
                f'{_esc(text)}</div>'
            )
        return '<div><i>Diff unavailable — use the link above to view it on Wikipedia.</i></div>'
