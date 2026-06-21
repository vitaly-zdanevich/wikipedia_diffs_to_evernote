# wikipedia_diffs_to_evernote

[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=vitaly-zdanevich_wikipedia_diffs_to_evernote&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=vitaly-zdanevich_wikipedia_diffs_to_evernote)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=vitaly-zdanevich_wikipedia_diffs_to_evernote&metric=coverage)](https://sonarcloud.io/summary/new_code?id=vitaly-zdanevich_wikipedia_diffs_to_evernote)
[![Lines of Code](https://sonarcloud.io/api/project_badges/measure?project=vitaly-zdanevich_wikipedia_diffs_to_evernote&metric=ncloc)](https://sonarcloud.io/summary/new_code?id=vitaly-zdanevich_wikipedia_diffs_to_evernote)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=vitaly-zdanevich_wikipedia_diffs_to_evernote&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=vitaly-zdanevich_wikipedia_diffs_to_evernote)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=vitaly-zdanevich_wikipedia_diffs_to_evernote&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=vitaly-zdanevich_wikipedia_diffs_to_evernote)
[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=vitaly-zdanevich_wikipedia_diffs_to_evernote&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=vitaly-zdanevich_wikipedia_diffs_to_evernote)
[![Bugs](https://sonarcloud.io/api/project_badges/measure?project=vitaly-zdanevich_wikipedia_diffs_to_evernote&metric=bugs)](https://sonarcloud.io/summary/new_code?id=vitaly-zdanevich_wikipedia_diffs_to_evernote)
[![Code Smells](https://sonarcloud.io/api/project_badges/measure?project=vitaly-zdanevich_wikipedia_diffs_to_evernote&metric=code_smells)](https://sonarcloud.io/summary/new_code?id=vitaly-zdanevich_wikipedia_diffs_to_evernote)
[![Duplicated Lines (%)](https://sonarcloud.io/api/project_badges/measure?project=vitaly-zdanevich_wikipedia_diffs_to_evernote&metric=duplicated_lines_density)](https://sonarcloud.io/summary/new_code?id=vitaly-zdanevich_wikipedia_diffs_to_evernote)
[![Technical Debt](https://sonarcloud.io/api/project_badges/measure?project=vitaly-zdanevich_wikipedia_diffs_to_evernote&metric=sqale_index)](https://sonarcloud.io/summary/new_code?id=vitaly-zdanevich_wikipedia_diffs_to_evernote)

Sync a Wikipedia user's edits to your notes. A daily [GitHub Actions](#github-actions-setup)
cron reads a user's contributions from the MediaWiki API and creates **one note per edit**,
each containing:

- the **page title** (linked to the article),
- a **clickable editor** name (→ their contributions page),
- the **date**,
- the **byte-size change** (`+/-` bytes, colour-coded),
- a **link to the diff** on Wikipedia, and
- the **diff itself**, rendered inline.

The export destination is **pluggable**. Evernote ships working; Notion is
included as a reference implementation; adding another (OneNote, a Markdown repo,
a database…) is a single new file — see [Adding a destination](#adding-a-destination).

## How it works

```
MediaWiki API ──> Edit objects ──> render ──> Sink.export()  (Evernote / Notion / …)
 (usercontribs            │                         ▲
  + compare)              └── state.json high-water mark ──┘  only new edits each run
```

- **No Wikipedia auth.** Contributions and diffs come from the public API.
- **Multiple wikis.** `WIKIPEDIA_LANG` accepts a comma-separated list (e.g. `en,ru,be,be-tarask`);
  the same username is synced on each edition independently. Notes are prefixed with `[lang]`.
- **Evernote auth is just a developer token** (Premium accounts can mint one), stored
  as a GitHub Secret — no interactive OAuth at runtime.
- **Idempotent.** A committed `state.json` records the last-synced revision per
  `host|username`, so each run only adds new edits. As a safety net, sinks also skip
  edits already present (Evernote dedupes by the note's `sourceURL`).

## GitHub Actions setup

1. **Fork / create** this repo on GitHub.
2. **Settings → Secrets and variables → Actions**:
   - **Secrets**: `EVERNOTE_DEV_TOKEN` (and `NOTION_TOKEN` if using Notion).
     Also set `WIKIPEDIA_USER_AGENT` here as a **Secret** if you include a contact
     email and the repo is public — the workflow reads the secret first, then the
     variable. A descriptive UA reduces 429 rate-limiting.
   - **Variables**: `WIKIPEDIA_USERNAME` (required). Optionally `WIKIPEDIA_LANG`,
     `EVERNOTE_NOTEBOOK`, `EXPORT_TARGETS`, `MAX_EDITS_PER_RUN`, etc. — see
     [`.env.example`](.env.example) for the full list.
3. The workflow runs daily at **06:17 UTC** and can be triggered manually from the
   **Actions** tab (*Run workflow*). It commits `state.json` back to the repo after
   each run, so it needs the default `contents: write` permission (already set in the
   workflow). If your org disables Actions writing to the repo, enable
   *Settings → Actions → General → Workflow permissions → Read and write*.

### Getting an Evernote developer token

Premium/Professional accounts can request a developer token via Evernote developer
support (developer tokens are no longer self-serve). It looks like
`S=s1:U=…:E=…:C=…:P=…:A=…:V=2:H=…`. Paste it into the `EVERNOTE_DEV_TOKEN` secret.
If your token is for Evernote China, also set `EVERNOTE_SERVICE_HOST=app.yinxiang.com`.

## Local run / dry run

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# No-credential dry run — prints what would be exported:
EXPORT_TARGETS=stdout WIKIPEDIA_USERNAME="Jimbo Wales" python -m wikisync

# Real run against Evernote:
cp .env.example .env   # fill in EVERNOTE_DEV_TOKEN, WIKIPEDIA_USERNAME
set -a; . ./.env; set +a
python -m wikisync
```

Run the tests with `pip install pytest && pytest`.

## Configuration

All configuration is via environment variables; the full annotated list is in
[`.env.example`](.env.example). Highlights:

| Variable | Default | Purpose |
| --- | --- | --- |
| `WIKIPEDIA_USERNAME` | — (required) | User whose edits to sync (the same name is looked up on every wiki) |
| `WIKIPEDIA_LANG` | `en` | Comma-separated language edition(s) → `<lang>.wikipedia.org`. e.g. `en,ru,be,be-tarask` |
| `WIKIPEDIA_HOST` | — | Comma-separated host override for non-Wikipedia wikis (e.g. `commons.wikimedia.org`); takes precedence over `WIKIPEDIA_LANG` |
| `EXPORT_TARGETS` | `evernote` | Comma-separated sinks: `evernote,notion,stdout` |
| `EXPORT_DEDUP` | `true` | Skip edits already exported |
| `MAX_EDITS_PER_RUN` | `50` | Cap per run; remainder syncs next run |
| `FIRST_RUN_LOOKBACK_DAYS` | `7` | On first run, ignore edits older than this |
| `EVERNOTE_DEV_TOKEN` | — | **Secret.** Required for the Evernote sink |
| `EVERNOTE_NOTEBOOK` | (default notebook) | Notebook name (created if missing) |

## Adding a destination

1. Create `wikisync/sinks/mysink.py` with a `Sink` subclass:

   ```python
   from .base import Sink

   class MySink(Sink):
       name = "mysink"

       @classmethod
       def from_env(cls, env, dedup):
           return cls(token=env["MYSINK_TOKEN"], dedup=dedup)

       def exists(self, edit):      # optional: idempotency
           return False

       def export(self, edit, diff, title):
           # edit: facts + .diff_url/.user_contribs_url/.page_url
           # diff: .kind in {"diff","newpage","unavailable"}, .html
           # render.diff_rows_to_xhtml / render.diff_rows_to_text help
           ...
   ```

2. Register it in `wikisync/sinks/__init__.py`:

   ```python
   from .mysink import MySink
   _BUILDERS = { ..., MySink.name: MySink.from_env }
   ```

3. Add `mysink` to `EXPORT_TARGETS`. Done.

`wikisync/sinks/stdout.py` is the minimal worked example.

## Code quality (SonarQube Cloud)

Static analysis and test coverage run on every push via
[`.github/workflows/sonar.yml`](.github/workflows/sonar.yml) and publish to
[SonarQube Cloud](https://sonarcloud.io) (the badges above). One-time setup:

1. Sign in to https://sonarcloud.io with GitHub and **import this repo**. The defaults
   used here are organization `vitaly-zdanevich` and project key
   `vitaly-zdanevich_wikipedia_diffs_to_evernote` — if yours differ, update
   [`sonar-project.properties`](sonar-project.properties) and the badge URLs above.
2. In the SonarCloud project, **Administration → Analysis Method → turn _off_ Automatic
   Analysis** (CI-based analysis is required to ingest the coverage report).
3. Add a repository **Secret** `SONAR_TOKEN` (SonarCloud → *My Account → Security → Generate Token*).

Until `SONAR_TOKEN` is set, the workflow still runs the tests and coverage; it just skips
the upload step (so CI stays green).

## Notes & limits

- The Notion sink is a **reference implementation** (not run in CI). It expects a
  database with properties `Name` (title), `Editor` (rich_text), `Date` (date),
  `Size` (number), `Diff URL` (url), shared with your integration.
- New-page edits embed the created **wikitext** (there is no "previous" revision to
  diff against); regular edits embed the two-column visual diff.
- Very large diffs are linked rather than embedded to stay under note-size limits.

## Development

```bash
pip install -r requirements.txt ruff pytest pytest-cov
ruff check . && ruff format --check .   # lint + format (single-quote style; CI-enforced)
pytest                                   # unit tests
```

## License

[MIT](LICENSE) © Vitaly Zdanevich
