import importlib
import json
import logging
import sys
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'skills/ace-rtl/scripts'))
from ace_rtl_agent.focused_guidance import FocusedGuidanceMixin


class PrimaryFixture:
    def __init__(self):self.calls=[]
    def call_llm(self,prompt,**kwargs):
        import os
        self.calls.append({'prompt':prompt,'fallback':os.environ.get('ACE_EXPERIMENT_FALLBACK'),'reason':os.environ.get('ACE_EXPERIMENT_FALLBACK_REASON')})
        return '### IMPLEMENTATION CHANGES\nChanged public code\n### FIX EFFECTIVENESS\nThe target error remains.'


class DebuggerFixture(FocusedGuidanceMixin):
    def __init__(self):
        self.llm_client=PrimaryFixture();self.ace_rtl_stages=set();self.logger=logging.getLogger('fixture')


def test_baseline_bypasses_jev_and_preserves_primary_behavior(monkeypatch):
    monkeypatch.setenv('ACE_EXPERIMENT_MODE','baseline')
    obj=DebuggerFixture()
    assert obj.extract_implementation_changes('assign y=0;','assign y=a;','fix','mismatch','mismatch')==('Changed public code','The target error remains.')
    assert len(obj.llm_client.calls)==1 and obj.llm_client.calls[0]['fallback'] is None


def test_jev_no_change_does_not_call_either_model(monkeypatch):
    monkeypatch.setenv('ACE_EXPERIMENT_MODE','jev')
    obj=DebuggerFixture()
    assert obj.extract_implementation_changes('same','same','fix','mismatch','report')==('No code changes detected','No changes made')
    assert obj.llm_client.calls==[]


def test_jev_low_confidence_falls_back_and_restores_environment(monkeypatch,tmp_path):
    module=importlib.import_module('jev_retrospective')
    def uncertain(*args,**kwargs):raise module.DecisionFallback('low_confidence')
    monkeypatch.setattr(module,'judge_retrospective',uncertain)
    monkeypatch.setenv('ACE_EXPERIMENT_MODE','jev');monkeypatch.setenv('ACE_EXPERIMENT_TELEMETRY',str(tmp_path))
    obj=DebuggerFixture()
    assert obj.extract_implementation_changes('before','after','fix','error','report')[1]=='The target error remains.'
    assert obj.llm_client.calls[0]['fallback']=='1'
    assert obj.llm_client.calls[0]['reason']=='low_confidence'
    import os
    assert os.environ.get('ACE_EXPERIMENT_FALLBACK') is None
    events=[json.loads(p.read_text()) for p in tmp_path.glob('fallback-*.json')]
    assert events[0]['reason']=='low_confidence'


def test_effectiveness_labels_use_history_compatible_language():
    module=importlib.import_module('jev_retrospective')
    assert 'resolved' in module.effectiveness('resolved').lower()
    assert 'still present' in module.effectiveness('persistent').lower()
    assert 'new error' in module.effectiveness('regression').lower()
    assert 'different error' in module.effectiveness('changed').lower()


def test_bounded_public_state_is_finite_and_contains_no_hidden_sources():
    module=importlib.import_module('jev_retrospective')
    state=module.build_state('before\n'*5000,'after\n'*5000,'guide'*5000,'target'*5000,'mismatch'*5000)
    assert len(state)<=12000
    assert 'Generated-code diff' in state and 'Evaluator report' in state


def test_valid_http_decision_bypasses_primary_and_is_recorded(tmp_path,monkeypatch):
    module=importlib.import_module('jev_retrospective')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert body['questions']==module.QUESTIONS and isinstance(body['state'],str)
            answer={'type':'choice','choice':'persistent','confidence':0.99,'probabilities':{k:int(k=='persistent') for k in module.CRITERIA}}
            response={'answers':{'effectiveness':answer},'usage':{'input_tokens':100,'output_tokens':32,'cost':0.0000042}}
            self.send_response(200);self.end_headers();self.wfile.write(json.dumps(response).encode())
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    for key,value in {'ACE_EXPERIMENT_MODE':'jev','ACE_EXPERIMENT_TELEMETRY':str(tmp_path),'JEV_API_MODE':'systemone','JEV_AUTH_MODE':'none','JEV_MODEL':'fixture','JEV_ENDPOINT_URL':f'http://127.0.0.1:{server.server_port}/decision'}.items():monkeypatch.setenv(key,value)
    try:
        obj=DebuggerFixture();changes,effect=obj.extract_implementation_changes('assign y=0;','assign y=a;','fix','mismatch','still mismatch')
        assert 'delta' in changes and 'still present' in effect
        assert obj.llm_client.calls==[]
        event=json.loads(next(tmp_path.glob('*.json')).read_text())
        assert event['kind']=='retrospective_decision' and event['decision_used'] is True
        assert event['usage']['total_tokens']==132 and event['fallback'] is False
    finally:server.shutdown();server.server_close();thread.join()


@pytest.mark.parametrize('label,expected',[('resolved',True),('persistent',False),('regression',False),('changed',False)])
def test_mapped_effect_preserves_real_focus_history_semantics(label,expected):
    from ace_rtl_agent.focused_history import FocusedHistoryMixin
    class History(FocusedHistoryMixin):
        def __init__(self):self.fix_history=[];self.logger=logging.getLogger('history')
    history=History()
    history.record_attempt(iteration=2,focused_error='functional mismatch',error_reasoning='',guidance='fix',implementation_changes='delta',
                           fix_effectiveness=importlib.import_module('jev_retrospective').effectiveness(label),test_results='0/1',outcome='no_change',test_passed=False)
    assert history.error_solved is expected
