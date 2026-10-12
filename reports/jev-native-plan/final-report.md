# Native JEV implementation — measured validation

## Outcome

Typed native D/J integration and opt-in X algorithms are implemented and covered by local contracts/integration fixtures. Default remains **`baseline_fixed`**. Real verification establishes evaluator-based PASS; this small campaign does **not** establish JEV superiority.

PR: https://github.com/wontaeJeong/ace-rtl-jev/pull/4. Final local verification: **286 tests passed**, compile/diff checks clean; nine Important review reproductions and active integration omissions fixed in a single test-covered pass. No automatic merge or second fresh-review approval is claimed.

## Fixed A/B/C task: bus-arbiter

One task, one attempt, two iterations, one worker; same prepared primary model/adapter, dataset and CVDP/tool environment. X off. Warmup excluded. Requested model aliases are fixed; sampling seed and concrete resolved weight revisions are not guaranteed.

Comparison runtime source: `ab609ce`; signed-adder smoke source: `b16f512`. Later review fixes revalidated existing evaluator/claim artifacts rather than relabelling those as newly measured simulator runs.

| Arm | Outcome | Wall seconds | Primary HTTP calls | Primary tokens | JEV HTTP calls | JEV tokens |
|---|---|---:|---:|---:|---:|---:|
| A: original `94754d7` | Infrastructure blocked; custom model backend unsupported | 1.08 | 0 | 0 | 0 | 0 |
| B: fixed baseline | **Verified actual PASS**, iteration 2 | 37.23 | 4 | 16,624 | 0 | 0 |
| C: core | Actual task failure after iteration 2 | 29.68 | 3 | 16,962 | 3 | 32,981 |

C used **49,943 total tokens**, versus B's 16,624 (+200.4%). Its shorter wall time is not a speedup claim because the outcomes differ. Core executed a real `gather_evidence` transition; subsequent strict Score schema failures invoked primary analysis fallback. No model judgment was counted as benchmark success.

A is excluded from the valid-evaluation denominator, but remains an end-to-end infrastructure failure. B: end-to-end/valid-evaluation-only success 1/1. C: 0/1. These single stochastic samples are insufficient for noninferiority or causal conclusions.

## Additional actual verification

- Mixed `/v1/systemone` Choice/Noul/Score contract: valid with reported usage.
- Frozen 25-question contract replay: valid; contract diagnostic only, not E2E improvement.
- Intermittent actual Score responses were rejected for expected-score consistency. Additional scalar evidence instrumentation preserves supplied score versus distribution expectation; no invalid answer is approved.
- Signed-adder `jev_core`: **verified PASS** on required service `01-new-tb`, first iteration; total wall 20.33s, worker time to verified pass 19.50s. An initial PASS does not exercise or prove a successful JEV repair branch.
- Initial B/C run had a real multiprocessing serialization failure after evaluations. This was fixed by a RED→GREEN pickle regression; all its paid calls and results remain in the campaign ledger. It is not silently included as a successful run.

## Evidence locations

Local artifacts, deliberately Git-ignored because working copies include benchmark-private harness source:

- `outputs/jev-full-validation/contract-smoke.json`
- `outputs/jev-full-validation/primary-contract.json`
- `outputs/jev-full-validation/abc/` — initial failed collection, preserved
- `outputs/jev-full-validation/abc-recheck/summary.json`, `report.md`
- `outputs/jev-full-validation/signed-adder-core/` — actual evaluator/claim/provenance
- `outputs/jev-full-validation/campaign.sqlite` — immutable shared admission/settlement

Published summaries contain statuses, hashes, counters and measurements—not private checker/reference source, credentials or prompt snapshots. The signed-adder verified claim binds tested hash `70c7b4f050288dda3dd6a62d35491773585aba1e701e368680d5ef583e6b3569` and evaluator hash `b37a010b2bc7ea64ffef3fe83c9b8c42e161e06fe43a8292c6e3659817cd256f`.

## Extension/data status

| Extension | Implementation/verification | Actual performance experiment |
|---|---|---|
| X-01 beam | Own-fit/risk gated alternatives, frozen-parent independent files/actions, bounded generation checkpoints, discarded outcomes; native fixture | Not funded/run; no benefit claimed |
| X-02 scheduling | Minimum exploration/fair next-iteration checkpoint admission; no paid-call refund or process pause/resume | Not run |
| X-03 routing | User alias allowlist, maximum individual risk, output allowance and evaluator requirement | Not run |
| X-04 lessons | Frozen snapshot retrieval; bounded evidence-linked candidate curation; no online benchmark memory update | No real cross-task memory study |
| X-05 learned policy | Stdlib stump, executed-action/valid-next-evaluation labels, task/design-family group split, future-feature rejection; fixture artifacts refused by native | Real-data training incomplete: insufficient independent families/outcomes |
| X-06 questions | Pinned registry/snapshot, dev-only proposals, order/wording/negation/missing/duplicate perturbation metrics; no runtime self-modification | No calibrated dev/held-out semantic accuracy study |

All extensions default off and are excluded from B/C. Raw VCD numeric analysis is unsupported; diagnostics inspect only already-emitted permitted log/trace text and reject raw waveform input.

## Blocking limits and rerun

- Original A cannot use the prepared non-NVIDIA role model without changing its old backend. Preserve that blocker rather than call a modified program the exact original. A compatible environment/model, or a separately labelled adapted baseline, is required for a complete controlled A→B estimate.
- Provider Score contract failures are intermittent. Invalid responses are retained as failures/fallback, not fixed by integerization or invented probabilities.
- Primary monetary pricing and generic SystemOne receipt currency are not established. Report tokens and conservative exposure, not zero-price savings. Provider-side billing limits are needed for an unconditional financial cap.
- More tasks/repetitions, development labels and separate X ablations need a **new explicit allocation**; do not reset the spent campaign.

Exact bounded rerun commands and budget/configuration examples: [`docs/jev_native_runbook.md`](../../docs/jev_native_runbook.md). Static source audit and F01–F20 dispositions: [`docs/jev_integration_audit.md`](../../docs/jev_integration_audit.md). Final verification/remaining review findings are recorded in the completion summary.
