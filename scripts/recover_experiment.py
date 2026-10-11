#!/usr/bin/env python3
"""Recover bookkeeping from actual finished native evaluators, never rerun/fake cases."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from experiment_reports import case_status
from local_llm_adapter import write_event
from run_experiments import aggregate_calls


def recover_batch(batch: Path) -> dict:
    manifest=json.loads((batch/'manifest.json').read_text())
    records=[];recovered=[]
    for case_id in manifest['case_ids']:
        case=batch/'cases'/case_id
        result_path=case/'result.json'
        if result_path.exists():
            record=json.loads(result_path.read_text())
        else:
            summaries=list((case/'native').glob('*/summary.json'))
            if len(summaries)!=1:
                raise ValueError(f'Cannot recover {case_id}: expected one real native summary')
            native=json.loads(summaries[0].read_text())
            results=native.get('results',[])
            if len(results)!=1 or results[0].get('id')!=case_id:
                raise ValueError(f'Invalid real native summary for {case_id}')
            calls=[json.loads(p.read_text()) for p in (case/'calls').glob('*.json')]
            record={'id':case_id,'category':results[0].get('category',native.get('cid')),
                    'mode':manifest.get('mode','baseline'),'status':'success' if results[0].get('passed') is True else 'failure',
                    'returncode':None,'elapsed_seconds':None,'elapsed_seconds_source':'unavailable_after_parent_exit',
                    'metrics':aggregate_calls(calls),'native_summary':str(summaries[0].relative_to(batch)),
                    'result':results[0],'recovered_from_real_evaluator':True}
            record['status']=case_status(record)
            recovered.append((result_path,record))
        if record.get('id')!=case_id:raise ValueError('Mismatched case record during recovery')
        records.append(record)
    # Validate every case before writing anything. Missing work is a blocker,
    # not a case that can be invented or assigned a zero-cost failure.
    backup=batch/'manifest.before-recovery.json'
    if not backup.exists():write_event(manifest,backup)
    for path,record in recovered:write_event(record,path)
    manifest.update(state='completed',elapsed_seconds=None,timing_complete=False,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    recovery={'source':'existing real native summaries','recovered_case_ids':[r['id'] for _,r in recovered],
                              'missing_parent_exit_cause':'unknown; ephemeral shell log unavailable',
                              'batch_wall_time':'unavailable; not reconstructed or fabricated'})
    write_event(manifest,batch/'manifest.json')
    final={'manifest':manifest,'results':sorted(records,key=lambda r:r['id'])}
    write_event(final,batch/'summary.json')
    return final


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('batch',type=Path)
    final=recover_batch(parser.parse_args().batch)
    print(json.dumps({'evaluated_cases':len(final['results']),'recovery':final['manifest']['recovery']},indent=2))
