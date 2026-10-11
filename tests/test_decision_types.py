import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/ace-rtl/scripts'))


def test_bundle_tracks_second_file_and_rejects_escape():
    from ace_rtl_agent.decision.types import CandidateBundle
    first = CandidateBundle.create({'rtl/a.sv': 'a', 'rtl/b.sv': 'b'}, episode_id='e1')
    second = CandidateBundle.create({'rtl/a.sv': 'a', 'rtl/b.sv': 'c'}, episode_id='e1', parent=first)
    assert second.changed_files == ('rtl/b.sv',)
    assert second.tested_hash != first.tested_hash
    assert second.parent_candidate_id == first.candidate_id
    with pytest.raises(ValueError):
        CandidateBundle.create({'../private.sv': 'bad'}, episode_id='e1')


def test_observation_is_frozen_and_unknown_metrics_remain_null():
    from dataclasses import FrozenInstanceError
    from ace_rtl_agent.decision.types import Observation
    observation = Observation('o1', 1, 't', 1, 'e1', 1, 'hash')
    assert observation.to_dict()['metrics'] == {}
    assert observation.evaluation_validity == 'unknown'
    with pytest.raises(FrozenInstanceError):
        observation.version = 2


def test_contracts_freeze_nested_maps_and_do_not_alias_caller_input():
    from ace_rtl_agent.decision.types import Observation
    original={'sanity':{'result':0}}
    observation=Observation('o',1,'t',1,'e',1,'hash',services=original)
    original['sanity']['result']=1
    assert observation.services['sanity']['result'] == 0
    with pytest.raises(TypeError):
        observation.services['sanity']['result']=1
    assert observation.to_dict()['services']['sanity']['result'] == 0


def test_immutable_contracts_survive_real_multiprocessing_pickle_transport():
    import pickle
    from ace_rtl_agent.decision.types import Observation
    observation=Observation('o',1,'t',1,'e',1,'hash',services={'direct':{'result':1}})
    received=pickle.loads(pickle.dumps({'history':[{'observation':observation.to_dict()}]}))
    assert received['history'][0]['observation']['services']['direct']['result']==1
    restored=pickle.loads(pickle.dumps(observation))
    with pytest.raises(TypeError):restored.services['direct']['result']=0
