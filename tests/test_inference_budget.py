import concurrent.futures
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))


def budget():return importlib.import_module('inference_budget')


def limits(calls=2):
    return {'primary':{'max_calls':calls,'max_tokens':50000},
            'jev':{'max_calls':2,'max_tokens':10000,'max_usd':0.01,'reserve_usd':0.0015}}


def test_missing_budget_disables_inference(monkeypatch):
    monkeypatch.delenv('ACE_EXPERIMENT_BUDGET_FILE',raising=False)
    with pytest.raises(budget().BudgetDenied,match='NON_RETRYABLE'):
        budget().reserve('primary','hello',20)


def test_atomic_parallel_request_limit(tmp_path,monkeypatch):
    path=tmp_path/'budget.sqlite';budget().init_budget(path,limits(calls=3))
    monkeypatch.setenv('ACE_EXPERIMENT_BUDGET_FILE',str(path))
    def attempt():
        try:return budget().reserve('primary','abc',20)
        except budget().BudgetDenied:return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        tickets=list(pool.map(lambda _:attempt(),range(12)))
    assert len([t for t in tickets if t])==3
    assert budget().snapshot(path)['primary']['calls']==3


def test_unknown_usage_retains_reservation_and_reported_usage_reconciles(tmp_path,monkeypatch):
    path=tmp_path/'budget.sqlite';budget().init_budget(path,limits())
    monkeypatch.setenv('ACE_EXPERIMENT_BUDGET_FILE',str(path))
    first=budget().reserve('primary','abc',20);before=budget().snapshot(path)['primary']['token_charge']
    budget().settle(first,None)
    assert budget().snapshot(path)['primary']['token_charge']==before
    second=budget().reserve('primary','abc',20)
    budget().settle(second,{'source':'reported','total_tokens':11})
    assert budget().snapshot(path)['primary']['token_charge']==before+11


def test_actual_overshoot_closes_new_admission(tmp_path,monkeypatch):
    path=tmp_path/'budget.sqlite';budget().init_budget(path,limits())
    monkeypatch.setenv('ACE_EXPERIMENT_BUDGET_FILE',str(path))
    ticket=budget().reserve('primary','abc',20)
    budget().settle(ticket,{'source':'reported','total_tokens':20000})
    with pytest.raises(budget().BudgetDenied):budget().reserve('primary','abc',20)
    assert budget().snapshot(path)['closed'] is True


def test_existing_campaign_cannot_be_reset_or_reconfigured(tmp_path):
    path=tmp_path/'budget.sqlite';budget().init_budget(path,limits())
    with pytest.raises(ValueError,match='immutable'):budget().init_budget(path,limits(calls=3))


def test_jev_unknown_currency_keeps_exposure_and_usd_receipt_reconciles(tmp_path,monkeypatch):
    path=tmp_path/'budget.sqlite';budget().init_budget(path,limits())
    monkeypatch.setenv('ACE_EXPERIMENT_BUDGET_FILE',str(path))
    first=budget().reserve('jev','abc',128)
    budget().settle(first,{'source':'reported','total_tokens':357,'provider_cost':0.00001365})
    assert budget().snapshot(path)['jev']['usd_exposure']==0.0015
    second=budget().reserve('jev','abc',128)
    budget().settle(second,{'source':'reported','total_tokens':357,'provider_cost':0.00001365,'cost_currency':'USD'})
    assert budget().snapshot(path)['jev']['usd_exposure']==pytest.approx(0.00151365)
