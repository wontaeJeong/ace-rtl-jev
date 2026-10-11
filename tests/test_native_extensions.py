import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/ace-rtl/scripts'))


def test_native_routing_only_uses_explicit_aliases_and_maximum_risk():
    from ace_cvdp_native.extensions import route_roles
    from ace_rtl_agent.decision.settings import DecisionSettings
    from ace_rtl_agent.decision.types import DecisionRecord
    settings=DecisionSettings(mode='jev_extended',enabled_extensions=('model_routing',),
                 model_aliases={'local':'configured-local','strong':'configured-strong'})
    decision=DecisionRecord('d','o',answers={'risk_reflect_focused_reset':{'noul':.95},
                                           'risk_reflect_focused_interface':{'noul':.01}})
    route=route_roles(settings,decision,failures=0,default_model='configured-local')
    assert route['generator_model']=='configured-strong'
    assert route['max_output_tokens']==4096
    assert route_roles(DecisionSettings(),decision,failures=0,default_model='user-primary')['generator_model']=='user-primary'


def test_native_learned_policy_cannot_activate_fixture_artifact(tmp_path):
    import json
    from ace_cvdp_native.extensions import load_learned_policy
    path=tmp_path/'fixture.json'
    path.write_text(json.dumps({'production_ready':False,'artifact_version':'ace-offline-stump-1'}))
    with pytest.raises(ValueError,match='validated'):
        load_learned_policy(path,question_version='q',policy_version='p',model_version='m')
