# Completion and review evidence

Implementation scope is the supplied `ACE_RTL_JEV_OPENCODE_IMPLEMENTATION_PLAN.md`; evidence is not a claim of statistical performance superiority.

## Phase gates

| Phase | Implemented / active path | Verification |
|---|---|---|
| D-01 | Canonical contract, metadata/negation detection, same roles/targets | task and native fixtures |
| D-02 | Authoritative service/check validity, status/exit consistency, timeout/incomplete, diagnostic separation, comparable nullable metrics | observation/review regressions; real CVDP claims |
| D-03 | Manifest-only paths, all mutable files, initial/public context distinction, raw/normalized/actual prepared bytes | bundle/context/binding tests |
| D-04 | Baseline and deterministic effects before optional inference, action/observation links | native baseline/terminal/rollback tests |
| D-05 | PASS/fatal/cancel/deadline/last iteration gates, retry re-enters full gate | native terminal and fatal-retry fixtures |
| D-06 | Durable locked verified winner, recoverable invalid claims, typed cancellation | process concurrency/crash tests |
| D-07 | Process-local durable ledger, actual HTTP receipts, unknown reservations, retained loser artifacts | runtime/admission tests, campaign snapshot |
| D-08 | HTTP/subprocess retries under common deadline; run/task/attempt wall and atomic scoped admission | runtime and parent deadline/crash fixtures |
| D-09 | Structured reflection and public delivery views, no nested complete prompt, estimated packing | reflection/context/privacy fixtures |
| D-10 | Episode isolation, objective comparison against archive, functional-first optimization, new rollback state/repair action and current budget | best/rollback/active cancellation fixtures |
| D-11 | Evaluation gate requires verified determinism/seed/config/tool/harness; pinned answer cache, unknown-alias fallback | cache/no-op tests; actual runs keep evaluation cache off |
| J-01 | Actual separate SystemOne transport and all primitive distributions, strict finite/schema/provider validation | offline contracts and actual mixed/replayed endpoint calls |
| J-02 | Typed effect judgments consumed as semantic proposals; deterministic resolution/masked/not-executed facts cannot be overridden | semantic-effect and history fixtures |
| J-03 | Observed symptom/target IDs, bounded hypotheses explicitly unverified, own-fit supported hypothesis | policy and diagnostic candidate tests |
| J-04 | Closed eligible actions, stale/no-op/version/budget checks, explicit termination | policy plus actual native action fixtures |
| J-05 | Selected action's own fit, individual risks, preserved raw distributions, experimental thresholds | own-fit/severe-risk tests |
| J-06 | Narrow recipes instruct generator; deep/focused fallback retains real evaluator | recipe/deep/native tests |
| J-07 | Canonical tasks bypass classifier; ambiguous public contract can receive one typed proposal | registry/task fixtures; real smoke tasks canonical |
| J-08 | Rule Noul/Score, public bounded context and typed native history; contradictory/passing evidence mandatory | rule/context/history fixtures |
| J-09 | Bounded novel view of existing emitted artifact, no repeated source/no-op diagnostics | diagnostic tests; real C gather/fallback path |
| X-01 | Actual native precommitted frozen-parent branches and per-branch files/provenance/outcomes | native two-branch fixture; real extension ablation not run |
| X-02 | Parent-owned fair checkpoint admission with crashed-slot recovery; no pause/resume or fee refund | scheduling/dead-worker fixtures; actual ablation not run |
| X-03 | User aliases, maximum risk, actual current reflector/generator model/output allowance | routing/review fixtures; actual ablation not run |
| X-04 | Frozen retrieval and evidence-bound candidate curation; no online evaluation-memory update | lesson fixtures; cross-task study not run |
| X-05 | Explainable optional offline pipeline, executed-action links, comparable improvement labels, group splitting and fixture refusal | offline/CLI/review fixtures; real-data training incomplete |
| X-06 | Dev-only proposals and pinned question/threshold/model snapshots, robustness perturbations | offline fixtures; calibration/held-out model accuracy not established |

No raw VCD numeric parser is claimed; this diagnostic implementation rejects raw waveform content and inspects permitted emitted text only. Default mode remains `baseline_fixed`, and every X flag is false.

## Whole-branch review and fix pass

Fresh read-only reviewer inspected `880b7c9..b16f512`; assessment was “not ready” with nine Important findings. Each reproduced failure was fixed with RED→GREEN regression evidence, followed by the full suite. No second fresh review is claimed.

| Finding | Fix / regression |
|---|---|
| Contradictory service status could pass | rejects status/exit contradiction |
| Auxiliary timeout words invalidated authoritative PASS | valid authoritative completion takes precedence |
| Raw service error source could reach models | allowlisted public observation for current/before/best/lesson views; raw result retained only as artifact |
| Retry could continue after fatal/cancel/deadline | complete terminal re-gate after retried evaluation |
| Best compared against predecessor, not best | archived objective comparison; functional-first/Pareto optimization |
| Rollback action/focus/evidence/budget mismatch | explicit reused activated state, current budget, restored evidence/focus and newly bound repair action |
| Cancel versions collided with activated versions | durable latest active-state checkpoint consumed by parent |
| Crashed scheduler slot leaked | dead-process recovery releases slot/admission |
| Improvement labels always false | comparable measured objective deltas, unavailable labels rejected |

The four initially Minor functional omissions were regraded because the user requested active integration: typed native history now reaches SystemOne; semantic effect proposals are consumed conservatively; reflector routing updates `LLMClient.model` at the current action and applies output allowance; absent/malformed diagnostic duration is nullable rather than fabricated zero.

## Rulings and limitations retained

- Supplied detailed design was executed without another planning approval pause, as explicitly requested; independent owners were parallelized while native integration remained one owner.
- Worktree was created from fetched `origin/main`, then fast-forwarded to the original user HEAD to retain eleven prepared commits. Main and existing worktree/settings were not reset or overwritten.
- Original A is kept unmodified and infrastructure-blocked with the prepared custom model. A separate adapted baseline would be a different experiment, not a silently patched original.
- Provider Score contract failures stay rejected. No normalization, integerization or fabricated probability distribution was used to buy a valid decision.
- A single failed episode lesson stays a candidate; benchmark memory is frozen. Fixture learned artifacts cannot become native production policy.
- Provider alias resolution, primary money pricing, actual invoices/upstream cancellation billing, statistical noninferiority/causal superiority, unexecuted outcomes, real-data learning quality, Ubuntu/commercial EDA/full legacy-agent E2E, exhaustive nondeterministic races are not established by these tests. They require separate evidence/allocation, not guessed results.
- No hidden checker/reference/mutation source or `.env` values were used to expand model inputs. The review boundary reproduction was hypothetical, not evidence of leakage in the recorded trials.

## Final evidence

- Full local suite: **286 passed**; compile checks and `git diff --check` clean.
- Final validators revalidated both existing actual CVDP winner claims: bus-arbiter (`direct`) and signed-adder (`01-new-tb`). Their tests were run before the review fix commit; this revalidation is not labelled a new simulator measurement.
- Actual aggregate campaign includes failed trials, warmups and contract diagnostics: **16 primary HTTP attempts / 68,174 reported tokens**, **8 JEV attempts / 79,973 reported tokens** at the published snapshot. No unknown-token reservations then remained. JEV conservative exposure $0.016 is not an established invoice; primary currency cost unknown.
- Measured A/B/C outcomes and limitations: [`reports/jev-native-plan/final-report.md`](../reports/jev-native-plan/final-report.md).
- Usage and exact rerun commands: [`docs/jev_native_runbook.md`](jev_native_runbook.md).

Remaining experiment/data work is listed explicitly above. The local isolated worktree and complete ignored artifacts are preserved for review/reproduction; no automatic merge or cleanup is performed.
