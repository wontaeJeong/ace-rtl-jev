"""Public report charts retain exact measurements and uncertainty; no inference."""
import importlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]


def visuals():
    return importlib.import_module('report_visuals')


def public_metrics(report):
    return json.loads((ROOT / 'reports' / report / 'metrics.json').read_text())


def figures(html):
    root = ET.fromstring('<main>' + html + '</main>')
    for element in root.iter():
        element.tag = element.tag.rsplit('}', 1)[-1]
    return root.findall('figure')


def test_native_preserves_stacks_outcomes_and_failure_time_caution():
    html = visuals().native_figures([
        dict(arm='A', status='infra', wall_seconds=1.08, primary_tokens=0, jev_tokens=0,
             primary_calls=0, jev_calls=0),
        dict(arm='B', status='PASS', wall_seconds=37.23, primary_tokens=16624, jev_tokens=0),
        dict(arm='C', status='FAIL', wall_seconds=29.68, primary_tokens=16962, jev_tokens=32981),
    ])
    cards = figures(html)
    assert len(cards) == 2
    token_chart, time_chart = cards
    assert token_chart.attrib['class'] == 'visual-card'
    text = ''.join(token_chart.itertext())
    for value in ('16,624', '16,962', '32,981', '49,943', '기반 환경 차단', '실제 통과', '실제 실패'):
        assert value in text
    assert '호출 0' in text and '성능 0' in text
    # Infra A must not receive even a zero-width performance bar.
    assert not token_chart.findall(".//rect[@data-arm='A']")
    assert len(token_chart.findall(".//rect[@data-arm='C']")) == 2
    assert '성공과 실패의 종료 시간은 속도 우열로 비교할 수 없습니다' in ''.join(time_chart.itertext())
    for value in ('1.08', '37.23', '29.68', '초'):
        assert value in ''.join(time_chart.itertext())


def test_baseline_reports_real_denominator_and_incomplete_usage():
    html = visuals().baseline_figures(public_metrics('clean-baseline'))
    text = ''.join(ET.fromstring('<main>' + html + '</main>').itertext())
    for value in ('239', '52', '1', '292', '16,538,281', '33', '시간 초과', '알려진', '전체 토큰 합계가 아닙니다'):
        assert value in text
    assert '전체 토큰 합계: 16,538,281' not in text


def test_audit_distinguishes_contract_acceptance_from_evaluation_and_proxy_accuracy():
    html = visuals().audit_figures(public_metrics('jev-final'))
    text = ''.join(ET.fromstring('<main>' + html + '</main>').itertext())
    for value in ('48', '45', '3', '13', '35', '스키마 유효', '승인', '대체 필요', '성공률이 아닙니다', '정확도가 아닙니다', '1 / 19'):
        assert value in text
    assert '확률적 성공' not in text


def test_historical_single_case_chart_retains_both_token_components():
    html = visuals().historical_comparison_figures(public_metrics('jev-comparison'))
    root = ET.fromstring('<main>' + html + '</main>')
    text = ''.join(root.itertext())
    for value in ('45,979', '50,269', '45,280', '4,989', '+9.33%', '과제 1개', '일반화'):
        assert value in text
    assert len(figures(html)[0].findall(".//rect[@data-arm='JEV']")) == 2


def test_flow_contains_real_evaluation_feedback_and_deterministic_terminal_gate():
    html = visuals().flow_diagram()
    text = ''.join(ET.fromstring('<main>' + html + '</main>').itertext())
    for value in ('주 모델 생성', '정규화', '준비 묶음', '실제 CVDP', '결정적', 'PASS', '기반 환경', '예산', 'SystemOne', '유한', '각 대안 자체', 'Noul', 'Score', '주 모델 수정', '실제 평가 피드백', '성공 확률이 아닙니다'):
        assert value in text
    assert '→' in text


def test_every_chart_has_unique_accessible_svg_names_and_text_alternatives():
    v = visuals()
    html = v.native_figures([]) + v.baseline_figures({}) + v.audit_figures({}) + v.historical_comparison_figures({}) + v.flow_diagram() + v.flow_diagram()
    cards = figures(html)
    ids = []
    for card in cards:
        svg = card.find('svg')
        assert svg.attrib['role'] == 'img'
        assert svg.attrib['viewBox'].startswith('0 0 ')
        assert svg.attrib['width'] == '100%'
        assert svg.find('title').text and svg.find('desc').text
        labels = svg.attrib['aria-labelledby'].split()
        assert labels == [svg.find('title').attrib['id'], svg.find('desc').attrib['id']]
        ids.extend(labels)
        assert card.find('figcaption') is not None
        assert card.find('.//table') is not None or card.find('ol') is not None
    assert len(ids) == len(set(ids))
    assert '<script' not in html and 'https://' not in html


def test_unknowns_are_not_zero_bars_and_labels_are_escaped():
    html = visuals().native_figures([dict(arm='<script>', status=None, wall_seconds=None, primary_tokens=None, jev_tokens=None)])
    assert '<script>' not in html and '&lt;script&gt;' in html
    cards = figures(html)
    assert all('미확인' in ''.join(card.itertext()) for card in cards)
    assert not any(card.findall('.//rect[@data-arm]') for card in cards)


@pytest.mark.parametrize('value', [-1, float('nan'), float('inf'), 'unknown', True])
@pytest.mark.parametrize('field', ['wall_seconds', 'primary_tokens', 'jev_tokens'])
def test_native_invalid_numbers_are_rejected(value, field):
    row = dict(arm='B', status='PASS', wall_seconds=0, primary_tokens=0, jev_tokens=0)
    row[field] = value
    with pytest.raises(ValueError):
        visuals().native_figures([row])


@pytest.mark.parametrize('method,key,field', [
    ('baseline_figures', 'baseline', 'case_count'),
    ('audit_figures', 'audit', 'executed_count'),
    ('historical_comparison_figures', 'jev', 'reported_total_tokens'),
])
def test_metric_invalid_numbers_are_rejected(method, key, field):
    with pytest.raises(ValueError):
        getattr(visuals(), method)({key: {field: -1}})


def test_zero_denominators_do_not_create_invalid_svg_geometry():
    v = visuals()
    html = v.baseline_figures({'baseline': {'case_count': 0, 'status_counts': {'success': 0, 'failure': 0, 'timeout': 0}}})
    html += v.historical_comparison_figures({'baseline': {'reported_total_tokens': 0}, 'jev': {'reported_total_tokens': 0}})
    html += v.audit_figures({'audit': {'executed_count': 0, 'valid_decisions': 0, 'decision_errors': 0, 'accepted_decisions': 0, 'would_fallback_count': 0}})
    assert 'nan' not in html.lower() and 'inf' not in html.lower()
    assert '미확인' in html


def test_zero_tokens_do_not_imply_zero_calls_without_call_measurements():
    html = visuals().native_figures([dict(arm='A', status='infra', wall_seconds=1,
                                          primary_tokens=0, jev_tokens=0)])
    assert '실제 모델 호출 0' not in html
    assert '호출 수 미확인' in html


def test_flow_draws_feedback_to_actual_evaluation_not_to_a_model_score():
    svg = figures(visuals().flow_diagram())[0].find('svg')
    assert svg.find("path[@data-feedback='actual-evaluation']") is not None


def test_overflowing_arithmetic_is_rejected_instead_of_drawing_zero_width_bars():
    with pytest.raises(ValueError):
        visuals().native_figures([dict(arm='B', status='PASS', primary_tokens=1e308,
                                       jev_tokens=1e308, wall_seconds=1)])
