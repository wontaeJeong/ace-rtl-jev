"""Finite-choice retrospective judgment; never generates RTL or deep fix guidance."""
from __future__ import annotations

import difflib
import json
import math
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from inference_budget import BudgetDenied
from local_llm_adapter import write_event
from systemone_adapter import DecisionError, decide

CRITERIA={
    'resolved':'The specific target error is gone and no new failure is reported.',
    'persistent':'The same target error remains; no clear new failure was introduced.',
    'regression':'The target error remains and additional/new failures or regression appeared.',
    'changed':'The target error is gone but a different/new failure now appears.',
    'uncertain':'The bounded evidence is insufficient to determine the effect reliably.',
}
QUESTIONS={'effectiveness':{'type':'choice','instructions':'Judge only the effect on the specified target error from the generated-code diff and real emitted evaluator report. Do not invent test outcomes or generate code. Prefer uncertain when evidence is insufficient.','criteria':CRITERIA}}


class DecisionFallback(RuntimeError):
    def __init__(self,reason):self.reason=reason;super().__init__(reason)


def bounded(text: str, size: int) -> str:
    if len(text)<=size:return text
    marker='\n... [BOUNDED PUBLIC EVIDENCE] ...\n'
    remaining=size-len(marker)
    return text[:remaining//2]+marker+text[-(remaining-remaining//2):]


def build_state(before: str, after: str, guidance: str, error: str, report: str) -> str:
    delta='\n'.join(difflib.unified_diff(before.splitlines(),after.splitlines(),fromfile='generated_before',tofile='generated_after',n=2))
    return ('Target error:\n'+bounded(error,1200)+'\nApplied guidance:\n'+bounded(guidance,1200)
            +'\nGenerated-code diff:\n'+bounded(delta,4000)+'\nEvaluator report:\n'+bounded(report,5000))


def effectiveness(label: str) -> str:
    return {
        'resolved':'The target error was resolved successfully.',
        'persistent':'Did not solve the target error; it is still present.',
        'regression':'The target error remains and a new error/regression was introduced.',
        'changed':'The target error was resolved but a different error now appears.',
    }[label]


def confidence_threshold() -> float:
    try:value=float(os.environ.get('JEV_MIN_CONFIDENCE','0.65'))
    except ValueError:raise ValueError('JEV_MIN_CONFIDENCE must be a finite probability') from None
    if not math.isfinite(value) or not 0<=value<=1:raise ValueError('JEV_MIN_CONFIDENCE must be a finite probability')
    return value


def judge_retrospective(before: str, after: str, guidance: str, error: str, report: str) -> tuple[str,str]:
    threshold=confidence_threshold()
    with call_kind('retrospective_decision'):
        try:result=decide(build_state(before,after,guidance,error,report),QUESTIONS)
        except BudgetDenied:raise
        except (DecisionError,ValueError):raise DecisionFallback('decision_error') from None
    answer=result['answers']['effectiveness']
    reason=None
    if answer['choice']=='uncertain':reason='uncertain'
    elif answer['confidence']<threshold:reason='low_confidence'
    path=Path(result['event_file']) if result.get('event_file') else None
    if path:
        event=json.loads(path.read_text())
        event.update(fallback=reason is not None,fallback_reason=reason,decision_used=reason is None)
        write_event(event,path)
    if reason:raise DecisionFallback(reason)
    removed=len(set(before.splitlines())-set(after.splitlines()))
    added=len(set(after.splitlines())-set(before.splitlines()))
    summary=f'Generated-code delta: {removed} distinct lines removed, {added} distinct lines added; no causal explanation inferred.'
    return summary,effectiveness(answer['choice'])


@contextmanager
def call_kind(kind: str):
    previous=os.environ.get('ACE_EXPERIMENT_CALL_KIND');os.environ['ACE_EXPERIMENT_CALL_KIND']=kind
    try:yield
    finally:
        if previous is None:os.environ.pop('ACE_EXPERIMENT_CALL_KIND',None)
        else:os.environ['ACE_EXPERIMENT_CALL_KIND']=previous


@contextmanager
def primary_fallback(reason: str):
    names=('ACE_EXPERIMENT_FALLBACK','ACE_EXPERIMENT_FALLBACK_REASON')
    previous={name:os.environ.get(name) for name in names}
    os.environ.update(ACE_EXPERIMENT_FALLBACK='1',ACE_EXPERIMENT_FALLBACK_REASON=reason)
    directory=os.environ.get('ACE_EXPERIMENT_TELEMETRY')
    if directory:
        write_event({'event':'primary_fallback','reason':reason,'case_id':os.environ.get('ACE_EXPERIMENT_CASE_ID'),
                     'at_utc':datetime.now(timezone.utc).isoformat()},Path(directory)/('fallback-'+uuid.uuid4().hex+'.json'))
    try:
        with call_kind('retrospective_fallback'):yield
    finally:
        for name,value in previous.items():
            if value is None:os.environ.pop(name,None)
            else:os.environ[name]=value
