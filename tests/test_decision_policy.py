"""Public-only, endpoint-free policy fixtures."""
import sys
from pathlib import Path
from dataclasses import replace
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/ace-rtl/scripts'))
from ace_rtl_agent.decision.types import CandidateBundle, TaskContract, Observation, Evidence
from ace_rtl_agent.decision.policy import DecisionPolicy
from ace_rtl_agent.decision.state_builder import build_state, build_effect
from ace_rtl_agent.decision.context_selector import select_context


def fixture():
    bundle = CandidateBundle.create({'src/top.sv': 'module top; endmodule'}, episode_id='e1')
    contract = TaskContract('t', task_kind='rtl_implementation', mutable_targets=('src/top.sv',), specification='public spec')
    obs = Observation('o1', 1, 't', 0, 'e1', 1, bundle.tested_hash,
                      evaluator_status='CANDIDATE_FUNCTIONAL', evaluation_validity='valid',
                      executed_checks=('A',), failed_checks=('A',), errors=('A',))
    return obs, contract, bundle


class Client:
    def __init__(self, selected='reflect_deep', fit=.9, risk=0):
        self.selected, self.fit, self.risk = selected, fit, risk
        self.calls = []

    def decide(self, state, questions, *, timeout):
        self.calls.append((state, questions, timeout))
        answers = {}
        for key, question in questions.items():
            if question['type'] == 'noul':
                answers[key] = {'probability': self.risk if 'risk' in key else (.99 if 'reflect_focused' in key else self.fit)}
        answers['next_action'] = {'choice': self.selected, 'probabilities': {}, 'confidence': .9}
        return dict(answers=answers, requested_model='fixture', resolved_model='fixture-v1', usage={}, latency_seconds=.01)


def test_fallback_and_stale_commit():
    obs, contract, bundle = fixture()
    policy = DecisionPolicy()
    record = policy.decide(obs, contract, bundle)
    assert record.chosen_action.action_kind == 'reflect_focused'
    with pytest.raises(ValueError, match='stale'):
        policy.commit(record, replace(obs, version=2), contract, bundle)
    assert policy.commit(record, obs, contract, bundle).action_kind == 'reflect_focused'
    with pytest.raises(ValueError, match='no.op'):
        policy.commit(record, obs, contract, bundle)


@pytest.mark.parametrize('fit,risk', [(.1, 0), (.9, .9)])
def test_own_fit_and_single_severe_risk_force_fallback(fit, risk):
    obs, contract, bundle = fixture()
    client = Client(fit=fit, risk=risk)
    record = DecisionPolicy(client).decide(obs, contract, bundle)
    assert record.chosen_action.action_kind == 'reflect_focused'
    assert record.abstention_reason
    assert record.resolved_model == 'fixture-v1'


def test_dynamic_eligibility_and_abstention_escape():
    obs, contract, bundle = fixture()
    client = Client(selected='none_suitable')
    record = DecisionPolicy(client).decide(obs, contract, bundle)
    state, questions, timeout = client.calls[0]
    assert 'retry_evaluator' not in state['actions']
    assert 'rollback_best' not in state['actions']
    assert 'none_suitable' in questions['next_action']['criteria']
    assert record.fallback_reason


def test_terminal_and_budget_gates_do_not_call():
    obs, contract, bundle = fixture()
    client = Client()
    policy = DecisionPolicy(client)
    for kwargs in ({'cancelled': True}, {'budget_remaining': 0}):
        record = policy.decide(obs, contract, bundle, **kwargs)
        assert record.chosen_action is None
    assert not client.calls


def test_public_state_filters_private_unknown_and_foreign_evidence():
    obs, contract, bundle = fixture()
    evidence = (Evidence('pub', 'emitted evaluator log', 'diagnostic', text='failure A'),
                Evidence('hidden', 'private checker', 'checker', text='secret', public=False),
                Evidence('unknown', 'unknown', 'arbitrary', text='secret'),
                Evidence('other', 'emitted log', 'diagnostic', text='old', candidate_id='other'))
    state = build_state(obs, contract, bundle, evidence=evidence)
    assert [e['evidence_id'] for e in state['evidence']] == ['pub']
    with pytest.raises(ValueError, match='private|secret|forbidden'):
        build_state(obs, replace(contract, specification='Authorization: Bearer secret'), bundle)


def test_context_preserves_contradiction_and_required_context():
    obs, contract, bundle = fixture()
    evidence = (Evidence('failure', 'public log', 'current_failure', text='A failed'),
                Evidence('contra', 'public log', 'contradiction', text='recipe failed'),
                Evidence('pass', 'public log', 'passing_constraint', text='B passed'))
    result = select_context(contract, obs, bundle, evidence=evidence, token_budget=2048)
    assert {e['evidence_id'] for e in result['evidence']} == {'failure', 'contra', 'pass'}
    assert result['token_accounting'] == 'estimated'
    assert result['contract']['specification'] == 'public spec'


def test_deterministic_effect_masks_semantic_solved_and_separates_new_failure():
    obs, contract, bundle = fixture()
    masked = replace(obs, observation_id='o2', evaluator_status='CANDIDATE_COMPILE', executed_checks=(), failed_checks=(), errors=())
    assert build_effect(obs, masked, bundle, focus_error='A', semantic_focus_status='observed_resolved').focus_status == 'masked'
    after = replace(obs, observation_id='o3', executed_checks=('A', 'B'), passed_checks=('A',), failed_checks=('B',))
    effect = build_effect(obs, after, bundle, focus_error='A')
    assert effect.focus_status == 'observed_resolved'
    assert effect.newly_reached_failures == ('B',)
    assert not effect.confirmed_regressions


def test_noop_fingerprint_does_not_depend_on_observation_version():
    obs, contract, bundle = fixture()
    policy = DecisionPolicy()
    record = policy.decide(obs, contract, bundle)
    policy.commit(record, obs, contract, bundle)
    newer = replace(obs, observation_id='o2', version=2)
    repeated = policy.decide(newer, contract, bundle)
    with pytest.raises(ValueError, match='no.op|limit'):
        policy.commit(repeated, newer, contract, bundle)


def test_actual_client_schema_noul_and_selected_action():
    class TypedClient(Client):
        def decide(self, state, questions, *, timeout):
            from ace_rtl_agent.decision.systemone_client import validate_questions, CAPABILITIES
            validate_questions(questions, CAPABILITIES['ollama'])
            result = super().decide(state, questions, timeout=timeout)
            for key, value in result['answers'].items():
                if 'probability' in value:
                    value['noul'] = value.pop('probability')
            return result
    obs, contract, bundle = fixture()
    policy = DecisionPolicy(TypedClient())
    record = policy.decide(obs, contract, bundle)
    assert record.chosen_action.action_kind == 'reflect_deep'
    policy.commit(record, obs, contract, bundle)


def test_relabeling_evidence_is_not_novel():
    obs, contract, bundle = fixture()
    policy = DecisionPolicy()
    old = Evidence('one', 'public log', 'emitted_log', text='A failed')
    record = policy.decide(obs, contract, bundle, evidence=(old,))
    policy.commit(record, obs, contract, bundle)
    newer = replace(obs, observation_id='o2', version=2)
    copy = replace(old, evidence_id='renamed', kind='diagnostic')
    repeated = policy.decide(newer, contract, bundle, evidence=(old, copy))
    with pytest.raises(ValueError, match='no.op'):
        policy.commit(repeated, newer, contract, bundle)


def test_typed_history_records_baseline_then_switches_same_category_focus():
    import logging
    from ace_rtl_agent.focused_history import FocusedHistoryMixin
    class History(FocusedHistoryMixin):
        def __init__(self):
            self.fix_history = []
            self.logger = logging.getLogger('test')
    obs, contract, bundle = fixture()
    h = History()
    baseline = h.record_observation(obs, bundle, focus_error_id='A')
    assert baseline.before_observation_id is None
    after = replace(obs, observation_id='o2', executed_checks=('A', 'B'), passed_checks=('A',), failed_checks=('B',), errors=('B',))
    h.record_attempt(2, 'A', 'real reasoning', 'guidance', 'diff', 'not fixed!', '', 'regressed',
                     observation=after, before=obs, bundle=bundle)
    assert h.error_solved
    assert h.fix_history[-1].focus_status == 'observed_resolved'
    assert h.fix_history[-1].newly_reached_failures == ('B',)
    assert h.fix_history[-1].error_reasoning == 'real reasoning'


@pytest.mark.parametrize('prose,solved,new_errors', [
    ('not fixed', False, False), ('not resolved', False, False),
    ('Solved; no new errors introduced', True, False),
])
def test_legacy_negation_compatibility(prose, solved, new_errors):
    import logging
    from ace_rtl_agent.focused_history import FocusedHistoryMixin
    class History(FocusedHistoryMixin):
        def __init__(self):
            self.fix_history, self.logger = [], logging.getLogger('test')
    history = History()
    history.record_attempt(1, 'A', '', '', '', prose, '', 'no_change')
    assert history.error_solved == solved
    assert history._check_if_new_errors_introduced(prose) == new_errors


def test_duplicate_failure_mentions_are_not_test_counts():
    from ace_rtl_agent.focused_guidance import FocusedGuidanceMixin
    obj = FocusedGuidanceMixin()
    assert obj.parse_test_results('A failed\nA failed\nA failed') == (0, 0)
    obs, _, _ = fixture()
    assert obj.parse_test_results('ignored', observation=obs) == (0, 1)


def test_recipe_preconditions_and_readonly_diagnostic():
    from ace_rtl_agent.decision.strategies import summarize_diagnostic
    obs, contract, bundle = fixture()
    compile_obs = replace(obs, evaluator_status='CANDIDATE_COMPILE')
    diag = Evidence('d', 'public compiler log', 'diagnostic', text='src/top.sv: syntax error')
    client = Client(selected='repair_with_template')
    record = DecisionPolicy(client).decide(compile_obs, contract, bundle, evidence=(diag,))
    assert record.chosen_action.strategy_id == 'syntax_local'
    assert 'generate every target file' in record.chosen_action.preconditions['recipe']['guidance']
    trace = replace(diag, evidence_id='trace', kind='trace', text='public header\n' * 1000 + 'public new tail')
    contract = replace(contract, allowed_tools=('inspect_public_artifact',))
    record = DecisionPolicy(Client(selected='gather_evidence')).decide(obs, contract, bundle, evidence=(trace,))
    artifact = summarize_diagnostic(record.chosen_action, (trace,))
    assert artifact.kind == 'diagnostic'
    assert artifact.text.endswith('public new tail')
    with pytest.raises(ValueError, match='permitted'):
        summarize_diagnostic(record.chosen_action, (replace(trace, public=False),))


def test_structured_reflection_has_no_nested_spec_or_code():
    from ace_rtl_agent.focused_prompting import FocusedPromptingMixin
    obs, contract, bundle = fixture()
    result = FocusedPromptingMixin().create_reflection(obs, contract, bundle, analysis='reason', guidance='repair')
    assert result['focus']['error_id'] == 'A'
    assert result['analysis'] == 'reason'
    assert 'public spec' not in str(result)
    assert 'module top' not in str(result)


def test_restart_clears_episode_history_not_lessons_or_rules():
    import logging
    from ace_rtl_agent.fresh_start_coordinator import FreshStartCoordinator
    obj = FreshStartCoordinator.__new__(FreshStartCoordinator)
    obj.fresh_start_count, obj.last_fresh_start_iteration, obj.episode_id = 0, 0, 0
    obj.iteration_history, obj.archived_episodes, obj.lessons = ['old evidence'], [], ['validated lesson']
    obj.logger = logging.getLogger('test')
    obj.mark_fresh_start(3)
    assert not obj.iteration_history and obj.archived_episodes == [('old evidence',)]
    assert obj.lessons == ['validated lesson'] and obj.episode_id == 1


def test_rule_parse_failure_is_retryable_and_valid_no_match_cached(tmp_path, monkeypatch):
    import json
    from ace_rtl_agent.rtl_rule_advisor import RTLRuleAdvisor
    path = tmp_path / 'public_rules.json'
    path.write_text(json.dumps({'rules': [{'id': 'r1', 'title': 'public rule', 'summary': 'summary'}]}))
    monkeypatch.setattr('ace_rtl_agent.rtl_rule_advisor.LLMClient', lambda **kwargs: object())
    advisor = RTLRuleAdvisor(str(path))
    class Stub:
        def __init__(self): self.calls = 0
        def call_llm(self, prompt, **kwargs):
            assert kwargs.get('role')=='rule_selector'
            self.calls += 1
            return 'not json' if self.calls == 1 else '{"selected_rules": []}'
    advisor.llm_client = Stub()
    assert advisor.retrieve_rules_from_specification('public specification') is False
    assert not advisor.specification_processed and advisor.selection_status == 'parse_error'
    assert advisor.retrieve_rules_from_specification('public specification') is False
    assert advisor.specification_processed and advisor.selection_status == 'no_match'
    assert advisor.retrieve_rules_from_specification('public specification') is False
    assert advisor.llm_client.calls == 2


def test_best_tuple_rollback_requires_matching_valid_archive():
    obs, contract, bundle = fixture()
    archived = CandidateBundle.create({'src/top.sv': 'module top; wire old; endmodule'}, episode_id='old')
    prior = replace(obs, observation_id='best', tested_hash=archived.tested_hash, passed_checks=('B',))
    client = Client(selected='rollback_best')
    record = DecisionPolicy(client).decide(obs, contract, bundle, best=(archived, prior))
    assert record.chosen_action.action_kind == 'rollback_best'
    assert record.chosen_action.preconditions['best_hash'] == archived.tested_hash
    with pytest.raises(ValueError, match='provenance'):
        DecisionPolicy().decide(obs, contract, bundle, best=(archived, replace(prior, evaluation_validity='invalid')))


def test_task_question_only_for_ambiguous_canonical_metadata():
    obs, contract, bundle = fixture()
    client = Client()
    DecisionPolicy(client).decide(obs, contract, bundle)
    assert 'task_kind' not in client.calls[-1][1]
    DecisionPolicy(client).decide(obs, replace(contract, task_kind='unknown', category='unrecognized'), bundle)
    assert 'task_kind' in client.calls[-1][1]


def test_limits_before_optional_inference_and_restart_count():
    obs, contract, bundle = fixture()
    client = Client(selected='fresh_start')
    policy = DecisionPolicy(client, {'max_decisions_per_candidate': 1, 'max_restarts': 1})
    record = policy.decide(obs, contract, bundle)
    policy.commit(record, obs, contract, bundle)
    terminal = policy.decide(replace(obs, observation_id='o2', version=2), contract, bundle)
    assert terminal.chosen_action is None and terminal.abstention_reason == 'action_limit'
    assert len(client.calls) == 1


def test_context_mandatory_overflow_fails_closed_not_silently_truncated():
    obs, contract, bundle = fixture()
    with pytest.raises(ValueError, match='mandatory'):
        select_context(contract, obs, bundle, token_budget=1)


def test_stale_or_mutated_receipt_rejected():
    obs, contract, bundle = fixture()
    policy = DecisionPolicy()
    record = policy.decide(obs, contract, bundle)
    with pytest.raises(ValueError, match='stale'):
        policy.commit(record, replace(obs, errors=('B',)), contract, bundle)
    record = replace(record, chosen_action=replace(record.chosen_action,
        preconditions={**record.chosen_action.preconditions, 'state_digest': 'forged'}))
    with pytest.raises(ValueError, match='invalid'):
        policy.commit(record, obs, contract, bundle)


def test_context_judgment_is_item_specific_and_cannot_drop_contradiction():
    class ContextClient(Client):
        def decide(self, state, questions, *, timeout):
            result = super().decide(state, questions, timeout=timeout)
            for key, question in questions.items():
                if key.startswith('applicable:'):
                    result['answers'][key] = {'noul': .01}
                elif question['type'] == 'score':
                    result['answers'][key] = {'score': 0}
            return result
    obs, contract, bundle = fixture()
    evidence = (Evidence('optional', 'public log', 'diagnostic', text='background'),
                Evidence('contra', 'public log', 'contradiction', text='previous strategy failed'))
    client = ContextClient()
    record = DecisionPolicy(client).decide(obs, contract, bundle, evidence=evidence)
    assert 'relevance:optional' in client.calls[0][1]
    assert tuple(record.chosen_action.preconditions['selected_evidence_ids']) == ('contra',)


def test_every_question_references_existing_state_roots_without_contract_alias():
    import json
    import re
    obs, contract, bundle = fixture()
    before = replace(obs, observation_id='before')
    evidence = (Evidence('d', 'public log', 'diagnostic', text='src/top.sv width mismatch'),)
    client = Client()
    DecisionPolicy(client).decide(obs, replace(contract, task_kind='unknown'), bundle,
                                before=before, evidence=evidence)
    state, questions, _ = client.calls[0]
    roots = set(re.findall(r'\bstate\.([A-Za-z_][A-Za-z_0-9]*)', json.dumps(questions)))
    assert roots <= set(state), roots - set(state)
    assert 'contract' in state and 'task_contract' not in state
def test_unknown_resolved_model_is_not_reused_as_raw_decision_cache():
    obs,contract,bundle=fixture()
    class Unresolved(Client):
        def decide(self,*args,**kwargs):
            result=super().decide(*args,**kwargs)
            result['resolved_model']=None
            return result
    client=Unresolved()
    policy=DecisionPolicy(client)
    policy.decide(obs,contract,bundle)
    second=policy.decide(replace(obs,observation_id='o2',version=2),contract,bundle)
    assert len(client.calls)==1
    assert not second.answers
    assert second.fallback_reason=='duplicate_state_unknown_resolved_model'


def test_hypotheses_are_evidence_grounded_proposals_with_own_fit():
    obs,contract,bundle=fixture()
    evidence=(Evidence('reset-log','emitted evaluator','diagnostic',text='public reset output mismatch'),)
    class HypothesisClient(Client):
        def decide(self,state,questions,**kwargs):
            result=super().decide(state,questions,**kwargs)
            assert set(state['hypotheses'])=={'reset_preservation'}
            result['answers']['hypothesis']={'choice':'reset_preservation','confidence':.9}
            result['answers']['hypothesis_fit:reset_preservation']={'noul':.95}
            return result
    decision=DecisionPolicy(HypothesisClient()).decide(obs,contract,bundle,evidence=evidence)
    assert decision.chosen_action.hypothesis_id=='reset_preservation'
    assert decision.chosen_action.preconditions['hypothesis_verified'] is False


def test_runtime_pid_duration_and_log_path_are_not_novel_evidence():
    obs,contract,bundle=fixture()
    obs=replace(obs,services={'sanity':{'result':1,'pid':1,'execution':.1,'log':'/run/iter_01/report.txt'}})
    policy=DecisionPolicy(Client())
    first=policy.decide(obs,contract,bundle)
    policy.commit(first,obs,contract,bundle)
    second_obs=replace(obs,observation_id='o2',version=2,
                       services={'sanity':{'result':1,'pid':2,'execution':.9,'log':'/run/iter_02/report.txt'}})
    second=policy.decide(second_obs,contract,bundle)
    with pytest.raises(ValueError,match='no.op'):
        policy.commit(second,second_obs,contract,bundle)


def test_decision_delivery_does_not_repeat_raw_normalized_tested_source():
    obs,contract,bundle=fixture()
    state=build_state(obs,contract,bundle)
    assert 'raw_files' not in state['candidate']
    assert 'normalized_files' not in state['candidate']
    assert state['candidate']['files']==bundle.files


def test_beam_alternative_is_committed_against_frozen_parent_and_own_fit():
    obs,contract,bundle=fixture()
    policy=DecisionPolicy(Client())
    first=policy.decide(obs,contract,bundle)
    policy.commit(first,obs,contract,bundle)
    alternative=policy.alternative(first,'fresh_start',obs,contract,bundle)
    assert alternative.chosen_action.action_kind=='fresh_start'
    assert alternative.chosen_action.preconditions['search_heuristic'] is True
    policy.commit(alternative,obs,contract,bundle)
    assert alternative.chosen_action.observation_id==obs.observation_id
    poor=DecisionPolicy(Client(fit=.1))
    rejected=poor.decide(obs,contract,bundle)
    with pytest.raises(ValueError,match='fit'):
        poor.alternative(rejected,'fresh_start',obs,contract,bundle)
