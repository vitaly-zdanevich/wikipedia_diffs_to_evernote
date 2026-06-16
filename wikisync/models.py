"""Domain models shared across the pipeline and all sinks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote, urlencode


@dataclass(frozen=True)
class Edit:
    """A single Wikipedia revision authored by the tracked user.

    Sink-agnostic: holds the raw facts plus convenience URL builders. How an edit
    is rendered into a note is the sink's concern.
    """

    host: str
    username: str
    revid: int
    parentid: int
    title: str
    timestamp: datetime
    comment: str
    sizediff: int
    is_new: bool
    is_minor: bool
    is_top: bool

    @classmethod
    def from_api(cls, item: dict, host: str) -> "Edit":
        ts = datetime.strptime(item["timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return cls(
            host=host,
            username=item["user"],
            revid=int(item["revid"]),
            parentid=int(item.get("parentid") or 0),
            title=item["title"],
            timestamp=ts,
            comment=item.get("comment") or "",
            sizediff=int(item.get("sizediff") or 0),
            is_new=bool(item.get("new", False)),
            is_minor=bool(item.get("minor", False)),
            is_top=bool(item.get("top", False)),
        )

    @property
    def lang(self) -> str:
        """Short wiki label from the host, e.g. 'en', 'ru', 'be-tarask', 'commons'."""
        return self.host.split(".")[0]

    # --- URL builders -----------------------------------------------------
    def _wiki(self, title: str) -> str:
        return f"https://{self.host}/wiki/" + quote(title.replace(" ", "_"), safe="/:()_,'!.&%-+")

    @property
    def page_url(self) -> str:
        return self._wiki(self.title)

    @property
    def diff_url(self) -> str:
        query = {"title": self.title, "diff": self.revid, "oldid": self.parentid or self.revid}
        return f"https://{self.host}/w/index.php?" + urlencode(query)

    @property
    def permalink(self) -> str:
        return f"https://{self.host}/w/index.php?" + urlencode({"title": self.title, "oldid": self.revid})

    @property
    def user_contribs_url(self) -> str:
        return self._wiki("Special:Contributions/" + self.username)

    @property
    def user_url(self) -> str:
        return self._wiki("User:" + self.username)


@dataclass(frozen=True)
class DiffContent:
    """The fetched representation of an edit's change.

    ``kind`` is one of:
      - ``"diff"``      : ``html`` is MediaWiki ``compare`` body (a run of <tr> rows).
      - ``"newpage"``   : ``html`` is the new page's wikitext (the whole thing is "added").
      - ``"unavailable"``: could not be fetched; sinks should fall back to the diff link.
    """

    kind: str
    html: str | None = None
