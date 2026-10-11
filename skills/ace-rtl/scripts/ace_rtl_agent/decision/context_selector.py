"""Conservative public context packing with explicitly estimated token accounting."""
from __future__ import annotations
import json
import math
from .state_builder import assert_public, public_evidence, serialize_best, public_contract, public_candidate


def estimate_tokens(value):
    # A conservative UTF-8 byte estimate, NOT a provider tokenizer or hard token cap.
    return max(1, math.ceil(len(json.dumps(value, ensure_ascii=False).encode('utf-8')) / 3))


def select_context(contract, observation, bundle, *, evidence=(), history=(), best=None,
                   token_budget=24000, ratings=None):
    """Never silently drop contract, current failure, diff, best or counterevidence.

    A mandatory set exceeding the estimate fails closed. Full artifacts remain with
    the caller; returned omission/truncation IDs describe only this delivery view.
    ratings may contain item-specific relevance/usefulness, never override privacy.
    """
    if token_budget <= 0:
        raise ValueError('context token budget exhausted')
    items = public_evidence(evidence, observation, bundle)
    required_kinds = {'current_failure', 'contradiction', 'previous_failed_attempt', 'passing_constraint', 'best_candidate'}
    def mandatory(item):
        return item.kind in required_kinds or (item.observation_id == observation.observation_id
               and item.kind in {'diagnostic', 'emitted_log', 'error'})
    required = [e.to_dict() for e in items if mandatory(e)]
    result = {'contract': public_contract(contract), 'observation': observation.to_dict(),
               'candidate': public_candidate(bundle), 'best': serialize_best(best),
              'evidence': required, 'history': [], 'token_accounting': 'estimated',
              'estimator': 'utf8-bytes/3; not a provider tokenizer',
              'estimated_tokens': 0,
              'omitted_evidence_ids': [], 'truncated_evidence_ids': [e.evidence_id for e in items if e.truncated]}
    assert_public(result)
    if estimate_tokens(result) > token_budget:
        raise ValueError('mandatory public context exceeds estimated token budget')
    ratings = ratings or {}
    optional = sorted((e for e in items if not mandatory(e)),
                      key=lambda e: ratings.get(e.evidence_id, {}).get('usefulness', 0), reverse=True)
    for item in optional:
        rating = ratings.get(item.evidence_id, {})
        if rating.get('relevance', 1) < .5:
            result['omitted_evidence_ids'].append(item.evidence_id)
            continue
        result['evidence'].append(item.to_dict())
        if estimate_tokens(result) > token_budget:
            result['evidence'].pop()
            result['omitted_evidence_ids'].append(item.evidence_id)
    # Include same-error/episode and failed approaches, not just successful/recent history.
    ordered_history = sorted((h for h in history if hasattr(h, 'to_dict')),
                             key=lambda h: (getattr(h, 'episode_id', '') == observation.episode_id,
                                            getattr(h, 'outcome', '') in {'no_change', 'regressed'},
                                            getattr(h, 'iteration', 0)), reverse=True)
    for item in ordered_history:
        payload = item.to_dict()
        assert_public(payload)
        result['history'].append(payload)
        if estimate_tokens(result) > token_budget:
            result['history'].pop()
    result['estimated_tokens'] = estimate_tokens(result)
    result['estimated_tokens'] = estimate_tokens(result)
    if result['estimated_tokens'] > token_budget:
        raise ValueError('public context provenance exceeds estimated token budget')
    return result
