"""Validated choice-only adapter for the actually verified SystemOne/JEV contract.

This module is independent of RTL generation and does not enable optimization.
Only an explicitly enabled, separately tested judgment hook may call it.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests

from experiment_config import positive_number, require_jev
from local_llm_adapter import usage_metrics, write_event


class DecisionError(RuntimeError):
    """Sanitized model/transport/schema failure; original reasoning may fall back."""


def probability(value) -> bool:
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and 0<=value<=1


def validate_answers(payload: dict, questions: dict) -> dict:
    if not isinstance(payload,dict) or not isinstance(payload.get('answers'),dict):
        raise ValueError('Decision response missing answers map')
    validated={}
    for name,question in questions.items():
        answer=payload['answers'].get(name)
        labels=question['criteria']
        if not isinstance(answer,dict) or answer.get('type')!='choice' or answer.get('choice') not in labels:
            raise ValueError('Invalid decision type or label')
        probs=answer.get('probabilities')
        if not isinstance(probs,dict) or set(probs)!=set(labels) or not all(probability(p) for p in probs.values()):
            raise ValueError('Invalid decision probabilities')
        if not math.isclose(sum(probs.values()),1,abs_tol=0.001):
            raise ValueError('Decision probability distribution does not sum to one')
        if probs[answer['choice']]+1e-9<max(probs.values()) or not probability(answer.get('confidence')):
            raise ValueError('Invalid winning decision or confidence')
        validated[name]={'type':'choice','choice':answer['choice'],'probabilities':probs,'confidence':answer['confidence']}
    return validated


def decision_usage(usage: dict | None, prompt: str, completion: str) -> dict:
    usage=usage if isinstance(usage,dict) else {}
    counts=[usage.get(k) for k in ('input_tokens','output_tokens')]
    if all(isinstance(n,int) and not isinstance(n,bool) and n>=0 for n in counts):
        result=usage_metrics({'prompt_tokens':counts[0],'completion_tokens':counts[1],'total_tokens':sum(counts)},prompt,completion)
    else:result=usage_metrics(None,prompt,completion)
    cost=usage.get('cost')
    result['provider_cost']=cost if isinstance(cost,(int,float)) and not isinstance(cost,bool) and math.isfinite(cost) and cost>=0 else None
    return result


def decide(state: str | dict, questions: dict) -> dict:
    config=require_jev()
    if not isinstance(state,(str,dict)) or not state or not isinstance(questions,dict) or not questions:
        raise ValueError('Decision needs nonempty state and questions')
    for question in questions.values():
        if (not isinstance(question,dict) or question.get('type')!='choice'
                or not isinstance(question.get('instructions'),str) or not question['instructions'].strip()
                or not isinstance(question.get('criteria'),dict) or not 2<=len(question['criteria'])<=26
                or any(not isinstance(k,str) or not isinstance(v,str) or not v.strip() for k,v in question['criteria'].items())):
            raise ValueError('Only validated choice questions with 2–26 described options are supported')
    body={'model':config['JEV_MODEL'],'state':state,'questions':questions}
    encoded=json.dumps(body,ensure_ascii=False)
    call_id=uuid.uuid4().hex
    directory=os.environ.get('ACE_EXPERIMENT_TELEMETRY')
    path=Path(directory)/f'{call_id}.json' if directory else None
    event={'call_id':call_id,'provider':'jev','model':config['JEV_MODEL'],
           'case_id':os.environ.get('ACE_EXPERIMENT_CASE_ID'),'mode':os.environ.get('ACE_EXPERIMENT_MODE','jev'),
           'phase':os.environ.get('ACE_EXPERIMENT_PHASE','evaluation'),'questions':list(questions),
           'started_at':datetime.now(timezone.utc).isoformat(),'status':'inflight','usage':None,'usage_unknown':True,
           'request_sha256':hashlib.sha256(encoded.encode()).hexdigest(),'prompt_chars':len(encoded),'fallback':False}
    write_event(event,path);started=time.perf_counter()
    headers={'Authorization':'Bearer '+config['JEV_API_KEY']} if config['JEV_AUTH_MODE']=='bearer' else {}
    try:
        try:response=requests.post(config['JEV_ENDPOINT_URL'],json=body,headers=headers,timeout=positive_number('JEV_REQUEST_TIMEOUT',15))
        except requests.Timeout:raise DecisionError('JEV request timeout') from None
        except requests.RequestException:raise DecisionError('JEV connection error') from None
        if not response.ok:raise DecisionError(f'JEV HTTP {response.status_code} (body withheld)')
        try:
            payload=response.json()
            if isinstance(payload,dict):
                supplied=decision_usage(payload.get('usage'),encoded,'')
                if supplied['source']=='reported':event.update(usage=supplied,usage_unknown=False)
            answers=validate_answers(payload,questions)
        except (ValueError,TypeError,KeyError):raise DecisionError('JEV invalid response schema') from None
        usage=decision_usage(payload.get('usage'),encoded,json.dumps(answers))
        event.update(status='ok',usage=usage,usage_unknown=False,answers=answers)
        return {'answers':answers,'usage':usage,'call_id':call_id,'event_file':str(path) if path else None}
    except DecisionError as exc:
        event.update(status='error',error_type=type(exc).__name__,error_message=str(exc))
        raise
    finally:
        event['latency_seconds']=time.perf_counter()-started
        write_event(event,path)
