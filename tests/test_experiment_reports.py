import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


def report():
    return importlib.import_module('experiment_reports')


def batch(mode, tokens, seconds):
    provider = {'calls':2, 'reported_prompt_tokens':tokens-20, 'reported_completion_tokens':20,
                'reported_total_tokens':tokens,'estimated_total_tokens':0,'unknown_usage_calls':0,
                'latency_seconds':8, 'latency_complete':True,'fallback_calls':0,'error_calls':0}
    empty = {'calls':0,'reported_prompt_tokens':0,'reported_completion_tokens':0,
             'reported_total_tokens':0,'estimated_total_tokens':0,'unknown_usage_calls':0,
             'latency_seconds':0,'latency_complete':True,'fallback_calls':0,'error_calls':0}
    decision=dict(empty)
    if mode=='jev':
        # Arithmetic fixtures represent an actually exercised decision hook.
        decision.update(calls=1,reported_prompt_tokens=10,reported_completion_tokens=1,reported_total_tokens=11)
        provider.update(reported_prompt_tokens=tokens-31,reported_total_tokens=tokens-11)
    return {'manifest':{'mode':mode, 'state':'completed','cases_planned':2,'case_ids':['a','b'],
                       'conditions':{'attempts':1,'iterations':5,'workers':4},
                       'environment':{'dataset_sha256':'fixture','cvdp_commit':'fixed',
                                      'configuration':{'primary_model':'same','sampling_mode':'default'}},
                       'elapsed_seconds':seconds},
            'results':[{'id':'a','status':'success','elapsed_seconds':10,
                        'metrics':{'total_tokens_complete':True,'primary':provider,'jev':decision}},
                       {'id':'b','status':'failure','elapsed_seconds':20,
                        'metrics':{'total_tokens_complete':True,'primary':empty,'jev':empty}}]}


def test_measured_savings_and_success_denominator():
    base, jev = batch('baseline',150,30), batch('jev',100,20)
    metrics=report().batch_metrics(base)
    assert metrics['case_count']==2 and metrics['success_count']==1
    assert metrics['success_rate']==0.5 and metrics['average_case_seconds']==15
    comparison=report().compare(base,jev)
    assert comparison['token_savings_percent']==pytest.approx(100/3)
    assert comparison['wall_time_savings_percent']==pytest.approx(100/3)


def test_unknown_usage_suppresses_token_savings():
    base, jev = batch('baseline',150,30), batch('jev',100,20)
    jev['results'][0]['metrics']['primary']['unknown_usage_calls']=1
    jev['results'][0]['metrics']['total_tokens_complete']=False
    comparison=report().compare(base,jev)
    assert comparison['token_savings_percent'] is None


def test_incomplete_run_has_no_success_rate_or_savings():
    base, jev = batch('baseline',150,30), batch('jev',100,20)
    jev['manifest']['state']='running';jev['results']=[]
    assert report().batch_metrics(jev)['success_rate'] is None
    assert report().compare(base,jev)['token_savings_percent'] is None
    assert report().compare(base,jev)['wall_time_savings_percent'] is None


def test_different_case_sets_or_budgets_are_not_fair_comparison():
    base, jev = batch('baseline',150,30), batch('jev',100,20)
    jev['manifest']['conditions']['iterations']=3
    with pytest.raises(ValueError,match='conditions'):
        report().compare(base,jev)


def test_missing_improved_mode_is_unavailable_not_zero():
    text=report().render_markdown(batch('baseline',150,30), None)
    assert '미실행' in text
    assert '33.3%' not in text


def test_updated_jev_config_does_not_change_primary_matched_conditions():
    base, jev = batch('baseline',150,30), batch('jev',100,20)
    base['manifest']['environment']['configuration']['jev_model']='old-unused-model'
    jev['manifest']['environment']['configuration']['jev_model']='new-approved-model'
    assert report().compare(base,jev)['token_savings_percent']==pytest.approx(100/3)


def test_real_service_timeout_is_not_hidden_as_functional_failure():
    data=batch('baseline',150,30)
    data['results'][1]['result']={'passed':False,'attempts':[{'history':[{'primary_failure':{'stage':'CANDIDATE_FUNCTIONAL'},'result':{'tests':[{'result':124,'error_msg':'native harness timeout after 300s'}]}}]}]}
    assert report().batch_metrics(data)['status_counts']=={'success':1,'timeout':1}
    assert '| `b` | 시간 초과 |' in report().render_markdown(data,None)


def test_generated_csv_uses_portable_lf_line_endings(tmp_path,monkeypatch):
    import json
    source=tmp_path/'batch';source.mkdir();output=tmp_path/'report'
    (source/'summary.json').write_text(json.dumps(batch('baseline',150,30)))
    monkeypatch.setattr(sys,'argv',['report','--baseline',str(source),'--output',str(output)])
    report().main()
    assert b'\r' not in (output/'cases.csv').read_bytes()
