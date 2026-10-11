# Cost-first execution policy and remaining design gates

Status: **new paid experiments paused** on the user's instruction. This document is a preparation checklist, not a claim that a programmatic spending cap or the complete JEV integration already exists.

## Before any new paid request

1. Freeze the selected judgment hook, mode separation, adapter schema, unchanged RTL generation/deep reasoning, cohort, iteration/retry/time/concurrency conditions and success predicate.
2. Complete the active call-path audit, including retries, warmups, reflection, retrospective judgments and primary fallback. Do not guess a worst-case call count from three role names alone.
3. Validate the full loop without inference charges: deterministic local HTTP fixtures, synthetic/public candidates and actual previously emitted evaluator artifacts. Cover missing config, malformed/empty replies, low-confidence/uncertain decisions, failure and timeout paths, exact fallback counts, primary/JEV token accounting, process ownership/cleanup and durable interrupted-run recovery. Fixtures validate plumbing, not real model accuracy.
4. Review that model inputs use only public task/context, generated candidates and bounded real diagnostics, never separately opened hidden solutions or scorer/mutation implementations. Preserve the original evaluator and immutable files.
5. Establish an explicit run budget: maximum actual HTTP requests (including retries/warmups), primary/JEV/token totals, concurrency reservations and currency exposure. Primary pricing is currently unverified; do not invent a price or bill. Exact token/money caps cannot be promised when provider-internal prompt overhead or pricing is unknown.
6. Design a shared atomic reservation ledger across worker/adapter processes. Reserve before sending; keep reservations for failed/inflight/unknown-usage calls rather than treating them as free. Include fallback and warmup costs. Define safe stop/checkpoint semantics and clarify that client cancellation may not cancel provider billing.
7. Use the completed clean baseline when conditions truly match. Do not launch another full baseline just because a new code/report revision exists. If conditions must change, explicitly scope and budget remeasurement first.
8. Prepare a small, preselected representative smoke and its acceptance criteria. Only after offline gates and a deliberate budget allocation should real smoke/full paired evaluation occur. Do not expand to full/repeated/ablation runs automatically.

## Remaining JEV design

The candidate is retrospective fix-effectiveness judgment: deterministic generated-code diff plus validated finite-label decision, retaining the original primary path for deep repair and fallback. Specify and test label-to-history semantics, bounded state construction, confidence/uncertainty policy, counted fallback and strict baseline bypass before enabling the hook. The independent adapter alone is not this integration.

Use only features confirmed for the updated hosted endpoint. A string `state`, choice `questions`, probabilities, confidence and usage were actually observed. Do not infer Chat Completions, arbitrary generated RTL, tool execution, server cancellation or cache/load controls. Provider-reported JEV cost is retained without assuming undocumented currency units.

No claim of a "perfect" design can remove stochastic/API risk. The purpose of the gates is to discover preventable infrastructure/accounting failures offline, minimize paid validation and disclose what remains unproved.
