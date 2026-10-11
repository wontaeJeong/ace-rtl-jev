#!/usr/bin/env python3
"""Cost-bounded judgment audit and one-case E2E using existing baseline evidence."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import os
import re
import sys
from collections import Counter,deque
from pathlib import Path

from experiment_config import ROOT,load_config,require_jev
from inference_budget import BudgetDenied,snapshot
from jev_retrospective import QUESTIONS,build_state,confidence_threshold
from local_llm_adapter import write_event
from run_experiments import run_batch
from systemone_adapter import DecisionError,decide

sys.path.insert(0,str(ROOT/'skills/ace-rtl/scripts'))
from ace_rtl_agent.focused_guidance import FocusedGuidanceMixin
from ace_rtl_agent.llm_backend import enforce_prompt_char_budget


def match_calls(events: list[dict], request_sha: str) -> list[dict] | None:
    matches=[e for e in events if e.get('provider')=='primary' and e.get('request_sha256')==request_sha]
    if not matches or not all(e.get('usage',{} ) and e['usage'].get('source')=='reported' for e in matches):return None
    return matches


class CaptureClient:
    def __init__(self):self.prompt=None
    def call_llm(self,prompt,**kwargs):self.prompt=prompt;return '### IMPLEMENTATION CHANGES\nCaptured only\n### FIX EFFECTIVENESS\nCaptured only'


class OriginalPrompt(FocusedGuidanceMixin):
    def __init__(self):
        self.llm_client=CaptureClient();self.logger=logging.getLogger('offline_prompt_capture');self.ace_rtl_stages=set()


def original_hash(before,after,guidance,error,report,model) -> str | None:
    capture=OriginalPrompt();capture._extract_implementation_changes_primary(before,after,guidance,error,report)
    if capture.llm_client.prompt is None:return None
    prompt=enforce_prompt_char_budget(capture.llm_client.prompt,model)
    messages=json.dumps([{'role':'user','content':prompt}],ensure_ascii=False)
    return hashlib.sha256(messages.encode()).hexdigest()


def read_artifact(path: str | Path, batch: Path, kind: str) -> str:
    p=Path(path).resolve();root=batch.resolve()
    if root not in p.parents:raise ValueError('Artifact outside selected baseline')
    if kind=='candidate' and 'candidate' not in p.relative_to(root).parts:raise ValueError('Not a generated candidate artifact')
    if kind=='report' and p.name!='evaluator_error_report.txt':raise ValueError('Not an emitted evaluator report')
    return p.read_text(encoding='utf-8',errors='replace')


def primary_label(text: str | None) -> str | None:
    if not text:return None
    low=text.lower();new=any(s in low for s in ('new error','different error','different failure','new failure','introduced'))
    if any(s in low for s in ('not solve','still present','remains','persists')):return 'regression' if new else 'persistent'
    if any(s in low for s in ('solved','resolved','fixed','no longer present','successfully')):return 'changed' if new else 'resolved'
    return None


def collect_snapshots(batch: Path) -> tuple[list[dict],dict]:
    data=json.loads((batch/'summary.json').read_text());model=data['manifest']['environment']['configuration']['primary_model']
    eligible=[];excluded=Counter()
    for case in data['results']:
        events=[json.loads(p.read_text()) for p in (batch/'cases'/case['id']/'calls').glob('*.json')]
        for attempt in (case.get('result') or {}).get('attempts',[]):
            history=attempt.get('history',[])
            for index,current in enumerate(history[1:],start=1):
                previous=history[index-1]
                try:
                    before=read_artifact(previous['candidate_path'],batch,'candidate')
                    after=read_artifact(current['candidate_path'],batch,'candidate')
                    if not before.strip() or not after.strip() or before==after:excluded['no_changed_nonempty_candidate']+=1;continue
                    prev_dir=Path(previous['evaluator_error_report']).parent
                    metadata=json.loads((prev_dir/'reflector.response.json').read_text())['metadata']
                    report=read_artifact(current['evaluator_error_report'],batch,'report')
                    guidance,error=metadata['guidance'],metadata['focused_error']
                    request_sha=original_hash(before,after,guidance,error,report,model)
                    matches=match_calls(events,request_sha)
                    if not matches:excluded['no_exact_complete_billing_match']+=1;continue
                    narrative=None;current_dir=Path(current['evaluator_error_report']).parent
                    emitted_prompt=current_dir/'reflector.response.prompt.txt'
                    if emitted_prompt.exists():
                        # Previously emitted agent prompt, never hidden scorer source.
                        text=emitted_prompt.read_text(errors='replace')
                        section=re.search(r'\*\*Iteration '+str(current['iteration'])+r'\*\*:(.*?)(?=\*\*Iteration|\Z)',text,re.S)
                        if section:
                            found=re.search(r'\*\*Did it solve the error\?\*\*:\s*([^\n]+)',section.group(1))
                            if found:narrative=found.group(1)
                    label=primary_label(narrative)
                    eligible.append({'snapshot_id':case['id']+':'+str(attempt['attempt'])+':'+str(current['iteration']),
                                     'case_id':case['id'],'category':case.get('category'), 'iteration':current['iteration'],
                                     'state':build_state(before,after,guidance,error,report),'primary_request_sha256':request_sha,
                                     'historical_primary_calls':len(matches),'historical_primary_tokens':sum(e['usage']['total_tokens'] for e in matches),
                                     'historical_primary_latency_seconds':sum(e.get('latency_seconds',0) for e in matches),
                                     'primary_narrative_label':label,'official_evaluator_passed':current.get('passed') is True})
                except (OSError,KeyError,ValueError):excluded['missing_generated_or_emitted_artifacts']+=1
    return eligible,dict(excluded)


def stratified_select(rows: list[dict], limit: int) -> list[dict]:
    groups={}
    for row in sorted(rows,key=lambda r:r['snapshot_id']):groups.setdefault(row['category'],deque()).append(row)
    selected=[]
    while len(selected)<limit and any(groups.values()):
        for category in sorted(groups):
            if groups[category] and len(selected)<limit:selected.append(groups[category].popleft())
    return selected


def project_baseline(data: dict, ids: list[str]) -> dict:
    result=copy.deepcopy(data);manifest=result['manifest']
    if not set(ids)<=set(manifest['case_ids']):raise ValueError('Projection has unmeasured cases')
    manifest.update(case_ids=ids,cases_planned=len(ids),source_case_count=len(data['manifest']['case_ids']),
                    elapsed_seconds=None,subset_projection=True,timing_comparable=False)
    result['results']=[r for r in result['results'] if r['id'] in ids]
    return result


def prepare(baseline: Path, output: Path, limit: int=48) -> dict:
    if limit<=0:raise ValueError('Snapshot limit must be positive')
    data=json.loads((baseline/'summary.json').read_text())
    if data['manifest']['state']!='completed':raise ValueError('Completed baseline required')
    rows,excluded=collect_snapshots(baseline);selected=stratified_select(rows,limit)
    if not selected:raise ValueError('No exact historical judgment matches; no paid study allowed')
    candidates=[]
    for case in data['results']:
        result=case.get('result') or {}
        passed=[a for a in result.get('attempts',[]) if a.get('status')=='passed' and a.get('passed_iteration',0)>=3]
        if case['status']=='success' and passed and case['metrics']['total_tokens_complete']:
            candidates.append(case)
    if not candidates:raise ValueError('No suitable measured E2E case with repair trajectory')
    chosen=min(candidates,key=lambda c:c['elapsed_seconds'])
    output.mkdir(parents=True,exist_ok=False)
    for row in selected:write_event(row,output/'inputs'/ (hashlib.sha256(row['snapshot_id'].encode()).hexdigest()+'.json'))
    manifest={'baseline':str(baseline),'state':'prepared_offline','eligible_snapshots':len(rows),'selected_snapshot_ids':[r['snapshot_id'] for r in selected],
              'selected_count':len(selected),'excluded':excluded,'e2e_case_id':chosen['id'],
              'e2e_baseline_seconds':chosen['elapsed_seconds'],'scope':'judgment audit plus one real E2E; not full 292-case JEV evaluation'}
    write_event(manifest,output/'study.json');return manifest


def audit(output: Path) -> dict:
    require_jev();confidence_threshold()
    snapshot(Path(os.environ['ACE_EXPERIMENT_BUDGET_FILE']))
    manifest=json.loads((output/'study.json').read_text())
    if manifest.get('state')!='prepared_offline':raise ValueError('Study is not a fresh frozen prepared selection')
    rows={json.loads(p.read_text())['snapshot_id']:json.loads(p.read_text()) for p in (output/'inputs').glob('*.json')}
    manifest['state']='audit_running';write_event(manifest,output/'study.json')
    os.environ.update(ACE_EXPERIMENT_TELEMETRY=str((output/'audit-calls').resolve()),ACE_EXPERIMENT_MODE='jev',
                      ACE_EXPERIMENT_PHASE='judgment_audit',ACE_EXPERIMENT_CALL_KIND='snapshot_decision')
    results=[]
    try:
        for snapshot_id in manifest['selected_snapshot_ids']:
            row=rows[snapshot_id];os.environ['ACE_EXPERIMENT_CASE_ID']=row['case_id']
            record={k:v for k,v in row.items() if k!='state'}
            try:
                result=decide(row['state'],QUESTIONS);answer=result['answers']['effectiveness']
                used=answer['choice']!='uncertain' and answer['confidence']>=confidence_threshold()
                record.update(status='ok',jev_answer=answer,jev_usage=result['usage'],call_id=result['call_id'],decision_accepted=used,
                              would_fallback=not used,actual_primary_fallback_calls=0,
                              primary_proxy_agreement=answer['choice']==row['primary_narrative_label'] if row['primary_narrative_label'] else None,
                              all_pass_oracle_agreement=answer['choice']=='resolved' if row['official_evaluator_passed'] else None)
            except BudgetDenied:
                manifest['state']='budget_exhausted';break
            except (DecisionError,ValueError) as exc:record.update(status='decision_error',error_type=type(exc).__name__,actual_primary_fallback_calls=0)
            results.append(record);write_event({'results':results},output/'audit.partial.json')
        if manifest['state']!='budget_exhausted':manifest['state']='audit_completed'
    finally:
        for name in ('ACE_EXPERIMENT_TELEMETRY','ACE_EXPERIMENT_CASE_ID','ACE_EXPERIMENT_PHASE','ACE_EXPERIMENT_CALL_KIND'):os.environ.pop(name,None)
        manifest['budget']=snapshot(Path(os.environ['ACE_EXPERIMENT_BUDGET_FILE']))
        write_event(manifest,output/'study.json');write_event({'manifest':manifest,'results':results},output/'audit.json')
    return manifest


def e2e(output: Path) -> Path:
    study=json.loads((output/'study.json').read_text())
    if study['state']!='audit_completed':raise ValueError('Complete bounded audit required before E2E')
    baseline=Path(study['baseline']);data=json.loads((baseline/'summary.json').read_text());conditions=data['manifest']['conditions']
    args=argparse.Namespace(mode='jev',baseline=baseline,id=[study['e2e_case_id']],limit=0,
                            attempts=conditions['attempts'],iterations=conditions['iterations'],workers=conditions['workers'],
                            llm_timeout=conditions['llm_timeout'],evaluator_timeout=conditions['evaluator_timeout'],case_timeout=conditions['case_timeout'])
    study['state']='e2e_running';write_event(study,output/'study.json')
    try:batch=run_batch(args)
    except Exception as exc:
        study.update(state='e2e_error',error_type=type(exc).__name__,budget=snapshot(Path(os.environ['ACE_EXPERIMENT_BUDGET_FILE'])))
        write_event(study,output/'study.json');raise
    projection=output/'baseline-projection';projection.mkdir()
    write_event(project_baseline(data,args.id),projection/'summary.json')
    study.update(state='e2e_executed',e2e_batch=str(batch),baseline_projection=str(projection),budget=snapshot(Path(os.environ['ACE_EXPERIMENT_BUDGET_FILE'])))
    write_event(study,output/'study.json');return batch


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['prepare','audit','e2e'])
    parser.add_argument('--baseline',type=Path);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--limit',type=int,default=48)
    args=parser.parse_args();load_config()
    if args.command=='prepare':result=prepare(args.baseline.resolve(),args.output.resolve(),args.limit)
    elif args.command=='audit':result=audit(args.output.resolve())
    else:result={'e2e_batch':str(e2e(args.output.resolve()))}
    print(json.dumps(result,indent=2))
