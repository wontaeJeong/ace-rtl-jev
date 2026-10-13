# JEV 네이티브 통합 감사

## 시작 상태 (2026-10-12)

- 원래 `main`의 `HEAD`: `880b7c9eb362b66c500cb2943ad8f85ee39ad9c5` (`origin/main`보다 커밋 11개 앞섬).
- 기본 저장소에는 추적되지 않은 구현 지시 문서만 있었다. 추적 제외된 `.env.local`은 값을 출력하지 않고 보존했다.
- 갱신된 `origin/main`에서 워크트리 `implementation/jev-full-plan`을 만든 뒤, 사용자 어댑터와 실측 보고서를 유지하도록 원래 `HEAD`로 빨리 감기했다.
- `CodeGraph` 색인은 없으며, 프로젝트 `AGENTS.md`도 발견되지 않았다.
- 기존 격리 환경의 기준 검증: 테스트 71개 통과. 시스템 Python에는 `pytest`가 없으므로 로컬 환경을 구성하기 전까지 준비된 Python을 사용한다.

## 수정 전 활성 호출 흐름

`ace_cvdp_native_runner.py -> ace_cvdp_native.cli.main -> run_datapoint -> attempt_worker_main -> run_attempt`.
`run_attempt -> processor.prepare(model=AceIterationModel) -> AceIterationModel.prompt -> run_role_call -> llm_call.py -> ACE_RTL_LLM_SCRIPT / llm_backend`.
`run_attempt -> processor.run -> patched native_obj_harness -> real service results -> result_passed`.
후보 실패 시: `record_reflector_iteration_result -> FocusedDebugger.extract_implementation_changes`, 다음 `call_coordinator -> FreshStartCoordinator.should_fresh_start`, 다음 `call_reflector -> FocusedDebugger.create_focused_prompt`.
기존 JEV 연결 지점(`scripts/jev_retrospective.py`)은 `Choice` 판단만 지원하며, 설명문 기반 회고 분류에 영향을 준다. 타입이 명시된 네이티브 상태·동작 계약은 아니다.
별도 기존 에이전트는 `ace_agent_runner.py -> ace_rtl_agent.main/agent/agent_loop`다. `ContextBuilder`/`IterationMemory`/`ComprehensiveReasoningCoordinator`는 네이티브 통합 대상이 아니다.

## 경계

수정 전 회고기는 비 RTL 과제에서 `.env`, 검사기 Python, 구성 파일을 읽는다. 이를 새 모델 입력으로 사용하는 것은 안전하지 않다. 새 네이티브 맥락은 행에 선언된 공개 입력 맥락만 사용하고 모든 변경 가능 대상을 제외한다. 진단은 정제된 출력 결과로 제한하며, 숨겨진 검사기·참조 소스는 읽지 않는다.
실제 평가기만 통과(`PASS`)를 판정할 권한이 있다. 비어 있거나 미완료인 서비스 결과는 성공이 아니다.

## 담당 범위와 공유 인터페이스

공유 불변 데이터 클래스는 `ace_rtl_agent/decision/types.py`에 있으며, 모든 사용자는 `to_dict()`로 직렬화한다. 통합 담당자가 타입, 네이티브 `cli.py`/`llm.py`, 통합 테스트를 맡는다.

| 담당자 | 독점 담당 범위 |
|---|---|
| 관측 | 네이티브 진단·실행 기반·설정, `decision/observations.py`, 과제 감지·오류 분석, `tests/test_decision_observations.py` |
| 실행 관리 | 네이티브 `processes.py`, `decision/budget.py` `ledger.py` `cache.py`, `backend/client/llm_call.py`, `tests/test_decision_runtime.py` |
| SystemOne 판단 서비스 | `decision/systemone_client.py` `questions.py`, `tests/test_decision_systemone.py` |
| 정책·맥락 | `decision/policy.py` `state_builder.py` `strategies.py` `context_selector.py`; 집중 이력·지침·프롬프트 구성·디버거·타입·조정기·규칙 조언기; `tests/test_decision_policy.py` |
| 확장 | `decision/extensions.py` `offline.py`; `scripts/decision_offline.py`; `tests/test_decision_extensions.py` |
| 통합 | `cli.py`/`llm.py`/`types.py`/`settings.py`, 실행기·보고서 문서·통합 테스트 |

담당자는 다른 담당자의 파일 수정, 사용자 변경 초기화, 유료 호출, 공유 작업 커밋을 해서는 안 된다.

## 실제 CVDP와의 대응

설치된 프레임워크 커밋: `8e894cf74414ab1eaea1e2b4e80a02f123df07b6`. `DatasetProcessor.prepare -> create_repo -> get_context_for_repo -> model.prompt`, 이후 `Repository.prepare -> restore_files -> write_file` 순서다. 복원은 템플릿 치환을 수행한다. 따라서 네이티브 결합은 `repo.issue_path`에서 **선언된 변경 가능 파일만** 읽고, 정규화된 출력을 별도로 보존하며, 실제 준비·평가된 바이트의 해시를 계산한다. 개선 단계의 `include_harness/include_golden_patch`는 강제로 거짓으로 설정하며, 해당 프레임워크 경로는 사용하지 않는다.

실제 데이터셋의 서비스 정의는 단순히 `row.harness["docker-compose.yml"]`이 아니라 `row.harness.files["docker-compose.yml"]` 아래에 있다. 실제 행 검사로 차이를 확인했고, 회귀 테스트가 설치된 형태를 고정한다. 버스 중재기는 `direct`, 부호 있는 덧셈기는 `01-new-tb`를 요구한다. 보고서는 서비스 이름 하나를 가정하지 않고 각 과제의 실제 명세를 사용해야 한다.

## F01–F20 처리 결과

| 식별자 | 활성 수정 기준 실행·핵심 경로의 처리 | 증거 |
|---|---|---|
| F01 | 수정: 타입이 명시된 관측·효과가 초점 제어; 설명문은 기존 경로로 격리 | `test_decision_policy.py`, `focused_history.record_observation` |
| F02 | 실행으로 해결이 입증되는 경우 수정; 사라진 증상은 미확인으로 유지; 새 증상 식별자는 초점 변경 가능 | 관측 효과·이름 있는 증상 테스트, 정책 초점 적격성 |
| F03 | 수정: 사용 불가 사유가 있는 결측 허용 지표; 가공의 불일치 개선 없음 | 관측 지표 가용성·비교 가능성 테스트 |
| F04 | 수정: 회고 호출 없이 기준 실행을 항상 저장·기록 | 네이티브 종료·기준 실행 통합 테스트 |
| F05 | 수정: 완전한 묶음, 파일별 차이, 모든 대상을 회고기에 전달 | 타입·두 번째 파일·회고기 묶음 테스트 |
| F06 | 수정: 공개 불변 맥락에서 모든 변경 가능 대상 제외, 초기 대상은 별도 출처 이력 보유 | 네이티브 공개 맥락·계약 테스트 |
| F07 | 수정: 역할 간 표준 과제 계약 공유; 부정·부수적 코드로 재분류하지 않음 | 과제 감지·메타데이터 검증용 표본 |
| F08 | 수정: 도구 이름 언급만으로 컴파일 실패를 판정하지 않음 | 관측·오류 분석 검증용 표본 |
| F09 | 수정: 서비스별 최적화 지침 | 기본 점검 통과(`PASS`)·합성 실패(`FAIL`) 검증용 표본 |
| F10 | 네이티브에서 수정: 구조화된 식별자·개수; 미지원 개수는 미확인 | 중복 제거·개수 검증용 표본; 설명문은 호환 경로에만 유지 |
| F11 | 수정: 시간 초과는 미완료·미확인이지 기능 성공이 아님 | 시간 초과·효과 테스트 |
| F12 | 수정: 필수 서비스, 유효 종료 코드, 비어 있지 않은 권위 있는 기록, 필수 검사의 실제 실행 | 빈 결과·누락·건너뛰기·잘린 진단 검증용 표본; 실제 검증된 명세 |
| F13 | 수정: 결정적 감사·효과 기록이 종료 검사에 선행; 선택적 호출 생략 | 네이티브 통과(`PASS`)·마지막 반복의 호출 0회 검증용 표본 |
| F14 | 수정 기준 실행·핵심 경로의 타입 명시 원인과 검증된 통과 주장 검사; 부모 취소 증거 영속화 | 부모 기한·취소 검증용 표본 |
| F15 | 수정: 후보·호출·결과 증거 보존, 임시 작업 파일만 정리 | 실행 정리 검증용 표본 |
| F16 | 수정: 배타적 OS 잠금, 산출물 영속성·해시 검증, 원자적 공개와 잘못된 주장 복구 | 동시·부분·비정상 종료 통과 주장 테스트 |
| F17 | 수정: 실제 기한·재시도와 사용량 한도 | 실행 백엔드·클라이언트·HTTP 테스트 |
| F18 | 수정: 구조화된 회고 결과, 생성기 프롬프트 중첩 없음; 전달 화면에서 원시·정규화 소스 제외 | 네이티브 회고·공개 후보 테스트 |
| F19 | 수정: 현재 에피소드와 보관된 에피소드 이력 분리 | 집중 분석·조정기 에피소드 검증용 표본 |
| F20 | 수정: 오해를 부르는 `error_reasoning=guidance` 제거 | 구조화된 회고 메타데이터 테스트 |

기존 호환 모드는 일부 참조 제어 의미를 의도적으로 유지한다. 원래 수정되지 않은 프로그램이나 새로운 타입 명시 제어 경로라고 소개하지 않는다.

## 실제 실행에서 확인한 사항 — 추정 성능 아님

1. 실제 혼합 `SystemOne` 요청이 `Choice`/`Noul`/`Score`를 받아들였고 사용량을 보고했다.
2. `94754d7`의 원본 A는 기존 조정기 백엔드에서 설정된 사용자 지정 주 모델을 초기화할 수 없다. 유료 호출은 0회이며 CVDP 평가는 없었다. 암묵적으로 수정하거나 대체하지 않았다.
3. 첫 B/C 실험은 실제 평가까지 도달했지만 불변 사전의 `Queue` `pickle` 복원에 실패했다. 명시적 전송 회귀 테스트와 생성자 기반 `pickle` 규약을 추가했고, 실패 실행의 영수증·산출물을 모두 보존했다.
4. 수정 후 재검사: B 버스 중재기는 통과(`PASS`) 검증, C 과제는 실패했다. C가 더 많은 전체 토큰을 사용했다. 이는 JEV 성능 개선이나 기본 모드 변경을 뒷받침하지 않는다.
5. 부호 있는 덧셈기 핵심 경로의 간이 검증은 필수 서비스 `01-new-tb`와 영속 명세·결과 해시를 검증했다. 처음부터 통과했으므로 JEV 수정 효과를 입증하지 않는다.
6. 일부 실제 `Score` 응답이 기대 점수·분포 일관성 검증에 실패했다. 엄격한 거부·기존 모델 대체 경로를 유지하며, 임의의 응답 본문 없이 스칼라 전용 검증 증거를 기록했다. 고정된 계약 묶음의 재실행은 유효했다. 간헐적 공급자 계약 실패와 유료 사용량은 계속 공개 기록에 남는다.
