# 타입 명시 네이티브 CVDP / SystemOne 실행 안내

## 모드와 안전 요건

- `baseline_fixed` (기본값): 결정적 D 수정과 기존 주 모델의 생성·분석을 사용하며, `SystemOne` 호출은 없다.
- `shadow`: `SystemOne` 제안을 기록하지만 기준 실행의 동작을 수행한다. 관찰 모드의 과금은 추가 비용이지 절감이 아니다.
- `jev_core`: 타입이 명시된 적격 동작, 선택 동작의 적합도·개별 위험도 검사를 사용하며, 기존 주 모델 대체 경로를 갖춘다.
- `jev_extended`: 핵심 경로에 명시적으로 활성화한 확장을 더한다. 모든 X 플래그의 기본값은 거짓이다.
- `legacy`: 호환 제어 경로이며, 정확한 원본 기준 실행이 **아니다**. A에는 원본 참조 소스를 사용한다.

실제 필수 CVDP 서비스 결과만 통과(`PASS`)를 확정할 수 있다. 비어 있거나 잘못된 결과, 생략된 필수 검사, 시간 초과, 취소, 모델 답변으로는 확정할 수 없다. 소스 증상 식별자는 입증된 원인이 아니다. 누락 지표와 미확인 단가는 0이 아니다.

생성기는 준비된 주 어댑터·모델을 그대로 사용한다. `SystemOne`은 RTL을 작성하지 않는다. 입력은 행에 선언된 공개 명세·맥락, 모든 변경 가능 대상, 생성 후보와 정제된 출력 진단이며, 비공개 검사기·참조 코드나 `.env` 내용이 아니다.

## 준비된 설정

기존 `.env.local`은 보존한다. 해당 변수를 로컬에서 내보내거나, 값을 출력하지 않고 불러오는 `decision_compare.py`를 사용한다. 원래 어댑터는 `ACE_RTL_LLM_SCRIPT`를 통해 사용하는 `scripts/local_llm_adapter.py` 그대로다.

| 새 설정 | 기존 별칭·기본값 |
|---|---|
| `SYSTEMONE_ENDPOINT_URL` | `JEV_ENDPOINT_URL`; 전체 URL 사용, `/v1` 자동 추가 없음 |
| `SYSTEMONE_MODEL` | `JEV_MODEL`; `LLM_MODEL`과 별도 |
| `SYSTEMONE_API_KEY` | `JEV_API_KEY`; 로그에 기록하지 않음 |
| `SYSTEMONE_PROVIDER` | `JEV_PROVIDER`; `typesafe`, `ollama` 또는 기능이 미확인인 `systemone` |
| `SYSTEMONE_TIMEOUT_SECONDS` | `JEV_TIMEOUT_SECONDS`, `JEV_REQUEST_TIMEOUT`; 기본값 15, 공통 기한으로 제한 |
| `ACE_RTL_POLICY_FILE` | 명시적 JSON 임계값·한도; 기본값은 실험적이며 보정되지 않음 |
| `ACE_RTL_QUESTION_SCHEMA_VERSION` | `jev-questions-1`; 미확인 등록부 버전 거부 |
| `ACE_RTL_RUN_BUDGET_FILE` | 기존 불변 실험과 범위별 할당량을 가리키는 선택적 JSON |
| `ACE_RTL_RUN_WALL_SECONDS` | 1800 |
| `ACE_RTL_TASK_WALL_SECONDS` | 1200 |
| `ACE_RTL_ATTEMPT_WALL_SECONDS` | 600 |
| `ACE_RTL_EVALUATION_CACHE_MODE` | `off`; `deterministic`은 검증된 결정성·시드·완전한 도구·실행 기반·설정 해시도 요구 |

공급자마다 기능이 다르다. 임의의 프록시에 `TypeSafe`의 한도를 가정하지 않는다. 응답에 되돌아온 별칭은 고정된 가중치 버전이 아니며, 실제 모델 해석이 미확인이면 보수적으로 원시 답변 재사용을 끈다. 판단 기본 요소인 `Choice`/`Noul`/`Score`의 분포는 보존한다. TLS 검증을 활성화하고 기존 프록시·CA 설정을 따른다.

## 제한 예산 내 호출 승인

`ACE_EXPERIMENT_BUDGET_FILE` 없이는 유료 추론을 승인하지 않는다. 새 예산 배정에는 **새로운** 실험 원장을 사용하며, 소진한 실험을 초기화하지 않는다. 기존 SQLite 승인 체계는 주 모델·기존 모델 대체 경로·재시도·준비 호출·JEV 호출이 공유한다.

```bash
.cvdp-native/bin/python scripts/inference_budget.py outputs/<new-run>/campaign.sqlite --init
export ACE_EXPERIMENT_BUDGET_FILE="$PWD/outputs/<new-run>/campaign.sqlite"
export ACE_RTL_LLM_SCRIPT="$PWD/scripts/local_llm_adapter.py"
export PATH="$PWD/.cvdp-native/bin:$PATH"
```

기본 초기 예산은 의도적으로 작다. 주 모델은 HTTP 시도 12회 / 토큰 노출 300,000개, JEV는 시도 64회 / 토큰 노출 1,000,000개 / 비용 노출 $0.10이다. 과금이 미확인이면 예약을 유지한다. 토큰 예약은 보수적인 UTF-8 입력 노출에 래퍼·출력 허용량을 더한 것으로, 불투명한 공급자 내부 처리에 대한 검증된 상한은 아니다. 단가 영수증 없이는 주 모델의 USD 비용이 미확인이며, 무조건적인 금액 보장에는 공급자 측 크레딧 상한이 필요하다.

선택적 실행 예산 JSON 예시(유료 예약 **전에** 범위별 할당량 초기화):

```json
{
  "campaign_file": "campaign.sqlite",
  "run_wall_seconds": 600,
  "task_wall_seconds": 240,
  "attempt_wall_seconds": 180,
  "scope_limits": {
    "task": {"primary": {"max_calls": 6, "max_tokens": 250000}},
    "attempt": {"primary": {"max_calls": 6, "max_tokens": 250000}}
  }
}
```

범위별 할당량은 실행·과제·시도별 이름 공간에서 원자적 예약·정산을 사용한다. 전체 지출을 초기화하거나, 범위 표기가 없는 과거 예약에 소급 적용할 수 없다. 예산을 관리하는 다른 어댑터는 `ACE_RTL_ADAPTER_BUDGET_MANAGED=1`을 명시해야 하며, 준비된 어댑터는 자동으로 인식한다.

## 실제 간이 검증 1회 후 수정 실행

실제로 설치된 비상용 도구용 데이터셋을 사용하고 도구 사전 점검부터 수행한다. 소규모 실험에 네이티브 기본값을 그대로 사용하지 않는다.

```bash
.cvdp-native/bin/python skills/ace-rtl/scripts/ace_cvdp_native_runner.py \
  --workspace "$PWD" \
  --dataset datasets/cvdp-benchmark-dataset/cvdp_v1.1.0_nonagentic_code_generation_no_commercial.jsonl \
  --cid cid002 --id cvdp_copilot_bus_arbiter_0001 \
  --generator-model "$LLM_MODEL" --reflector-model "$LLM_MODEL" --coordinator-model "$LLM_MODEL" \
  --attempts 1 --datapoint-workers 1 --max-iterations 1 \
  --llm-timeout 60 --evaluator-timeout 60 --decision-mode baseline_fixed
```

제한 예산 수정 실행에는 `--max-iterations 2 --decision-mode jev_core`로 변경한다. 초기 통과(`PASS`)는 생성·평가를 입증하지, 수정·의사결정 분기를 입증하지 않는다. 인증·설정 오류는 기반 환경·계약 실패이며, 후보 실패나 성공으로 취급하지 않는다.

## A / B / C

기록된 원본 커밋에서 전용 원본 소스 참조 워크트리를 만들거나 읽되, `main`은 변경하지 않는다. CVDP 체크아웃과 데이터셋은 그 참조 작업 공간에 로컬로 있어야 한다. 비교는 시도 1회, 작업자 1명, 최대 반복 3회, 명시적 과제 식별자 최대 4개로 실행한다.

```bash
.cvdp-native/bin/python skills/ace-rtl/scripts/decision_compare.py \
  --dataset datasets/cvdp-benchmark-dataset/cvdp_v1.1.0_nonagentic_code_generation_no_commercial.jsonl \
  --id cvdp_copilot_bus_arbiter_0001 \
  --reference-workspace /path/to/original-reference-worktree \
  --output outputs/<new-comparison> --iterations 2 \
  --llm-timeout 60 --evaluator-timeout 60 --case-timeout 240
```

A는 원본 소스, B는 수정된 기준 실행, C는 핵심 경로다. 기존 주 어댑터는 공통 엔드포인트 연결에 필요한 조정이다. 원본 서비스 기록에는 식별자가 없다. 검증기는 정확한 기존 보고서 이름 결합을 허용하며, A에 한해서만 명시적으로 기록된 단일 서비스 명세 결합도 허용한다. `tests=[]`는 절대 허용하지 않는다. 준비 호출은 별도로 구분하며 X 플래그는 강제로 끈다. 단일 확률적 표본은 기술적 설명일 뿐, 비열등성이나 인과적 속도 향상의 증거가 아니다.

## 산출물과 되돌리기

각 시도는 과제 계약, 모드·정책·모델 메타데이터, 원시·정규화 후보, 실제 준비된 `tested_candidate/`, 불변 관측·효과·보관 항목을 유지한다. `candidate_manifest.json`은 원시·정규화·검사 대상 해시를 구분한다. CVDP 준비 과정이 정규화된 바이트를 바꿀 수 있기 때문이다.

- `events/`: 디스크 동기화된 프로세스별 호출·평가·동작·종료 기록; 임시 작업 파일과 분리한다.
- `calls/attempt_<n>/`: HTTP 영수증과 허용된 요청·답변 산출물; 헤더·자격 증명은 없다.
- `iter_<n>/observation.json`, `effect.json`, `decision.json`, `action.json`: 명시적인 상태·동작·결과 연결.
- `real_evaluator_result.json`: 권위 있는 서비스 결과; 보조 출력의 잘림만으로 진짜 결과를 무효화하지 않는다.
- `first_pass_claim.json`: 검증된 명세·결과 해시를 참조하는 잠금 기반 원자적 공개; 손상된 주장은 보존하고 복구한다.
- `candidate_archive.json`, 되돌리기·진단 기록: 추가만 가능한 출처 이력 참조이며 새 측정이 아니다.

`rollback_best`는 보관된 묶음·관측을 선택한다. 지출을 환불하거나 반복·기한·버전을 되감고, 취소를 지우거나 과거 평가를 새 평가로 바꾸지 않는다. `fresh_start`는 새 에피소드를 만들고 활성 로컬 수정 맥락을 비우지만, 전체 원장을 지우지는 않는다. 패자 정리는 후보·호출·결과를 유지하고 큰 임시 작업·빌드 산출물만 제거한다. 로컬 요청을 종료했다고 상위 서비스 과금이 중단되었다는 증거가 되지는 않는다.

## 선택적 확장과 오프라인 작업

`ACE_RTL_ENABLE_BEAM`, `ACE_RTL_ENABLE_ADAPTIVE_SCHEDULING`, `ACE_RTL_ENABLE_MODEL_ROUTING`, `ACE_RTL_ENABLE_LESSON_MEMORY`, `ACE_RTL_ENABLE_LEARNED_POLICY`는 기본값이 거짓이며 `jev_extended`가 필요하다.

모델 선택은 사용자가 제공한 `ACE_RTL_MODEL_ALIASES`만 허용한다. 기억 기능에는 명시적으로 고정된 스냅샷·버전이 필요하다. 네이티브 실행은 검증용 표본의 학습 산출물을 거부하며, 별도로 검증된 산출물과 고정 버전이 필요하다. 작업 배정은 점검 지점에서 다음 반복을 승인하는 방식이지 프로세스 일시 중지·재개가 아니며, 종료된 진행 중 요청을 환불로 집계하지 않는다.

```bash
.cvdp-native/bin/python skills/ace-rtl/scripts/decision_offline.py train --help
.cvdp-native/bin/python skills/ace-rtl/scripts/decision_offline.py evaluate --help
.cvdp-native/bin/python -m pytest -q
```

오프라인 레이블에는 실행 동작 → 유효한 다음 평가기 결과의 연결이 필요하다. 특성은 의사결정 시점의 정보만 사용하고, 설계 계열별로 분할한다. 개발용 질문 제안·견고성 API는 `decision/offline.py`에 있다. 실행 중 질문을 자체 수정하거나 별도 평가용 데이터를 검사하지 않는다. 검증용 표본 처리 과정의 정확도는 모델 정확도, 종단간 개선 또는 실제 데이터 학습 완료를 뜻하지 않는다. 전체 완료·실험 상태는 최종 보고서에 별도로 기록했다.
