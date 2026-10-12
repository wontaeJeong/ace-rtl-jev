"""One monotonic deadline and the existing SQLite campaign admission contract."""
from __future__ import annotations

import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import subprocess
import time
import uuid
from email.utils import parsedate_to_datetime

from .ledger import EventLedger


class Deadline:
    def __init__(self, seconds, clock=time.monotonic):
        seconds = float(seconds)
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError('deadline seconds must be finite and nonnegative')
        self.clock = clock
        self.end = clock() + seconds

    def remaining(self):
        return max(0.0, self.end - self.clock())

    @property
    def expired(self):
        return self.remaining() <= 0

    def timeout(self, requested):
        remaining = self.remaining()
        if remaining <= 0:
            raise TimeoutError('NON_RETRYABLE: common deadline exhausted')
        requested = float(requested)
        if not math.isfinite(requested) or requested <= 0:
            raise ValueError('timeout must be positive and finite')
        return min(requested, remaining)

    @classmethod
    def from_env(cls, seconds=None):
        raw = os.environ.get('ACE_RTL_DEADLINE_MONOTONIC')
        if raw is not None:
            end = float(raw)
            if not math.isfinite(end):
                raise ValueError('invalid shared monotonic deadline')
            result = cls(max(0, end - time.monotonic()))
            result.end = end
            if seconds is not None:
                result.end = min(end, time.monotonic() + float(seconds))
            return result
        return cls(seconds if seconds is not None else float(os.environ.get('ACE_RTL_LLM_TIMEOUT', '1800')))

    def sleep(self, seconds):
        time.sleep(min(max(0, seconds), self.remaining()))
        if self.expired:
            raise TimeoutError('NON_RETRYABLE: common deadline exhausted during backoff')


def campaign():
    """Load the same module used by user adapters; do not create a second budget."""
    if 'inference_budget' in sys.modules:
        return sys.modules['inference_budget']
    for parent in Path(__file__).resolve().parents:
        path = parent / 'scripts/inference_budget.py'
        if path.is_file():
            spec = importlib.util.spec_from_file_location('inference_budget', path)
            module = importlib.util.module_from_spec(spec)
            sys.modules['inference_budget'] = module
            spec.loader.exec_module(module)
            return module
    raise RuntimeError('NON_RETRYABLE: inference_budget.py campaign module unavailable')


def adapter_manages_budget(script_path):
    declared = os.environ.get('ACE_RTL_ADAPTER_BUDGET_MANAGED')
    if declared is not None:
        return declared.lower() in ('1', 'true', 'yes')
    # Existing user adapter owns its reservation, settlement and unknown usage records.
    path = Path(script_path).resolve()
    return any(path == parent / 'scripts/local_llm_adapter.py' for parent in Path(__file__).resolve().parents)


def usage_envelope(raw):
    raw = raw if isinstance(raw, dict) else {}
    known = isinstance(raw.get('total_tokens'), int) and not isinstance(raw.get('total_tokens'), bool) and raw['total_tokens'] >= 0
    known = known and raw.get('source', 'reported') == 'reported'
    if raw.get('prompt_tokens') is not None and raw.get('completion_tokens') is not None:
        known = known and all(type(raw[k]) is int and raw[k] >= 0 for k in ('prompt_tokens', 'completion_tokens'))
        known = known and raw.get('total_tokens') == raw.get('prompt_tokens') + raw.get('completion_tokens')
    details = raw.get('completion_tokens_details') or {}
    prompt_details = raw.get('prompt_tokens_details') or {}
    details = details if isinstance(details, dict) else {}
    prompt_details = prompt_details if isinstance(prompt_details, dict) else {}
    source = 'reported' if known else raw.get('source', 'unknown')
    if not known and source == 'reported':
        source = 'unknown'
    return dict(raw, source=source,
                input_tokens=raw.get('input_tokens', raw.get('prompt_tokens')),
                output_tokens=raw.get('output_tokens', raw.get('completion_tokens')),
                cached_tokens=raw.get('cached_tokens', prompt_details.get('cached_tokens')),
                reasoning_tokens=raw.get('reasoning_tokens', details.get('reasoning_tokens')))


def retryable(error):
    text = str(error).lower()
    if 'non_retryable' in text:
        return False
    code = getattr(error, 'code', None)
    match = re.search(r'(?:http(?:/\d(?:\.\d)?)?\s+|status[=: ]+)(\d{3})\b', text)
    code = int(match.group(1)) if match else code
    if code is not None:
        return code == 429 or 500 <= code <= 599
    if isinstance(error, ValueError) or 'non_retryable' in text:
        return False
    if any(s in text for s in ('validation', 'context window', 'contextwindow', 'maximum context', 'too many tokens', 'invalid', 'unauthorized', 'forbidden')):
        return False
    return any(s in text for s in ('timeout', 'timed out', 'connection reset', 'connection error',
                                   'connection failure', 'temporarily unavailable', 'rate limit',
                                   'too many requests', 'overloaded', 'http 429'))


def retry_after_seconds(value):
    if value is None:
        return None
    try:
        seconds = float(value)
    except (ValueError, TypeError):
        try:
            seconds = parsedate_to_datetime(str(value)).timestamp() - time.time()
        except (ValueError, TypeError, OverflowError):
            return None
    return max(0.0, seconds) if math.isfinite(seconds) else None


class HTTPRequestError(RuntimeError):
    def __init__(self, code, retry_after=None):
        self.code = int(code)
        self.retry_after = retry_after_seconds(retry_after)
        suffix = f' Retry-After={self.retry_after}' if self.retry_after is not None else ''
        super().__init__(f'HTTP {self.code}: request failed (body withheld){suffix}')


def retry_delay(error, backoff):
    value = getattr(error, 'retry_after', None)
    if value is None:
        match = re.search(r'Retry-After\s*[=:]\s*([\d.]+)', str(error), re.I)
        value = match.group(1) if match else None
    delay = retry_after_seconds(value)
    return max(backoff, delay) if delay is not None else backoff


class PaidCall:
    """Every physical request gets admission; crashes retain conservative exposure."""
    def __init__(self, *, provider, model, messages, max_tokens, managed=False, role=None,
                 retry_index=0, ledger=None, parent_action=None):
        self.provider = provider
        self.model = model
        self.messages = messages
        self.max_tokens = max_tokens
        self.managed = managed
        self.role = role or os.environ.get('ACE_RTL_ROLE', 'unknown')
        self.retry_index = retry_index
        self.parent_action = parent_action or os.environ.get('ACE_RTL_PARENT_ACTION')
        self.ledger = ledger or EventLedger.from_env()
        self.ticket = None
        self.usage = usage_envelope(None)
        self.call_id = uuid.uuid4().hex
        self.request_id = None

    def __enter__(self):
        self.started = time.monotonic()
        if not self.managed:
            self.ticket = campaign().reserve('primary', json.dumps(self.messages, ensure_ascii=False), self.max_tokens)
        self._event('call_started', status='inflight', usage=self.usage,
                    budget_ticket=self.ticket['id'] if self.ticket else None,
                    admission_owner='adapter' if self.managed else 'runtime')
        return self

    def _event(self, kind, **fields):
        if self.ledger:
            self.ledger.append(kind, call_id=self.call_id, provider=self.provider, role=self.role,
                model=self.model, parent_action=self.parent_action, retry_index=self.retry_index,
                cache_hit=False, request_id=self.request_id, **fields)

    def complete(self, payload):
        if isinstance(payload, dict):
            self.usage = usage_envelope(payload.get('usage'))
            self.request_id = payload.get('id')

    def __exit__(self, kind, error, traceback):
        if self.ticket:
            campaign().settle(self.ticket, self.usage)
        cancelled = isinstance(error, (KeyboardInterrupt, SystemExit, subprocess.TimeoutExpired)) or (
            isinstance(error, TimeoutError) and 'NON_RETRYABLE' in str(error))
        event_kind = 'call_completed' if kind is None else 'call_cancelled' if cancelled else 'call_error'
        self._event(event_kind,
            usage=self.usage, duration_seconds=time.monotonic() - self.started,
            error_type=kind.__name__ if kind else None, upstream_billing_unknown=self.usage['source'] == 'unknown')
        return False
