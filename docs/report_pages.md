# Public report Pages publication

Public site: **https://wontaejeong.github.io/ace-rtl-jev/**.

The site is an index of the latest native validation report plus previously published historical reports. It preserves the actual failed/blocked outcomes and does not claim JEV improvement. PR #4 was merged with explicit user approval; publishing reports does not run any models or evaluators.

## Build and verify

```bash
python3 scripts/build_report_pages.py --output site
python3 -m pytest tests/test_report_pages.py -q
```

The builder is standard-library only. It escapes raw HTML in Markdown, renders report tables/lists/code, maps the public documentation links, and refuses unexpected existing output or output symlinks rather than deleting user files.

`publication.json` records source hashes and the exact allowlisted output. Only selected report Markdown, completion/audit/runbook documents, already-public historical HTML and two sanitized JSON summaries are included. Dataset, `external/`, `experiments/`, `outputs/`, prompts, responses, raw logs, SQLite, `.env` and private harness/checker/reference implementations are **not** site sources. Repository root is never deployed.

## Artifact-only branch

The public Pages source is branch `gh-pages`, root `/`, with `.nojekyll`. Generate its history solely from the tracked public `site/` subtree:

```bash
git add scripts/build_report_pages.py tests/test_report_pages.py docs/report_pages.md site
git commit -m "docs: publish public report site"
git subtree split --prefix site --branch publish/jev-pages-artifact
git push jev publish/jev-pages-artifact:gh-pages
```

Use a fresh local split branch name for later updates if needed. Never force-push or replace an existing site blindly; fetch and inspect the branch first. Source/test changes are proposed separately for main via PR, while the explicitly authorized site publication uses the artifact branch directly.

The repository administrator enables Pages once with the REST API source `{ "branch": "gh-pages", "path": "/" }`, build type `legacy`. GitHub's Pages deployment workflow publishes the static branch. Check workflow completion and HTTP responses for the index, latest report and JSON summaries before reporting the site as live. Local main, existing worktrees and the ignored execution evidence remain unchanged.
