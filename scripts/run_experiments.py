#!/usr/bin/env python3
"""Measured per-case execution around the official ACE-RTL native runner."""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

from experiment_config import ROOT, load_config, require_primary, require_jev
from local_llm_adapter import complete, write_event
from inference_budget import BudgetDenied, snapshot

sys.path.insert(0, str(ROOT / 'skills/ace-rtl/scripts'))
from ace_cvdp_native.harness import required_native_tools_for_row

DATASET = ROOT / 'datasets/cvdp-benchmark-dataset/cvdp_v1.1.0_nonagentic_code_generation_no_commercial.jsonl'
OSS_TOOLS = {'iverilog', 'vvp', 'verilator', 'yosys'}


def inventory(rows: list[dict]) -> list[dict]:
    result = []
    for row in rows:
        tools = required_native_tools_for_row(row)
        unsupported = sorted(set(tools) - OSS_TOOLS)
        result.append({'id': row['id'], 'category': row['categories'][0],
                       'required_tools': tools, 'eligible': bool(tools) and not unsupported,
                       'exclusion_reason': 'requires non-open-source tools: ' + ', '.join(unsupported) if unsupported else ('no recognized simulator service' if not tools else None)})
    return result


def classify_result(summary: dict | None, returncode: int | None) -> str:
    if returncode is None:
        return 'timeout'
    if not summary or len(summary.get('results', [])) != 1:
        return 'execution_error'
    result = summary['results'][0]
    if result.get('passed') is True:
        return 'success'
    attempts = result.get('attempts', [])
    if summary.get('preflight_failed') or any(a.get('status') == 'infra_error' or (a.get('primary_failure') or {}).get('stage') == 'INFRA_SETUP' for a in attempts):
        return 'environment_error'
    stages = [h.get('primary_failure', {}).get('stage', '') for a in attempts for h in a.get('history', [])]
    service_timeouts=any(t.get('result')==124 for a in attempts for h in a.get('history',[]) for t in (h.get('result') or {}).get('tests',[]))
    if service_timeouts or any('TIMEOUT' in s for s in stages):
        return 'timeout'
    if returncode != 0 or any(a.get('status') == 'error' for a in attempts):
        return 'execution_error'
    return 'failure'


def aggregate_calls(calls: list[dict]) -> dict:
    result = {'total_tokens_complete': True}
    for provider in ('primary', 'jev'):
        events = [c for c in calls if c.get('provider') == provider]
        usage = [c.get('usage') for c in events]
        result[provider] = {
            'calls': len(events), 'error_calls': sum(c.get('status') != 'ok' for c in events),
            'fallback_calls': sum(bool(c.get('fallback')) for c in events),
            'unknown_usage_calls': sum(u is None or (c.get('usage_unknown') is True and u.get('source')!='reported') for c,u in zip(events,usage)),
            'reported_prompt_tokens': sum(u['prompt_tokens'] for u in usage if u and u['source'] == 'reported'),
            'reported_completion_tokens': sum(u['completion_tokens'] for u in usage if u and u['source'] == 'reported'),
            'reported_total_tokens': sum(u['total_tokens'] for u in usage if u and u['source'] == 'reported'),
            'estimated_total_tokens': sum(u['total_tokens'] for u in usage if u and u['source'] != 'reported'),
            'latency_seconds': sum(c.get('latency_seconds', 0) for c in events),
            'latency_complete': all('latency_seconds' in c for c in events),
            'reported_usd': (sum(u['provider_cost'] for u in usage if u and u.get('cost_currency')=='USD' and u.get('provider_cost') is not None)
                             if any(u and u.get('cost_currency')=='USD' and u.get('provider_cost') is not None for u in usage) else None),
        }
        if result[provider]['unknown_usage_calls']:
            result['total_tokens_complete'] = False
    return result


def git_commit(path: Path) -> str:
    return subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()


def preflight(output: Path) -> dict:
    primary = require_primary()
    jev = require_jev()
    rows = [json.loads(line) for line in DATASET.open()]
    cases = inventory(rows)
    tools = {tool: shutil.which(tool) for tool in sorted(OSS_TOOLS | {'make','git'})}
    report = {'platform': platform.platform(), 'python': sys.version,
              'ace_commit': git_commit(ROOT), 'cvdp_commit': git_commit(ROOT / 'external/cvdp_benchmark'),
              'dataset_sha256': hashlib.sha256(DATASET.read_bytes()).hexdigest(),
              'dataset_rows': len(cases), 'eligible_rows': sum(c['eligible'] for c in cases),
              'tools': tools, 'configuration': {'primary_model':primary['LLM_MODEL'], 'jev_model':jev['JEV_MODEL'],
              'jev_auth_mode':jev['JEV_AUTH_MODE'], 'token_parameter':os.environ.get('LLM_TOKEN_PARAMETER','max_tokens'),
              'sampling_mode':os.environ.get('LLM_SAMPLING_MODE','explicit'), 'request_timeout':os.environ.get('REQUEST_TIMEOUT','60')},
              'cases': cases, 'ok': all(tools.values())}
    write_event(report, output)
    return report


def terminate_tree(proc: subprocess.Popen) -> None:
    try:
        children = psutil.Process(proc.pid).children(recursive=True)
    except psutil.Error:
        children = []
    for child in children:
        try: child.terminate()
        except psutil.Error: pass
    try: os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError: pass
    _, alive = psutil.wait_procs(children, timeout=2)
    for child in alive:
        try: child.kill()
        except psutil.Error: pass
    try: proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try: os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        proc.wait()


def run_case(case: dict, batch: Path, args: argparse.Namespace) -> dict:
    case_dir = batch / 'cases' / case['id']
    case_dir.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.update(ACE_RTL_LLM_SCRIPT=str(ROOT / 'scripts/local_llm_adapter.py'),
               ACE_EXPERIMENT_TELEMETRY=str(case_dir / 'calls'), ACE_EXPERIMENT_CASE_ID=case['id'],
               ACE_EXPERIMENT_MODE=args.mode, ACE_EXPERIMENT_PHASE='evaluation',
               CVDP_NATIVE_HARNESS='1', PYTHONNOUSERSITE='1', ACE_RTL_STREAM='0',
               ACE_RTL_LLM_TIMEOUT=str(args.llm_timeout))
    model = require_primary()['LLM_MODEL']
    cmd = [str(ROOT / '.cvdp-native/bin/python'), str(ROOT / 'skills/ace-rtl/scripts/ace_cvdp_native_runner.py'),
           '--workspace', str(ROOT), '--cvdp-repo', str(ROOT / 'external/cvdp_benchmark'),
           '--dataset', str(DATASET), '--cid', case['category'], '--id', case['id'],
           '--outputs-root', str(case_dir / 'native'), '--attempts', str(args.attempts),
           '--max-iterations', str(args.iterations), '--datapoint-workers', '1',
           '--llm-timeout', str(args.llm_timeout), '--evaluator-timeout', str(args.evaluator_timeout),
           '--generator-model', model, '--reflector-model', model, '--coordinator-model', model]
    start = mark_case_started(case_dir)
    with (case_dir / 'process.log').open('w') as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, cwd=ROOT, start_new_session=True)
        try:
            code = proc.wait(timeout=args.case_timeout)
        except subprocess.TimeoutExpired:
            terminate_tree(proc);code = None
    elapsed=mark_case_finished(case_dir,start,code)
    summaries = list((case_dir / 'native').glob('*/summary.json'))
    summary = json.loads(summaries[0].read_text()) if len(summaries) == 1 else None
    calls = [json.loads(p.read_text()) for p in (case_dir / 'calls').glob('*.json')]
    record = {'id':case['id'], 'category':case['category'], 'mode':args.mode,
              'status':classify_result(summary, code), 'returncode':code,
              'elapsed_seconds':elapsed, 'metrics':aggregate_calls(calls),
              'native_summary':str(summaries[0].relative_to(batch)) if summaries else None,
              'result':summary['results'][0] if summary else None}
    if record['status']!='success' and any(c.get('event')=='budget_denied' for c in calls):record['status']='budget_exhausted'
    write_event(record, case_dir / 'result.json')
    print(f"{case['id']}: {record['status']} ({record['elapsed_seconds']:.1f}s)", flush=True)
    return record


def mark_case_started(case_dir: Path) -> float:
    started=time.perf_counter()
    write_event({'state':'running','started_at':datetime.now(timezone.utc).isoformat(),
                 'pid':os.getpid(),'monotonic_started':started},case_dir/'execution.json')
    return started


def validate_baseline_reference(path: Path, case_ids: list[str], conditions: dict, environment: dict) -> dict:
    summary_path=Path(path)/'summary.json'
    if not summary_path.is_file():raise ValueError('Completed baseline summary is required')
    data=json.loads(summary_path.read_text());manifest=data['manifest']
    if manifest.get('state')!='completed' or sorted(r['id'] for r in data['results'])!=sorted(manifest['case_ids']):
        raise ValueError('Baseline is incomplete')
    if not set(case_ids)<=set(manifest['case_ids']):raise ValueError('Cases do not match baseline cohort')
    if conditions!=manifest['conditions']:raise ValueError('Unmatched baseline conditions')
    for key in ('dataset_sha256','cvdp_commit'):
        if environment.get(key)!=manifest['environment'].get(key):raise ValueError('Unmatched baseline '+key)
    left=environment['configuration'];right=manifest['environment']['configuration']
    for key in ('primary_model','token_parameter','sampling_mode','request_timeout'):
        if left.get(key)!=right.get(key):raise ValueError('Unmatched primary configuration '+key)
    return manifest


def completion_state(results: list[dict]) -> str:
    return 'budget_exhausted' if any(r['status']=='budget_exhausted' for r in results) else 'completed'


def warm_models(batch: Path, manifest: dict, model: str) -> None:
    names=('ACE_EXPERIMENT_TELEMETRY','ACE_EXPERIMENT_PHASE','ACE_EXPERIMENT_MODE')
    previous={name:os.environ.get(name) for name in names}
    os.environ.update(ACE_EXPERIMENT_TELEMETRY=str(batch/'warmup'),ACE_EXPERIMENT_PHASE='warmup',ACE_EXPERIMENT_MODE=manifest['mode'])
    try:
        complete({'model':model,'messages':[{'role':'user','content':'Reply READY.'}],'max_tokens':256})
        if manifest['mode']=='jev':
            from systemone_adapter import decide
            decide('A compiler reports a syntax error.',{'failure_class':{'type':'choice','instructions':'Classify the failure.','criteria':{'compile':'Syntax or elaboration failure','functional':'Wrong simulated output'}}})
    except Exception as exc:
        manifest.update(state='budget_exhausted' if isinstance(exc,BudgetDenied) else 'warmup_error',error_type=type(exc).__name__,
                        budget_after=snapshot(Path(os.environ['ACE_EXPERIMENT_BUDGET_FILE'])))
        write_event(manifest,batch/'manifest.json');write_event({'manifest':manifest,'results':[]},batch/'summary.json')
        raise
    finally:
        for name,value in previous.items():
            if value is None:os.environ.pop(name,None)
            else:os.environ[name]=value


def mark_case_finished(case_dir: Path, started: float, returncode: int | None) -> float:
    elapsed=time.perf_counter()-started
    record=json.loads((case_dir/'execution.json').read_text())
    record.update(state='finished',finished_at=datetime.now(timezone.utc).isoformat(),
                  elapsed_seconds=elapsed,returncode=returncode)
    write_event(record,case_dir/'execution.json')
    return elapsed


def run_batch(args: argparse.Namespace) -> Path:
    budget_file=os.environ.get('ACE_EXPERIMENT_BUDGET_FILE')
    if not budget_file:raise BudgetDenied('explicit campaign file required before a new run')
    budget_before=snapshot(Path(budget_file))
    config = require_primary()
    require_jev()
    report = preflight(ROOT / 'experiments/preflight/environment.json')
    if not report['ok']:
        raise ValueError('Missing required tools: ' + ', '.join(k for k,v in report['tools'].items() if not v))
    cases = [c for c in report['cases'] if c['eligible'] and (not args.id or c['id'] in args.id)]
    if args.id and set(args.id) - {c['id'] for c in cases}:
        raise ValueError('Unknown or excluded requested case IDs')
    if args.limit: cases = cases[:args.limit]
    if not cases: raise ValueError('No eligible cases selected')
    conditions={k:getattr(args,k) for k in ('attempts','iterations','workers','llm_timeout','evaluator_timeout','case_timeout')}
    reference=None
    if args.mode=='jev':
        if not getattr(args,'baseline',None):raise ValueError('JEV requires --baseline completed batch')
        reference=validate_baseline_reference(Path(args.baseline),[c['id'] for c in cases],conditions,report)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    batch = ROOT / 'experiments/runs' / f'{args.mode}-{stamp}-{os.getpid()}'
    batch.mkdir(parents=True, exist_ok=False)
    manifest = {'mode':args.mode, 'pid':os.getpid(), 'started_at':datetime.now(timezone.utc).isoformat(),
                'case_ids':[c['id'] for c in cases], 'cases_planned':len(cases),
                'conditions':conditions,'budget_before':budget_before,
                'baseline_reference':str(args.baseline) if reference else None,
                'effective_case_workers':min(args.workers,len(cases)),'requires_hook_coverage':args.mode=='jev',
                'environment':{k:v for k,v in report.items() if k != 'cases'}, 'state':'running'}
    write_event(manifest, batch / 'manifest.json')
    warm_models(batch,manifest,config['LLM_MODEL'])
    start = time.perf_counter();results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(run_case,c,batch,args) for c in cases]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
            write_event({'results':sorted(results,key=lambda r:r['id'])}, batch / 'summary.partial.json')
    manifest.update(state=completion_state(results), elapsed_seconds=time.perf_counter()-start,
                    budget_after=snapshot(Path(budget_file)),
                    completed_at=datetime.now(timezone.utc).isoformat())
    write_event(manifest, batch / 'manifest.json')
    write_event({'manifest':manifest, 'results':sorted(results,key=lambda r:r['id'])}, batch / 'summary.json')
    with (batch / 'cases.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=['id','category','status','elapsed_seconds'],lineterminator='\n');writer.writeheader()
        writer.writerows({k:r[k] for k in writer.fieldnames} for r in sorted(results,key=lambda r:r['id']))
    print(f'BATCH_DIR={batch}', flush=True)
    return batch


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', default=str(ROOT / '.env.local'))
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('preflight')
    run=commands.add_parser('run')
    run.add_argument('--mode',choices=['baseline','jev'],default='baseline')
    run.add_argument('--baseline',type=Path)
    run.add_argument('--id',action='append');run.add_argument('--limit',type=int,default=0)
    run.add_argument('--attempts',type=int,default=1);run.add_argument('--iterations',type=int,default=5)
    run.add_argument('--workers',type=int,default=4);run.add_argument('--llm-timeout',type=int,default=90)
    run.add_argument('--evaluator-timeout',type=int,default=300);run.add_argument('--case-timeout',type=int,default=1800)
    args=parser.parse_args();load_config(args.env_file)
    if args.command=='preflight':
        report=preflight(ROOT / 'experiments/preflight/environment.json')
        print(json.dumps({k:v for k,v in report.items() if k not in ('cases','configuration')},indent=2))
        return 0 if report['ok'] else 2
    if any(getattr(args,k)<=0 for k in ('attempts','iterations','workers','llm_timeout','evaluator_timeout','case_timeout')) or args.limit<0:
        parser.error('Budgets must be positive; limit must be nonnegative')
    run_batch(args);return 0


if __name__=='__main__':
    try: raise SystemExit(main())
    except (ValueError, RuntimeError) as exc:
        print(str(exc),file=sys.stderr);raise SystemExit(2)
