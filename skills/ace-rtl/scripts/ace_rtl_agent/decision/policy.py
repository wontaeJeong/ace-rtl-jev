"""Deterministic gates around finite JEV judgments; probabilities are never multiplied."""
from __future__ import annotations
from collections.abc import Mapping
import math
import re
from .types import ProposedAction, DecisionRecord, canonical_hash, ACTION_KINDS
from .state_builder import build_state, public_evidence
from .context_selector import select_context
from .strategies import eligible_recipes, diagnostic_candidates


def _semantic(value):
    if isinstance(value,Mapping):
        return {k:_semantic(v) for k,v in value.items() if k not in
                {'pid','execution','log','terminated_pids','wall_timestamp','started_at','duration','latency_seconds'}}
    if isinstance(value,(tuple,list)):
        return [_semantic(item) for item in value]
    if isinstance(value,str):
        value=re.sub(r'(?:/[^\s"\'<>]+)+/(?:iter_\d+|reports|rundir|sim_build)/[^\s"\'<>]*','[artifact path]',value)
        value=re.sub(r'\b\d+(?:\.\d+)?\s*(?:ns|us|ms)?\s+INFO\b','INFO',value)
    return value


class DecisionPolicy:
    """Native adapter: decide(...)->DecisionRecord, then commit(...)->ProposedAction.

    client=None is endpoint-free deterministic legacy-reflector fallback. Thresholds
    are experimental defaults, not calibrated success probabilities. A policy
    instance belongs to one attempt and must survive observation/episode changes.
    """
    def __init__(self, client=None, config=None):
        self.client, self.config = client, config or {}
        self._records, self._committed, self._counts, self._responses = {}, set(), {}, {}
        self._restarts = 0
        for key, default in (('fit_threshold', .7), ('severe_risk_threshold', .5)):
            value = self._setting(key, default)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError('policy thresholds must be finite probabilities')
        for key, default in (('max_restarts', 2), ('max_decisions_per_candidate', 4), ('max_evaluator_retries', 1)):
            value = self._setting(key, default)
            if type(value) is not int or value < (1 if key == 'max_decisions_per_candidate' else 0):
                raise ValueError('policy action limits must be nonnegative integers')

    def _setting(self, key, default):
        if isinstance(self.config, Mapping):
            return self.config.get(key, default)
        policy = getattr(self.config, 'policy', None) or {}
        return policy.get(key, getattr(self.config, key, default))

    @staticmethod
    def _budget_ok(budget):
        if budget is None:
            return True
        if isinstance(budget, Mapping):
            return not budget.get('exhausted', False) and all(
                budget.get(key) is None or budget[key] > 0
                for key in ('remaining_seconds', 'remaining_calls', 'remaining_tokens', 'remaining_cost'))
        return isinstance(budget, (int, float)) and budget > 0

    def _terminal(self, observation, budget, cancelled):
        if cancelled:
            return 'cancelled'
        if not self._budget_ok(budget):
            return 'budget_exhausted'
        if observation.evaluator_status == 'PASS' and observation.evaluation_validity == 'valid':
            return 'verified_pass'
        if any(isinstance(service, Mapping) and service.get('fatal_infra') for service in observation.services.values()):
            return 'fatal_infra'
        return None

    def _eligible(self, observation, contract, bundle, evidence, best, history):
        actions = {}
        allowed = set(contract.allowed_strategies)
        def add(kind, **details):
            if kind in allowed:
                actions[kind] = dict(action_kind=kind, target_ids=list(contract.mutable_targets),
                                     preconditions=details, eligibility=['public contract', 'budget available'])
        add('reflect_focused')
        add('reflect_deep')
        recipes = eligible_recipes(observation, contract, evidence)
        if recipes:
            add('repair_with_template', recipe=recipes[0].to_dict(), strategy_id=recipes[0].strategy_id)
        current_focus = getattr(self, '_focus', None)
        errors = list(dict.fromkeys(observation.errors or observation.failed_checks))
        if len(errors) > 1 or (errors and current_focus and current_focus not in errors):
            add('switch_focus', error_ids=errors, previous_focus=current_focus)
        diagnostics = diagnostic_candidates(contract, evidence)
        if diagnostics:
            add('gather_evidence', **diagnostics[0])
        if isinstance(best, tuple) and len(best) == 2:
            best_bundle, best_observation = best
            if (best_bundle.tested_hash != bundle.tested_hash and best_observation.evaluation_validity == 'valid'
                    and best_observation.tested_hash == best_bundle.tested_hash
                    and set(best_bundle.files) == set(contract.mutable_targets)):
                add('rollback_best', best_hash=best_bundle.tested_hash,
                    best_observation_id=best_observation.observation_id)
        elif best is not None and getattr(best, 'tested_hash', '') != bundle.tested_hash:
            # Caller must provide a verified archive manifest, not an unverified bundle.
            valid = getattr(best, 'evaluation_validity', '') == 'valid'
            if isinstance(best, Mapping):
                valid = best.get('evaluation_validity') == 'valid' and best.get('tested_hash') != bundle.tested_hash
            if valid:
                add('rollback_best', best_hash=getattr(best, 'tested_hash', '') or best.get('tested_hash'))
        if self._restarts < self._setting('max_restarts', 2):
            add('fresh_start', restart_count=self._restarts, episode_id=bundle.episode_id)
        retryable = any(isinstance(s, Mapping) and s.get('retryable_execution_failure') is True
                        for s in observation.services.values())
        if retryable and 'retry_evaluator' in contract.allowed_tools:
            retries = sum(getattr(h, 'action_kind', '') == 'retry_evaluator' for h in history)
            if retries < self._setting('max_evaluator_retries', 1):
                add('retry_evaluator', retry_count=retries)
        return actions

    @staticmethod
    def _questions(state, before):
        actions = state['actions']
        from .questions import build_action_questions
        registry = build_action_questions(actions)
        questions = {'next_action': registry['action']}
        for key in actions:
            questions['fit_' + key] = registry['fit:' + key]
            for risk in ('interface', 'reset', 'latency', 'width'):
                questions['risk_' + key + '_' + risk] = {'type': 'noul', 'instructions':
                    'Does state.actions.' + key + ' pose a severe ' + risk + ' preservation risk under state.contract and evidence?',
                    'criteria': {'true': 'Severe supported risk.', 'false': 'No severe supported risk.'}}
        errors = list(dict.fromkeys(state['observation']['errors'] or state['observation']['failed_checks']))
        if errors:
            questions['focus_error'] = {'type': 'choice', 'instructions': 'Select only an observed error ID from state.observation.errors/failed_checks.',
                                        'criteria': {**{e: 'Observed candidate error, not a proven root cause.' for e in errors},
                                                     'none_suitable': 'No supported focus.', 'insufficient_evidence': 'Insufficient evidence.'}}
        targets = state['contract']['mutable_targets']
        if targets:
            questions['focus_target'] = {'type': 'choice', 'instructions': 'Choose a declared mutable path in state.contract.mutable_targets supported by public evidence.',
                                         'criteria': {**{t: 'Declared mutable path; select only when evidence localizes here.' for t in targets},
                                                      'none_suitable': 'Keep full manifest; no localized target.'}}
        if state['contract']['task_kind'] == 'unknown':
            questions['task_kind'] = {'type': 'choice', 'instructions':
                'Classify the requested output from public state.contract.specification only; respect negations. Generated code does not determine task purpose.',
                'criteria': {k: 'Requested output is ' + k for k in ('rtl_implementation', 'rtl_optimization', 'assertion', 'coverage', 'checker', 'unknown')}}
        focus_id = state['focused_error']['id']
        observed_focus = focus_id in set(state['observation']['failed_checks']) | set(state['observation']['passed_checks']) | set(state['observation']['errors'])
        execution_mask = state['observation']['evaluator_status'] in {'LOCAL_PREFLIGHT', 'INFRA_SETUP', 'CANDIDATE_COMPILE'}
        explicitly_skipped = focus_id in state['observation']['skipped_checks']
        if before and focus_id and not (observed_focus or execution_mask or explicitly_skipped):
            questions['focus_status'] = {'type': 'choice', 'instructions':
                'Evaluate state.focused_error using state.before and state.observation executed/passed/failed/skipped checks and public evidence. Absence from a log does not prove resolution.',
                'criteria': {k: k for k in ('persists', 'observed_resolved', 'masked', 'not_executed', 'unknown')}}
        from .questions import build_context_questions
        candidates = state.get('context_candidates', {})
        if candidates:
            questions.update(build_context_questions(candidates))
            for eid, item in candidates.items():
                questions['applicable:' + eid] = {'type': 'noul', 'instructions':
                    'Independently evaluate the evidence item at state.evidence[' + str(item['evidence_index']) +
                    '] for the current observed failure and state.contract. Counterevidence and passing constraints are useful evidence too.',
                     'criteria': {'true': 'Relevant supported public evidence.', 'false': 'Unrelated or unsupported evidence.'}}
        hypotheses=state.get('hypotheses',{})
        if hypotheses:
            questions['hypothesis']={'type':'choice','instructions':'Choose a supported hypothesis from state.hypotheses. These are proposals, not established causes.',
                 'criteria':{**{k:v['description'] for k,v in hypotheses.items()},'none_suitable':'No supplied hypothesis fits the public evidence.'}}
            for key in hypotheses:
                questions['hypothesis_fit:'+key]={'type':'noul','instructions':'Is state.hypotheses['+repr(key)+'] supported by its stated public evidence IDs?',
                         'criteria':{'true':'Supplied evidence supports considering this hypothesis.','false':'Unsupported or contradicted proposal.'}}
        return questions

    @staticmethod
    def _probability(answer):
        if not isinstance(answer, Mapping):
            return None
        value = next((answer[k] for k in ('probability', 'noul', 'value', 'yes_probability') if k in answer), None)
        if value is None and isinstance(answer.get('probabilities'), Mapping):
            value = answer['probabilities'].get('true', answer['probabilities'].get('yes'))
        return float(value) if not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and 0 <= value <= 1 else None

    def decide(self, observation, contract, bundle, *, before=None, history=(), evidence=(),
               best=None, budget_remaining=None, cancelled=False):
        terminal = self._terminal(observation, budget_remaining, cancelled)
        if terminal:
            return DecisionRecord(canonical_hash([observation.observation_id, terminal]), observation.observation_id,
                                  abstention_reason=terminal, fallback_reason=terminal)
        if self._counts.get(bundle.tested_hash, 0) >= self._setting('max_decisions_per_candidate', 4):
            return DecisionRecord(canonical_hash([observation.observation_id, 'action_limit']), observation.observation_id,
                                  abstention_reason='action_limit', fallback_reason='explicit_termination')
        clean = public_evidence(evidence, observation, bundle)
        actions = self._eligible(observation, contract, bundle, clean, best, history)
        if not actions:
            return DecisionRecord(canonical_hash([observation.observation_id, 'no_eligible_action']), observation.observation_id,
                                  abstention_reason='no_eligible_action', fallback_reason='explicit_termination')
        state = build_state(observation, contract, bundle, before=before, evidence=clean, history=history,
                            best=best, actions=actions, budget_remaining=budget_remaining)
        selected_context = select_context(contract, observation, bundle, evidence=clean, history=history, best=best,
                                          token_budget=self._setting('context_token_budget', 24000))
        state['evidence'], state['history'] = selected_context['evidence'], selected_context['history']
        from .strategies import hypothesis_candidates
        state['hypotheses']=hypothesis_candidates(clean)
        # One canonical root agrees with the question registry; no contract alias.
        state['focused_error'] = {'id': getattr(self, '_focus', None) or next(
            iter(observation.errors or observation.failed_checks), None)}
        state['context_selection'] = {k: v for k, v in selected_context.items() if k in
                                     {'token_accounting', 'estimator', 'omitted_evidence_ids', 'truncated_evidence_ids', 'estimated_tokens'}}
        # Shortlist fits the 64-question provider capability even with 8 actions.
        # Content appears only once; candidates are indices into the evidence list.
        state['context_candidates'] = {item['evidence_id']: {'evidence_index': index}
                                        for index, item in enumerate(state['evidence'][:3 if state['hypotheses'] else 6])}
        questions = self._questions(state, before)
        semantic = {'bundle': bundle.tested_hash, 'contract': canonical_hash(contract.to_dict()),
            'checks': [observation.evaluator_status, observation.evaluation_validity, _semantic(observation.services),
                               sorted(observation.executed_checks), sorted(observation.passed_checks),
                               sorted(observation.failed_checks), sorted(observation.errors)],
                    'metrics': [observation.metric_comparability_key, observation.metrics],
                    # Relabeling/re-IDing already supplied content is not novel evidence.
                     'evidence': sorted({canonical_hash({'text': _semantic(e.text), 'values': _semantic(e.values)}) for e in clean}),
                    'focus': getattr(self, '_focus', None) or next(iter(observation.errors or observation.failed_checks), None)}
        digest = canonical_hash(semantic)
        request_key = canonical_hash([digest, questions, actions])
        envelope, abstention, fallback = {}, None, None
        chosen = 'reflect_focused' if 'reflect_focused' in actions else None
        if self.client is None:
            fallback = 'client_disabled'
        elif request_key in self._responses:
            previous_response = self._responses[request_key]
            if previous_response.get('resolved_model') is None:
                fallback = 'duplicate_state_unknown_resolved_model'
            else:
                envelope = previous_response
        else:
            try:
                timeout = self._setting('timeout_seconds', 20.0)
                if isinstance(budget_remaining, (int, float)):
                    timeout = min(timeout, budget_remaining)
                elif isinstance(budget_remaining, Mapping) and budget_remaining.get('remaining_seconds') is not None:
                    timeout = min(timeout, budget_remaining['remaining_seconds'])
                envelope = self.client.decide(state, questions, timeout=timeout)
                self._responses[request_key] = envelope
            except Exception as exc:
                # No exception text: provider errors can contain credentials/request bodies.
                fallback = 'systemone_' + type(exc).__name__
        answers = envelope.get('answers', {}) if isinstance(envelope, Mapping) else {}
        ratings = {}
        for eid in state['context_candidates']:
            relevance = self._probability(answers.get('applicable:' + eid))
            usefulness = answers.get('relevance:' + eid, {}).get('score')
            if relevance is not None and isinstance(usefulness, (int, float)) and math.isfinite(usefulness):
                ratings[eid] = {'relevance': relevance, 'usefulness': usefulness}
        if ratings:
            selected_context = select_context(contract, observation, bundle, evidence=clean, history=history,
                                              best=best, token_budget=self._setting('context_token_budget', 24000), ratings=ratings)
        if envelope:
            selected = answers.get('next_action', {}).get('choice')
            if selected not in actions:
                abstention = 'no_supported_choice'
            else:
                fit = self._probability(answers.get('fit_' + selected))
                risks = [self._probability(answers.get('risk_' + selected + '_' + risk))
                         for risk in ('interface', 'reset', 'latency', 'width')]
                if fit is None or fit < self._setting('fit_threshold', .7):
                    abstention = 'selected_action_own_fit'
                elif any(r is None or r >= self._setting('severe_risk_threshold', .5) for r in risks):
                    abstention = 'severe_or_unknown_single_risk'
                else:
                    chosen = selected
            if abstention:
                fallback = 'deterministic_reflect_focused'
        details = actions.get(chosen, {})
        preconditions = {**details.get('preconditions', {}), 'contract_hash': canonical_hash(contract.to_dict()),
                         'observation_hash': canonical_hash(observation.to_dict()),
                         'state_digest': digest, 'evidence_ids': [e.evidence_id for e in clean],
                         'selected_evidence_ids': [e['evidence_id'] for e in selected_context['evidence']],
                         'context_selection': {k: selected_context[k] for k in ('token_accounting', 'estimated_tokens',
                                                  'omitted_evidence_ids', 'truncated_evidence_ids')}}
        targets = tuple(contract.mutable_targets)
        selected_target = answers.get('focus_target', {}).get('choice')
        if selected_target in contract.mutable_targets and any(
                selected_target in e.text or e.values.get('target_id') == selected_target for e in clean):
            # Scope is guidance-only: generator still emits every mutable target.
            preconditions['focus_target'] = selected_target
        error = answers.get('focus_error', {}).get('choice')
        errors = observation.errors or observation.failed_checks
        if error not in errors:
            error = errors[0] if errors else None
        if chosen == 'switch_focus' and (error is None or error == getattr(self, '_focus', None)):
            chosen = 'reflect_focused' if 'reflect_focused' in actions else None
            fallback = 'unsupported_focus_switch'
        action = ProposedAction(canonical_hash([observation.observation_id, observation.version, digest, chosen]),
                                observation.observation_id, chosen, targets, error,
                                strategy_id=preconditions.get('strategy_id'), eligibility=tuple(details.get('eligibility', ())),
                                preconditions=preconditions, observation_version=observation.version,
                                 tested_hash=bundle.tested_hash) if chosen else None
        hypothesis=answers.get('hypothesis',{}).get('choice')
        fit=self._probability(answers.get('hypothesis_fit:'+str(hypothesis)))
        if action and hypothesis in state['hypotheses'] and fit is not None and fit>=self._setting('fit_threshold',.7):
            from dataclasses import replace
            action=replace(action,hypothesis_id=hypothesis,
                           preconditions={**action.preconditions,'hypothesis_verified':False,
                                          'hypothesis_evidence_ids':state['hypotheses'][hypothesis]['evidence_ids']})
        from .questions import QUESTION_VERSION
        record = DecisionRecord(canonical_hash([observation.observation_id, digest, answers, chosen]),
                                observation.observation_id, answers=answers,
                                policy_version='policy-1/' + QUESTION_VERSION,
                                requested_model=envelope.get('requested_model', '') if envelope else '',
                                resolved_model=envelope.get('resolved_model') if envelope else None,
                                chosen_action=action, abstention_reason=abstention, fallback_reason=fallback,
                                latency_seconds=envelope.get('latency_seconds') if envelope else None,
                                usage=envelope.get('usage', {}) if envelope else {})
        self._records[record.decision_id] = (record, actions, clean, best, history, canonical_hash(record.to_dict()))
        return record

    def commit(self, record, observation, contract, bundle, *, budget_remaining=None, cancelled=False):
        if self._terminal(observation, budget_remaining, cancelled):
            raise ValueError('invalid terminal/cancelled/exhausted action')
        saved = self._records.get(record.decision_id)
        if not saved or saved[0] != record or saved[5] != canonical_hash(record.to_dict()) or record.chosen_action is None:
            raise ValueError('invalid or unrecognized decision')
        action = record.chosen_action
        if (action.observation_id != observation.observation_id or action.observation_version != observation.version
                or action.tested_hash != bundle.tested_hash or observation.tested_hash != bundle.tested_hash
                or action.preconditions['observation_hash'] != canonical_hash(observation.to_dict())
                or canonical_hash(dict(bundle.files)) != bundle.tested_hash
                or action.preconditions['contract_hash'] != canonical_hash(contract.to_dict())):
            raise ValueError('stale decision: observation/version/candidate/contract changed')
        if set(action.target_ids) != set(contract.mutable_targets) or set(bundle.files) != set(contract.mutable_targets):
            raise ValueError('invalid mutable target manifest')
        eligible = self._eligible(observation, contract, bundle, saved[2], saved[3], saved[4])
        if action.action_kind not in eligible or action.action_kind not in ACTION_KINDS:
            raise ValueError('invalid action preconditions/eligibility')
        fingerprint = canonical_hash([bundle.tested_hash, action.preconditions['state_digest'], action.error_id,
                                      action.action_kind, action.strategy_id])
        if fingerprint in self._committed:
            raise ValueError('no-op repeated semantic state/action')
        count = self._counts.get(bundle.tested_hash, 0)
        if count >= self._setting('max_decisions_per_candidate', 4):
            raise ValueError('action limit per candidate reached')
        self._committed.add(fingerprint)
        self._counts[bundle.tested_hash] = count + 1
        self._focus = action.error_id
        if action.action_kind == 'fresh_start':
            self._restarts += 1
        return action
