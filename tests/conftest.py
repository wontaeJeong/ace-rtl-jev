"""Unit HTTP fixtures get isolated, explicit budgets; never real model calls."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))


@pytest.fixture(autouse=True)
def isolated_fixture_budget(tmp_path,monkeypatch):
    from inference_budget import init_budget
    path=tmp_path/'fixture-budget.sqlite'
    init_budget(path,{'primary':{'max_calls':100,'max_tokens':10000000},
                      'jev':{'max_calls':100,'max_tokens':10000000,'max_usd':1,'reserve_usd':0.0015}})
    monkeypatch.setenv('ACE_EXPERIMENT_BUDGET_FILE',str(path))
    monkeypatch.setenv('JEV_COST_CURRENCY','USD')
