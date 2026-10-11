# JEV native integration audit

## Starting state (2026-10-12)

- Original main HEAD: `880b7c9eb362b66c500cb2943ad8f85ee39ad9c5` (11 commits ahead of origin/main).
- Main had only the untracked implementation instruction; ignored `.env.local` is preserved without printing values.
- Worktree `implementation/jev-full-plan` created from fetched origin/main, then fast-forwarded to original HEAD to retain user adapters and measured reports.
- No CodeGraph index exists. No project AGENTS.md found.
- Existing isolated environment baseline: 71 tests passed. System Python lacks pytest; use the prepared Python until a local environment is established.

## Active graph before edits

`ace_cvdp_native_runner.py -> ace_cvdp_native.cli.main -> run_datapoint -> attempt_worker_main -> run_attempt`.
`run_attempt -> processor.prepare(model=AceIterationModel) -> AceIterationModel.prompt -> run_role_call -> llm_call.py -> ACE_RTL_LLM_SCRIPT / llm_backend`.
`run_attempt -> processor.run -> patched native_obj_harness -> real service results -> result_passed`.
Failed candidate: `record_reflector_iteration_result -> FocusedDebugger.extract_implementation_changes`, then `call_coordinator -> FreshStartCoordinator.should_fresh_start`, then `call_reflector -> FocusedDebugger.create_focused_prompt`.
The existing JEV hook (`scripts/jev_retrospective.py`) is choice-only and affects prose retrospective classification, not a typed native state/action contract.
The separate legacy agent is `ace_agent_runner.py -> ace_rtl_agent.main/agent/agent_loop`; ContextBuilder/IterationMemory/ComprehensiveReasoningCoordinator are not the native integration surface.

## Boundaries

The pre-edit reflector reads `.env`, checker Python and compose files for non-RTL tasks: this is unsafe as a new model input. New native context will use only row-declared public input context, excluding every mutable target. Diagnostics remain sanitized emitted results; no hidden checker/reference source is read.
The real evaluator is the sole authority for PASS. Empty or incomplete service results are not success.

## Ownership / shared interface

Shared frozen dataclasses live in `ace_rtl_agent/decision/types.py`; all consumers serialize with `to_dict()`. Orchestrator owns types, native `cli.py`/`llm.py` and integration tests.

| Worker | Exclusive ownership |
|---|---|
| Observation | native diagnostics/harness/config, decision/observations.py, task detection/error analysis, tests/test_decision_observations.py |
| Runtime | native processes.py, decision/budget.py ledger.py cache.py, backend/client/llm_call.py, tests/test_decision_runtime.py |
| SystemOne | decision/systemone_client.py questions.py, tests/test_decision_systemone.py |
| Policy/context | decision/policy.py state_builder.py strategies.py context_selector.py; focused history/guidance/prompting/debugger/types/coordinator/rule advisor; tests/test_decision_policy.py |
| Extensions | decision/extensions.py offline.py; scripts/decision_offline.py; tests/test_decision_extensions.py |
| Integration | cli.py/llm.py/types.py/settings.py, runner/report docs and integration tests |

Workers must not modify files owned by another worker, reset user changes, make paid calls or commit shared work.

## Actual CVDP correspondence

Installed framework commit: `8e894cf74414ab1eaea1e2b4e80a02f123df07b6`. `DatasetProcessor.prepare -> create_repo -> get_context_for_repo -> model.prompt`, then `Repository.prepare -> restore_files -> write_file`. Restore performs template substitution. Native binding therefore reads **only declared mutable files** from `repo.issue_path`, preserves normalized output separately, and hashes the actual prepared/evaluated bytes. Refinement `include_harness/include_golden_patch` is forced false; that framework path is not used.

Actual dataset service definitions are under `row.harness.files["docker-compose.yml"]`, not only `row.harness["docker-compose.yml"]`. A real row inspection exposed the difference; a regression test now pins the installed shape. Bus-arbiter requires `direct`; signed-adder requires `01-new-tb`. A report must use each task's actual manifest, not assume one service name.

## F01–F20 disposition

| ID | Disposition in active fixed/core path | Evidence |
|---|---|---|
| F01 | Fixed: typed observation/effect controls focus; prose isolated to legacy | `test_decision_policy.py`, `focused_history.record_observation` |
| F02 | Fixed where execution proves resolution; absent symptoms remain unknown; new symptom IDs may switch focus | observation effect / named-symptom tests, policy focus eligibility |
| F03 | Fixed: nullable metrics with unavailability reason; no synthetic mismatch improvements | observation metric availability/comparability tests |
| F04 | Fixed: baseline always saved and recorded without retrospective calls | native terminal/baseline integration tests |
| F05 | Fixed: complete bundle, per-file diff, all targets passed to reflector | types/second-file and reflector bundle tests |
| F06 | Fixed: every mutable target excluded from public immutable context, initial targets have separate provenance | native public-context and contract tests |
| F07 | Fixed: canonical task contract across roles; negation/incidental code do not reclassify | task detection/metadata fixtures |
| F08 | Fixed: tool-name mentions do not establish compile failure | observation/error-analysis fixtures |
| F09 | Fixed: service-specific optimization guidance | sanity PASS / synth FAIL fixtures |
| F10 | Fixed in native: structured IDs/counts; unsupported counts unknown | dedupe/count fixtures; prose remains compatibility-only |
| F11 | Fixed: timeout is incomplete/unknown, never functional success | timeout/effect tests |
| F12 | Fixed: required services, valid exits, nonempty authoritative records, required checks actually executed | empty/missing/skipped/truncated diagnostics fixtures; real verified manifests |
| F13 | Fixed: deterministic audit/effect precedes terminal gate; optional calls skipped | native PASS/last-iteration call-zero fixtures |
| F14 | Fixed/core typed causes and verified claim checks; parent cancellation evidence persisted | parent deadline/cancellation fixtures |
| F15 | Fixed: retained candidate/call/result evidence, scratch-only cleanup | runtime cleanup fixtures |
| F16 | Fixed: exclusive OS lock, artifact durability/hash validation, atomic publication and invalid-claim recovery | concurrent/partial/crash claim tests |
| F17 | Fixed: actual deadlines/retries and usage envelopes | runtime backend/client/HTTP tests |
| F18 | Fixed: structured reflector result, no nested generator prompt; raw/normalized source omitted from delivery view | native reflection/public candidate tests |
| F19 | Fixed: current episode separated from archived episode history | focused/coordinator episode fixtures |
| F20 | Fixed: misleading `error_reasoning=guidance` removed | structured reflector metadata test |

Legacy mode retains some reference-control semantics intentionally; it is not advertised as the original unmodified program or as the new typed control path.

## Real-run findings (not inferred performance)

1. Mixed actual SystemOne request accepted Choice/Noul/Score, with reported usage.
2. Original A at `94754d7` cannot initialize the configured custom primary model in its old coordinator backend; zero paid calls, no CVDP evaluation. It was not silently patched or replaced.
3. First B/C campaign reached actual evaluations but immutable dictionaries failed Queue pickle reconstruction. Added an explicit transport regression and constructor-based pickle protocol; retained all failed-run receipts/artifacts.
4. Fixed recheck: B bus-arbiter verified PASS; C task failed. C used more total tokens. This does not support a JEV performance improvement or changing the default.
5. Signed-adder core smoke verified required service `01-new-tb` and durable manifest/result hashes. It passed initially and therefore does not demonstrate JEV repair efficacy.
6. Some actual Score responses fail expected-score/distribution consistency validation. Strict rejection/fallback is retained; scalar-only validation evidence is recorded without arbitrary response bodies. A repeat frozen contract batch was valid. Intermittent provider contract failures and their paid usage remain visible.
