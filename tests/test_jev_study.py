import importlib
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))


def study():return importlib.import_module('jev_study')


def test_exact_historical_hash_and_complete_usage_required():
    event={'provider':'primary','request_sha256':'abc','status':'ok','usage':{'source':'reported','total_tokens':10}}
    assert study().match_calls([event],'abc')[0]['usage']['total_tokens']==10
    assert study().match_calls([event],'ab') is None
    assert study().match_calls([event,{**event,'usage':None}],'abc') is None


def test_subset_projection_never_reuses_full_batch_wall_time():
    original={'manifest':{'state':'completed','case_ids':['a','b'],'cases_planned':2,'elapsed_seconds':100},
              'results':[{'id':'a','elapsed_seconds':20},{'id':'b','elapsed_seconds':30}]}
    projection=study().project_baseline(original,['a'])
    assert projection['manifest']['case_ids']==['a']
    assert projection['manifest']['elapsed_seconds'] is None
    assert projection['manifest']['timing_comparable'] is False
    assert len(projection['results'])==1
    assert original['manifest']['case_ids']==['a','b']
