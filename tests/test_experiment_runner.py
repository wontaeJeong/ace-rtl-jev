import importlib
import json
import sys
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
