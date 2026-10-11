# Native JEV full implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Independent ownership is parallelized as explicitly requested.

**Goal:** Execute D-01–11, J-01–09 and disabled-by-default X-01–06 in the actual native evaluator loop, with honest bounded verification.
**Architecture:** Frozen shared task/bundle/observation/action/effect dataclasses; isolated SystemOne transport; deterministic execution gates and policy. Preserve prepared generator adapter and shared campaign admission, compose public-only prompts, retain durable per-worker events.
**Tech Stack:** Python, dataclasses, requests, SQLite, pytest, official CVDP native services.
**Spec:** `ACE_RTL_JEV_OPENCODE_IMPLEMENTATION_PLAN.md`.

## Global constraints
- PASS only from valid real required CVDP services; model output cannot set success.
- Preserve user main, existing changes, endpoint secrets and prepared adapters.
- X flags default false; baseline_fixed default; no unbounded paid experiments.
- Public input/context/candidates/sanitized emitted diagnostics only.
- Counts, arithmetic, eligibility, stale checks, hard budgets and terminal gates are deterministic.

## Review focus
- Multi-file overlapping input/output context stays mutable and path-safe.
- Auxiliary diagnostic truncation cannot invalidate authoritative valid results.
- Winner crash/races cannot fabricate PASS or destroy loser billing evidence.
- Independent selected action fit cannot borrow another candidate's fit.
- Unknown usage and missing metrics are not zero; off-policy replay is not E2E evidence.

## Tasks and verification

### 1. Shared contract / audit (integration owner)
- [x] Record current HEAD, preserved configuration names, native graph and file ownership in audit.
- [ ] Write `tests/test_decision_types.py`: frozen Observation, nullable metrics, path rejection, bundle second-file change.
- [ ] Observe RED, implement `decision/types.py`: TaskContract, CandidateBundle, Observation, Evidence, ProposedAction, DecisionRecord, EffectRecord and canonical hashes.
- [ ] Run focused tests, then full suite; commit with integrated work.

### 2. D observation and runtime (independent owners)
- [ ] Test F07–12, service validity, execution stage, baseline/bundle/test comparability and public metadata classification.
- [ ] Implement `observations.build_task_contract(row,cid)`, `observe(result,contract,bundle,...)`, `effect(before,after,action)`.
- [ ] Test winner partial/crash/concurrent publication, evidence-preserving cleanup, deadline and retry behavior.
- [ ] Implement `processes` compatible atomic claim; common ledger/deadline/cache/backend accounting without changing native integration files.
- [ ] Verify focused tests plus suite. Retain RED/GREEN evidence.

### 3. J transport and policy (independent owners)
- [ ] Test mixed choice/noul/score schema, NaN, bad option/legend, errors and unknown usage.
- [ ] Implement `SystemOneClient.from_env().decide(state,questions,...)`, versioned questions and capabilities.
- [ ] Test selected-candidate fit, stale/no-op/loop checks, serious risks, masked effects, mandatory contrary evidence and forbidden material.
- [ ] Implement `DecisionPolicy.decide(observation,contract,bundle,...)`, eligible registry and context selection with explicit fallbacks.
- [ ] Verify transport/policy tests plus suite. No external calls from workers.

### 4. Native integration (integration owner)
- [ ] Test mocked real processor flow with terminal PASS/final failure optional calls zero; baseline saved, second target reflector visibility and typed actions applied.
- [ ] Integrate types, observation/effect, decision mode, episode/archive, public context and bundle provenance in cli.py/llm.py.
- [ ] Apply hard terminal/deadline/cancellation gate before optional calls; verify native and legacy adapter compatibility.
- [ ] Run full suite; inspect staged diff for secrets/private inputs.

### 5. X optional extensions (extension owner, then integration)
- [ ] Test disabled defaults, semantic beam diversity, minimum scheduling, alias/risk routing, provenance-bound memory, group-split learned fixture and question robustness.
- [ ] Implement real bounded extension algorithms/offline tooling; wire enabled features at native action/checkpoint boundaries.
- [ ] Isolate optional learning from core imports; report real-data training unavailable when applicable.
- [ ] Run focused/full tests and mark each X's integration and experiment status separately.

### 6. Bounded real verification / report (integration owner)
- [ ] Establish local CVDP/EDA/environment without modifying existing setup.
- [ ] Freeze task/models/policy/questions/budget: one attempt, at most 2 iterations, one worker; contract smoke and A/B/C cohort.
- [ ] Capture authoritative evaluation and complete cost/unknown events; no guessed improvement.
- [ ] Document blockers/evidence/exact rerun commands and D/J/X/F completion matrix.
- [ ] Review, verify, commit/push/create PR on writable remote. Never merge without approval.

Progress checkboxes are updated only with observed evidence; a helper existing without native wiring is not complete.
