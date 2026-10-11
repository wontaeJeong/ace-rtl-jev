#!/usr/bin/env python3
"""Generate honest summaries from measured experiment JSON, not guessed outcomes."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def case_status(case: dict) -> str:
    # Preserve original raw JSON; normalize only the reporting view using real
    # service return codes. Upstream sometimes labels service timeouts functional.
    status=case['status']
    if status in ('success','environment_error','execution_error','timeout'):
        return status
    result=case.get('result') or {}
    for attempt in result.get('attempts', []):
        for iteration in attempt.get('history', []):
            for service in (iteration.get('result') or {}).get('tests', []):
                if service.get('result')==124 or 'native harness timeout' in str(service.get('error_msg','')).lower():
                    return 'timeout'
    return status


def batch_metrics(batch: dict) -> dict:
    manifest, results = batch['manifest'], batch['results']
    ids = [r['id'] for r in results]
    complete = (manifest.get('state') == 'completed' and len(ids) == len(set(ids))
                and sorted(ids) == sorted(manifest['case_ids']))
    n = len(results)
    status = Counter(case_status(r) for r in results)
    provider_metrics = {}
    for provider in ('primary', 'jev'):
        values = [r['metrics'][provider] for r in results]
        fields = ('calls', 'error_calls', 'fallback_calls', 'unknown_usage_calls',
                  'reported_prompt_tokens', 'reported_completion_tokens',
                  'reported_total_tokens', 'estimated_total_tokens', 'latency_seconds')
        totals = {k: sum(v.get(k, 0) for v in values) for k in fields}
        totals['average_latency_seconds'] = (totals['latency_seconds'] / totals['calls']
                                            if totals['calls'] and all(v.get('latency_complete', False) for v in values) else None)
        provider_metrics[provider] = totals
    reported = sum(v['reported_total_tokens'] for v in provider_metrics.values())
    estimated = sum(v['estimated_total_tokens'] for v in provider_metrics.values())
    token_complete = complete and all(r['metrics']['total_tokens_complete'] for r in results)
    calls = sum(v['calls'] for v in provider_metrics.values())
    latency = sum(v['latency_seconds'] for v in provider_metrics.values())
    durations=[r.get('elapsed_seconds') for r in results]
    timing_complete=all(isinstance(d,(int,float)) for d in durations)
    return {'complete':complete, 'case_count':n, 'planned_case_count':len(manifest['case_ids']),
            'success_count':status['success'], 'success_rate':status['success']/n if complete and n else None,
            'status_counts':dict(status), 'failure_error_count':n-status['success'],
            'reported_total_tokens':reported, 'estimated_total_tokens':estimated,
            'total_tokens':reported+estimated if token_complete else None,
            'average_tokens':(reported+estimated)/n if token_complete and n else None,
            'batch_wall_seconds':manifest.get('elapsed_seconds') if complete else None,
            'sum_case_seconds':sum(durations) if timing_complete else None,
            'average_case_seconds':sum(durations)/n if timing_complete and n else None,
            'unknown_case_runtime_count':sum(d is None for d in durations),
            'average_call_latency_seconds':latency/calls if calls and all(r['metrics'][p].get('latency_complete', False) for r in results for p in ('primary','jev')) else None,
            **provider_metrics}


def compare(baseline: dict, improved: dict | None) -> dict:
    if improved is None:
        return {'token_savings_percent':None, 'wall_time_savings_percent':None, 'success_rate_change_points':None}
    b, j = baseline['manifest'], improved['manifest']
    for field in ('case_ids', 'conditions'):
        left, right = b[field], j[field]
        if field == 'case_ids': left, right = sorted(left), sorted(right)
        if left != right: raise ValueError(f'Unmatched experimental {field}')
    for field in ('dataset_sha256', 'cvdp_commit', 'configuration'):
        left, right = b['environment'].get(field), j['environment'].get(field)
        if field == 'configuration':
            # Baseline does not call JEV; updating only the approved decision
            # provider is not a change to the common primary model conditions.
            left = {k:v for k,v in (left or {}).items() if not k.startswith('jev_')}
            right = {k:v for k,v in (right or {}).items() if not k.startswith('jev_')}
        if left != right:
            raise ValueError(f'Unmatched experimental environment {field}')
    bm, jm = batch_metrics(baseline), batch_metrics(improved)
    def saving(key):
        x,y=bm[key],jm[key]
        return (x-y)/x*100 if bm['complete'] and jm['complete'] and x is not None and y is not None and x>0 else None
    # Estimates are disclosed but cannot support a claimed measured token saving.
    tokens = saving('total_tokens') if bm['estimated_total_tokens']==0 and jm['estimated_total_tokens']==0 else None
    return {'token_savings_percent':tokens, 'wall_time_savings_percent':saving('batch_wall_seconds'),
            'success_rate_change_points':(jm['success_rate']-bm['success_rate'])*100 if bm['success_rate'] is not None and jm['success_rate'] is not None else None}


def render_markdown(baseline: dict, improved: dict | None) -> str:
    bm, jm = batch_metrics(baseline), batch_metrics(improved) if improved else None
    changes=compare(baseline, improved)
    def fmt(value):
        if value is None: return 'Unavailable'
        return f'{value:.3f}' if isinstance(value,float) else str(value)
    fields=[('평가 케이스 수','case_count'),('성공 케이스 수','success_count'),('성공률 (0–1)','success_rate'),
            ('총 토큰 (reported + disclosed estimates)','total_tokens'),('평균 토큰/케이스','average_tokens'),
            ('총 실행 시간 (batch wall s)','batch_wall_seconds'),('평균 실행 시간/케이스 (s)','average_case_seconds'),
            ('주력 LLM 호출 수',('primary','calls')),('JEV-like 호출 수',('jev','calls')),
            ('평균 호출 지연 시간 (s)','average_call_latency_seconds'),('실패 및 오류 건수','failure_error_count')]
    lines=['# ACE-RTL measured comparison', '',
           f"Baseline state: `{baseline['manifest'].get('state')}`; coverage {bm['case_count']}/{bm['planned_case_count']}.",
           f"Improved state: `{improved['manifest'].get('state')}`." if improved else 'Improved state: **Not run**.', '',
           '| 지표 | Baseline | JEV-like | 변화 (JEV − baseline) |','|---|---:|---:|---:|']
    for label,key in fields:
        x=bm[key[0]][key[1]] if isinstance(key,tuple) else bm[key]
        y=(jm[key[0]][key[1]] if isinstance(key,tuple) else jm[key]) if jm else None
        delta=y-x if bm['complete'] and jm and jm['complete'] and x is not None and y is not None else None
        lines.append(f'| {label} | {fmt(x)} | {fmt(y) if jm else "Not run"} | {fmt(delta)} |')
    lines += ['', f"Measured token savings (%): {fmt(changes['token_savings_percent'])}.",
              f"Measured batch wall-time savings (%): {fmt(changes['wall_time_savings_percent'])}.",
              '', '## Conditions and measurement', '', '```json',json.dumps(baseline['manifest']['conditions'],indent=2),'```',
              '', 'Warmup is actual inference, excluded from evaluation metrics. Total wall time is concurrent batch wall time; average case time includes subprocess/evaluator/repair overhead. Retry calls, JEV calls and primary fallback calls count toward totals.',
              'An inflight/error call with unavailable usage is not assigned fictional zero cost. Unknown billing suppresses token savings. Char/4 estimates are labeled and cannot establish measured token savings. Provider caches/load time may be opaque; no custom cache was added.',
              '', '## Provider accounting', '', '| Mode/provider | Calls | Reported input | Reported output | Reported total | Estimated total | Unknown usage calls | Fallback calls | Mean latency (s) |',
              '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for mode,metrics in [('baseline',bm),('jev',jm)]:
        if metrics:
            for provider in ('primary','jev'):
                v=metrics[provider]
                lines.append('| '+mode+'/'+provider+' | '+' | '.join(fmt(v[k]) for k in ('calls','reported_prompt_tokens','reported_completion_tokens','reported_total_tokens','estimated_total_tokens','unknown_usage_calls','fallback_calls','average_latency_seconds'))+' |')
    lines += ['', '## Case outcomes', '', '| Case | Baseline | JEV-like | Baseline s | JEV s |', '|---|---|---|---:|---:|']
    bi={r['id']:r for r in baseline['results']};ji={r['id']:r for r in improved['results']} if improved else {}
    for case_id in baseline['manifest']['case_ids']:
        x,y=bi.get(case_id),ji.get(case_id)
        lines.append(f'| `{case_id}` | {case_status(x) if x else "Not evaluated"} | {case_status(y) if y else "Not run"} | {fmt(x["elapsed_seconds"] if x else None)} | {fmt(y["elapsed_seconds"] if y else None)} |')
    lines += ['', '## Limitations', '', 'One bounded non-agentic no-commercial native cohort, not all CVDP workflows or original default budgets. Commercial rows are explicitly excluded by actual tool requirements. API stochasticity and remote latency remain uncontrolled; single-run differences are descriptive, not statistically established effects. Repetitions/ablation must be reported only when actually executed. See environment and opportunities documents for provenance, integrity rules and remaining work.', '']
    return '\n'.join(lines)


def load_batch(path: Path) -> dict:
    if (path/'summary.json').exists(): return json.loads((path/'summary.json').read_text())
    manifest=json.loads((path/'manifest.json').read_text())
    partial=path/'summary.partial.json'
    return {'manifest':manifest,'results':json.loads(partial.read_text())['results'] if partial.exists() else []}


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--improved',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();baseline=load_batch(args.baseline)
    improved=load_batch(args.improved) if args.improved else None
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'comparison.md').write_text(render_markdown(baseline,improved))
    payload={'baseline':batch_metrics(baseline),'jev':batch_metrics(improved) if improved else None,'changes':compare(baseline,improved)}
    (args.output/'metrics.json').write_text(json.dumps(payload,indent=2))
    with (args.output/'cases.csv').open('w') as f:
        fields=['mode','id','status','elapsed_seconds','reported_total_tokens','estimated_total_tokens','unknown_usage_calls']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for batch in (baseline,improved):
            if batch:
                for case in batch['results']:
                    metrics=case['metrics']
                    writer.writerow({'mode':batch['manifest']['mode'],'id':case['id'],'status':case_status(case),'elapsed_seconds':case['elapsed_seconds'],
                                     **{k:sum(metrics[p][k] for p in ('primary','jev')) for k in fields[4:]}})
    print(f'Reports saved: {args.output}')


if __name__=='__main__':main()
