"""Stdlib-only X-05/06 fixture tooling, deliberately separate from runtime.

Data requirements: JSONL rows from executed action/effect/valid next-observation
links, explicit design family and decision-time numeric features from ALLOWED_FEATURES.
Question tuning consumes dev rows only; final held-out evaluation is read-only.
Stumps describe observed-policy associations, not causal superiority or calibrated
RTL success probability. Artifacts are experimental and never enable themselves.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import math
from types import MappingProxyType
from typing import Mapping

from .types import canonical_hash

ALLOWED_FEATURES = frozenset(('fit', 'scope', 'counterevidence', 'repetition',
                             'risk_max', 'risk_interface', 'risk_reset', 'risk_latency',
                             'risk_signedness', 'score_mean', 'score_spread',
                             'progress', 'prior_cost', 'prior_changed_files'))


@dataclass(frozen=True)
class Example:
    family: str
    task_id: str
    action_id: str
    features: Mapping[str, float | None]
    label: bool
    outcome: str
    actual_cost: float | None = None
    actual_seconds: float | None = None
    label_target: str = 'pass'


def training_row_from_records(family, before, action, after, effect, features, *, executed,
                              actual_cost=None, actual_seconds=None):
    """Adapter for the shared frozen contracts; no inferred unexecuted outcomes."""
    return {'family': family, 'task_id': before.task_id, 'action_id': action.action_id,
            'executed': executed, 'decision_observation_id': before.observation_id,
            'action_observation_id': action.observation_id,
            'next_observation_id': after.observation_id,
            'effect_after_observation_id': effect.after_observation_id,
            'effect_action_id': effect.action_id, 'effect_before_observation_id': effect.before_observation_id,
            'evaluation_validity': after.evaluation_validity, 'next_evaluator_status': after.evaluator_status,
            'features': dict(features), 'feature_phase': 'decision', 'outcome': effect.outcome,
            'effect_comparable': effect.comparable, 'confirmed_regressions': list(effect.confirmed_regressions),
            'actual_cost': actual_cost, 'actual_seconds': actual_seconds}


def build_examples(rows, *, label_target='pass', max_rows=10000):
    if label_target not in ('pass', 'improvement', 'regression') or max_rows < 1:
        raise ValueError('unsupported label target or invalid data bound')
    examples, rejected, seen = [], [], set()
    for index, row in enumerate(rows):
        if index >= max_rows:
            raise ValueError('offline data exceeds row bound')
        features = row.get('features', {})
        if set(features) - ALLOWED_FEATURES or row.get('feature_phase', 'decision') != 'decision':
            raise ValueError('unknown or future feature; only decision-time allowlist accepted')
        clean = {}
        for key, value in features.items():
            if value is not None and (isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value)):
                raise ValueError('features must be finite numeric values or null')
            clean[key] = float(value) if value is not None else None
        link = (row.get('action_id') and row.get('decision_observation_id') and row.get('next_observation_id')
                and row.get('decision_observation_id') == row.get('action_observation_id')
                and row.get('effect_action_id') == row.get('action_id')
                and row.get('effect_after_observation_id') == row.get('next_observation_id')
                and row.get('decision_observation_id') != row.get('next_observation_id')
                and row.get('effect_before_observation_id', row.get('decision_observation_id')) == row.get('decision_observation_id'))
        if row.get('executed') is not True or row.get('evaluation_validity') != 'valid' or not link:
            rejected.append({'index': index, 'reason': 'unexecuted_invalid_or_unlinked'})
            continue
        if not row.get('family') or not row.get('task_id'):
            raise ValueError('task and design family are required for grouped splitting')
        identity = (row['task_id'], row['action_id'])
        if identity in seen:
            raise ValueError('duplicate executed action; do not overweight repeated ledger rows')
        seen.add(identity)
        status = row.get('next_evaluator_status')
        if status not in ('PASS', 'FAIL', 'CANDIDATE_COMPILE', 'CANDIDATE_FUNCTIONAL'):
            rejected.append({'index': index, 'reason': 'no_valid_candidate_outcome'})
            continue
        cost, seconds = row.get('actual_cost'), row.get('actual_seconds')
        for value in (cost, seconds):
            if value is not None and (not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0):
                raise ValueError('invalid measured cost/time')
        outcome = row.get('outcome', 'pass' if status == 'PASS' else 'failure')
        if label_target != 'pass' and row.get('effect_comparable') is not True:
            rejected.append({'index': index, 'reason': 'incomparable_effect_label'})
            continue
        label = (status == 'PASS' if label_target == 'pass' else
                 bool(row.get('confirmed_regressions')) if label_target == 'regression' else outcome == 'improved')
        examples.append(Example(row['family'], row['task_id'], row['action_id'],
                                MappingProxyType(clean), label, outcome, cost, seconds, label_target))
    return tuple(examples), tuple(rejected)


def grouped_split(examples, test_fraction=.25, *, seed='ace-offline-1'):
    if not 0 < test_fraction < 1:
        raise ValueError('test fraction must lie between zero and one')
    families = sorted({row.family for row in examples},
                      key=lambda family: hashlib.sha256((seed + family).encode()).hexdigest())
    if len(families) < 2:
        raise ValueError('at least two design families required')
    count = min(len(families) - 1, max(1, math.ceil(len(families) * test_fraction)))
    held_out = set(families[:count])
    # A task erroneously tagged as two families must not leak across the split.
    train = tuple(row for row in examples if row.family not in held_out)
    test = tuple(row for row in examples if row.family in held_out)
    if {r.task_id for r in train} & {r.task_id for r in test}:
        raise ValueError('task assigned to conflicting families')
    return train, test


def _majority(rows, default=False):
    return sum(row.label for row in rows) > len(rows) / 2 if rows else default


def train_policy(examples, *, question_version, model_version, policy_version):
    """Fit a one-level decision tree with explicit missing-value branch.

    No imputation from test data, no feature selection using outcome columns,
    no optional ML imports. Missing metrics remain a separate category.
    """
    examples = tuple(examples)
    if not examples or not all((question_version, model_version, policy_version)):
        raise ValueError('training rows and pinned versions required')
    if len({row.label_target for row in examples}) != 1:
        raise ValueError('cannot mix outcome label targets')
    default = _majority(examples)
    best = {'feature': None, 'threshold': None, 'low': default, 'high': default, 'missing': default}
    best_errors = sum(row.label != default for row in examples)
    for feature in sorted({key for row in examples for key in row.features}):
        if feature not in ALLOWED_FEATURES:
            raise ValueError('unapproved training feature')
        values = sorted({row.features[feature] for row in examples if row.features.get(feature) is not None})
        for threshold in values:
            low = [r for r in examples if r.features.get(feature) is not None and r.features[feature] <= threshold]
            high = [r for r in examples if r.features.get(feature) is not None and r.features[feature] > threshold]
            missing = [r for r in examples if r.features.get(feature) is None]
            rule = {'feature': feature, 'threshold': threshold,
                    'low': _majority(low, default), 'high': _majority(high, default), 'missing': _majority(missing, default)}
            errors = sum(r.label != rule[key] for key, group in [('low', low), ('high', high), ('missing', missing)] for r in group)
            if errors < best_errors:
                best, best_errors = rule, errors
    return {'artifact_version': 'ace-offline-stump-1', 'algorithm': 'decision_stump',
            'production_ready': False, 'rule': best, 'train_count': len(examples),
            'label_target': examples[0].label_target,
            'train_families': sorted({r.family for r in examples}),
            'train_task_ids': sorted({r.task_id for r in examples}),
            'question_version': question_version, 'model_version': model_version,
            'policy_version': policy_version, 'feature_allowlist': sorted(ALLOWED_FEATURES),
            'limitations': ['observational executed-policy bias', 'not calibrated', 'fixture-only until separately validated']}


def predict_policy(artifact, features, *, pinned_versions=None):
    if artifact.get('artifact_version') != 'ace-offline-stump-1':
        raise ValueError('unsupported policy artifact version')
    if pinned_versions and any(artifact.get(key) != value for key, value in pinned_versions.items()):
        raise ValueError('pinned runtime versions differ from offline artifact')
    if set(features) - ALLOWED_FEATURES:
        raise ValueError('unapproved prediction feature')
    rule = artifact['rule']
    feature = rule['feature']
    value = features.get(feature)
    if value is not None and (not isinstance(value, (float, int)) or not math.isfinite(value)):
        raise ValueError('invalid prediction feature')
    return bool(rule['missing'] if value is None else rule['low'] if value <= rule['threshold'] else rule['high'])


def evaluate_policy(artifact, examples, *, allow_training_families=False):
    examples = tuple(examples)
    if not allow_training_families and set(artifact['train_families']) & {row.family for row in examples}:
        raise ValueError('held-out evaluation overlaps training families')
    if any(row.label_target != artifact['label_target'] for row in examples):
        raise ValueError('evaluation label target differs from training')
    predictions = [predict_policy(artifact, row.features) for row in examples]
    return {'count': len(examples), 'accuracy': sum(p == r.label for p, r in zip(predictions, examples)) / len(examples) if examples else None,
            'false_positive_count': sum(p and not r.label for p, r in zip(predictions, examples)),
            'measured_cost': sum(r.actual_cost for r in examples if r.actual_cost is not None),
            'unknown_cost_count': sum(r.actual_cost is None for r in examples),
            'causal_claim': False}


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class QuestionSnapshot:
    questions: Mapping
    question_version: str
    policy_version: str
    model_version: str
    digest: str
    thresholds: Mapping

    @classmethod
    def create(cls, questions, *, question_version, policy_version, model_version, thresholds=None):
        if not questions or not all((question_version, policy_version, model_version)):
            raise ValueError('questions and all pinned versions required')
        copied = deepcopy(questions)
        thresholds = dict(thresholds or {})
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1
               for v in thresholds.values()):
            raise ValueError('invalid probability threshold')
        digest = canonical_hash([copied, question_version, policy_version, model_version, thresholds])
        return cls(_freeze(copied), question_version, policy_version, model_version, digest, _freeze(thresholds))


def propose_questions(dev_rows, proposals, *, held_out_families=()):
    """Validate externally generated add/revise/drop proposals offline only.

    An LLM can be supplied dev failures by the caller; this function performs no
    calls. It does not adopt proposals or mutate a pinned runtime registry.
    """
    if any(row.get('split') != 'dev' or row.get('family') in held_out_families for row in dev_rows):
        raise ValueError('question proposal/tuning accepts isolated dev rows only')
    result = []
    for proposal in proposals:
        if proposal.get('operation') not in ('add', 'revise', 'drop') or not proposal.get('question_id'):
            raise ValueError('invalid question proposal')
        if proposal['operation'] != 'drop' and not proposal.get('question'):
            raise ValueError('add/revise needs proposed question')
        result.append(deepcopy(proposal))
    return tuple(result)


def _thaw(value):
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def compare_question_proposals(snapshot, dev_rows, proposals, predictor, *, proposal_version,
                               held_out_families=(), repeats=2):
    """Compare one externally proposed batch on dev, without automatic adoption.

    An explicit new question version is mandatory; policy/model remain pinned.
    held_out_families comes from the experiment manifest, not these dev records.
    Returned metrics support manual selection, never runtime self-modification.
    """
    dev_rows = tuple(dev_rows)
    if not dev_rows or proposal_version == snapshot.question_version:
        raise ValueError('nonempty dev set and new proposal version required')
    proposals = propose_questions(dev_rows, proposals, held_out_families=held_out_families)
    questions = _thaw(snapshot.questions)
    for proposal in proposals:
        operation, key = proposal['operation'], proposal['question_id']
        if operation == 'add' and key in questions:
            raise ValueError('cannot add an existing question')
        if operation in ('revise', 'drop') and key not in questions:
            raise ValueError('cannot revise/drop a missing question')
        if operation == 'drop':
            del questions[key]
        else:
            questions[key] = proposal['question']
    proposed_snapshot = QuestionSnapshot.create(questions, question_version=proposal_version,
                                                policy_version=snapshot.policy_version,
                                                model_version=snapshot.model_version,
                                                thresholds=snapshot.thresholds)
    baseline = evaluate_questions(snapshot, dev_rows, predictor, repeats=repeats)
    proposed = evaluate_questions(proposed_snapshot, dev_rows, predictor, repeats=repeats)
    return {'baseline': baseline, 'proposed': proposed,
            'accuracy_delta': proposed['accuracy'] - baseline['accuracy'],
            'known_cost_delta': proposed['known_cost'] - baseline['known_cost'],
            'abstention_delta': proposed['abstention_rate'] - baseline['abstention_rate'],
            'fallback_delta': proposed['fallback_rate'] - baseline['fallback_rate'],
            'proposal_version': proposal_version, 'adopted': False, 'split': 'dev'}


def robustness_variants(state):
    """Synthetic perturbations of *public* fixture states, not task generation.

    Negation keeps the exclusion meaning (Do not -> Never); caller supplies gold
    labels. This is a robustness probe, not an automatic language entailment test.
    """
    variants = {key: deepcopy(state) for key in ('option_order', 'wording', 'negation', 'missing_metrics', 'duplicate_logs')}
    if isinstance(state.get('options'), list):
        variants['option_order']['options'] = list(reversed(state['options']))
    variants['missing_metrics']['metrics'] = {}
    if isinstance(state.get('logs'), list):
        variants['duplicate_logs']['logs'] = state['logs'] + state['logs']
    instruction = state.get('instruction', '')
    variants['wording']['instruction'] = 'Requirement: ' + instruction
    variants['negation']['instruction'] = instruction.replace('Do not ', 'Never ').replace('do not ', 'never ')
    return variants


def _question_variant(snapshot, variant):
    questions = _thaw(snapshot.questions)
    for question in questions.values():
        criteria = question.get('criteria')
        if variant == 'option_order' and question.get('type') == 'choice':
            if isinstance(criteria, dict):
                question['criteria'] = dict(reversed(tuple(criteria.items())))
            elif isinstance(criteria, list):
                question['criteria'] = list(reversed(criteria))
        if variant == 'wording' and 'instructions' in question:
            question['instructions'] = 'Requirement: ' + question['instructions']
        if variant == 'negation' and 'instructions' in question:
            question['instructions'] = question['instructions'].replace('Do not ', 'Never ').replace('do not ', 'never ')
    return QuestionSnapshot.create(questions, question_version=snapshot.question_version,
                                   policy_version=snapshot.policy_version, model_version=snapshot.model_version,
                                   thresholds=snapshot.thresholds)


def evaluate_questions(snapshot, rows, predictor, *, repeats=2):
    """Accuracy and repeat-label consistency are intentionally separate metrics.

    predictor(state, immutable_snapshot) -> label or {label, cost, abstained,
    fallback}. No automatic adoption or held-out-driven proposal generation.
    """
    if repeats < 2:
        raise ValueError('two or more repeats required for consistency')
    rows = tuple(rows)
    total, correct, consistent, cost, unknown_cost, abstained, fallback = 0, 0, 0, 0., 0, 0, 0
    variants_correct = {key: 0 for key in ('option_order', 'wording', 'negation', 'missing_metrics', 'duplicate_logs')}
    def run(state, pinned=snapshot):
        nonlocal cost, unknown_cost, abstained, fallback
        answer = predictor(deepcopy(state), pinned)
        if isinstance(answer, dict):
            measured = answer.get('cost')
            if measured is not None:
                if not isinstance(measured, (int, float)) or not math.isfinite(measured) or measured < 0:
                    raise ValueError('invalid measured question cost')
                cost += measured
            else:
                unknown_cost += 1
            abstained += bool(answer.get('abstained'))
            fallback += bool(answer.get('fallback'))
            return answer.get('label')
        unknown_cost += 1
        return answer
    for row in rows:
        labels = [run(row['state']) for _ in range(repeats)]
        total += repeats
        correct += sum(label == row['expected'] for label in labels)
        consistent += all(label == labels[0] for label in labels)
        for key, state in robustness_variants(row['state']).items():
            variants_correct[key] += run(state, _question_variant(snapshot, key)) == row['expected']
    calls = len(rows) * (repeats + len(variants_correct))
    return {'count': len(rows), 'accuracy': correct / total if total else None,
            'repeat_consistency': consistent / len(rows) if rows else None,
            'variant_accuracy': {k: v / len(rows) if rows else None for k, v in variants_correct.items()},
            'known_cost': cost, 'unknown_cost_count': unknown_cost,
            'abstention_rate': abstained / calls if calls else None,
            'fallback_rate': fallback / calls if calls else None,
            'snapshot_digest': snapshot.digest, 'runtime_modified': False}
