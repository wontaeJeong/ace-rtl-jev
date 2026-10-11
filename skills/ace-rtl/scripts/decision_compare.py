#!/usr/bin/env python3
"""Small frozen A(original)/B(fixed)/C(core) experiment, never a whole sweep."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'skills/ace-rtl/scripts'))
from ace_rtl_agent.decision.observations import validate_result, build_task_contract


def classify_native(summary, required_services=(), *, legacy_manifest_binding=False):
    if not summary or len(summary.get('results',[])) != 1:
        return {'reported_success':False,'verified_success':False,'status':'infra_error'}
    row=summary['results'][0]
    histories=[h for a in row.get('attempts',[]) for h in a.get('history',[])]
    def authoritative(h):
        result=h.get('result')
        if not isinstance(result,dict):return result
        if not isinstance(result.get('tests'),list):return result
        tests=[]
        for test in result.get('tests',[]):
            test=dict(test) if isinstance(test,dict) else test
            if isinstance(test,dict) and not (test.get('service') or test.get('service_id')):
                stem=Path(str(test.get('log') or '')).stem
                match=[s for s in required_services if stem==s or stem.endswith('_'+s)]
                if (not match and legacy_manifest_binding and len(required_services)==len(result['tests'])==1
                        and stem=='1' and isinstance(test.get('execution'),(int,float)) and test['execution']>=0):
                    # Original wrapper iterates the sole public compose service and
                    # writes reports/1.txt; this is explicit provenance adaptation.
                    match=list(required_services)
                if len(match)==1:
                    test['service']=match[0]
            tests.append(test)
        return {**result,'tests':tests}
    verified=any(not validate_result(authoritative(h),required_services) and
                 (authoritative(h) or {}).get('errors')==0 for h in histories)
    reported=row.get('passed') is True
    status='verified_pass' if verified else 'task_failed'
    if any(a.get('status') in ('infra_error','error') for a in row.get('attempts',[])) or summary.get('preflight_failed'):
        status='infra_error'
    elif any(t.get('result')==124 for h in histories for t in h.get('result',{}).get('tests',[])):
        status='evaluator_timeout'
    elif histories and all(validate_result(authoritative(h),required_services) for h in histories):
        status='invalid_evaluation'
    return {'reported_success':reported,'verified_success':verified,'status':status}


def run(args):
    from experiment_config import load_config, require_primary
    from inference_budget import snapshot
    load_config(args.env_file)
    if not os.environ.get('ACE_EXPERIMENT_BUDGET_FILE'):
        raise ValueError('explicit campaign admission file required')
    dataset=Path(args.dataset).resolve()
    rows=[json.loads(line) for line in dataset.open()]
    selected=[r for r in rows if r['id'] in args.id]
    if len(selected)!=len(set(args.id)) or not 1<=len(selected)<=4:
        raise ValueError('select 1..4 existing task IDs')
    if not 1<=args.iterations<=3:
        raise ValueError('comparison bounded to 1..3 iterations')
    model=require_primary()['LLM_MODEL']
    output=Path(args.output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    conditions={'attempts':1,'iterations':args.iterations,'workers':1,'llm_timeout':args.llm_timeout,
                'evaluator_timeout':args.evaluator_timeout,'case_timeout':args.case_timeout,
                'generator_model':model,'reflector_model':model,'coordinator_model':model}
    manifest={'conditions':conditions,'task_ids':args.id,'dataset_sha256':hashlib.sha256(dataset.read_bytes()).hexdigest(),
              'ace_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'reference_commit':None,'budget_before':snapshot(Path(os.environ['ACE_EXPERIMENT_BUDGET_FILE'])),
              'question_version':os.environ.get('ACE_RTL_QUESTION_SCHEMA_VERSION','jev-questions-1'),
              'extensions':[],'sampling_seed_guaranteed':False,
              'acceptance':'descriptive only: n<=4 insufficient for noninferiority; no automatic default change',
              'warmup_excluded':True}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2))
    results=[]
    for arm,mode in [('A','original'),('B','baseline_fixed'),('C','jev_core')]:
        workspace=Path(args.reference_workspace).resolve() if arm=='A' else ROOT
        for row in selected:
            case=output/arm/row['id'];case.mkdir(parents=True)
            contract=build_task_contract(row,row['categories'][0])
            if arm=='A' and not (workspace/'skills/ace-rtl/scripts/ace_cvdp_native_runner.py').exists():
                results.append({'arm':arm,'id':row['id'],'status':'blocked','reason':'original source worktree missing',
                                'reported_success':False,'verified_success':False});continue
            if arm=='A':
                manifest['reference_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=workspace,text=True).strip()
            native_dataset=workspace/'datasets'/dataset.name
            if arm!='A':native_dataset=dataset
            env=os.environ.copy()
            env.update(ACE_RTL_LLM_SCRIPT=str(ROOT/'scripts/local_llm_adapter.py'),
                       ACE_EXPERIMENT_TELEMETRY=str(case/'calls'),ACE_EXPERIMENT_MODE='baseline',
                       ACE_RTL_DECISION_MODE='legacy' if arm=='A' else mode,ACE_RTL_STREAM='0',
                       CVDP_NATIVE_HARNESS='1',PYTHONNOUSERSITE='1',ACE_EXPERIMENT_CASE_ID=row['id'],
                       ACE_RTL_ATTEMPT_WALL_SECONDS=str(args.case_timeout),
                       PATH=str(ROOT/'.cvdp-native/bin')+os.pathsep+os.environ['PATH'])
            for name in ('ACE_RTL_ENABLE_BEAM','ACE_RTL_ENABLE_ADAPTIVE_SCHEDULING','ACE_RTL_ENABLE_MODEL_ROUTING',
                         'ACE_RTL_ENABLE_LESSON_MEMORY','ACE_RTL_ENABLE_LEARNED_POLICY'):
                env[name]='false'
            native_output=workspace/'outputs'/f'comparison-{output.name}-{arm}-{row["id"]}'
            cmd=[str(ROOT/'.cvdp-native/bin/python'),str(workspace/'skills/ace-rtl/scripts/ace_cvdp_native_runner.py'),
                 '--workspace',str(workspace),'--dataset',str(native_dataset),'--cid',row['categories'][0],
                 '--id',row['id'],'--outputs-root',str(native_output),'--attempts','1','--max-iterations',str(args.iterations),
                 '--datapoint-workers','1','--llm-timeout',str(args.llm_timeout),'--evaluator-timeout',str(args.evaluator_timeout),
                 '--generator-model',model,'--reflector-model',model,'--coordinator-model',model]
            if arm!='A':cmd.extend(['--decision-mode',mode])
            started=time.monotonic()
            from run_experiments import terminate_tree
            with (case/'process.log').open('w') as handle:
                proc=subprocess.Popen(cmd,env=env,cwd=workspace,stdout=handle,stderr=subprocess.STDOUT,start_new_session=True)
                try:code=proc.wait(timeout=args.case_timeout)
                except subprocess.TimeoutExpired:terminate_tree(proc);code=None
            paths=list(native_output.glob('*/summary.json'))
            summary=json.loads(paths[0].read_text()) if len(paths)==1 else None
            record={'arm':arm,'id':row['id'],'mode':mode,'returncode':code,'wall_seconds':time.monotonic()-started,
                    'command':cmd,'native_summary':str(paths[0]) if paths else None,
                    'legacy_single_service_manifest_binding':arm=='A',
                    **classify_native(summary,contract.required_services,legacy_manifest_binding=arm=='A')}
            calls=[json.loads(p.read_text()) for p in case.rglob('calls/**/*.json')]
            # Native fixed arms keep their request artifacts outside scratch.
            for run_dir in native_output.glob('*'):
                calls.extend(json.loads(p.read_text()) for p in (run_dir/'datapoints'/row['id']/'calls').rglob('*.json'))
            from run_experiments import aggregate_calls
            compatible=[c for c in calls if c.get('provider') in ('primary','jev')]
            for call in compatible:
                u=call.get('usage')
                if isinstance(u,dict) and u.get('source')=='reported' and 'prompt_tokens' not in u:
                    u.update(prompt_tokens=u.get('input_tokens',0),completion_tokens=u.get('output_tokens',0))
            record['usage']=aggregate_calls(compatible)
            record['call_artifacts']=len(calls)
            (case/'result.json').write_text(json.dumps(record,indent=2))
            if summary:(case/'native_summary.json').write_text(json.dumps(summary,indent=2))
            results.append(record)
            (output/'summary.json').write_text(json.dumps({'manifest':manifest,'results':results},indent=2))
            print(arm,row['id'],record['status'],round(record['wall_seconds'],2),flush=True)
    manifest['budget_after']=snapshot(Path(os.environ['ACE_EXPERIMENT_BUDGET_FILE']))
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (output/'summary.json').write_text(json.dumps({'manifest':manifest,'results':results},indent=2))
    lines=['# Bounded A/B/C comparison','', '| Arm | Task | Verified | Status | Wall seconds |', '|---|---|---|---|---|']
    lines += [f'| {r["arm"]} | {r["id"]} | {r["verified_success"]} | {r["status"]} | {r.get("wall_seconds","unknown")} |' for r in results]
    lines += ['', 'Single stochastic samples do not establish performance improvement. Warmup separate; X disabled.',
              'No primary price receipt: primary monetary cost unknown. Replay is not E2E. Full request costs include failed/inflight reservations.']
    (output/'report.md').write_text('\n'.join(lines)+'\n')
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',required=True);parser.add_argument('--id',action='append',required=True)
    parser.add_argument('--reference-workspace',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--env-file',default=str(ROOT/'.env.local'))
    parser.add_argument('--iterations',type=int,default=2);parser.add_argument('--llm-timeout',type=int,default=60)
    parser.add_argument('--evaluator-timeout',type=int,default=60);parser.add_argument('--case-timeout',type=int,default=240)
    run(parser.parse_args())


if __name__=='__main__':main()
