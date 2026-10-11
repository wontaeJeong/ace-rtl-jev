# Reproduce ACE-RTL experiments

## Setup

From the dedicated worktree root:

```bash
bash scripts/setup_experiments.sh
cp .env.local.example .env.local
chmod 600 .env.local
# Fill actual endpoints/models/keys locally. Do not paste keys into logs/issues.
.cvdp-native/bin/python scripts/run_experiments.py preflight
```

For a worktree created from a checkout that already has `.env.local`, explicitly copy that file into the worktree (mode 0600). Configuration is **not** silently searched outside the current workspace. The preflight validates required names/formats, actual native tools and selected dataset service requirements without printing secrets/URLs. Missing data requires the official setup helper; missing native tools are listed, not installed silently during a run.

The original upstream setup now recognizes split heavy JSONL filenames. Environment/commit/version details: [environment.md](environment.md). API capabilities and optimization proposals: [jev-opportunities.md](jev-opportunities.md).

## Smoke and baseline

```bash
.cvdp-native/bin/python scripts/run_experiments.py run \
  --mode baseline --limit 1 --attempts 1 --iterations 1 --workers 1

.cvdp-native/bin/python scripts/run_experiments.py run \
  --mode baseline --attempts 1 --iterations 5 --workers 4 \
  --llm-timeout 90 --evaluator-timeout 300 --case-timeout 1800
```

`--id <case-id>` is repeatable to rerun exactly a case/cohort. `--limit` is for smoke/debug only; the actual full baseline command has no limit. The common defaults are explicitly lower than the original paper/runner budgets. The prepared primary API in this session is remote and was explicitly approved by the user; set a truly local API when required.

Every batch creates `experiments/runs/<mode>-<timestamp>-<pid>/`, with manifest, per-case result JSON, individual API event JSON, actual warmup events, process logs, summary and case CSV. Failed smoke is preserved separately from measured baseline. Native raw evaluator/generation artifacts remain under each case's `native/` directory, excluded from Git because they embed private benchmark source. The per-case published result retains actual evaluator outcomes.

Status distinguishes `success`, `failure`, `timeout`, `environment_error`, `execution_error`. The original native runner may exit 0 even with failed RTL: only real evaluator pass is success. Inflight requests killed by timeout retain unknown usage. No estimate is mislabeled as reported/billed usage.

## Report

```bash
.cvdp-native/bin/python scripts/experiment_reports.py \
  --baseline experiments/runs/<baseline-batch> --output reports/baseline
# Only after a real improved experiment exists:
.cvdp-native/bin/python scripts/experiment_reports.py \
  --baseline experiments/runs/<baseline-batch> \
  --improved experiments/runs/<improved-batch> --output reports/comparison
.cvdp-native/bin/python -m pytest -q
```

Report generation emits Markdown, metrics JSON and per-case CSV. Missing/incomplete improved runs remain unavailable, never artificial 100% savings. Different cohort/model/conditions are rejected for matched comparisons. Batch wall time and sum/average case runtime are separate. Unknown usage or token estimates suppress a **measured** token-saving claim. Warmup costs are separate; API-internal loading/cache times may be opaque.

## Current gate

SystemOne real schema/warmup was verified. Optimization code and improved-mode CLI are intentionally **not yet implemented** while the full baseline is running. Do not interpret the proposed opportunity design, report template or passing mock HTTP tests as completed optimized E2E evidence. This document will be extended with tested improved commands after the baseline gate.
