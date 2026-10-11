"""Typed System One HTTP boundary, independent of the generative chat backend.

Verified 2026-10-12 against https://api.typesafe.ai/openapi.json and
https://docs.ollama.com/api/systemone. Both use ``noul`` (not bool/yes)
and zero-based string keys for score legends/distributions. No retries or
domain fallback happen here. Every request requires the existing campaign.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import time
from typing import Any
from urllib.parse import urlsplit
import uuid

import requests

PROBABILITY_TOLERANCE = .001  # Accept documented four-decimal response rounding.


@dataclass(frozen=True)
class ProviderCapabilities:
    provider: str = 'systemone'
    model_required: bool = False
    usage_required: bool = False
    reports_resolved_model: bool = False
    max_choice_options: int | None = None
    max_score_levels: int | None = None
    min_score_levels: int = 1
    max_questions: int | None = None
    max_request_bytes: int | None = None
    request_context_tokens: int | None = None
    state_longest_question_tokens: int | None = None


CAPABILITIES = {
    'typesafe': ProviderCapabilities('typesafe', True, True, True, 255, 10, 1,
                                    request_context_tokens=64000,
                                    state_longest_question_tokens=32000),
    # These are HTTP-schema ceilings, not promises about an arbitrary model.
    'ollama': ProviderCapabilities('ollama', True, True, False, 255, 26, 2, 64, 65536),
    'systemone': ProviderCapabilities(),
}


class SystemOneError(RuntimeError):
    """Sanitized boundary failure; policy, not the client, decides fallback."""
    kind = 'systemone'
    retryable = False
    status_code = None


class SystemOneTransportError(SystemOneError):
    def __init__(self, kind: str):
        self.kind = kind
        self.retryable = True
        super().__init__('SystemOne request ' + kind + ' (details withheld)')


class SystemOneHTTPError(SystemOneError):
    kind = 'http'

    def __init__(self, status_code: int):
        self.status_code = status_code
        self.retryable = status_code == 429 or status_code >= 500
        super().__init__(f'SystemOne HTTP {status_code} (body withheld)')


class SystemOneSchemaError(SystemOneError):
    kind = 'schema'

    def __init__(self):
        super().__init__('SystemOne invalid response schema (body withheld)')


DecisionError = SystemOneError  # Explicit compatibility for callers catching the boundary.


def _finite_number(value: Any) -> bool:
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def probability(value: Any) -> bool:
    return _finite_number(value) and 0 <= value <= 1


def _content(value: Any) -> bool:
    return isinstance(value, (dict, list)) or isinstance(value, str) and bool(value.strip())


def validate_questions(questions: dict, capabilities: ProviderCapabilities | None = None) -> None:
    caps = capabilities or CAPABILITIES['systemone']
    if not isinstance(questions, dict) or not questions:
        raise ValueError('SystemOne needs a nonempty questions map')
    if caps.max_questions is not None and len(questions) > caps.max_questions:
        raise ValueError('SystemOne question count exceeds provider limit')
    for name, question in questions.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(question, dict):
            raise ValueError('Invalid SystemOne question')
        # Our stricter semantic contract requires self-contained instructions;
        # provider APIs allow omission but question IDs are not model-visible.
        if not _content(question.get('instructions')):
            raise ValueError('SystemOne questions need self-contained instructions')
        kind, criteria = question.get('type'), question.get('criteria')
        if kind == 'choice':
            if (not isinstance(criteria, dict) or len(criteria) < 2
                    or caps.max_choice_options is not None and len(criteria) > caps.max_choice_options
                    or any(not isinstance(k, str) or not k.strip() for k in criteria)):
                raise ValueError('Invalid SystemOne choice criteria')
            allowed = (str, dict, list) if caps.provider != 'ollama' else (str,)
            if any(v is not None and not isinstance(v, allowed) for v in criteria.values()):
                raise ValueError('Invalid SystemOne choice descriptions')
        elif kind == 'noul':
            if criteria is not None and (not isinstance(criteria, dict)
                    or not set(criteria) <= {'true', 'false'}
                    or any(v is not None and not _content(v) for v in criteria.values())):
                raise ValueError('Invalid SystemOne noul criteria')
            if caps.provider == 'ollama' and criteria is not None and any(not isinstance(v, str) for v in criteria.values()):
                raise ValueError('Ollama noul descriptions must be strings')
        elif kind == 'score':
            if (not isinstance(criteria, list) or len(criteria) < caps.min_score_levels
                    or caps.max_score_levels is not None and len(criteria) > caps.max_score_levels
                    or any(not _content(v) for v in criteria)):
                raise ValueError('Invalid SystemOne score criteria')
            if caps.provider == 'ollama' and any(not isinstance(v, str) for v in criteria):
                raise ValueError('Ollama score descriptions must be strings')
        else:
            raise ValueError('Unsupported SystemOne question type')


def _distribution(value: Any, labels: set[str]) -> dict:
    if (not isinstance(value, dict) or set(value) != labels
            or not all(probability(p) for p in value.values())
            or not math.isclose(sum(value.values()), 1, rel_tol=0, abs_tol=PROBABILITY_TOLERANCE)):
        raise ValueError('Invalid SystemOne probability distribution')
    return value


def validate_answers(payload: dict, questions: dict, *, capabilities: ProviderCapabilities | None = None) -> dict:
    """Validate and copy raw typed answers without lossy coercion or renaming."""
    validate_questions(questions, capabilities)
    if (not isinstance(payload, dict) or not isinstance(payload.get('answers'), dict)
            or set(payload['answers']) != set(questions)):
        raise ValueError('SystemOne response question keys do not match')
    validated = {}
    for name, question in questions.items():
        answer = payload['answers'][name]
        kind = question['type']
        if not isinstance(answer, dict) or answer.get('type') != kind:
            raise ValueError('SystemOne response question type does not match')
        # Also reject non-finite values in optional concrete-provider fields.
        json.dumps(answer, allow_nan=False)
        if kind == 'noul':
            if not probability(answer.get('noul')):
                raise ValueError('Invalid SystemOne noul probability')
            # A concrete provider may additionally supply confidence/distribution.
            if 'confidence' in answer and not probability(answer['confidence']):
                raise ValueError('Invalid SystemOne noul confidence')
            if 'probabilities' in answer:
                probs = _distribution(answer['probabilities'], {'false', 'true'})
                if not math.isclose(probs['true'], answer['noul'], rel_tol=0, abs_tol=PROBABILITY_TOLERANCE):
                    raise ValueError('Inconsistent SystemOne noul distribution')
        else:
            if not probability(answer.get('confidence')):
                raise ValueError('Invalid SystemOne confidence')
            if kind == 'choice':
                labels = set(question['criteria'])
                probs = _distribution(answer.get('probabilities'), labels)
                selected = answer.get('choice')
                if not isinstance(selected, str) or selected not in labels or probs[selected] + 1e-9 < max(probs.values()):
                    raise ValueError('Invalid SystemOne selected choice')
            else:
                legend = {str(i): item for i, item in enumerate(question['criteria'])}
                if answer.get('legend') != legend:
                    raise ValueError('SystemOne score legend does not match rubric')
                probs = _distribution(answer.get('probabilities'), set(legend))
                score = answer.get('score')
                expected = sum(int(k) * p for k, p in probs.items())
                # Rounded probabilities can perturb the expectation by up to
                # number of levels * the probability rounding tolerance.
                if (not _finite_number(score) or not 0 <= score <= len(legend) - 1
                        or not math.isclose(score, expected, rel_tol=0,
                                            abs_tol=PROBABILITY_TOLERANCE * len(legend))):
                    raise ValueError('Invalid SystemOne expected score')
        validated[name] = copy.deepcopy(answer)
    return validated


def _positive_timeout(value: Any) -> float:
    try:
        if isinstance(value, bool):
            raise ValueError
        number = float(value)
        if not math.isfinite(number) or number <= 0:
            raise ValueError
        return number
    except (TypeError, ValueError, OverflowError):
        raise ValueError('SystemOne timeout must be finite and positive') from None


def _capture_usage(raw: Any) -> dict:
    """Keep independently valid token/cost receipts even if another field fails."""
    unknown = {'source': 'unknown', 'input_tokens': None, 'output_tokens': None,
               'total_tokens': None, 'provider_cost': None, 'cost_currency': None}
    if not isinstance(raw, dict):
        return unknown
    counts = [raw.get(k) for k in ('input_tokens', 'output_tokens')]
    if all(isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in counts):
        unknown.update(source='reported', input_tokens=counts[0], output_tokens=counts[1],
                       total_tokens=sum(counts))
    cost = raw.get('cost', raw.get('provider_cost'))
    if _finite_number(cost) and cost >= 0:
        unknown['provider_cost'] = cost
    currency = raw.get('cost_currency')
    if isinstance(currency, str) and currency.strip():
        unknown['cost_currency'] = currency
    return unknown


def _usage_receipt(raw: Any) -> dict:
    if raw is None:
        return _capture_usage(raw)
    if not isinstance(raw, dict):
        raise ValueError('Invalid SystemOne usage')
    counts = [raw.get(k) for k in ('input_tokens', 'output_tokens')]
    if not all(isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in counts):
        raise ValueError('Invalid SystemOne token usage')
    cost = raw.get('cost', raw.get('provider_cost'))
    if cost is not None and (not _finite_number(cost) or cost < 0):
        raise ValueError('Invalid SystemOne reported cost')
    # Never invent a price/currency, even for a known provider.
    currency = raw.get('cost_currency')
    if currency is not None and (not isinstance(currency, str) or not currency.strip()):
        raise ValueError('Invalid SystemOne currency')
    return _capture_usage(raw)


def validate_public_state(state: Any) -> None:
    """Defense in depth, not a replacement for the public-only state builder.

    Reject explicit credential/private-source fields recursively. This cannot
    establish the provenance of arbitrary prose: callers still must whitelist
    input paths and sanitize evaluator diagnostics before building state.
    """
    forbidden = {'api_key', 'apikey', 'authorization', 'password', 'secret',
                 'access_token', 'refresh_token', 'private_key', 'credentials',
                 'private_checker', 'private_checker_source', 'hidden_checker',
                 'checker_source', 'reference_source', 'hidden_reference',
                 'private_reference', 'env', '.env'}
    if isinstance(state, dict):
        for key, value in state.items():
            if not isinstance(key, str):
                raise ValueError('SystemOne state keys must be strings')
            if key.lower().replace('-', '_') in forbidden:
                raise ValueError('SystemOne input contains a prohibited private field')
            validate_public_state(value)
    elif isinstance(state, (list,tuple)):
        for value in state:
            validate_public_state(value)
    elif isinstance(state, str) and re.search(
            r'authorization\s*:|\bbearer\s+\S+|'
            r'(?:api[_ -]?key|access[_ -]?token|password|secret)\s*[=:]', state, re.I):
        raise ValueError('SystemOne input contains a prohibited credential marker')


def _campaign_budget():
    """Load only the repository's guarded campaign module; no sys.path edits."""
    path = Path(__file__).resolve().parents[5] / 'scripts/inference_budget.py'
    if not path.is_file():
        raise SystemOneError('SystemOne campaign admission module unavailable')
    spec = importlib.util.spec_from_file_location('_ace_systemone_campaign', path)
    if spec is None or spec.loader is None:
        raise SystemOneError('SystemOne campaign admission module unavailable')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_event(event: dict, path: Path | None) -> None:
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(event, allow_nan=False), encoding='utf-8')
        temporary.replace(path)


class SystemOneClient:
    def __init__(self, endpoint_url: str, model: str, *, api_key: str = '',
                 provider: str = 'systemone', timeout_seconds: float = 15,
                 auth_mode: str | None = None, transport=None,
                 capabilities: ProviderCapabilities | None = None):
        parsed = urlsplit(endpoint_url)
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError('SystemOne endpoint must be a full HTTP(S) URL without credentials/query/fragment')
        if not isinstance(model, str) or not model.strip():
            raise ValueError('SystemOne model must be nonempty')
        provider = {'jev': 'typesafe', 'generic': 'systemone'}.get(provider, provider)
        if provider not in CAPABILITIES and capabilities is None:
            raise ValueError('Unknown SystemOne provider; explicit capabilities required')
        self.capabilities = capabilities or CAPABILITIES[provider]
        auth_mode = auth_mode or ('bearer' if api_key or provider == 'typesafe' else 'none')
        if auth_mode not in ('none', 'bearer') or auth_mode == 'bearer' and not api_key:
            raise ValueError('SystemOne bearer authentication requires an API key')
        if any(c in api_key for c in '\r\n'):
            raise ValueError('Invalid SystemOne API key')
        self.endpoint_url = endpoint_url
        self.model = model.strip()
        self.provider = provider
        self.api_key = api_key
        self.auth_mode = auth_mode
        self.timeout_seconds = _positive_timeout(timeout_seconds)
        self.transport = transport if transport is not None else requests
        self._resolved_model = None

    @classmethod
    def from_env(cls, *, transport=None) -> 'SystemOneClient':
        def setting(name, *aliases, default=''):
            # Present-but-empty primary configuration is invalid, not an alias fallback.
            for key in (name, *aliases):
                if key in os.environ:
                    return os.environ[key].strip()
            return default

        endpoint = setting('SYSTEMONE_ENDPOINT_URL', 'JEV_ENDPOINT_URL')
        model = setting('SYSTEMONE_MODEL', 'JEV_MODEL')
        provider = setting('SYSTEMONE_PROVIDER', 'JEV_PROVIDER')
        if not provider:
            host = urlsplit(endpoint).hostname
            provider = 'typesafe' if host == 'api.typesafe.ai' else 'systemone'
        mode = setting('SYSTEMONE_API_MODE', 'JEV_API_MODE', default='systemone')
        if mode != 'systemone':
            raise ValueError('SystemOne does not support chat compatibility')
        return cls(endpoint, model, api_key=setting('SYSTEMONE_API_KEY', 'JEV_API_KEY'),
                   provider=provider, transport=transport,
                   auth_mode=setting('SYSTEMONE_AUTH_MODE', 'JEV_AUTH_MODE') or None,
                   timeout_seconds=setting('SYSTEMONE_TIMEOUT_SECONDS', 'JEV_TIMEOUT_SECONDS',
                                           'JEV_REQUEST_TIMEOUT', default='15'))

    def decide(self, state: dict, questions: dict, *, timeout: float | None = None) -> dict:
        if not isinstance(state, dict) or not state:
            raise ValueError('SystemOne needs a nonempty public state object')
        validate_public_state(state)
        validate_public_state(questions)
        validate_questions(questions, self.capabilities)
        request_timeout = self.timeout_seconds if timeout is None else min(self.timeout_seconds,_positive_timeout(timeout))
        from .budget import Deadline
        deadline=Deadline.from_env(request_timeout)
        request_timeout=deadline.timeout(request_timeout)
        body = {'model': self.model, 'state': state, 'questions': questions}
        # Match requests' json= serializer, including non-ASCII escaping, so
        # admission hashing, byte limits and token exposure cover the wire body.
        encoded = json.dumps(body, allow_nan=False)
        if self.api_key and self.api_key in encoded:
            raise ValueError('SystemOne input contains configured credentials')
        if self.capabilities.max_request_bytes is not None and len(encoded.encode()) > self.capabilities.max_request_bytes:
            raise ValueError('SystemOne request exceeds provider byte limit')
        from .cache import DecisionCache
        from .ledger import EventLedger
        root = os.environ.get('ACE_RTL_EVENT_ROOT')
        cache = DecisionCache(Path(root).parent/'decision_cache') if root else None
        context = {'provider':self.provider,'requested_model':self.model,'resolved_model':self._resolved_model,
                   'schema_version':'systemone-wire-1'}
        pinned = bool(self.capabilities.reports_resolved_model and re.fullmatch(r'jev-\d+\.\d+\.\d+',self.model))
        cached = cache.get(state,questions,**context) if cache and pinned else None
        if cached:
            answers=validate_answers(cached,questions,capabilities=self.capabilities)
            ledger=EventLedger.from_env()
            if ledger:ledger.append('decision_cache_hit',requested_model=self.model,resolved_model=self._resolved_model,
                                    network_request=False)
            return {'answers':answers,'requested_model':self.model,'resolved_model':self._resolved_model,
                    'usage':{'source':'local_cache_no_request'},'latency_seconds':0.0,'call_id':'cache-'+uuid.uuid4().hex}
        budget = _campaign_budget()
        ticket = budget.reserve('jev', encoded, 128 * len(questions))
        call_id = uuid.uuid4().hex
        directory = os.environ.get('ACE_EXPERIMENT_TELEMETRY')
        path = Path(directory) / f'{call_id}.json' if directory else None
        event = {'call_id': call_id, 'provider': 'jev', 'systemone_provider': self.provider,
                 'status': 'inflight', 'usage': None, 'usage_unknown': True,
                 'budget_ticket': ticket['id'], 'request_sha256': hashlib.sha256(encoded.encode()).hexdigest(),
                 'started_at': datetime.now(timezone.utc).isoformat(), 'role':'rule_selector' if 'rules' in state else 'jev_decision',
                 'model':self.model,'requested_model':self.model,'retry_index':0,'cache_hit':False,
                 'parent_action_id':os.environ.get('ACE_RTL_PARENT_ACTION'),
                 'question_keys':list(questions),'schema_version':'systemone-wire-1'}
        usage = None
        started = time.perf_counter()
        try:
            _write_event(event, path)
            if path:
                _write_event(body,path.parent/'requests'/f'{call_id}.json')
            headers = {'Content-Type': 'application/json'}
            if self.auth_mode == 'bearer':
                headers['Authorization'] = 'Bearer ' + self.api_key
            post = self.transport.post if hasattr(self.transport, 'post') else self.transport
            try:
                request_timeout=deadline.timeout(request_timeout)
                response = post(self.endpoint_url, json=body, headers=headers,
                                timeout=request_timeout, allow_redirects=False)
            except requests.Timeout:
                raise SystemOneTransportError('timeout') from None
            except requests.RequestException:
                raise SystemOneTransportError('connection') from None
            if not 200 <= response.status_code < 300:
                raise SystemOneHTTPError(response.status_code)
            try:
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError
                # Capture validated receipts *before* any model/answer failure.
                usage = _capture_usage(payload.get('usage'))
                event.update(usage=usage, usage_unknown=usage['source'] != 'reported')
                _usage_receipt(payload.get('usage'))
                if self.capabilities.usage_required and usage['source'] != 'reported':
                    raise ValueError
                reported_model = payload.get('model')
                if reported_model is not None and (not isinstance(reported_model, str) or not reported_model.strip()):
                    raise ValueError
                if self.capabilities.model_required and reported_model is None:
                    raise ValueError
                if self.provider == 'ollama' and reported_model != self.model:
                    raise ValueError
                pinned = r'jev-\d+\.\d+\.\d+'
                if (self.capabilities.reports_resolved_model and re.fullmatch(pinned, self.model)
                        and isinstance(reported_model, str) and re.fullmatch(pinned, reported_model)
                        and reported_model != self.model):
                    raise ValueError
                answers = validate_answers(payload, questions, capabilities=self.capabilities)
            except (ValueError, TypeError, KeyError, OverflowError):
                raise SystemOneSchemaError() from None
            # TypeSafe may return an alias in live schema examples. Only a concrete
            # versioned ID counts as cache-safe; neither request pinning nor an
            # Ollama mutable tag/echo proves what weights actually answered.
            resolved_model = None
            if (self.capabilities.reports_resolved_model and isinstance(reported_model, str)
                    and re.fullmatch(r'jev-\d+\.\d+\.\d+', reported_model)):
                resolved_model = reported_model
            self._resolved_model = resolved_model
            event['resolved_model'] = resolved_model
            event['reported_model'] = reported_model
            if path:
                _write_event({'answers':answers,'requested_model':self.model,'reported_model':reported_model,
                              'resolved_model':resolved_model,'usage':usage},path.parent/'responses'/f'{call_id}.json')
            if cache and pinned and resolved_model:
                cache.put(state,questions,{'answers':answers},provider=self.provider,requested_model=self.model,
                          resolved_model=resolved_model,schema_version='systemone-wire-1')
            event.update(status='ok')
            return {'answers': answers, 'requested_model': self.model,
                    'resolved_model': resolved_model, 'usage': usage,
                    'latency_seconds': time.perf_counter() - started, 'call_id': call_id}
        except SystemOneError as exc:
            event.update(status='error', error_type=type(exc).__name__, error_kind=exc.kind,
                         http_status=exc.status_code)
            raise
        finally:
            event['latency_seconds'] = time.perf_counter() - started
            try:
                _write_event(event, path)
            finally:
                budget.settle(ticket, usage)
