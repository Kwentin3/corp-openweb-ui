"""Offline actual-source/bytes checks; native HTTP is an explicit IO leaf."""
import copy
import asyncio
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


def test_quota_status_envelope_uses_actual_source_and_never_exports_private_result():
    from prove_pricing_snapshots import no_credentials
    data=native_io();state={'stage':'verified_readback','prepared_sha256':R.proof.digest(data.office),
        'quota':{'stage':'baseline_ready','result':{'private':'sk-private-result-must-stay-in-journal'}}}
    d={'read_private':lambda path:data.office if path==R.OFFICE else state,'no_credentials':no_credentials}
    value=R.run('quota-status',d)
    assert value['quota_present'] is True and value['quota_stage']=='baseline_ready'
    assert value['source_sha256']==R.sha256(Path(R.__file__).read_bytes()).hexdigest()
    assert value['native_office_accepted'] is False and 'result' not in value
    assert 'private-result' not in json.dumps(value)


def quota_public_case(monkeypatch,tmp_path):
    from test_capture_webui_auth import C
    data=native_io();data.people[data.actor]['spend']=1.32
    data.keys[data.actor][0]['spend']=1.2;data.keys[data.actor][1]['spend']=.12
    original=R.inventory(data.native,data.office);worker=original['personal'][R.MODELS[1]]['key']
    data.keys[data.actor][1]['max_budget']=.12
    restricted=R.inventory(data.native,data.office,worker_cap=Decimal('.12'))
    R.quota_cap_only(original,restricted,worker['token'],Decimal('.12'))
    data.keys[data.actor][1]['max_budget']=1000
    restored=R.inventory(data.native,data.office)
    R.quota_cap_only(restricted,restored,worker['token'],Decimal(1000))
    q={'stage':'restored','original_cap':str(worker['max_budget']),'restricted_cap':str(worker['spend']),
       'finance':restricted,'restored_inventory':restored,
       'journal':['restrict_pre_write','restrict_returned','restrict_readback','restore_pre_write','restore_readback']}
    monkeypatch.setattr(C,'CAPTURE',tmp_path/'capture.private.json')
    for index in range(36):C._append({'body':{'index':index,'input':'Приватный контекст не экспортировать'}})
    return q,C,data


def test_quota_public_readback_uses_native_inventory_and_actual_serialized_capture(monkeypatch,tmp_path):
    q,capture,data=quota_public_case(monkeypatch,tmp_path)
    with capture.capture_lock():
        observed=capture._read_locked()
        capture.CAPTURE.write_bytes(json.dumps(observed,ensure_ascii=False,indent=1).encode('utf8')+b'\n')
    raw=capture.CAPTURE.read_bytes();before=copy.deepcopy(q)
    value=R.quota_public_readback(q,capture)
    assert q==before and value['worker']=={'original_cap_usd':'1000','restricted_cap_usd':'0.12',
        'restriction_readback_complete':True,'restricted_readback':{'cap_usd':'0.12','spend_usd':'0.12'},
        'restored_readback':{'cap_usd':'1000','spend_usd':'0.12'},'restoration_complete':True}
    assert value['capture']=={'total_records':36,'serialized_bytes':len(raw),'sha256':R.sha256(raw).hexdigest(),
        'max_records':36,'max_bytes':4*1024*1024}
    assert len(raw)>len(raw.decode('utf8')) and 'verified' not in value
    assert all(secret not in json.dumps(value) for secret in (data.actor,data.payer,'Приватный контекст'))


def test_quota_public_readback_allowlists_existing_verified_summary_and_phase_envelope(monkeypatch,tmp_path):
    import ast
    from prove_pricing_snapshots import no_credentials
    q,capture,data=quota_public_case(monkeypatch,tmp_path)
    verified=R.verify(**complete_case(tmp_path,monkeypatch))
    # Reuse the exact existing quota result producer; finance comes from the
    # actual native/context/SDK/rate collector, not another summary assembler.
    tree=ast.parse(Path(R.__file__).read_bytes())
    producer=next(n for n in tree.body if getattr(n,'name',None)=='verify_quota')
    returned=next(n for n in reversed(producer.body) if isinstance(n,ast.Return))
    q['result']=eval(compile(ast.Expression(returned.value),'<existing-quota-result-producer>','eval'),
        {'finance':verified['personal'][R.MODELS[0]],'service':verified['service'],'added':[],
         'cost':{'error':'usage_unavailable'},'status':{'private':'raw status must remain private'}})
    q['result']['raw_wire']={'authorization':'sk-secret-raw-not-for-public'}
    q['result']['personal']['token']='sk-secret-nested-not-for-public'
    q['private_journal_copy']='private-password-sentinel'
    state={'quota':q};seen=[]
    monkeypatch.setattr(R,'quota_run',lambda phase,d:dict(schema=1,phase=phase,passed=True,native_office_accepted=False))
    def safe(value):no_credentials(value,('private-password-sentinel',));seen.append(copy.deepcopy(value))
    packet=R.run('quota-verify',{'read_private':lambda path:state,'capture':capture,'no_credentials':safe})
    value=packet['quota_readback']['verified']
    assert value['personal']=={'physical_calls':6,'new_raw_rows':6,'native_spend_delta_usd':'1.20'}
    assert value['service']=={'physical_calls':1,'new_raw_rows':1,'native_spend_delta_usd':'.20'}
    assert (value['native_denial_status'],value['worker_provider_calls'],value['provider_calls'],value['captured_attempts'])==(422,0,7,8)
    assert value['row_absence_is_not_zero_cost_proof'] is True and value['worker_expense_final'] is False
    assert 'result' not in packet and not any(text in json.dumps(packet) for text in ('sk-secret','private-password','raw status'))
    assert seen==[packet] and packet['source_sha256']==R.sha256(Path(R.__file__).read_bytes()).hexdigest()


def test_quota_public_readback_rejects_missing_or_inconsistent_actual_restore_facts(monkeypatch,tmp_path):
    q,capture,_=quota_public_case(monkeypatch,tmp_path)
    for change in (lambda value:value.pop('restored_inventory'),
                   lambda value:value['restored_inventory']['personal'][R.MODELS[1]]['key'].update(max_budget=999),
                   lambda value:value['restored_inventory']['personal'][R.MODELS[1]]['key'].update(spend=.13),
                   lambda value:value['journal'].remove('restore_readback'),
                   lambda value:value['finance']['personal'][R.MODELS[1]]['key'].update(max_budget=.13)):
        changed=copy.deepcopy(q);change(changed)
        with pytest.raises(N.ProofError):R.quota_public_readback(changed,capture)


def test_quota_public_readback_keeps_actual_capture_owner_count_and_byte_limits(monkeypatch,tmp_path):
    q,capture,_=quota_public_case(monkeypatch,tmp_path)
    original=capture.CAPTURE.read_bytes()
    for raw in (json.dumps({'schema':1,'requests':[{}]*37}).encode(),original+b' '*(capture.MAX_BYTES+1-len(original))):
        capture.CAPTURE.write_bytes(raw)
        with pytest.raises(RuntimeError):R.quota_public_readback(q,capture)
        assert capture.CAPTURE.read_bytes()==raw


@pytest.mark.parametrize('mode',['success','failed_complete','timeout','empty','wrong_source','wrong_phase','wrong_exit','accepted'])
def test_attached_quota_phase_requires_real_owner_source_and_native_completion(monkeypatch,mode):
    import subprocess
    fixture=SimpleNamespace(command=['docker','compose','--project-name','owned'])
    marks=[];events=[]
    def leaf(command,**kwargs):
        events.append(command)
        assert command==fixture.command+['exec','-T','proxy','python','-B','/proof/prove_office_delegation_readback.py','--phase','quota-baseline']
        assert kwargs=={'capture_output':True,'timeout':75}
        if mode=='timeout':raise subprocess.TimeoutExpired(command,75)
        value={'schema':1,'phase':'quota-baseline','passed':mode!='failed_complete','native_office_accepted':False,
            'source_sha256':R.sha256(Path(R.__file__).read_bytes()).hexdigest()}
        if mode=='wrong_source':value['source_sha256']='f'*64
        if mode=='wrong_phase':value['phase']='quota-restore'
        if mode=='accepted':value['native_office_accepted']=True
        code=1 if mode in ('failed_complete','wrong_exit') else 0
        return subprocess.CompletedProcess(command,code,b'' if mode=='empty' else json.dumps(value).encode())
    monkeypatch.setattr(R.subprocess,'run',leaf)
    if mode in ('success','failed_complete'):
        packet=R.host_quota_phase(fixture,'quota-baseline',marks.append,timeout=75)
        assert packet['passed'] is (mode=='success') and marks==[True,False]
    else:
        with pytest.raises(N.ProofError,match='mutation_unconfirmed'):
            R.host_quota_phase(fixture,'quota-baseline',marks.append,timeout=75)
        assert marks==[True]
    assert len(events)==1


@pytest.mark.parametrize('mutation',[None,'foreign_actor','positive_chat','foreign_owner','still_active','wrong_session'])
def test_quiesce_uses_actual_webui_owner_preserves_pre_stop_and_never_claims_product_tasks(monkeypatch,tmp_path,mutation):
    monkeypatch.setattr(R,'PRIVATE',tmp_path)
    data=native_io();actor=data.actor;chat=str(uuid4());positive=str(uuid4())
    data.office['office_delegation_setup']['actor']['token']='actor-IO-token'
    packet={'actor_id':actor,'chat_id':chat}
    if mutation=='foreign_actor':packet['actor_id']=data.old
    if mutation=='positive_chat':packet['chat_id']=positive
    (tmp_path/'office-delegation-quota.private.json').write_text(json.dumps(packet))
    state={'browser':{'chat_id':positive},'quota':{'stage':'baseline_ready','journal':['restrict_readback']}}
    active=['actual-native-background'];events=[];writes=[]
    class Transport:
        def open(self,request,timeout):
            nonlocal active
            path=urlsplit(request.full_url).path;method=request.get_method();events.append((method,path))
            assert timeout==20 and request.headers['Authorization']=='Bearer actor-IO-token'
            if path=='/api/v1/auths/':return HttpResult({'id':actor,'role':'admin' if mutation=='wrong_session' else 'user'})
            if path=='/api/v1/chats/'+chat:
                return HttpResult({'id':chat,'user_id':data.old if mutation=='foreign_owner' else actor,
                    'tasks':[{'id':'real-task','status':'pending'}]})
            if method=='POST':
                assert path=='/api/tasks/chat/'+chat+'/stop'
                assert writes[-1]['quota']['cleanup']['before']['task_ids']==['actual-native-background']
                if mutation!='still_active':active=[]
                return HttpResult({'status':True})
            assert path=='/api/tasks/chat/'+chat
            return HttpResult({'task_ids':active})
    webui=provision.WebUI();webui.opener=Transport()
    d={'read_private':lambda path:json.loads(path.read_text()),'WebUI':lambda:webui,
       'write_private':lambda path,value:writes.append(copy.deepcopy(value))}
    if mutation:
        with pytest.raises(N.ProofError):R.quota_quiesce(state,data.office,d)
    else:
        R.quota_quiesce(state,data.office,d)
        assert state['quota']['cleanup']['before']['task_ids']==['actual-native-background']
        assert state['quota']['cleanup']['after']=={'task_ids':[]}
        assert state['quota']['cleanup']['saved_chat']['tasks'][0]['status']=='pending'
        assert state['quota']['journal'][-1]=='quiesce_readback'
    if mutation in ('foreign_actor','positive_chat','foreign_owner','wrong_session'):
        assert not any(method=='POST' for method,path in events)
    assert all(path.endswith(chat) or path.endswith(chat+'/stop') or path=='/api/v1/auths/' for method,path in events)


def context_case(monkeypatch, tmp_path, *, quota=False):
    """Actual provider/Tasks/media/send-loop/serializer owners; Office IO leaves."""
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
    with provider_test.patch.object(native_test, 'NATIVE', source):
        _, router, media = native_test.native.__wrapped__()
    from collections.abc import Callable
    params_owner = native_test.native_owner('utils/payload.py',
        {'remove_open_webui_params', 'apply_model_params_to_body', 'apply_model_params_to_body_openai'},
        namespace={'Callable': Callable})
    profiles_raw = (root / 'deploy/openwebui-tools/corporate_template_models.json').read_bytes().replace(b'\r\n', b'\n')
    assert R.sha256(profiles_raw).hexdigest() == provision.DELEGATION_PROFILES_SHA256
    profiles = {v['id']: v for v in json.loads(profiles_raw)}
    def profile_form(profile_id, form):
        params = copy.deepcopy(profiles[profile_id]['params']); params.pop('system', None)
        return params_owner['apply_model_params_to_body_openai'](params, form)
    case.parent = router['convert_to_responses_payload'](profile_form('corporate-documents', {
        'model': case.parent['model'], 'tools': case.parent['tools'], 'include': ['reasoning.encrypted_content'],
        'messages': [{'role': 'developer', 'content': workflow + '\n' + case.skill['id']},
                     {'role': 'user', 'content': provider_test.MOCK.DELEGATED_USER_REQUEST}]}))
    if quota:
        for message in case.parent['input']:
            if message.get('role')=='user':
                message['content']=[{'type':'input_text','text':provider_test.MOCK.DELEGATED_USER_REQUEST+'\nNative Skill ID: '+case.skill['id']}]
    actor, chat, answer = [str(uuid4()) for _ in range(3)]
    office = prepared(actor, str(uuid4()))
    office['office_setup'] = {'workflow_skill': {'content': workflow}, 'openapi': {}}
    office['office_delegation_setup'].update(skill=case.skill, source_file={'id': case.source_id}, source_sha256=R.sha256(provision.delegated_source_docx()).hexdigest())
    tool_path = Path(__import__('os').environ.get('GOAL584_COMMUNITY_TOOL_SOURCE', str(root.with_name('corp-openweb ui') /
        'local/subagent-office-trial-20261029/sub_agent.py')))
    tool_raw = tool_path.read_bytes(); assert R.sha256(tool_raw).hexdigest() == provision.DELEGATION_TOOL_SHA256
    spec = importlib.util.spec_from_file_location('delegated_image_actual_pinned_tool', tool_path)
    tool = importlib.util.module_from_spec(spec);sys.modules[spec.name]=tool;spec.loader.exec_module(tool)
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
            if quota:
                native_worker_tools = router['convert_to_responses_payload']({'messages': [], 'tools': [{'type': 'function', 'function': {k: v for k, v in s.items() if k != 'type'}} for s in case.office_tools]})['tools']
                worker = router['convert_to_responses_payload'](profile_form('corporate-office-worker', {
                    'model': provider_test.MOCK.DELEGATED_WORKER_MODEL, 'stream': False,
                    'tools': copy.deepcopy(native_worker_tools), 'messages': [
                        {'role': 'developer', 'content': workflow + '\n' + case.skill['content']},
                        {'role': 'user', 'content': json.dumps(packet)}]}))
                provider_test.DelegatedQuotaProviderTests.setUpClass()
                result=json.loads(provider_test.DelegatedQuotaProviderTests.quota_output)
                append_response(case.parent,response,result,True)
                continue
            async def worker_turns():
                from starlette.requests import Request
                request = Request({'type':'http','method':'POST','path':'/api/chat/completions','headers':[],
                    'state':{},'app':SimpleNamespace(state=SimpleNamespace(MODELS={}))})
                pipeline=dict(model={'id':'corporate-office-worker'},model_id='corporate-office-worker',
                    process=None,functions=[],context=None,supports_context=False,supports_request=False)
                tools={s['name']:{'spec':{k:v for k,v in s.items() if k!='type'},'type':'external'} for s in case.office_tools}
                requests=tool.AgentRequests(tools,{'__request__':request,'__metadata__':{'chat_context':{},'filter_ids':[]}})
                messages=await requests.prepare(pipeline,request,profile_form('corporate-office-worker',
                    dict(model='corporate-office-worker',stream=False,
                         messages=[dict(role='developer',content=case.skill['content']),
                                   dict(role='user',content=json.dumps(packet))])))
                run=tool._LoopRunState(compaction=tool.LoopCompactionOptions(enabled=False),
                    large_results=tool.LargeToolResultOptions(mode='raw'),encoder=None,encoder_ready=False,filter_identity=None)
                async def send(**kwargs):
                    form=copy.deepcopy(kwargs['form_data']);form.pop('metadata',None)
                    payload=router['convert_to_responses_payload'](form)
                    payload['model']=provider_test.MOCK.DELEGATED_WORKER_MODEL
                    return dispatch(payload,R.MODELS[1])
                for j in range(6):
                    error,child,_,_=await tool._send_loop_request(run,generate_chat_completion=send,request=request,
                        user_obj=None,model_id='corporate-office-worker',agent_requests=requests,filter_pipeline=pipeline,
                        current_messages=messages,trailing_message={'role':'user','content':f'[Iteration {j+1}/12]'},
                        merge_trailing_into_last_user=True,metadata={'task':'sub_agent','sub_agent_iteration':j+1,'filter_ids':[]},
                        check_reader=True,neutralize_tool_choice=False)
                    assert error is None
                    if j==5: break
                    call=next(v for v in child['output'] if v.get('type')=='function_call')
                    leaf=worker_leaf_results[j]
                    if j==4:
                        from PIL import Image
                        png=BytesIO();Image.new('RGB',(3,2),'white').save(png,format='PNG')
                        leaf='data:image/png;base64,'+__import__('base64').b64encode(png.getvalue()).decode()
                    else: leaf=json.loads(leaf) if isinstance(leaf,str) else leaf
                    text,files,embeds=await media['process_tool_result'](None,call['name'],(leaf,{}),'external')
                    images,display=await tool.split_tool_result_files(files)
                    assert not embeds and not display
                    messages.extend([dict(role='assistant',content='',tool_calls=[dict(id=call['call_id'],type='function',
                        function={'name':call['name'],'arguments':call['arguments']})]),
                        dict(role='tool',tool_call_id=call['call_id'],content=text if isinstance(text,str) else json.dumps(text))])
                    tool.append_tool_result_images(messages,images)
            asyncio.run(worker_turns())
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
    if quota: browser['denied_wire']=worker
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


def test_shared_reader_selector_cold_import_needs_no_host_or_proxy_transport_package():
    import os, subprocess
    code="""import importlib.abc,sys
class AbsentOptionalTransport(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in ('aiohttp','playwright','litellm'):
   raise ImportError('Optional transport unavailable')
sys.meta_path.insert(0,AbsentOptionalTransport())
import prove_office_delegation_readback as reader
assert callable(reader.select_render_image)
"""
    result=subprocess.run([sys.executable,'-B','-c',code],capture_output=True,timeout=15,
        env=os.environ|{'PYTHONPATH':str(Path(__file__).resolve().parent),'PYTHONDONTWRITEBYTECODE':'1'})
    assert result.returncode==0,result.stderr.decode(errors='replace')


def test_context_composes_actual_native_tasks_serializer_full_skill_and_actual_provider_tape(monkeypatch, tmp_path):
    values = context_case(monkeypatch, tmp_path)
    scopes = R.verify_context(*values)
    assert {m: len(v) for m, v in scopes.items()} == dict.fromkeys(R.MODELS, 6)




def test_native_context_accepts_independent_native_schema_processes_and_preserves_strict_invariants(monkeypatch,tmp_path):
    import os,subprocess
    # Fresh processes execute the producer's own schema expressions using the
    # pinned native helpers and real14-operation OpenAPI; no schema substitute.
    code="""import ast,contextlib,io,json,pathlib
with contextlib.redirect_stdout(io.StringIO()):
 import test_office_compatibility as n
 tools,router,_=n.native.__wrapped__()
 schema=n.create_app(n.CliIO()).openapi()
 tree=ast.parse((n.ROOT/'scripts/goal584-budget-proof/office_fixture.py').read_bytes())
 cls=next(v for v in tree.body if isinstance(v,ast.ClassDef) and v.name=='OfficeFixture')
 method=next(v for v in cls.body if getattr(v,'name',None)=='native_context')
 source=next(v.value.value for v in method.body if isinstance(v,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='code' for t in v.targets))
 scope=next(v for v in ast.parse(source).body if isinstance(v,ast.With))
 statements=[v for v in scope.body if isinstance(v,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('specs','cases') for t in v.targets)]
 assert len(statements)==2
 namespace={'p':{'openapi':schema,'reasoning_cases':[[]]},'convert_openapi_to_tool_payload':tools['convert_openapi_to_tool_payload'],'clean_openai_tool_schema':tools['clean_openai_tool_schema'],'convert_to_responses_payload':router['convert_to_responses_payload']}
 exec(compile(ast.Module(body=statements,type_ignores=[]),'actual-native-context-producer','exec'),namespace)
print(json.dumps({'specs':namespace['specs'],'cases':namespace['cases'],'source':n.P.digest(schema)}))
"""
    packets=[]
    for seed in ('0','1'):
        result=subprocess.run([sys.executable,'-B','-c',code],capture_output=True,timeout=20,
            env=os.environ|{'PYTHONHASHSEED':seed,'PYTHONPATH':os.pathsep.join(sys.path),'PYTHONDONTWRITEBYTECODE':'1'})
        assert result.returncode==0,result.stderr.decode(errors='replace')
        packets.append(json.loads(result.stdout))
    assert packets[0]['source']==packets[1]['source'] and packets[0]['cases']==packets[1]['cases']
    assert len(packets[0]['specs'])==len(packets[1]['specs'])==14 and packets[0]['specs']!=packets[1]['specs']
    values=context_case(monkeypatch,tmp_path);groups,office,browser,context,d,tape=values
    assert packets[0]['source']==R.proof.digest(office['office_setup']['openapi'])
    for packet,observed in zip(context['packets'],packets):packet['native_specs']=observed['specs']
    before=copy.deepcopy((groups,context))
    scopes=R.verify_context(*values)
    assert {m:len(v) for m,v in scopes.items()}==dict.fromkeys(R.MODELS,6)
    assert (groups,context)==before
    for mutation in ('missing','extra','duplicate','description','required','parameter'):
        changed=copy.deepcopy(context);specs=changed['packets'][1]['native_specs']
        if mutation=='missing':specs.pop()
        elif mutation=='extra':specs.append(dict(specs[-1],name='unrelated-native-operation'))
        elif mutation=='duplicate':specs.append(copy.deepcopy(specs[-1]))
        elif mutation=='description':specs[0]['description']='different schema'
        elif mutation=='required':specs[0]['parameters']['required'].append('missing-required-field')
        else:specs[0]['parameters']['properties']['unrelated']={'type':'string'}
        with pytest.raises(N.ProofError,match='^office_delegation_native_context_specs$'):
            R.verify_context(groups,office,browser,changed,d,tape)
    for mutation,code in (('shape','shape'),('ids','provider_ids'),('duplicate','reasoning_duplicate'),('missing','cases')):
        changed=copy.deepcopy(context)
        if mutation=='shape':changed['schema']=2
        elif mutation=='ids':changed['provider_ids'][0]=changed['provider_ids'][1]
        elif mutation=='duplicate':
            case=copy.deepcopy(changed['packets'][0]['reasoning_cases'][0]);case['native_input']=[{'type':'reasoning','encrypted_content':'different'}]
            changed['packets'][1]['reasoning_cases'].append(case)
        else:changed['packets'][1]['reasoning_cases'].pop()
        with pytest.raises(N.ProofError,match='^office_delegation_native_context_'+code+'$'):
            R.verify_context(groups,office,browser,changed,d,tape)
    assert (groups,context)==before


def test_context_accepts_native_profile_store_omission_and_rejects_explicit_invalid_provider_contract(monkeypatch,tmp_path):
    values = context_case(monkeypatch,tmp_path)
    groups = values[0]; before = copy.deepcopy(groups)
    assert all('store' not in call['wire_before_auth'] and 'store' not in call['provider']['body']
               for model in R.MODELS for call in groups[model])
    assert R.verify_context(*values) and groups == before
    explicit = copy.deepcopy(groups)
    for model in R.MODELS:
        for call in explicit[model]: call['wire_before_auth']['store'] = False
    assert R.verify_context(explicit,*values[1:])
    changes = [lambda c,v=value:c['wire_before_auth'].update(store=v) for value in (True,None,0,1,'false','')]
    changes += [lambda c:c['wire_before_auth'].update(previous_response_id='unrelated-response'),
                lambda c:c['wire_before_auth'].update(background=True),
                lambda c:c['provider'].update(route='/v1/chat/completions'),
                lambda c:c['provider'].update(usage=None),
                lambda c:c['provider']['response'].update(usage=None),
                lambda c:c['provider']['response'].update(id='foreign-provider'),
                lambda c:c['provider']['response'].update(model='foreign-model'),
                lambda c:c['provider']['response'].update(status='in_progress'),
                lambda c:c['provider'].update(lifecycle={'terminal':False,'outcome':'completed'})]
    for change in changes:
        changed = copy.deepcopy(groups); change(changed[R.MODELS[0]][0])
        with pytest.raises(N.ProofError,match='^office_delegation_provider_response$'):
            R.verify_context(changed,*values[1:])
    assert groups == before


def test_native_render_selector_returns_actual_adjacent_carrier_and_preserves_full_input(monkeypatch,tmp_path):
    groups,*_=context_case(monkeypatch,tmp_path)
    wire=groups[R.MODELS[1]][-1]['wire_before_auth'];before=copy.deepcopy(wire)
    call=next(v for v in groups[R.MODELS[1]][-2]['provider']['response']['output'] if v.get('type')=='function_call')
    png,carrier=R.select_render_image(wire,call,file_id=json.loads(call['arguments'])['file_id'])
    assert carrier is wire['input'][-1] and wire==before
    assert carrier['content'][-1]=={'type':'input_text','text':'\n\n[Iteration 6/12]'}
    from officecli_openapi_proof.rendering import checked_png
    assert checked_png(png)==png


@pytest.mark.parametrize('mutation',['earlier_image','wrong_call','wrong_role','extra_part','extra_tail',
    'wrong_file','image_json','wrong_notice','invalid_bytes','duplicate_result','external_url'])
def test_native_render_selector_rejects_unbound_images_and_context_drift(monkeypatch,tmp_path,mutation):
    groups,*_=context_case(monkeypatch,tmp_path)
    wire=groups[R.MODELS[1]][-1]['wire_before_auth'];call=copy.deepcopy(next(v for v in
        groups[R.MODELS[1]][-2]['provider']['response']['output'] if v.get('type')=='function_call'))
    file_id=json.loads(call['arguments'])['file_id'];carrier=wire['input'][-1]
    if mutation=='earlier_image':wire['input'].insert(1,copy.deepcopy(carrier))
    elif mutation=='wrong_call':call['call_id']='foreign-call'
    elif mutation=='wrong_role':carrier['role']='assistant'
    elif mutation=='extra_part':carrier['content'].append({'type':'input_text','text':'unrelated'})
    elif mutation=='extra_tail':wire['input'].append({'type':'message','role':'user','content':'unrelated'})
    elif mutation=='wrong_file':file_id=str(uuid4())
    elif mutation=='image_json':wire['input'][-2]['output']=json.dumps(carrier['content'])
    elif mutation=='wrong_notice':carrier['content'][-1]['text']='\n\n[Iteration 5/12]'
    elif mutation=='invalid_bytes':carrier['content'][1]['image_url']='data:image/png;base64,'+__import__('base64').b64encode(b'swapped-document-bytes').decode()
    elif mutation=='duplicate_result':wire['input'].insert(-1,copy.deepcopy(wire['input'][-2]))
    else:carrier['content'][1]['image_url']='https://unowned.invalid/image.png'
    with pytest.raises(N.ProofError):R.select_render_image(wire,call,file_id=file_id)


def test_quota_context_uses_actual_native_error_formatter_tasks_and_all_six_parent_inputs(monkeypatch,tmp_path):
    groups,office,browser,context,d,tape=context_case(monkeypatch,tmp_path,quota=True)
    scopes=R.verify_context(groups,office,browser,context,d,tape,quota=True)
    assert len(tape)==6 and len(scopes[R.MODELS[0]])==6 and groups[R.MODELS[1]]==[]
    assert [v['status'] for v in browser['stored_chat']['tasks']]==['cancelled','cancelled']
    assert '/api/v1/files/' not in json.dumps(tape[-1]['response'])
    for mutation in ('last_result','cancelled_id','root','reasoning'):
        changed=copy.deepcopy(groups); packets=copy.deepcopy(context)
        if mutation=='last_result': changed[R.MODELS[0]][-1]['wire_before_auth']['input'][-1]['output']='{}'
        elif mutation=='cancelled_id': changed[R.MODELS[0]][4]['wire_before_auth']['input'][-2]['arguments']='{"id":"wrong","status":"cancelled"}'
        elif mutation=='root':changed[R.MODELS[0]][0]['wire_before_auth']['input'][0]['content']='root marker only'
        else:packets['packets'][0]['reasoning_cases'].pop()
        with pytest.raises((N.ProofError,ValueError)):
            R.verify_context(changed,office,browser,packets,d,tape,quota=True)


def test_quota_cap_only_uses_native_protected_fields_and_preserves_all_owner_rows_and_counters():
    data=native_io();before=R.inventory(data.native,data.office)
    worker=before['personal'][R.MODELS[1]]['key'];key_hash=worker['token']
    data.keys[data.actor][1]['max_budget']=.12
    after=R.inventory(data.native,data.office,worker_cap=Decimal('.12'))
    R.quota_cap_only(before,after,key_hash,Decimal('.12'))
    for mutation in ('spend','old_row','other_cap','blocked','missing_owner'):
        changed=copy.deepcopy(after)
        if mutation=='spend':changed['raw_owners'][data.actor]['user']['spend']=.1
        elif mutation=='old_row':changed['raw_owners'][data.old]['rows']=[]
        elif mutation=='other_cap':changed['raw_owners'][data.old]['keys'][0]['max_budget']=2
        elif mutation=='blocked':changed['raw_owners'][data.actor]['keys'][1]['blocked']=True
        else:changed['raw_owners'].pop(data.old)
        with pytest.raises(N.ProofError):R.quota_cap_only(before,changed,key_hash,Decimal('.12'))


def test_quota_baseline_native_api_sets_actual_spend_and_verify_failure_finally_restores_only_cap(monkeypatch,tmp_path):
    import contextlib
    from test_native_key_block import Response
    monkeypatch.setattr(R,'PRIVATE',tmp_path)
    data=native_io();data.people[data.actor]['spend']=1.32
    data.keys[data.actor][0]['spend']=1.2;data.keys[data.actor][1]['spend']=.12
    initial=R.inventory(data.native,data.office);provider={'synthetic':True,'control':{},'requests':[]};captured={'requests':[]}
    state={'stage':'verified_readback','prepared_sha256':R.proof.digest(data.office),
        'history_start_utc':datetime.now(timezone.utc).isoformat(),'provider_after':provider,'capture_after':captured,
        'after':copy.deepcopy(initial),'descriptors':{}}
    posts=[];writes=[]
    class Session:
        def __init__(self,**kwargs):assert kwargs=={'trust_env':False}
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        def request(self,method,url,**kwargs):
            assert (method,url)==('POST','http://proxy:4000/key/update')
            assert kwargs['allow_redirects'] is False and kwargs['headers']=={'Authorization':'Bearer sk-local-operator'}
            body=kwargs['json'];assert set(body)=={'key','max_budget'} and body['key']=='b'*64
            posts.append(copy.deepcopy(body));data.keys[data.actor][1]['max_budget']=body['max_budget']
            return Response(200,{'key':'b'*64})
    def read(path):
        if path==R.OFFICE:return data.office
        if path==R.STATE:return state
        if Path(path).name=='operator':return {'operator_token':'sk-local-operator'}
        if path==R.COMMON:return {}
        raise RuntimeError('Missing actual browser packet IO leaf')
    d={'read_private':read,'write_private':lambda path,value:writes.append(copy.deepcopy(value)),
        'native_client':lambda common:data.native,'provider':lambda:copy.deepcopy(provider),
        'capture':SimpleNamespace(MAX_RECORDS=32,capture_lock=contextlib.nullcontext,_read_locked=lambda:copy.deepcopy(captured)),
        'ClientSession':Session,'OPERATOR_STATE':Path('operator')}
    result=R.quota_run('quota-baseline',d)
    assert result['quota_stage']=='baseline_ready' and posts==[{'key':'b'*64,'max_budget':.12}]
    assert R.amount(data.keys[data.actor][1]['spend'])==Decimal('.12')
    with pytest.raises(RuntimeError,match='Missing actual browser packet'):R.quota_run('quota-verify',d)
    assert state['quota']['stage']=='restored' and posts[-1]=={'key':'b'*64,'max_budget':1000.0}
    count=len(posts);assert R.quota_run('quota-restore',d)['quota_stage']=='restored'
    assert len(posts)==count
    R.quota_cap_only(initial,R.inventory(data.native,data.office),'b'*64,Decimal(1000))
    assert any(v['quota']['journal']==['restrict_pre_write'] for v in writes)
    # No existing full-tape prefix may be truncated to fit the current limit.
    state.pop('quota');captured['requests']=[{'body':{'preserved':i}} for i in range(28)]
    state['capture_after']=copy.deepcopy(captured);before=len(posts)
    with pytest.raises(N.ProofError,match='capture_capacity'):R.quota_run('quota-baseline',d)
    assert len(posts)==before and 'quota' not in state and len(captured['requests'])==28


def test_quota_restore_refuses_active_native_tasks_before_any_budget_write(monkeypatch,tmp_path):
    monkeypatch.setattr(R,'PRIVATE',tmp_path)
    packet={'chat_id':str(uuid4())};(tmp_path/'office-delegation-quota.private.json').write_text(json.dumps(packet))
    actor,payer=str(uuid4()),str(uuid4());reads=[]
    class WebUI:
        def ok(self,method,path,**kwargs):
            reads.append((method,path));return {'task_ids':['actual-native-running-task']}
    office=prepared(actor,payer);office['office_delegation_setup']['actor']['token']='actor-IO-token'
    state={'quota':{'stage':'baseline_ready','original_cap':'1000','restricted_cap':'.12'}}
    with pytest.raises(N.ProofError,match='restore_background_active'):
        R.quota_restore(state,None,office,{'read_private':lambda path:packet,'WebUI':WebUI})
    assert reads==[('GET','/api/tasks/chat/'+packet['chat_id'])]


def test_quota_denial_join_uses_actual_gateway_signed_native_422_not_an_illustrated_envelope(monkeypatch,tmp_path):
    import asyncio,sys
    import test_capture_webui_auth as C
    from unittest.mock import patch
    groups,office,browser,context,d,tape=context_case(monkeypatch,tmp_path,quota=True)
    harness=C.CaptureContextsTests();module_guard=patch.dict(sys.modules);module_guard.start()
    try:
        asyncio.run(harness.asyncSetUp())
        owner,req,invoke,proxy,errors,events,error_type=harness.native_denial()
        carrier=req.data['litellm_metadata']; req.data.clear()
        wire=copy.deepcopy(browser['denied_wire']);wire['model']=R.MODELS[1]
        req.data.update(wire,litellm_metadata=carrier)
        with patch.object(C.C,'product_auth',return_value=invoke),patch.object(C.C,'product_denial_reader',return_value=owner.auth.personal_key_budget_denial),patch.dict(sys.modules,{'litellm.proxy.proxy_server':proxy}):
            with pytest.raises(error_type) as caught:asyncio.run(C.C.gateway_auth(req,owner.SECRET))
        assert caught.value is errors[0] and len([v for v in events if v[0]=='validate'])==1
        denied=C.C._read_locked()['requests'][0]
    finally:harness.doCleanups();module_guard.stop()
    actor,chat,answer=owner.USER,owner.ROOT_CHAT,owner.ROOT_ANSWER
    office['office_delegation_setup']['actor']['id']=actor
    for model in office['office_delegation_setup']['budget']['models']:
        model['key_hash']=('b' if model['model']==R.MODELS[0] else 'a')*64
    browser.update(chat_id=chat,answer_id=answer)
    rows=[]
    for call in groups[R.MODELS[0]]:
        call['verified_cost_scope'].update(user_id=actor,chat_id=chat,root_chat_id=chat,answer_id=answer,root_answer_id=answer)
        rows.append(dict(body=call['wire_before_auth'],body_after_auth=copy.deepcopy(call['wire_before_auth']),route='/responses',
            verified_cost_scope=call['verified_cost_scope'],native_auth_user_id=actor,native_auth_key_hash='b'*64,
            attestation_present_before=True,provenance_removed_after=True))
    rows.insert(3,denied)
    service_wire={'model':'gpt-6-luna','input':[],'store':False,'stream':False}
    service_body=R.proof.expected_provider_body(service_wire,'goal584-fake-office-service')
    service={'id':'source-service-IO-leaf','body':service_body,'lifecycle':{'terminal':True,'outcome':'completed'}}
    rows.append(dict(body=service_wire,body_after_auth=copy.deepcopy(service_wire),route='/responses',
        verified_cost_scope={'call_id':str(uuid4())},native_auth_user_id='service-IO-leaf',native_auth_key_hash='c'*64,
        attestation_present_before=True,provenance_removed_after=True))
    before={'provider':{'synthetic':True,'control':{},'requests':[]},'capture':{'requests':[]},
        'finance':{'personal':{R.MODELS[1]:{'key':{'token':'a'*64}}}}}
    provider={'synthetic':True,'control':{},'requests':[*tape,service]};captured={'requests':rows}
    joined,actual=R.quota_calls(before,provider,captured,office,browser,d)
    assert actual==denied and len(joined[R.MODELS[0]])==6
    for mutation in ('missing','wrong_key','status','root','worker_dispatch'):
        altered=copy.deepcopy(captured);physical=copy.deepcopy(provider);row=altered['requests'][3]
        if mutation=='missing':row.pop('native_budget_denial')
        elif mutation=='wrong_key':row['native_budget_denial']['key_hash']='d'*64
        elif mutation=='status':row['auth_failure']['status_code']=403
        elif mutation=='root':row['native_budget_denial']['scope']['root_chat_id']=str(uuid4())
        else:physical['requests'][-1]['body']['model']=R.WIRES[R.MODELS[1]]
        with pytest.raises((N.ProofError,ValueError)):
            R.quota_calls(before,physical,altered,office,browser,d)


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


def quota_workflow():
    import ast,yaml
    path=Path(__file__).resolve().parents[2]/'.github/workflows/goal584-office-proof.yml'
    workflow=yaml.safe_load(path.read_text(encoding='utf8'))
    steps=workflow['jobs']['office-build-proof']['steps']
    step=next(v for v in steps if v.get('name')=='Verify one exhausted Terra refusal after accepted positive delegation')
    source=step['run'].split("<<'PY'\n",1)[1].rsplit('\nPY',1)[0]
    return workflow,steps,ast.parse(source)


def test_workflow_adds_only_bounded_negative_and_recovery_steps_after_unchanged_positive():
    import ast,subprocess,yaml
    root=Path(__file__).resolve().parents[2];workflow,steps,tree=quota_workflow()
    old=yaml.safe_load(subprocess.check_output(['git','-c','gc.auto=0','show',
        '64d145639d33854697a95497bb6d15ceeec74aa6:.github/workflows/goal584-office-proof.yml'],cwd=root,timeout=5))
    names={'Verify one exhausted Terra refusal after accepted positive delegation',
           'Recover only a completed quota mutation before owned Compose teardown'}
    remaining=copy.deepcopy(workflow);remaining['jobs']['office-build-proof']['steps']=[v for v in steps if v.get('name') not in names]
    assert remaining==old
    positive=next(i for i,v in enumerate(steps) if v.get('name')=='Verify one ordinary delegated Office Send and native personal accounting')
    assert steps[positive+1]['name'] in names and steps[positive+1]['timeout-minutes']==8
    assert steps[positive+2]['name']=='Recover only a completed quota mutation before owned Compose teardown'
    assert steps[positive+2]['timeout-minutes']==2 and 'always()' in steps[positive+2]['if']
    assert workflow['jobs']['office-build-proof']['timeout-minutes']==55
    main=next(n for n in tree.body if isinstance(n,ast.Try));body=ast.unparse(main)
    assert body.index("setting('QUOTA_RESTORE_ARMED', True)")<body.index("baseline = phase(stage)")
    assert "run(browser, fixture, base, build, revision, quota=True)" in body
    assert 'browser.close()' in body and 'host_quota_restore(phase)' in body


def test_actual_context_heredoc_uses_six_real_parent_inputs_and_native_batches_4_plus_2(monkeypatch,tmp_path):
    import ast,hashlib
    groups,office,browser,context,d,physical=context_case(monkeypatch,tmp_path,quota=True)
    assert len(physical)==6
    _,_,tree=quota_workflow();node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='collect_context')
    prefix={'synthetic':True,'control':{'unchanged':True},'requests':[{'id':'prior','body':{'keep':'whole prefix'}}]}
    service={'id':'actual-service-transport-leaf','body':{'model':'goal584-fake-office-service'}}
    provider=dict(prefix,requests=copy.deepcopy(prefix['requests']+physical+[service]));original=copy.deepcopy(provider)
    qualification=R.QUALIFICATION.read_bytes();output=tmp_path/'output';output.mkdir();(output/'qualification.safe.json').write_bytes(qualification)
    batches=[];written=[];public=[]
    expected=[[v for v in row['response']['output'] if v.get('type')=='reasoning'] for row in physical]
    def native_context(base,build,revision,cases):
        start=sum(len(v) for v in batches);assert cases==expected[start:start+4]
        batches.append(copy.deepcopy(cases));return context['packets'][len(batches)-1]
    namespace={'fixture':SimpleNamespace(native_context=native_context),'private':tmp_path,'out':output,
        'base':'http://native-IO-leaf:8080','build':{'bound':'existing artifact IO'},'revision':'f'*40,
        'digest':R.proof.digest,'hashlib':hashlib,'json':json,
        'write_private':lambda path,value:written.append((path,copy.deepcopy(value))),
        'public':lambda name,value:public.append((name,value))}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual-workflow-context>','exec'),namespace)
    baseline={'provider_prefix_count':1,'provider_prefix_sha256':R.proof.digest(prefix)}
    namespace['collect_context'](provider,baseline)
    assert [len(v) for v in batches]==[4,2] and provider==original
    result=written[-1][1]
    assert written[-1][0].name=='office-delegation-quota-context.private.json'
    assert result['provider_ids']==[v['id'] for v in physical] and result['packets']==context['packets']
    assert result['binding']==context['binding'] and public[-1][1]['personal_provider_calls']==6
    for mutation in ('prefix','worker','duplicate'):
        changed=copy.deepcopy(provider)
        if mutation=='prefix':changed['requests'][0]['body']['keep']='changed'
        elif mutation=='worker':changed['requests'][-1]['body']['model']='goal584-fake-delegated-worker'
        else:changed['requests'][2]['id']=changed['requests'][1]['id']
        count=len(written)
        with pytest.raises(AssertionError):namespace['collect_context'](changed,baseline)
        assert len(written)==count


@pytest.mark.parametrize('mode',['success','baseline_failed_complete','baseline_timeout','verify_timeout','quiesce_failed','browser_unclosed'])
def test_actual_host_finally_never_restores_an_unconfirmed_mutation_or_accepts_failed_cleanup(monkeypatch,tmp_path,mode):
    import ast,hashlib,subprocess,time
    _,steps,tree=quota_workflow()
    events=[];published=[];timer=object();timer_events=[];envfile=tmp_path/'github-env';envfile.touch()
    monkeypatch.setenv('GITHUB_ENV',str(envfile))
    def leaf(command,**kwargs):
        phase=command[-1];events.append(phase)
        if mode=='baseline_timeout' and phase=='quota-baseline' or mode=='verify_timeout' and phase=='quota-verify':
            raise subprocess.TimeoutExpired(command,kwargs['timeout'])
        passed=not(mode=='baseline_failed_complete' and phase=='quota-baseline' or mode=='quiesce_failed' and phase=='quota-quiesce')
        value={'schema':1,'phase':phase,'passed':passed,'native_office_accepted':False,
            'source_sha256':R.sha256(Path(R.__file__).read_bytes()).hexdigest(),'quota_present':True,
            'quota_stage':'restored' if phase=='quota-restore' else 'baseline_ready'}
        return subprocess.CompletedProcess(command,0 if passed else 1,json.dumps(value).encode())
    monkeypatch.setattr(R.subprocess,'run',leaf)
    namespace={'Path':Path,'os':__import__('os'),'json':json,'hashlib':hashlib,'time':time,
        'signal':SimpleNamespace(ITIMER_REAL=timer,setitimer=lambda kind,value:timer_events.append((kind,value))),
        'quota_owner':R,'fixture':SimpleNamespace(command=['docker','compose']),
        'stage':'quota-baseline','armed':True,'unconfirmed':False,'browser_closed':mode!='browser_unclosed',
        'restored':False,'deadline':time.monotonic()+300,'observed':{'external_browser_leaf':True},
        'public':lambda name,value:published.append((name,value))}
    functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('setting','mutation','phase')]
    exec(compile(ast.Module(body=functions,type_ignores=[]),'<actual-workflow-phase-functions>','exec'),namespace)
    main=copy.deepcopy(next(n for n in tree.body if isinstance(n,ast.Try)))
    # Only the browser/source-preparation IO work is replaced. The exception,
    # finally, marker, attached phase helper and final acceptance are actual.
    main.body=ast.parse("baseline=phase('quota-baseline')\nfinancial=phase('quota-verify')").body
    tail=tree.body[tree.body.index(next(n for n in tree.body if isinstance(n,ast.Try)))+1:]
    program=compile(ast.fix_missing_locations(ast.Module(body=[main,*tail],type_ignores=[])),'<actual-workflow-finally>','exec')
    if mode=='success':exec(program,namespace)
    else:
        with pytest.raises((AssertionError,N.ProofError)):exec(program,namespace)
    if mode in ('baseline_timeout','verify_timeout','browser_unclosed'):
        assert 'quota-restore' not in events and 'quota-quiesce' not in events
    elif mode=='quiesce_failed':assert events[-2:]==['quota-status','quota-quiesce'] and 'quota-restore' not in events
    else:assert events[-3:]==['quota-status','quota-quiesce','quota-restore']
    accepted=[v for name,v in published if name=='office-delegation-quota' and v.get('passed') is True]
    assert bool(accepted) is (mode=='success')
    assert timer_events==[(timer,140),(timer,0)]
    if mode in ('baseline_timeout','verify_timeout'):
        assert namespace['unconfirmed'] is True and envfile.read_text().splitlines()[-1]=='QUOTA_MUTATION_UNCONFIRMED=true'
    recovery=next(v for v in steps if v.get('name')=='Recover only a completed quota mutation before owned Compose teardown')['run']
    guard=next(n for n in ast.parse(recovery.split("<<'PY'\n",1)[1].rsplit('\nPY',1)[0]).body if isinstance(n,ast.Assert))
    with pytest.raises(AssertionError):
        exec(compile(ast.Module(body=[guard],type_ignores=[]),'<actual-always-recovery-guard>','exec'),
            {'os':SimpleNamespace(environ={'QUOTA_MUTATION_UNCONFIRMED':'true','QUOTA_BROWSER_CLOSED':'true'})})
