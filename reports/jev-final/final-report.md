# ACE-RTL JEV-like 최종 제한 예산 검증 보고서

**범위:** 기존 292-case Baseline 재사용, 판단 지점 48개 + 실제 CVDP 1개 E2E. 전체 292개 개선 버전 평가는 실행하지 않았다.
**결과를 구분한다:** 판단 API 비용 실험은 전체 RTL 성공률 실험이 아니다. 1-case 결과는 일반화·통계적 우위를 입증하지 않는다.

**핵심 결론:** 소규모 실측은 전체 JEV 기본 적용의 개선을 입증하지 않는다. 실측 case 토큰 45979 → 50269 (+9.33%), 평균 case 시간 43.794 → 65.415 s. 실제 primary fallback 1회. 원래 batch 동시 실행 조건이 달라 시간 차이를 통제된 속도 차이로 해석하지 않는다.
판단 감사는 48회 중 45개 schema-valid /3개 decision error, 수용 13개 /would-fallback 35개였다. 옛 primary 문장 휴리스틱과 19개 중 1개 일치(ground truth 아님), 공식 all-pass 12개 중 12개 resolved였다. 수용 부분집합 토큰 감소만으로 전체 최적화를 주장하지 않는다.
수용 판단 13개 중 11개는 이미 공식 evaluator가 all-pass인 상태였다. 따라서 단순히 성공을 확인하는 데 모델을 쓰지 않는 결정적 terminal 처리부터 오프라인 검토할 가치가 있다. 해당 개선은 이번에 구현/추가 실험하지 않았으며 절감을 실제 성과로 계산하지 않는다.
따라서 baseline을 기본으로 유지하고 JEV 경로를 실험적 opt-in으로 둔다. 남은 예산을 이유로 재시도·추가 cohort를 실행하지 않았다.

## 1. 판단 지점 실측

| 항목 | 결과 |
|---|---:|
| selected_count | 48 |
| executed_count | 48 |
| valid_decisions | 45 |
| decision_errors | 3 |
| accepted_decisions | 13 |
| would_fallback_count | 35 |
| historical_primary_tokens | 622384 |
| actual_jev_tokens | 159308 |
| actual_jev_usd_known | 0.006569219999999998 |
| unknown_jev_usage_calls | 0 |
| accepted_point_token_reduction_percent | 75.68949580107383 |
| primary_proxy_labeled_count | 19 |
| primary_proxy_agree_count | 1 |
| all_pass_oracle_count | 12 |
| all_pass_resolved_count | 12 |

각 snapshot의 원래 주력 LLM 요청을 생성 후보·실제 emitted 보고서·role metadata로 재구성하고 원본 API event SHA256의 정확한 일치를 요구했다. 원본 판단 토큰은 과거 실제 측정이며 새 주력 호출로 재측정하지 않았다.
JEV는 bounded state와 finite-label 출력만 사용한다. 기존 주력 LLM의 풍부한 변경 분석/설명과 정보량이 같지 않으므로 토큰 감소에는 정확도·정보 손실 trade-off가 있다.
accepted_point_token_reduction_percent는 **확신 기준을 통과한 판단 부분집합만의** 원본 기록 대비 실제 JEV 토큰 감소이며 전체 agent 절감률이 아니다. 실패·불확실 판단의 실제 JEV 비용은 모두 포함했다.
primary_proxy_agreement는 추출한 옛 primary 문장과의 휴리스틱 일치이며 ground truth가 아니다. all-pass subset에서는 공식 evaluator가 통과한 경우 resolved인지 제한적으로 확인했다.
감사 단계에서는 추가 주력 fallback을 구매하지 않았다. would-fallback과 actual fallback을 혼동하지 않는다. 다음 값은 실제 지출이 아닌 **원본 fallback 토큰을 재사용한 시나리오 추정**이다:
`hypothetical_tokens_with_historical_fallback = 629153`.

## 2. 실제 CVDP E2E

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


## 3. 비용 제어와 원본 보존

주력 API 12회/예약 300,000 tokens, JEV 64회/예약 1,000,000 tokens/USD 0.10 노출 한도. 공유 SQLite가 warmup·재시도·실제 fallback까지 포함한다. redirect 재전송을 차단하고, token 정보 없는 실패도 예약을 유지하며, 답변이 잘못돼도 유효한 USD 영수증은 정산한다.
입력 UTF-8 bytes + wrapper/output allowance 예약은 opaque provider의 절대 요금 보증이 아니다. 주력 가격 API는 model ID만 제공하여 정확한 주력 USD와 전체 비용을 만들지 않았다. JEV receipt USD는 OpenRouter 공식 문서로 확인했다. 서버측 credit cap이 필요하면 운영자가 설정해야 한다.
Baseline은 다시 실행하지 않았다. 292-case clean baseline은 239 success / 52 failure / 1 timeout, 4,367.250 s, 알려진 16,538,281 tokens +33 usage-unknown calls로 보존돼 있다.

## 4. 해석·한계·후속 방향

1-case E2E에서 토큰이 늘거나 지연이 증가하면 그대로 보고한다. 원래 292-case batch와 달리 새로운 한 케이스만 실행했으므로 historical per-case 시간 차이를 통제된 batch speedup으로 주장하지 않는다.
판단 실패/낮은 confidence/낮은 proxy agreement가 많으면 원래 주력 경로를 유지하는 것이 합리적이다. 코드 생성과 깊은 수정 추론은 대체하지 않았다. 비용이 남았다는 이유로 추가 실험을 임의로 확대하지 않는다.
추가 설계: 목표 오류 식별과 report compaction 품질을 먼저 오프라인 보완하고, 더 큰 paired cohort/반복/ablation은 별도 예산을 정한 뒤 수행한다. 현재 그런 실험은 NOT RUN이다.

## 5. 재현 경로

- Study: `experiments/studies/jev-budgeted-20261011-reviewed`
- Actual E2E: `/Users/wt.jeong/workspace/ACE-RTL/.worktrees/ace-rtl-e2e/experiments/runs/jev-20261011T140333Z-87520`
- CLI / 설정: `docs/experiments/jev-guide.md`
- 원본 JSON/CSV/API events와 budget JSON snapshots는 저장소에, private harness/입력과 SQLite binary는 로컬 ignored 영역에 유지한다.
