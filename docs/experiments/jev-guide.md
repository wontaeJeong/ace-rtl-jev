# Budgeted JEV execution and reports

The completed eight-worker baseline is reused. Do **not** rerun the full baseline. This guide describes an explicitly funded small campaign, not permission for unlimited experiments.

## Mode and fallback

`--mode baseline` uses the original primary retrospective implementation. `--mode jev` changes only retrospective effectiveness judgment: public generated-code delta + bounded emitted diagnostics → one validated choice. RTL generation/deep fix guidance stay on the configured primary model. Confidence below `JEV_MIN_CONFIDENCE` (default 0.65), uncertain choice or decision errors delegate to the unchanged original primary function. Fallback routing and actual fallback API calls are separate records. Budget refusal is permanent/non-retryable, not permission to bypass limits.

The finite labels map to the existing focus-history semantics. State is at most 12,000 characters; no additional private scorer/reference source is read. Exact unchanged candidates use neither model. Missing campaign configuration disables inference in both adapters.

## Shared campaign admission

```bash
# No inference: creates immutable campaign limits.
.cvdp-native/bin/python scripts/inference_budget.py \
  experiments/studies/jev-budgeted-20261011/budget.sqlite --init
export ACE_EXPERIMENT_BUDGET_FILE="$PWD/experiments/studies/jev-budgeted-20261011/budget.sqlite"
.cvdp-native/bin/python scripts/inference_budget.py "$ACE_EXPERIMENT_BUDGET_FILE"
```

Default small campaign: primary 12 HTTP attempts / 300,000 token reservations; JEV 64 attempts / 1,000,000 token reservations / USD 0.10 exposure, with USD 0.0015 reserved before each decision. Warmups, retries and primary fallback consume the same ledger. Existing limits cannot silently reset/change. Failed/inflight/unreported usage keeps its reservation; estimated character counts are not refunded as actual usage. A receipt exceeding its reservation closes further admission.

Request counts are hard atomic limits. Token reservations use conservative UTF-8 input bytes + 4,096 wrapper tokens + output allowance; they are not an independently verified bound on opaque provider internals. JEV money accounting uses the documented OpenRouter USD receipt. Primary pricing is unavailable, so no primary dollar limit/bill is invented. Provider-side credit limits are necessary for an unconditional financial cap. The SQLite file/sidecars are Git-ignored; JSON snapshots and raw API events are published instead.

## Prepare without paid calls

```bash
.cvdp-native/bin/python scripts/jev_study.py prepare \
  --baseline experiments/runs/baseline-20261011T103810Z-97717 \
  --output experiments/studies/<fresh-study-directory> --limit 48
```

Preparation reads only existing generated candidate files, emitted evaluator reports and emitted role metadata/prompts. It reconstructs the original retrospective request and requires an **exact SHA256 match** to recorded primary API events with complete reported billing. No primary re-inference is made to reconstruct cost. Selection round-robins task categories; inputs stay local/Git-ignored because bounded emitted diagnostics can include checker traceback text. Published data is hashes, case IDs, actual usage and decisions.

## Paid scope — only after offline tests/review and allocation

```bash
.cvdp-native/bin/python scripts/jev_study.py audit \
  --output experiments/studies/<prepared-study-directory>
.cvdp-native/bin/python scripts/jev_study.py e2e \
  --output experiments/studies/<prepared-study-directory>
```

The audit asks JEV about frozen historical judgment inputs. Old primary-narrative agreement is a heuristic proxy, not correctness ground truth. Historical all-pass evaluator records provide a limited resolved-error check. Audit uncertainty records **would-fallback**, without secretly buying new primary calls. An actual native E2E then uses one preselected measured repair case, the same primary model/attempt/iteration/timeouts and the original evaluator, with real generation/JEV/fallback calls counted.

This small campaign does **not** execute all 292 JEV cases or repetitions/ablation. The historical single-case projection cannot reuse the original whole-batch wall time or establish a controlled batch speedup; other cases ran concurrently in the original cohort. If the new case passes immediately and never needs retrospective judgment, report that coverage gap explicitly. Missing usage, budget-stopped data and unrun cohorts never support invented savings/success.

## HTML / Markdown / JSON / CSV

```bash
.cvdp-native/bin/python scripts/experiment_reports.py \
  --baseline experiments/studies/<study>/baseline-projection \
  --improved experiments/runs/<actual-jev-batch> --output reports/jev-comparison
```

`comparison.html` is self-contained and escapes case/model text. It renders from already collected data with no model calls. The full baseline HTML is available at `reports/clean-baseline/comparison.html`; open it locally (GitHub raw HTML is not a hosted dashboard). Markdown, metrics JSON and case CSV accompany it.
