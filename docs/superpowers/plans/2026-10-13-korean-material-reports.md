# 한국어 시각화 보고서 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 사용자가 지정한 한국어·그래프/다이어그램·Material 디자인과 전체 PR 병합 요구를 적용한다.

**Goal:** 실제 측정과 제한을 보존하며 모든 공개 보고서를 한국어로 읽을 수 있는 Material 3 기반 시각화 사이트로 배포한다.
**Architecture:** Markdown 원문과 공개 JSON을 유지하고, 허용 목록 기반 정적 빌더에 공통 Material UI와 접근성 있는 SVG를 결합한다. 과거 HTML 복사 대신 한국어 원문의 공통 렌더링을 사용한다.
**Tech Stack:** Python 표준 라이브러리, HTML/CSS, 인라인 SVG, GitHub Pages gh-pages 하위 트리.
**Spec:** 사용자 지시: 보고서 전부 한국어, 그래프와 다이어그램으로 시각적 개선, 최소 Material 디자인, PR 모두 병합.

## Global Constraints
- 측정 수치·분모·시간·해시·코드 식별자는 변경하지 않는다. 설명과 UI 문구는 한국어다.
- C 실패의 짧은 종료 시간을 성공 대비 속도 개선으로 표시하지 않는다. unknown/미실행은 0 또는 성공이 아니다.
- 새 모델/평가 호출 없이 기존 공개 원문·JSON만 사용한다. 기존 허용 목록과 입력/출력 심볼릭 링크 방어를 유지한다.
- 기본 저장소 main·endpoint 설정·로컬 실행 증거는 수정하거나 삭제하지 않는다. 기존 Pages 작업 워크트리를 재사용한다.

## Review Focus
- 그래프 수치와 표·원본이 일치하고 과거 실험과 최신 A/B/C가 섞이지 않는지 확인한다.
- 작은 화면에서 SVG 라벨·표·목차가 잘리거나 문서 전체 가로 스크롤을 만들지 않는지 확인한다.
- 화면 문구와 접근성 이름이 한국어인지, 코드와 데이터 키만 원문을 유지하는지 확인한다.
- 색상 외에 문자·범례·설명이 결과와 불확실성을 전달하는지 확인한다.
- 새 그림·원문·공개 데이터 외 private/log/prompt 파일이 배포에 들어가지 않는지 확인한다.

### 1. 한국어 원문 (독립 담당 A)
- [x] `reports/jev-native-plan/final-report.md`, `docs/jev_completion_status.md`, `docs/jev_native_runbook.md`, `docs/jev_integration_audit.md`의 설명·제목·표를 한국어로 번역한다.
- [x] 숫자·해시·코드·링크를 전후 비교하고 제한/미완료 문장을 보존한다.

### 2. 과거 보고서 한국어 (독립 담당 B)
- [x] `scripts/report_localization.py`의 `localize_report_markdown(text)`와 정확한 공통 문구 번역을 RED→GREEN 테스트한다.
- [x] `reports/*/*.md`의 과거 보고서(최신 native 제외)를 코드/수치 보존해 번역한다. 원본 JSON/CSV는 변경하지 않는다.
- [x] 과거 HTML 생성기가 다시 영어를 내보내지 않도록 표현 계층에 번역을 적용한다. 기존 실험/계산 로직은 변경하지 않는다.

### 3. 시각화 (독립 담당 C)
- [x] `scripts/report_visuals.py`, `tests/test_report_visuals.py`: `native_figures(rows)`, `baseline_figures(metrics)`, `audit_figures(metrics)`, `historical_comparison_figures(metrics)`, `flow_diagram()`을 RED→GREEN 구현한다.
- [x] 한글 `<title>/<desc>`·수치·범례·비교 제한을 포함하는 반응형 SVG를 생성한다. 비수치/unknown/음수는 정직하게 처리한다.

### 4. Material UI 및 통합 (통합 담당)
- [x] `scripts/build_report_pages.py`와 `tests/test_report_pages.py`: Material 3 색상/표면/그림자/모양/서체 토큰, 상단 앱 바, 요약 카드, 상태 칩, 목차, 섹션 앵커, 반응형 표를 테스트 후 구현한다.
- [x] 최신/과거 원문을 같은 한국어 UI로 렌더링하고 실측 SVG·흐름도·확장 상태를 배치한다. 허용 목록·자료 해시·안전한 HTML 처리를 유지한다.

### 5. 검증·병합·게시
- [x] 전체 pytest, 링크/앵커/파일 목록/원본 수치 검증, 브라우저 큰 화면·모바일 점검을 실행한다. 332개 통과, 1440px/390px 점검.
- [x] 읽기 전용 리뷰의 실제 결함을 RED→GREEN 수정한다. 동일 프로세스 반복 생성 일치, 당시 검증 수 명확화, 모바일 앱 바 앵커 여백.
- [ ] 변경을 커밋·푸시·PR 생성 후 사용자 승인(모든 PR 병합)에 따라 병합한다.
- [ ] site 하위 트리만 gh-pages에 일반 푸시하고 배포/HTTP/브라우저/manifest 일치를 확인한다.
