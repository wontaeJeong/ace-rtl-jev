import importlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))


def test_pair_requires_completed_matching_baseline(tmp_path):
    module=importlib.import_module('run_experiments')
    conditions={'attempts':1,'iterations':5,'workers':8,'llm_timeout':90,'evaluator_timeout':300,'case_timeout':1800}
    env={'dataset_sha256':'data','cvdp_commit':'cvdp','configuration':{'primary_model':'same','token_parameter':'max_completion_tokens','sampling_mode':'default','request_timeout':'60','jev_model':'unused'}}
    manifest={'state':'completed','case_ids':['a','b'],'conditions':conditions,'environment':env}
    (tmp_path/'summary.json').write_text(json.dumps({'manifest':manifest,'results':[{'id':'a'},{'id':'b'}]}))
    assert module.validate_baseline_reference(tmp_path,['a'],conditions,env)['case_ids']==['a','b']
    wrong={**conditions,'iterations':1}
    with pytest.raises(ValueError,match='conditions'):module.validate_baseline_reference(tmp_path,['a'],wrong,env)


def test_budget_denial_never_becomes_complete_benchmark():
    module=importlib.import_module('run_experiments')
    assert module.completion_state([{'status':'success'},{'status':'budget_exhausted'}])=='budget_exhausted'
    assert module.completion_state([{'status':'success'},{'status':'failure'}])=='completed'


def test_failed_warmup_persists_budget_state_and_restores_context(tmp_path,monkeypatch):
    import os
    from inference_budget import BudgetDenied
    module=importlib.import_module('run_experiments')
    manifest={'state':'running','mode':'jev'}
    def denied(request):raise BudgetDenied('fixture limit')
    monkeypatch.setattr(module,'complete',denied)
    monkeypatch.delenv('ACE_EXPERIMENT_TELEMETRY',raising=False)
    monkeypatch.delenv('ACE_EXPERIMENT_PHASE',raising=False)
    with pytest.raises(BudgetDenied):module.warm_models(tmp_path,manifest,'fixture-model')
    saved=json.loads((tmp_path/'summary.json').read_text())
    assert saved['manifest']['state']=='budget_exhausted' and saved['results']==[]
    assert 'ACE_EXPERIMENT_TELEMETRY' not in os.environ and 'ACE_EXPERIMENT_PHASE' not in os.environ
