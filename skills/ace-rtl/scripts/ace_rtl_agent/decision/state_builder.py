"""Build bounded decision input from explicitly public artifacts, never filesystem reads."""
from __future__ import annotations

import json
import re
from dataclasses import replace
from collections.abc import Mapping
from .types import Evidence, EffectRecord, canonical_hash, validate_target

PUBLIC_EVIDENCE_KINDS = frozenset({
    'specification', 'interface', 'diagnostic', 'emitted_log', 'trace', 'diff',
    'observation', 'history', 'rule', 'lesson', 'error', 'hypothesis',
    'current_failure', 'contradiction', 'previous_failed_attempt', 'passing_constraint', 'best_candidate',
})
_FORBIDDEN = re.compile(
    r'authorization\s*:|bearer\s+\S+|(?:api[_ -]?key|access[_ -]?token|password|secret)\s*[=:]|'
    r'private[_ /-](?:checker|reference)|hidden[_ /-](?:checker|reference)|'
    r'checker/reference|harness_library|(?:^|[/\s])\.env(?:\b|/)', re.I)
_FORBIDDEN_KEYS = {'authorization', 'api_key', 'apikey', 'password', 'secret',
                   'access_token', 'private_checker', 'reference_source', 'checker_source',
                   'mutation_definition', 'environ', 'environment_variables'}
_FORBIDDEN_SOURCE = re.compile(r'(?:checker|reference|golden|mutation)[^\n]*\.(?:py|json|yaml|yml)\b|private|hidden', re.I)


def assert_public(value):
    """Reject credential/source markers recursively; this is not a secrecy classifier."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise ValueError('forbidden private/secret state field')
            assert_public(str(key))
            assert_public(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            assert_public(item)
    elif isinstance(value, str) and _FORBIDDEN.search(value):
        raise ValueError('forbidden private/secret state content')


def public_evidence(evidence, observation=None, bundle=None, *, max_chars=8000):
    """Allowlist kinds/provenance; discard unavailable, foreign, private and duplicate items."""
    result, seen = [], set()
    for item in evidence:
        if not isinstance(item, Evidence) or item.public is not True or item.kind not in PUBLIC_EVIDENCE_KINDS:
            continue
        if _FORBIDDEN_SOURCE.search(item.source):
            continue
        if item.availability != 'available':
            continue
        if bundle and item.candidate_id and item.candidate_id != bundle.candidate_id:
            continue
        if observation and item.observation_id and item.observation_id != observation.observation_id:
            # Archived history/contradictions are explicitly useful, unlike stale diagnostics.
            if item.kind not in {'history', 'contradiction', 'previous_failed_attempt', 'passing_constraint', 'best_candidate', 'lesson'}:
                continue
        try:
            assert_public(item.to_dict())
            digest = canonical_hash({'kind': item.kind, 'text': item.text, 'values': item.values})
        except (ValueError, TypeError):
            continue
        if digest in seen or item.evidence_id in {e.evidence_id for e in result}:
            continue
        seen.add(digest)
        # Structured values cannot bypass the bounded-text contract.
        values = dict(item.values)
        if item.kind in {'emitted_log', 'trace'} and len(item.text) > max_chars and not item.truncated:
            # Availability descriptor only; excluded tail content is not yet model input.
            values['unexposed_tail_available'] = True
        if len(json.dumps(values, ensure_ascii=False)) > max_chars:
            values = {'omitted': 'structured values exceed public context bound'}
        result.append(replace(item, text=item.text[:max_chars], values=values,
                              truncated=item.truncated or len(item.text) > max_chars or
                              values.get('omitted') == 'structured values exceed public context bound'))
    return tuple(result)


def build_state(observation, contract, bundle, *, before=None, history=(), evidence=(),
                best=None, actions=None, budget_remaining=None, max_evidence_chars=8000):
    """Public-only state; callers must supply row-declared public contract and diagnostics."""
    if observation.task_id != contract.task_id or observation.tested_hash != bundle.tested_hash:
        raise ValueError('observation/task/candidate mismatch')
    for path in contract.mutable_targets:
        validate_target(path)
    if set(bundle.files) != set(contract.mutable_targets):
        raise ValueError('candidate must contain exactly the mutable target manifest')
    if canonical_hash(dict(bundle.files)) != bundle.tested_hash:
        raise ValueError('candidate content must match evaluated hash')
    state = {
        'observation': observation.to_dict(), 'contract': public_contract(contract),
        'candidate': public_candidate(bundle),
        'before': before.to_dict() if before else None,
        'history': [h.to_dict() for h in history[-8:] if hasattr(h, 'to_dict')],
        'best': serialize_best(best),
        'budget_remaining': budget_remaining,
        'evidence': [e.to_dict() for e in public_evidence(evidence, observation, bundle, max_chars=max_evidence_chars)],
        'actions': actions or {},
    }
    assert_public(state)
    return state


def public_contract(contract):
    payload = contract.to_dict()
    # An input-context copy of a generated target is not an immutable helper.
    payload['immutable_context'] = {path: text for path, text in contract.immutable_context.items()
                                    if path not in contract.mutable_targets}
    assert_public(payload)
    return payload


def public_candidate(bundle):
    payload=bundle.to_dict()
    payload.pop('raw_files',None)
    payload.pop('normalized_files',None)
    return payload


def serialize_best(best):
    """Verified native archive is a (CandidateBundle, Observation) pair."""
    if isinstance(best, tuple) and len(best) == 2:
        candidate, observation = best
        if candidate.tested_hash != observation.tested_hash or observation.evaluation_validity != 'valid':
            raise ValueError('best archive must have matching valid evaluator provenance')
        return {'candidate': public_candidate(candidate), 'observation': observation.to_dict()}
    return best.to_dict() if hasattr(best, 'to_dict') else dict(best) if isinstance(best, Mapping) else None


def build_effect(before, after, bundle, *, action=None, focus_error=None,
                 semantic_focus_status=None):
    """Execution facts always override a semantic focus answer; JEV never establishes PASS."""
    status = 'unknown'
    if focus_error:
        if focus_error in after.failed_checks:
            status = 'persists'
        elif focus_error in after.passed_checks and focus_error in after.executed_checks and after.evaluation_validity == 'valid':
            status = 'observed_resolved'
        elif focus_error in after.errors:
            status = 'persists'
        elif after.evaluator_status in {'LOCAL_PREFLIGHT', 'INFRA_SETUP', 'CANDIDATE_COMPILE'}:
            status = 'masked'
        elif focus_error in after.skipped_checks or (before and focus_error in before.executed_checks and focus_error not in after.executed_checks):
            status = 'not_executed'
        elif semantic_focus_status in {'persists', 'unknown'}:
            status = semantic_focus_status
    comparable = bool(before and before.evaluation_validity == after.evaluation_validity == 'valid'
                      and before.metric_comparability_key
                      and before.metric_comparability_key == after.metric_comparability_key
                      and set(before.executed_checks) == set(after.executed_checks))
    regressions = tuple(sorted(set(after.failed_checks) & set(before.passed_checks) & set(before.executed_checks) & set(after.executed_checks))) if before and before.evaluation_validity == after.evaluation_validity == 'valid' and before.metric_comparability_key and before.metric_comparability_key == after.metric_comparability_key else ()
    newly = tuple(sorted(set(after.failed_checks) - set(before.executed_checks))) if before else ()
    delta = {key: value - before.metrics[key] for key, value in after.metrics.items()
             if comparable and isinstance(value, (int, float)) and isinstance(before.metrics.get(key), (int, float))}
    identity = {'before': before.observation_id if before else None, 'after': after.observation_id,
                'action': action.action_id if action else None}
    return EffectRecord(canonical_hash(identity), identity['before'], identity['after'], identity['action'],
                        bundle.changed_files, status, newly, regressions, delta, comparable,
                        'passed' if after.evaluator_status == 'PASS' and after.evaluation_validity == 'valid' else
                        'failed' if after.evaluation_validity == 'valid' else 'unknown')
