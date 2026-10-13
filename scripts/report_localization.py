"""Static presentation translations; never modify experiment data or code spans."""
from __future__ import annotations

import re


# Exact methodology translations retain the original scope and uncertainty.
_PHRASES = {
    'Warmup is actual inference, excluded from evaluation metrics. Total wall time is concurrent batch wall time; average case time includes subprocess/evaluator/repair overhead. Retry calls, JEV calls and primary fallback calls count toward totals.': '준비 실행은 실제 추론이며 평가 지표에서 제외한다. 총 경과 시간은 동시 실행 배치의 실제 경과 시간이며, 평균 케이스 시간에는 하위 프로세스·평가기·수정 처리의 부가 시간이 포함된다. 재시도 호출, JEV 호출, 주력 모델 대체 호출을 모두 합산한다.',
    'An inflight/error call with unavailable usage is not assigned fictional zero cost. Unknown billing suppresses token savings. Char/4 estimates are labeled and cannot establish measured token savings. Provider caches/load time may be opaque; no custom cache was added.': '사용량이 없는 진행 중·오류 호출에는 비용이 없다고 임의로 가정하지 않는다. 과금이 미확인이면 토큰 절감률을 제시하지 않는다. 문자 수/4 추정치는 별도로 표시하며 실측 토큰 절감을 입증하지 못한다. 제공자의 캐시·적재 시간은 불투명할 수 있으며 별도 캐시는 추가하지 않았다.',
    'One bounded non-agentic no-commercial native cohort, not all CVDP workflows or original default budgets. Commercial rows are explicitly excluded by actual tool requirements. API stochasticity and remote latency remain uncontrolled; single-run differences are descriptive, not statistically established effects. Repetitions/ablation must be reported only when actually executed. See environment and opportunities documents for provenance, integrity rules and remaining work.': '비에이전트 방식·비상용 도구의 제한된 네이티브 평가군 한 묶음으로, 모든 CVDP 작업 흐름이나 원래 기본 예산을 포괄하지 않는다. 실제 도구 요구에 따라 상용 도구가 필요한 항목을 명시적으로 제외했다. API의 확률적 변동과 원격 지연은 통제하지 못했으며, 단일 실행 차이는 관찰 결과일 뿐 통계적으로 입증된 효과가 아니다. 반복·요소 제거 실험은 실제 실행한 경우에만 보고해야 한다. 출처·무결성 규칙·남은 작업은 환경 및 개선 기회 문서를 참고한다.',
    '**Retrospective hook not exercised:** zero evaluation-phase JEV calls. Observed differences are not JEV-attributable.': '**회고 판단 연결부 미사용:** 평가 단계 JEV 호출이 없다. 관찰된 차이를 JEV 효과로 볼 수 없다.',
    'Retrospective hook not exercised: zero evaluation-phase JEV calls; differences are not JEV-attributable.': '회고 판단 연결부 미사용: 평가 단계 JEV 호출이 없으며 차이를 JEV 효과로 볼 수 없다.',
    'No improved E2E data. No optimization or savings claim.': '개선 버전의 종단 간 실행 자료가 없다. 최적화나 절감을 주장하지 않는다.',
    'Matched measured case data only. Small-cohort stochastic outcomes do not establish general improvements.': '조건이 일치하는 케이스의 실측 자료만 비교한다. 작은 평가군의 확률적 결과는 일반적인 개선을 입증하지 않는다.',
    'Historical subset projection: original concurrent batch time is not reused; no controlled batch-wall speedup claim.': '과거 부분집합 추출: 원래 동시 실행 배치 시간을 재사용하지 않으며 통제된 배치 경과 시간의 속도 개선을 주장하지 않는다.',
    'Token estimates, unknown billing and primary currency prices are not treated as zero. Warmup is separate in performance statistics but included in spending controls.': '토큰 추정치·미확인 과금·주력 모델의 통화 가격을 0으로 처리하지 않는다. 준비 실행은 성능 통계에서 분리하되 지출 통제에는 포함한다.',
    'Self-contained HTML; no external assets or model inference used to render this report.': '독립 실행형 HTML이며 보고서 표시에 외부 자료나 모델 추론을 사용하지 않는다.',
    'REAL EVALUATOR EVIDENCE · NO INFERRED SUCCESSES': '실제 평가기 증거 · 성공을 추정하지 않음',
    'Full methodology, provider accounting and limitations': '전체 방법·제공자 사용량 집계·한계',
    'ACE-RTL measured comparison': 'ACE-RTL 실측 비교',
    'ACE-RTL measured report': 'ACE-RTL 실측 보고서',
    'ACE-RTL JEV budgeted evaluation': 'ACE-RTL JEV 제한 예산 검증',
    'Actual E2E not complete.': '실제 종단 간 실행이 완료되지 않았다.',
    'Baseline state': '기준 실행 상태', 'Improved state': '개선 실행 상태',
    'Retrospective hook coverage': '회고 판단 연결부 사용량',
    'evaluation-phase JEV calls (warmup excluded)': '평가 단계 JEV 호출 (준비 실행 제외)',
    'Measured token savings (%)': '실측 토큰 절감률 (%)',
    'Measured batch wall-time savings (%)': '실측 배치 경과 시간 절감률 (%)',
    'Conditions and measurement': '조건과 측정', 'Provider accounting': '제공자 사용량 집계',
    'Case outcomes': '케이스별 결과', 'Limitations': '한계',
    'reported + disclosed estimates': '보고된 사용량 + 공개된 추정치',
    'batch wall s': '배치 경과 시간, 초',
    'Mode/provider': '실행 방식/제공자', 'Reported input': '보고된 입력 토큰',
    'Reported output': '보고된 출력 토큰', 'Reported total': '보고된 총 토큰',
    'Estimated total': '추정 총 토큰', 'Unknown usage calls': '사용량 미확인 호출',
    'Fallback calls': '대체 호출', 'Mean latency (s)': '평균 지연 (초)',
    'Baseline s': '기준 실행 시간 (초)', 'JEV s': 'JEV 시간 (초)',
    'baseline/primary': '기준 실행/주력 모델', 'baseline/jev': '기준 실행/JEV',
    'jev/primary': 'JEV 실행/주력 모델', 'jev/jev': 'JEV 실행/JEV',
    'Baseline cases': '기준 실행 케이스', 'Baseline passed': '기준 실행 성공',
    'Known reported tokens': '확인된 보고 토큰', 'Complete total tokens': '완전한 총 토큰',
    'Known tokens': '확인된 토큰', 'Batch wall seconds': '배치 경과 시간 (초)',
    'Mean case seconds': '평균 케이스 시간 (초)', 'Mean API latency seconds': '평균 API 지연 (초)',
    'Failed/error cases': '실패·오류 케이스', 'Success rate': '성공률',
    'Not evaluated': '미평가', 'Not run': '미실행', 'NOT RUN': '미실행',
    'Unavailable': '자료 없음', 'unknown': '미확인',
    'True': '참', 'False': '거짓', 'None': '자료 없음',
    'environment_error': '환경 오류', 'execution_error': '실행 오류',
    'success': '성공', 'failure': '실패', 'timeout': '시간 초과',
    'Baseline': '기준 실행', 'baseline': '기준 실행', 'primary': '주력 모델',
    'coverage': '평가 범위', 'Calls': '호출 수', 'Cases': '케이스 수', 'Passed': '성공',
    'Metric': '지표', 'Case': '케이스',
    # Mixed-language historical narrative and visible metric labels.
    'selected_count': '선택 판단 수', 'executed_count': '실행 판단 수',
    'valid_decisions': '유효 판단 수', 'decision_errors': '판단 오류 수',
    'accepted_decisions': '수용 판단 수', 'would_fallback_count': '대체 호출 필요 판단 수',
    'historical_primary_tokens': '과거 주력 모델 토큰', 'actual_jev_tokens': '실제 JEV 토큰',
    'actual_jev_usd_known': '확인된 실제 JEV 비용 (USD)',
    'unknown_jev_usage_calls': 'JEV 사용량 미확인 호출',
    'accepted_point_token_reduction_percent': '수용 판단 부분집합 토큰 감소율 (%)',
    'primary_proxy_labeled_count': '주력 모델 대리 지표 판정 수',
    'primary_proxy_agree_count': '주력 모델 대리 지표 일치 수',
    'primary_proxy_agreement': '주력 모델 대리 지표 일치',
    'all_pass_oracle_count': '공식 전체 통과 기준 판정 수',
    'all_pass_resolved_count': '공식 전체 통과 중 해결 판단 수',
    'complete': '완료 여부', 'actual_primary_fallback_calls': '실제 주력 모델 대체 호출 수',
    'accepted_already_all_pass_count': '수용 판단 중 이미 전체 통과한 수',
    'accepted_historical_primary_tokens': '수용 판단의 과거 주력 모델 토큰',
    'accepted_actual_jev_tokens': '수용 판단의 실제 JEV 토큰',
    'hypothetical_tokens_with_historical_fallback': '과거 대체 호출을 가정한 시나리오 토큰',
    'primary_proxy_agreement_rate': '주력 모델 대리 지표 일치율',
    'all_pass_resolved_rate': '공식 전체 통과 중 해결 판단 비율',
    'schema-valid': '스키마 유효', 'decision error': '판단 오류',
    'would-fallback': '대체 호출 필요', 'actual fallback': '실제 대체 호출',
    'ground truth': '정답 기준', 'all-pass subset': '전체 통과 부분집합',
    'all-pass': '전체 통과', 'resolved': '해결 판단', 'evaluator': '평가기',
    'terminal': '종료 상태', 'opt-in': '선택적 활성화', 'cohort': '평가군',
    'snapshot': '시점 기록', 'emitted': '출력된', 'role metadata': '역할 메타데이터',
    'API event': 'API 사건 기록', 'bounded state': '제한된 상태',
    'finite-label': '유한한 선택지', 'trade-off': '상충 관계', 'agent': '에이전트',
    'fallback': '대체 호출', 'warmup': '준비 실행', 'redirect': '리디렉션',
    'tokens': '토큰', 'token': '토큰', 'UTF-8 bytes': 'UTF-8 바이트',
    'wrapper/output allowance': '래퍼·출력 여유분', 'opaque provider': '불투명한 제공자',
    'model ID': '모델 식별자', 'receipt USD': 'USD 영수증', 'credit cap': '사용 한도',
    'usage-unknown calls': '사용량 미확인 호출', 'clean baseline': '정리된 기준 실행',
    'historical per-case': '과거 케이스별', 'batch speedup': '배치 속도 개선',
    'batch': '배치', 'case': '케이스', 'confidence': '확신도',
    'proxy agreement': '대리 지표 일치', 'report compaction': '보고서 압축',
    'paired cohort': '짝지은 평가군', 'ablation': '요소 제거 실험',
    'Actual E2E': '실제 E2E 실행', 'Study': '연구',
    'API events': 'API 사건 기록', 'budget JSON snapshots': '예산 JSON 시점 기록',
    'private harness': '비공개 평가 장치', 'SQLite binary': 'SQLite 바이너리',
    'ignored': 'Git 추적 제외',
    'resolved였다': '해결로 판단했다', 'ground truth가': '정답 기준이',
    '실험적 opt-in으로': '실험적으로 선택 활성화하는 경로로',
    'cohort를': '평가군을', 'would-fallback과': '대체 호출 필요 판단과',
    'receipt USD는': 'USD 영수증은', 'credit cap이': '사용 한도가',
    'API events와': 'API 사건 기록과', 'budget JSON snapshots는': '예산 JSON 시점 기록은',
    # Also repair particles in already-localized historical prose.
    '해결 판단였다': '해결로 판단했다', '정답 기준가': '정답 기준이',
    '실험적 선택적 활성화으로': '실험적으로 선택 활성화하는 경로로',
    '평가군를': '평가군을', '대체 호출 필요과': '대체 호출 필요 판단과',
    'USD 영수증는': 'USD 영수증은', '사용 한도이': '사용 한도가',
    'API 사건 기록와': 'API 사건 기록과', '예산 JSON 시점 기록는': '예산 JSON 시점 기록은',
}

_TRANSLATIONS = re.compile(
    r'(?<![A-Za-z0-9_])(?:' + '|'.join(re.escape(key) for key in sorted(_PHRASES, key=len, reverse=True)) + r')(?![A-Za-z0-9_])'
)
_PROTECTED = re.compile(
    r'(?P<inline>`+)(?:(?!(?P=inline)).)*?(?P=inline)'
    r'|!?\[[^\]\n]*\]\((?:[^()\n]|\([^()\n]*\))*\)'
    r'|https?://[^\s<>]+'
    r'|(?<![A-Za-z0-9_])/(?:[A-Za-z0-9_.%-]+/)+[A-Za-z0-9_.%?=&-]+'
    r'|\b[a-fA-F0-9]{32,64}\b'
    r'|\b(?:cvdp_[A-Za-z0-9_]+)\b'
)


def _translate_prose(text: str) -> str:
    parts = []
    end = 0
    for match in _PROTECTED.finditer(text):
        parts.append(_TRANSLATIONS.sub(lambda m: _PHRASES[m.group()], text[end:match.start()]))
        token = match.group()
        # A link's label is prose, but its target must remain byte-identical.
        if re.match(r'!?\[', token):
            label_end = token.index('](')
            token = _TRANSLATIONS.sub(lambda m: _PHRASES[m.group()], token[:label_end]) + token[label_end:]
        parts.append(token)
        end = match.end()
    parts.append(_TRANSLATIONS.sub(lambda m: _PHRASES[m.group()], text[end:]))
    return ''.join(parts)


def localize_report_markdown(text: str) -> str:
    """Translate known report prose, retaining fences, code, links and numbers."""
    result = []
    fence = None
    for line in text.splitlines(keepends=True):
        marker = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if fence:
            result.append(line)
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not line[marker.end():].strip():
                fence = None
        elif marker:
            fence = marker[1]
            result.append(line)
        else:
            result.append(_translate_prose(line))
    return ''.join(result)


def localize_report_html(text: str) -> str:
    """Localize generated text nodes only; never rewrite markup or attributes."""
    return ''.join(part if part.startswith('<') else localize_report_markdown(part)
                   for part in re.split(r'(<code\b[^>]*>.*?</code>|<[^>]*>)', text, flags=re.DOTALL))
