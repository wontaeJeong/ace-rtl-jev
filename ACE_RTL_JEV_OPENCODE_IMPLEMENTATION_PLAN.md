# ACE-RTL × JEV/SystemOne — OpenCode 전체 구현 작업지시서

작성일: 2026-10-11 (Asia/Seoul)  
조사 대상: [NVlabs/ACE-RTL](https://github.com/NVlabs/ACE-RTL)  
조사 기준 커밋: `94754d796350d42502c9a32639a20d86f50e9678`  
목표: ACE-RTL의 관찰·판단·수정·검증 루프를 개선하고, 실제 `/v1/systemone`의 `choice`·`noul`·`score`와 전체 확률 분포를 활용한다.

> OpenCode에게: 이 문서는 구현 지시다. 현재 체크아웃을 조사한 뒤 코드 수정, 필요한 테스트, 설정·실행 문서, 비교 실험까지 진행하라. 계획이나 일반적인 제안만 작성하고 종료하지 말 것. 생성형 LLM 및 JEV의 endpoint/key/model은 사용자가 준비한 환경 설정을 재사용한다. 비밀값을 이 문서·코드·로그에 복사하지 않는다.

## 0. 범위, 실행 원칙, 완료 수준

1. 아래 경로와 행 번호는 조사 기준 커밋의 위치다. 현재 HEAD와 다르면 함수·호출 관계로 대응 지점을 찾는다. 사용자의 변경을 되돌리거나 조사 커밋으로 강제 checkout하지 않는다.
2. 먼저 `AGENTS.md`, 프로젝트 지침, `skills/ace-rtl/SKILL.md`, `skills/ace-rtl/references/agent-components.md`, CVDP 실행 문서를 읽는다. 아래 내용과 구현이 달라졌으면 실제 코드 근거를 남긴다.
3. **native CVDP 경로를 우선 완성한다.** 공통 컴포넌트를 쓰는 기존 agent 경로도 호환성을 확인한다. 실행되지 않는 클래스만 수정해 완료 처리하지 않는다.
4. `D-*`는 상태·실행·측정 기반 수정, `J-*`는 핵심 JEV 기능이다. 둘 다 기본 구현 범위다. `X-*`는 실험 기능으로 코드·설정·테스트를 구현하되 기본 비활성화한다. 학습에 필요한 실제 데이터가 부족하면 학습 파이프라인과 작은 fixture 검증까지 완료하고 실데이터 학습 미완료를 명시한다.
5. 자유로운 RTL 작성, 복잡한 원인 설명, 새 수정안·새 교훈 작성은 생성형 LLM이 맡는다. JEV는 제공된 증거와 후보에 대해 판단한다.
6. PASS는 유효한 실제 CVDP evaluator 결과만 결정한다. JEV, LLM, 로그 속 PASS 문자열, 빈 결과는 성공 근거가 아니다.
7. CVDP에서 허용하는 공개 명세·공개 context·생성 대상·sanitized diagnostics만 모델 입력으로 사용한다. 숨겨진 checker/reference 구현·정답·mutation 정의를 새롭게 노출하지 않는다. 기존 비공개 경계도 점검한다.
8. E2E 결과를 만들거나 추정값을 실측값으로 적지 않는다. endpoint/EDA/dataset이 없으면 구현과 로컬 검증은 계속하고 해당 실험만 정확한 사유와 재실행 명령으로 남긴다.
9. 모델·정책·질문·명세·harness·도구 버전과 실행 예산을 기록한다. 실행 도중 질문·threshold·model alias가 바뀌지 않게 고정한다.
10. 기존 생성형 LLM이 사용자 adapter로 연결되어 있으면 유지한다. JEV를 붙이기 위해 모든 role model을 JEV 이름으로 바꾸지 않는다.

## 1. 실제 실행 경로와 수정 위치 지도

이하 `S`는 `skills/ace-rtl/scripts/`이다. `N`은 `S/ace_cvdp_native/`, `A`는 `S/ace_rtl_agent/`다. 약어는 문서용이며 실제 디렉터리를 새로 만들라는 뜻이 아니다.

native 경로:

```text
S/ace_cvdp_native_runner.py
  -> N/cli.py::main / run_datapoint / run_attempt
  -> N/llm.py::AceIterationModel.prompt
  -> S/llm_call.py -> A/llm_backend.py 또는 기존 사용자 adapter
  -> 실제 CVDP processor.run / N/harness.py
  -> N/llm.py::record_reflector_iteration_result
  -> N/llm.py::call_coordinator -> A/fresh_start_coordinator.py
  -> N/llm.py::call_reflector -> A/focused_debugger.py의 mixin
  -> 다음 candidate 생성
```

기존 agent 경로는 `S/ace_agent_runner.py -> A/main.py -> A/agent.py -> A/agent_loop.py`이며 native와 동일한 코드가 아니다. 특히 native에 없는 best-code 보존이 `agent_loop.py`에는 존재한다.

| 기존 파일 | 확인할 함수·대략적 위치 | 이 문서에서의 수정 역할 |
|---|---|---|
| `N/cli.py` | `run_attempt` 81~, `run_datapoint` 437~, CLI 715~ | 공통 상태, 종료 순서, multi-file, decision 적용, 병렬 시도·예산·보고 |
| `N/llm.py` | `AceIterationModel.prompt` 114~, `build_reflector_harness_context` 330~, `call_reflector` 412~, `record_reflector_iteration_result` 468~, `call_coordinator` 526~ | 생성/판단 분리, bundle 전달, reflection 계약, 관측·행동 연결 |
| `N/diagnostics.py` | `summarize_result` 442~, `primary_failure_from_summary` 473~, `primary_failure_from_attempt_error` 507~ | 실행 사실 정규화, timeout/unknown 구분, 오류 ID |
| `N/harness.py` | `native_obj_harness` 403~, `result_passed` 511~ | 명시적인 실행 단계·서비스 결과·PASS 유효성 |
| `N/processes.py` | `cleanup_attempt_root` 232~, `try_claim_first_pass` 249~, `read_first_pass_claim` 277~ | 기록 보존, 원자적 winner 게시, crash 복구 |
| `N/config.py` | `classify_task` 333~, guidance/system prompt helpers | metadata 기반 task contract 공유 |
| `N/sv.py` | `normalize_generated_sv` 496~, bundle/hash helpers 610~ | raw/normalized/tested candidate provenance, deterministic cache key |
| `A/focused_prompting.py` | `create_focused_prompt` 14~, focus logic 260~ | canonical task kind, 오류 상태 전환, 선택 context 조립 |
| `A/focused_history.py` | `record_attempt` 14~, prose predicates 53~129, `_build_history_trajectory` 235~, stall 308~ | typed 오류 상태, 회귀 분리, episode/history 선택 |
| `A/focused_guidance.py` | `extract_implementation_changes` 172~, truncation 265~, `parse_test_results` 403~ | bundle diff, 문장 제어 제거, 구조화 결과 우선 |
| `A/focused_error_analysis.py` | `_is_compilation_error` 14~, `_extract_and_analyze_error` 127~, `_generate_code_related_reasoning` 310~ | 실제 compile 상태, 선택적 생성형 분석 |
| `A/focused_task_detection.py` | task detectors 14~201, optimization guidance 248~ | 부정문·코드 이름에 의한 task drift 제거, 서비스별 지침 |
| `A/focused_debugger.py` | `__init__`, `clear_history` 67~ | 상태/decision client 주입, episode 초기화 |
| `A/focused_debugger_types.py` | `FixAttempt` | observation/action/effect IDs, nullable metrics |
| `A/fresh_start_coordinator.py` | `mark_fresh_start` 84~, `should_fresh_start` 121~, analysis 181~, lessons 690~ | episode, typed next action, bounded restart |
| `A/rtl_rule_advisor.py` | `retrieve_rules_from_specification` 61~, `reset_session` | rule별 noul/score, 오류·빈 결과 구분, cache |
| `A/utils/llm_client.py` | `call_llm` 179~ | timeout 실제 적용, 공통 response envelope, 모든 retry 계측 |
| `A/llm_backend.py` | `_get_model_response` 631~, `complete_messages` 646~, `prompt` 670~ | usage 보존, call context, deadline 전달 |
| `S/llm_call.py` | role 호출·retry·결과 저장 | generator를 포함한 공통 ledger |
| `A/agent_loop.py`, `agent_reporting.py`, `agent_types.py` | loop/config/report | 기존 agent 호환, 공통 기능 재사용 |

파일을 수정하기 전에 실제 active call graph를 `docs/jev_integration_audit.md`에 기록한다. 위 표의 함수명을 그대로 믿고 미사용 경로에만 코드를 붙이지 않는다.

## 2. 확인된 결함과 재현 범위

아래 항목은 코드 정적 분석 및 일부 함수의 작은 입력 재현 결과다. 전체 CVDP 성능 저하나 발생 빈도를 측정했다는 뜻은 아니다.

| ID | 발견 | 코드 근거 | 기대 수정 |
|---|---|---|---|
| F01 | `not fixed`가 solved로, `Solved; no new errors introduced`가 regression으로 해석될 수 있음 | `A/focused_history.py:53–129` | 문자열 표현에서 제어 상태를 분리 |
| F02 | A를 해결하고 runtime 오류 B가 나타나도 A에 계속 집중 가능 | history 69–86 + prompting 260–301 + native mismatch=-1 | A 해결 여부와 B의 회귀 여부를 독립 상태로 관리 |
| F03 | native mismatch=-1, signal 정보=None. 일부 stall/oscillation 감지가 작동하지 않음 | `N/llm.py:430,480–539` | 실제 가능한 지표 연결, 누락은 unknown |
| F04 | 첫 평가가 focused history에 없어서 첫 수정의 개선을 놓칠 수 있음 | `N/llm.py:477–497` | baseline observation을 항상 기록 |
| F05 | multi-file 생성은 지원하지만 reflector·수정 효과는 첫 파일 중심 | `N/cli.py:97–98,174–176,247–254,338–347` | 전체 bundle과 변경 파일 전달 |
| F06 | 두 번째 generated RTL target이 immutable/helper로 표시 가능 | `N/llm.py:396–407` | 모든 mutable targets를 immutable context에서 제외 |
| F07 | `Do not add assertions`가 assertion task, `helper u_dut()`가 verification task로 판정 가능 | `A/focused_task_detection.py:14–41,78–138` | metadata/명세 기반 task contract 고정 |
| F08 | `iverilog compilation successful` + runtime 오류도 compilation error로 분류 가능 | `A/focused_error_analysis.py:14–48` | tool 이름과 실행 실패를 구분 |
| F09 | `sanity: PASS` + `synth: FAIL`에 두 서비스 모두 실패했다는 guidance 생성 | `A/focused_task_detection.py:267–285` | 서비스 ID별 관측 상태로 지침 선택 |
| F10 | 같은 failure의 중복 언급을 여러 테스트 실패로 셀 수 있음 | `A/focused_guidance.py:430–435` | test ID/구조화 결과 기반 count |
| F11 | native evaluator timeout이 일반 functional failure가 될 수 있음 | `N/harness.py:466–469`, diagnostics 479–496 | timeout/unknown execution 독립 분류 |
| F12 | `{errors:0, tests:[]}`가 PASS | `N/harness.py:511–514`, 작은 입력으로 확인 | required service와 결과 유효성 검증 |
| F13 | PASS를 안 뒤 회고 LLM 호출, 마지막 실패 뒤 coordinator 호출 가능 | `N/cli.py:199–201,247,275,301,325` | terminal gate를 optional inference 앞에 배치 |
| F14 | infrastructure 종료와 sibling 성공이 같은 stop_event 사용 | `N/cli.py:132–137,200–201,284–299` | typed cancellation cause |
| F15 | sibling 종료 시 전체 attempt 디렉터리 삭제 | `N/cli.py:415,471–490`, processes 232–242 | 비용·증거 저장소와 scratch 분리 |
| F16 | winner claim 파일 생성 후 JSON 기록. crash 시 partial 파일로 승자 게시가 막힐 위험 | `N/processes.py:268–284`, `N/cli.py:201,425–433` | 검증 manifest와 원자적 claim 게시·복구 |
| F17 | reflector/coordinator timeout 인자 미사용, text 경로에서 usage 유실 | `A/utils/llm_client.py:179–204`, backend 631–668 | 모든 role에 공통 deadline·usage 계약 |
| F18 | reflection 속 full prompt와 generator의 spec/이전 코드 중복 | `N/llm.py:152–173,443–451` | structured reflection에서 한 번만 compose |
| F19 | 현재 episode 재시작 판단에 이전 episode 전체 history가 섞임 | `A/fresh_start_coordinator.py:84–92,194–218` | episode별 evidence와 교훈 분리 |
| F20 | `error_reasoning` metadata에 실제 reasoning 대신 fix guidance 저장 | `N/llm.py:438–440` | 필드 의미대로 저장 또는 부정확한 필드 제거 |

추가 범위 주의:

- RTL rule DB는 현재 `ARCH_001`, `ARCH_002` 두 개다. rule selection만으로 큰 E2E 개선을 주장하지 않는다.
- native restart는 `FreshStartCoordinator.generate_fresh_rtl()`이나 `_llm_extract_high_level_lessons()`를 호출하지 않는다. candidate/history를 비우고 고정 지침으로 다음 generator를 실행한다. 교훈 큐레이션은 native에는 새 기능이다.
- `ContextBuilder`/`IterationMemory`/`ComprehensiveReasoningCoordinator`는 활성 호출을 먼저 확인한다. 조사본에서 `iteration_memory.py`의 `re` import 누락 및 coordinator의 `DebugContext` import 불일치가 보였다. 미사용이면 감사 문서에 기록하고 핵심 통합 경로로 삼지 않는다. 연결하려면 해당 오류부터 테스트한다.

## 3. 권장 모듈 분리와 공통 데이터 계약

기존 구조에 맞춰 `A/decision/` 패키지를 추가하는 것을 권장한다. 아래는 **새 파일 제안**이며 이름은 기존 관례에 맞게 조정할 수 있다. 기존 구현이 있으면 중복 계층을 만들지 말고 통합한다.

| 새 모듈 제안 | 책임 |
|---|---|
| `types.py` | TaskContract, Observation, Evidence, CandidateBundle, Action, Decision, Effect |
| `systemone_client.py` | 순수 `/v1/systemone` transport·typed validation·provider capabilities |
| `questions.py` | 버전이 있는 질문·criteria·동적 후보 구성 |
| `state_builder.py` | 허용된 관측 자료만으로 bounded state 구성 |
| `policy.py` | eligibility, abstention, threshold, action commit, fallback |
| `context_selector.py` | 규칙·history·로그 evidence 선택과 token packing |
| `ledger.py` | call/action/evaluation event 및 usage 저장 |
| `budget.py` | deadline·call/token/cost budget과 reservation |
| `cache.py` | decision cache, 검증된 deterministic evaluation cache |
| `strategies.py` | 닫힌 repair/diagnostic 전략 registry |

필수 객체와 필드:

| 객체 | 필수 내용 |
|---|---|
| `TaskContract` | task_id, CID/category, task_kind, 공개 spec hash, 전체 mutable target IDs/paths, immutable context, required evaluator services, 허용 도구/전략 |
| `CandidateBundle` | candidate_id, parent_candidate_id, episode_id, raw/normalized/tested bundle hash, 모든 파일 hash, 실제 변경 파일·diff, normalization actions |
| `Observation` | observation_id/version, task/attempt/episode/iteration, tested bundle hash, evaluator status, evaluation_validity와 diagnostic_completeness, service별 상태, 실행·미실행·skip test IDs(제공될 때), nullable metrics, metric comparability key, evidence IDs, budget snapshot |
| `Evidence` | 안정적 ID, 출처, candidate/observation 연결, 공개 여부, kind, bounded text/structured values, truncation·availability 표시 |
| `ProposedAction` | action_id, observation_id, action_kind, target IDs, error/hypothesis/strategy IDs, eligibility 근거, 적용 전제조건 |
| `DecisionRecord` | raw answers/distributions, requested/resolved model, schema/policy version, chosen action, abstention/fallback 이유, latency/usage |
| `EffectRecord` | before/after observation IDs, action ID, 실제 변경 bundle, target error 상태, 새 failure·회귀·미실행 구분, 관측된 metric delta |

`mismatch_count=-1`나 `0/0 tests`를 유효한 실측값으로 다루지 않는다. 새 타입에서는 `null` + availability/reason을 쓰고, 구형 인터페이스에만 필요한 변환을 둔다. “로그에 없다”는 것은 “해결됨”이 아니다.

오류 상태는 최소 다음을 구분한다:

```text
persists             같은 오류가 실제 관측됨
observed_resolved    대응 검사가 실제 실행되어 통과한 증거가 있음
masked               앞선 compile/setup 실패 등으로 해당 검사가 가려짐
not_executed         해당 검사가 실행되지 않았음
unknown              판단에 필요한 관측이 부족함
```

새 failure도 `newly_reached_failure`와 `confirmed_regression`을 분리한다. 기존에 실행되지 않던 검사가 처음 실패했다고 바로 회귀로 표시하지 않는다.

## 4. D — JEV 적용 전 필수 기반 수정

### D-01. TaskContract를 한 번 결정하고 모든 role에 전달

수정: `N/config.py::classify_task`, `N/cli.py::run_attempt`, `N/llm.py::AceIterationModel.prompt`, `A/focused_task_detection.py`, `focused_prompting.py`, `focused_error_analysis.py`.

- dataset/category/declared targets를 우선 사용해 task_kind를 결정한다. category 인자가 있어도 다시 prompt keywords만으로 무시하는 흐름을 제거한다.
- metadata가 부족할 때만 공개 명세 기반 fallback을 사용한다. JEV 모호성 분류는 J-07에서 추가한다.
- generated code의 `u_dut`, `$error`, `assert`가 과제의 목적 자체를 변경하게 하지 않는다.
- generator/reflector/coordinator가 같은 task_kind와 output contract를 받도록 한다.
- `sanity`/`synth`/coverage/assertion 지침은 해당 서비스의 실제 상태에만 연결한다.
- 검증: F07–F09의 입력 및 외부/내부 reflector의 task kind 일치.

### D-02. evaluator 관측을 정규화하고 PASS를 강화

수정: `N/harness.py::native_obj_harness/result_passed`, `N/diagnostics.py`, `N/llm.py::build_evaluator_error_report/record_reflector_iteration_result`.

- 명시적으로 확보한 실행 사실과 추론을 다른 필드에 둔다. 로그 요약이 원본 structured result를 덮어쓰지 않게 한다.
- 최소 stage: `LOCAL_PREFLIGHT`, `INFRA_SETUP`, `CANDIDATE_COMPILE`, `CANDIDATE_FUNCTIONAL`, `EVALUATOR_TIMEOUT`, `INVALID_EVALUATION`, `UNKNOWN`, `PASS`. 필요하면 task별 coverage/optimization 세부 상태 추가.
- timeout exit 124/error metadata를 직접 사용한다. timeout만으로 “compiled and ran”이라고 쓰지 않는다.
- result schema, `errors`, 필수 service의 존재·완료·상태, tested bundle 대응을 검증한 뒤 PASS 허용. dataset별 조건부 service가 있으면 expected service manifest에 반영한다.
- 필수 tests가 비어 있거나 authoritative 결과가 누락·손상되어 유효한 평가를 확인할 수 없으면 invalid/incomplete이며 PASS가 아니다. authoritative 결과 parser 실패와 선택적 diagnostics parser 실패를 구분한다.
- `evaluation_validity`와 `diagnostic_completeness`를 분리한다. 필수 서비스의 structured result와 tested bundle이 유효하면 보조 로그 또는 모델 입력의 truncation만으로 PASS를 무효화하지 않는다.
- 테스트 수는 structured results와 stable test IDs를 이용한다. 지원되지 않는 harness는 수를 unknown으로 둔다. `passed`/`failed` 단어 출현 수 계산을 control metric에서 제거한다.
- 값 비교·count·delta·PPA arithmetic는 코드에서 계산한다. JEV에 세어 달라고 하지 않는다.
- metric 비교 키에 service, testset, parameterization, seed, harness/tool/config 버전을 포함한다. count delta·개선율·best candidate 비교 전에 키와 실제 실행 test 집합·분모를 확인한다. 실행 집합이 달라지면 비교 가능한 부분만 명시하거나 incomparable로 남긴다. 새로 도달한 검사 2개의 통과를 이전 검사 1개의 통과보다 자동으로 개선이라고 하지 않는다.
- functional failure를 모두 같은 generic signature로 축약하지 않는다. 제공 가능한 service/test/signal/failure stage 정보를 써서 candidate error IDs를 만든다. signature는 진짜 원인 ID라고 단정하지 않는다.

### D-03. multi-file을 end-to-end 단위로 수정

수정: `N/cli.py::run_attempt`, `N/llm.py::call_reflector/record_reflector_iteration_result/build_reflector_harness_context`, `A/focused_guidance.py` 및 필요한 prompting 타입.

- `target_files` 전체를 전달하고 첫 파일은 표시용 primary로만 사용한다.
- reflector와 retrospective에 bundle manifest·파일별 diff·관련 code를 제공한다. 두 번째 파일만 바뀌어도 변경으로 기록한다.
- `build_reflector_harness_context`는 `mutable_targets` 집합을 받아 **모든 생성 대상**을 immutable/helper 목록에서 제외한다.
- 읽기 가능한 context와 수정 권한을 분리한다. 같은 경로가 `input.context`와 `output.context`에 모두 있으면 declared mutable target을 우선한다. 입력의 초기 코드와 현재 candidate를 별도 provenance로 표시하고, input에 있다는 이유만으로 immutable로 취급하지 않는다.
- 코드 생성 output contract는 기존의 전체 target bundle 요구와 일치시킨다. focus target 하나를 골라도 다른 target을 누락하거나 immutable 파일을 생성하지 못하게 검증한다.
- 파일 경로는 manifest에서만 해결하고 path traversal/미선언 target을 거부한다.
- normalization 전후와 실제 evaluator에 전달한 hash를 기록한다. 실제 평가된 코드의 효과를 원본 LLM 출력에 무조건 귀속하지 않는다.

### D-04. baseline·행동·결과를 정확히 연결

수정: `N/llm.py::record_reflector_iteration_result`, `N/cli.py::run_attempt`, `A/focused_debugger_types.py`, `focused_history.py`.

- 초기 생성의 첫 평가도 Observation으로 저장한다. 첫 수정은 이 baseline과 비교한다.
- `before_observation -> action -> after_observation` 연결을 명시한다. 이전 전체 결과·실행 여부 없이 새로운 로그만 보고 해결/회귀를 확정하지 않는다.
- `error_reasoning=fix_guidance` 대입을 제거한다. 실제 reasoning을 반환하게 하거나 필드를 명확히 재정의한다.
- 관측 기반 solved와 새 오류의 회귀 여부를 분리하여 F02의 sticky focus 루프를 제거한다. A가 해결됐으면 A의 통과 조건을 보존하면서 B를 다음 focus 후보로 만든다.
- 기존 prose parser는 legacy compatibility로만 격리한다. 신규 control path의 source of truth로 사용하지 않는다.

### D-05. 종료 조건을 optional inference 앞에 배치

수정: `N/cli.py::run_attempt`.

순서: candidate evaluation 결과·필수 audit 저장 → 유효성 검증·deterministic EffectRecord 저장 → PASS/fatal infra/budget/마지막 iteration 처리 → 재시도 가능한 실행 실패는 bounded retry gate → 살아 있는 candidate 실패에 대해서만 retrospective/decision/reflector.

- PASS 후 반드시 필요한 기록은 deterministic하게 저장하고, 성공 처리에 retrospective LLM을 기다리게 하지 않는다.
- PASS·최종 실패·취소도 `before → action → after`와 관측 가능한 effect를 저장한다. 취소로 평가가 끝나지 않았다면 outcome을 unknown/cancelled로 기록하며 성공·실패를 추정하지 않는다. optional inference 생략 때문에 성공한 수정만 학습·보고 데이터에서 빠지지 않게 한다.
- `fatal_infra`와 `retryable_execution_failure`를 명확한 코드 정책으로 구분한다. 인증·필수 도구 부재 등 지속 오류는 종료하고, 재시도로 복구 가능한 일시 오류만 남은 deadline·retry budget 내에서 `retry_evaluator`로 보낸다. timeout을 무조건 일시 오류로 취급하지 않는다.
- 마지막 iteration에는 실행될 다음 행동이 없으므로 coordinator/restart 선택을 호출하지 않는다.
- 취소된 attempt의 in-flight 응답이 도착해도 다음 generation을 실행하지 않는다.
- `time_to_first_verified_pass`, worker completion, 전체 run wall time을 구분한다.

### D-06. winner 게시와 취소 원인을 별도 계약으로 관리

수정: `N/processes.py::try_claim_first_pass/read_first_pass_claim`, `N/cli.py::run_attempt/run_datapoint/stop_attempt_process/passed_result_from_claim`.

- cancellation reason: `verified_sibling_pass`, `infra_halt`, `budget_exhausted`, `user_cancel`, `fatal_runner_error` 등. winner ID는 verified sibling pass일 때만 존재한다.
- bare stop_event로 성공 원인을 추정하지 않는다. 원인·winner·version을 공유하고 race 시 우선순위를 정의한다.
- 검증된 evaluator result와 candidate bundle manifest를 먼저 내구성 있게 저장한다. winner claim은 그 파일과 hash를 참조한다.
- 경쟁하는 성공 중 하나를 채택할 때 잠금/원자적 게시로 complete claim만 보이게 한다. 단순 `os.replace`만으로 모든 writer가 덮어쓰는 구현도 금지한다. 현재 process 모델에 맞는 exclusive lock + atomic file publication 또는 parent-owned arbitration을 선택한다.
- partial claim, writer crash, stale ownership 복구를 설계한다. 기존 파일의 존재만으로 영구 lock 또는 PASS를 만들지 않는다.
- claim이 가리키는 evaluation validity를 확인한 뒤 sibling cancellation을 게시한다.

### D-07. 모든 유료 작업의 ledger와 증거 보존

수정: `N/processes.py::cleanup_attempt_root`, `N/cli.py` cleanup/report, `S/llm_call.py`, `A/utils/llm_client.py`, `A/llm_backend.py`.

- parent-owned append-only ledger 또는 process별 ledger + 안전한 merge를 사용한다. 멀티프로세스가 잠금 없이 같은 JSONL에 쓰게 하지 않는다.
- 보존 데이터는 cleanup 대상 attempt scratch 밖에 둔다. 기본적으로 loser의 후보·질문·응답·사용량·평가 결과·전환 이력을 유지한다. 대형 임시 build 파일만 정리한다.
- `call_started`, `call_completed/error/cancelled`, `evaluation_started/completed`, `action_committed`, `attempt_terminated`를 기록한다.
- call별 provider, role, model, request ID, parent action, input/output/cached/reasoning usage(제공될 때), retry index, monotonic duration, wall timestamp, cache hit, known/estimated/unknown usage를 기록한다.
- 생성형 LLM의 문자열 반환 API는 호환 wrapper로 남길 수 있지만 내부는 usage가 있는 envelope를 보존한다. generator뿐 아니라 reflector/coordinator/rule selector/fallback/JEV의 모든 호출을 계측한다.
- 프로세스를 종료해도 upstream 과금이 중지됐다고 가정하지 않는다. request가 발송됐으나 응답 usage를 못 받은 경우 unknown 또는 provider usage reconciliation 대상으로 남긴다.
- credential/Authorization/.env 내용은 저장하지 않는다. 연구용 state/response 보존은 허용된 내용만 저장하고 경로·hash로 참조한다.

### D-08. 공통 deadline과 실행 예산

수정: `A/utils/llm_client.py::call_llm`, `A/llm_backend.py`, `S/llm_call.py`, `N/llm.py::run_role_call`, `N/cli.py`.

- 선언만 있는 timeout을 실제 HTTP/subprocess 경로까지 전달한다. generator/reflector/coordinator/JEV/fallback에 같은 budget context를 사용한다.
- retry·backoff는 남은 deadline 내에서만 한다. 각 retry가 새 full timeout을 받으며 전체 예산을 초과하지 못하게 한다.
- run/task/attempt 범위의 wall time, call 수, token/cost budget을 구분한다. 동시 실행 시 budget reservation과 정산을 사용한다.
- usage 미제공 상태에서 정확한 token hard cap을 보장한다고 하지 않는다. 알려진 upper bound 또는 보수적 reservation과 상태 표시를 사용한다.
- 401/403/대부분 4xx validation은 맹목 retry하지 않는다. 429/일시 오류는 제한된 backoff와 Retry-After(제공될 때)를 적용한다. 오류 종류별 fallback 정책을 기록한다.

### D-09. prompt 중복 제거와 bounded context

수정: `N/llm.py::call_reflector/AceIterationModel.prompt`, `A/focused_prompting.py`, `focused_guidance.py`.

- reflector는 `focus/evidence/analysis/guidance/constraints` 구조를 반환한다. 전체 generator prompt를 reflection 문자열에 중첩시키지 않는다.
- generator prompt builder에서 공개 spec, candidate bundle, immutable context, diagnostics, history, guidance를 각각 한 번 compose한다.
- 필수 task contract와 output contract는 context selection이 제거할 수 없다.
- model/provider token budget을 사용하고, bytes/chars limit을 token limit처럼 표시하지 않는다. 추정 tokenizer 사용 시 estimated라고 기록한다.
- 전체 원본 artifact는 디스크에 유지하고 모델 전달본의 truncation 및 제외 evidence를 기록한다.

### D-10. episode와 best candidate 보존

수정: `N/cli.py`, `A/fresh_start_coordinator.py`, `focused_debugger.py`, `focused_history.py`.

- restart마다 episode_id를 새로 만든다. 현재 episode의 진행 상태와 이전 episode의 검증된 교훈을 분리한다.
- native restart에서 existing `clear_history()`가 rule cache까지 초기화하는 동작을 인지한다. 이전 code/guidance를 무조건 다시 주입하지 않는다.
- native에 candidate archive와 best-known valid snapshot을 추가한다. task별 객관적 지표와 D-02의 비교 가능성 계약을 사용하고 missing metrics를 0으로 간주하지 않는다.
- rollback은 fresh_start와 다른 행동이다. 이전 candidate bundle과 관련 evidence·focus·passing constraints·provenance를 새 활성 branch로 선택하고, archived observation을 참조하는 새 active-state/observation version과 rollback event를 append한다. 과거 평가를 재사용하면 새 실측이라고 표시하지 않는다.
- rollback으로 iteration counter, deadline, 지출·reservation, 전체 ledger, 이후 발생한 observation, cancellation 상태를 되감거나 삭제하지 않는다. version과 소비 예산은 단조 증가하며 이전 version의 JEV 응답은 계속 stale이다.
- RTL optimization은 먼저 functional validity를 만족하고 그 안에서 실제 측정 metric을 비교한다. area 하나와 실패 테스트 수를 임의 가중합해 잘못된 RTL을 best로 채택하지 않는다.

### D-11. 완전히 같은 후보의 중복 평가·판단 방지

수정: `N/llm.py::AceIterationModel.prompt`의 normalized hash, `N/cli.py` 평가 전 gate, 새 cache 모듈.

- hash가 이미 평가 전에 확보되므로 `processor.run` 전에 중복 여부를 확인한다.
- evaluation cache는 candidate bundle + task/dataset row + harness/tool/config + 관련 seed + 평가 정책 버전이 같고 재현성이 확인된 경우에만 사용한다.
- 비결정적 harness/seed 미확정/외부 상태 의존이면 cache reuse를 끈다. cache hit도 유효 evaluator manifest를 참조한다.
- byte-identical 여부는 코드가 판단한다. 이것을 위한 JEV 호출은 하지 않는다.
- JEV cache는 canonical state/questions, provider, pinned/resolved model, schema version으로 구분한다. policy 변경 시 raw answer 재사용은 가능하지만 action은 새 policy로 다시 검증한다. alias 변경과 unknown resolved version을 보수적으로 처리한다.

## 5. J — 핵심 JEV 구현

### J-01. 별도 SystemOne client와 엄격한 API 계약

새 `A/decision/systemone_client.py` 및 타입/설정. 기존 chat backend를 SystemOne처럼 꾸미지 않는다.

```text
POST <SYSTEMONE_ENDPOINT_URL>
Authorization: Bearer <configured key>   # provider에 필요한 경우
Content-Type: application/json

{ "model": "<configured model>", "state": {...}, "questions": {...} }
```

- full endpoint 설정을 우선 지원하여 `/v1/v1/systemone` 중복을 방지한다. base URL을 지원하면 base/full endpoint의 의미를 구분한다.
- `noul`: yes/true 확률을 float로 보존. adapter에서 bool화하지 않는다.
- `choice`: choice, probabilities, confidence를 보존한다. 반드시 요청 후보에 속하는지 확인한다.
- `score`: score, probabilities, legend, confidence를 보존한다. score는 level index의 기대값이며 정수화하지 않는다.
- response question key/type 대응, finite values, [0,1] probabilities, tolerance 내 합, score 범위/legend, model/usage schema를 검증한다. NaN/Inf/누락/잘못된 후보를 정상 판단으로 받아들이지 않는다.
- 필수/선택 응답 필드는 provider capability로 명확히 구분한다. usage 미지원은 unknown으로 기록한다.
- 질문 키는 응답 매핑용이며 모델이 보지 않는다. `instructions` 또는 `criteria`에 평가할 state 경로/후보 ID를 명시한다.
- questions는 같은 state에서 독립 평가된다. 동일 요청의 다른 answer를 참조하지 않는다. 독립 평가를 통계적 독립으로 간주해 확률들을 곱하지 않는다.
- 불확실/invalid/timeout에 대한 fallback은 domain policy가 결정한다. client가 임의로 continue/fresh_start를 반환하지 않는다.
- 입력에 secret/private checker가 들어가지 않는 경계를 state builder와 별도로 검증한다.

참고 한도(2026-10-11 공식 문서, 구현 시 재확인): TypeSafe Jev 1.13은 전체 request 64k tokens, state+longest question 32k, Choice 255 options, Score 10 levels. Ollama 호환 구현의 limits/context/auth/usage/keep_alive는 다르므로 별도 capabilities를 둔다. 모든 provider에 한 값을 복사하지 않는다.

### J-02. 수정 효과를 typed 판단으로 전환

수정: `A/focused_history.py::record_attempt`, `focused_guidance.py::extract_implementation_changes`, `N/llm.py::record_reflector_iteration_result`.

- deterministic test observation으로 알 수 있는 사실을 먼저 확정한다. 남은 의미적 대응만 JEV에 묻는다.
- before/after observation, 실행된 check, focused error, 실제 bundle diff, 관련 evidence를 사용한다.
- `focus_status`는 3절 상태 enum의 Choice. `new_failure_is_regression`은 비교 가능한 실행 증거가 있을 때만 Noul을 소비한다.
- 실제 관측으로 가려짐/미실행이 확인되면 모델의 solved 응답보다 관측이 우선한다.
- 변경 설명은 deterministic diff summary를 기본으로 한다. 자유로운 해석이 필요한 경우에만 별도 생성형 LLM 호출을 사용한다.
- `likely/probably`를 삭제해 불확실한 설명을 확실한 판단처럼 만들지 않는다.
- test_passed와 특정 error resolution의 의미를 분리한다. JEV는 전체 benchmark success를 설정할 수 없다.

### J-03. focus·가설·대상 선택

수정: `A/focused_prompting.py`의 sticky focus, `focused_error_analysis.py`, `N/diagnostics.py`, 새 policy/questions.

- 로그 parser가 error/evidence 후보 IDs를 만든다. evidence가 없는 임의 signal/file/error 이름을 모델이 만들어내게 하지 않는다.
- 오류 선택 Choice에는 `none_suitable/insufficient_evidence` 탈출 옵션을 둔다.
- 여러 증상이 공통 원인일 수 있다. root-cause hypothesis는 후보 가설로 보존하고 검증된 사실과 구분한다.
- target file/module은 전체 mutable manifest에서 선택한다. 독립 질문의 strategy/target 조합이 모두 유효한지도 코드가 확인한다.
- 같은 runtime 범주에서 A가 해결되고 B가 발생하면 category가 같아도 focus 전환 가능해야 한다.
- 하나의 오류를 고르는 Choice와 여러 관련 증거를 포함하는 item별 Noul/Score를 구분한다.

### J-04. 다음 행동을 closed action set에서 결정

수정: `A/fresh_start_coordinator.py`, `N/llm.py::call_coordinator`, `N/cli.py::run_attempt`, 새 strategies/policy.

행동 집합 예시:

```text
repair_with_template    적용 전제조건을 만족하는 기존 recipe로 generator에 지시
reflect_focused         관련 증거와 target을 제한해 생성형 reflector 호출
reflect_deep            복잡하거나 불확실한 원인 분석
switch_focus            후보 코드는 보존하고 집중 오류를 전환
gather_evidence         허용된 bounded 진단 수행 후 다시 판단
rollback_best           검증된 이전 bundle/state에서 새로운 수정 시도
fresh_start            새 episode에서 공개 명세 기반으로 재생성
retry_evaluator         일시적 실행 문제에 대해 제한된 재평가
```

- 모든 행동을 모든 state에 노출하지 않는다. task kind, tool availability, edit scope, budget, previous action, cancellation state로 eligible actions를 먼저 계산한다.
- count/deadline/최대 restart 한도와 실제 PASS/fatal infra 처리는 deterministic하다. 일시 실행 실패의 retry eligibility는 D-05에 따른다. JEV가 hard limit을 해제하지 못한다.
- coordinator의 기존 12회 규칙과 3회 default-output 예외는 legacy 모드에 보존한다. JEV 모드에서는 질문·policy config로 대체하며, early restart 효과를 별도로 측정한다.
- bool/reason return에 행동을 억지로 넣지 말고 typed result로 호출부를 수정한다. reason은 evidence/decision code 기반으로 렌더링한다.
- action commit 전에 observation ID/version, candidate hash, mutable set, 남은 budget을 다시 확인한다. stale response는 폐기하고 reason을 기록한다.
- 비생성 action에도 `max_decisions_per_candidate`와 상태 전환 budget을 둔다. 같은 의미 상태의 `(bundle, evidence digest, focus, action)` 반복을 탐지하여 observation version만 증가시키는 순환도 차단한다. 새로운 증거·focus·candidate 변화가 없는 no-op을 거부하고, 한도에 도달하면 적격 repair/fallback 또는 명시적 종료로 간다.

### J-05. 상대 순위와 절대 적합성을 분리

새 policy/questions/strategies, J-04에서 사용.

- Choice는 제공된 후보 중 상대적인 최선만 의미한다. 후보별 Noul로 실제 전제조건과 evidence fit을 별도 확인한다.
- **선택된 후보 자신의 fit**이 기준을 만족해야 한다. `max(all_candidate_fits)`로 다른 후보의 적합성을 빌려 실행하지 않는다.
- 모든 후보가 부적합하면 abstain하고 기존 reflector 또는 새 가설 생성으로 넘어간다.
- 작은 후보 집합은 한 요청으로 atomic 질문들을 묶는다. 큰 registry는 요약으로 shortlist한 다음 해당 후보의 상세 preconditions·예시·반증 이력으로 재평가한다.
- interface/reset/latency/width 등 위험은 별도 질문과 임계치로 관리한다. 평균 위험이 낮다는 이유로 심각한 단일 위험을 무시하지 않는다.
- confidence/top1/top2 margin/entropy는 telemetry로 보존한다. cutoff는 dev traces에서 검증한다. 미검증 숫자는 experimental default라고 표시한다.
- probability/score/composite score를 실제 성공률로 이름 붙이지 않는다.

### J-06. 선택적 Reflector와 검증된 repair recipe

수정: `A/focused_error_analysis.py`, `focused_prompting.py`, `N/llm.py::call_reflector`, 새 strategies.

- syntax/누락 target/명시적 width 문제 등 실제 증거로 식별할 수 있는 좁은 유형에 recipe registry를 둔다.
- recipe는 id, 적용 task kind, preconditions, 허용 target/scope, 필요한 evidence, generator guidance, 검증 절차를 가진다.
- recipe 선택이 실제 RTL 패치 생성은 아니다. generator가 코드를 만들고 evaluator가 검증한다.
- 익숙하지 않은 실패, 근거 부족, 위험 신호, 반복 무개선이면 기존의 생성형 분석으로 fallback한다.
- compile 성공, 신호 값 비교 등 도구로 확정 가능한 사실을 JEV로 다시 승인받지 않는다.
- 같은 정보로 JEV를 계속 재호출하지 않는다. 새 observation 또는 실제 새로운 증거가 있어야 다시 판단한다.

### J-07. 모호한 task/실패 의미의 보완 분류

수정: `N/config.py`, `A/focused_task_detection.py`, `focused_error_analysis.py`, 새 questions.

- D-01의 canonical metadata가 확정돼 있으면 우회한다.
- 모호한 공개 요구를 `rtl_implementation/rtl_optimization/assertion/coverage/checker/unknown`처럼 서로 구분되는 Choice로 평가한다.
- “assertion이 포함돼 있다”와 “assertion을 생성하라는 요청”을 다른 질문으로 취급한다. 명시적 부정문·제외 조건을 criteria에 반영한다.
- 불확실하면 요구사항·target contract를 보강하거나 기존 적절한 분석 경로로 fallback한다. generated code 때문에 task 목적을 다시 바꾸지 않는다.

### J-08. 규칙·history·로그·context의 증거 기반 선별

수정: `A/rtl_rule_advisor.py`, `focused_history.py::_build_history_trajectory`, `focused_guidance.py` truncation, `N/llm.py::build_reflector_harness_context`, 새 context_selector.

- 먼저 exact duplicates, 명백히 무관한 파일, 금지 자료를 deterministic하게 걸러낸다.
- item별 relevant/applicable Noul, 직접성·유용성 Score, contradiction/previous_failed_attempt 등 필요한 질문을 배치한다.
- 긍정 근거만 남기지 않는다. 현재 전략이 실패했음을 보여주는 반대 증거와 보존해야 할 통과 조건도 선택한다.
- 필수 contract, current failure 원문, 실제 결과, 최근 diff, best candidate reference는 최소 보존 집합으로 둔다.
- history는 최근 N개만이 아니라 현재 episode/같은 오류/유사 실패 전략/최선 결과를 함께 고려하여 token budget 내에서 구성한다.
- 여러 규칙을 뽑을 때 rule별 Noul/Score 사용. rule IDs dedupe, 상세 예시 token budget, spec+rule version hash cache를 추가한다.
- `rtl_rule_advisor`의 정상적인 no-match와 일시 API/parse 실패를 분리한다. 후자를 `specification_processed=True`로 영구 no-match 처리하지 않는다.
- 개인정보·비밀·private evaluator 경계를 관련성 점수로 우회하지 않는다.

### J-09. diagnostic action으로 불확실성을 줄이기

새 strategies/policy와 기존 공개 도구·로그 parser 연결.

- `observed_resolved`와 `masked`가 경합하면 우선 해당 test/service 실행 여부를 확인한다.
- width/signedness, reset, handshake, pipeline alignment 등 후보가 경합할 때 관련 공개 신호·경고·trace만 추가 수집하는 bounded action을 제공한다.
- 예: 허용된 기존 로그 상세 보기, public interface의 trace 요약, 현재 후보의 compile/elaboration 재확인. 새 숨겨진 테스트·private scorer를 읽지 않는다.
- waveform을 사용하면 결정적으로 시간/값을 파싱하고 해당 요약을 모델에 보낸다. JEV가 긴 VCD를 읽고 수치 계산하게 하지 않는다.
- 각 진단의 allowed inputs, timeout, artifact, 실행 비용을 선언한다. 질문 불확실성만 보고 무한히 추가 도구를 부르지 않는다.
- 추가 진단이 없거나 예산이 부족하면 기존 reflector 또는 bounded continue로 fallback한다. 정보를 수집하지 않고 같은 상태를 재질문하는 것을 진단으로 기록하지 않는다.

## 6. X — 전체 확장 포인트: 구현하되 기본 비활성화

이 절의 기능은 기본 JEV 효과와 구분하여 평가한다. native에는 없는 새 기능이 포함돼 있다. 설정 플래그만 만들고 구현 완료라고 하지 않는다. 실행에 필요한 학습 데이터가 없으면 코드·fixture 테스트와 데이터 요구조건까지 제공한다.

### X-01. 확률 기반 복수 전략 탐색

연결: `N/cli.py::run_datapoint/run_attempt`, 새 policy/strategies, candidate archive.

- top-1이 명확하면 한 경로, 상위 후보가 경합하면 budget 내 최대 K개를 유지한다. K는 config이며 초기 예시는 2다.
- 먼저 semantic strategy diversity를 보장한다. 같은 수정안을 표현만 바꿔 두 개의 독립 전략으로 세지 않는다.
- branch마다 parent candidate, action, episode, observation, 예산, 결과를 별도로 관리한다. 동시 branch가 같은 candidate 파일을 덮어쓰지 않는다.
- 전략→대상→recipe 계층이 필요하면 각 노드의 적법한 후보만 확장한다. 같은 state에서 독립 평가 가능한 질문만 batch한다.
- 경로 점수·확률 곱·geometric mean은 탐색 휴리스틱으로만 사용한다. RTL 통과 확률이라는 이름을 붙이지 않는다.
- 어떤 분기를 폐기했는지 보존한다. 후보 제거가 잘못됐는지 확인할 수 있도록 예산이 허용하는 평가 표본을 별도로 마련한다.
- 최초 검증 실험에서는 generator와 총 시뮬레이션·토큰 예산을 맞춘다. 더 많은 후보를 실행해 얻은 이득을 JEV 자체 정확도 향상이라고 쓰지 않는다.

### X-02. adaptive attempt scheduling과 best snapshot에서 분기

연결: `N/cli.py::run_datapoint`, 현재 모든 attempts를 즉시 생성하는 505–526 부근.

- 초기 최소 탐색을 보장하고, 이후 iteration/checkpoint 경계에서 다음 실행 budget을 배분한다.
- JEV relevance/risk/novelty 신호와 실제 progress/cost를 사용한다. unknown metric을 무진전으로 취급하지 않는다.
- 점수가 낮다는 이유만으로 관측 기회 없이 모든 어려운 과제를 중단하지 않는다. 최소 시도·탐색 예산을 config로 보장한다.
- best snapshot에서 새 전략을 분기할 수 있게 한다. rollback과 fresh_start는 별개다.
- pause/resume을 지원하면 후보와 관측·정책 버전을 함께 checkpoint한다. 지원하지 않으면 다음 iteration 미실행 방식으로 제한하고 그 사실을 문서화한다.
- 지금 진행 중인 유료 call을 단순 terminate해 비용이 회수됐다고 계산하지 않는다.

### X-03. 모델·추론 예산 라우팅과 후보 위험 검토

연결: `N/llm.py::AceIterationModel`, `A/utils/llm_client.py`, `S/llm_call.py`, 설정/ledger.

- 사용자가 설정한 model aliases 안에서만 generator/reflector 모델을 선택한다. 문서의 임의 상용 모델명을 hard-code하지 않는다.
- 좁은 국소 수정과 복잡한 구조 재설계에 다른 모델·허용 출력 예산을 매핑할 수 있게 한다.
- interface, reset, protocol latency, signedness 등의 위험을 별도 Noul로 평가한다. 실제 parser·compiler가 확인하는 위반은 hard gate다.
- 위험이 높거나 실제 실패가 누적되면 강한 모델로 승격할 수 있다. 위험 평균값으로 심각한 한 항목을 숨기지 않는다.
- 예측상 위험이 낮아도 필수 실제 evaluator를 생략하지 않는다.
- B/C 핵심 비교에서는 이 기능을 끈다. 모델 라우팅 효과는 별도의 실험군으로 측정한다.

### X-04. 교훈 큐레이션과 지속 메모리

연결: `A/fresh_start_coordinator.py::_llm_extract_high_level_lessons`는 기존 agent 참조용. native에는 `N/cli.py`의 episode 종료/재시작 지점에 새로 연결한다.

- 새로운 교훈 문장은 생성형 LLM 또는 deterministic summary가 만든다. JEV는 근거 있음/적용 가능/중복/반증 있음 등을 판단한다.
- lesson에는 source observation/action/evaluation IDs, task family, 적용 전제조건, 반례, 검증 상태, 생성·평가 모델 버전을 저장한다.
- 단일 실패에서 추측한 조언을 검증된 규칙처럼 승격하지 않는다. candidate lesson과 confirmed lesson을 구분한다.
- 현재 episode의 수정 맥락, 이전 episode의 교훈, 다른 task의 일반 지식을 분리한다.
- 비공개 정답·checker 구현·평가 task의 해결 코드를 다른 task 메모리에 넣지 않는다. benchmark 평가에서는 메모리를 고정하고 evaluation set에서 학습하지 않는다.
- 현재 레포에 범용 playbook curator가 이미 있다고 가정하지 말 것. 이 기능의 추가 비용·효과를 별도 보고한다.

### X-05. JEV 특징 기반 학습 정책

새 offline 모듈을 기존 `skills/ace-rtl/scripts/` 규칙 안에 추가한다. 핵심 실행 경로가 ML dependency를 필수로 import하지 않도록 optional dependency로 격리한다.

- 입력: decision 시점의 observation + eligible action + JEV semantic features + deterministic tool statistics.
- 특징: 원인/행동 적합성, 수정 범위, 반증, 이전 실패 반복성, 위험별 Noul, Score 전체 분포 또는 mean/spread, 실제 changed files/cost/progress.
- 레이블: 해당 action을 실제 실행한 뒤의 valid next evaluation pass/개선/회귀, 실제 소요시간·비용. 실행하지 않은 행동의 결과를 만들어내지 않는다.
- 처음에는 설명 가능한 작은 모델 또는 단순 정책부터 비교한다. 사용 라이브러리와 모델은 환경·데이터 규모에 맞춰 선택한다.
- split은 iteration random split이 아니라 task/design family 단위 group split으로 한다. 유사 candidate가 train/test에 섞이지 않게 한다.
- label이나 future evaluation 정보를 decision-time feature에 넣지 않는다.
- 기록은 기존 정책이 실행한 행동에 치우쳐 있다. 단순 로그 학습으로 새로운 정책의 우수성을 인과적으로 증명했다고 하지 않는다. 제한된 branch 실험/탐색과 별도 E2E가 필요하다.
- 데이터 부족 시 synthetic fixture로 pipeline만 검증하고 모델을 production policy로 켜지 않는다.

### X-06. 질문·criteria의 offline 개선과 안정성 검증

새 offline tooling + 질문 registry.

- 실패 사례를 보고 생성형 LLM이 질문·criteria의 add/revise/drop 후보를 제안할 수 있다.
- dev set에서 비용·오류·abstention·fallback을 비교하여 채택한다. held-out test set은 제안/튜닝 과정에서 보지 않는다.
- Choice option 순서 변경, 표현 변경, 로그 중복, 누락 지표, 부정문에 대한 안정성 fixture를 만든다.
- 반복 호출의 label 일관성과 실제 정답 정확도를 별도 지표로 보고한다.
- 질문·threshold/model version을 함께 pin하고 runtime 중 자동 자기수정을 금지한다.
- calibration과 충분한 outcome data 없이 score를 성공 확률로 바꾸지 않는다. 확률끼리의 상관관계도 무시하지 않는다.

## 7. 요청 설계 예시와 결정 순서

아래 JSON은 API 모양을 보여주는 작은 fixture다. 실제 런타임은 후보 IDs·state paths를 현재 observation에서 생성해야 한다. 모델명·증거 내용은 예시이며 실측 결과가 아니다.

```json
{
  "model": "<configured-systemone-model>",
  "state": {
    "observation_id": "fixture-observation-2",
    "task_kind": "rtl_implementation",
    "focused_error": {"id": "error-A", "description": "Output data not aligned with valid"},
    "before": {"executed_checks": ["public-check-A"], "failed_checks": ["public-check-A"]},
    "after": {"compile_status": "passed", "executed_checks": [], "unreached_checks": ["public-check-A"], "termination": "timeout"},
    "actions": {
      "inspect_progress": {"description": "Inspect existing public valid/data trace around timeout", "preconditions": "An allowed trace is available"}
    },
    "available_evidence": [{"id": "trace-1", "description": "Public interface trace exists for this tested candidate"}]
  },
  "questions": {
    "focus_status": {
      "type": "choice",
      "instructions": "Determine the observed status of state.focused_error from the before and after execution facts. Absence from a log does not establish resolution.",
      "criteria": {
        "persists": "The corresponding executed check still reports the same failure.",
        "observed_resolved": "The corresponding check executed and explicitly passed.",
        "masked": "An earlier execution failure prevented observing the corresponding check.",
        "not_executed": "The corresponding check was not executed or reached, with no established earlier masking failure.",
        "unknown": "The supplied facts do not establish any of these states."
      }
    },
    "inspect_progress_applicable": {
      "type": "noul",
      "instructions": "Are the stated preconditions of state.actions.inspect_progress supported by state.available_evidence?",
      "criteria": {
        "true": "The permitted trace required by the action is available for the tested candidate.",
        "false": "The required trace is absent or belongs to a different candidate."
      }
    },
    "trace_relevance": {
      "type": "score",
      "instructions": "How directly could available evidence trace-1 inform the observed valid/data progress issue?",
      "criteria": [
        "The evidence is unrelated to the observed failure.",
        "The evidence is relevant but does not directly observe the affected interface behavior.",
        "The evidence directly observes the affected public interface around the failure."
      ]
    }
  }
}
```

위 fixture처럼 실행 사실만으로 판단할 수 있는 항목은 실제 동작에서 deterministic gate를 우선한다. 예시의 모든 질문을 매번 호출하라는 뜻이 아니다.

추천 decision 순서:

1. immutable Observation을 만들고 유효성·termination·budget을 검사한다.
2. 실제 task contract에서 적법한 error/target/action 후보를 만든다.
3. 같은 state에서 독립 평가 가능한 질문만 한 batch로 실행한다.
4. type/key/option/수치 범위와 selected candidate fit을 검증한다.
5. 상충하는 답·불확실성·unknown은 코드 정책으로 처리한다. 답 사이 의존성이 필요하면 다음 요청에 이전 결과를 명시적으로 넣는다.
6. 최종 action tuple의 preconditions·target scope·budget·observation version을 검사하고 commit한다.
7. generator/tool을 실행하고 실제 outcome을 기록한다.

## 8. 설정·실행 모드·기본값

기존 `.env.local`/환경 변수/adapters를 먼저 조사하고 사용자 설정을 재사용한다. `.env.example`에는 변수명과 dummy 설명만 넣는다. secret 존재 여부를 확인할 때 값은 출력하지 않는다. TLS 검증을 끄지 말고 기존 사내 CA/proxy 설정을 존중한다.

다음은 새 설정의 권장 이름이다. 이미 같은 의미의 설정이 있으면 alias 또는 명시적 mapping을 제공한다.

| 설정 | 의미·기본 동작 |
|---|---|
| `ACE_RTL_DECISION_MODE` | `legacy`, `baseline_fixed`, `shadow`, `jev_core`, `jev_extended` |
| `SYSTEMONE_ENDPOINT_URL` | 실제 `/v1/systemone` 전체 URL |
| `SYSTEMONE_MODEL` | 요청 모델. 실험에서는 concrete version 또는 resolved version 기록 |
| `SYSTEMONE_API_KEY` | provider/proxy 인증키. 로그 출력 금지 |
| `SYSTEMONE_PROVIDER` | capability preset. schema·limit·usage 차이 분리 |
| `SYSTEMONE_TIMEOUT_SECONDS` | 공통 남은 deadline보다 작게 적용 |
| `ACE_RTL_POLICY_FILE` | 질문별 threshold·fallback·action budget 정책 |
| `ACE_RTL_QUESTION_SCHEMA_VERSION` | 질문과 criteria 버전 |
| `ACE_RTL_RUN_BUDGET_FILE` | run/task/attempt별 bounded budget |
| `ACE_RTL_ENABLE_BEAM` | 기본 false |
| `ACE_RTL_BEAM_WIDTH` | 켜진 경우 제한된 K, 예시 2 |
| `ACE_RTL_ENABLE_ADAPTIVE_SCHEDULING` | 기본 false |
| `ACE_RTL_ENABLE_MODEL_ROUTING` | 기본 false |
| `ACE_RTL_ENABLE_LESSON_MEMORY` | 기본 false, 평가 때 memory snapshot 고정 |
| `ACE_RTL_ENABLE_LEARNED_POLICY` | 기본 false, 학습·검증·version 필요 |
| `ACE_RTL_EVALUATION_CACHE_MODE` | 기본 off 또는 검증된 deterministic tasks 한정 |
| `ACE_RTL_KEEP_AUDIT_ARTIFACTS` | 기본 true |

모드 의미:

- `legacy`: 기존 제어 전략을 재현하는 reference 모드. 실제 원본 비교는 원본 worktree/commit에서 수행한다. 새 코드의 legacy mode가 원본과 완전히 같다고 가정하지 않는다.
- `baseline_fixed`: D 기반 수정 적용, 생성 모델·기존 전략은 가능한 유지, JEV 호출 없음.
- `shadow`: baseline_fixed의 행동을 실행하고 JEV 판단은 기록만 한다. JEV 때문에 실제 분기가 바뀌지 않는다. shadow 비용은 별도 표시한다.
- `jev_core`: D + J. 실제 적합성·불확실성 정책과 fallback을 사용한다.
- `jev_extended`: D + J + 사용자가 켠 X 기능. 활성 목록을 run manifest에 기록한다.

초기 배포 기본값은 `baseline_fixed` 또는 기존 호환 모드로 두고, JEV 활성 실행은 명령/설정에 명시한다. 실험 후 성공률·비용 기준을 만족한 모드만 기본값 변경 후보로 제안한다.

시작 시 preflight:

1. 생성형 LLM과 SystemOne의 URL·인증·모델을 구분한다.
2. 최소 요청으로 각 endpoint contract를 검증한다. JEV는 최소한 세 primitive와 multi-question 혼합을 확인한다.
3. 실제 provider capabilities와 요청 크기 제한을 적용한다.
4. cold-start/warm-up 호출은 timed benchmark에서 제외하고 별도 ledger로 남긴다. local runtime이 keep_alive를 지원하면 capability에 따라 사용한다.
5. 연결이 안 되면 원인을 명시하고 fixture 테스트·구현·문서를 마친다. auth 오류를 모델 판단 unknown과 섞지 않는다.

## 9. 병렬 구현 분담과 통합 순서

여러 OpenCode 세션/서브에이전트를 쓸 수 있다면 독립 파일 소유권으로 나눈다. 먼저 root orchestrator가 타입·설정·새 API 계약을 확정한다. 같은 파일을 동시에 수정하지 않는다. 별도 worktree를 써도 타입 계약은 하나다.

| 담당 | 범위 | 주요 소유 파일 | 의존성 |
|---|---|---|---|
| A — 관측·평가 | D-01~04, task/metric/multifile | diagnostics/harness/task detection, observation types | 공통 타입 먼저 |
| B — 실행·기록 | D-05~08, D-10~11 | processes, budget/ledger/cache | A observation 계약 |
| C — SystemOne | J-01, 질문 registry·contract tests | systemone_client/questions/provider config | 공통 타입 |
| D — 판단·context | J-02~09, D-09 | focused history/prompting/guidance, policy/context_selector/rule advisor | A/C 계약 |
| E — 실험 확장 | X-01~06 | scheduler/strategy extensions, offline learning tools | core 안정화 후 |
| F — 테스트·리포트 | fixtures, integration, ablation runner/report/docs | tests, report tools, docs | 위 계약에 맞춘 mocks 가능 |
| 통합 담당 | `N/cli.py`, `N/llm.py`, 공통 backend API | 공유 호출부는 한 담당이 변경 | 모든 담당 산출물 통합 |

`N/cli.py`/`N/llm.py`는 특히 충돌이 많으므로 각 담당은 필요한 interface 변경안을 통합 담당에게 전달한다. 위 표가 파일 소유권 충돌을 만들면 실제 담당표를 조정한다.

통합 순서:

1. upstream/current state 기록, baseline 보존, 호출 관계 audit.
2. 공통 타입·TaskContract·Observation·CallResult/ledger 계약.
3. D 기반 수정 및 재현 fixture 통과.
4. SystemOne client contract 및 capability smoke.
5. shadow 판단과 typed 효과 판정.
6. jev_core의 action/reflector/context 통합.
7. E2E core 비교.
8. X 기능을 각각 flag로 통합·fixture 검증하고 별도 실험.

## 10. 필수 테스트와 실제 검증

실제 branch 전환·평가 유효성·비용 누락을 검증하는 테스트를 만든다. 함수 구현을 그대로 복사한 형식적인 테스트는 만들지 않는다. 모델의 확률이 매번 정확히 같은 숫자일 것이라는 snapshot도 금지한다.

### 10.1 결정적 회귀 fixture

| 테스트 | 기대 결과 |
|---|---|
| `not fixed` / `no new errors introduced` | 문장 substring이 신규 control 상태를 결정하지 않음 |
| A 해결 후 B runtime failure | A를 해결된 관측으로 보존하고 B 선택 가능 |
| compile 실패로 A test 미실행 | A resolved가 아니라 masked/not_executed |
| native metric 없음 | unknown이며 stall 개선율을 조작하지 않음 |
| initial evaluation -> 첫 수정 개선 | 초기 observation과 올바르게 비교 |
| 두 번째 target만 변경 | bundle changed, 해당 diff/target이 reflector에 전달 |
| 여러 mutable targets | 어떤 target도 immutable/helper로 잘못 표시되지 않음 |
| 두 번째 target이 input.context에도 있고 수정됨 | 입력 초기 코드와 현재 candidate를 구분하며 target은 mutable 유지 |
| `Do not add assertions` | assertion 생성 과제로 전환하지 않음 |
| RTL의 `helper u_dut()` | 인스턴스명만으로 verification task가 되지 않음 |
| compile success + iverilog + runtime assertion | compilation failure로 오분류하지 않음 |
| sanity PASS, synth FAIL | functional failure guidance를 만들지 않음 |
| 같은 failure가 로그에 3번 등장 | 실패 테스트 3개로 세지 않음 |
| evaluator timeout | timeout/unknown execution, PASS 아님 |
| errors=0, tests=[] | invalid evaluation, PASS 아님 |
| 필수 service 누락/결과 불일치 | invalid/incomplete, PASS 아님 |
| 유효한 required results + 보조 로그 truncation | verified PASS 유지, diagnostic completeness만 별도 표시 |
| test 집합·분모·seed가 다른 두 관측 | 단순 count delta로 개선을 단정하지 않음 |
| 성공 또는 마지막 iteration | 불필요한 retrospective/coordinator call 0회 |
| terminal PASS/실패/취소 | deterministic EffectRecord와 action 연결이 보존됨 |
| infra halt + sibling stop | sibling_pass로 기록하지 않음 |
| 일시 evaluator 실패와 fatal infra | 전자만 제한된 retry 가능, 후자는 즉시 명시적 종료 |
| partial winner claim·동시 winner | 유효한 단일 claim, invalid claim 복구 |
| winner 뒤 loser cleanup | paid calls·기존 평가·candidate 증거 보존 |
| 역할별 timeout·retry | 공통 deadline 초과 신규 call 금지 |
| old episode progress | current episode 진행 수치에 합산하지 않음 |
| rollback 후 다음 action | bundle·focus 복원, 새 version 생성, 예산·전체 이력·취소 상태 유지 |
| switch_focus/gather_evidence/rollback 순환 | no-op·반복 탐지와 결정 budget으로 유한 종료 |
| stale observation의 JEV 응답 | action commit 거부 |
| 같은 후보 + 같은 deterministic harness | 평가 reuse와 출처 기록 |
| 같은 후보 + 다른 seed/tool/harness | cache miss |
| normalized code가 raw와 다름 | 실제 tested hash와 normalization provenance 보존 |
| 없는 target/path 또는 잘못된 action tuple | 실행 전 reject |
| 선택 후보 fit 낮고 다른 후보 fit 높음 | 다른 후보의 fit으로 승인하지 않음 |
| severe risk 하나와 낮은 나머지 위험 | 평균에 묻히지 않고 해당 정책 실행 |
| context에 전략 반증 자료 존재 | 필수 반증 보존 정책 검증 |
| contract 밖 private checker 조각 | JEV/LLM state에 포함되지 않음 |

### 10.2 SystemOne contract tests

- choice/noul/score/mixed batch 직렬화·응답 검증.
- question key/type mismatch, unknown option, 잘못된 legend, NaN/Inf, 누락 usage 등 provider별 계약 위반.
- timeout/401/403/422/429/5xx와 malformed response를 구분.
- invalid 답 또는 낮은 확신에서 fallback이 실제 호출되고 reason·usage가 남는지 확인.
- independent answers의 상충을 policy가 처리하는지 확인.
- request key에만 의미를 숨기지 않고 instructions가 state 대상 식별을 포함하는지 확인.
- option 순서/부정문 fixture를 통해 semantic robustness를 평가하되 probabilistic 응답을 strict equality로 요구하지 않는다.
- 실제 endpoint에 소량 contract smoke 수행. 실제 semantic 성능은 별도 labeled dev set에서 평가한다.

### 10.3 실제 CVDP smoke와 비교

- 사용자가 지정한 dataset/CID를 우선한다. 지정이 없으면 현재 설치된 no-commercial dataset에서 실행 가능한 대표 항목을 고른다. 기존에 사용한 `cid002/cid004/cid007/cid016`도 실제 metadata·tool 요구를 확인한 후 사용한다.
- 처음은 단일 task, attempt 1, iteration 1로 생성→실제 평가→artifact를 확인한다. core repair 검증은 iteration 2 이상으로 제한된 별도 run을 수행한다.
- 생성된 후보가 첫 시도에 성공해 repair 경로가 실행되지 않았으면 core decision 통과 증거로 삼지 않는다. 실패가 있는 trace/선별 task와 mock integration을 함께 사용한다.
- 다음으로 소규모 고정 task manifest를 A/B/C에서 실행한다. 전체 dataset·5 attempts×30 iterations 같은 대규모 기본값을 무심코 실행하지 않는다.
- benchmark runner가 실제로 적용한 모드·정책·모델·예산과 request counts를 확인한다. 설정 파일만 바뀌고 native 호출부는 그대로인 상태를 잡아낸다.
- 인프라가 막히면 `infra_error`, 계약 실패는 `contract_error`, benchmark 실패는 `task_failed`로 구분한다. skip을 pass로 집계하지 않는다.

## 11. 비교 실험 설계와 산출물

| 실험군 | 구성 | 분리하려는 효과 |
|---|---|---|
| A | 원본 baseline commit/worktree | 기존 실행 상태 |
| B | D 기반 수정, 같은 모델·기존 전략 | 데이터/제어/중복/측정 개선 |
| C | B + JEV core | JEV 판단·선택적 reflector·context 개선 |
| D | C + beam/adaptive scheduling 중 한 기능 | 탐색·스케줄링 효과 |
| E | C + model routing | 생성 모델/예산 변화 효과 |
| F | 충분한 데이터 후 C + learned policy/lesson memory | 학습·기억 효과 |

- 한 실험에서 여러 X 기능을 동시에 켜서 각각의 효과를 주장하지 않는다. 마지막에 combined mode를 별도 비교할 수 있다.
- A가 F12 같은 invalid PASS를 보고하면 원본 reported success와 공통 검증기로 재판정한 verified success를 함께 보존한다. 잘못된 baseline success를 그대로 분모/성공률 기준에 사용하지 않는다.
- B와 C는 generator/reflector 모델, dataset/task IDs, evaluator/tool 버전, concurrency, 총 예산을 고정한다. 모델 sampling seed가 보장되지 않으면 반복 측정하고 그 한계를 명시한다.
- 개발 traces와 최종 평가 task를 분리한다. threshold/prompt는 dev에서만 조정한다.
- offline replay는 contract·분류·policy 선택 검증용이다. 다른 행동을 실제 실행하지 않은 replay로 E2E 성공률 상승을 입증하지 않는다.
- 가능한 경우 같은 frozen parent candidate에서 action alternatives를 실제 분기 실행하여 효과를 비교한다. 다른 행동의 관측하지 않은 결과는 unknown으로 둔다.

필수 보고 지표:

1. task별 verified success, task failure, infra/invalid/cancelled 상태와 각 분모. end-to-end 성공률과 valid-evaluation-only 성공률을 분리한다.
2. time to first verified pass, 전체 wall time, latency 분포. 병렬 call duration의 합을 wall time이라고 쓰지 않는다.
3. 전체 attempts·retries·fallback·JEV·취소 작업을 포함한 input/output/cached/reasoning tokens와 비용. provider별 usage 차이와 unknown을 표시한다.
4. generator/reflector/coordinator/JEV/진단/평가 호출 수, fallback·abstention·invalid/stale decision 비율.
5. 반복 candidate 평가, 같은 오류 반복, focus 전환, restart, rollback, confirmed regression, masked/not-executed 상태 수.
6. context 입력량과 선별 비용, evaluator 소요량, branch별 소비 예산.
7. JEV semantic 판단 fixture의 정확성, 선택 후보 fit 오류, 잘못된 후보 제거 표본, threshold별 coverage/오류 tradeoff.
8. run manifest, 질문/정책/model/data/harness/tool versions, cost price snapshot/근거 또는 비용 미산정 사유.

비용을 모르면 token 지표만 보고하고 0원으로 적지 않는다. 공식 가격을 쓸 때는 provider·날짜·cached discount 적용 여부를 확인하고 실제 billing과 추정 계산을 구분한다.

권장 출력 구조(이름은 repo 관례로 조정 가능):

```text
outputs/<run_id>/
  run_manifest.json
  events/                 # cleanup과 분리된 per-process 또는 parent ledger
  decisions/
  evaluations/
  candidates/
  checkpoints/
  task_results.jsonl
  summary.json
  comparison.csv
  report.md
  scratch/                # 정리 가능한 simulator/build 임시 자료
```

보고서에는 원인에 따라 `A→B`, `B→C`, 각 X 기능 추가 효과를 나눠 적는다. 성공률 비열등 기준·허용 비용·통계적 판단 기준은 실험 전에 정하고, 표본이 부족하면 결론 불충분으로 남긴다.

## 12. 최종 완료 체크리스트

- [ ] 현재 HEAD/사용자 변경/active native call graph를 확인했고 audit 문서가 있다.
- [ ] F01–F20을 각각 재현·해결·이미 해결됨·해당 없음으로 분류하고 근거를 남겼다.
- [ ] D-01~D-11이 구현됐고 native 경로에서 실제로 사용된다.
- [ ] SystemOne은 실제 `/v1/systemone` 계약으로 호출된다.
- [ ] J-01~J-09가 구현됐고 shadow/core/fallback 경로가 검증됐다.
- [ ] X-01~X-06의 구현/데이터 의존 검증/실험 상태를 개별 표시했다. flag만 있는 기능을 완료로 적지 않았다.
- [ ] mutable target manifest, bundle diff, tested candidate provenance가 연결됐다.
- [ ] solved/regression/masked/unknown이 분리되고 문자열 substring이 신규 제어 상태를 결정하지 않는다.
- [ ] PASS가 required evaluator services와 유효 결과로만 결정된다.
- [ ] winner/cancellation/deadline/ledger가 멀티프로세스 환경에서 테스트됐다.
- [ ] 취소된 작업·retry·fallback을 포함한 비용과 unknown usage가 보존된다.
- [ ] credentials/private benchmark internals가 prompt·로그·commit에 유출되지 않는다.
- [ ] 기존 생성형 LLM adapter와 기존 agent 실행 경로에 대한 호환 검증이 있다.
- [ ] 실제 endpoint/CVDP 실행 결과 또는 구체적 차단 사유와 재실행 명령이 있다.
- [ ] A/B/C 실험이 가능하며 기본 개선과 JEV 개선을 분리한 report가 있다.
- [ ] README 또는 runbook에 설정·모드·실행·rollback·artifact 해석을 설명했다.

최종 응답에는 변경 파일·핵심 동작·실행한 검증·실측 결과·남은 차단 항목·사용자 실행 명령을 간결히 보고하라. 실제로 수행하지 않은 E2E/학습/성능 검증을 완료했다고 쓰지 말 것.

## 13. 공식 근거와 재확인 링크

이 문서의 API 사실은 아래 공식 자료를 바탕으로 작성했다. ACE-RTL 적용 설계·우선순위·실험 제안은 코드 조사에 따른 권고이며 공식 성능 보장이 아니다.

- [ACE-RTL 조사 스냅샷](https://github.com/NVlabs/ACE-RTL/tree/94754d796350d42502c9a32639a20d86f50e9678)
- [native runner](https://github.com/NVlabs/ACE-RTL/blob/94754d796350d42502c9a32639a20d86f50e9678/skills/ace-rtl/scripts/ace_cvdp_native/cli.py)
- [native role 연결](https://github.com/NVlabs/ACE-RTL/blob/94754d796350d42502c9a32639a20d86f50e9678/skills/ace-rtl/scripts/ace_cvdp_native/llm.py)
- [focused history](https://github.com/NVlabs/ACE-RTL/blob/94754d796350d42502c9a32639a20d86f50e9678/skills/ace-rtl/scripts/ace_rtl_agent/focused_history.py)
- [coordinator](https://github.com/NVlabs/ACE-RTL/blob/94754d796350d42502c9a32639a20d86f50e9678/skills/ace-rtl/scripts/ace_rtl_agent/fresh_start_coordinator.py)
- [TypeSafe live schema](https://api.typesafe.ai/openapi.json)
- [기본 개념·독립 질문](https://docs.typesafe.ai/introduction)
- [Choice·후보·question ID](https://docs.typesafe.ai/primitives/choice)
- [Noul](https://docs.typesafe.ai/primitives/noul)
- [Score·rubric](https://docs.typesafe.ai/primitives/score)
- [confidence 수학·의미](https://docs.typesafe.ai/confidence)
- [provider model/limits](https://docs.typesafe.ai/models)
- [수치·긴 상태·순서 편향 등 모델 한계](https://docs.typesafe.ai/model-jaggedness/jev-1.13)
- [여러 atomic 판단 조합](https://docs.typesafe.ai/patterns/composite-scoring)
- [후보의 상대 순위/절대 적합성](https://docs.typesafe.ai/cookbooks/skill_suggestion)
- [typed action/function 조립](https://docs.typesafe.ai/cookbooks/function_calling)
- [확률 기반 계층 탐색](https://docs.typesafe.ai/cookbooks/hierarchical_classification)
- [필드별 위험 검토·모델 승격](https://docs.typesafe.ai/cookbooks/sde_cascade)
- [evidence/반대 증거 선별](https://docs.typesafe.ai/cookbooks/classifying_rag_passages)
- [의미 특징과 offline 질문 개선](https://docs.typesafe.ai/cookbooks/autoresearch_feature_discovery)
- [보정의 집단적 의미](https://docs.typesafe.ai/introduction/machine-learning-primer)
- [Ollama decision capability](https://docs.ollama.com/capabilities/decision)
- [Ollama SystemOne contract](https://docs.ollama.com/api/systemone)

## 14. OpenCode에 붙여 넣을 시작 지시

```text
현재 ACE-RTL 저장소에서 ACE_RTL_JEV_OPENCODE_IMPLEMENTATION_PLAN.md를 읽고 전체 작업을 수행하라.
먼저 현재 HEAD와 실제 native CVDP 호출 경로를 확인하고, 사용자 변경과 준비된 LLM/JEV endpoint 설정을 보존하라.
문서의 D 기반 수정과 J 핵심 기능을 구현·테스트한 뒤, X 확장 기능은 각각 기본 비활성화된 설정으로 구현하라.
공통 타입과 파일 소유권을 먼저 확정하고 독립 작업은 병렬화하되 cli.py/llm.py는 통합 담당이 수정하라.
실제 /v1/systemone의 typed 결과·확률 분포를 사용하고, 최종 PASS는 실제 유효한 CVDP 평가로만 결정하라.
단계마다 문서의 완료 조건을 확인하고 계획 작성만으로 종료하지 말 것.
소규모 bounded contract/E2E와 A/B/C 비교를 수행하고, 실제 실행이 막힌 부분은 정확한 사유·증거·재실행 명령을 남겨라.
최종적으로 변경 파일, 검증 결과, 실측 개선, 미완료/차단 항목, 사용법을 보고하라.
```

