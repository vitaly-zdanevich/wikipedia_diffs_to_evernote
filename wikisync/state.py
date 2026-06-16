"""Persistent high-water mark so each run only syncs new edits.

State is a small JSON file keyed by ``host|username`` holding the last synced
revision id and timestamp. It is committed back to the repo by the workflow.
"""

from __future__ import annotations

import json
import logging
import os

log = logging.getLogger(__name__)


def load(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh) or {}
    except Exception as exc:
        log.warning("Could not read state %s (%s); starting fresh.", path, exc)
        return {}


def save(path: str, state: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def _key(host: str, username: str) -> str:
    return f"{host}|{username}"


def get(state: dict, host: str, username: str) -> tuple[int | None, str | None]:
    entry = state.get(_key(host, username)) or {}
    return entry.get("last_revid"), entry.get("last_timestamp")


def update(state: dict, host: str, username: str, last_revid: int, last_timestamp: str | None) -> None:
    state[_key(host, username)] = {"last_revid": last_revid, "last_timestamp": last_timestamp}
