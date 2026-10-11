import importlib
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


def module():
    return importlib.import_module('local_llm_adapter')


def test_missing_configuration_names_only(monkeypatch):
    config = importlib.import_module('experiment_config')
    for key in ('LLM_BASE_URL', 'LLM_API_KEY', 'LLM_MODEL'):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValueError) as err:
        config.require_primary()
    assert all(key in str(err.value) for key in ('LLM_BASE_URL','LLM_API_KEY','LLM_MODEL'))


def test_reported_tokens_and_estimates_are_separate():
    adapter = module()
    assert adapter.usage_metrics({'prompt_tokens': 3, 'completion_tokens': 4, 'total_tokens': 7}, 'abcd', 'efgh')['source'] == 'reported'
    usage = adapter.usage_metrics(None, 'abcdefgh', 'abcd')
    assert usage['source'] == 'estimated_chars_div_4'
    assert usage['prompt_tokens'] == 2 and usage['completion_tokens'] == 1


def test_primary_http_contract_and_telemetry(tmp_path, monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert self.path == '/v1/chat/completions'
            assert self.headers['Authorization'] == 'Bearer test-secret'
            assert body['model'] == 'test-model'
            assert body['max_completion_tokens'] == 20
            assert 'temperature' not in body and 'top_p' not in body and 'extra_body' not in body
            assert body['stream'] is False
            payload = {'choices':[{'message':{'content':'module example; endmodule'},'finish_reason':'stop'}], 'usage':{'prompt_tokens':5,'completion_tokens':6,'total_tokens':11}}
            self.send_response(200);self.end_headers();self.wfile.write(json.dumps(payload).encode())
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
    monkeypatch.setenv('LLM_BASE_URL', f'http://127.0.0.1:{server.server_port}/v1')
    monkeypatch.setenv('LLM_API_KEY', 'test-secret');monkeypatch.setenv('LLM_MODEL', 'test-model')
    monkeypatch.setenv('LLM_TOKEN_PARAMETER', 'max_completion_tokens')
    monkeypatch.setenv('LLM_SAMPLING_MODE', 'default')
    monkeypatch.setenv('ACE_EXPERIMENT_TELEMETRY', str(tmp_path))
    try:
        result = module().complete({'model':'test-model','messages':[{'role':'user','content':'Generate public RTL'}],'max_tokens':20,'extra_body':{'unsupported':True}})
        assert result['choices'][0]['message']['content'] == 'module example; endmodule'
        records = [json.loads(p.read_text()) for p in tmp_path.glob('*.json')]
        assert len(records) == 1 and records[0]['status'] == 'ok'
        assert records[0]['usage']['total_tokens'] == 11
        assert records[0]['latency_seconds'] > 0
        assert 'test-secret' not in json.dumps(records)
    finally:
        server.shutdown();server.server_close();thread.join()


def test_http_error_never_echoes_server_body(tmp_path, monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            self.send_response(401);self.end_headers();self.wfile.write(b'credential=test-secret')
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
    for key,value in {'LLM_BASE_URL':f'http://127.0.0.1:{server.server_port}/v1','LLM_API_KEY':'test-secret','LLM_MODEL':'test-model','ACE_EXPERIMENT_TELEMETRY':str(tmp_path)}.items():
        monkeypatch.setenv(key,value)
    try:
        with pytest.raises(RuntimeError,match='HTTP 401') as err:
            module().complete({'messages':[{'role':'user','content':'hi'}],'max_tokens':20})
        assert 'test-secret' not in str(err.value)
        record=json.loads(next(tmp_path.glob('*.json')).read_text())
        assert record['status']=='error' and record['usage'] is None
        assert record['usage_unknown'] is True
    finally:
        server.shutdown();server.server_close();thread.join()
