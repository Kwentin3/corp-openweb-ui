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
from test_office_compatibility import saved_continuation, saved_context_owners


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
    observed, wire_owner, finance_owner = {}, R.wire_calls, R.proof.verify_service_finance
    def calls(*args):
        result = wire_owner(*args); observed['dispatch'] = result[1]; return result
    def finance(*args, **kwargs):
        assert kwargs['dispatch'] is observed['dispatch']
        return finance_owner(*args, **kwargs)
    monkeypatch.setattr(R, 'wire_calls', calls)
    monkeypatch.setattr(R.proof, 'verify_service_finance', finance)
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
    elif change == 'service_binding':
        partial['service']['rows'][-1]['request_id'] = data['provider']['requests'][-1]['id']
        partial['service']['rows'][-1]['metadata']['spend_logs_metadata']['owui_budget']['call_id'] = str(uuid4())
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
            assert public['binding_diagnostic']['scope'] != public['binding_diagnostic']['verified_scope']
            assert set(public['binding_atoms']) == R.proof.SERVICE_BINDING_ATOMS
            assert not public['binding_atoms']['scope_equal'] and not public['binding_atoms']['decoded_model']
            assert public['binding_atoms']['native_id_binding'] and public['binding_atoms']['opaque_log_id']


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
    atoms = dict.fromkeys(R.proof.SERVICE_BINDING_ATOMS, True); atoms['decoded_model'] = False
    error.office_service_binding_atoms = atoms
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
    assert result['binding_atoms'] == atoms
    if unsafe:
        assert result['binding_diagnostic_suppression_stage'] == ('size' if unsafe == 'oversize' else 'credential_check')
    assert result.get('binding_diagnostic') == (binding if unsafe is None else None)
    assert 'opaque-private-password' not in json.dumps(result) and 'sk-' + 'x' * 32 not in json.dumps(result)


@pytest.mark.parametrize('invalid_atoms', [False, True])
def test_cli_binding_atoms_survive_private_read_failure_and_reject_nonboolean_payload(monkeypatch, capsys, invalid_atoms):
    error = N.ProofError('office_service_dispatch_binding'); error.office_service_binding = {'decoded': {'model_id': None}}
    atoms = dict.fromkeys(R.proof.SERVICE_BINDING_ATOMS, False)
    if invalid_atoms: atoms['decoded_model'] = 'sk-' + 'x' * 32
    error.office_service_binding_atoms = atoms
    def unreadable(path): raise OSError('private filesystem detail must remain private')
    d = dict(OPERATOR_STATE='operator', read_private=unreadable,
        private_credentials=T.snapshots.private_credentials, no_credentials=T.snapshots.no_credentials)
    monkeypatch.setattr(R, 'dependencies', lambda: d)
    def fail(*args): raise error
    monkeypatch.setattr(R, 'run', fail)
    monkeypatch.setattr('sys.argv', ['prove_office_readback.py', '--phase', 'verify'])
    assert R.main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result['binding_diagnostic_collected'] is False and result['binding_diagnostic_suppression_stage'] == 'private_read'
    assert result.get('binding_atoms') == (None if invalid_atoms else atoms)
    assert 'private filesystem detail' not in json.dumps(result) and 'sk-' + 'x' * 32 not in json.dumps(result)


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


@pytest.mark.parametrize('mutation', ('valid', 'missing', 'extra', 'nonbool', 'all_true', 'wrong_failure'))
def test_main_exposes_only_bounded_saved_history_failure_booleans(monkeypatch, capsys, mutation):
    atoms = dict.fromkeys(R.proof.SAVED_HISTORY_ATOMS, True)
    atoms['native_saved_join_match'] = False
    code = 'office_saved_provider_history'
    if mutation == 'missing': atoms.pop('native_saved_has_eight_items')
    elif mutation == 'extra': atoms['private_db_value'] = 'do-not-export'
    elif mutation == 'nonbool': atoms['native_saved_join_match'] = 0
    elif mutation == 'all_true': atoms['native_saved_join_match'] = True
    elif mutation == 'wrong_failure': code = 'office_saved_full_context'
    error = N.ProofError(code); error.office_saved_history_atoms = atoms
    def fail(*args): raise error
    monkeypatch.setattr(R, 'dependencies', lambda: {})
    monkeypatch.setattr(R, 'run', fail)
    monkeypatch.setattr('sys.argv', ['prove_office_readback.py', '--phase', 'continuation-verify'])
    assert R.main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result['passed'] is False and result['failure_code'] == code
    assert result.get('saved_history_atoms') == (atoms if mutation == 'valid' else None)
    assert 'do-not-export' not in json.dumps(result)


def continuation_capture(call):
    """HTTP/auth observation leaf; the actual domain validators remain real."""
    return {'body': copy.deepcopy(call['wire_before_auth']), 'body_after_auth': copy.deepcopy(call['wire_after_auth']),
        'native_auth_user_id': call['auth_user_id'], 'native_auth_key_hash': call['auth_key_hash'],
        'attestation_present_before': call['attestation_present_before'], 'provenance_removed_after': call['provenance_removed_after'],
        'route': call['route'], 'verified_cost_scope': copy.deepcopy(call['verified_cost_scope'])}


def continuation_service(component, native, monkeypatch, *, actor, payer, key_hash, chat, messages):
    """Existing native task/Pipe/router and actual memory Handler, no listener."""
    import test_office_provider as provider_owner
    original_spec = provider_owner.importlib.util.spec_from_file_location
    native_ids = T.NATIVE / 'utils/model_ids.py'
    assert native_ids.read_bytes().replace(b'\r\n', b'\n') == T.subprocess.check_output(['git', '-C', str(T.NATIVE.parents[1]),
        'show', '6a18585ff4c2e5f6805f682222cfbc46dc669ef8:backend/open_webui/utils/model_ids.py'])
    def cached_spec(name, *args, **kwargs):
        spec = original_spec(name, *args, **kwargs)
        if name == 'office_service_pipe_fixture':
            load = spec.loader.exec_module
            def execute(module):
                load(module)
                module.prefix_owner = module.load('native_model_ids_for_service_test', native_ids)
            spec.loader.exec_module = execute
        return spec
    def send(wire):
        statuses, raw = provider_owner.memory_office_response(wire)
        assert statuses == [200]
        response = json.loads(raw); provider_owner.http_owner.Response.model_validate(response)
        return provider_owner.http_owner.native_parsers()['convert_responses_result'](copy.deepcopy(response))
    with monkeypatch.context() as leaf:
        leaf.setattr(provider_owner.importlib.util, 'spec_from_file_location', cached_spec)
        result, wires, _ = provider_owner.native_service_request(native, send, messages=messages)
    assert len(wires) == 1
    physical = copy.deepcopy(provider_owner.P.REQUESTS[-1]); wire = dict(wires[0], model='gpt-6-luna')
    secret = 'synthetic-readback-service-gateway-secret'
    claims = T.provenance.decode_service_call(T.provenance.encode_service_call(secret, user_id=actor, payer_id=payer,
        chat_id=chat, model='gpt-6-luna', task='follow_up_generation'), secret, user_id=actor, model='gpt-6-luna', task='follow_up_generation')
    scope = {'schema': 1, 'category': 'service', 'user_id': payer, 'actor_id': actor, 'chat_id': chat,
        'model': 'gpt-6-luna', 'task': 'follow_up_generation', 'call_id': claims['jti']}
    call = {'provider': physical, 'wire_before_auth': wire, 'wire_after_auth': copy.deepcopy(wire),
        'verified_cost_scope': scope, 'auth_user_id': payer, 'auth_key_hash': key_hash,
        'attestation_present_before': True, 'provenance_removed_after': True, 'route': '/responses'}
    followups = json.loads(result['choices'][0]['message']['content'])['follow_ups']
    return call, followups


@pytest.fixture
def continuation_case(component, native, monkeypatch, request):
    """Actual native/domain work over explicit HTTP, auth and private-DB leaves.

    The prepared objects are component inputs. They prove no actual DB, browser
    or auth origin; no checker is replaced with a success-returning fake.
    """
    import test_office_fixture as context
    packets = []; real_context = context.office.OfficeFixture.native_context
    def observe(self, *args, **kwargs):
        packet = real_context(self, *args, **kwargs); packets.append(copy.deepcopy(packet)); return packet
    monkeypatch.setattr(context.office.OfficeFixture, 'native_context', observe)
    case = request.getfixturevalue('saved_continuation')
    assert len(packets) == 3 and packets[1] == case.kwargs['native_saved'] and packets[2] == case.kwargs['native_final']
    seed = scenario(component, monkeypatch)
    _, one_after, _ = T.continuation_financial_fixture(component, monkeypatch)
    actor, chat = case.kwargs['actor'], case.kwargs['chat_id']
    previous = case.kwargs['first_calls'][0]['verified_cost_scope']['answer_id']; answer = case.kwargs['answer_id']
    payer = seed['office']['service_fixture']['payer_id']; file_id = case.artifact['native_file_id']; user = str(uuid4())
    first_messages = [{'role': 'user', 'content': 'Prepare the complete original proposal.'}, {'role': 'assistant', 'content': R.proof.SOURCE},
        {'role': 'user', 'content': R.proof.USER_REQUEST}, {'role': 'assistant', 'content': '[Download](/api/v1/files/' + file_id + '/content)'}]
    service_first, follow_first = continuation_service(component, native, monkeypatch, actor=actor, payer=payer,
        key_hash='b' * 64, chat=chat, messages=first_messages)
    service_next, follow_next = continuation_service(component, native, monkeypatch, actor=actor, payer=payer,
        key_hash='b' * 64, chat=chat, messages=first_messages + [{'role': 'user', 'content': R.proof.CONTINUATION_REQUEST},
            {'role': 'assistant', 'content': case.call['provider']['response']['output'][-1]['content'][0]['text']}])
    office = copy.deepcopy(seed['office']); office['users'][0].update(id=actor, token='opaque-private-readback-user-token')
    office.update(stage='setup_complete', office_service_setup={'stage': 'readback_ready'})
    office['office_setup']['budget'] = {'models': [{'key_hash': case.kwargs['key_hash']}]}
    office['service_fixture']['key_hash'] = 'b' * 64
    assert R.proof.digest(office['office_setup']['openapi']) == case.kwargs['native_source_sha256']
    def row(template, call, deployment):
        value = copy.deepcopy(template); scope = call['verified_cost_scope']; service = scope['category'] == 'service'
        value.update(request_id='resp_' + T.base64.b64encode(('litellm:custom_llm_provider:openai;model_id:' + deployment
            + ';response_id:' + call['provider']['id']).encode()).decode(), user=call['auth_user_id'], api_key=call['auth_key_hash'],
            model='openai/' + call['provider']['response']['model'], model_id=deployment,
            model_group='gpt-6-luna' if service else R.proof.MODEL, session_id=('owui-service:' if service else '') + chat)
        value['metadata']['spend_logs_metadata']['owui_budget'] = copy.deepcopy(scope)
        return value
    initial = {k: copy.deepcopy(seed['before']['finance'][k]) for k in ('primary', 'service')}
    for owner, uid, token in (('primary', actor, case.kwargs['key_hash']), ('service', payer, 'b' * 64)):
        initial[owner]['user']['user_id'] = initial[owner]['key']['user_id'] = uid; initial[owner]['key']['token'] = token
        for item in initial[owner]['rows']: item['user'] = uid
    phases = [copy.deepcopy(initial) for _ in range(3)]
    for slot in (1, 2):
        phases[slot]['primary']['rows'] += [row(one_after['rows'][-1], call, 'goal584-office-primary') for call in case.kwargs['first_calls']]
        phases[slot]['service']['rows'].append(row(seed['after']['service']['rows'][-1], service_first, 'goal584-office-service'))
        phases[slot]['primary']['user']['spend'] = phases[slot]['primary']['key']['spend'] = .60
        phases[slot]['service']['user']['spend'] = phases[slot]['service']['key']['spend'] = .20
    phases[2]['primary']['rows'].append(row(one_after['rows'][-1], case.call, 'goal584-office-primary'))
    phases[2]['service']['rows'].append(row(seed['after']['service']['rows'][-1], service_next, 'goal584-office-service'))
    phases[2]['primary']['user']['spend'] = phases[2]['primary']['key']['spend'] = .80
    phases[2]['service']['user']['spend'] = phases[2]['service']['key']['spend'] = .40
    old = str(uuid4()); old_user = dict(initial['primary']['user'], user_id=old, spend=4)
    old_keys = [dict(initial['primary']['key'], user_id=old, token=letter * 64, spend=4) for letter in ('c', 'd')]
    backend = SimpleNamespace(phase=0, calls=[], phases=phases)
    class Opener:
        def open(self, req, timeout):
            uri = urlsplit(req.full_url); query = parse_qs(uri.query); backend.calls.append((req.get_method(), uri.path, query))
            assert req.get_method() == 'GET'
            owners = {actor: backend.phases[backend.phase]['primary'], payer: backend.phases[backend.phase]['service']}
            if uri.path == '/user/list': return HttpResult({'users': [{'user_id': uid} for uid in (*owners, old)], 'page': 1, 'total': 3, 'total_pages': 1})
            uid = query['user_id'][0]
            keys = old_keys if uid == old else [owners[uid]['key']]
            if uri.path == '/key/list': return HttpResult({'keys': keys, 'current_page': 1, 'total_count': len(keys), 'total_pages': 1})
            if uri.path == '/user/info': return HttpResult({'user_info': old_user if uid == old else owners[uid]['user'], 'keys': keys})
            assert uri.path == '/spend/logs/v2'
            return HttpResult({'data': [{'user': old, 'request_id': 'retained-other-zero', 'spend': 0, 'opaque': {'keep': True}}]
                if uid == old else owners[uid]['rows'], 'total_pages': 1})
    native_owner = N.NativeProof('http://127.0.0.1:4000', 'opaque-private-native-operator', 2, {}); native_owner.opener = Opener()
    from datetime import datetime
    native_owner.started_at = datetime.fromisoformat('2026-11-05T09:59:00+00:00')
    finances = []
    for index in range(3): backend.phase = index; finances.append(R.inventory(native_owner, office))
    first_calls = case.kwargs['first_calls']; first_provider = {'requests': [*[copy.deepcopy(c['provider']) for c in first_calls], service_first['provider']]}
    first_capture = {'requests': [*[continuation_capture(c) for c in first_calls], continuation_capture(service_first)]}
    provider = {'requests': first_provider['requests'] + [copy.deepcopy(case.call['provider']), service_next['provider']]}
    capture = {'requests': first_capture['requests'] + [continuation_capture(case.call), continuation_capture(service_next)]}
    first_browser = dict(seed['browser'], chat_id=chat, answer_id=previous, file_id=file_id,
        source_message_id=case.artifact['source_message_id'])
    source_id = first_browser['source_message_id']; original_user = 'original-office-user'
    saved_before = {'id': chat, 'user_id': actor, 'chat': {'models': [R.proof.MODEL], 'history': {'currentId': previous, 'messages': {
        source_id: {'id': source_id, 'role': 'assistant', 'content': R.proof.SOURCE},
        original_user: {'id': original_user, 'role': 'user', 'content': R.proof.USER_REQUEST, 'parentId': source_id},
        previous: {'id': previous, 'role': 'assistant', 'model': R.proof.MODEL, 'content': first_messages[-1]['content'],
            'parentId': original_user, 'done': True, 'childrenIds': [], 'followUps': follow_first, 'output': copy.deepcopy(case.kwargs['saved_output'])}}}}}
    saved = copy.deepcopy(saved_before); history = saved['chat']['history']; history['currentId'] = answer
    history['messages'][previous]['childrenIds'] = [user]
    history['messages'][user] = {'id': user, 'role': 'user', 'content': R.proof.CONTINUATION_REQUEST, 'parentId': previous, 'childrenIds': [answer]}
    history['messages'][answer] = {'id': answer, 'role': 'assistant', 'model': R.proof.MODEL, 'parentId': user, 'done': True,
        'content': first_messages[-1]['content'], 'output': copy.deepcopy(case.call['provider']['response']['output']), 'followUps': follow_next,
        'statusHistory': [{'action': 'employee_budget_cost', 'done': True, 'description': 'Ответ: $0.20 · Чат: $0.80 · на 10:00:00 UTC'}]}
    sent = {'id': answer, 'model': R.proof.MODEL, 'chat_id': chat, 'parent_id': previous, 'stream': True,
        'user_message': copy.deepcopy(history['messages'][user]),
        'message_ids': [{'model_id': R.proof.MODEL, 'message_id': answer, 'modelIdx': 0}],
        'background_tasks': {'follow_up_generation': True}}
    ack = {'chat_id': chat, 'status': True}
    browser = {'schema': 1, 'actor_id': actor, 'chat_id': chat, 'first_answer_id': previous, 'file_id': file_id,
        'http_status': 200, 'submission': sent, 'acknowledgement': ack, 'raw_submission': json.dumps(sent),
        'raw_acknowledgement_base64': T.base64.b64encode(json.dumps(ack).encode()).decode(), 'task_ids': [],
        'baseline_chat': copy.deepcopy(saved_before), 'reloaded_before': copy.deepcopy(saved_before),
        'stored_chat': copy.deepcopy(saved), 'reloaded_after': copy.deepcopy(saved)}
    state = dict(seed['before'], schema=1, stage='verified_readback', prepared_sha256=R.proof.digest(office),
        history_start_utc=native_owner.started_at.isoformat(), finance=finances[0], after=finances[1],
        provider={'requests': []}, capture={'requests': []}, provider_after=first_provider, capture_after=first_capture,
        saved_chat=saved_before, browser=first_browser, native_context=packets[0])
    assert R.verify(state, finances[1], first_provider, first_capture, saved_before, first_browser, packets[0], office, seed['d'])['provider_calls'] == 4
    state['continuation_baseline'] = {'schema': 1, 'stage': 'baseline', 'saved_chat': saved_before,
        'finance': finances[1], 'provider': first_provider, 'capture': first_capture}
    backend.phase = 2
    return SimpleNamespace(state=state, after=finances[2], provider=provider, captured=capture, saved=saved,
        browser=browser, packets={'schema': 1, 'saved': packets[1], 'final': packets[2]}, office=office, d=seed['d'],
        native=native_owner, backend=backend, saved_before=saved_before, first_provider=first_provider, first_capture=first_capture,
        factory=__import__('test_office_provider').P, finances=finances)


def test_continuation_readback_joins_actual_native_factory_context_inventory_scope_rates_and_sdk(continuation_case):
    case = continuation_case
    original = copy.deepcopy((case.state, case.after, case.provider, case.captured, case.saved, case.browser, case.packets))
    dispatches = copy.deepcopy(case.factory.REQUESTS)
    result = R.verify_continuation(case.state, case.after, case.provider, case.captured, case.saved, case.browser, case.packets, case.office, case.d)
    assert result['primary'] == result['service'] == {'physical_calls': 1, 'new_raw_rows': 1, 'native_spend_delta_usd': '.20'}
    assert result['provider_calls'] == 2 and result['saved_chat_verified'] is True
    assert (case.state, case.after, case.provider, case.captured, case.saved, case.browser, case.packets) == original
    assert case.factory.REQUESTS == dispatches and all(method == 'GET' for method, _, _ in case.backend.calls)


def test_continuation_readback_rejects_coherent_raw_fields_context_rows_caps_and_extra_dispatch(continuation_case):
    case = continuation_case
    names = ['raw_submission', 'raw_ack', 'submitted_parent', 'submitted_user_parent', 'submitted_model', 'submitted_chat',
        'submitted_content', 'submitted_stream', 'submitted_old_answer', 'submitted_selection', 'submitted_task',
        'saved_parent', 'browser_history', 'nonce', 'opaque', 'native_source', 'native_echo', 'primary_row', 'old_row',
        'primary_cap', 'service_row', 'service_scope', 'extra_provider', 'extra_capture', 'prior_provider']
    for name in names:
        data = copy.deepcopy({k: getattr(case, k) for k in ('state', 'after', 'provider', 'captured', 'saved', 'browser', 'packets')})
        browser, saved, captured = data['browser'], data['saved'], data['captured']
        sent = browser['submission']; user = sent['user_message']['id']; answer = sent['id']
        added = {owner: next(row for row in data['after'][owner]['rows'] if row['request_id'] not in {
            old['request_id'] for old in data['state']['continuation_baseline']['finance'][owner]['rows']}) for owner in ('primary', 'service')}
        if name == 'raw_submission': browser['raw_submission'] = json.dumps(dict(sent, parent_id='forged'))
        elif name == 'raw_ack': browser['raw_acknowledgement_base64'] = T.base64.b64encode(json.dumps({'chat_id': str(uuid4())}).encode()).decode()
        elif name.startswith('submitted_'):
            if name == 'submitted_parent': sent['parent_id'] = str(uuid4())
            elif name == 'submitted_user_parent': sent['user_message']['parentId'] = str(uuid4())
            elif name == 'submitted_model': sent['model'] = 'foreign-model'
            elif name == 'submitted_chat': sent['chat_id'] = str(uuid4())
            elif name == 'submitted_content': sent['user_message']['content'] = 'different second turn'
            elif name == 'submitted_stream': sent['stream'] = False
            elif name == 'submitted_old_answer': sent['id'] = browser['first_answer_id']
            elif name == 'submitted_selection': sent['message_ids'][0]['message_id'] = str(uuid4())
            else: sent['background_tasks']['follow_up_generation'] = False
            browser['raw_submission'] = json.dumps(sent)  # Coherent parsed/raw damage must still reject.
        elif name == 'saved_parent': saved['chat']['history']['messages'][user]['parentId'] = str(uuid4())
        elif name == 'browser_history': browser['reloaded_after']['chat']['history']['messages'][answer]['content'] = 'forged reload'
        elif name == 'nonce': captured['requests'][-2]['verified_cost_scope']['call_id'] = captured['requests'][0]['verified_cost_scope']['call_id']
        elif name == 'opaque':
            before = data['state']['continuation_baseline']['saved_chat']['chat']['history']['messages'][browser['first_answer_id']]['output']
            groups = [before, data['packets']['saved']['saved_output_case']['input_saved_output'], data['packets']['saved']['saved_output_case']['native_input'],
                captured['requests'][-2]['body']['input'], captured['requests'][-2]['body_after_auth']['input'], data['provider']['requests'][-2]['body']['input']]
            groups += [chat['chat']['history']['messages'][browser['first_answer_id']]['output'] for chat in (
                saved, browser['baseline_chat'], browser['reloaded_before'], browser['stored_chat'], browser['reloaded_after'])]
            for items in groups: [v for v in items if v.get('type') == 'reasoning'][-1]['encrypted_content'] = 'coherently forged opaque'
        elif name == 'native_source': data['packets']['saved']['source_body_sha256'] = '0' * 64
        elif name == 'native_echo': data['packets']['final']['saved_output_case']['input_saved_output'] = []
        elif name == 'primary_row': added['primary']['spend'] = 0
        elif name == 'old_row': data['after']['primary']['rows'][0]['spend'] = 1
        elif name == 'primary_cap': data['after']['primary']['key']['max_budget'] = 99
        elif name == 'service_row': added['service']['spend'] = .60
        elif name == 'service_scope': captured['requests'][-1]['verified_cost_scope']['actor_id'] = str(uuid4())
        elif name == 'extra_provider': data['provider']['requests'].append(copy.deepcopy(data['provider']['requests'][-1]))
        elif name == 'extra_capture': captured['requests'].append(copy.deepcopy(captured['requests'][-1]))
        else: data['state']['continuation_baseline']['provider']['requests'][0]['body']['store'] = True
        try:
            R.verify_continuation(**data, office=case.office, d=case.d)
        except (N.ProofError, ValueError, KeyError):
            pass
        else:
            raise AssertionError('Damaged continuation boundary accepted: ' + name)


def continuation_cli(case, monkeypatch, tmp_path):
    """Private and HTTP leaves only; actual R.inventory, NativeProof.poll and P owners."""
    path = tmp_path / 'continuation-readback.private.json'; path.write_text(json.dumps(case.state))
    monkeypatch.setattr(R, 'STATE', path)
    world = SimpleNamespace(rounds=0, phases=[2], saved=None, writes=[], reads=[], path=path)
    common = {'started_at_utc': '2026-11-05T10:01:00+00:00'}
    operator = {'started_at': '2026-11-05T10:00:00+00:00', 'operator_token': 'opaque-private-readback-operator'}
    inputs = {R.COMMON: common, R.OFFICE: case.office, R.CONTINUATION_BROWSER: case.browser,
        R.CONTINUATION_CONTEXT: case.packets, 'operator': operator}
    def read(target):
        world.reads.append(target)
        return json.loads(path.read_text()) if target == path else copy.deepcopy(inputs[target])
    def write(target, value):
        assert target == path; world.writes.append(copy.deepcopy(value)); path.write_text(json.dumps(value))
    class WebUI:
        def ok(self, method, route, *, token):
            assert method == 'GET' and route == '/api/v1/chats/' + case.state['browser']['chat_id']
            assert token == case.office['users'][0]['token']
            case.backend.phase = world.phases[min(world.rounds, len(world.phases) - 1)]; world.rounds += 1
            return copy.deepcopy(world.saved if world.saved is not None else case.saved_before if case.backend.phase == 1 else case.saved)
    def provider(): return copy.deepcopy(case.first_provider if case.backend.phase == 1 else case.provider)
    def captured(): return copy.deepcopy(case.first_capture if case.backend.phase == 1 else case.captured)
    d = dict(case.d, OPERATOR_STATE='operator', read_private=read, write_private=write,
        native_client=lambda common: case.native, WebUI=WebUI, provider=provider,
        no_credentials=T.snapshots.no_credentials, private_credentials=T.snapshots.private_credentials,
        capture=SimpleNamespace(capture_lock=nullcontext, _read_locked=captured))
    monkeypatch.setattr(R, 'dependencies', lambda: d)
    def invoke(phase):
        world.rounds = 0; monkeypatch.setattr('sys.argv', ['prove_office_readback.py', '--phase', phase]); return R.main()
    world.invoke = invoke; world.d = d
    return world


def test_continuation_cli_baseline_verify_diagnostic_and_no_new_dispatch_preserve_original_phase(continuation_case, monkeypatch, tmp_path, capsys):
    case = continuation_case; world = continuation_cli(case, monkeypatch, tmp_path)
    state = copy.deepcopy(case.state); state.pop('continuation_baseline'); world.path.write_text(json.dumps(state))
    dispatches = copy.deepcopy(case.factory.REQUESTS); world.phases = [1]
    assert world.invoke('continuation-baseline') == 0
    public = json.loads(capsys.readouterr().out); accepted_baseline = json.loads(world.path.read_text())
    assert public['passed'] and public['inference_issued'] is False and public['native_office_accepted'] is False
    assert {k: accepted_baseline[k] for k in state} == state
    assert accepted_baseline['continuation_baseline']['finance'] == case.finances[1]
    world.phases = [2]
    assert world.invoke('continuation-verify') == 0
    public = json.loads(capsys.readouterr().out); final = json.loads(world.path.read_text())
    assert public['primary'] == public['service'] == {'physical_calls': 1, 'new_raw_rows': 1, 'native_spend_delta_usd': '.20'}
    assert public['provider_calls'] == 2 and public['native_office_accepted'] is public['live_filter_prepost_qualified'] is False
    assert {k: final[k] for k in state} == state and final['continuation_baseline'] == accepted_baseline['continuation_baseline']
    assert final['continuation_verified']['saved_chat'] == case.saved and 'continuation_last_observation' not in final
    writes = len(world.writes); before = world.path.read_bytes()
    assert world.invoke('continuation-diagnostic') == 0
    diagnostic = json.loads(capsys.readouterr().out)
    assert diagnostic['passed'] and diagnostic['validation_passed'] is False and len(diagnostic['provider_observations']) == 2
    assert len(world.writes) == writes and world.path.read_bytes() == before
    assert world.invoke('continuation-verify') == 1
    assert json.loads(capsys.readouterr().out)['failure_code'] == 'office_continuation_no_baseline'
    assert case.factory.REQUESTS == dispatches and all(method == 'GET' for method, _, _ in case.backend.calls)


def test_continuation_cli_retries_only_missing_rows_or_underconverged_counters_and_keeps_failures(continuation_case, monkeypatch, tmp_path, capsys):
    case = continuation_case; world = continuation_cli(case, monkeypatch, tmp_path)
    original = copy.deepcopy(case.state); dispatches = copy.deepcopy(case.factory.REQUESTS)
    cases = [('primary_rows', True), ('service_rows', True), ('primary_counter', True), ('service_counter', True),
        ('extra_row', False), ('counter_over', False), ('old_row', False), ('service_scope', False)]
    complete = copy.deepcopy(case.backend.phases[2])
    for change, waiting in cases:
        world.path.write_text(json.dumps(original)); world.writes.clear(); world.phases = [3, 2]
        partial = copy.deepcopy(complete)
        if change == 'primary_rows': partial['primary']['rows'].pop()
        elif change == 'service_rows': partial['service']['rows'].pop()
        elif change == 'primary_counter': partial['primary']['key']['spend'] = .60
        elif change == 'service_counter': partial['service']['user']['spend'] = .20
        elif change == 'extra_row': partial['primary']['rows'].append({'user': case.office['users'][0]['id'], 'request_id': 'unexpected-zero', 'spend': 0})
        elif change == 'counter_over': partial['primary']['user']['spend'] = .90
        elif change == 'old_row': partial['primary']['rows'][0]['spend'] = 1
        else: partial['service']['rows'][-1]['metadata']['spend_logs_metadata']['owui_budget']['call_id'] = str(uuid4())
        case.backend.phases[:] = case.backend.phases[:3] + [partial]
        status = world.invoke('continuation-verify'); public = json.loads(capsys.readouterr().out); private = json.loads(world.path.read_text())
        assert world.rounds == (2 if waiting else 1), change
        assert all(private[k] == original[k] for k in original), change
        assert 'opaque-private' not in json.dumps(public)
        if waiting:
            assert status == 0 and public['passed'] and private['continuation_verified']['stage'] == 'verified', (change, public, private.get('continuation_failure_code'))
            assert any('continuation_last_observation' in value for value in world.writes)
        else:
            assert status == 1 and not public['passed'] and 'continuation_verified' not in private, change
            assert private['continuation_last_observation']['provider'] == case.provider
            assert private['continuation_last_observation']['capture'] == case.captured
            assert private['continuation_last_observation']['after']['primary']['rows'] == sorted(partial['primary']['rows'], key=lambda r: r['request_id'])
    # A missing row that never arrives must time out, never become acceptance.
    partial = copy.deepcopy(complete); partial['primary']['rows'].pop()
    case.backend.phases[:] = case.backend.phases[:3] + [partial]; world.phases = [3]; world.path.write_text(json.dumps(original))
    case.native.timeout = .1
    assert world.invoke('continuation-verify') == 1
    public = json.loads(capsys.readouterr().out); private = json.loads(world.path.read_text())
    assert not public['passed'] and private['continuation_failure_code'] == 'office_row_count' and 'continuation_verified' not in private
    assert case.factory.REQUESTS == dispatches


def test_continuation_baseline_rejects_stale_state_and_retains_corrupt_original_native_reads(continuation_case, monkeypatch, tmp_path, capsys):
    case = continuation_case; world = continuation_cli(case, monkeypatch, tmp_path)
    original = copy.deepcopy(case.state); original.pop('continuation_baseline'); world.phases = [1]
    for field, value in (('stage', 'baseline'), ('prepared_sha256', '0' * 64), ('history_start_utc', '2020-01-01T00:00:00+00:00')):
        state = dict(original, **{field: value}); world.path.write_text(json.dumps(state)); reads = len(case.backend.calls)
        assert world.invoke('continuation-baseline') == 1
        assert json.loads(capsys.readouterr().out)['failure_code'] == 'office_continuation_prior_state'
        assert len(case.backend.calls) == reads and json.loads(world.path.read_text()) == state
    world.path.write_text(json.dumps(original)); case.backend.phases[1]['primary']['rows'][0]['spend'] = 1
    assert world.invoke('continuation-baseline') == 1
    public = json.loads(capsys.readouterr().out); private = json.loads(world.path.read_text())
    assert not public['passed'] and public['failure_code'] == 'office_old_row_changed'
    assert 'continuation_baseline' not in private and private['stage'] == 'verified_readback'
    retained_id = case.backend.phases[1]['primary']['rows'][0]['request_id']
    assert next(r for r in private['continuation_baseline_observation']['finance']['primary']['rows']
        if r['request_id'] == retained_id)['spend'] == 1
    assert private['continuation_baseline_observation']['provider'] == case.first_provider
    assert {k: private[k] for k in original} == original
    before = world.path.read_bytes(); writes = len(world.writes)
    assert world.invoke('continuation-diagnostic') == 1
    assert json.loads(capsys.readouterr().out)['failure_code'] == 'office_continuation_no_baseline'
    assert world.path.read_bytes() == before and len(world.writes) == writes
