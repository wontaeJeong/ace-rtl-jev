# ACE-RTL measured comparison

Baseline state: `completed`; coverage 1/1.
Improved state: **Not run**.

| 지표 | Baseline | JEV-like | 변화 (JEV − baseline) |
|---|---:|---:|---:|
| 평가 케이스 수 | 1 | Not run | Unavailable |
| 성공 케이스 수 | 1 | Not run | Unavailable |
| 성공률 (0–1) | 1.000 | Not run | Unavailable |
| 총 토큰 (reported + disclosed estimates) | 3818 | Not run | Unavailable |
| 평균 토큰/케이스 | 3818.000 | Not run | Unavailable |
| 총 실행 시간 (batch wall s) | 22.913 | Not run | Unavailable |
| 평균 실행 시간/케이스 (s) | 22.911 | Not run | Unavailable |
| 주력 LLM 호출 수 | 1 | Not run | Unavailable |
| JEV-like 호출 수 | 0 | Not run | Unavailable |
| 평균 호출 지연 시간 (s) | 17.362 | Not run | Unavailable |
| 실패 및 오류 건수 | 0 | Not run | Unavailable |

Measured token savings (%): Unavailable.
Measured batch wall-time savings (%): Unavailable.

## Conditions and measurement

```json
{
  "attempts": 1,
  "iterations": 1,
  "workers": 1,
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
| baseline/primary | 1 | 1788 | 2030 | 3818 | 0 | 0 | 0 | 17.362 |
| baseline/jev | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Unavailable |

## Case outcomes

| Case | Baseline | JEV-like | Baseline s | JEV s |
|---|---|---|---:|---:|
| `cvdp_copilot_16qam_mapper_0001` | success | Not run | 22.911 | Unavailable |

## Limitations

One bounded non-agentic no-commercial native cohort, not all CVDP workflows or original default budgets. Commercial rows are explicitly excluded by actual tool requirements. API stochasticity and remote latency remain uncontrolled; single-run differences are descriptive, not statistically established effects. Repetitions/ablation must be reported only when actually executed. See environment and opportunities documents for provenance, integrity rules and remaining work.
