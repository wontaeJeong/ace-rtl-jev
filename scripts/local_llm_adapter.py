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
from pathlib import Path

import requests

from experiment_config import load_config, positive_number, require_primary


def usage_metrics(usage: dict | None, prompt: str, completion: str) -> dict:
    fields = ('prompt_tokens', 'completion_tokens', 'total_tokens')
    if isinstance(usage, dict) and all(isinstance(usage.get(k), int) and not isinstance(usage[k], bool) and usage[k] >= 0 for k in fields):
        return {**{k: usage[k] for k in fields}, 'source': 'reported',
                'cached_tokens': (usage.get('prompt_tokens_details') or {}).get('cached_tokens'),
                'reasoning_tokens': (usage.get('completion_tokens_details') or {}).get('reasoning_tokens')}
    p, c = math.ceil(len(prompt) / 4), math.ceil(len(completion) / 4)
    return {'prompt_tokens': p, 'completion_tokens': c, 'total_tokens': p + c,
            'source': 'estimated_chars_div_4', 'cached_tokens': None, 'reasoning_tokens': None}


def write_event(record: dict, path: Path | None) -> None:
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(record, indent=2), encoding='utf-8')
        temporary.replace(path)


def complete(request: dict) -> dict:
    config = require_primary()
    messages = request.get('messages')
    if not isinstance(messages, list) or not messages or any(not isinstance(m, dict) or not isinstance(m.get('content'), str) for m in messages):
        raise ValueError('messages must be a nonempty list with string content')
    model = request.get('model') or config['LLM_MODEL']
    if model != config['LLM_MODEL']:
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
              'usage_unknown': True, 'fallback': os.environ.get('ACE_EXPERIMENT_FALLBACK') == '1'}
    write_event(record, path)
    started = time.perf_counter()
    try:
        try:
            response = requests.post(config['LLM_BASE_URL'].rstrip('/') + '/chat/completions',
                                     json=body, headers={'Authorization': 'Bearer ' + config['LLM_API_KEY']},
                                     timeout=positive_number('REQUEST_TIMEOUT', 60))
        except requests.Timeout:
            raise RuntimeError('timeout: primary inference request') from None
        except requests.RequestException:
            raise RuntimeError('connection error: primary inference request') from None
        if not response.ok:
            raise RuntimeError(f'HTTP {response.status_code}: primary inference request failed (body withheld)')
        try:
            payload = response.json()
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
        record.update(status='ok', usage=usage_metrics(usage, prompt, content), usage_unknown=False,
                      finish_reason=choice.get('finish_reason'), completion_chars=len(content))
        return {'choices': [{'message': {'role': 'assistant', 'content': content},
                             'finish_reason': choice.get('finish_reason')}], 'usage': usage}
    except Exception as exc:
        record.update(status='error', error_type=type(exc).__name__)
        raise
    finally:
        record['latency_seconds'] = time.perf_counter() - started
        write_event(record, path)


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
