"""Offline contracts verified against TypeSafe OpenAPI and Ollama System One docs."""
import json
import math
import sys
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/ace-rtl/scripts'))


def mixed_questions():
    return {
        'pick': {'type': 'choice', 'instructions': 'Choose from state.actions.',
                 'criteria': {'a': 'Repair', 'b': 'Inspect'}},
        'fit': {'type': 'noul', 'instructions': 'Does state.actions.a fit?',
                'criteria': {'true': 'Supported', 'false': 'Unsupported'}},
        'risk': {'type': 'score', 'instructions': 'Rate state.actions.a risk.',
                 'criteria': ['Low', 'Medium', 'High']},
    }


def response_payload():
    return {'model': 'jev-1.13.0', 'usage': {'input_tokens': 20, 'output_tokens': 3},
            'answers': {
                'pick': {'type': 'choice', 'choice': 'a', 'probabilities': {'a': .8, 'b': .2}, 'confidence': .3},
                'fit': {'type': 'noul', 'noul': .81},
                'risk': {'type': 'score', 'score': .7, 'probabilities': {'0': .4, '1': .5, '2': .1},
                         'legend': {'0': 'Low', '1': 'Medium', '2': 'High'}, 'confidence': .2},
            }}


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    # Use the real campaign implementation, not an admission-bypassing mock.
    import importlib.util
    spec = importlib.util.spec_from_file_location('test_campaign', ROOT / 'scripts/inference_budget.py')
    budget = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(budget)
    path = tmp_path / 'campaign.sqlite'
    budget.init_budget(path, {'primary': {'max_calls': 2, 'max_tokens': 100000},
                             'jev': {'max_calls': 10, 'max_tokens': 1000000,
                                     'max_usd': .10, 'reserve_usd': .0015}})
    monkeypatch.setenv('ACE_EXPERIMENT_BUDGET_FILE', str(path))
    monkeypatch.setenv('ACE_EXPERIMENT_TELEMETRY', str(tmp_path / 'events'))
    return path, budget


def test_validated_answers_preserve_actual_mixed_wire_format():
    from ace_rtl_agent.decision.systemone_client import validate_answers
    payload = response_payload()
    answers = validate_answers(payload, mixed_questions())
    assert answers == payload['answers']
    assert type(answers['fit']['noul']) is float
    assert answers['risk']['score'] == .7
    answers['risk']['legend']['0'] = 'changed'
    assert payload['answers']['risk']['legend']['0'] == 'Low'


@pytest.mark.parametrize('mutation', [
    lambda p: p['answers'].pop('fit'),
    lambda p: p['answers'].update(extra={'type': 'noul', 'noul': .5}),
    lambda p: p['answers']['fit'].update(type='choice'),
    lambda p: p['answers']['fit'].update(noul=True),
    lambda p: p['answers']['fit'].update(noul=math.nan),
    lambda p: p['answers']['fit'].update(noul=math.inf),
    lambda p: p['answers']['fit'].update(noul=-.1),
    lambda p: p['answers']['pick'].update(choice='unknown'),
    lambda p: p['answers']['pick'].update(choice='b'),
    lambda p: p['answers']['pick'].update(probabilities={'a': .8, 'x': .2}),
    lambda p: p['answers']['pick'].update(probabilities={'a': .8, 'b': .8}),
    lambda p: p['answers']['pick'].update(confidence=2),
    lambda p: p['answers']['risk'].update(legend={'0': 'Low', '1': 'Wrong', '2': 'High'}),
    lambda p: p['answers']['risk'].update(score=1.7),
    lambda p: p['answers']['risk'].update(score=True),
    lambda p: p['answers']['risk'].update(score=3),
])
def test_rejects_invalid_typed_distributions(mutation):
    from ace_rtl_agent.decision.systemone_client import validate_answers
    payload = response_payload()
    mutation(payload)
    with pytest.raises(ValueError):
        validate_answers(payload, mixed_questions())


class Transport:
    def __init__(self, payload=None, status=200, error=None):
        self.payload = payload if payload is not None else response_payload()
        self.status = status
        self.error = error
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        return self

    @property
    def status_code(self):
        return self.status

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def client(transport, **kwargs):
    from ace_rtl_agent.decision.systemone_client import SystemOneClient
    return SystemOneClient('https://api.typesafe.ai/v1/systemone', 'jev-latest',
                           api_key='secret-test-token', provider='typesafe', transport=transport, **kwargs)


def test_client_envelope_full_endpoint_tls_and_real_campaign(campaign):
    transport = Transport()
    result = client(transport).decide({'actions': {'a': {}}}, mixed_questions(), timeout=2.5)
    assert set(result) == {'answers', 'requested_model', 'resolved_model', 'usage', 'latency_seconds', 'call_id'}
    assert result['requested_model'] == 'jev-latest'
    assert result['resolved_model'] == 'jev-1.13.0'
    assert result['usage']['total_tokens'] == 23
    assert result['usage']['source'] == 'reported'
    assert result['latency_seconds'] >= 0
    url, request = transport.calls[0]
    assert url == 'https://api.typesafe.ai/v1/systemone'
    assert request['allow_redirects'] is False
    assert request.get('verify', True) is True
    assert 0 < request['timeout'] <= 2.5
    assert request['json'] == {'model': 'jev-latest', 'state': {'actions': {'a': {}}}, 'questions': mixed_questions()}
    path, budget = campaign
    assert budget.snapshot(path)['jev']['calls'] == 1
    assert budget.snapshot(path)['jev']['known_tokens'] == 23
    events = list(path.parent.glob('events/*.json'))
    assert len(events) == 1
    event = json.loads(events[0].read_text())
    assert event['status'] == 'ok'
    assert 'secret-test-token' not in events[0].read_text()
    assert 'state' not in event


def test_missing_campaign_blocks_even_injected_transport(monkeypatch):
    monkeypatch.delenv('ACE_EXPERIMENT_BUDGET_FILE', raising=False)
    transport = Transport()
    with pytest.raises(RuntimeError, match='budget denied'):
        client(transport).decide({'x': 1}, mixed_questions())
    assert not transport.calls


@pytest.mark.parametrize('status', [301, 401, 403, 422, 429, 500, 503])
def test_http_failures_are_typed_sanitized_and_settle_unknown(status, campaign):
    from ace_rtl_agent.decision.systemone_client import SystemOneHTTPError
    with pytest.raises(SystemOneHTTPError) as caught:
        client(Transport(status=status)).decide({'x': 1}, mixed_questions())
    assert caught.value.status_code == status
    assert caught.value.retryable == (status == 429 or status >= 500)
    assert 'secret' not in str(caught.value)
    assert campaign[1].snapshot(campaign[0])['jev']['unknown_token_reservations'] == 1


@pytest.mark.parametrize('error,kind', [(requests.Timeout('secret'), 'timeout'),
                                      (requests.ConnectionError('secret'), 'connection')])
def test_transport_errors_do_not_leak_credentials(error, kind, campaign):
    from ace_rtl_agent.decision.systemone_client import SystemOneTransportError
    with pytest.raises(SystemOneTransportError) as caught:
        client(Transport(error=error)).decide({'x': 1}, mixed_questions())
    assert caught.value.kind == kind
    assert 'secret' not in str(caught.value)


@pytest.mark.parametrize('field,value', [('model', None), ('model', 5), ('usage', None),
                                       ('usage', {'input_tokens': True, 'output_tokens': 2}),
                                       ('usage', {'input_tokens': -1, 'output_tokens': 2})])
def test_required_provider_receipt_contract(field, value, campaign):
    from ace_rtl_agent.decision.systemone_client import SystemOneSchemaError
    payload = response_payload()
    payload[field] = value
    with pytest.raises(SystemOneSchemaError):
        client(Transport(payload)).decide({'x': 1}, mixed_questions())


def test_usage_survives_answer_validation_failure(campaign):
    from ace_rtl_agent.decision.systemone_client import SystemOneSchemaError
    payload = response_payload()
    payload['answers']['fit']['noul'] = True
    with pytest.raises(SystemOneSchemaError):
        client(Transport(payload)).decide({'x': 1}, mixed_questions())
    assert campaign[1].snapshot(campaign[0])['jev']['known_tokens'] == 23


def test_unsupported_usage_and_unknown_resolution_are_not_fabricated(campaign):
    from ace_rtl_agent.decision.systemone_client import SystemOneClient
    payload = response_payload()
    payload.pop('model')
    payload.pop('usage')
    result = SystemOneClient('http://localhost:8000/v1/systemone', 'local', transport=Transport(payload)).decide({'x': 1}, mixed_questions())
    assert result['resolved_model'] is None
    assert result['usage']['source'] == 'unknown'
    assert result['usage']['total_tokens'] is None


def test_ollama_model_echo_is_not_a_pinned_resolution(campaign):
    from ace_rtl_agent.decision.systemone_client import SystemOneClient
    payload = response_payload()
    payload['model'] = 'nimble'
    obj = SystemOneClient('http://localhost:11434/v1/systemone', 'nimble', provider='ollama', transport=Transport(payload))
    assert obj.capabilities.max_request_bytes == 65536
    assert obj.capabilities.max_score_levels == 26
    assert obj.decide({'x': 1}, mixed_questions())['resolved_model'] is None


def test_environment_aliases_and_precedence(monkeypatch):
    from ace_rtl_agent.decision.systemone_client import SystemOneClient
    for name in list(__import__('os').environ):
        if name.startswith(('JEV_', 'SYSTEMONE_')):
            monkeypatch.delenv(name)
    monkeypatch.setenv('JEV_ENDPOINT_URL', 'https://api.typesafe.ai/v1/systemone')
    monkeypatch.setenv('JEV_MODEL', 'jev-latest')
    monkeypatch.setenv('JEV_API_KEY', 'secret')
    monkeypatch.setenv('JEV_PROVIDER', 'typesafe')
    monkeypatch.setenv('JEV_REQUEST_TIMEOUT', '7')
    obj = SystemOneClient.from_env(transport=Transport())
    assert obj.model == 'jev-latest'
    assert obj.timeout_seconds == 7
    monkeypatch.setenv('SYSTEMONE_MODEL', 'jev-1.13.0')
    monkeypatch.setenv('SYSTEMONE_TIMEOUT_SECONDS', '3')
    assert SystemOneClient.from_env().model == 'jev-1.13.0'
    assert SystemOneClient.from_env().timeout_seconds == 3


@pytest.mark.parametrize('change', [{'timeout_seconds': math.nan}, {'timeout_seconds': 0},
                                  {'endpoint_url': 'https://secret@api.typesafe.ai/v1/systemone'},
                                  {'endpoint_url': 'https://api.typesafe.ai/v1/systemone?key=secret'}])
def test_invalid_configuration_is_rejected(change):
    from ace_rtl_agent.decision.systemone_client import SystemOneClient
    args = {'endpoint_url': 'https://api.typesafe.ai/v1/systemone', 'model': 'jev-latest', 'api_key': 'secret', 'provider': 'typesafe'}
    args.update(change)
    with pytest.raises(ValueError):
        SystemOneClient(**args)


def test_question_factories_identify_state_paths_and_independent_candidates():
    from ace_rtl_agent.decision.questions import (
        QUESTION_VERSION, QUESTION_REGISTRY, build_action_questions, build_context_questions,
        build_effect_questions, build_focus_questions, build_task_kind_questions,
    )
    actions = {'repair': {'description': 'Repair width', 'preconditions': ['Width evidence']},
               'inspect': {'description': 'Inspect public evidence'}}
    questions = build_action_questions(actions)
    assert {'action', 'fit:repair', 'fit:inspect', 'risk:repair:interface', 'risk:inspect:width'} <= set(questions)
    assert questions['fit:repair']['type'] == 'noul'
    assert questions['risk:repair:interface']['type'] == 'noul'
    assert 'repair' in questions['fit:repair']['instructions']
    assert 'state.actions' in questions['action']['instructions']
    assert questions['action']['criteria']['none_suitable']
    assert QUESTION_VERSION in QUESTION_REGISTRY
    factories = [build_effect_questions(), build_focus_questions({'e1': 'Width mismatch'}),
                 build_context_questions({'c1': 'Public interface trace'}), build_task_kind_questions()]
    for batch in [questions, *factories]:
        for question in batch.values():
            assert 'state.' in question['instructions']
            assert 'answer' not in question['instructions'].lower()
    assert 'insufficient_evidence' in factories[1]['focus_error']['criteria']
    assert 'unknown' in factories[-1]['task_kind']['criteria']


def test_invalid_request_never_spends_campaign(campaign):
    transport = Transport()
    questions = mixed_questions()
    questions['risk']['criteria'] = []
    with pytest.raises(ValueError):
        client(transport).decide({'x': 1}, questions)
    assert not transport.calls
    assert campaign[1].snapshot(campaign[0])['jev']['calls'] == 0


@pytest.mark.parametrize('state', [{'api_key': 'secret'}, {'nested': {'private_checker': 'hidden code'}},
                                 {'evidence': [{'reference_source': 'hidden'}]},
                                 {'authorization': 'Bearer secret'}, {'value': math.nan},
                                 {'diagnostic': 'Authorization: Bearer exposed-token'},
                                 {'diagnostic': 'API_KEY=exposed-token'},
                                 {'diagnostic': 'password: exposed-password'}])
def test_unsafe_state_rejected_before_admission(state, campaign):
    transport = Transport()
    with pytest.raises(ValueError):
        client(transport).decide(state, mixed_questions())
    assert not transport.calls
    assert campaign[1].snapshot(campaign[0])['jev']['calls'] == 0


def test_typesafe_single_score_level_allowed_by_actual_openapi(campaign):
    questions = {'r': {'type': 'score', 'instructions': 'Rate state.fact.', 'criteria': ['Only level']}}
    payload = {'model': 'jev-1.13.0', 'usage': {'input_tokens': 1, 'output_tokens': 1},
               'answers': {'r': {'type': 'score', 'score': 0., 'legend': {'0': 'Only level'},
                                 'probabilities': {'0': 1.}, 'confidence': 1.}}}
    assert client(Transport(payload)).decide({'fact': 'x'}, questions)['answers']['r']['score'] == 0.


def test_malformed_json_is_typed_and_still_settles(campaign):
    from ace_rtl_agent.decision.systemone_client import SystemOneSchemaError
    with pytest.raises(SystemOneSchemaError):
        client(Transport(ValueError('secret in malformed payload'))).decide({'x': 1}, mixed_questions())
    assert campaign[1].snapshot(campaign[0])['jev']['unknown_token_reservations'] == 1


def test_alias_echo_is_unknown_even_when_request_is_pinned(campaign):
    payload = response_payload()
    payload['model'] = 'jev-latest'
    assert client(Transport(payload)).decide({'x': 1}, mixed_questions())['resolved_model'] is None


def test_campaign_is_inflight_during_actual_request(campaign):
    path, budget = campaign
    def transport(url, **kwargs):
        import sqlite3
        with sqlite3.connect(path) as db:
            assert db.execute('SELECT status FROM tickets').fetchall() == [('inflight',)]
        return Transport()
    assert client(transport).decide({'x': 1}, mixed_questions())['usage']['total_tokens'] == 23
    assert budget.snapshot(path)['jev']['calls'] == 1


def test_cost_receipt_survives_invalid_tokens(campaign):
    from ace_rtl_agent.decision.systemone_client import SystemOneSchemaError
    payload = response_payload()
    payload['usage'] = {'input_tokens': True, 'output_tokens': 3, 'cost': .0001, 'cost_currency': 'USD'}
    with pytest.raises(SystemOneSchemaError):
        client(Transport(payload)).decide({'x': 1}, mixed_questions())
    assert campaign[1].snapshot(campaign[0])['jev']['usd_exposure'] == .0001


def test_pinned_model_mismatch_rejects_but_preserves_usage(campaign):
    from ace_rtl_agent.decision.systemone_client import SystemOneClient, SystemOneSchemaError
    transport = Transport()
    obj = SystemOneClient('https://api.typesafe.ai/v1/systemone', 'jev-1.12.0', api_key='secret',
                          provider='typesafe', transport=transport)
    with pytest.raises(SystemOneSchemaError):
        obj.decide({'x': 1}, mixed_questions())
    assert campaign[1].snapshot(campaign[0])['jev']['known_tokens'] == 23


def test_nonfinite_unrecognized_response_values_are_not_preserved():
    from ace_rtl_agent.decision.systemone_client import validate_answers
    payload = response_payload()
    payload['answers']['fit']['unexpected_provider_metric'] = math.nan
    with pytest.raises(ValueError):
        validate_answers(payload, mixed_questions())


def test_public_state_guard_also_covers_structured_question_inputs(campaign):
    questions = mixed_questions()
    questions['pick']['instructions'] = {'private_checker': 'hidden'}
    transport = Transport()
    with pytest.raises(ValueError):
        client(transport).decide({'x': 1}, questions)
    assert not transport.calls


def test_request_byte_limit_uses_actual_requests_json_encoding(campaign):
    from ace_rtl_agent.decision.systemone_client import SystemOneClient, ProviderCapabilities
    caps = ProviderCapabilities(max_request_bytes=900)
    transport = Transport()
    obj = SystemOneClient('http://localhost:8000/v1/systemone', 'local', capabilities=caps, transport=transport)
    with pytest.raises(ValueError, match='byte limit'):
        obj.decide({'text': '한' * 100}, mixed_questions())
    assert not transport.calls


def test_focus_target_factory_is_closed_to_mutable_manifest():
    from ace_rtl_agent.decision.questions import build_focus_questions
    questions = build_focus_questions({'e1': 'Mismatch'}, targets=('rtl/a.sv', 'rtl/b.sv'))
    assert set(questions['focus_target']['criteria']) == {'rtl/a.sv', 'rtl/b.sv', 'none_suitable', 'insufficient_evidence'}
    assert 'state.contract.mutable_targets' in questions['focus_target']['instructions']
def test_transport_private_boundary_checks_tuple_containers():
    from ace_rtl_agent.decision.systemone_client import validate_public_state
    import pytest
    with pytest.raises(ValueError):
        validate_public_state({'items':('password=do-not-send',)})


def test_concrete_model_cache_preserves_raw_answers_without_new_http(campaign,monkeypatch):
    from ace_rtl_agent.decision.systemone_client import SystemOneClient
    path,budget=campaign
    monkeypatch.setenv('ACE_RTL_EVENT_ROOT',str(path.parent/'ledger'))
    transport=Transport()
    instance=SystemOneClient('https://api.typesafe.ai/v1/systemone','jev-1.13.0',
                            api_key='secret-test-token',provider='typesafe',transport=transport)
    first=instance.decide({'actions':{'a':{}}},mixed_questions())
    second=instance.decide({'actions':{'a':{}}},mixed_questions())
    assert second['answers']==first['answers']
    assert len(transport.calls)==1
    assert budget.snapshot(path)['jev']['calls']==1
    assert second['usage']['source']=='local_cache_no_request'


def test_policy_timeout_cannot_expand_configured_provider_timeout(campaign):
    transport=Transport()
    client(transport,timeout_seconds=2).decide({'actions':{'a':{}}},mixed_questions(),timeout=10)
    assert transport.calls[0][1]['timeout']<=2


def test_inconsistent_score_records_scalar_evidence_not_arbitrary_body(campaign):
    from ace_rtl_agent.decision.systemone_client import SystemOneSchemaError
    path,_=campaign
    payload=response_payload();payload['answers']['risk']['score']=1.7
    with pytest.raises(SystemOneSchemaError):client(Transport(payload)).decide({'actions':{'a':{}}},mixed_questions())
    event=json.loads(next((path.parent/'events').glob('*.json')).read_text())
    assert event['score_consistency']['risk']['score']==1.7
    assert event['score_consistency']['risk']['distribution_expectation']==pytest.approx(.7)
