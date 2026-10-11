#!/usr/bin/env python3
"""Primary model adapter for the original ACE_RTL_LLM_SCRIPT protocol."""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

from experiment_config import load_config, positive_number, require_primary
from inference_budget import reserve, settle


def usage_metrics(usage: dict | None, prompt: str, completion: str) -> dict:
    fields = ('prompt_tokens', 'completion_tokens', 'total_tokens')
    if (isinstance(usage, dict) and all(isinstance(usage.get(k), int) and not isinstance(usage[k], bool) and usage[k] >= 0 for k in fields)
            and usage['total_tokens']==usage['prompt_tokens']+usage['completion_tokens']):
        return {**{k: usage[k] for k in fields}, 'source': 'reported',
                 'cached_tokens': usage['prompt_tokens_details'].get('cached_tokens') if isinstance(usage.get('prompt_tokens_details'), dict) else None,
                 'reasoning_tokens': usage['completion_tokens_details'].get('reasoning_tokens') if isinstance(usage.get('completion_tokens_details'), dict) else None}
    p, c = math.ceil(len(prompt) / 4), math.ceil(len(completion) / 4)
    return {'prompt_tokens': p, 'completion_tokens': c, 'total_tokens': p + c,
            'source': 'estimated_chars_div_4', 'cached_tokens': None, 'reasoning_tokens': None}


def write_event(record: dict, path: Path | None) -> None:
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        # Never allow configured credentials to leak through error/fallback metadata.
        secrets = [secret for key, secret in os.environ.items() if secret and
            (any(s in key.upper() for s in ('API_KEY', 'PASSWORD', 'SECRET')) or
             key.upper().endswith(('ACCESS_TOKEN', 'AUTH_TOKEN')))]
        def clean(value):
            if isinstance(value, dict):
                return {key: '[REDACTED]' if any(s in key.lower() for s in ('authorization', 'api_key', 'password', 'secret'))
                        else clean(item) for key, item in value.items()}
            if isinstance(value, (list, tuple)):
                return [clean(item) for item in value]
            if isinstance(value, str):
                for secret in sorted(secrets, key=len, reverse=True):
                    value = value.replace(secret, '[REDACTED]')
            return value
        encoded = json.dumps(clean(record), indent=2)
        with temporary.open('w', encoding='utf-8') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def request_timeout():
    timeout = positive_number('REQUEST_TIMEOUT', 60)
    raw = os.environ.get('ACE_RTL_DEADLINE_MONOTONIC')
    if raw is not None:
        try:
            end = float(raw)
        except ValueError:
            raise RuntimeError('NON_RETRYABLE: invalid shared deadline') from None
        if not math.isfinite(end):
            raise RuntimeError('NON_RETRYABLE: invalid shared deadline')
        remaining = end - time.monotonic()
        if remaining <= 0:
            raise RuntimeError('NON_RETRYABLE: common deadline exhausted')
        timeout = min(timeout, remaining)
    return timeout


class InferenceHTTPError(RuntimeError):
    def __init__(self, status, retry_after=None):
        self.code = status
        try:
            seconds = float(retry_after)
        except (TypeError, ValueError):
            try:
                seconds = parsedate_to_datetime(str(retry_after)).timestamp() - time.time()
            except (TypeError, ValueError, OverflowError):
                seconds = None
        self.retry_after = max(0.0, seconds) if seconds is not None and math.isfinite(seconds) else None
        suffix = f' Retry-After={self.retry_after}' if self.retry_after is not None else ''
        super().__init__(f'HTTP {status}: primary inference request failed (body withheld){suffix}')


def complete(request: dict) -> dict:
    config = require_primary()
    messages = request.get('messages')
    if not isinstance(messages, list) or not messages or any(not isinstance(m, dict) or not isinstance(m.get('content'), str) for m in messages):
        raise ValueError('messages must be a nonempty list with string content')
    model = request.get('model') or config['LLM_MODEL']
    try:
        aliases = json.loads(os.environ.get('ACE_RTL_MODEL_ALIASES', '{}'))
    except ValueError:
        raise ValueError('Invalid configured model aliases') from None
    if not isinstance(aliases, dict) or any(not isinstance(v, str) or not v for v in aliases.values()):
        raise ValueError('Invalid configured model aliases')
    if model != config['LLM_MODEL'] and model not in aliases.values():
        raise ValueError('Request model differs from configured LLM_MODEL')
    parameter = os.environ.get('LLM_TOKEN_PARAMETER', 'max_tokens')
    if parameter not in ('max_tokens', 'max_completion_tokens'):
        raise ValueError('LLM_TOKEN_PARAMETER must be max_tokens or max_completion_tokens')
    token_limit = request.get('max_tokens', 32768)
    if not isinstance(token_limit, int) or isinstance(token_limit, bool) or token_limit <= 0:
        raise ValueError('max_tokens must be a positive integer')
    body = {'model': model, 'messages': messages, parameter: token_limit, 'stream': False}
    sampling = os.environ.get('LLM_SAMPLING_MODE', 'explicit')
    if sampling == 'explicit':
        body.update(temperature=request.get('temperature', 0.2), top_p=request.get('top_p', 0.95))
    elif sampling != 'default':
        raise ValueError('LLM_SAMPLING_MODE must be explicit or default')
    # NVIDIA-specific extra_body fields are intentionally not sent to another provider.
    prompt = json.dumps(messages, ensure_ascii=False)
    request_timeout()  # Reject expired work before creating an inference reservation.
    ticket=reserve('primary',prompt,token_limit)
    call_id = uuid.uuid4().hex
    directory = os.environ.get('ACE_EXPERIMENT_TELEMETRY')
    path = Path(directory) / f'{call_id}.json' if directory else None
    record = {'call_id': call_id, 'provider': 'primary', 'model': model,
              'case_id': os.environ.get('ACE_EXPERIMENT_CASE_ID'),
              'mode': os.environ.get('ACE_EXPERIMENT_MODE', 'baseline'),
              'phase': os.environ.get('ACE_EXPERIMENT_PHASE', 'evaluation'),
              'started_at': datetime.now(timezone.utc).isoformat(),
              'request_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
              'prompt_chars': len(prompt), 'status': 'inflight', 'usage': None,
              'usage_unknown': True, 'fallback': os.environ.get('ACE_EXPERIMENT_FALLBACK') == '1',
              'fallback_reason':os.environ.get('ACE_EXPERIMENT_FALLBACK_REASON'), 'budget_ticket':ticket['id'],
              'kind':os.environ.get('ACE_EXPERIMENT_CALL_KIND','primary_reasoning')}
    record.update(role=os.environ.get('ACE_RTL_ROLE', 'unknown'),
                  attempt=os.environ.get('ACE_RTL_ATTEMPT_ID'),
                  parent_action=os.environ.get('ACE_RTL_PARENT_ACTION'))
    write_event(record, path)
    started = time.perf_counter()
    try:
        try:
            response = requests.post(config['LLM_BASE_URL'].rstrip('/') + '/chat/completions',
                                     json=body, headers={'Authorization': 'Bearer ' + config['LLM_API_KEY']},
                                     timeout=request_timeout(),allow_redirects=False)
        except requests.Timeout:
            request_timeout()  # Deadline expiry is nonretryable, ordinary socket timeout is bounded retryable.
            raise RuntimeError('timeout: primary inference request') from None
        except requests.RequestException:
            raise RuntimeError('connection error: primary inference request') from None
        if not 200<=response.status_code<300:
            raise InferenceHTTPError(response.status_code, getattr(response, 'headers', {}).get('Retry-After'))
        try:
            payload = response.json()
            if isinstance(payload, dict):
                supplied_usage=usage_metrics(payload.get('usage'), prompt, '')
                if supplied_usage['source']=='reported':
                    record.update(usage=supplied_usage, usage_unknown=False)
            choice = payload['choices'][0]
            content = choice['message']['content']
        except (ValueError, KeyError, IndexError, TypeError):
            raise RuntimeError('Invalid primary response schema') from None
        if not isinstance(content, str) or not content.strip():
            if choice.get('finish_reason') == 'length':
                raise RuntimeError('NON_RETRYABLE: empty response exhausted output budget')
            raise RuntimeError('empty response: primary inference')
        # Never propagate arbitrary provider metadata/error bodies to original run logs.
        for name in ('LLM_API_KEY', 'JEV_API_KEY'):
            secret = os.environ.get(name)
            if secret:
                content = content.replace(secret, '[REDACTED]')
        usage = payload.get('usage')
        metrics = usage_metrics(usage, prompt, content)
        record.update(status='ok', usage=metrics, usage_unknown=metrics['source'] != 'reported',
                      finish_reason=choice.get('finish_reason'), completion_chars=len(content))
        return {'choices': [{'message': {'role': 'assistant', 'content': content},
                             'finish_reason': choice.get('finish_reason')}], 'usage': usage}
    except Exception as exc:
        record.update(status='error', error_type=type(exc).__name__)
        raise
    finally:
        record['latency_seconds'] = time.perf_counter() - started
        write_event(record, path)
        settle(ticket,record.get('usage'))


def main() -> int:
    load_config()
    try:
        print(json.dumps(complete(json.load(sys.stdin))))
        return 0
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
