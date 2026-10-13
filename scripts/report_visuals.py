"""Accessible Korean, dependency-free SVG figures from public measurements only.

Each public API returns HTML figure strings. None is unknown, never a measured
zero; invalid numeric inputs raise ValueError. Tables preserve full input values.
No model score is interpreted as an evaluator outcome or success probability.
"""
from html import escape
from itertools import count
import math


_IDS = count(1)
_BLUE = '#2457c5'
_TEAL = '#00796b'
_RED = '#b3261e'
_AMBER = '#925c00'
_INK = '#192b42'
_SURFACE = '#eef3fa'


def reset_visual_ids():
    """Start a new independently rendered document set with reproducible IDs."""
    global _IDS
    _IDS=count(1)


def _number(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('측정값은 음이 아닌 유한한 숫자 또는 None이어야 합니다')
    if value < 0 or (isinstance(value, float) and not math.isfinite(value)):
        raise ValueError('측정값은 음이 아닌 유한한 숫자여야 합니다')
    return value


def _mapping(value):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError('보고서 데이터는 사전이어야 합니다')
    return value


def _get(data, key):
    return _number(data.get(key))


def _fmt(value):
    if value is None:
        return '미확인'
    return format(value, ',')


def _sum_known(values):
    if any(value is None for value in values):
        return None
    return _number(sum(values))


def _text(x, y, value, size=18, color=_INK, weight='400', anchor='start'):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
            f'font-weight="{weight}" text-anchor="{anchor}">{escape(str(value))}</text>')


def _table(headers, rows, caption='그림의 정확한 값'):
    head = ''.join(f'<th scope="col">{escape(str(cell))}</th>' for cell in headers)
    body = ''
    for row in rows:
        cells = f'<th scope="row">{escape(str(row[0]))}</th>'
        cells += ''.join(f'<td>{escape(str(cell))}</td>' for cell in row[1:])
        body += '<tr>' + cells + '</tr>'
    return (f'<div class="table-wrap"><table><caption>{escape(caption)}</caption>'
            f'<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')


def _figure(title, desc, content, height, caption, alternative, legend=''):
    uid = f'report-visual-{next(_IDS)}'
    return (f'<figure class="visual-card"><h3>{escape(title)}</h3>'
            f'<svg xmlns="http://www.w3.org/2000/svg" role="img" '
            f'aria-labelledby="{uid}-title {uid}-desc" width="100%" '
            f'viewBox="0 0 480 {height}" style="display:block;max-width:100%;height:auto" '
            f'font-family="sans-serif"><title id="{uid}-title">{escape(title)}</title>'
            f'<desc id="{uid}-desc">{escape(desc)}</desc>{content}</svg>'
            f'<figcaption>{escape(caption)}</figcaption>{legend}{alternative}</figure>')


def _legend(items):
    return '<ul class="visual-legend">' + ''.join(
        f'<li><span aria-hidden="true" style="color:{color}">■</span> '
        f'{escape(label)}</li>' for label, color in items
    ) + '</ul>'


def _status(value):
    label = '' if value is None else str(value)
    lower = label.lower()
    if any(word in lower for word in ('infra', 'blocked', '기반', '차단')):
        return '기반 환경 차단', _AMBER, True
    if any(word in lower for word in ('not run', 'not measured', '미실행', '미측정')):
        return '미측정', _AMBER, True
    if any(word in lower for word in ('fail', '실패')):
        return '실제 실패', _RED, False
    if any(word in lower for word in ('pass', 'success', '통과')):
        return '실제 통과', _TEAL, False
    return '결과 미확인', _AMBER, False


def _stack(x, y, width, pairs, maximum, arm=None):
    """Known components only; exact labels live beside bars, not tiny segments."""
    content = ''
    for value, color in pairs:
        if value is not None and value > 0 and maximum > 0:
            segment = width * (value / maximum)
            tag = '' if arm is None else f' data-arm="{escape(str(arm), quote=True)}"'
            content += (f'<rect x="{x:.3f}" y="{y}" width="{segment:.3f}" '
                        f'height="24" fill="{color}"{tag}/>')
            x += segment
    return content


def native_figures(rows: list[dict]) -> str:
    """A/B/C tokens and seconds; optional primary_calls/jev_calls verify zero calls."""
    parsed = []
    for row in rows:
        row = _mapping(row)
        primary = _get(row, 'primary_tokens')
        jev = _get(row, 'jev_tokens')
        wall = _get(row, 'wall_seconds')
        state, color, blocked = _status(row.get('status'))
        primary_calls, jev_calls = _get(row, 'primary_calls'), _get(row, 'jev_calls')
        note = ('실제 모델 호출 0 · 성능 0을 뜻하지 않음'
                if primary_calls == 0 and jev_calls == 0
                else '성능 미측정 · 호출 수 미확인')
        parsed.append((str(row.get('arm', '비교군 미확인')), state, color, blocked,
                       primary, jev, wall, note))
    maximum = max([sum(v for v in (p, j) if v is not None)
                   for _, _, _, blocked, p, j, _, _ in parsed if not blocked] + [0])
    max_wall = max([row[6] for row in parsed if row[6] is not None] + [0])
    tokens, duration, token_rows, time_rows = '', '', [], []
    for index, (arm, state, color, blocked, primary, jev, wall, note) in enumerate(parsed):
        y = 30 + index * 114
        tokens += _text(16, y, f'{arm} · {state}', 19, color, '600')
        total = _sum_known((primary, jev))
        if blocked:
            tokens += _text(16, y + 35, note, 17, _AMBER)
        elif primary is None and jev is None:
            tokens += _text(16, y + 35, '토큰 미확인 · 막대를 표시하지 않음', 17, _AMBER)
        else:
            tokens += _stack(16, y + 14, 448, [(primary, _BLUE), (jev, _TEAL)], maximum, arm)
        tokens += _text(16, y + 66, f'주 모델 {_fmt(primary)} / JEV {_fmt(jev)}', 17)
        tokens += _text(16, y + 89, f'합계 {_fmt(total)} 토큰', 17, weight='600')
        token_rows.append((arm, state, _fmt(primary), _fmt(jev), _fmt(total)))
        duration += _text(16, y, f'{arm} · {state}', 19, color, '600')
        if wall is None:
            duration += _text(16, y + 45, '종료 시간 미확인', 17, _AMBER)
        else:
            duration += _stack(16, y + 14, 448, [(wall, color)], max_wall, arm)
            duration += _text(16, y + 65, f'{_fmt(wall)} 초', 19, weight='600')
        time_rows.append((arm, state, _fmt(wall)))
    if not parsed:
        tokens = duration = _text(16, 38, '측정 자료 미확인', color=_AMBER)
    height = max(90, len(parsed) * 114 + 15)
    caption = '실제 사용 토큰만 비교합니다. 기반 환경 차단은 유효 성능 측정이 아니며, 미확인 값은 0으로 바꾸지 않습니다.'
    caution = '성공과 실패의 종료 시간은 속도 우열로 비교할 수 없습니다'
    return (_figure('네이티브 A/B/C · 실제 토큰 사용량', caption, tokens, height, caption,
                    _table(('비교군', '결과', '주 모델 토큰', 'JEV 토큰', '합계 토큰'), token_rows),
                    _legend((('주 모델 토큰 · 파랑', _BLUE), ('JEV 토큰 · 청록', _TEAL))))
            + _figure('네이티브 A/B/C · 종료까지 걸린 시간', caution, duration, height,
                      caution + '. 단위: 초. A는 기반 환경 차단까지의 시간입니다.',
                      _table(('비교군', '결과', '종료 시간(초)'), time_rows)))


def baseline_figures(metrics: dict) -> str:
    """Whole-baseline evaluator outcome donut and explicitly incomplete usage."""
    baseline = _mapping(_mapping(metrics).get('baseline'))
    status = _mapping(baseline.get('status_counts'))
    cases = _get(baseline, 'case_count')
    values = [_get(status, key) for key in ('success', 'failure', 'timeout')]
    known = _get(baseline, 'reported_total_tokens')
    unknown = _get(_mapping(baseline.get('primary')), 'unknown_usage_calls')
    labels = ('통과', '실패', '시간 초과')
    colors = (_TEAL, _RED, _AMBER)
    content = '<circle cx="130" cy="125" r="82" fill="none" stroke="#e1e8f2" stroke-width="28"/>'
    if cases and all(v is not None for v in values):
        circumference = 2 * math.pi * 82
        offset = 0
        for value, color in zip(values, colors):
            length = value / cases * circumference
            if value:
                content += (f'<circle cx="130" cy="125" r="82" fill="none" stroke="{color}" '
                            f'stroke-width="28" stroke-dasharray="{length:.6f} {circumference:.6f}" '
                            f'stroke-dashoffset="{-offset:.6f}" transform="rotate(-90 130 125)"/>')
            offset += length
    content += _text(130, 122, _fmt(cases), 30, weight='700', anchor='middle')
    content += _text(130, 148, '전체 과제 수', 16, anchor='middle')
    for i, (label, value, color) in enumerate(zip(labels, values, colors)):
        content += _text(246, 85 + i * 40, f'{label} {_fmt(value)}개', 19, color, '600')
    content += _text(16, 250, f'알려진 토큰: {_fmt(known)}', 20, _BLUE, '600')
    content += _text(16, 283, f'사용량 미확인 호출: {_fmt(unknown)}건', 19, _AMBER)
    caption = '전체 기준 실행의 실제 평가 결과입니다. 알려진 토큰은 보고된 사용량이며 전체 토큰 합계가 아닙니다. 미확인 호출의 토큰을 0으로 간주하지 않습니다.'
    rows = [(label, _fmt(value), '과제') for label, value in zip(labels, values)]
    rows += [('전체 과제', _fmt(cases), '과제'), ('알려진 토큰', _fmt(known), '토큰'),
             ('사용량 미확인 호출', _fmt(unknown), '호출')]
    return _figure('전체 기준 실행 · 평가 결과와 사용량 범위', caption, content, 310,
                   caption, _table(('항목', '정확한 값', '단위'), rows),
                   _legend(tuple(zip(labels, colors))))


def audit_figures(metrics: dict) -> str:
    """Decision audit partitions, not a benchmark-success or accuracy funnel."""
    audit = _mapping(_mapping(metrics).get('audit'))
    executed = _get(audit, 'executed_count')
    valid = _get(audit, 'valid_decisions')
    errors = _get(audit, 'decision_errors')
    accepted = _get(audit, 'accepted_decisions')
    fallback = _get(audit, 'would_fallback_count')
    agree = _get(audit, 'primary_proxy_agree_count')
    labeled = _get(audit, 'primary_proxy_labeled_count')
    actual_fallback = _get(audit, 'actual_primary_fallback_calls')
    maximum = executed or max([v for v in (valid, errors, accepted, fallback) if v is not None] + [0])
    content = _text(16, 32, f'실행 {_fmt(executed)}건', 23, _BLUE, '700')
    content += _stack(16, 48, 448, [(executed, _BLUE)], maximum)
    content += _text(240, 101, '↓ 계약 검사', 18, anchor='middle')
    content += _text(16, 134, f'스키마 유효 {_fmt(valid)} / 오류 {_fmt(errors)}', 19, weight='600')
    content += _stack(16, 151, 448, [(valid, _TEAL), (errors, _RED)], maximum)
    content += _text(240, 203, '↓ 전체 실행의 승인 여부', 18, anchor='middle')
    content += _text(16, 235, f'승인 {_fmt(accepted)} / 대체 필요 {_fmt(fallback)}', 19, weight='600')
    content += _stack(16, 252, 448, [(accepted, _TEAL), (fallback, _AMBER)], maximum)
    content += _text(16, 310, f'과거 대리 지표 일치: {_fmt(agree)} / {_fmt(labeled)}', 18)
    caption = ('승인은 판단 계약의 승인이지 벤치마크 성공률이 아닙니다. '
               '대체 필요 수에는 계약 오류가 포함되며, 실제 대체 호출과 다릅니다. '
               '과거 대리 지표와의 일치는 의미 정확도가 아닙니다.')
    rows = [('실행', executed), ('스키마 유효', valid), ('판단 오류', errors),
            ('승인', accepted), ('대체 필요', fallback), ('실제 주 모델 대체 호출', actual_fallback),
            ('과거 대리 지표 레이블', labeled), ('과거 대리 지표 일치', agree)]
    return _figure('판단 감사 · 실행 → 계약 검사 → 승인', caption, content, 334, caption,
                   _table(('항목', '정확한 값(건)'), [(label, _fmt(v)) for label, v in rows]),
                   _legend((('실행 · 파랑', _BLUE), ('유효 또는 승인 · 청록', _TEAL),
                            ('오류 · 빨강', _RED), ('대체 필요 · 황갈색', _AMBER))))


def historical_comparison_figures(metrics: dict) -> str:
    """Historical single-case primary/JEV stacks (tokens), not general effects."""
    metrics = _mapping(metrics)
    parsed = []
    for key, label in (('baseline', '기준 실행'), ('jev', 'JEV 적용')):
        data = _mapping(metrics.get(key))
        total = _get(data, 'reported_total_tokens')
        primary = _get(_mapping(data.get('primary')), 'reported_total_tokens')
        jev = _get(_mapping(data.get('jev')), 'reported_total_tokens')
        cases = _get(data, 'case_count')
        parsed.append((key, label, total, primary, jev, cases))
    maximum = max([sum(v for v in (p, j) if v is not None) for _, _, _, p, j, _ in parsed] + [0])
    content, rows = '', []
    for i, (key, label, total, primary, jev, cases) in enumerate(parsed):
        y = 32 + i * 118
        content += _text(16, y, f'{label} · 과제 {_fmt(cases)}개', 19, weight='600')
        content += _stack(16, y + 16, 448, [(primary, _BLUE), (jev, _TEAL)], maximum,
                          'JEV' if key == 'jev' else '기준')
        content += _text(16, y + 65, f'주 모델 {_fmt(primary)} / JEV {_fmt(jev)}', 17)
        content += _text(16, y + 90, f'보고된 합계 {_fmt(total)} 토큰', 18, weight='600')
        rows.append((label, _fmt(cases), _fmt(primary), _fmt(jev), _fmt(total)))
    before, after = parsed[0][2], parsed[1][2]
    if before and after is not None:
        change = (after / before - 1) * 100
        delta = f'{change:+.2f}%'
    else:
        delta = '미확인'
    content += _text(16, 291, f'보고된 토큰 변화: {delta}', 21, _AMBER, '600')
    caption = ('과거 과제 1개 비교이며 최신 A/B/C와 다른 실험입니다. '
               '관측된 토큰 변화는 일반화 가능한 효과나 JEV의 우위를 입증하지 않습니다. 단위: 토큰.')
    return _figure('과거 단일 과제 · 실제 토큰 비교', caption, content, 318, caption,
                   _table(('실행', '과제 수', '주 모델 토큰', 'JEV 토큰', '보고된 합계 토큰'), rows),
                   _legend((('주 모델 토큰 · 파랑', _BLUE), ('JEV 토큰 · 청록', _TEAL))))


def flow_diagram() -> str:
    """Vertical repair loop with deterministic gates before finite SystemOne choice."""
    steps = [
        ('주 모델 생성', '검증할 후보 RTL 생성'),
        ('정규화 → 준비 묶음', '후보와 평가 입력을 일관되게 준비'),
        ('실제 CVDP 평가', '실제 도구 결과와 증거 수집'),
        ('결정적 종료 게이트', 'PASS · 기반 환경 차단 · 예산 종료 → 정지'),
        ('SystemOne · 허용된 유한 선택', '종료하지 않은 적격 상태에서만 실행'),
        ('각 대안 자체의 Noul 적합도·위험도', 'Score 증거와 계약 검사 · 무효 시 대체'),
        ('주 모델 수정', '승인된 판단 또는 기존 대체 경로 적용'),
        ('실제 평가 피드백 → 재평가', '수정 후보는 실제 CVDP 결과로 다시 확인'),
    ]
    content = ''
    for i, (label, detail) in enumerate(steps):
        y = 16 + i * 112
        gate = i == 3
        color = _AMBER if gate else _BLUE
        content += (f'<rect x="16" y="{y}" width="448" height="82" rx="20" '
                    f'fill="{_SURFACE}" stroke="{color}" stroke-width="2"/>')
        content += _text(32, y + 31, f'{i + 1}. {label}', 19, color, '600')
        content += _text(32, y + 59, detail, 16)
        if i < len(steps) - 1:
            arrow = '↓ 종료가 아닌 경우' if gate else '↓'
            content += _text(240, y + 105, arrow, 17, anchor='middle')
    # The repair loop returns to the actual evaluator, never directly to Score.
    content += (f'<path data-feedback="actual-evaluation" d="M464 841 H474 V281 H464" '
                f'fill="none" stroke="{_TEAL}" stroke-width="2" stroke-dasharray="5 4"/>'
                f'<path d="M470 276 L464 281 L470 286" fill="none" '
                f'stroke="{_TEAL}" stroke-width="2"/>')
    caption = ('PASS·기반 환경 차단·예산 종료는 모델 선택보다 먼저 결정적으로 처리합니다. '
               '적격 상태에서만 유한 대안을 선택하고 각 대안 자체의 적합도·위험도와 Score 증거를 검사합니다. '
               '모델의 판단 확률이나 기대 점수는 벤치마크 성공 확률이 아닙니다. '
               '수정 → 실제 CVDP 평가 → 종료 게이트로 되돌아갑니다.')
    alternative = '<ol class="visual-steps">' + ''.join(
        f'<li><strong>{escape(label)}</strong> — {escape(detail)}</li>' for label, detail in steps
    ) + '</ol>'
    return _figure('생성부터 실제 평가 피드백까지', caption, content, 912, caption, alternative)
