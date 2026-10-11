import importlib
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))


def test_html_report_is_self_contained_and_escapes_case_text():
    from test_experiment_reports import batch
    report=importlib.import_module('experiment_reports')
    data=batch('baseline',150,30)
    data['manifest']['case_ids']=['<script>alert(1)</script>','b']
    data['results'][0]['id']='<script>alert(1)</script>'
    html=report.render_html(data,None)
    assert '<!doctype html>' in html.lower()
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;' in html
    assert 'Not run' in html
    assert 'src="http' not in html


def test_reported_usd_not_invented_for_unknown_primary_price():
    from run_experiments import aggregate_calls
    metrics=aggregate_calls([{'provider':'primary','status':'ok','usage':{'source':'reported','prompt_tokens':1,'completion_tokens':1,'total_tokens':2},'latency_seconds':1}])
    assert metrics['primary']['reported_usd'] is None
