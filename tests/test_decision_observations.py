import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/ace-rtl/scripts'))
from ace_cvdp_native.harness import result_passed
from ace_rtl_agent.decision.types import CandidateBundle, ProposedAction


def fixtures():
    from ace_rtl_agent.decision.observations import build_task_contract
    row = {'id': 'fixture', 'categories': ['RTL implementation'],
           'input': {'prompt': 'Implement RTL. Do not add assertions.', 'context': {'rtl/a.sv': 'old', 'public.txt': 'public'}},
           'output': {'context': {'rtl/a.sv': ''}},
           'harness': {'docker-compose.yml': 'services:\n  sanity:\n    command: pytest\n  synth:\n    command: pytest\n'}}
    return build_task_contract(row), CandidateBundle.create({'rtl/a.sv': 'module a; endmodule'}, episode_id='e')


def result(codes=(0, 0), **extra):
    defaults={'testset':'public-fixture','parameterization':'default','harness_version':'fixture-1',
              'tool_version':'fixture-tool-1','config_version':'fixture-config-1'}
    defaults.update(extra)
    return dict(errors=sum(c != 0 for c in codes), tests=[{'service': s, 'result': c, 'execution_status': 'completed'} for s, c in zip(('sanity', 'synth'), codes)], **defaults)


def obs(r, iteration=1):
    from ace_rtl_agent.decision.observations import observe
    c, b = fixtures()
    return observe(r, c, b, attempt=1, iteration=iteration, version=iteration, episode_id='e')


def test_f12_empty_never_passes():
    assert not result_passed({'errors': 0, 'tests': []})


@pytest.mark.parametrize('r', [result((0,)), result(execution_status='running'), {'errors': 0, 'tests': [None]}, result(tested_hash='wrong')])
def test_invalid_authoritative_results(r):
    c, b = fixtures()
    assert not result_passed(r, required_services=c.required_services, tested_hash=b.tested_hash)
    assert obs(r).evaluation_validity == 'invalid'


def test_contract_metadata_and_public_context():
    c, _ = fixtures()
    assert c.task_kind == 'rtl_implementation'
    assert c.required_services == ('sanity', 'synth')
    assert tuple(c.immutable_context) == ('public.txt',)
    assert c.initial_targets == {'rtl/a.sv':'old'}


def test_optional_diagnostics_do_not_invalidate_pass():
    o = obs(result(diagnostics_truncated=True))
    assert o.evaluation_validity == 'valid' and o.evaluator_status == 'PASS'
    assert o.diagnostic_completeness == 'truncated'


def test_timeout_and_compile_not_tool_names():
    assert obs(result((124, 0))).evaluator_status == 'EVALUATOR_TIMEOUT'
    r = result((1, 0)); r['tests'][0]['error_msg'] = 'iverilog compilation successful; runtime mismatch'
    assert obs(r).evaluator_status != 'CANDIDATE_COMPILE'
    from ace_rtl_agent.focused_error_analysis import FocusedErrorAnalysisMixin
    assert not FocusedErrorAnalysisMixin()._is_compilation_error('', r['tests'][0]['error_msg'])


def test_f07_metadata_fixes_detector_and_legacy_ignores_code():
    from ace_rtl_agent.focused_task_detection import FocusedTaskDetectionMixin
    d = FocusedTaskDetectionMixin()
    assert not d._is_verification_task('Implement RTL', 'helper u_dut(); $error("x");')
    assert not d._is_cvdp_assertion_insertion_task('Implement RTL. Do not add assertions.', 'module a;', None)
    d.task_contract = fixtures()[0]
    assert not d._is_verification_task('Generate testbench', 'module tb;')
    assert d._is_cvdp_rtl_modification_task('', '', None)


def test_f09_service_guidance():
    from ace_rtl_agent.focused_task_detection import FocusedTaskDetectionMixin
    text = FocusedTaskDetectionMixin()._rtl_optimization_stage_guidance('sanity: PASS\nsynth: FAIL')
    assert 'Sanity failed.' not in text and 'Synthesis/optimization failed.' in text
    from ace_cvdp_native.diagnostics import summarize_result
    text = FocusedTaskDetectionMixin()._rtl_optimization_stage_guidance(summarize_result(result((0, 1))))
    assert 'Sanity failed.' not in text and 'Synthesis/optimization failed.' in text


def test_effect_regression_resolution_masking_and_comparability():
    from ace_rtl_agent.decision.observations import effect
    c, b = fixtures()
    before = obs(result((1, 0), seed=1))
    after = obs(result((0, 1), seed=1), 2)
    a = ProposedAction('a', before.observation_id, 'reflect_focused', error_id='sanity')
    e = effect(before, after, a, b)
    assert e.focus_status == 'observed_resolved'
    assert e.confirmed_regressions == ('synth',) and e.comparable
    assert effect(before, obs(result((0, 1), seed=2), 2), a, b).metric_delta == {}
    r = result((1, 0)); r['tests'][0]['stage'] = 'CANDIDATE_COMPILE'; r['tests'][1]['execution_status'] = 'not_executed'
    a = ProposedAction('a', before.observation_id, 'reflect_focused', error_id='synth')
    assert effect(before, obs(r, 2), a, b).focus_status == 'masked'


def test_recorded_service_exit_schema_legacy_and_manifest():
    recorded = {'errors': 0, 'tests': [{'result': 0, 'log': 'fixture.txt', 'error_msg': None, 'execution': 0.25, 'pid': 123}]}
    assert result_passed(recorded)
    assert not result_passed(recorded, required_services=('sanity',))
    assert obs(recorded).metrics['passed_count'] is None


@pytest.mark.parametrize('field,value', [('tests', 'corrupt'), ('tests', {}), ('errors', False)])
def test_malformed_authoritative_payload_never_raises(field, value):
    r = result(); r[field] = value
    assert not result_passed(r)
    assert obs(r).evaluation_validity == 'invalid'


def test_checks_deduplicate_and_count_only_structured_ids():
    r = result(); r['tests'][0]['checks'] = [{'id': 'a', 'result': 0}, {'id': 'b', 'result': 1}]
    assert not result_passed(r)
    r['tests'][0]['result'] = 1; r['errors'] = 1
    r['tests'][1]['checks'] = [{'id': 'c', 'result': 0}]
    o = obs(r)
    assert o.executed_checks == ('sanity/a', 'sanity/b', 'synth/c')
    assert o.metrics['failed_count'] == 1
    r['tests'][0]['checks'].append({'id': 'b', 'result': 1})
    assert obs(r).evaluation_validity == 'invalid'


def test_newly_reached_not_regression_and_changed_denominator_incomparable():
    from ace_rtl_agent.decision.observations import effect
    _, b = fixtures()
    before_result = result(); before_result['tests'][0]['checks'] = [{'id': 'a', 'result': 0}]
    after_result = result((1, 0)); after_result['tests'][0]['checks'] = [{'id': 'a', 'result': 0}, {'id': 'b', 'result': 1}]
    e = effect(obs(before_result), obs(after_result, 2), None, b)
    assert e.newly_reached_failures == ('sanity/b',)
    assert not e.confirmed_regressions and not e.comparable


def test_summary_timeout_and_empty_are_not_functional_or_pass():
    from ace_cvdp_native.diagnostics import primary_failure_from_summary
    assert primary_failure_from_summary(result((124, 0)), '{}')['stage'] == 'EVALUATOR_TIMEOUT'
    assert primary_failure_from_summary({'errors': 0, 'tests': []}, '{}')['stage'] == 'INVALID_EVALUATION'


def test_unknown_seed_or_harness_version_is_not_comparable():
    from ace_rtl_agent.decision.observations import effect
    _, bundle=fixtures()
    assert not effect(obs(result((1,0))),obs(result((0,1)),2),None,bundle).comparable
    r=result((1,0),seed=1)
    r.pop('tool_version')
    assert obs(r).metric_comparability_key is None


def test_named_symptom_resolves_only_when_its_service_explicitly_passes():
    from dataclasses import replace
    from ace_rtl_agent.decision.observations import effect
    _,bundle=fixtures()
    before=replace(obs(result((1,0))),errors=('symptom-A',),
             inferences={'error_candidates':{'symptom-A':{'services':['sanity']}}})
    action=ProposedAction('a',before.observation_id,'reflect_focused',error_id='symptom-A')
    assert effect(before,obs(result((0,1)),2),action,bundle).focus_status=='observed_resolved'
    assert effect(before,obs(result((1,0)),2),action,bundle).focus_status=='unknown'


def test_skipped_required_checks_cannot_establish_pass():
    r=result()
    r['tests'][0]['checks']=[{'id':'A','status':'skipped'}]
    assert not result_passed(r)
    assert obs(r).evaluation_validity=='invalid'


def test_missing_metric_has_explicit_unavailability_reason():
    o=obs(result((1,0)))
    assert o.metric_availability['mismatch_count']['available'] is False
    assert o.metric_availability['mismatch_count']['reason']


def test_actual_cvdp_nested_harness_files_supply_required_services():
    from ace_rtl_agent.decision.observations import build_task_contract
    row={'id':'t','categories':['cid002'],'input':{'prompt':'Implement RTL'},
         'output':{'context':{'rtl/a.sv':''}},
         'harness':{'files':{'docker-compose.yml':"services:\n  '1':\n    command: pytest\n",'src/private_checker.py':'MUST NOT READ'}}}
    contract=build_task_contract(row,'cid002')
    assert contract.required_services==('1',)
    assert 'MUST NOT READ' not in str(contract.to_dict())


def test_timeout_is_incomplete_not_a_measured_candidate_failure():
    from ace_rtl_agent.decision.observations import effect
    _,bundle=fixtures()
    after=obs(result((124,0)))
    assert after.evaluation_validity=='incomplete'
    assert effect(None,after,None,bundle).outcome=='unknown'
