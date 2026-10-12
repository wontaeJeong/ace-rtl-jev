"""Runtime contracts: no real providers, durable artifacts and process races."""
import json
import multiprocessing
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/ace-rtl/scripts'
sys.path.insert(0, str(SCRIPTS))


def artifacts(root):
    from ace_rtl_agent.decision.types import CandidateBundle
    candidate = root / 'candidate'
    candidate.mkdir(parents=True, exist_ok=True)
    (candidate / 'top.sv').write_text('module top; endmodule\n')
    bundle = CandidateBundle.create({'top.sv': (candidate / 'top.sv').read_text()}, episode_id='e')
    manifest = root / 'manifest.json'
    manifest.write_text(json.dumps(bundle.to_dict()))
    evaluation = root / 'evaluation.json'
    evaluation.write_text(json.dumps({'task_id': 't', 'tested_hash': bundle.tested_hash,
        'evaluator_status': 'PASS', 'evaluation_validity': 'valid',
        'errors': 0, 'tests': [{'service': 'sim', 'execution_status': 'completed', 'result': 0}]}))
    return candidate, manifest, evaluation


def claim_worker(root, queue):
    from ace_cvdp_native.processes import try_claim_first_pass
    root = Path(root)
    queue.put(try_claim_first_pass(dp_root=root, task_id='t', attempt_index=1,
        iteration=1, candidate_path=root / 'candidate', manifest_path=root / 'manifest.json',
        evaluation_path=root / 'evaluation.json', required_services=('sim',)))


def test_claim_requires_authoritative_artifacts(tmp_path):
    from ace_cvdp_native.processes import try_claim_first_pass
    assert not try_claim_first_pass(dp_root=tmp_path, task_id='t', attempt_index=1,
                                   iteration=1, candidate_path=tmp_path / 'missing')
    assert not (tmp_path / 'first_pass_claim.json').exists()


def test_claim_exclusive_and_revalidated(tmp_path):
    from ace_cvdp_native.processes import read_first_pass_claim
    candidate, manifest, evaluation = artifacts(tmp_path)
    ctx = multiprocessing.get_context('spawn')
    queue = ctx.Queue()
    workers = [ctx.Process(target=claim_worker, args=(str(tmp_path), queue)) for _ in range(5)]
    for worker in workers:
        worker.start()
    answers = [queue.get(timeout=20) for _ in workers]
    for worker in workers:
        worker.join(20)
        assert worker.exitcode == 0
    assert answers.count(True) == 1
    assert read_first_pass_claim(tmp_path)['tested_hash']
    (candidate / 'top.sv').write_text('tampered')
    assert read_first_pass_claim(tmp_path) is None


@pytest.mark.parametrize('partial', ['{', '[]', '{"attempt":1}', 'null'])
def test_partial_claim_recovers(tmp_path, partial):
    from ace_cvdp_native.processes import read_first_pass_claim
    artifacts(tmp_path)
    (tmp_path / 'first_pass_claim.json').write_text(partial)
    assert read_first_pass_claim(tmp_path) is None
    queue = multiprocessing.get_context('spawn').Queue()
    claim_worker(str(tmp_path), queue)
    assert queue.get(timeout=5) is True
    assert read_first_pass_claim(tmp_path) is not None


def test_invalid_evaluation_cannot_claim(tmp_path):
    from ace_cvdp_native.processes import try_claim_first_pass
    candidate, manifest, evaluation = artifacts(tmp_path)
    result = json.loads(evaluation.read_text())
    result['tests'][0]['result'] = 1
    evaluation.write_text(json.dumps(result))
    assert not try_claim_first_pass(dp_root=tmp_path, task_id='t', attempt_index=1,
        iteration=1, candidate_path=candidate, manifest_path=manifest,
        evaluation_path=evaluation, required_services=('sim',))


def test_cleanup_retains_audit(tmp_path):
    from ace_cvdp_native.processes import cleanup_attempt_root
    root = tmp_path / 'attempt'
    for name in ('candidates', 'calls', 'results', 'scratch', 'build'):
        (root / name).mkdir(parents=True)
        (root / name / 'data').write_text('audit')
    cleanup_attempt_root(root, tmp_path)
    assert all((root / name / 'data').exists() for name in ('candidates', 'calls', 'results'))
    assert not (root / 'scratch').exists()
    assert not (root / 'build').exists()


def test_deadline_remaining_and_env(monkeypatch):
    from ace_rtl_agent.decision.budget import Deadline
    now = [10.0]
    deadline = Deadline(5, clock=lambda: now[0])
    assert deadline.timeout(30) == 5
    now[0] = 12
    assert deadline.remaining() == 3
    now[0] = 16
    assert deadline.expired
    with pytest.raises(TimeoutError):
        deadline.timeout(1)
    monkeypatch.setenv('ACE_RTL_DEADLINE_MONOTONIC', str(time.monotonic() - 1))
    assert Deadline.from_env().expired


def test_ledger_sanitizes_and_process_files(tmp_path, monkeypatch):
    from ace_rtl_agent.decision.ledger import EventLedger
    monkeypatch.setenv('NVIDIA_API_KEY', 'secret-token')
    ledger = EventLedger(tmp_path, 1)
    ledger.append('call_started', authorization='Bearer secret-token',
                  detail='secret-token', nested={'api_key': 'secret-token'})
    ledger.append('call_completed', usage={'source': 'unknown'})
    files = list(tmp_path.glob('*.jsonl'))
    assert len(files) == 1
    text = files[0].read_text()
    assert 'secret-token' not in text
    rows = [json.loads(line) for line in text.splitlines()]
    assert [row['kind'] for row in rows] == ['call_started', 'call_completed']


def test_cache_seed_and_policy_separation(tmp_path):
    from ace_rtl_agent.decision.cache import EvaluationCache
    candidate, manifest, evaluation = artifacts(tmp_path)
    result = {'evaluation_path': str(evaluation), 'manifest_path': str(manifest),
              'candidate_path': str(candidate), 'required_services': ['sim']}
    digest = json.loads(manifest.read_text())['tested_hash']
    cache = EvaluationCache(tmp_path / 'cache')
    context = dict(deterministic=True, seed=1, tool_hash='tool', harness_hash='h',
                   task_hash='task', config_hash='config', policy_version='p1')
    assert cache.put(digest, context, result)
    assert cache.get(digest, context) == result
    assert cache.get(digest, dict(context, seed=2)) is None
    assert cache.get(digest, dict(context, deterministic=False)) is None
    assert cache.get(digest, dict(context, seed=None)) is None
    assert cache.get(digest, dict(context, policy_version='p2')) is None
    evaluation.write_text('{}')
    assert cache.get(digest, context) is None


def test_retry_classification_validation():
    from llm_call import transient_error
    assert not transient_error(RuntimeError('HTTP 401: timeout'))
    assert not transient_error(RuntimeError('HTTP 403: rate limit'))
    assert not transient_error(ValueError('context window too many tokens'))
    assert transient_error(RuntimeError('HTTP 429: overloaded'))
    assert transient_error(RuntimeError('HTTP 503: unavailable'))


def test_backend_adapter_timeout_usage_and_admission(tmp_path, monkeypatch):
    from ace_rtl_agent.llm_backend import LLMBackend
    from inference_budget import snapshot
    script = tmp_path / 'adapter.py'
    script.write_text('import json,sys\njson.load(sys.stdin)\nprint(json.dumps({"content":"ok", "usage":{"total_tokens":7}}))\n')
    monkeypatch.setenv('ACE_RTL_LLM_SCRIPT', str(script))
    monkeypatch.setenv('ACE_RTL_EVENT_ROOT', str(tmp_path / 'events'))
    backend = LLMBackend('custom')
    envelope = backend.complete_messages([{'role': 'user', 'content': 'p'}], timeout=1)
    assert envelope['usage']['total_tokens'] == 7
    assert envelope['usage']['source'] == 'reported'
    assert snapshot(Path(__import__('os').environ['ACE_EXPERIMENT_BUDGET_FILE']))['primary']['calls'] == 1
    assert backend.prompt('p', timeout=1) == 'ok'


def test_retry_shares_deadline(tmp_path, monkeypatch):
    from llm_call import call_with_retries
    script = tmp_path / 'slow.py'
    script.write_text('import time\ntime.sleep(2)\n')
    monkeypatch.setenv('ACE_RTL_LLM_SCRIPT', str(script))
    monkeypatch.setenv('ACE_RTL_DEADLINE_MONOTONIC', str(time.monotonic() + .15))
    start = time.monotonic()
    with pytest.raises((RuntimeError, TimeoutError)):
        call_with_retries(provider='nvidia', model='custom', messages=[{'role': 'user', 'content': 'p'}],
            temperature=.2, max_tokens=10, max_retries=3, initial_backoff=.01, shrink_chars=100)
    assert time.monotonic() - start < 1


def test_local_adapter_deadline_alias_and_unknown_usage(tmp_path, monkeypatch):
    import local_llm_adapter as adapter
    from inference_budget import snapshot
    import os
    for key, value in dict(LLM_BASE_URL='http://localhost/v1', LLM_API_KEY='secret',
                           LLM_MODEL='default', ACE_RTL_MODEL_ALIASES='{"reflector":"allowed"}',
                           ACE_EXPERIMENT_TELEMETRY=str(tmp_path / 'telemetry')).items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv('ACE_RTL_DEADLINE_MONOTONIC', str(time.monotonic() + .3))
    captured = {}
    class Response:
        status_code = 200
        def json(self):
            return {'choices': [{'message': {'content': 'ok'}}]}
    def post(*args, **kwargs):
        captured.update(kwargs)
        return Response()
    monkeypatch.setattr(adapter.requests, 'post', post)
    result = adapter.complete({'model': 'allowed', 'messages': [{'role': 'user', 'content': 'p'}], 'max_tokens': 10})
    assert result['choices'][0]['message']['content'] == 'ok'
    assert captured['json']['model'] == 'allowed'
    assert 0 < captured['timeout'] <= .3
    assert os.environ['LLM_MODEL'] == 'default'
    record = json.loads(next((tmp_path / 'telemetry').glob('*.json')).read_text())
    assert record['usage_unknown'] is True
    assert record['usage']['source'] == 'estimated_chars_div_4'
    with pytest.raises(ValueError, match='model'):
        adapter.complete({'model': 'reflector', 'messages': [{'role': 'user', 'content': 'p'}]})
    with pytest.raises(ValueError, match='model'):
        adapter.complete({'model': 'unconfigured', 'messages': [{'role': 'user', 'content': 'p'}]})
    calls = snapshot(Path(os.environ['ACE_EXPERIMENT_BUDGET_FILE']))['primary']['calls']
    monkeypatch.setenv('ACE_RTL_DEADLINE_MONOTONIC', str(time.monotonic() - 1))
    with pytest.raises(RuntimeError, match='NON_RETRYABLE'):
        adapter.complete({'messages': [{'role': 'user', 'content': 'p'}], 'max_tokens': 10})
    assert snapshot(Path(os.environ['ACE_EXPERIMENT_BUDGET_FILE']))['primary']['calls'] == calls


def test_managed_adapter_does_not_double_reserve(tmp_path, monkeypatch):
    from llm_call import call_adapter_script
    from inference_budget import snapshot
    import os
    script = tmp_path / 'managed.py'
    script.write_text('import sys,json\nsys.path.insert(0,' + repr(str(Path(__file__).resolve().parents[1] / 'scripts')) + ')\n'
                      'from inference_budget import reserve,settle\nr=json.load(sys.stdin)\n'
                      't=reserve("primary",json.dumps(r["messages"]),r["max_tokens"])\n'
                      'settle(t,None)\nprint(json.dumps({"content":"ok"}))\n')
    monkeypatch.setenv('ACE_RTL_ADAPTER_BUDGET_MANAGED', '1')
    assert call_adapter_script(script_path=str(script), model='default', messages=[{'role': 'user', 'content': 'p'}],
        temperature=.2, max_tokens=10, timeout=2)['content'] == 'ok'
    assert snapshot(Path(os.environ['ACE_EXPERIMENT_BUDGET_FILE']))['primary']['calls'] == 1


def test_retries_account_each_physical_request(tmp_path, monkeypatch):
    from llm_call import call_with_retries
    from inference_budget import snapshot
    import os
    script = tmp_path / 'retry.py'
    counter = tmp_path / 'counter'
    script.write_text('import pathlib,sys,json\np=pathlib.Path(' + repr(str(counter)) + ')\n'
        'n=int(p.read_text()) if p.exists() else 0\np.write_text(str(n+1))\n'
        'if n<2:\n print("HTTP 503: unavailable",file=sys.stderr)\n sys.exit(1)\n'
        'print(json.dumps({"content":"ok","usage":{"prompt_tokens":3,"completion_tokens":4,"total_tokens":7}}))\n')
    monkeypatch.setenv('ACE_RTL_LLM_SCRIPT', str(script))
    monkeypatch.setenv('ACE_RTL_EVENT_ROOT', str(tmp_path / 'events'))
    result = call_with_retries(provider='nvidia', model='custom', messages=[{'role': 'user', 'content': 'p'}],
        temperature=.2, max_tokens=10, max_retries=3, initial_backoff=0, shrink_chars=100, role='reflector')
    assert result['content'] == 'ok' and result['attempts'] == 3
    campaign = snapshot(Path(os.environ['ACE_EXPERIMENT_BUDGET_FILE']))['primary']
    assert campaign['calls'] == 3
    assert campaign['unknown_token_reservations'] == 2
    rows = [json.loads(line) for p in (tmp_path / 'events').glob('*.jsonl') for line in p.read_text().splitlines()]
    assert len([r for r in rows if r['kind'] == 'call_started']) == 3
    assert {r['role'] for r in rows} == {'reflector'}


def test_usage_envelope_does_not_promote_estimates_to_reported():
    from ace_rtl_agent.decision.budget import usage_envelope
    assert usage_envelope({'total_tokens': 5, 'source': 'estimated_chars_div_4'})['source'] != 'reported'
    assert usage_envelope({'prompt_tokens': 5, 'completion_tokens': 6, 'total_tokens': 1})['source'] != 'reported'


def test_backend_http_low_timeout_and_auth_no_duplicate(monkeypatch):
    from ace_rtl_agent import llm_backend as backend
    import urllib.request
    captured = {}
    class Process:
        returncode = 22
        stdout = 'server body secret-key'
        stderr = 'curl: (22) The requested URL returned error: 401'
    def run(*args, **kwargs):
        captured.update(kwargs)
        return Process()
    monkeypatch.setattr(backend.subprocess, 'run', run)
    monkeypatch.setattr(backend.shutil, 'which', lambda _: '/usr/bin/curl')
    req = urllib.request.Request('http://localhost/v1', data=b'{}')
    with pytest.raises(RuntimeError, match='HTTP 401') as exc:
        backend.urlopen_json_with_total_timeout(req, .2)
    assert captured['timeout'] <= .2
    assert 'secret-key' not in str(exc.value)


def test_llm_client_timeout_forwarded_and_string_envelope_preserved(tmp_path, monkeypatch):
    from ace_rtl_agent.utils.llm_client import LLMClient
    monkeypatch.setenv('ACE_RTL_LLM_SCRIPT', str(tmp_path / 'fake.py'))
    client = LLMClient('custom', initial_backoff=0)
    captured = {}
    def prompt(text, **kwargs):
        captured.update(kwargs)
        client.client.last_response = {'content': 'ok', 'usage': {'source': 'reported', 'total_tokens': 7}}
        return 'ok'
    monkeypatch.setattr(client.client, 'prompt', prompt)
    assert client.call_llm('p', timeout=.2, role='coordinator') == 'ok'
    assert captured['timeout'] <= .2 and captured['role'] == 'coordinator'
    assert client.last_response['usage']['total_tokens'] == 7


def test_retry_after_is_bounded_by_common_deadline(tmp_path, monkeypatch):
    from llm_call import call_with_retries
    from inference_budget import snapshot
    import os
    script = tmp_path / 'rate.py'
    script.write_text('import sys\nprint("HTTP 429: request failed Retry-After=30",file=sys.stderr)\nsys.exit(1)\n')
    monkeypatch.setenv('ACE_RTL_LLM_SCRIPT', str(script))
    monkeypatch.setenv('ACE_RTL_DEADLINE_MONOTONIC', str(time.monotonic() + .15))
    with pytest.raises(TimeoutError, match='NON_RETRYABLE'):
        call_with_retries(provider='nvidia', model='custom', messages=[{'role': 'user', 'content': 'p'}],
            temperature=.2, max_tokens=10, max_retries=3, initial_backoff=0, shrink_chars=100)
    assert snapshot(Path(os.environ['ACE_EXPERIMENT_BUDGET_FILE']))['primary']['calls'] == 1


def test_adapter_timeout_kills_descendants(tmp_path, monkeypatch):
    from llm_call import call_adapter_script
    from ace_cvdp_native.processes import pid_is_alive
    import os
    pid_file = tmp_path / 'child.pid'
    script = tmp_path / 'spawner.py'
    script.write_text('import subprocess,sys,time,pathlib\np=subprocess.Popen([sys.executable,"-c","import time; time.sleep(20)"])\n'
                      'pathlib.Path(' + repr(str(pid_file)) + ').write_text(str(p.pid))\ntime.sleep(20)\n')
    with pytest.raises(Exception):
        call_adapter_script(script_path=str(script), model='custom', messages=[{'role': 'user', 'content': 'p'}],
            temperature=.2, max_tokens=10, timeout=.3)
    pid = int(pid_file.read_text())
    try:
        # A zombie is not a running provider request; psutil handles this on macOS.
        import psutil
        running = psutil.pid_exists(pid) and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
        assert not running
    finally:
        if pid_is_alive(pid):
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass


def test_typed_multifile_manifest_generated_paths_claim(tmp_path):
    from ace_rtl_agent.decision.types import CandidateBundle
    from ace_cvdp_native.processes import try_claim_first_pass, read_first_pass_claim
    files = {'rtl/a.sv': 'module a; endmodule', 'rtl/b.sv': 'module b; endmodule'}
    generated = {}
    for name, content in files.items():
        path = tmp_path / 'candidate' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        generated[name] = str(path)
    bundle = CandidateBundle.create(files, episode_id='episode-1')
    manifest = tmp_path / 'candidate_manifest.json'
    manifest.write_text(json.dumps(dict(bundle.to_dict(), generated_files=generated,
                                       mutable_targets=list(files), task_id='t')))
    evaluation = tmp_path / 'real_evaluator_result.json'
    evaluation.write_text(json.dumps({'errors': 0, 'tests': [{'service': 'sim', 'result': 0}],
                                      'tested_hash': bundle.tested_hash}))
    assert try_claim_first_pass(dp_root=tmp_path, task_id='t', attempt_index=1, iteration=1,
        candidate_path=Path(generated['rtl/a.sv']), manifest_path=manifest, evaluation_path=evaluation,
        required_services=('sim',))
    assert read_first_pass_claim(tmp_path) is not None
    Path(generated['rtl/b.sv']).write_text('corrupt secondary file')
    assert read_first_pass_claim(tmp_path) is None


def test_cancelled_paid_call_is_durable_unknown(tmp_path, monkeypatch):
    from ace_rtl_agent.decision.budget import PaidCall
    monkeypatch.setenv('ACE_RTL_EVENT_ROOT', str(tmp_path / 'events'))
    monkeypatch.setenv('ACE_RTL_ATTEMPT_ID', 'attempt-2')
    with pytest.raises(KeyboardInterrupt):
        with PaidCall(provider='fixture', model='model', messages=[{'content': 'p'}], max_tokens=10):
            raise KeyboardInterrupt()
    rows = [json.loads(line) for path in (tmp_path / 'events').glob('*.jsonl') for line in path.read_text().splitlines()]
    assert [row['kind'] for row in rows] == ['call_started', 'call_cancelled']
    assert rows[-1]['upstream_billing_unknown'] is True
    assert rows[-1]['attempt'] == 'attempt-2'


def test_local_http_retry_after_is_preserved_without_body(monkeypatch):
    import local_llm_adapter as adapter
    for key, value in dict(LLM_BASE_URL='http://localhost/v1', LLM_API_KEY='secret', LLM_MODEL='default').items():
        monkeypatch.setenv(key, value)
    class Response:
        status_code = 429
        headers = {'Retry-After': '12'}
    monkeypatch.setattr(adapter.requests, 'post', lambda *a, **kw: Response())
    with pytest.raises(RuntimeError) as exc:
        adapter.complete({'messages': [{'role': 'user', 'content': 'p'}], 'max_tokens': 10})
    assert exc.value.retry_after == 12


def test_curl_http_retry_after(monkeypatch):
    from ace_rtl_agent import llm_backend as backend
    import urllib.request
    class Process:
        returncode = 22
        stdout = 'secret body'
        stderr = 'curl: (22) The requested URL returned error: 429'
    def run(command, **kwargs):
        Path(command[command.index('--dump-header') + 1]).write_text('HTTP/1.1 429 Too Many Requests\r\nRetry-After: 12\r\n\r\n')
        return Process()
    monkeypatch.setattr(backend.subprocess, 'run', run)
    monkeypatch.setattr(backend.shutil, 'which', lambda _: '/usr/bin/curl')
    with pytest.raises(RuntimeError) as exc:
        backend.urlopen_json_with_total_timeout(urllib.request.Request('http://localhost/v1', data=b'{}'), 1)
    assert exc.value.retry_after == 12
    assert 'secret body' not in str(exc.value)


def test_raw_decision_cache_never_reuses_actions_or_unknown_model(tmp_path):
    from ace_rtl_agent.decision.cache import DecisionCache
    cache = DecisionCache(tmp_path)
    context = dict(provider='typesafe', requested_model='jev-latest', resolved_model='jev-1.2.3', schema_version='s1')
    result = {'answers': {'q': 'A'}, 'chosen_action': {'action_kind': 'fresh_start'}, 'policy_version': 'old'}
    assert cache.put({'state': 1}, ['q'], result, **context)
    assert cache.get({'state': 1}, ['q'], **context) == {'answers': {'q': 'A'}}
    assert cache.get({'state': 1}, ['q'], **dict(context, resolved_model=None)) is None
    assert cache.get({'state': 1}, ['q'], **dict(context, resolved_model='jev-latest')) is None
    assert cache.get({'state': 2}, ['q'], **context) is None
    assert cache.get({'state': 1}, ['q'], **dict(context, requested_model='jev-new')) is None


def test_usage_malformed_details_cannot_lose_known_charge():
    from ace_rtl_agent.decision.budget import usage_envelope
    raw = {'prompt_tokens': 3, 'completion_tokens': 4, 'total_tokens': 7,
           'prompt_tokens_details': ['invalid'], 'completion_tokens_details': ['invalid']}
    usage = usage_envelope(raw)
    assert usage['source'] == 'reported' and usage['total_tokens'] == 7
    import local_llm_adapter
    assert local_llm_adapter.usage_metrics(raw, '', '')['total_tokens'] == 7


def test_telemetry_redaction_never_corrupts_numeric_metadata(tmp_path, monkeypatch):
    import local_llm_adapter
    monkeypatch.setenv('LLM_API_KEY', '123')
    path = tmp_path / 'event.json'
    local_llm_adapter.write_event({'usage': {'total_tokens': 123}, 'detail': 'key=123'}, path)
    stored = json.loads(path.read_text())
    assert stored['usage']['total_tokens'] == 123
    assert stored['detail'] == 'key=[REDACTED]'


def test_urllib_large_response_does_not_deadlock_on_pipe(monkeypatch):
    from ace_rtl_agent import llm_backend as backend
    import urllib.request
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({'content': 'x' * 200000}).encode())
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(backend.shutil, 'which', lambda _: None)
    try:
        req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/v1', data=b'{}')
        result = backend.urlopen_json_with_total_timeout(req, 2)
        assert len(result['content']) == 200000
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_ledger_preserves_token_limits_and_safe_ids(tmp_path, monkeypatch):
    from ace_rtl_agent.decision.ledger import EventLedger
    monkeypatch.setenv('ACE_RTL_MAX_TOKENS', '123')
    ledger = EventLedger(tmp_path, 1)
    ledger.append('call_started', request_id='request-123', max_tokens=123)
    row = json.loads(ledger.path.read_text())
    assert row['request_id'] == 'request-123' and row['max_tokens'] == 123
