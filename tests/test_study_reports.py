import importlib
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))


def test_audit_actual_tokens_separate_hypothetical_fallback():
    rows=[{'status':'ok','historical_primary_tokens':10000,'jev_usage':{'source':'reported','total_tokens':1000,'provider_cost':0.00004,'cost_currency':'USD'},'decision_accepted':True,'would_fallback':False,'primary_proxy_agreement':True,'all_pass_oracle_agreement':None},
          {'status':'ok','historical_primary_tokens':20000,'jev_usage':{'source':'reported','total_tokens':2000,'provider_cost':0.00008,'cost_currency':'USD'},'decision_accepted':False,'would_fallback':True,'primary_proxy_agreement':False,'all_pass_oracle_agreement':None}]
    metrics=importlib.import_module('study_reports').audit_metrics({'manifest':{'state':'audit_completed','selected_count':2},'results':rows})
    assert metrics['historical_primary_tokens']==30000
    assert metrics['actual_jev_tokens']==3000
    assert metrics['accepted_point_token_reduction_percent']==90
    assert metrics['would_fallback_count']==1 and metrics['actual_primary_fallback_calls']==0
    assert metrics['hypothetical_tokens_with_historical_fallback']==23000


def test_partial_audit_never_claims_completed_point_savings():
    data={'manifest':{'state':'budget_exhausted','selected_count':2},'results':[]}
    metrics=importlib.import_module('study_reports').audit_metrics(data)
    assert metrics['complete'] is False and metrics['accepted_point_token_reduction_percent'] is None
