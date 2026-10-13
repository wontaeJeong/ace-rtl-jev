# 한국어 시각화 보고서 게시

공개 사이트: **https://wontaejeong.github.io/ace-rtl-jev/**.

최신 네이티브 검증과 과거 실험을 분리하여 게시한다. 설명·표·접근성 문구는 한국어로 표시하고, 식별자·경로·해시와 기계 판독용 데이터 키는 원문을 보존한다. 실제 실패·차단과 미확인 사용량을 숨기지 않으며 JEV 성능 우위를 주장하지 않는다. 사용자는 전체 PR 병합을 승인했다. 보고서 렌더링에는 추가 모델·평가기 호출이 없다.

## 시각적 구성

- Material 3 색상·표면·그림자·모양·서체 토큰을 사용한다. 외부 서체나 자바스크립트 라이브러리 없이 작동한다.
- 최신 비교: 주 모델/JEV 토큰 누적 막대, 결과별 종료 시간 그래프, 실제 평가와 판단의 흐름도.
- 과거 기준 실행: 292건의 통과·실패·시간 초과 분포와 미확인 호출을 구분하는 도넛.
- 과거 판단 실험: 48건의 스키마 검사와 수용·대체 필요 상태를 시각화한다. 수용률을 성공률로 부르지 않는다.
- 각 SVG에는 한국어 제목·설명·범례·정확한 값 표를 제공한다. 색상만으로 상태를 구분하지 않는다.
- 상단 앱 바, 상태 칩, 목차·절 앵커, 키보드 본문 바로가기, 모바일 표 스크롤과 줄바꿈을 제공한다.

## 생성과 검증

```bash
python3 scripts/build_report_pages.py --output site
python3 -m pytest tests/test_report_pages.py -q
```

빌더는 Python 표준 라이브러리만 사용한다. Markdown의 원시 HTML을 텍스트로 처리하고, 표·목록·코드·문서 링크를 렌더링한다. 입력·출력 심볼릭 링크와 허용 목록 밖 기존 출력을 거부하며 사용자 파일을 삭제하지 않는다.

`publication.json`에는 원문 해시와 정확한 출력 목록을 기록한다. 지정한 최신·과거 Markdown, 완료·감사·사용법 문서, 공개 실측 JSON과 정리된 JSON 요약만 입력으로 사용한다. 과거 HTML을 그대로 복사하지 않고 같은 한국어 Material 화면으로 다시 렌더링한다. 데이터셋, `external/`, `experiments/`, `outputs/`, 프롬프트·응답·원시 로그·SQLite·`.env`·비공개 실행 기반·검사기·참조 구현은 **배포 입력이 아니다**. 저장소 전체를 배포하지 않는다.

## 공개 산출물 전용 브랜치

Pages는 `gh-pages` 브랜치의 `/`와 `.nojekyll`을 사용한다. 추적된 공개 `site/` 하위 트리만 추출한다.

```bash
git add scripts/build_report_pages.py tests/test_report_pages.py docs/report_pages.md site
git commit -m "docs: publish public report site"
git subtree split --prefix site --branch publish/jev-pages-artifact
git push jev publish/jev-pages-artifact:gh-pages
```

후속 게시에는 필요할 경우 새로운 로컬 추출 브랜치 이름을 사용한다. 기존 게시 브랜치를 먼저 가져와 조사하고, 강제 푸시하거나 임의로 대체하지 않는다. 소스·테스트 변경은 PR로 제안하고 사용자의 전체 병합 승인에 따라 검증 후 병합한다. 사이트 게시에는 공개 산출물 브랜치만 사용한다.

저장소 관리자는 REST API의 `{ "branch": "gh-pages", "path": "/" }`와 빌드 방식 `legacy`로 Pages를 설정한다. GitHub 배포 완료와 목록·최신 보고서·JSON의 HTTP 응답을 확인한 뒤 게시 완료를 보고한다. 로컬 main, 기존 작업 워크트리와 추적 제외 실행 증거는 유지한다.
