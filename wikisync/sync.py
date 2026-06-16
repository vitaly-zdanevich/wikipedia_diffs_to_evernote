"""Pipeline orchestration: fetch new edits, render, export, advance state."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from . import render
from . import state as state_mod
from .config import Config
from .sinks import build_sinks
from .wikipedia import Wikipedia

log = logging.getLogger(__name__)


def run(config: Config, env) -> int:
    """Run one sync. Returns a process exit code (0 ok, 1 if any edit failed)."""
    wiki = Wikipedia(config.host, config.user_agent)
    sinks = build_sinks(config.targets, env, config.dedup)
    log.info("Syncing %r on %s → %s", config.username, config.host, ", ".join(s.name for s in sinks))

    state = state_mod.load(config.state_file)
    last_revid, last_ts = state_mod.get(state, config.host, config.username)

    cutoff = None
    if last_revid is None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=config.first_run_lookback_days)
        log.info("No prior state — first run limited to edits since %s.", cutoff.date())

    candidates = list(wiki.iter_contributions(config.username, since_revid=last_revid, cutoff=cutoff))
    candidates.sort(key=lambda e: (e.timestamp, e.revid))  # oldest first → monotonic high-water

    batch = candidates[: config.max_edits]
    if len(candidates) > len(batch):
        log.info("%d new edits; processing oldest %d this run (rest next run).", len(candidates), len(batch))
    elif candidates:
        log.info("%d new edit(s) to process.", len(candidates))
    else:
        log.info("No new edits.")

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
                    log.info("skip (already in %s): %s", sink.name, title)
                    continue
                sink.export(edit, diff, title)
                created += 1
                log.info("created in %s: %s", sink.name, title)
            if not blocked:
                new_revid = edit.revid
                new_ts = edit.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception as exc:
            failures += 1
            blocked = True
            log.error("FAILED edit revid=%s (%s): %s", edit.revid, edit.title, exc)

    if batch and new_revid and new_revid != (last_revid or 0):
        state_mod.update(state, config.host, config.username, new_revid, new_ts)
        state_mod.save(config.state_file, state)
        log.info("State saved: last_revid=%s", new_revid)

    log.info("Done. created=%d failures=%d", created, failures)
    return 1 if failures else 0
