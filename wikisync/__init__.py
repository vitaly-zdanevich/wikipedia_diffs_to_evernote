"""wikisync — sync a Wikipedia user's edits to note services (Evernote, Notion, ...).

Each edit becomes one note containing the page title, a clickable editor link,
the date, the byte-size change, a link to the diff on Wikipedia, and the diff itself.

The export destination is pluggable: see ``wikisync.sinks``.
"""

__version__ = "1.0.0"
