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
