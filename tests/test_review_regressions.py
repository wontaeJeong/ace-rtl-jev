import importlib
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))


@pytest.mark.parametrize('provider',['primary','jev'])
def test_redirect_post_is_not_an_unbudgeted_second_request(provider,tmp_path,monkeypatch):
    paths=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']));paths.append(self.path)
            self.send_response(307 if self.path.endswith(('completions','decision')) else 200)
            self.send_header('Location','/redirected');self.end_headers()
            payload=({'choices':[{'message':{'content':'ok'},'finish_reason':'stop'}],'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}
                     if provider=='primary' else {'answers':{'label':{'type':'choice','choice':'a','confidence':1,'probabilities':{'a':1,'b':0}}},'usage':{'input_tokens':1,'output_tokens':1}})
            self.wfile.write(json.dumps(payload).encode())
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    for k,v in {'LLM_BASE_URL':base+'/v1','LLM_API_KEY':'fixture-key','LLM_MODEL':'fixture','JEV_API_MODE':'systemone','JEV_AUTH_MODE':'none','JEV_ENDPOINT_URL':base+'/decision','JEV_MODEL':'fixture','ACE_EXPERIMENT_TELEMETRY':str(tmp_path)}.items():monkeypatch.setenv(k,v)
    try:
        with pytest.raises(RuntimeError,match='307'):
            if provider=='primary':importlib.import_module('local_llm_adapter').complete({'messages':[{'role':'user','content':'fixture'}],'max_tokens':10})
            else:importlib.import_module('systemone_adapter').decide('fixture',{'label':{'type':'choice','instructions':'pick','criteria':{'a':'one','b':'two'}}})
        assert len(paths)==1
    finally:server.shutdown();server.server_close();thread.join()


def test_invalid_jev_answer_retains_independent_usd_receipt_and_closes_budget(tmp_path,monkeypatch):
    from inference_budget import snapshot
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            self.send_response(200);self.end_headers();self.wfile.write(b'{"answers":{},"usage":{"cost":0.20}}')
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    for k,v in {'JEV_API_MODE':'systemone','JEV_AUTH_MODE':'none','JEV_ENDPOINT_URL':f'http://127.0.0.1:{server.server_port}/decision','JEV_MODEL':'fixture','JEV_COST_CURRENCY':'USD','ACE_EXPERIMENT_TELEMETRY':str(tmp_path)}.items():monkeypatch.setenv(k,v)
    try:
        with pytest.raises(RuntimeError):importlib.import_module('systemone_adapter').decide('fixture',{'label':{'type':'choice','instructions':'pick','criteria':{'a':'one','b':'two'}}})
        import os
        ledger=snapshot(Path(os.environ['ACE_EXPERIMENT_BUDGET_FILE']))
        assert ledger['closed'] is True and ledger['jev']['usd_exposure']==0.20
        event=json.loads(next(tmp_path.glob('*.json')).read_text())
        assert event['usage']['provider_cost']==0.20 and event['usage_unknown'] is True
    finally:server.shutdown();server.server_close();thread.join()


@pytest.mark.parametrize('text,want',[
    ('The fix did not solve the target error; no different error is reported.','persistent'),
    ('The target error was solved and no new errors were introduced.','resolved'),
    ('The target error remains and a new error was introduced.','regression'),
])
def test_primary_proxy_handles_negated_new_error(text,want):
    assert importlib.import_module('jev_study').primary_label(text)==want


def test_unexercised_hook_differences_are_not_claimed_as_jev_savings():
    from test_experiment_reports import batch
    module=importlib.import_module('experiment_reports')
    baseline,improved=batch('baseline',150,30),batch('jev',100,20)
    improved['results'][0]['metrics']['jev']=dict(improved['results'][1]['metrics']['jev'])
    improved['manifest']['requires_hook_coverage']=True
    assert module.compare(baseline,improved)['token_savings_percent'] is None
    assert 'not exercised' in module.render_markdown(baseline,improved).lower()


def test_unexercised_legacy_manifest_without_flag_also_has_no_savings():
    from test_experiment_reports import batch
    module=importlib.import_module('experiment_reports')
    baseline,improved=batch('baseline',150,30),batch('jev',100,20)
    improved['results'][0]['metrics']['jev']=dict(improved['results'][1]['metrics']['jev'])
    assert module.compare(baseline,improved)['token_savings_percent'] is None
