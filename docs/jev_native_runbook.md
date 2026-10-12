# Typed native CVDP / SystemOne runbook

## Modes and safety

- `baseline_fixed` (default): deterministic D fixes, existing primary generation/analysis; no SystemOne calls.
- `shadow`: records SystemOne proposals, but executes the baseline action. Shadow billing is additional, not a saving.
- `jev_core`: typed, eligible actions and selected-action fit / individual risk gates, with primary-model fallback.
- `jev_extended`: core plus explicitly enabled extensions. Every X flag defaults false.
- `legacy`: compatibility control path, **not** an exact original baseline. Use the original reference source for A.

Only actual required CVDP service results can establish PASS. Empty/malformed results, skipped required checks, timeouts, cancellation and model answers cannot. A source symptom ID is not a proven cause. Missing metrics and unknown prices are not zero.

The generator remains the prepared primary adapter/model. SystemOne never writes RTL. Input is row-declared public specification/context, every mutable target, generated candidates and sanitized emitted diagnostics—not private checker/reference code or `.env` contents.

## Prepared configuration

Existing `.env.local` is preserved. Export its variables locally or use `decision_compare.py`, which loads it without printing values. The original adapter remains `scripts/local_llm_adapter.py` via `ACE_RTL_LLM_SCRIPT`.

| New setting | Existing alias / default |
|---|---|
| `SYSTEMONE_ENDPOINT_URL` | `JEV_ENDPOINT_URL`; full URL, no automatic `/v1` append |
| `SYSTEMONE_MODEL` | `JEV_MODEL`; separate from `LLM_MODEL` |
| `SYSTEMONE_API_KEY` | `JEV_API_KEY`; not logged |
| `SYSTEMONE_PROVIDER` | `JEV_PROVIDER`; `typesafe`, `ollama`, or capability-unknown `systemone` |
| `SYSTEMONE_TIMEOUT_SECONDS` | `JEV_TIMEOUT_SECONDS`, `JEV_REQUEST_TIMEOUT`; default 15, clamped by common deadline |
| `ACE_RTL_POLICY_FILE` | explicit JSON thresholds/limits; defaults experimental, not calibrated |
| `ACE_RTL_QUESTION_SCHEMA_VERSION` | `jev-questions-1`; unknown registry versions rejected |
| `ACE_RTL_RUN_BUDGET_FILE` | optional JSON pointing at existing immutable campaign and scope quotas |
| `ACE_RTL_RUN_WALL_SECONDS` | 1800 |
| `ACE_RTL_TASK_WALL_SECONDS` | 1200 |
| `ACE_RTL_ATTEMPT_WALL_SECONDS` | 600 |
| `ACE_RTL_EVALUATION_CACHE_MODE` | `off`; `deterministic` also requires verified determinism, seed and complete tool/harness/config hashes |

Provider capabilities differ. TypeSafe limits are not assumed for an arbitrary proxy. An echoed alias is not a pinned weight revision; unknown resolution disables conservative raw-answer reuse. Choice/Noul/Score distributions are retained. TLS verification is enabled and existing proxy/CA settings are honored.

## Bounded admission

No paid inference is admitted without `ACE_EXPERIMENT_BUDGET_FILE`. Use a **new** campaign for a new allocation; do not reset a spent campaign. Existing SQLite admission is shared by primary, fallback, retry, warmup and JEV calls.

```bash
.cvdp-native/bin/python scripts/inference_budget.py outputs/<new-run>/campaign.sqlite --init
export ACE_EXPERIMENT_BUDGET_FILE="$PWD/outputs/<new-run>/campaign.sqlite"
export ACE_RTL_LLM_SCRIPT="$PWD/scripts/local_llm_adapter.py"
export PATH="$PWD/.cvdp-native/bin:$PATH"
```

Default initializer is deliberately small: primary 12 HTTP attempts / 300,000 token exposure; JEV 64 attempts / 1,000,000 token exposure / $0.10 exposure. Unknown billing retains reservations. Token reservations are conservative UTF-8 input exposure plus wrapper/output allowances, not a verified bound on opaque provider internals. Primary USD cost is unknown without pricing receipts; a provider-side credit cap is needed for an unconditional financial guarantee.

Optional run budget JSON (initialize scope quotas **before** any paid reservations):

```json
{
  "campaign_file": "campaign.sqlite",
  "run_wall_seconds": 600,
  "task_wall_seconds": 240,
  "attempt_wall_seconds": 180,
  "scope_limits": {
    "task": {"primary": {"max_calls": 6, "max_tokens": 250000}},
    "attempt": {"primary": {"max_calls": 6, "max_tokens": 250000}}
  }
}
```

Scope quotas use atomic reservations and settlement, namespaced by run/task/attempt. They cannot reset global spend or be retroactively added to unlabelled historic reservations. Other budget-owning adapters must explicitly set `ACE_RTL_ADAPTER_BUDGET_MANAGED=1`; the prepared adapter is recognized automatically.

## One real smoke, then repair

Use the actual installed no-commercial dataset and preflight its tools first. Never use native defaults for a small experiment.

```bash
.cvdp-native/bin/python skills/ace-rtl/scripts/ace_cvdp_native_runner.py \
  --workspace "$PWD" \
  --dataset datasets/cvdp-benchmark-dataset/cvdp_v1.1.0_nonagentic_code_generation_no_commercial.jsonl \
  --cid cid002 --id cvdp_copilot_bus_arbiter_0001 \
  --generator-model "$LLM_MODEL" --reflector-model "$LLM_MODEL" --coordinator-model "$LLM_MODEL" \
  --attempts 1 --datapoint-workers 1 --max-iterations 1 \
  --llm-timeout 60 --evaluator-timeout 60 --decision-mode baseline_fixed
```

For bounded repair, change to `--max-iterations 2 --decision-mode jev_core`. An initial PASS proves generation/evaluation, not the repair/decision branch. Auth/setup errors are infrastructure/contract failures, never candidate failures or success.

## A / B / C

Create/read a dedicated original-source reference worktree at the recorded original commit; do not change main. Its CVDP checkout and dataset must be local to that reference workspace. The comparison runs one attempt, one worker, at most three iterations and at most four explicit task IDs.

```bash
.cvdp-native/bin/python skills/ace-rtl/scripts/decision_compare.py \
  --dataset datasets/cvdp-benchmark-dataset/cvdp_v1.1.0_nonagentic_code_generation_no_commercial.jsonl \
  --id cvdp_copilot_bus_arbiter_0001 \
  --reference-workspace /path/to/original-reference-worktree \
  --output outputs/<new-comparison> --iterations 2 \
  --llm-timeout 60 --evaluator-timeout 60 --case-timeout 240
```

A is original source, B is fixed baseline, C is core. The existing primary adapter is the necessary common endpoint adaptation. Original service records lack IDs; the verifier accepts exact legacy report-name bindings, and only for A an explicitly recorded sole-service manifest binding. It never accepts `tests=[]`. Warmups are separate. X flags are forced off. Single stochastic samples are descriptive, not noninferiority or causal speedup evidence.

## Artifacts and rollback

Each attempt retains task contract, mode/policy/model metadata, raw and normalized candidates, actually prepared `tested_candidate/`, immutable observations, effects and archive entries. `candidate_manifest.json` distinguishes raw/normalized/tested hashes: CVDP preparation can change normalized bytes.

- `events/`: fsynced process-local call/evaluation/action/termination records, separate from scratch.
- `calls/attempt_<n>/`: HTTP receipts plus allowed request/answer artifacts; no headers/credentials.
- `iter_<n>/observation.json`, `effect.json`, `decision.json`, `action.json`: explicit state/action/outcome links.
- `real_evaluator_result.json`: authoritative service results; auxiliary truncation alone cannot invalidate a genuine result.
- `first_pass_claim.json`: atomic locked publication referencing verified manifest/result hashes; corrupt claims are retained and recovered.
- `candidate_archive.json`, rollback/diagnostic records: append-only provenance references, not new measurements.

`rollback_best` selects an archived bundle/observation; it does not refund spend, rewind iteration/deadline/version, clear cancellation, or turn an old evaluation into a new one. `fresh_start` creates a new episode and clears active local repair context, not the whole ledger. Loser cleanup retains candidates/calls/results and removes only large scratch/build products. Killing a local request does not prove upstream billing stopped.

## Optional extensions / offline work

`ACE_RTL_ENABLE_BEAM`, `ACE_RTL_ENABLE_ADAPTIVE_SCHEDULING`, `ACE_RTL_ENABLE_MODEL_ROUTING`, `ACE_RTL_ENABLE_LESSON_MEMORY`, `ACE_RTL_ENABLE_LEARNED_POLICY` are false by default and require `jev_extended`.

Model routing accepts only `ACE_RTL_MODEL_ALIASES` supplied by the user. Memory requires an explicit frozen snapshot/version. Fixture learned artifacts are refused by native execution; a separately validated artifact and pinned versions are required. Scheduling admits the next iteration at checkpoints, not process pause/resume, and never counts terminated inflight requests as refunded.

```bash
.cvdp-native/bin/python skills/ace-rtl/scripts/decision_offline.py train --help
.cvdp-native/bin/python skills/ace-rtl/scripts/decision_offline.py evaluate --help
.cvdp-native/bin/python -m pytest -q
```

Offline labels require executed action → valid next evaluator links; features are decision-time only and splitting is by design family. Dev-only question proposal/robustness APIs are in `decision/offline.py`; they do not self-modify runtime questions or inspect held-out data. Fixture pipeline accuracy is not model accuracy, E2E improvement or real-data training completion. Full completion/experiment status is recorded separately in the final report.
