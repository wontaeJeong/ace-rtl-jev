# Budgeted JEV completion plan

> Execute inline with executing-plans and test-driven-development. Existing worktree and completed baseline are reused. No full baseline rerun.

## Frozen design

- Keep original RTL generation, deep reflector reasoning, deterministic restart guards and real evaluator.
- Replace only retrospective effectiveness judgment with a five-label choice: resolved, persistent, regression, changed, uncertain. Deterministic code-diff summary replaces descriptive change generation. Preserve original primary function behind a counted fallback for uncertainty, low confidence, malformed schema or transport failure.
- Baseline mode bypasses JEV completely; unchanged code remains deterministic/no-call in both modes. No prompt-text interception or replacement of complex generation.
- State is a string containing bounded public generated-code diff, focused error, applied guidance and bounded emitted evaluator report (maximum 12,000 characters). No private scorer/reference/mutation source is opened.
- Every HTTP inference attempt, including warmup/retry/fallback, requires a shared SQLite reservation. Missing budget file disables paid inference. Atomic request counts are hard limits. Token reservations conservatively use UTF-8 input bytes plus wrapper allowance and output allowance; unavailable usage retains the reservation. Actual usage above the reservation closes further admission. These are conservative client reservations, not a promise about opaque provider billing.
- New campaign ceilings: primary 12 HTTP attempts / 300,000 reserved tokens; JEV 64 attempts / 1,000,000 reserved tokens / USD 0.10 accounted exposure. Primary API metadata exposes no price, so no primary currency total or hard dollar guarantee is invented. JEV USD cost/output-free semantics confirmed in OpenRouter documentation; reserve USD 0.0015 before each JEV request and reconcile actual receipts. Provider-side credit limits are needed for an unconditional bill guarantee.
- Start paid validation only after all local fixture, fallback, budget concurrency, interrupted usage, report and mode-bypass tests pass and review is complete.
- Paid scope is deliberately limited: preselected judgment snapshots (up to 48) paired with exact historical primary request hashes plus one real CVDP E2E case selected from completed baseline metadata. No automatic expansion, repeat, full baseline rerun or full 292-case improved benchmark.
- Snapshot study is a decision-point cost/agreement audit, not a full RTL success experiment. Unknown historical usage is excluded explicitly, not assigned zero. Agreement with the old primary judgment is a proxy, not correctness ground truth.
- E2E uses unchanged primary model and attempt/iteration/timeouts. Project the existing baseline case record without re-inference. Its historical per-case time is descriptive; the original batch ran other cases concurrently, so do not claim a controlled batch-wall speedup for a one-case rerun. If JEV hook is not exercised, report that coverage gap rather than attribute success/token differences to JEV.
- Publish Markdown/JSON/CSV and a self-contained escaped HTML report generated locally. Any unrun full-cohort/ablation/repetition remains explicitly unexecuted.

## Tasks and interfaces

### Task 1: Shared budget admission
Files: `scripts/inference_budget.py`, both API adapters, tests/conftest and budget tests.
Interfaces: `init_budget(path, limits)`, `reserve(provider, input_text, output_tokens) -> ticket`, `settle(ticket, usage)`, `snapshot(path)`. Denial is `NON_RETRYABLE`, emits no fictional API event, never releases unknown billing. Tokens/cost overshoot closes new admission; configuration cannot silently change/reset an existing ledger.
- [ ] RED: disabled budget, atomic parallel request limit, retained failed-call reservation, reported reconciliation, overshoot closure, immutable limits.
- [ ] GREEN: implement and wire before HTTP in both adapters; fixtures use explicit isolated budgets and localhost servers, not live models.

### Task 2: Retrospective hook and fallback
Files: `scripts/jev_retrospective.py`, `focused_guidance.py`, runner, tests.
Interfaces: `judge_retrospective(...) -> (diff_summary, effectiveness)`, `DecisionFallback(reason)` and fallback event recorder. Preserve original primary implementation as `_extract_implementation_changes_primary` unchanged. Hook imports repository-local script module only when JEV mode is enabled; invocation context records exact kind and fallback cause.
- [ ] RED: baseline/no-change bypass, validated mapped labels, low-confidence/uncertain/error primary fallback, history-compatible effect text, bounded state, actual fallback attribution.
- [ ] GREEN: add a minimal mode gate; keep all other generation/reflector/coordinator code and evaluation unchanged.

### Task 3: Bounded execution and evidence reuse
Files: runner, `scripts/jev_study.py`, tests.
Interfaces: existing run_batch supports JEV with a completed baseline reference and explicit budget. Persist partial/budget-stopped state, exceptions and warmup accounting; no false completed cohort on budget denial. Audit reconstructs original retrospective prompts from generated candidates/emitted reports/reflector metadata and matches exact recorded SHA256 after original prompt-budget function; never approximates a match or re-calls primary just for the audit.
- [ ] RED: paired configuration mismatch refusal, snapshot exact-hash matching and exclusion, budget-stopped incompleteness, successful E2E real evaluator semantics unchanged.
- [ ] GREEN: add deterministic selection/projection and durable study state; after offline gate, execute only the frozen paid scope within the shared campaign cap.

### Task 4: Reports, review and publication
Files: report HTML writer, study/comparison reports, guides and tests.
- [ ] RED: HTML escapes untrusted case/error text; unknown costs/incomplete data cannot produce savings; snapshot audit not mislabeled E2E; one-case baseline projection cannot claim original batch-wall savings.
- [ ] GREEN: generate all formats offline, fresh review before paid study, fix important findings through RED→GREEN, then preserve actual results and final limitations.
- [ ] Verify all tests, manifests, raw events, keys/private source exclusion; commit/push/new PR. No merge without that PR's explicit approval.

## Observed outcome

Frozen paid scope actually executed: audit48 +CVDP case1. Both E2E modes passed; total evaluation tokens 45,979 →50,269 (+9.33%), primary fallback1, JEV decisions2. Historical case43.794 s vs actual65.415 s is descriptive only, not controlled batch-wall comparison. Accepted audit13/48, would-fallback35, schema-error3; old narrative proxy1/19 (not accuracy ground truth), all-pass checks12/12. Budget: primary8 calls/45,293 tokens; JEV51 calls/164,649 tokens/USD0.006787242. No unknown new usage, denial or overrun. No full292 improved run/repetition/ablation and no additional paid tuning. Keep baseline default, publish the negative outcome and confidence/information-loss risks.

## Evidence and constraints

Baseline remains `baseline-20261011T103810Z-97717`: 292 actual outcomes, 239 success, known 16,538,281 tokens plus 33 usage-unknown calls; 4,367.250 s measured batch wall. Primary model metadata GET returned its ID but no pricing; no inference was sent for metadata discovery. Current JEV is OpenRouter/TypeSafe, not the initial local Ollama server. Full 292-case JEV evaluation is not authorized by this small new campaign allocation and must remain pending in reports.
