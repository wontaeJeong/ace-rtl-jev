# ACE-RTL measured comparison

Baseline state: `completed`; coverage 1/1.
Improved state: `completed`.

| 지표 | Baseline | JEV-like | 변화 (JEV − baseline) |
|---|---:|---:|---:|
| 평가 케이스 수 | 1 | 1 | 0 |
| 성공 케이스 수 | 1 | 1 | 0 |
| 성공률 (0–1) | 1.000 | 1.000 | 0.000 |
| 총 토큰 (reported + disclosed estimates) | 45979 | 50269 | 4290 |
| 평균 토큰/케이스 | 45979.000 | 50269.000 | 4290.000 |
| 총 실행 시간 (batch wall s) | Unavailable | 65.421 | Unavailable |
| 평균 실행 시간/케이스 (s) | 43.794 | 65.415 | 21.621 |
| 주력 LLM 호출 수 | 8 | 7 | -1 |
| JEV-like 호출 수 | 0 | 2 | 2 |
| 평균 호출 지연 시간 (s) | 5.182 | 6.922 | 1.740 |
| 실패 및 오류 건수 | 0 | 0 | 0 |

Retrospective hook coverage: 2 evaluation-phase JEV calls (warmup excluded).

Measured token savings (%): -9.330.
Measured batch wall-time savings (%): Unavailable.

## Conditions and measurement

```json
{
  "attempts": 1,
  "iterations": 5,
  "workers": 8,
  "llm_timeout": 90,
  "evaluator_timeout": 300,
  "case_timeout": 1800
}
```

Warmup is actual inference, excluded from evaluation metrics. Total wall time is concurrent batch wall time; average case time includes subprocess/evaluator/repair overhead. Retry calls, JEV calls and primary fallback calls count toward totals.
An inflight/error call with unavailable usage is not assigned fictional zero cost. Unknown billing suppresses token savings. Char/4 estimates are labeled and cannot establish measured token savings. Provider caches/load time may be opaque; no custom cache was added.

## Provider accounting

| Mode/provider | Calls | Reported input | Reported output | Reported total | Estimated total | Unknown usage calls | Fallback calls | Mean latency (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline/primary | 8 | 41746 | 4233 | 45979 | 0 | 0 | 0 | 5.182 |
| baseline/jev | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Unavailable |
| jev/primary | 7 | 40219 | 5061 | 45280 | 0 | 0 | 1 | 8.774 |
| jev/jev | 2 | 4871 | 118 | 4989 | 0 | 0 | 1 | 0.439 |

## Case outcomes

| Case | Baseline | JEV-like | Baseline s | JEV s |
|---|---|---|---:|---:|
| `cvdp_copilot_bus_arbiter_0001` | success | success | 43.794 | 65.415 |

## Limitations

One bounded non-agentic no-commercial native cohort, not all CVDP workflows or original default budgets. Commercial rows are explicitly excluded by actual tool requirements. API stochasticity and remote latency remain uncontrolled; single-run differences are descriptive, not statistically established effects. Repetitions/ablation must be reported only when actually executed. See environment and opportunities documents for provenance, integrity rules and remaining work.
