from concurrent.futures import ThreadPoolExecutor
import pytest
from inference_budget import init_budget, reserve, settle, snapshot, BudgetDenied


def test_task_attempt_admission_is_atomic_and_does_not_reset_global_budget(tmp_path,monkeypatch):
    from inference_budget import init_scope_limits
    path=tmp_path/'scope.sqlite'
    init_budget(path,{'primary':{'max_calls':8,'max_tokens':100000},
                      'jev':{'max_calls':8,'max_tokens':100000,'max_usd':.1,'reserve_usd':.001}})
    init_scope_limits(path,{'task':{'primary':{'max_calls':1,'max_tokens':20000}},
                            'attempt':{'primary':{'max_calls':1,'max_tokens':20000}}})
    monkeypatch.setenv('ACE_EXPERIMENT_BUDGET_FILE',str(path))
    monkeypatch.setenv('ACE_RTL_TASK_ID','task-1');monkeypatch.setenv('ACE_RTL_ATTEMPT_ID','1')
    def admit():
        try:return reserve('primary','public',16)
        except BudgetDenied:return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts=list(pool.map(lambda _:admit(),range(2)))
    assert sum(r is not None for r in receipts)==1
    settle(next(r for r in receipts if r),{'source':'reported','total_tokens':10})
    assert snapshot(path)['primary']['calls']==1
    monkeypatch.setenv('ACE_RTL_ATTEMPT_ID','2')
    with pytest.raises(BudgetDenied):reserve('primary','public',16)
    monkeypatch.setenv('ACE_RTL_TASK_ID','task-2')
    assert reserve('primary','public',16)
    assert snapshot(path)['primary']['calls']==2
    with pytest.raises(ValueError):
        init_scope_limits(path,{'task':{'primary':{'max_calls':99,'max_tokens':20000}}})
