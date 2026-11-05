"""Offline readback tests: existing native/domain owners, HTTP receipts doubled."""
import ast
import copy
from contextlib import nullcontext
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
import yaml
import prove_office_readback as R
import prove_native_budgets as N
import test_office_compatibility as T
from test_office_compatibility import component, native


def scenario(component, monkeypatch):
    monkeypatch.setattr(R, 'OFFICE_FILTER', T.ROOT / 'deploy/openwebui-functions/officecli_auto_attach_filter.py')
    instruction = R.proof.office_instruction(R.OFFICE_FILTER.read_bytes())
    calls, owner = T.wire_capture(component)
    for call in calls:
        for body in (call['wire_before_auth'], call['wire_after_auth'], call['provider']['body']):
            body['instructions'] = instruction
        call['provider']['body']['model'] = call['provider']['response']['model'] = 'goal584-fake-office'
    before, primary_after, kwargs = T.financial_fixture(component, monkeypatch)
    service_before, service_after, service_kwargs = T.service_financial_fixture(component, monkeypatch)
    actor, payer = owner['actor'], service_kwargs['payer']
    for key in ('user', 'key'):
        before[key]['user_id'] = actor
    before['key']['token'] = owner['key_hash']
    primary_after = copy.deepcopy(before)
    template = copy.deepcopy(T.financial_fixture(component, monkeypatch)[1]['rows'][-1])
    for call in calls:
        row = copy.deepcopy(template)
        row.update(user=actor, session_id=owner['chat_id'], model='openai/goal584-fake-office',
            request_id='resp_' + T.base64.b64encode(('litellm:custom_llm_provider:openai;model_id:goal584-office-primary;response_id:'
                + call['provider']['id']).encode()).decode(), model_id='goal584-office-primary')
        row['metadata']['spend_logs_metadata']['owui_budget'] = copy.deepcopy(call['verified_cost_scope'])
        primary_after['rows'].append(row)
    primary_after['user']['spend'] = primary_after['key']['spend'] = .60
    service_before['key']['token'] = service_kwargs['key_hash']
    service_after['key']['token'] = service_kwargs['key_hash']
    scope = service_kwargs['verified_scope']; scope.update(actor_id=actor, chat_id=owner['chat_id'])
    row = service_after['rows'][-1]; row['metadata']['spend_logs_metadata']['owui_budget'] = copy.deepcopy(scope)
    row['session_id'] = 'owui-service:' + owner['chat_id']
    text = '[Download](/api/v1/files/' + owner['exported']['result_file_id'] + '/content)'
    service_wire = component.router['convert_to_responses_payload']({'model': 'gpt-6-luna', 'messages': [
        {'role': 'system', 'content': 'Produce follow-up questions.'}, {'role': 'assistant', 'content': text}],
        'reasoning': {'effort': 'none'}, 'store': False, 'stream': False})
    followups = ['Prepare a PDF copy.']
    service_provider = {'id': service_kwargs['provider_id'], 'route': '/v1/responses',
        'body': {**copy.deepcopy(service_wire), 'model': 'goal584-fake-office-service'}, 'usage': R.proof.USAGE,
        'response': {'id': service_kwargs['provider_id'], 'model': 'goal584-fake-office-service', 'status': 'completed',
            'usage': R.proof.USAGE, 'output': [{'type': 'message', 'role': 'assistant',
                'content': [{'type': 'output_text', 'text': json.dumps({'follow_ups': followups})}]}]},
        'lifecycle': {'terminal': True, 'outcome': 'completed', 'stage': 'completed'}}
    provider = {'requests': [*[c['provider'] for c in calls], service_provider]}
    observed = [{'body': c['wire_before_auth'], 'body_after_auth': c['wire_after_auth'],
        'native_auth_user_id': c['auth_user_id'], 'native_auth_key_hash': c['auth_key_hash'],
        'attestation_present_before': True, 'provenance_removed_after': True, 'route': c['route'],
        'verified_cost_scope': c['verified_cost_scope']} for c in calls]
    observed.append({'body': service_wire, 'body_after_auth': copy.deepcopy(service_wire),
        'native_auth_user_id': payer, 'native_auth_key_hash': service_kwargs['key_hash'],
        'attestation_present_before': True, 'provenance_removed_after': True, 'route': '/responses', 'verified_cost_scope': scope})
    finance = {'primary': before, 'service': service_before, 'raw_owners': dict.fromkeys((actor, payer, 'old-owner'))}
    after = {'primary': primary_after, 'service': service_after, 'raw_owners': copy.deepcopy(finance['raw_owners'])}
    baseline = {'provider': {'requests': []}, 'capture': {'requests': []}, 'finance': finance, 'descriptor': service_kwargs['descriptor']}
    office = {'users': [{'id': actor}], 'service_fixture': {'payer_id': payer},
        'office_setup': {'openapi': component.client.get('/openapi.json').json()}}
    browser = {'schema': 1, 'chat_id': owner['chat_id'], 'answer_id': owner['answer_id'],
        'source_message_id': owner['exported']['source_message_id'], 'file_id': owner['exported']['result_file_id']}
    saved = {'id': owner['chat_id'], 'user_id': actor, 'chat': {'history': {'messages': {
        browser['source_message_id']: {'id': browser['source_message_id'], 'role': 'assistant', 'content': R.proof.SOURCE},
        'current-user': {'id': 'current-user', 'role': 'user', 'content': R.proof.USER_REQUEST, 'parentId': browser['source_message_id']},
        owner['answer_id']: {'id': owner['answer_id'], 'role': 'assistant', 'content': text, 'model': R.proof.MODEL, 'done': True,
            'parentId': 'current-user', 'followUps': followups}}}}}
    reasoning = [[v for v in c['provider']['response']['output'] if v.get('type') == 'reasoning'] for c in calls[:2]]
    packet = {'schema': 1, 'source_body_sha256': R.proof.digest(office['office_setup']['openapi']),
        'module_sha256': {k: R.proof.WEBUI_MODULES[k] for k in ('utils/tools.py', 'routers/openai.py')},
        'native_specs': owner['native_specs'], 'reasoning_cases': [{'input_reasoning': value,
            'native_input': component.router['convert_to_responses_payload']({'messages': [{'role': 'assistant', 'output': value}]})['input']}
            for value in reasoning]}
    d = {'validate_persisted_scope': T.provenance.validate_persisted_scope,
        'validate_persisted_service_scope': T.provenance.validate_persisted_service_scope,
        'validate_snapshot': T.snapshots.validate_snapshot, 'ResponsesAPIRequestUtils': type('NativeDecoder', (), {
            '_decode_responses_api_response_id': staticmethod(T.sdk_decoder())})}
    return dict(before=baseline, after=after, provider=provider, capture={'requests': observed}, saved=saved,
                browser=browser, packet=packet, office=office, d=d)


def test_actual_native_context_domain_finance_and_sdk_owners_join_complete_live_packet(component, monkeypatch):
    data = scenario(component, monkeypatch)
    result = R.verify(**data)
    assert result == {'primary': {'physical_calls': 3, 'new_raw_rows': 3, 'native_spend_delta_usd': '.60'},
        'service': {'physical_calls': 1, 'new_raw_rows': 1, 'native_spend_delta_usd': '.20'},
        'provider_calls': 4, 'saved_chat_verified': True}
    assert all('before_budget' not in row for row in data['capture']['requests'])


@pytest.mark.parametrize('change', ['source_hash', 'module_hash', 'missing_reasoning', 'conflicting_reasoning', 'source', 'file',
    'saved_owner', 'saved_followups', 'provider_extra', 'capture_extra', 'prior_provider', 'prior_capture', 'service_payer',
    'service_unconsumed', 'service_wire', 'service_cost', 'service_response_model', 'empty_followups',
    'primary_rows', 'old_payer', 'payer_inventory', 'unsafe_wire'])
def test_complete_readback_rejects_unbound_native_context_and_actual_boundary_drift(component, monkeypatch, change):
    data = scenario(component, monkeypatch)
    if change == 'source_hash': data['packet']['source_body_sha256'] = '0' * 64
    elif change == 'module_hash': data['packet']['module_sha256']['utils/tools.py'] = '0' * 64
    elif change == 'missing_reasoning': data['packet']['reasoning_cases'] = []
    elif change == 'conflicting_reasoning':
        value = copy.deepcopy(data['packet']['reasoning_cases'][0]); value['native_input'] = []
        data['packet']['reasoning_cases'].append(value)
    elif change == 'source': data['saved']['chat']['history']['messages'][data['browser']['source_message_id']]['content'] = 'summary'
    elif change == 'file': data['browser']['file_id'] = str(uuid4())
    elif change == 'saved_owner': data['saved']['user_id'] = str(uuid4())
    elif change == 'saved_followups': data['saved']['chat']['history']['messages'][data['browser']['answer_id']]['followUps'] = []
    elif change == 'provider_extra': data['provider']['requests'].append(copy.deepcopy(data['provider']['requests'][-1]))
    elif change == 'capture_extra': data['capture']['requests'].append(copy.deepcopy(data['capture']['requests'][-1]))
    elif change == 'prior_provider': data['before']['provider']['requests'] = [{'retained': 'must not disappear'}]
    elif change == 'prior_capture': data['before']['capture']['requests'] = [{'retained': 'must not disappear'}]
    elif change == 'service_payer': data['capture']['requests'][-1]['native_auth_user_id'] = data['office']['users'][0]['id']
    elif change == 'service_unconsumed': data['capture']['requests'][-1]['provenance_removed_after'] = False
    elif change == 'service_wire': data['capture']['requests'][-1]['body_after_auth']['instructions'] = 'drift'
    elif change == 'service_cost': data['after']['service']['rows'][-1]['spend'] = .60
    elif change == 'service_response_model': data['provider']['requests'][-1]['response']['model'] = 'foreign-model'
    elif change == 'empty_followups':
        data['provider']['requests'][-1]['response']['output'][0]['content'][0]['text'] = '{"follow_ups":null}'
        data['saved']['chat']['history']['messages'][data['browser']['answer_id']]['followUps'] = None
    elif change == 'primary_rows': data['after']['primary']['rows'].pop()
    elif change == 'old_payer': data['after']['primary']['old_payers']['existing-payer']['user']['spend'] = 99
    elif change == 'payer_inventory': data['after']['raw_owners']['unknown-payer'] = {}
    else: data['capture']['requests'][0]['body']['instructions'] = 'sk-' + 'x' * 32
    with pytest.raises((N.ProofError, ValueError)): R.verify(**data)


def test_native_reasoning_callable_rejects_every_unrecorded_input(component, monkeypatch):
    data = scenario(component, monkeypatch); converter = R.native_converter(data['packet'], data['office'])
    with pytest.raises(N.ProofError): converter({'messages': [{'role': 'assistant', 'output': []}]})


@pytest.mark.parametrize('change,expected', [('primary_rows', None), ('primary_counter', None),
    ('service_rows', None), ('service_counter', None), ('source', 'office_native_context_source'),
    ('extra_rows', 'office_row_count'), ('counter_over', 'office_native_spend_delta'),
    ('service_binding', 'office_service_dispatch_binding'), ('malformed_packet', 'office_readback_failed')])
def test_cli_retries_only_under_settlement_and_retains_immediate_failures_privately(component, monkeypatch, tmp_path, capsys, change, expected):
    data = scenario(component, monkeypatch)
    office = data['office']; office.update(stage='setup_complete', office_service_setup={'stage': 'readback_ready'})
    office['users'][0]['token'] = 'private-test-account-token'
    common = {'started_at_utc': '2026-11-05T10:01:00+00:00'}
    operator = {'started_at': '2026-11-05T10:00:00+00:00'}
    baseline = data['before']; baseline.update(schema=1, stage='baseline', prepared_sha256=R.proof.digest(office),
        history_start_utc='2026-11-05T09:59:00+00:00')
    path = tmp_path / 'readback.private.json'; path.write_text(json.dumps(baseline))
    actual, partial = copy.deepcopy(data['after']), copy.deepcopy(data['after'])
    if change == 'primary_rows': partial['primary']['rows'].pop()
    elif change == 'primary_counter': partial['primary']['key']['spend'] = 0
    elif change == 'service_rows': partial['service']['rows'].pop()
    elif change == 'service_counter': partial['service']['user']['spend'] = 0
    elif change == 'source': data['packet']['source_body_sha256'] = '0' * 64
    elif change == 'extra_rows': partial['primary']['rows'].append({'request_id': 'unplanned-zero', 'spend': 0})
    elif change == 'counter_over': partial['primary']['user']['spend'] = .80
    elif change == 'service_binding': partial['service']['rows'][-1]['request_id'] = data['provider']['requests'][-1]['id']
    else: data['packet'].pop('reasoning_cases')
    snapshots = []
    def inventory(native, prepared):
        snapshots.append(change)
        return copy.deepcopy(partial if len(snapshots) == 1 else actual)
    inputs = {R.COMMON: common, R.OFFICE: office, R.BROWSER: data['browser'], R.CONTEXT: data['packet'], 'operator': operator}
    def read(path_value): return json.loads(path.read_text()) if path_value == R.STATE else copy.deepcopy(inputs[path_value])
    def write(path_value, value):
        assert path_value == R.STATE
        path.write_text(json.dumps(value))  # Private I/O double; domain validators remain actual.
    native = N.NativeProof('http://127.0.0.1:4000', 'private-test-operator', 2, {})
    d = dict(data['d'], OPERATOR_STATE='operator', read_private=read, write_private=write,
        native_client=lambda state: native, provider=lambda: copy.deepcopy(data['provider']), no_credentials=T.snapshots.no_credentials,
        private_credentials=T.snapshots.private_credentials,
        WebUI=lambda: SimpleNamespace(ok=lambda *args, **kwargs: copy.deepcopy(data['saved'])),
        capture=SimpleNamespace(capture_lock=nullcontext, _read_locked=lambda: copy.deepcopy(data['capture'])))
    monkeypatch.setattr(R, 'inventory', inventory); monkeypatch.setattr(R, 'dependencies', lambda: d)
    monkeypatch.setattr('sys.argv', ['prove_office_readback.py', '--phase', 'verify'])
    status = R.main(); public = json.loads(capsys.readouterr().out); private = json.loads(path.read_text())
    assert len(snapshots) == (2 if expected is None else 1)
    assert 'private-test' not in json.dumps(public)
    if expected is None:
        assert status == 0 and public['passed'] is True and private['stage'] == 'verified_readback'
        assert 'failure_code' not in private
    else:
        assert status == 1 and public['failure_code'] == expected and private['stage'] == 'baseline'
        assert private['last_observation']['provider'] == data['provider']
        assert private['last_observation']['capture'] == data['capture']
        assert private['last_observation']['after'] == partial
        if change == 'service_binding':
            assert public['binding_diagnostic_collected'] is True
            assert public['binding_diagnostic']['request_id'] == partial['service']['rows'][-1]['request_id']
            assert public['binding_diagnostic']['scope'] == public['binding_diagnostic']['verified_scope']


@pytest.mark.parametrize('message', ['sk-private-native-error-value', 'office_private sk-secret', 'office_unsafe-raw-detail'])
def test_cli_never_exports_unclassified_proof_error_prose(monkeypatch, capsys, message):
    def dependencies(): raise N.ProofError(message)
    monkeypatch.setattr(R, 'dependencies', dependencies)
    monkeypatch.setattr('sys.argv', ['prove_office_readback.py', '--phase', 'verify'])
    assert R.main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result['failure_code'] == 'office_readback_failed' and message not in json.dumps(result)


@pytest.mark.parametrize('unsafe', [None, 'credential', 'opaque_secret', 'oversize'])
def test_cli_exports_only_bounded_secret_checked_service_binding_failure(monkeypatch, capsys, unsafe):
    binding = {'decoded': {'model_id': None, 'response_id': 'resp_observed'}, 'scope': {'category': 'service'}}
    if unsafe == 'credential': binding['decoded']['response_id'] = 'sk-' + 'x' * 32
    elif unsafe == 'opaque_secret': binding['decoded']['response_id'] = 'opaque-private-password'
    elif unsafe == 'oversize': binding['decoded']['response_id'] = 'x' * 4097
    error = N.ProofError('office_service_dispatch_binding'); error.office_service_binding = binding
    d = dict(OPERATOR_STATE='operator', read_private=lambda path: {'password': 'opaque-private-password'},
        private_credentials=T.snapshots.private_credentials, no_credentials=T.snapshots.no_credentials)
    monkeypatch.setattr(R, 'dependencies', lambda: d)
    def fail(*args): raise error
    monkeypatch.setattr(R, 'run', fail)
    monkeypatch.setattr('sys.argv', ['prove_office_readback.py', '--phase', 'verify'])
    assert R.main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result['failure_code'] == 'office_service_dispatch_binding' and result['passed'] is False
    assert result['binding_diagnostic_collected'] is (unsafe is None)
    assert result.get('binding_diagnostic') == (binding if unsafe is None else None)
    assert 'opaque-private-password' not in json.dumps(result) and 'sk-' + 'x' * 32 not in json.dumps(result)


def diagnostic(data, *, secrets=()):
    return R.wire_diagnostic(data['before'], data['provider'], data['capture'],
        expected_instruction=R.proof.office_instruction(R.OFFICE_FILTER.read_bytes()),
        secrets=secrets, no_credentials=T.snapshots.no_credentials)


def test_diagnostic_retains_complete_actual_native_priority_channels_without_auth_secrets_or_mutation(component, monkeypatch):
    data = scenario(component, monkeypatch)
    instruction = R.proof.office_instruction(R.OFFICE_FILTER.read_bytes())
    developer, = component.router['convert_to_responses_payload']({'messages': [
        {'role': 'developer', 'content': instruction}]})['input']
    for call in data['capture']['requests'][:3]:
        for body in (call['body'], call['body_after_auth']):
            body.pop('instructions'); body['input'].insert(0, copy.deepcopy(developer))
        call.update(native_auth_key_hash='private-native-key-hash', debug_inventory={'password': 'private-raw-owner'})
    for row in data['provider']['requests'][:3]:
        row['body'].pop('instructions'); row['body']['input'].insert(0, copy.deepcopy(developer))
        row['private_headers'] = {'Authorization': 'Bearer sk-' + 'x' * 32}
    original = copy.deepcopy(data)
    result = diagnostic(data, secrets=('private-native-key-hash', 'private-raw-owner'))
    assert result['passed'] is True and result['validation_passed'] is False and result['native_office_accepted'] is False
    assert result['expected_instruction'] == instruction
    assert len(result['auth_observations']) == len(result['provider_observations']) == 4
    for actual, raw in zip(result['auth_observations'], data['capture']['requests']):
        assert actual['before_auth'] == R.proof.responses_projection(raw['body'])
        assert actual['after_auth'] == R.proof.responses_projection(raw['body_after_auth'])
    first = result['auth_observations'][0]['instruction_channels']['before_auth']
    assert first['instructions'] == {'present': False, 'value': None}
    assert first['input_messages'][0] == developer
    for actual, raw in zip(result['provider_observations'], data['provider']['requests']):
        assert actual['request'] == R.proof.responses_projection(raw['body'])
        assert actual['response']['output'] == raw['response']['output']
    public = json.dumps(result)
    assert all(s not in public for s in ('private-native-key-hash', 'private-raw-owner', 'Authorization', 'sk-' + 'x' * 32))
    assert data == original


@pytest.mark.parametrize('change,code', [('credential', None), ('opaque_password', None),
    ('foreign', 'office_diagnostic_synthetic_model'), ('count', 'office_diagnostic_count'),
    ('prior', 'office_diagnostic_prior_context'), ('aggregate', 'office_diagnostic_bound')])
def test_diagnostic_refuses_unsafe_or_incomplete_aggregate_without_truncating(component, monkeypatch, change, code):
    data = scenario(component, monkeypatch)
    if change == 'credential': data['capture']['requests'][0]['body_after_auth']['instructions'] = 'sk-' + 'x' * 32
    elif change == 'opaque_password': data['provider']['requests'][0]['body']['instructions'] = 'not-a-shaped-private-password'
    elif change == 'foreign': data['provider']['requests'][0]['body']['model'] = 'foreign-model'
    elif change == 'count': data['provider']['requests'] *= 3
    elif change == 'prior': data['before']['capture']['requests'] = [{'prior': 'must remain'}]
    else:
        # Each request remains below the existing observer's individual bound;
        # repeated complete projections must still obey the aggregate cap.
        for row in data['provider']['requests']: row['body']['instructions'] = 'x' * (300 * 1024)
    original = copy.deepcopy(data)
    with pytest.raises((N.ProofError, RuntimeError)) as failure:
        diagnostic(data, secrets=('not-a-shaped-private-password',))
    if code: assert str(failure.value) == code
    assert 'sk-' + 'x' * 32 not in str(failure.value) and 'not-a-shaped-private-password' not in str(failure.value)
    assert data == original


def test_diagnostic_cli_reuses_actual_collector_context_io_without_inventory_or_private_writes(component, monkeypatch, capsys):
    data = scenario(component, monkeypatch)
    office = data['office']; office.update(stage='setup_complete', office_service_setup={'stage': 'readback_ready'})
    office['users'][0].update(token='opaque-private-user-token', password='opaque-private-password')
    common = {'schema': 1, 'started_at_utc': '2026-11-05T10:01:00+00:00'}
    operator = {'started_at': '2026-11-05T10:00:00+00:00', 'operator_token': 'opaque-private-operator-token'}
    inputs = {R.COMMON: common, R.OFFICE: office, R.STATE: data['before'], 'operator': operator}
    before = copy.deepcopy(inputs); reads = []
    def read(path): reads.append(path); return copy.deepcopy(inputs[path])
    def unexpected(*args, **kwargs): raise AssertionError('No diagnostic inventory or mutation allowed')
    d = dict(OPERATOR_STATE='operator', read_private=read, write_private=unexpected,
        native_client=lambda state: SimpleNamespace(), provider=lambda: copy.deepcopy(data['provider']),
        no_credentials=T.snapshots.no_credentials, private_credentials=T.snapshots.private_credentials,
        capture=SimpleNamespace(capture_lock=nullcontext, _read_locked=lambda: copy.deepcopy(data['capture'])))
    monkeypatch.setattr(R, 'inventory', unexpected); monkeypatch.setattr(R, 'dependencies', lambda: d)
    monkeypatch.setattr('sys.argv', ['prove_office_readback.py', '--phase', 'diagnostic'])
    assert R.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result['phase'] == 'diagnostic' and result['passed'] is True and result['validation_passed'] is False
    assert inputs == before and reads == [R.COMMON, R.OFFICE, 'operator', R.STATE]
    assert len(result['auth_observations']) == len(result['provider_observations']) == 4
    assert 'opaque-private' not in json.dumps(result)


@pytest.mark.parametrize('artifact_available', [False, True])
@pytest.mark.parametrize('diagnostic_available', [False, True])
@pytest.mark.parametrize('already_collected', [False, True])
def test_workflow_diagnostic_runs_before_verify_and_failure_collection_preserves_original_error(diagnostic_available, already_collected, artifact_available):
    workflow = yaml.safe_load((T.ROOT / '.github/workflows/goal584-office-proof.yml').read_bytes())
    step = next(s for s in workflow['jobs']['office-build-proof']['steps']
                if s.get('name', '').startswith('Prepare Office and verify'))
    code = step['run'].split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
    assert code.index("readback('diagnostic')") < code.index("financial=readback('verify')")
    tree = ast.parse(code); failure = next(n for n in tree.body if isinstance(n, ast.Try))
    # Inject only the failed external qualification operation; execute the real
    # workflow except body, including its best-effort diagnostic coordinator.
    failure.body = [ast.parse("raise ProofError('office_system_context')").body[0]]
    prior = {'complete_actual_wire': 'preserve'}
    collected, calls = ({'office-diagnostic': copy.deepcopy(prior)} if already_collected else {}), []
    def readback(phase):
        calls.append(phase)
        if not diagnostic_available: raise N.ProofError('office_diagnostic_bound')
        return {'passed': True}
    def artifacts():
        if not artifact_available: raise N.ProofError('office_artifact_unavailable')
        return {'docx_sha256': 'a' * 64, 'png_sha256': 'b' * 64}
    namespace = dict(ProofError=N.ProofError, stage='native_finance', readback=readback, artifacts=artifacts,
        wire_diagnostic_collected=already_collected,
        fixture=SimpleNamespace(secrets=[]), no_credentials=T.snapshots.no_credentials,
        public=lambda name, value: collected.update({name: value}))
    with pytest.raises(SystemExit) as stopped:
        exec(compile(ast.Module(body=[failure], type_ignores=[]), 'actual-workflow-failure-handler', 'exec'), namespace)
    assert stopped.value.code == 1 and calls == ([] if already_collected else ['diagnostic'])
    if already_collected: assert collected['office-diagnostic'] == prior
    result = collected['office-native']
    assert result['passed'] is False and result['failure'] == 'office_system_context'
    assert result['stage'] == 'native_finance' and result['wire_diagnostic_collected'] is (already_collected or diagnostic_available)
    assert result['artifact_diagnostic_collected'] is artifact_available
    assert ('office-artifact' in collected) is artifact_available


class HttpResult:
    code, headers = 200, {}
    def __init__(self, payload): self.raw = json.dumps(payload).encode()
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, limit): return self.raw[:limit]


def test_native_api_inventory_preserves_all_payers_keys_raw_zero_rows_and_ignores_only_activity_fields():
    actor, payer, old = (str(uuid4()) for _ in range(3))
    def user(uid): return {'user_id': uid, 'user_role': 'internal_user', 'models': [], 'max_budget': 1000,
        'spend': 0, 'budget_duration': '30d', 'budget_reset_at': '2026-12-01', 'last_active': 'before'}
    def key(uid, token): return {'user_id': uid, 'token': token, 'models': ['gpt-6-luna' if uid == payer else R.proof.MODEL],
        'key_alias': token, 'max_budget': 1000, 'spend': 0, 'budget_duration': '30d', 'budget_reset_at': '2026-12-01', 'updated_at': 'before'}
    people = {uid: user(uid) for uid in (actor, payer, old)}
    keys = {actor: [key(actor, 'a' * 64)], payer: [key(payer, 'b' * 64)], old: [key(old, 'c' * 64), key(old, 'd' * 64)]}
    calls = []
    class Opener:
        def open(self, request, timeout):
            path = urlsplit(request.full_url); query = parse_qs(path.query); calls.append((path.path, query))
            assert request.get_method() == 'GET'
            if path.path == '/user/list': return HttpResult({'users': [{'user_id': uid} for uid in people], 'page': 1, 'total': 3, 'total_pages': 1})
            uid = query['user_id'][0]
            if path.path == '/key/list': return HttpResult({'keys': keys[uid], 'current_page': 1, 'total_count': len(keys[uid]), 'total_pages': 1})
            if path.path == '/user/info': return HttpResult({'user_info': people[uid], 'keys': keys[uid]})
            assert path.path == '/spend/logs/v2'
            return HttpResult({'data': [{'user': uid, 'request_id': 'retained-zero', 'spend': 0, 'raw_private_metadata': {'keep': True}}]
                if uid == old else [], 'total_pages': 1})
    native = N.NativeProof('http://127.0.0.1:4000', 'synthetic-test-management', 5, {}); native.opener = Opener()
    office = {'users': [{'id': actor}], 'service_fixture': {'payer_id': payer, 'key_hash': 'b' * 64},
        'office_setup': {'budget': {'models': [{'key_hash': 'a' * 64}]}}}
    first = R.inventory(native, office)
    assert len(first['raw_owners']) == 3 and len(first['raw_owners'][old]['keys']) == 2
    assert first['primary']['old_payers'][old]['rows'][0]['raw_private_metadata'] == {'keep': True}
    assert all('start_date' in query and 'end_date' in query for path, query in calls if path == '/spend/logs/v2')
    people[old]['last_active'] = 'after'
    keys[old][0]['updated_at'] = 'after'
    second = R.inventory(native, office)
    assert first['raw_owners'] != second['raw_owners']
    assert first['primary']['old_payers'] == second['primary']['old_payers']
    keys[old][0]['max_budget'] = 2000
    assert first['primary']['old_payers'] != R.inventory(native, office)['primary']['old_payers']
