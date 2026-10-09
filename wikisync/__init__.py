"""wikisync — sync a Wikipedia user's edits to note services (Evernote, Notion, ...).

Each edit becomes one note containing the page title, the byte-size change,
and the diff itself. Evernote stores the revision URL in the note's metadata.

The export destination is pluggable: see ``wikisync.sinks``.
"""

__version__ = '1.0.2'
