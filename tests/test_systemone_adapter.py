import importlib
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))

QUESTIONS={'label':{'type':'choice','instructions':'Classify failure.','criteria':{'compile':'Syntax error','functional':'Wrong output'}}}
RESPONSE={'model':'typesafe/jev-1.13-20260917','answers':{'label':{'type':'choice','choice':'compile','probabilities':{'compile':1,'functional':0},'confidence':1}},'usage':{'input_tokens':325,'output_tokens':32,'cost':0.00001365}}


def adapter():return importlib.import_module('systemone_adapter')


def test_confirmed_choice_schema_and_provider_usage():
    assert adapter().validate_answers(RESPONSE,QUESTIONS)['label']['choice']=='compile'
    usage=adapter().decision_usage(RESPONSE['usage'],'x','compile')
    assert usage['prompt_tokens']==325 and usage['completion_tokens']==32 and usage['total_tokens']==357
    assert usage['provider_cost']==0.00001365 and usage['source']=='reported'


@pytest.mark.parametrize('field,value',[('choice','invented'),('confidence',float('nan')),('confidence',True),('probabilities',{'compile':0.9,'functional':0.9}),('probabilities',{'compile':1})])
def test_invalid_decisions_are_rejected(field,value):
    payload=json.loads(json.dumps(RESPONSE));payload['answers']['label'][field]=value
    with pytest.raises(ValueError):adapter().validate_answers(payload,QUESTIONS)


def test_live_http_contract_uses_decisions_not_chat_and_records_jev_cost(tmp_path,monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert self.path=='/api/alpha/decisions'
            assert self.headers['Authorization']=='Bearer decision-test-secret'
            assert body['state']=='syntax error' and body['questions']==QUESTIONS
            assert 'messages' not in body
            self.send_response(200);self.end_headers();self.wfile.write(json.dumps(RESPONSE).encode())
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    values={'JEV_API_MODE':'systemone','JEV_AUTH_MODE':'bearer','JEV_ENDPOINT_URL':f'http://127.0.0.1:{server.server_port}/api/alpha/decisions','JEV_API_KEY':'decision-test-secret','JEV_MODEL':'typesafe/jev-1.13','ACE_EXPERIMENT_TELEMETRY':str(tmp_path)}
    for key,value in values.items():monkeypatch.setenv(key,value)
    try:
        result=adapter().decide('syntax error',QUESTIONS)
        assert result['answers']['label']['choice']=='compile'
        event=json.loads(next(tmp_path.glob('*.json')).read_text())
        assert event['provider']=='jev' and event['usage']['total_tokens']==357
        assert event['latency_seconds']>0 and 'decision-test-secret' not in json.dumps(event)
    finally:server.shutdown();server.server_close();thread.join()
