"""Pipeline orchestration: fetch new edits, render, export, advance state.

Each configured wiki (host) is synced independently — its own high-water mark in
``state.json`` (keyed by ``host|username``) and its own per-run edit cap.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from . import render
from . import state as state_mod
from .config import Config
from .sinks import Sink, build_sinks
from .wikipedia import Wikipedia

log = logging.getLogger(__name__)


def run(config: Config, env) -> int:
    """Run one sync across all configured wikis. Returns an exit code (0 ok, 1 on failure)."""
    sinks = build_sinks(config.targets, env, config.dedup)
    log.info(
        "Syncing %r across %d wiki(s) [%s] → %s",
        config.username, len(config.hosts), ", ".join(config.hosts), ", ".join(s.name for s in sinks),
    )

    state = state_mod.load(config.state_file)
    total_created = total_failures = 0
    for host in config.hosts:
        created, failures = _sync_host(config, host, sinks, state)
        total_created += created
        total_failures += failures

    log.info("All wikis done. created=%d failures=%d", total_created, total_failures)
    return 1 if total_failures else 0


def _sync_host(config: Config, host: str, sinks: list[Sink], state: dict) -> tuple[int, int]:
    """Sync a single wiki. Returns (created, failures)."""
    wiki = Wikipedia(host, config.user_agent)
    last_revid, last_ts = state_mod.get(state, host, config.username)

    cutoff = None
    if last_revid is None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=config.first_run_lookback_days)
        log.info("[%s] no prior state — first run limited to edits since %s.", host, cutoff.date())

    candidates = list(wiki.iter_contributions(config.username, since_revid=last_revid, cutoff=cutoff))
    candidates.sort(key=lambda e: (e.timestamp, e.revid))  # oldest first → monotonic high-water

    batch = candidates[: config.max_edits]
    if not candidates:
        log.info("[%s] no new edits.", host)
        return 0, 0
    if len(candidates) > len(batch):
        log.info("[%s] %d new edits; processing oldest %d this run (rest next run).",
                 host, len(candidates), len(batch))
    else:
        log.info("[%s] %d new edit(s) to process.", host, len(candidates))

    new_revid = last_revid or 0
    new_ts = last_ts
    created = failures = 0
    blocked = False  # once an edit fails, stop advancing the high-water mark

    for edit in batch:
        title = render.format_title(edit, config.note_title_template)
        try:
            diff = wiki.fetch_diff(edit)
            for sink in sinks:
                if sink.exists(edit):
                    log.info("[%s] skip (already in %s): %s", host, sink.name, title)
                    continue
                sink.export(edit, diff, title)
                created += 1
                log.info("[%s] created in %s: %s", host, sink.name, title)
            if not blocked:
                new_revid = edit.revid
                new_ts = edit.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception as exc:
            failures += 1
            blocked = True
            log.error("[%s] FAILED edit revid=%s (%s): %s", host, edit.revid, edit.title, exc)

    if new_revid and new_revid != (last_revid or 0):
        state_mod.update(state, host, config.username, new_revid, new_ts)
        state_mod.save(config.state_file, state)
        log.info("[%s] state saved: last_revid=%s", host, new_revid)

    return created, failures
