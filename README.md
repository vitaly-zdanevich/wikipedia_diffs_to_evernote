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
- the **byte-size change** (`+/-` bytes, colour-coded) and edit flags,
- the edit summary, when present,
- a **link to the diff** on Wikipedia, and
- the **diff itself**, rendered as a unified single-column sequence.

The export destination is **pluggable**. Evernote ships working; Notion is
included as a reference implementation; adding another (OneNote, a Markdown repo,
a database…) takes a sink module plus one registry entry — see
[Adding a destination](#adding-a-destination).

## How it works

```
MediaWiki API ──> Edit objects ──> render ──> Sink.export()  (Evernote / Notion / …)
 (usercontribs            │                         ▲
  + compare/parse)        └── state.json high-water mark ──┘  only new edits each run
```

- **No Wikipedia auth.** Contributions and diffs come from the public API.
- **Multiple wikis.** `WIKIPEDIA_LANG` accepts a comma-separated list (e.g. `en,ru,be,be-tarask`);
  the same username is synced on each edition independently. Default titles are prefixed with `[lang]`.
- **Evernote authentication uses a developer token** stored as a GitHub Secret;
  no interactive OAuth runs during synchronization.
- **Idempotent.** A committed `state.json` records the last-synced revision per
  `host|username`, so each run only adds new edits. As a safety net, dedup-capable
  sinks also skip existing edits; Evernote searches by the note's `sourceURL`.
- **Retry-safe.** MediaWiki requests retry transient rate-limit and server failures
  with exponential backoff. If a diff request still fails after retries, that note is
  not created and the cursor does not advance past the revision, so a later run retries
  it. Other configured wikis continue independently.

## Evernote note format

The default title contains the wiki, page title, and byte-size change—without a date
or time:

```text
[ru] Пенья, Хосе Луис Хордан (-44 B)
```

The body also omits the edit date and time. It links the page and editor, shows the
size, `new page` and `minor` flags when applicable, the optional edit summary, and a
link to a readable Wikipedia diff URL. Diff links preserve Unicode page titles and
use `_` for spaces instead of percent-encoded titles.

Regular edits are converted from MediaWiki's left/right HTML into one inline column:
removed lines use `−` with a red background, added lines use `+` with a green
background, and unchanged context remains neutral. New pages show their wikitext as
added content. There is no divider before the diff.

Every Evernote note ends with a small “Note created by
[wikipedia_diffs_to_evernote](https://github.com/vitaly-zdanevich/wikipedia_diffs_to_evernote)”
footer. Set the `EVERNOTE_TAGS` repository variable to `wikipedia_diff` to apply the
recommended tag to newly created notes; existing notes are not retagged.

## GitHub Actions setup

1. **Fork / create** this repo on GitHub.
2. **Settings → Secrets and variables → Actions**:
   - **Secrets**: `EVERNOTE_DEV_TOKEN` (and `NOTION_TOKEN` if using Notion).
     Also set `WIKIPEDIA_USER_AGENT` here as a **Secret** if you include a contact
     email and the repo is public — the workflow reads the secret first, then the
     variable. A descriptive UA reduces 429 rate-limiting.
   - **Variables**: `WIKIPEDIA_USERNAME` (required). Optionally `WIKIPEDIA_LANG`,
     `EVERNOTE_NOTEBOOK`, `EVERNOTE_TAGS` (recommended: `wikipedia_diff`),
     `EXPORT_TARGETS`, `MAX_EDITS_PER_RUN`, etc. — see
     [`.env.example`](.env.example) for annotated options.
3. The workflow runs daily at **06:17 UTC** and can be triggered manually from the
   **Actions** tab (*Run workflow*). If `state.json` changes, the final step commits
   and pushes it, including partial progress saved before a later edit failed. The
   workflow explicitly requests `contents: write`; your repository or organization
   policy must also permit GitHub Actions to write. If it does not, enable
   *Settings → Actions → General → Workflow permissions → Read and write*.

### Getting an Evernote developer token

This project currently requires a developer token. **As of 2026, Evernote does not
issue new developer/API tokens for normal use**; its documentation says they are
[available only for proven necessity](https://dev.evernote.com/doc/articles/dev_tokens.php)
and recommends OAuth for new integrations. A previously issued or specially granted
token looks like `S=s1:U=…:E=…:C=…:P=…:A=…:V=2:H=…`; store it in the
`EVERNOTE_DEV_TOKEN` secret.
For a China token, local runs can set `EVERNOTE_SERVICE_HOST=app.yinxiang.com`; the
bundled GitHub workflow does not currently forward this setting.

## Local run / dry run

```bash
python3.14 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# No-credential dry run — prints what would be exported:
EXPORT_TARGETS=stdout WIKIPEDIA_USERNAME="Jimbo Wales" python -m wikisync

# Real run against Evernote:
cp .env.example .env   # fill in EVERNOTE_DEV_TOKEN, WIKIPEDIA_USERNAME
# Quote values containing spaces, e.g. WIKIPEDIA_USERNAME="Jimbo Wales".
set -a; . ./.env; set +a
python -m wikisync
```

Run the tests with `pip install -r requirements-dev.txt && pytest`.

## Configuration

All configuration is via environment variables; [`.env.example`](.env.example)
contains annotated common options. Highlights:

| Variable | Default | Purpose |
| --- | --- | --- |
| `WIKIPEDIA_USERNAME` | — (required) | User whose edits to sync (the same name is looked up on every wiki) |
| `WIKIPEDIA_LANG` | `en` | Comma-separated language edition(s) → `<lang>.wikipedia.org`. e.g. `en,ru,be,be-tarask` |
| `WIKIPEDIA_HOST` | — | Comma-separated host override for non-Wikipedia wikis (e.g. `commons.wikimedia.org`); takes precedence over `WIKIPEDIA_LANG` |
| `EXPORT_TARGETS` | `evernote` | Comma-separated sinks: `evernote,notion,stdout` |
| `EXPORT_DEDUP` | `true` | Skip edits already exported |
| `MAX_EDITS_PER_RUN` | `50` | Per-wiki cap per run; remaining edits sync on following runs |
| `FIRST_RUN_LOOKBACK_DAYS` | `7` | Lookback when a `host|username` pair has no saved state |
| `STATE_FILE` | `state.json` | Local high-water state path; the workflow persists `state.json` |
| `NOTE_TITLE_TEMPLATE` | `[{lang}] {title} ({sizediff:+d} B)` | Fields: `{lang}`, `{title}`, `{sizediff}`, `{date}`, `{revid}`, `{user}`, `{host}` |
| `EVERNOTE_DEV_TOKEN` | — | **Secret.** Required for the Evernote sink |
| `EVERNOTE_NOTEBOOK` | (default notebook) | Notebook name (created if missing) |
| `EVERNOTE_TAGS` | — | Tags for newly created notes; recommended: `wikipedia_diff` |
| `EVERNOTE_SANDBOX` | `false` | Use `sandbox.evernote.com` |
| `EVERNOTE_SERVICE_HOST` | `www.evernote.com` | Evernote API host; local-only in the bundled workflow |

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

Static analysis and test coverage run on pushes to `main` and pull requests targeting
`main` via [`.github/workflows/sonar.yml`](.github/workflows/sonar.yml), then publish
to [SonarQube Cloud](https://sonarcloud.io) (the badges above). One-time setup:

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

- The Notion sink is a **reference implementation**. Its mocked tests run in CI, but
  it is not tested against a live Notion workspace. It expects a database with
  properties `Name` (title), `Editor` (rich_text), `Date` (date), `Size` (number),
  `Diff URL` (url), shared with your integration.
- New-page edits embed the created **wikitext** (there is no "previous" revision to
  diff against); regular edits embed the unified single-column visual diff.
- Very large regular diffs fall back to the Wikipedia link; very large new-page
  wikitext is truncated and marked as truncated.
- If MediaWiki successfully returns no diff content, the note keeps the Wikipedia
  link and displays a “Diff unavailable” message.

## Development

```bash
pip install -r requirements-dev.txt
ruff check . && ruff format --check .   # lint + format (single-quote style; CI-enforced)
pytest                                   # unit tests
```

All runtime and development packages are pinned in `constraints.txt` for reproducible
Python 3.14 installs. Update that lock deliberately and rerun the checks above.

## License

[MIT](LICENSE) © Vitaly Zdanevich
