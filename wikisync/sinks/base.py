"""The export-destination interface.

Add a new destination (Notion, OneNote, a Markdown repo, a database, ...) by:

  1. Creating ``wikisync/sinks/<name>.py`` with a ``Sink`` subclass.
  2. Implementing ``from_env``, ``export``, and (optionally) ``exists``.
  3. Registering it in ``wikisync/sinks/__init__.py`` (one line).

That's the whole contract — the core pipeline knows nothing destination-specific.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import DiffContent, Edit


class Sink(ABC):
    #: Short identifier used in ``EXPORT_TARGETS`` and the registry.
    name: str = "sink"

    @classmethod
    @abstractmethod
    def from_env(cls, env, dedup: bool) -> "Sink":
        """Build the sink from environment variables (its own credentials/config)."""

    @abstractmethod
    def export(self, edit: Edit, diff: DiffContent, title: str) -> None:
        """Create one note/page/record for ``edit``. Raise on failure."""

    def exists(self, edit: Edit) -> bool:
        """Return True if this edit was already exported (idempotency).

        Default: no dedup. Override to make re-runs safe even if local state is lost.
        """
        return False
