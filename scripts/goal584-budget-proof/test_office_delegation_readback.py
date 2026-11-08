"""Offline actual-source/bytes checks; native HTTP is an explicit IO leaf."""
import copy
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4
from zipfile import ZipFile

import pytest

import prove_office_delegation_readback as R
import prove_native_budgets as N
from test_office_readback import HttpResult
import provision_webui as provision
import provenance


def prepared(actor, payer):
    return {'stage': 'setup_complete', 'office_service_setup': {'stage': 'readback_ready'},
        'service_fixture': {'payer_id': payer, 'key_hash': 'c' * 64},
        'office_delegation_setup': {'stage': 'readback_ready', 'actor': {'id': actor},
            'tool_valves': {'DEFAULT_MODEL': 'corporate-office-worker', 'APPLY_INLET_FILTERS': True},
            'budget': {'models': [{'model': m, 'key_hash': h * 64} for m, h in zip(R.MODELS, 'ab')]}}}


def native_io():
    actor, payer, old = [str(uuid4()) for _ in range(3)]
    def user(uid, cap):
        return dict(user_id=uid, user_role='internal_user', models=[], max_budget=cap, spend=0,
                    budget_duration='30d', budget_reset_at='2026-12-01')
    def key(uid, model, token):
        return dict(user_id=uid, models=[model], token=token, key_alias=token, max_budget=1000,
                    spend=0, budget_duration='30d', budget_reset_at='2026-12-01')
    people = {uid: user(uid, 2000 if uid == actor else 1000) for uid in (actor, payer, old)}
    keys = {actor: [key(actor, m, h * 64) for m, h in zip(R.MODELS, 'ab')],
            payer: [key(payer, 'gpt-6-luna', 'c' * 64)], old: [key(old, 'old-model', 'd' * 64)]}
    rows = {actor: [], payer: [], old: [dict(request_id='old-zero', user=old, spend=0, raw_metadata={'preserve': True})]}
    calls = []
    class Opener:
        def open(self, request, timeout):
            path = urlsplit(request.full_url); query = parse_qs(path.query); calls.append((path.path, query))
            assert request.get_method() == 'GET'
            if path.path == '/user/list':
                return HttpResult(dict(users=[{'user_id': u} for u in people], page=1, total=3, total_pages=1))
            uid = query['user_id'][0]
            if path.path == '/key/list': return HttpResult(dict(keys=keys[uid], current_page=1, total_count=len(keys[uid]), total_pages=1))
            if path.path == '/user/info': return HttpResult(dict(user_info=people[uid], keys=keys[uid]))
            assert path.path == '/spend/logs/v2'
            return HttpResult(dict(data=rows[uid], total_pages=1))
    native = N.NativeProof('http://127.0.0.1:4000', 'private-operator-IO-leaf', 3, {}); native.opener = Opener()
    return SimpleNamespace(native=native, office=prepared(actor, payer), people=people, keys=keys, rows=rows,
                           actor=actor, payer=payer, old=old, calls=calls)


def test_two_assignment_inventory_reuses_real_native_http_pagination_and_retains_zero_rows():
    data = native_io(); first = R.inventory(data.native, data.office)
    assert set(first['personal']) == set(R.MODELS)
    assert first['raw_owners'][data.old]['rows'] == data.rows[data.old]
    assert all('start_date' in q and 'end_date' in q for path, q in data.calls if path == '/spend/logs/v2')
    data.people[data.old]['last_active'] = 'new-native-activity'
    assert R.inventory(data.native, data.office)['personal'][R.MODELS[0]]['old_payers'] == first['personal'][R.MODELS[0]]['old_payers']
    data.keys[data.old][0]['spend'] = .01
    assert R.inventory(data.native, data.office)['personal'][R.MODELS[0]]['old_payers'] != first['personal'][R.MODELS[0]]['old_payers']


@pytest.mark.parametrize('mutation', ['extra_key', 'duplicate_key', 'foreign_assignment', 'user_cap', 'key_cap', 'unassigned_raw_zero'])
def test_inventory_fails_closed_for_wrong_native_assignment_or_hidden_rows(mutation):
    data = native_io()
    if mutation == 'extra_key': data.keys[data.actor].append({**data.keys[data.actor][0], 'token': 'e' * 64})
    elif mutation == 'duplicate_key': data.keys[data.actor].append(copy.deepcopy(data.keys[data.actor][0]))
    elif mutation == 'foreign_assignment': data.keys[data.actor][1]['models'] = ['gpt-6.1-sol']
    elif mutation == 'user_cap': data.people[data.actor]['max_budget'] = 2001
    elif mutation == 'key_cap': data.keys[data.actor][1]['max_budget'] = 1001
    else: data.rows[data.actor].append(dict(request_id='unowned-zero', api_key='e' * 64, user=data.actor, spend=0))
    with pytest.raises(N.ProofError): R.inventory(data.native, data.office)


def artifact_case(tmp_path, monkeypatch, mutation=None):
    source = provision.delegated_source_docx()
    result = BytesIO()
    with ZipFile(BytesIO(source)) as old, ZipFile(result, 'w') as new:
        for name in old.namelist():
            raw = old.read(name)
            if name == 'word/document.xml':
                raw = raw.replace(b'Employee: {{employee}}', b'Employee: Ada Example').replace(b'Case: {{case}}', b'Case: G584-2026')
                if mutation == 'missing_field': raw = raw.replace(b'G584-2026', b'UNKNOWN')
                if mutation == 'table': raw = raw.replace(b'FIXED TABLE', b'CHANGED TABLE')
            if name == 'word/footer1.xml' and mutation == 'footer': raw = raw.replace(b'synthetic only.', b'changed.')
            new.writestr(name, raw)
    raw = result.getvalue(); paths = {'browser': 'office-delegation-browser.docx', 'native': 'office-delegation-browser.native.docx'}
    for name in paths.values(): (tmp_path / name).write_bytes(raw)
    monkeypatch.setattr(R, 'PRIVATE', tmp_path)
    observation = {'paths': paths, 'artifacts': {k: {'sha256': R.sha256(raw).hexdigest(), 'bytes': len(raw)} for k in paths},
        'foreign_file_statuses': [404, 404], 'source_before': {'sha256': R.sha256(source).hexdigest(), 'bytes': len(source), 'status': 200},
        'source_after': {'sha256': R.sha256(source).hexdigest(), 'bytes': len(source), 'status': 200}}
    office = prepared('actor', 'payer'); office['office_delegation_setup']['source_sha256'] = R.sha256(source).hexdigest()
    return source, raw, observation, office


def test_artifact_check_compares_actual_zip_xml_fields_table_footer_and_both_downloads(tmp_path, monkeypatch):
    source, raw, observation, office = artifact_case(tmp_path, monkeypatch)
    assert R.verify_artifacts(observation, office, source) == {'sha256': R.sha256(raw).hexdigest(), 'bytes': len(raw)}


@pytest.mark.parametrize('mutation', ['missing_field', 'table', 'footer', 'source', 'browser_bytes', 'acl', 'path'])
def test_coherent_artifact_receipts_do_not_hide_source_or_preservation_defects(tmp_path, monkeypatch, mutation):
    source, raw, observation, office = artifact_case(tmp_path, monkeypatch, mutation)
    if mutation == 'source': observation['source_after']['sha256'] = '0' * 64
    elif mutation == 'browser_bytes':
        raw += b'changed-download'; (tmp_path / observation['paths']['browser']).write_bytes(raw)
        observation['artifacts']['browser'] = {'sha256': R.sha256(raw).hexdigest(), 'bytes': len(raw)}
    elif mutation == 'acl': observation['foreign_file_statuses'] = [200, 200]
    elif mutation == 'path': observation['paths']['native'] = '/outside/other.docx'
    with pytest.raises(N.ProofError): R.verify_artifacts(observation, office, source)


def wire_observations():
    groups = [(m, i) for m in (*R.MODELS, 'gpt-6-luna') for i in range(1 if m == 'gpt-6-luna' else 6)]
    captured, physical = [], []
    for model, index in groups:
        wire = {'model': model, 'input': [{'type': 'message', 'role': 'user', 'content': 'actual observed request ' + str(index)}], 'stream': model == R.MODELS[0]}
        target = R.WIRES.get(model, 'goal584-fake-office-service')
        body = R.proof.expected_provider_body(wire, target, provider_transport='buffered' if model == R.MODELS[0] else 'native')
        physical.append(dict(id='resp_' + uuid4().hex, body=body, lifecycle=dict(terminal=True, outcome='completed')))
        captured.append(dict(body=wire, body_after_auth=copy.deepcopy(wire), route='/responses',
            attestation_present_before=True, provenance_removed_after=True, native_auth_user_id='actor', native_auth_key_hash='a' * 64,
            verified_cost_scope={'call_id': str(uuid4())}))
    return {'requests': physical}, {'requests': captured}


def test_physical_dispatch_join_is_full_body_not_count_or_model_only():
    provider, capture = wire_observations()
    groups = R.calls({'provider': {'requests': []}, 'capture': {'requests': []}}, provider, capture)
    assert [len(groups[m]) for m in (*R.MODELS, 'gpt-6-luna')] == [6, 6, 1]


def test_public_single_join_retains_actual_auth_and_provider_for_another_responses_alias():
    provider, captured = wire_observations()
    row = captured['requests'][0]
    row['body']['model'] = row['body_after_auth']['model'] = 'goal584-usage'
    target = 'goal584-fake-usage'
    provider['requests'][0]['body'] = R.proof.expected_provider_body(row['body'], target, provider_transport='buffered')
    result = R.join_responses_call(row, provider['requests'], wire_model=target, provider_transport='buffered')
    assert result['wire_before_auth'] == row['body'] and result['provider']['id'] == provider['requests'][0]['id']
    assert result['verified_cost_scope'] == row['verified_cost_scope'] and result['auth_key_hash'] == 'a' * 64


@pytest.mark.parametrize('mutation', ['instructions', 'tool_result', 'duplicate', 'forged_auth', 'route'])
def test_public_single_join_does_not_repair_or_guess_context_and_auth(mutation):
    provider, captured = wire_observations(); row = captured['requests'][0]
    if mutation == 'instructions': row['body_after_auth']['instructions'] = 'different actual instructions'
    elif mutation == 'tool_result': provider['requests'][0]['body']['input'].append({'type': 'function_call_output', 'call_id': 'forged', 'output': '{}'})
    elif mutation == 'duplicate': provider['requests'].append(copy.deepcopy(provider['requests'][0]))
    elif mutation == 'forged_auth': row['auth_failure'] = {'status_code': 403}
    else: row['route'] = '/chat/completions'
    with pytest.raises(N.ProofError):
        R.join_responses_call(row, provider['requests'], wire_model=R.WIRES[R.MODELS[0]], provider_transport='buffered')


@pytest.mark.parametrize('mutation', ['missing_worker_capture', 'body', 'nonce', 'extra_provider', 'auth_failure', 'route', 'old_rewrite'])
def test_missing_or_coherently_unrelated_observations_do_not_prove_dispatch(mutation):
    provider, capture = wire_observations(); before = {'provider': {'requests': []}, 'capture': {'requests': []}}
    if mutation == 'missing_worker_capture': capture['requests'].pop(6)
    elif mutation == 'body': provider['requests'][6]['body']['input'][0]['content'] = 'lost source'
    elif mutation == 'nonce': capture['requests'][6]['verified_cost_scope'] = copy.deepcopy(capture['requests'][0]['verified_cost_scope'])
    elif mutation == 'extra_provider': provider['requests'].append(copy.deepcopy(provider['requests'][0]))
    elif mutation == 'auth_failure': capture['requests'][6]['auth_failure'] = {'status_code': 403}
    elif mutation == 'route': capture['requests'][6]['route'] = '/chat/completions'
    else: before['provider']['requests'] = [{'id': 'retained-original'}]
    with pytest.raises(N.ProofError): R.calls(before, provider, capture)


def native_cost_owner(monkeypatch):
    monkeypatch.setitem(sys.modules, 'employee_budget_provenance', provenance)
    path = Path(__file__).resolve().parents[2] / 'deploy/openwebui-budgets/cost_readback.py'
    spec = importlib.util.spec_from_file_location('delegated_test_actual_cost_readback', path)
    owner = importlib.util.module_from_spec(spec); monkeypatch.setitem(sys.modules, spec.name, owner); spec.loader.exec_module(owner)
    return owner


def test_saved_provisional_display_cannot_omit_worker_rows_or_reuse_old_amount(monkeypatch):
    owner = native_cost_owner(monkeypatch); actor, chat, answer = [str(uuid4()) for _ in range(3)]
    rows = [owner._Row('raw-' + str(i), str(uuid4()), answer, model, Decimal(spend), 10, 5, 15)
            for model, spend in zip(R.MODELS, ('.20', '.02')) for i in range(6)]
    total = owner._total(rows)
    snapshot = owner.CostSnapshot(actor, chat, answer, total, total, datetime.now(timezone.utc), False, True, ())
    description = 'Ответ: $1.32 · Чат: $1.32 · на 12:00:00 UTC · начислено на сейчас, учёт обновляется'
    final = {'statusHistory': [{'action': 'employee_budget_cost', 'done': True, 'description': description}]}
    assert R.verify_cost_status(final, snapshot, actor, chat, answer) is True
    final['statusHistory'][0]['description'] = description.replace('1.32', '1.20')
    with pytest.raises(N.ProofError, match='office_delegation_cost_status_amount'): R.verify_cost_status(final, snapshot, actor, chat, answer)
    partial = owner._total(rows[:6])
    snapshot = owner.CostSnapshot(actor, chat, answer, partial, partial, datetime.now(timezone.utc), True, False, (), missing_call_ids=('missing-worker',))
    with pytest.raises(N.ProofError, match='office_delegation_cost_snapshot'): R.verify_cost_status(final, snapshot, actor, chat, answer)


def test_cli_error_does_not_export_raw_private_exception(monkeypatch, capsys):
    monkeypatch.setattr(R, 'dependencies', lambda: (_ for _ in ()).throw(RuntimeError('private-token-with-source-content')))
    monkeypatch.setattr(sys, 'argv', ['readback', '--phase', 'verify'])
    assert R.main() == 1
    value = json.loads(capsys.readouterr().out)
    assert value['failure_code'] == 'office_delegation_readback_failed'
    assert 'private-token' not in json.dumps(value)


def context_case(monkeypatch, tmp_path):
    """Actual provider grammar, native Tasks and pinned serializer; Office IO leaves."""
    import io
    import test_mock_provider as provider_test
    import test_office_compatibility as native_test
    root = Path(__file__).resolve().parents[2]
    source = root.with_name('corp-openweb-ui-goal584') / 'local/goal584/cost-display/open-webui/backend/open_webui'
    monkeypatch.setenv('GOAL584_NATIVE_SOURCE_ROOT', str(source))
    provider_test.DelegatedProviderTests.setUpClass()
    # worker_history has already exercised the real native Task source. Its
    # Office replies are explicitly labelled CLI IO leaves, not accepted files.
    case = provider_test.DelegatedProviderTests(); case.setUp()
    worker_complete, _ = case.worker_history()
    worker_leaf_results = [r['output'] for r in worker_complete['input'] if r.get('type') == 'function_call_output']
    case = provider_test.DelegatedProviderTests(); case.setUp()
    workflow = (root / 'deploy/openwebui-skills/artifact-workflow.md').read_text(encoding='utf-8')
    case.parent['input'][0].update(role='developer', content=[{'type': 'input_text', 'text': workflow + '\n' + case.skill['id']}])
    case.parent.update(store=False, include=['reasoning.encrypted_content'])
    actor, chat, answer = [str(uuid4()) for _ in range(3)]
    office = prepared(actor, str(uuid4()))
    office['office_setup'] = {'workflow_skill': {'content': workflow}, 'openapi': {}}
    office['office_delegation_setup'].update(skill=case.skill, source_file={'id': case.source_id}, source_sha256=R.sha256(provision.delegated_source_docx()).hexdigest())
    with provider_test.patch.object(native_test, 'NATIVE', source):
        _, router, _ = native_test.native.__wrapped__()
    native_worker_tools = router['convert_to_responses_payload']({'messages': [], 'tools': [
        {'type': 'function', 'function': {k: v for k, v in s.items() if k != 'type'}} for s in case.office_tools]})['tools']
    # Use the same actual serializer/native schema owner as the runtime packet.
    # OpenAPI source digest is a separate bound input; no schema is guessed.
    office['office_setup']['openapi'] = native_test.create_app(native_test.CliIO()).openapi()
    physical = []; groups = {m: [] for m in R.MODELS}
    monkeypatch.setattr(provider_test.MOCK, 'REQUESTS', physical)
    monkeypatch.setitem(provider_test.MOCK.CONTROL, 'response_status', 200)
    def dispatch(payload, model):
        handler = object.__new__(provider_test.MOCK.Handler); statuses = []
        handler.send_response = statuses.append; handler.send_header = lambda *args: None; handler.end_headers = lambda: None
        handler.wfile = io.BytesIO(); handler.serve_responses(copy.deepcopy(payload))
        assert statuses == [200]
        response = json.loads(handler.wfile.getvalue()); p = copy.deepcopy(physical[-1])
        wire = copy.deepcopy(payload); wire['model'] = model
        if model == R.MODELS[0]: wire['stream'] = True
        scope = dict(schema=1, category='personal', model=model, user_id=actor, chat_id=chat, answer_id=answer,
                     root_chat_id=chat, root_answer_id=answer, call_id=str(uuid4()))
        p['lifecycle'] = {k: p['lifecycle'][k] for k in ('terminal', 'outcome')}
        groups[model].append(dict(wire_before_auth=wire, provider=p, verified_cost_scope=scope,
            auth_user_id=actor, auth_key_hash=('a' if model == R.MODELS[0] else 'b') * 64))
        return response
    def append_response(payload, response, result, preserve_reasoning):
        raw = response['output']; call = next(v for v in raw if v.get('type') == 'function_call')
        if preserve_reasoning:
            reasoning = [v for v in raw if v.get('type') == 'reasoning']
            payload['input'].extend(router['convert_to_responses_payload']({'messages': [{'role': 'assistant', 'output': reasoning}]})['input'])
        payload['input'].append({k: call[k] for k in ('type', 'call_id', 'name', 'arguments')})
        payload['input'].append(dict(type='function_call_output', call_id=call['call_id'], output=result if isinstance(result, list) else json.dumps(result)))
    for index in range(6):
        response = dispatch(case.parent, R.MODELS[0])
        if index == 5: break
        call = next(v for v in response['output'] if v.get('type') == 'function_call')
        args = json.loads(call['arguments'])
        if index in (0, 3, 4): result = case.native_task((call['name'], args, None))
        elif index == 1: result = case.skill
        else:
            packet = json.loads(args['prompt'])
            worker = dict(model=provider_test.MOCK.DELEGATED_WORKER_MODEL, max_output_tokens=6000, stream=False, store=False,
                tools=copy.deepcopy(native_worker_tools), input=[dict(type='message', role='developer', content=case.skill['content']),
                                                          dict(type='message', role='user', content=json.dumps(packet))])
            for j in range(6):
                child = dispatch(worker, R.MODELS[1])
                if j < 5:
                    leaf = worker_leaf_results[j]
                    append_response(worker, child, json.loads(leaf) if isinstance(leaf, str) else leaf, False)
            result = {'result': '[Download](/api/v1/files/' + case.file_id + '/content)'}
        append_response(case.parent, response, result, True)
    cases = [[v for v in c['provider']['response']['output'] if v.get('type') == 'reasoning'] for c in groups[R.MODELS[0]]]
    specs = [dict(s) for s in case.office_tools]
    for s in specs: s.pop('type')
    packets = [dict(schema=1, module_sha256={k: R.proof.WEBUI_MODULES[k] for k in ('utils/tools.py', 'routers/openai.py')},
        source_body_sha256=R.proof.digest(office['office_setup']['openapi']), native_specs=specs,
        reasoning_cases=[dict(input_reasoning=v, native_input=router['convert_to_responses_payload']({'messages': [{'role': 'assistant', 'output': v}]})['input']) for v in cases[i:i + 4]])
        for i in range(0, len(cases), 4)]
    context = dict(schema=1, packets=packets, provider_ids=[c['provider']['id'] for m in R.MODELS for c in groups[m]])
    browser = dict(chat_id=chat, answer_id=answer, file_id=case.file_id, stored_chat={'tasks': case.task_rows})
    guide = json.loads(worker_leaf_results[0])
    guide_packet = dict(schema=1, source_commit='f' * 40, office_image_id='sha256:' + 'a' * 64,
        qualification_image_id='sha256:' + 'b' * 64, version='1.0.152', modules={'officecli.py': 'c' * 64}, binary_sha256='d' * 64,
        output=dict(command=['/usr/local/bin/officecli', 'load_skill', 'word'], text=guide['content'],
                    content_sha256=guide['content_sha256'], auto_resident_disabled=True, diagnostics='explicit test CLI IO leaf'))
    guide_raw = json.dumps(guide_packet).encode()
    binding = dict(command=guide_packet['output']['command'], content_sha256=guide['content_sha256'],
        text_bytes=len(guide['content'].encode()), packet_sha256=R.sha256(guide_raw).hexdigest(), packet_bytes=len(guide_raw),
        image_id=guide_packet['qualification_image_id'], binary_sha256=guide_packet['binary_sha256'],
        modules=guide_packet['modules'], version='1.0.152')
    qualification_raw = json.dumps(dict(stage='complete', preflight_passed=True, word_guide=binding)).encode()
    guide_path, qualification_path = tmp_path / 'office-word-guide.private.json', tmp_path / 'office-qualification.safe.json'
    guide_path.write_bytes(guide_raw); qualification_path.write_bytes(qualification_raw)
    monkeypatch.setattr(R, 'GUIDE', guide_path); monkeypatch.setattr(R, 'QUALIFICATION', qualification_path)
    context['binding'] = dict(word_guide_binding=binding, source_commit='f' * 40, qualification_receipt_sha256=R.sha256(qualification_raw).hexdigest())
    browser['running'] = {'office': dict(image_id=guide_packet['office_image_id'], modules=guide_packet['modules'], binary_sha256=guide_packet['binary_sha256'])}
    d = dict(validate_persisted_scope=provenance.validate_persisted_scope, WORKFLOW_SKILL_SHA256=provision.WORKFLOW_SKILL_SHA256,
             delegated_responses_step=provider_test.MOCK.delegated_responses_step, delegated_responses_input=provider_test.MOCK.delegated_responses_input)
    return groups, office, browser, context, d, physical


def test_context_composes_actual_native_tasks_serializer_full_skill_and_actual_provider_tape(monkeypatch, tmp_path):
    values = context_case(monkeypatch, tmp_path)
    scopes = R.verify_context(*values)
    assert {m: len(v) for m, v in scopes.items()} == dict.fromkeys(R.MODELS, 6)


@pytest.mark.parametrize('mutation', ['skill_loss', 'duplicate_skill', 'root_tail', 'task_alias', 'guide_loss', 'native_case_loss', 'guide_packet', 'guide_qualification'])
def test_real_owner_context_composition_rejects_material_omissions(monkeypatch, tmp_path, mutation):
    groups, office, browser, context, d, tape = context_case(monkeypatch, tmp_path)
    if mutation in ('skill_loss', 'duplicate_skill'):
        wire = groups[R.MODELS[1]][0]['wire_before_auth']
        wire['input'][0]['content'] = '' if mutation == 'skill_loss' else office['office_delegation_setup']['skill']['content'] * 2
    elif mutation == 'root_tail': groups[R.MODELS[0]][0]['wire_before_auth']['input'][0]['content'] = 'artifact-workflow marker only'
    elif mutation == 'task_alias':
        groups[R.MODELS[0]][-1]['wire_before_auth']['input'][-2]['arguments'] = '{"task_id":"2","status":"completed"}'
    elif mutation == 'guide_loss':
        groups[R.MODELS[1]][-1]['wire_before_auth']['input'][3]['output'] = '{}'
    elif mutation == 'native_case_loss': context['packets'][0]['reasoning_cases'].pop()
    elif mutation == 'guide_packet': R.GUIDE.write_bytes(R.GUIDE.read_bytes() + b' ')
    else: context['binding']['qualification_receipt_sha256'] = '0' * 64
    with pytest.raises((N.ProofError, ValueError)):
        R.verify_context(groups, office, browser, context, d, tape)


def complete_case(tmp_path, monkeypatch):
    """Complete collector composition with actual domain owners and raw IO data."""
    import ast
    import test_office_compatibility as native_test
    import prove_pricing_snapshots as pricing
    from types import ModuleType
    groups, office, browser, context, d, tape = context_case(monkeypatch, tmp_path)
    source, _, artifact, _ = artifact_case(tmp_path, monkeypatch)
    browser.update(artifact)
    actor = office['office_delegation_setup']['actor']['id']; payer = office['service_fixture']['payer_id']
    chat, answer, file_id = browser['chat_id'], browser['answer_id'], browser['file_id']
    user_id = str(uuid4()); skill_id = office['office_delegation_setup']['skill']['id']
    import mock_provider
    text = mock_provider.DELEGATED_USER_REQUEST + '\nNative Skill ID: ' + skill_id
    download = '[Download](/api/v1/files/' + file_id + '/content)'
    final = dict(id=answer, model='corporate-documents', role='assistant', done=True, parentId=user_id,
        content=download, followUps=['Prepare a PDF copy.'],
        files=[dict(type='file', id=file_id, url=file_id, name='goal584-delegated.docx')],
        output=[v for c in groups[R.MODELS[0]] for v in c['provider']['response']['output'] if v.get('type') == 'reasoning'],
        statusHistory=[dict(action='employee_budget_cost', done=True,
            description='Ответ: $1.32 · Чат: $1.32 · на 12:00:00 UTC · начислено на сейчас, учёт обновляется')])
    stored = dict(id=chat, user_id=actor, tasks=copy.deepcopy(browser['stored_chat']['tasks']),
        chat={'history': {'messages': {user_id: dict(id=user_id, role='user', content=text), answer: final}}})
    browser.update(schema=1, actor_id=actor, source_file_id=office['office_delegation_setup']['source_file']['id'], skill_id=skill_id,
        user_message_id=user_id, stored_chat=stored, native_running={'task_ids': []}, submission_status=200,
        submission=dict(model='corporate-documents', chat_id=chat, id=answer,
            user_message=dict(id=user_id, role='user', content=text, parentId=None)), acknowledgement={'chat_id': chat},
        native_file=dict(id=file_id, user_id=actor, meta={'name': 'goal584-delegated.docx'}))
    root = Path(__file__).resolve().parents[2]
    fields = ast.literal_eval(next(n.value for n in ast.parse((root / 'deploy/openwebui-budgets/pricing_snapshot.py').read_bytes()).body
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'RATE_FIELDS' for t in n.targets)))
    representation = ModuleType('pricing_snapshot'); representation.RATE_FIELDS = fields
    monkeypatch.setitem(sys.modules, 'pricing_snapshot', representation)
    monkeypatch.setattr(native_test, 'LLM', root.with_name('corp-openweb-ui-goal584') / 'local/goal584/litellm/upstream')
    decode = native_test.sdk_decoder()
    d.update(validate_snapshot=pricing.validate_snapshot, validate_persisted_service_scope=provenance.validate_persisted_service_scope,
        ResponsesAPIRequestUtils=SimpleNamespace(_decode_responses_api_response_id=decode),
        delegated_source_docx=provision.delegated_source_docx, DELEGATED_USER_REQUEST=mock_provider.DELEGATED_USER_REQUEST)
    def user(uid):
        return dict(user_id=uid, user_role='internal_user', models=list(R.MODELS), max_budget=2000,
                    budget_duration='30d', budget_reset_at='2026-12-01', spend=0)
    def key(uid, model, token):
        return dict(user_id=uid, models=[model], token=token, key_alias=token, max_budget=1000,
                    budget_duration='30d', budget_reset_at='2026-12-01', spend=0)
    before = dict(provider={'requests': []}, capture={'requests': []}, descriptors={},
                  finance=dict(personal={}, raw_owners={actor: {}, payer: {}, 'old-owner': {}}, service={}))
    after = dict(personal={}, raw_owners=copy.deepcopy(before['finance']['raw_owners']), service={})
    def row(provider_id, scope, model, wire, deployment, token, spend, rates, descriptor):
        values = {k: None for k in fields}; values.update(input_cost_per_token=rates[0], output_cost_per_token=rates[1])
        return dict(request_id=provider_id, model='openai/' + wire, model_group=model, model_id=deployment, status='success',
            user=scope['user_id'], api_key=token, session_id=chat, spend=spend, prompt_tokens=10, completion_tokens=5, total_tokens=15,
            metadata={'spend_logs_metadata': {'owui_budget': copy.deepcopy(scope),
                'owui_billed_token_rates': dict(schema=1, availability='partial', observed_at_utc='2026-11-08T00:00:00Z', rates=values),
                'owui_tariff_descriptor': dict(schema=1, availability='available', descriptor=descriptor)}})
    for model, delta, spend, rates, token in zip(R.MODELS, (1.20, .12), (.20, .02), ((.01, .02), (.001, .002)), ('a' * 64, 'b' * 64)):
        descriptor = {'deployment_id': R.DEPLOYMENTS[model]}; before['descriptors'][model] = {'model_info': {'owui_pricing': descriptor}}
        original = dict(user=user(actor), key=key(actor, model, token), rows=[], old_payers={'old-owner': {'rows': [{'request_id': 'old-zero', 'spend': 0}]}})
        current = copy.deepcopy(original); current['user']['spend'] = 1.32; current['key']['spend'] = delta
        current['rows'] = [row(c['provider']['id'], c['verified_cost_scope'], model, R.WIRES[model], R.DEPLOYMENTS[model], token, spend, rates, descriptor) for c in groups[model]]
        before['finance']['personal'][model], after['personal'][model] = original, current
    service_scope = dict(schema=1, category='service', model='gpt-6-luna', task='follow_up_generation',
                         user_id=payer, actor_id=actor, chat_id=chat, call_id=str(uuid4()))
    service_id = 'resp_' + uuid4().hex; service_wire = dict(model='gpt-6-luna', input=[], store=False, stream=False)
    service_body = R.proof.expected_provider_body(service_wire, 'goal584-fake-office-service')
    service_provider = dict(id=service_id, route='/v1/responses', body=service_body, usage=R.proof.USAGE,
        response=dict(id=service_id, model='goal584-fake-office-service', status='completed', usage=R.proof.USAGE,
            output=[dict(type='message', role='assistant', content=[dict(type='output_text', text=json.dumps({'follow_ups': final['followUps']}))])]),
        lifecycle={'terminal': True, 'outcome': 'completed'})
    original = dict(user=user(payer), key=key(payer, 'gpt-6-luna', 'c' * 64), rows=[])
    current = copy.deepcopy(original); current['user']['spend'] = current['key']['spend'] = .20
    descriptor = {'deployment_id': 'goal584-office-service'}; before['descriptors']['service'] = {'model_info': {'owui_pricing': descriptor}}
    service_row = row(service_id, service_scope, 'gpt-6-luna', 'goal584-fake-office-service', 'goal584-office-service', 'c' * 64, .20, (.01, .02), descriptor)
    service_row['session_id'] = 'owui-service:' + chat; current['rows'] = [service_row]
    before['finance']['service'], after['service'] = original, current
    capture = {'requests': []}; provider = {'requests': []}
    for model in R.MODELS:
        for c in groups[model]:
            capture['requests'].append(dict(body=c['wire_before_auth'], body_after_auth=copy.deepcopy(c['wire_before_auth']),
                route='/responses', verified_cost_scope=c['verified_cost_scope'], native_auth_user_id=actor, native_auth_key_hash=c['auth_key_hash'],
                attestation_present_before=True, provenance_removed_after=True))
            provider['requests'].append(c['provider'])
    capture['requests'].append(dict(body=service_wire, body_after_auth=copy.deepcopy(service_wire), route='/responses',
        verified_cost_scope=service_scope, native_auth_user_id=payer, native_auth_key_hash='c' * 64,
        attestation_present_before=True, provenance_removed_after=True))
    provider['requests'].append(service_provider)
    owner = native_cost_owner(monkeypatch)
    raw_rows = [row for model in R.MODELS for row in after['personal'][model]['rows']]
    total = owner._total([owner._row(row, actor, chat) for row in raw_rows])
    cost = owner.CostSnapshot(actor, chat, answer, total, total, datetime.now(timezone.utc), False, True, ())
    return dict(before=before, after=after, provider=provider, captured=capture, saved=stored, browser=browser,
                context=context, office=office, cost=cost, d=d)


def test_complete_collector_uses_actual_task_context_scope_rates_sdk_cost_and_artifact_owners(tmp_path, monkeypatch):
    data = complete_case(tmp_path, monkeypatch)
    result = R.verify(**data)
    assert result['personal']['gpt-6.1-sol']['native_spend_delta_usd'] == '1.20'
    assert result['personal']['gpt-6.1-terra']['native_spend_delta_usd'] == '.12'
    assert result['service']['physical_calls'] == 1 and result['provider_calls'] == 13
    assert result['cost_status_provisional'] is True


@pytest.mark.parametrize('mutation', ['worker_nonce', 'worker_key', 'worker_row_missing', 'shared_counter', 'saved_reasoning', 'tariff'])
def test_complete_collector_rejects_financial_and_saved_context_divergence(tmp_path, monkeypatch, mutation):
    data = complete_case(tmp_path, monkeypatch)
    row = data['after']['personal']['gpt-6.1-terra']['rows'][-1]
    if mutation == 'worker_nonce': row['metadata']['spend_logs_metadata']['owui_budget']['call_id'] = str(uuid4())
    elif mutation == 'worker_key': row['api_key'] = 'a' * 64
    elif mutation == 'worker_row_missing': data['after']['personal']['gpt-6.1-terra']['rows'].pop()
    elif mutation == 'shared_counter': data['after']['personal']['gpt-6.1-terra']['user']['spend'] = 1.20
    elif mutation == 'saved_reasoning': data['saved']['chat']['history']['messages'][data['browser']['answer_id']]['output'].pop()
    else: row['metadata']['spend_logs_metadata']['owui_tariff_descriptor']['descriptor'] = {'deployment_id': 'wrong-terms'}
    with pytest.raises(N.ProofError): R.verify(**data)
