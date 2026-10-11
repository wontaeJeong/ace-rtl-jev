import importlib
import json
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


def runner():
    return importlib.import_module('run_experiments')


def test_inventory_excludes_commercial_services_not_dataset_label():
    rows = [
        {'id':'a','categories':['cid003'],'harness':{'docker-compose.yml':'services:\n  icarus:\n    image: __OSS_SIM_IMAGE__\n'}},
        {'id':'b','categories':['cid007'],'harness':{'docker-compose.yml':'services:\n  xcelium:\n    image: __VERIF_EDA_IMAGE__\n'}},
    ]
    inventory = runner().inventory(rows)
    assert inventory[0]['eligible'] is True
    assert inventory[1]['eligible'] is False


def test_zero_exit_with_failed_summary_is_not_success():
    summary = {'results':[{'id':'a','passed':False,'attempts':[{'status':'failed','history':[{'primary_failure':{'stage':'FUNCTIONAL'}}]}]}]}
    assert runner().classify_result(summary, 0) == 'failure'


def test_infra_error_and_timeout_are_distinct():
    summary = {'results':[{'id':'a','passed':False,'attempts':[{'status':'infra_error'}]}]}
    assert runner().classify_result(summary, 0) == 'environment_error'
    assert runner().classify_result(None, None) == 'timeout'


def test_aggregate_unknown_usage_does_not_become_zero_cost():
    result = runner().aggregate_calls([
        {'provider':'primary','status':'ok','latency_seconds':1,'usage':{'source':'reported','prompt_tokens':2,'completion_tokens':3,'total_tokens':5}},
        {'provider':'primary','status':'inflight','usage':None},
    ])
    assert result['primary']['calls'] == 2
    assert result['primary']['reported_total_tokens'] == 5
    assert result['primary']['unknown_usage_calls'] == 1
    assert result['total_tokens_complete'] is False


def test_timeout_cleanup_terminates_spawned_descendants():
    import psutil
    code = 'import subprocess,sys,time; p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); print(p.pid,flush=True); time.sleep(60)'
    proc=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,text=True,start_new_session=True)
    child_pid=int(proc.stdout.readline())
    try:
        runner().terminate_tree(proc)
        assert proc.poll() is not None
        assert not psutil.pid_exists(child_pid) or psutil.Process(child_pid).status()==psutil.STATUS_ZOMBIE
    finally:
        if proc.poll() is None: proc.kill();proc.wait()
        proc.stdout.close()


def test_native_service_exit_124_classifies_as_timeout():
    summary={'results':[{'id':'a','passed':False,'attempts':[{'status':'failed','history':[{'primary_failure':{'stage':'CANDIDATE_FUNCTIONAL'},'result':{'tests':[{'result':124}]}}]}]}]}
    assert runner().classify_result(summary,0)=='timeout'


def test_case_timing_is_persisted_before_and_after_work(tmp_path):
    started=runner().mark_case_started(tmp_path)
    first=json.loads((tmp_path/'execution.json').read_text())
    assert first['state']=='running' and first['started_at']
    elapsed=runner().mark_case_finished(tmp_path,started,0)
    final=json.loads((tmp_path/'execution.json').read_text())
    assert elapsed>0 and final['elapsed_seconds']==elapsed
    assert final['state']=='finished' and final['returncode']==0
