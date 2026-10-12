"""Whole-branch review reproductions, no paid calls or private source inputs."""
import sys
from pathlib import Path
from dataclasses import replace
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/ace-rtl/scripts'))
from ace_rtl_agent.decision.types import TaskContract,CandidateBundle,Observation,ProposedAction
from ace_rtl_agent.decision.observations import observe


def pair():
    contract=TaskContract('t',mutable_targets=('rtl/a.sv',),required_services=('sanity',),task_kind='rtl_implementation')
    bundle=CandidateBundle.create({'rtl/a.sv':'module a;\nendmodule\n'},episode_id='e')
    return contract,bundle


@pytest.mark.parametrize('status,code',[('FAIL',0),('passed',1)])
def test_service_status_and_exit_cannot_contradict(status,code):
    from ace_cvdp_native.harness import result_passed
    result={'errors':int(code!=0),'tests':[{'service':'sanity','status':status,'result':code}]}
    assert not result_passed(result,required_services=('sanity',))


def test_authoritative_pass_is_not_invalidated_by_auxiliary_timeout_word():
    c,b=pair()
    result={'errors':0,'tests':[{'service':'sanity','result':0,'status':'completed','error_msg':'timeout watchdog disabled'}]}
    o=observe(result,c,b,attempt=1,iteration=1,version=1,episode_id='e')
    assert (o.evaluator_status,o.evaluation_validity)==('PASS','valid')


def test_model_observation_allowlist_excludes_checker_source_in_raw_service_fields():
    from ace_rtl_agent.decision.state_builder import build_state
    c,b=pair()
    result={'errors':1,'tests':[{'service':'sanity','result':1,'error_msg':'def checker(dut):\n    expected = 42\n    assert dut.out == expected',
                              'private_implementation':'hidden body','execution':.1}]}
    o=observe(result,c,b,attempt=1,iteration=1,version=1,episode_id='e')
    state=build_state(o,c,b,before=o,best=(b,o))
    text=str(state)
    assert 'def checker' not in text and 'expected = 42' not in text and 'private_implementation' not in text


def test_best_compares_against_archived_best_not_immediate_predecessor():
    from ace_rtl_agent.decision.observations import choose_best_snapshot
    c,b=pair();best=None
    for version,failed in enumerate((5,1,4,3),1):
        bundle=CandidateBundle.create({'rtl/a.sv':str(version)},episode_id='e')
        o=Observation(str(version),version,'t',1,'e',version,bundle.tested_hash,
             evaluator_status='CANDIDATE_FUNCTIONAL',evaluation_validity='valid',
             metrics={'failed_count':failed},metric_comparability_key='same')
        best=choose_best_snapshot(best,bundle,o,c)
    assert best[1].metrics['failed_count']==1


def test_optimization_best_requires_functional_pass_and_objective_improvement():
    from ace_rtl_agent.decision.observations import choose_best_snapshot
    c,b=pair();c=replace(c,task_kind='rtl_optimization',functional_services=('sanity',),optimization_objectives={'area':'min'})
    valid=Observation('o',1,'t',1,'e',1,b.tested_hash,evaluation_validity='valid',passed_checks=('sanity',),
                      metrics={'area':100},metric_comparability_key='same')
    invalid=replace(valid,observation_id='bad',passed_checks=(),metrics={'area':1})
    assert choose_best_snapshot(None,b,invalid,c) is None
    best=choose_best_snapshot(None,b,valid,c)
    assert choose_best_snapshot(best,b,replace(valid,metrics={'area':150}),c)==best
    assert choose_best_snapshot(best,b,replace(valid,metrics={'area':80}),c)[1].metrics['area']==80


def test_improvement_training_label_uses_comparable_measured_delta():
    from ace_rtl_agent.decision.offline import training_row_from_records,build_examples
    from ace_rtl_agent.decision.types import EffectRecord
    c,b=pair()
    before=Observation('before',1,'t',1,'e',1,b.tested_hash,evaluation_validity='valid')
    after=replace(before,observation_id='after',version=2,evaluator_status='PASS')
    action=ProposedAction('a','before','reflect_focused')
    effect=EffectRecord('effect','before','after','a',metric_delta={'failed_count':-1},comparable=True,outcome='passed')
    row=training_row_from_records('family',before,action,after,effect,{'fit':.8},executed=True)
    examples,rejected=build_examples([row],label_target='improvement')
    assert examples[0].label is True and not rejected


def test_semantic_effect_is_typed_but_cannot_override_masked_execution():
    from ace_rtl_agent.decision.observations import apply_semantic_effect
    from ace_rtl_agent.decision.types import EffectRecord,DecisionRecord
    effect=EffectRecord('e','before','after','a',focus_status='masked')
    decision=DecisionRecord('d','after',answers={'focus_status':{'type':'choice','choice':'observed_resolved','confidence':.99}})
    after=Observation('after',2,'t',1,'e',2,'hash',evaluator_status='CANDIDATE_COMPILE',evaluation_validity='valid')
    enriched=apply_semantic_effect(effect,decision,after)
    assert enriched.focus_status=='masked'
    assert enriched.semantic_judgment['focus_status']['choice']=='observed_resolved'


def test_reflector_route_updates_actual_wrapper_model_and_output_allowance():
    import types
    from ace_cvdp_native.extensions import apply_reflector_route
    debugger=types.SimpleNamespace(model_name='old',llm_client=types.SimpleNamespace(model='old',client=types.SimpleNamespace(model='old')))
    apply_reflector_route(debugger,{'reflector_model':'configured-strong','max_output_tokens':4096})
    assert debugger.llm_client.model=='configured-strong'
    assert debugger.llm_client.max_output_tokens==4096


def test_missing_or_malformed_diagnostic_duration_is_nullable_not_zero():
    import json
    from ace_cvdp_native.diagnostics import summarize_result
    for duration in (None,'malformed'):
        summary=json.loads(summarize_result({'errors':0,'tests':[{'service':'sanity','result':0,'execution':duration}]}))
        assert summary['service_results'][0]['execution'] is None
