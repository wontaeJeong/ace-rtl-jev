import importlib.util
from pathlib import Path


def load_runner():
    path=Path(__file__).resolve().parents[1]/'skills/ace-rtl/scripts/decision_compare.py'
    spec=importlib.util.spec_from_file_location('decision_compare',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_comparison_separates_invalid_reported_success_from_verified():
    runner=load_runner()
    summary={'results':[{'id':'t','passed':True,'attempts':[{'status':'passed','history':[
        {'passed':True,'result':{'errors':0,'tests':[]}}]}]}]}
    classified=runner.classify_native(summary)
    assert classified['reported_success'] is True
    assert classified['verified_success'] is False
    assert classified['status'] == 'invalid_evaluation'


def test_comparison_uses_authoritative_service_results_not_model_pass():
    runner=load_runner()
    summary={'results':[{'id':'t','passed':True,'attempts':[{'status':'passed','history':[
        {'passed':True,'result':{'errors':0,'tests':[{'service':'1','result':0,'execution':0.1}]},
         'observation':{'evaluation_validity':'valid','evaluator_status':'PASS'}}]}]}]}
    classified=runner.classify_native(summary,required_services=['1'])
    assert classified['verified_success'] is True
    assert runner.classify_native(summary,required_services=['missing'])['verified_success'] is False


def test_original_service_id_can_be_verified_from_exact_log_manifest_name():
    runner=load_runner()
    summary={'results':[{'id':'t','passed':True,'attempts':[{'history':[{'result':{'errors':0,
      'tests':[{'result':0,'execution':.1,'log':'/fixture/reports/1.txt'}]}}]}]}]}
    assert runner.classify_native(summary,required_services=['1'])['verified_success'] is True
    assert runner.classify_native(summary,required_services=['sanity'])['verified_success'] is False


def test_original_single_service_requires_explicit_legacy_manifest_binding():
    runner=load_runner()
    summary={'results':[{'id':'t','passed':True,'attempts':[{'history':[{'result':{'errors':0,
       'tests':[{'result':0,'execution':.1,'log':'/fixture/reports/1.txt'}]}}]}]}]}
    assert runner.classify_native(summary,required_services=['direct'],legacy_manifest_binding=True)['verified_success'] is True
