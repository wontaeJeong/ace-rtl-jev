import importlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))


def test_recovery_uses_real_native_result_and_marks_missing_time(tmp_path):
    root=tmp_path/'run';native=root/'cases'/'a'/'native'/'real-run'
    native.mkdir(parents=True)
    (root/'manifest.json').write_text(json.dumps({'state':'running','case_ids':['a'],'cases_planned':1}))
    result={'id':'a','passed':False,'attempts':[{'history':[{'result':{'tests':[{'result':124,'error_msg':'native harness timeout after 300s'}]}}]}]}
    (native/'summary.json').write_text(json.dumps({'results':[result]}))
    (root/'cases'/'a'/'calls').mkdir()
    recovery=importlib.import_module('recover_experiment')
    final=recovery.recover_batch(root)
    assert final['results'][0]['status']=='timeout'
    assert final['results'][0]['elapsed_seconds'] is None
    assert final['manifest']['elapsed_seconds'] is None
    assert final['manifest']['timing_complete'] is False
    assert (root/'manifest.before-recovery.json').exists()


def test_recovery_refuses_to_invent_an_unexecuted_case(tmp_path):
    (tmp_path/'manifest.json').write_text(json.dumps({'state':'running','case_ids':['missing'],'cases_planned':1}))
    recovery=importlib.import_module('recover_experiment')
    with pytest.raises(ValueError,match='native summary'):
        recovery.recover_batch(tmp_path)
    assert not (tmp_path/'summary.json').exists()


def test_recovered_missing_runtime_suppresses_speed_claim():
    from test_experiment_reports import batch
    report=importlib.import_module('experiment_reports')
    data=batch('baseline',150,30)
    data['manifest']['elapsed_seconds']=None
    data['results'][0]['elapsed_seconds']=None
    assert report.batch_metrics(data)['average_case_seconds'] is None
