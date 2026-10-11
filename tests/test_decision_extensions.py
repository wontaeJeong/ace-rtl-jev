import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/ace-rtl/scripts'
sys.path.insert(0, str(SCRIPTS))


def test_branch_selection_diversity_margin_budget_and_isolated_provenance(tmp_path):
    from ace_rtl_agent.decision.extensions import select_branches, materialize_branches
    from ace_rtl_agent.decision.types import CandidateBundle, Observation
    strategies = {'a': {'semantic_family': 'reset'}, 'b': {'semantic_family': 'reset'},
                  'c': {'semantic_family': 'latency'}}
    plan = select_branches({'a': .4, 'b': .35, 'c': .25}, strategies, 2, margin=.2)
    assert plan.selected == ('a', 'c')
    assert plan.discarded['b'] == 'semantic_duplicate'
    assert select_branches({'a': .9, 'c': .1}, strategies, 2).selected == ('a',)
    assert select_branches({'a': .4, 'c': .6}, strategies, 0).selected == ()
    parent = CandidateBundle.create({'rtl/a.sv': 'old'}, episode_id='episode')
    obs = Observation('o', 2, 't', 1, 'episode', 1, parent.tested_hash)
    branches = materialize_branches(plan, parent, obs, tmp_path, checkpoint_version='p1')
    assert branches[0].directory != branches[1].directory
    (branches[0].directory / 'rtl/a.sv').write_text('new')
    assert (branches[1].directory / 'rtl/a.sv').read_text() == 'old'
    manifest = json.loads((branches[0].directory / 'branch.json').read_text())
    assert manifest['parent_candidate_id'] == parent.candidate_id
    assert manifest['observation_id'] == 'o' and manifest['checkpoint_version'] == 'p1'
    with pytest.raises(FileExistsError):
        materialize_branches(plan, parent, obs, tmp_path, checkpoint_version='p1')


def test_scheduler_minimum_exploration_unknown_progress_fairness_and_inflight():
    from ace_rtl_agent.decision.extensions import AdaptiveScheduler, AttemptCheckpoint
    scheduler = AdaptiveScheduler(minimum_checkpoints=1, enabled=True)
    states = [AttemptCheckpoint('hard', progress=None, relevance=0),
              AttemptCheckpoint('easy', progress=1, relevance=1)]
    assert scheduler.allocate(states, 1) == ('easy',)
    assert scheduler.allocate(states, 1) == ('hard',)
    # Repeated boundaries cannot starve the unknown-progress attempt.
    chosen = [scheduler.allocate(states, 1)[0] for _ in range(8)]
    assert chosen.count('hard') >= 3
    inflight = replace(states[0], paid_inflight=True)
    assert scheduler.allocate([inflight], 10) == ()
    assert scheduler.cancel_attempts == ()


def test_routing_uses_configured_aliases_max_risk_and_hard_gate():
    from ace_rtl_agent.decision.extensions import route_model
    aliases = {'local': 'configured-small', 'strong': 'configured-large'}
    assert route_model(aliases, local_alias='local', strong_alias='strong',
                       risks={'reset': .95, 'interface': .01}, enabled=True).alias == 'strong'
    assert route_model(aliases, local_alias='local', strong_alias='strong',
                       hard_violations=('undeclared_target',), enabled=True).allowed is False
    assert route_model(aliases, local_alias='local', strong_alias='strong').alias == 'local'
    with pytest.raises(ValueError):
        route_model(aliases, local_alias='made-up', strong_alias='strong', enabled=True)


def test_lessons_require_evidence_freeze_and_do_not_transfer_solution_code(tmp_path):
    from ace_rtl_agent.decision.extensions import Lesson, LessonStore, curate_lessons
    candidate = Lesson('l1', 'Check reset polarity', 'fifo', 'task1', ('o1',), ('a1',),
                       ('ev1',), ('evidence1',), ('reset failure',), generator_version='g1',
                       evaluator_version='v1')
    curated = curate_lessons([candidate], {'evidence1'}, confirmed_evaluations={'ev1'})
    assert curated[0].status == 'confirmed'
    assert curate_lessons([candidate], {'evidence1'})[0].status == 'candidate'
    store = LessonStore(max_lessons=2)
    store.add(curated[0])
    store.add(replace(candidate, lesson_id='l2', contains_solution=True))
    snapshot = store.freeze(tmp_path / 'memory.json', version='memory-1')
    assert len(snapshot.retrieve('fifo', 'task2')) == 1
    assert snapshot.retrieve('other', 'task2') == ()
    with pytest.raises(RuntimeError):
        store.add(replace(candidate, lesson_id='l3'))
    with pytest.raises(ValueError):
        curate_lessons([replace(candidate, evidence_ids=('missing',))], {'evidence1'})
    assert json.loads((tmp_path / 'memory.json').read_text())['version'] == 'memory-1'


def training_row(family='fifo', passed=True):
    return {'family': family, 'task_id': family + '-task', 'action_id': family + '-a',
            'executed': True, 'decision_observation_id': 'before',
            'action_observation_id': 'before', 'next_observation_id': 'after',
            'effect_after_observation_id': 'after', 'effect_action_id': family + '-a',
            'evaluation_validity': 'valid', 'next_evaluator_status': 'PASS' if passed else 'FAIL',
            'features': {'fit': .9 if passed else .1, 'risk_max': .1, 'progress': None}}


def test_offline_learning_filters_executed_valid_links_and_rejects_future_features():
    from ace_rtl_agent.decision.offline import build_examples, grouped_split, train_policy, evaluate_policy
    rows = [training_row('fifo'), training_row('alu', False), training_row('uart'),
            dict(training_row(), executed=False), dict(training_row(), evaluation_validity='invalid')]
    examples, rejected = build_examples(rows)
    assert len(examples) == 3 and len(rejected) == 2
    train, test = grouped_split(examples, test_fraction=.34)
    assert {r.family for r in train}.isdisjoint({r.family for r in test})
    model = train_policy(train, question_version='q1', model_version='m1', policy_version='p1')
    assert model['algorithm'] == 'decision_stump' and model['production_ready'] is False
    assert 'rule' in model and evaluate_policy(model, test)['count'] == len(test)
    with pytest.raises(ValueError):
        build_examples([dict(training_row(), features={'future_pass': 1})])
    with pytest.raises(ValueError):
        build_examples([dict(training_row(), features={'fit': float('nan')})])
    assert build_examples([dict(training_row(), effect_action_id='unexecuted')])[0] == ()


def test_question_dev_only_proposals_pinned_versions_and_robustness():
    from ace_rtl_agent.decision.offline import (QuestionSnapshot, propose_questions,
                                               robustness_variants, evaluate_questions)
    snap = QuestionSnapshot.create({'kind': {'type': 'choice', 'criteria': {'rtl': 'RTL', 'unknown': 'Unknown'}}},
                                   question_version='q1', policy_version='p1', model_version='m1')
    dev = [{'split': 'dev', 'family': 'fifo', 'expected': 'rtl', 'state': {
        'options': ['rtl', 'unknown'], 'metrics': {'count': 2}, 'logs': ['failure'],
        'instruction': 'Do not add assertions'}}]
    proposals = propose_questions(dev, [{'operation': 'revise', 'question_id': 'kind',
                                        'question': {'type': 'choice', 'instructions': 'Respect exclusions'}}])
    assert proposals[0]['operation'] == 'revise'
    with pytest.raises(ValueError):
        propose_questions([dict(dev[0], split='held_out')], [])
    variants = robustness_variants(dev[0]['state'])
    assert {'option_order', 'negation', 'missing_metrics', 'duplicate_logs', 'wording'} <= variants.keys()
    report = evaluate_questions(snap, dev, lambda state, snapshot: 'rtl', repeats=2)
    assert report['accuracy'] == 1 and report['repeat_consistency'] == 1
    assert report['variant_accuracy']['negation'] == 1
    assert snap.questions['kind']['type'] == 'choice'
    with pytest.raises(TypeError):
        snap.questions['kind']['type'] = 'noul'


def test_offline_cli_fixture_train_and_evaluate(tmp_path):
    data = tmp_path / 'rows.jsonl'
    data.write_text('\n'.join(json.dumps(training_row(f, i % 2 == 0)) for i, f in enumerate(['fifo', 'alu', 'uart', 'spi'])))
    artifact = tmp_path / 'model.json'
    run = subprocess.run([sys.executable, str(SCRIPTS / 'decision_offline.py'), 'train',
                          '--data', str(data), '--output', str(artifact), '--question-version', 'q1',
                          '--model-version', 'm1', '--policy-version', 'p1'], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    result = subprocess.run([sys.executable, str(SCRIPTS / 'decision_offline.py'), 'evaluate',
                             '--data', str(data), '--artifact', str(artifact)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['count'] > 0


def test_branch_and_route_reject_invalid_inputs_and_stale_parent(tmp_path):
    from ace_rtl_agent.decision.extensions import select_branches, materialize_branches, route_model
    from ace_rtl_agent.decision.types import CandidateBundle, Observation
    strategies = {'a': {'semantic_family': 'reset', 'eligible': False}}
    assert select_branches({'a': 1}, strategies, 2).discarded['a'] == 'ineligible'
    for distribution in ({'a': float('nan')}, {'a': .2}, {'unknown': 1}):
        with pytest.raises(ValueError):
            select_branches(distribution, strategies, 2)
    parent = CandidateBundle.create({'a.sv': 'code'}, episode_id='e')
    with pytest.raises(ValueError):
        materialize_branches(select_branches({}, {}, 0), parent,
                             Observation('o', 1, 't', 1, 'e', 1, 'wrong'), tmp_path,
                             checkpoint_version='p1')
    with pytest.raises(ValueError):
        route_model({'l': 'model'}, local_alias='l', strong_alias='l', risks={'reset': -1})
    assert route_model({'l': 'small', 's': 'large'}, local_alias='l', strong_alias='s',
                       risks={'reset': None}, enabled=True).alias == 's'


def test_lessons_do_not_accept_unbounded_or_missing_provenance_and_snapshot_is_deep_frozen(tmp_path):
    from ace_rtl_agent.decision.extensions import Lesson, LessonStore
    store = LessonStore()
    missing = Lesson('l', 'advice', 'fifo', 't', (), (), (), (), ())
    with pytest.raises(ValueError):
        store.add(missing)
    mutable = ['o']
    lesson = Lesson('l', 'general reset advice', 'fifo', 't', mutable, ('a',), ('ev',),
                    ('evidence',), ('reset issue',), generator_version='g', evaluator_version='v')
    store.add(lesson)
    frozen = store.freeze(tmp_path / 'frozen.json', version='v1')
    mutable.append('future-evaluation')
    assert frozen.lessons[0].observation_ids == ('o',)


def test_training_rejects_duplicate_action_future_cost_and_family_overlap():
    from ace_rtl_agent.decision.offline import build_examples, grouped_split, train_policy, evaluate_policy, predict_policy
    with pytest.raises(ValueError):
        build_examples([training_row(), training_row()])
    with pytest.raises(ValueError):
        build_examples([dict(training_row(), features={'actual_cost': .5})])
    rows, _ = build_examples([training_row('fifo'), training_row('alu', False)])
    artifact = train_policy(rows, question_version='q1', model_version='m1', policy_version='p1')
    with pytest.raises(ValueError):
        evaluate_policy(artifact, rows)
    with pytest.raises(ValueError):
        predict_policy(artifact, {'fit': .1}, pinned_versions={'question_version': 'q2'})
    conflicting, _ = build_examples([training_row('fifo'), dict(training_row('alu'), task_id='fifo-task')])
    with pytest.raises(ValueError):
        grouped_split(conflicting)


def test_question_proposal_comparison_never_tunes_on_heldout():
    from ace_rtl_agent.decision.offline import QuestionSnapshot, compare_question_proposals
    snapshot = QuestionSnapshot.create({'kind': {'type': 'choice', 'instructions': 'old'}},
                                       question_version='q1', policy_version='p1', model_version='m1')
    dev = [{'split': 'dev', 'family': 'fifo', 'expected': 'rtl', 'state': {'instruction': 'Do not add assertions'}}]
    proposals = [{'operation': 'revise', 'question_id': 'kind',
                  'question': {'type': 'choice', 'instructions': 'new'}}]
    def predictor(state, pinned):
        improved = pinned.questions['kind']['instructions'] == 'new'
        return {'label': 'rtl' if improved else 'unknown', 'cost': .1,
                'abstained': not improved, 'fallback': not improved}
    report = compare_question_proposals(snapshot, dev, proposals, predictor, proposal_version='q2',
                                        held_out_families={'uart'})
    assert report['baseline']['accuracy'] == 0
    assert report['proposed']['accuracy'] == 1
    assert report['accuracy_delta'] == 1
    assert snapshot.question_version == 'q1' and snapshot.questions['kind']['instructions'] == 'old'
    with pytest.raises(ValueError):
        compare_question_proposals(snapshot, [dict(dev[0], family='uart')], proposals, predictor,
                                   proposal_version='q2', held_out_families={'uart'})


def test_saved_lesson_snapshot_verifies_hash_version_and_remains_readonly(tmp_path):
    from ace_rtl_agent.decision.extensions import Lesson, LessonStore, load_lesson_snapshot
    lesson = Lesson('l', 'Check public reset polarity', 'fifo', 't', ('o',), ('a',), ('ev',),
                    ('e',), ('reset failure',), generator_version='g1', evaluator_version='v1')
    store = LessonStore()
    store.add(lesson)
    path = tmp_path / 'memory.json'
    snapshot = store.freeze(path, version='mem1')
    assert load_lesson_snapshot(path, expected_version='mem1').digest == snapshot.digest
    with pytest.raises(ValueError):
        load_lesson_snapshot(path, expected_version='mem2')
    payload = json.loads(path.read_text())
    payload['lessons'][0]['text'] = 'Changed after benchmark started'
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        load_lesson_snapshot(path, expected_version='mem1')


def test_offline_action_links_bounded_data_and_distinct_effect_labels():
    from ace_rtl_agent.decision.offline import build_examples, training_row_from_records
    from ace_rtl_agent.decision.types import Observation, ProposedAction, EffectRecord
    before = Observation('before', 1, 'task', 1, 'episode', 1, 'hash')
    action = ProposedAction('action', 'before', 'reflect_focused')
    after = replace(before, observation_id='after', version=2, evaluator_status='CANDIDATE_FUNCTIONAL', evaluation_validity='valid')
    effect = EffectRecord('eff', 'before', 'after', 'action', comparable=True,
                          confirmed_regressions=('check',), outcome='regression')
    row = training_row_from_records('fifo', before, action, after, effect, {'fit': .7}, executed=True,
                                     actual_cost=.2, actual_seconds=1.5)
    examples, _ = build_examples([row], label_target='regression')
    assert examples[0].label is True and examples[0].actual_cost == .2
    assert build_examples([row], label_target='pass')[0][0].label is False
    with pytest.raises(ValueError):
        build_examples([row, dict(row, action_id='second')], max_rows=1)


def test_robustness_reorders_actual_choice_criteria_not_only_state_options():
    from ace_rtl_agent.decision.offline import QuestionSnapshot, evaluate_questions
    snapshot = QuestionSnapshot.create({'kind': {'type': 'choice', 'criteria': {'rtl': 'RTL', 'unknown': 'Unknown'}}},
                                       question_version='q1', policy_version='p1', model_version='m1')
    seen_orders = []
    def biased_predictor(state, pinned):
        options = list(pinned.questions['kind']['criteria'])
        seen_orders.append(tuple(options))
        return options[0]
    report = evaluate_questions(snapshot, [{'expected': 'rtl', 'state': {}}], biased_predictor)
    assert ('unknown', 'rtl') in seen_orders
    assert report['accuracy'] == 1 and report['variant_accuracy']['option_order'] == 0


def test_question_thresholds_are_pinned_and_curation_reference_lists_bounded():
    from ace_rtl_agent.decision.offline import QuestionSnapshot
    from ace_rtl_agent.decision.extensions import Lesson
    thresholds = {'fit': .7}
    snapshot = QuestionSnapshot.create({'kind': {'type': 'noul', 'instructions': 'Fit?'}},
                                       question_version='q1', policy_version='p1', model_version='m1',
                                       thresholds=thresholds)
    thresholds['fit'] = .1
    assert snapshot.thresholds['fit'] == .7
    with pytest.raises(TypeError):
        snapshot.thresholds['fit'] = .2
    with pytest.raises(ValueError):
        Lesson('l', 'bounded advice', 'fifo', 't', tuple(str(i) for i in range(100)), ('a',),
               ('eval',), ('evidence',), ('condition',))
