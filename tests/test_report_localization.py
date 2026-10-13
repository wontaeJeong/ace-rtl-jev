import importlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


def localizer():
    return importlib.import_module('report_localization').localize_report_markdown


def test_localizes_missing_status_and_full_measurement_prose():
    source = ('# ACE-RTL measured comparison\nNot run | Unavailable | unknown | success | failure | timeout\n'
              'Warmup is actual inference, excluded from evaluation metrics. Total wall time is concurrent batch wall time; average case time includes subprocess/evaluator/repair overhead. Retry calls, JEV calls and primary fallback calls count toward totals.')
    text = localizer()(source)
    assert 'ACE-RTL 실측 비교' in text
    assert '미실행 | 자료 없음 | 미확인 | 성공 | 실패 | 시간 초과' in text
    assert '평가 지표에서 제외' in text and '재시도 호출' in text
    assert 'Warmup is' not in text


def test_preserves_code_links_numbers_and_is_idempotent():
    source = ('# Case outcomes\n`success` `cvdp_copilot_0001` `/api/primary`\n'
              '[Case outcomes](https://example.org/Case-outcomes?q=unknown)\n'
              '```json\n{"status": "unknown", "success": 239}\n```\n'
              '~~~text\nNot run\n~~~\n'
              '45979 → 50269 (+9.33%), 43.794 → 65.415; 16,538,281 +33\n')
    text = localizer()(source)
    for protected in ('`success`', '`cvdp_copilot_0001`', '`/api/primary`',
                      'https://example.org/Case-outcomes?q=unknown',
                      '```json\n{"status": "unknown", "success": 239}\n```',
                      '~~~text\nNot run\n~~~'):
        assert protected in text
    assert re.findall(r'\d+(?:[,.]\d+)*', source) == re.findall(r'\d+(?:[,.]\d+)*', text)
    assert localizer()(text) == text


def test_generators_localize_ui_without_changing_metrics_or_escaping():
    from test_experiment_reports import batch
    report = importlib.import_module('experiment_reports')
    base = batch('baseline', 150, 30)
    base['results'][0]['id'] = '<script>alert(1)</script>'
    before = report.batch_metrics(base)
    markdown = report.render_markdown(base, None)
    html = report.render_html(base, None)
    assert '미실행' in markdown and '자료 없음' in markdown
    assert '미실행' in html and '실제 평가기 증거' in html
    assert 'Not run' not in html and 'Case outcomes' not in html
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html
    assert report.batch_metrics(base) == before


def test_preserves_bare_api_paths_and_html_code_identifiers():
    module = importlib.import_module('report_localization')
    assert module.localize_report_markdown('unknown /api/primary/unknown') == '미확인 /api/primary/unknown'
    assert module.localize_report_html('<code>success</code><p>unknown</p>') == '<code>success</code><p>미확인</p>'


def test_historical_reports_preserve_honest_baseline_and_e2e():
    root = Path(__file__).resolve().parents[1]
    final = (root / 'reports/jev-final/final-report.md').read_text()
    for literal in ('45979 → 50269 (+9.33%)', '43.794 → 65.415',
                    '| 유효 판단 수 | 45 |', '| 판단 오류 수 | 3 |',
                    '| 수용 판단 수 | 13 |', '| 대체 호출 필요 판단 수 | 35 |',
                    '239 성공 / 52 실패 / 1 시간 초과', '16,538,281 토큰 +33'):
        assert literal in final
    assert '통제된 배치 속도 개선으로 주장하지 않는다' in final
    for folder in ('clean-baseline', 'jev-final', 'jev-comparison', 'original-baseline', 'smoke'):
        for path in (root / 'reports' / folder).glob('*.md'):
            text = path.read_text()
            assert 'Warmup is actual inference' not in text
            assert 'Not run' not in text and 'Unavailable' not in text
            assert 'ground truth' not in text and 'schema-valid' not in text


def test_study_generator_localizes_visible_metric_labels_not_json_keys(tmp_path):
    study = tmp_path / 'study'
    study.mkdir()
    (study / 'study.json').write_text(json.dumps({'budget': {}}))
    (study / 'audit.json').write_text(json.dumps({
        'manifest': {'state': 'audit_completed', 'selected_count': 0}, 'results': []}))
    output = tmp_path / 'output'
    importlib.import_module('study_reports').generate(study, output)
    html = (output / 'final-report.html').read_text()
    markdown = (output / 'final-report.md').read_text()
    assert '<th>선택 판단 수</th>' in html
    assert '<th>실제 주력 모델 대체 호출 수</th>' in html
    assert 'Actual E2E not complete' not in html
    assert 'NOT RUN' not in html and 'NOT RUN' not in markdown
    assert '실험적으로 선택 활성화하는 경로로' in markdown
    data = json.loads((output / 'metrics.json').read_text())
    assert data['audit']['selected_count'] == 0
    assert data['full_292_case_jev_evaluation'] == 'NOT RUN'
