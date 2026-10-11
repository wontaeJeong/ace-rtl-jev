#!/usr/bin/env python3
"""Observe a running batch; reap only its completed-case orphan simulators."""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import psutil

from local_llm_adapter import write_event


def finished_orphan_case(batch: Path, name: str, ppid: int, args: list[str]) -> str | None:
    if name != 'vvp' or ppid != 1:
        return None
    root=batch.resolve()
    for arg in args:
        try:
            path=Path(arg)
            if not path.is_absolute(): continue
            rel=path.resolve().relative_to(root)
        except (ValueError, OSError): continue
        if len(rel.parts)>=4 and rel.parts[0]=='cases' and rel.parts[2]=='native':
            case=rel.parts[1]
            if (root/'cases'/case/'result.json').is_file(): return case
            # A case may still be repairing while an earlier completed evaluator
            # has leaked vvp. Never touch the live iteration; require its real
            # evaluator-result artifact before treating a path as finished.
            for parent in path.resolve().parents:
                if parent == root: break
                if parent.name.startswith('iter_') and (parent/'real_evaluator_result.json').is_file():
                    return case
    return None


def scan_orphans(batch: Path) -> list[dict]:
    events=[];victims=[]
    for proc in psutil.process_iter(['pid','name','ppid']):
        try:
            case=finished_orphan_case(batch,proc.name(),proc.ppid(),proc.cmdline())
            if case:
                cpu=proc.cpu_times()
                events.append({'at_utc':datetime.now(timezone.utc).isoformat(), 'pid':proc.pid,'case':case,
                               'cpu_seconds':cpu.user+cpu.system,'action':'terminate_completed_evaluator_orphan'})
                proc.terminate();victims.append(proc)
        except psutil.Error:continue
    _,alive=psutil.wait_procs(victims,timeout=2)
    for proc in alive:
        try:proc.kill()
        except psutil.Error:pass
    psutil.wait_procs(alive,timeout=2)
    return events


def watch(batch: Path, parent_pid: int, interval: float) -> dict:
    batch=batch.resolve()
    manifest=json.loads((batch/'manifest.json').read_text())
    parent=psutil.Process(parent_pid)
    if not batch.name.endswith('-'+str(parent_pid)) or not any('run_experiments.py' in arg for arg in parent.cmdline()):
        raise ValueError('Parent PID does not match this batch runner')
    monitor=batch/'monitor';events=[]
    while True:
        new=scan_orphans(batch);events.extend(new)
        if new:write_event({'events':events},monitor/'orphan-events.json')
        results=[]
        for path in batch.glob('cases/*/result.json'):
            try:results.append(json.loads(path.read_text()))
            except json.JSONDecodeError:continue
        summary=batch/'summary.json'
        state={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'parent_alive':parent.is_running(),
               'completed':len(results),'planned':manifest['cases_planned'],
               'status_counts':dict(Counter(r['status'] for r in results)),
               'final_summary_exists':summary.exists(),'orphan_cleanup_events':len(events)}
        write_event(state,monitor/'snapshot.json')
        if summary.exists() or not state['parent_alive']:
            print(json.dumps(state,indent=2),flush=True)
            return state
        time.sleep(interval)


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch',type=Path,required=True);parser.add_argument('--parent-pid',type=int,required=True)
    parser.add_argument('--interval',type=float,default=30)
    args=parser.parse_args()
    if args.interval<=0:parser.error('interval must be positive')
    result=watch(args.batch,args.parent_pid,args.interval)
    return 0 if result['final_summary_exists'] else 2


if __name__=='__main__':raise SystemExit(main())
