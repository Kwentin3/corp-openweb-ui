"""Batch collector joins real public clients/provenance/cost reader over HTTP leaves."""
import copy
import asyncio
from contextlib import redirect_stdout
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from hashlib import sha256
import json
import io
import os
from pathlib import Path
import sys
import stat
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parents[1]/'deploy/openwebui-budgets')]
import test_unknown_usage_gui_fixture as setup_tests
from test_unknown_usage_gui_fixture import Response
import unknown_usage_gui_fixture as setup_owner
import prove_unknown_usage_gui as C
import prove_service_tasks as provider_owner


class CollectorTests(unittest.TestCase):
    def setUp(self):
        setup_tests.UnknownGuiSetupTests.setUp(self)
        self.common['started_at_utc']=(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()
        self.loop.run_until_complete(setup_owner.setup_unknown_usage_gui(self.webui,self.common,self.office,self.path))
        self.enterContext(patch.object(C,'STATE',self.path))
        self.enterContext(patch.object(C,'COMMON',self.path.with_name('common.private.json')))
        self.enterContext(patch.object(C,'OFFICE',self.path.with_name('office.private.json')))
        self.enterContext(patch.object(C,'PACKET',self.path.with_name('packet.private.json')))
        C.P.fixture.write_private(C.COMMON,self.common);C.P.fixture.write_private(C.OFFICE,self.office)
        self.enterContext(patch.object(C.P.fixture,'WebUI',return_value=self.webui))
        self.enterContext(patch.object(provider_owner,'build_opener',return_value=self.wire))
        # Provider control GET shares the real urllib leaf, never the WebUI API.
        original_open=self.wire.open
        def open_request(request,timeout):
            from urllib.parse import urlsplit
            if urlsplit(request.full_url).hostname=='provider':
                return Response(*self.wire.handle(request.get_method(),request.full_url,dict(request.header_items())))
            return original_open(request,timeout)
        self.enterContext(patch.object(self.wire,'open',side_effect=open_request))
        original_native=self.wire.native_handle
        def native_request(method,url,headers,body=None,params=None):
            from urllib.parse import urlsplit
            if urlsplit(url).path in ('/spend/logs/v2',C.P.SESSION_ROUTE):
                return self.wire.handle(method,url,headers,body,params)
            return original_native(method,url,headers,body,params)
        self.enterContext(patch.object(self.wire,'native_handle',side_effect=native_request))
        def get(session,url,*,params,headers,allow_redirects,timeout):
            self.assertFalse(allow_redirects)
            return Response(*self.wire.handle('GET',url,headers,params=params))
        self.enterContext(patch.object(C.P.ClientSession,'get',get))
        self.enterContext(patch.object(C.P,'MOUNTED_SOURCES',{
            'usage_guard_fixture.py':HERE/'usage_guard_fixture.py',
            'unknown_usage_guard.py':HERE.parents[1]/'deploy/openwebui-budgets/unknown_usage_guard.py'}))
        assignment=sys.modules['employee_budget_assignment']
        self.old_ids=[]
        for account,model in ((self.wire.old_user,'goal584-a'),(self.wire.office_user,'gpt-5.4-mini')):
            uid=account['id'];self.old_ids.append(uid)
            self.wire.users[uid]={'user_id':uid,'user_role':'internal_user','models':[model],'max_budget':100,
                'spend':0,'budget_duration':'1mo','budget_reset_at':'2099-01-01T00:00:00Z','teams':[]}
            key_hash=sha256(uid.encode()).hexdigest()
            self.wire.keys[key_hash]={'token':key_hash,'user_id':uid,'models':[model],'key_alias':assignment.assignment_alias(uid,model),
                'metadata':assignment.assignment_metadata(model),'max_budget':100,'spend':0,'total_spend':0,'budget_duration':'1mo',
                'budget_reset_at':'2099-01-01T00:00:00Z','blocked':False,'team_id':None}
        # Actual GUI own keys start with zero lifetime in the native owner.
        for key in self.wire.keys.values():key.setdefault('total_spend',0)
        self.wire.rows.append({'request_id':'private-old-history','user':self.old_ids[0],'spend':0,'status':'failure'})
        self.wire.physical.append({'id':'old-office-provider-record'})
        original=C.P.fixture.native_client
        def native():
            value=original();value.timeout=.35;return value
        self.enterContext(patch.object(C.P.fixture,'native_client',side_effect=native))
        for model in self.wire.models:
            model['model_info']['supports_native_streaming'] = False
        self.run_phase('baseline')
        self.initial_requests=len(self.wire.requests)

    def tearDown(self):
        setup_tests.UnknownGuiSetupTests.tearDown(self)

    def run_phase(self,phase):
        return self.loop.run_until_complete(C.execute(phase))

    def build_packet(self):
        packet={'schema':1,'actor_id':self.wire.actor_id,'calls':[],
                'foreign_chat_status':401,'foreign_chat_detail':C.CHAT_NOT_FOUND,'foreign_chat_not_found':True,
                'foreign_auth_confirmed':True,'foreign_auth':{'http_status':200,'session':{'id':self.common['users'][0]['id'],'role':'user'}},
                'office_settings_before':{'unchanged':True},'office_settings_after':{'unchanged':True}}
        for index,slot in enumerate(C.ORDER):
            alias=C.P.ALIASES[slot];chat,answer,user=(str(uuid4()) for _ in range(3))
            text=C.UNKNOWN if slot else C.KNOWN+' · на 12:00:00 UTC'
            a={'id':answer,'parentId':user,'role':'assistant','model':alias,'done':True}
            if index in C.DENIED:
                a.update(error={'content':C.BLOCKED},content='',statusHistory=[])
            else:
                a.update(error=None,content='',output=[{'type':'message','role':'assistant','content':[
                    {'type':'output_text','text':'Proof','annotations':[]}]}],
                    statusHistory=[{'action':C.FILTER_ID,'done':True,'description':text}])
                # Real provenance owner issues the token; collector reads only
                # persisted scope. No collector-supplied call nonce exists.
                token=C.P.encode_call(self.wire.gateway,user_id=self.wire.actor_id,model=alias,chat_id=chat,answer_id=answer,
                                      root_chat_id=chat,root_answer_id=answer)
                native_request={'model':alias,'input':'Hi','max_output_tokens':16,'store':False,'stream':False,
                    'litellm_metadata':{C.P.PROVENANCE_FIELD:token}}
                self.wire.handle('POST','http://proxy:4000/v1/responses',{'Authorization':'Bearer '+self.wire.gateway,
                    C.P.USER_ID_HEADER:self.wire.actor_id,C.P.TASK_HEADER:''},native_request)
                record=self.wire.physical[-1]
                # This collector fixture observes the already-buffered HTTP leaf;
                # native adapter/authorization origin is qualified separately.
                record['body'].pop('stream')
                record['body']['input']=[{'type':'message','role':'user','content':[{'type':'input_text','text':'Hi'}]}]
                row=self.wire.rows[-1]
                if slot:
                    row.update(prompt_tokens=0,completion_tokens=0,total_tokens=0)
                ownkey=self.wire.keys[row['api_key']];ownkey['total_spend']=ownkey['spend']
            u={'id':user,'parentId':None,'role':'user','content':'Hi','childrenIds':[answer]}
            packet['calls'].append({'model':alias,'chat_id':chat,'submitted':{'model':alias,'stream':True,'id':answer,
                'parent_id':None,'user_message':u,'message_ids':[{'model_id':alias,'message_id':answer,'modelIdx':0}],
                'background_tasks':{'title_generation':False,'tags_generation':False,'follow_up_generation':False}},
                'acknowledgement':{'chat_id':chat},'http_status':200,'task_ids':[],
                'stored':{'id':chat,'user_id':self.wire.actor_id,'chat':{'models':[alias],
                    'history':{'currentId':answer,'messages':{user:u,answer:a}}}},
                'visible_status':None if index in C.DENIED else text,
                'visible_error':C.BLOCKED if index in C.DENIED else None,
                'visible_text':C.BLOCKED if index in C.DENIED else 'Proof\n'+text})
        C.P.fixture.write_private(C.PACKET,packet)
        return packet

    def test_actual_ack_scopes_provider_prefix_native_money_and_viewer(self):
        self.build_packet();before=len(self.wire.requests);result=self.run_phase('verify')
        self.assertTrue(result['passed']);self.assertEqual(result['known_positive_total'],'.332')
        self.assertEqual(result['provider_dispatches'],4);self.assertFalse(result['native_401_inferred'])
        self.assertEqual(result['foreign_chat_status'],401);self.assertTrue(result['foreign_auth_confirmed'])
        self.assertTrue(result['foreign_chat_not_found'])
        self.assertFalse(result['unknown_cost_finality']);self.assertFalse(result['production_accepted'])
        self.assertEqual(len(self.wire.physical),5)
        self.assertTrue(all(method=='GET' for method,_,_ in self.wire.requests[before:]))
        self.assertEqual(self.network_attempts,[])

    def test_buffered_profile_requires_native_false_flag_on_every_model(self):
        self.build_packet();before=len(self.wire.physical)
        for value in (None, True, 'false', 0):
            with self.subTest(value=value):
                self.wire.models[1]['model_info']['supports_native_streaming']=value
                with self.assertRaisesRegex(C.P.ProofError,'unknown_unbuffered_deployment'):
                    self.run_phase('verify')
        del self.wire.models[1]['model_info']['supports_native_streaming']
        with self.assertRaisesRegex(C.P.ProofError,'unknown_unbuffered_deployment'):
            self.run_phase('verify')
        self.assertEqual(len(self.wire.physical),before)

    def test_blocked_feedback_does_not_expose_administrative_api_paths(self):
        packet=self.build_packet();denied=packet['calls'][2]
        suffix=' Update via /key/unblock.'
        denied['visible_text']+=suffix;denied['visible_error']+=suffix
        denied['stored']['chat']['history']['messages'][denied['submitted']['id']]['error']['content']+=suffix
        C.P.fixture.write_private(C.PACKET,packet)
        with self.assertRaisesRegex(C.P.ProofError,'unknown_gui_saved_denial'):
            self.run_phase('verify')

    def test_exact_buffered_provider_transport_and_native_ui_stream_are_required(self):
        packet=self.build_packet()
        for stream in (False, True):
            with self.subTest(provider_stream=stream):
                self.wire.physical[-1]['body']['stream']=stream
                with self.assertRaisesRegex(C.P.ProofError,'unknown_gui_provider_context'):
                    self.run_phase('verify')
        self.wire.physical[-1]['body'].pop('stream')
        packet['calls'][0]['submitted']['stream']=False
        C.P.fixture.write_private(C.PACKET,packet)
        with self.assertRaisesRegex(C.P.ProofError,'unknown_gui_submitted_context'):
            self.run_phase('verify')

    def test_foreign_native_scope_and_extra_dispatch_reject(self):
        self.build_packet();row=self.wire.rows[1];scope=row['metadata']['spend_logs_metadata']['owui_budget']
        scope['user_id']=str(uuid4())
        with self.assertRaises(C.P.ProofError):self.run_phase('verify')
        retained=C.P.fixture.read_private(C.STATE)['unknown_gui_verification']['native']['rows']
        self.assertEqual(next(r for r in retained if r['request_id']==row['request_id'])['metadata']
                         ['spend_logs_metadata']['owui_budget']['user_id'],scope['user_id'])
        scope['user_id']=self.wire.actor_id
        self.wire.physical.append(copy.deepcopy(self.wire.physical[-1]))
        with self.assertRaisesRegex(C.P.ProofError,'provider_prefix'):self.run_phase('verify')

    def test_foreign_chat_401_requires_fresh_other_user_session_and_native_not_found(self):
        packet=self.build_packet()
        for mutate in (lambda p:p.update(foreign_chat_status=200),lambda p:p.update(foreign_chat_status=404),
                       lambda p:p.update(foreign_chat_detail='Invalid token'),lambda p:p.update(foreign_chat_not_found=False),
                       lambda p:p.update(foreign_auth_confirmed=False),lambda p:p['foreign_auth'].update(http_status=401),
                       lambda p:p['foreign_auth']['session'].update(id=self.wire.actor_id),
                       lambda p:p['foreign_auth']['session'].update(id=str(uuid4())),
                       lambda p:p['foreign_auth']['session'].update(role='admin')):
            with self.subTest(mutate=mutate):
                changed=copy.deepcopy(packet);mutate(changed);C.P.fixture.write_private(C.PACKET,changed)
                with self.assertRaisesRegex(C.P.ProofError,'foreign_session|foreign_or_office_settings'):
                    self.run_phase('verify')

    def test_old_history_and_caps_are_not_repaired(self):
        self.build_packet();self.wire.rows[0]['spend']=.1
        with self.assertRaisesRegex(C.P.ProofError,'old_accounts'):self.run_phase('verify')
        self.wire.rows[0]['spend']=0
        key=next(k for k in self.wire.keys.values() if k['user_id']==self.wire.actor_id)
        key['max_budget']=3
        with self.assertRaisesRegex(C.P.ProofError,'caps_or_policy'):self.run_phase('verify')

    def test_unknown_visible_amount_and_missing_known_usage_reject(self):
        packet=self.build_packet();packet['calls'][1]['visible_text']+=' $0.00'
        C.P.fixture.write_private(C.PACKET,packet)
        with self.assertRaisesRegex(C.P.ProofError,'visible_unknown_amount'):self.run_phase('verify')
        packet['calls'][1]['visible_text']=C.UNKNOWN;C.P.fixture.write_private(C.PACKET,packet)
        self.wire.physical[1]['response'].pop('usage')
        with self.assertRaisesRegex(C.P.ProofError,'provider_usage'):self.run_phase('verify')

    def test_saved_failure_cannot_be_reported_as_success(self):
        packet=self.build_packet();call=packet['calls'][0]
        call['stored']['chat']['history']['messages'][call['submitted']['id']]['error']={'message':'failure'}
        C.P.fixture.write_private(C.PACKET,packet)
        with self.assertRaisesRegex(C.P.ProofError,'saved_success'):self.run_phase('verify')

    def test_submitted_message_selection_and_stored_owner_are_actual_bindings(self):
        packet=self.build_packet();selection=packet['calls'][0]['submitted']['message_ids'][0]
        original=selection['message_id'];selection['message_id']=str(uuid4())
        C.P.fixture.write_private(C.PACKET,packet)
        with self.assertRaisesRegex(C.P.ProofError,'submitted_context'):self.run_phase('verify')
        selection['message_id']=original;packet['calls'][0]['stored']['user_id']=str(uuid4())
        C.P.fixture.write_private(C.PACKET,packet)
        with self.assertRaisesRegex(C.P.ProofError,'chat_owner'):self.run_phase('verify')

    def test_counter_lag_is_bounded_and_unsettled_is_not_success(self):
        self.build_packet();original=self.wire.native_handle;reads=[]
        def lag(method,url,headers,body=None,params=None):
            from urllib.parse import urlsplit,parse_qs
            status,value=original(method,url,headers,body,params)
            query=params or {k:v[0] for k,v in parse_qs(urlsplit(url).query).items()}
            if urlsplit(url).path=='/user/info' and query.get('user_id')==self.wire.actor_id and 'user_info' in value:
                reads.append(True)
                if len(reads)<3:value['user_info']['spend']=0
            return status,value
        with patch.object(self.wire,'native_handle',side_effect=lag):self.assertTrue(self.run_phase('verify')['passed'])
        self.wire.users[self.wire.actor_id]['spend']=0
        with self.assertRaisesRegex(C.P.ProofError,'Timed out|deadline expired'):self.run_phase('verify')

    def test_baseline_window_is_real_and_cannot_expire_silently(self):
        self.build_packet();state=C.P.fixture.read_private(C.STATE)
        state['unknown_gui_baseline']['start_utc']=(datetime.now(timezone.utc)-timedelta(minutes=16)).isoformat()
        C.P.fixture.write_private(C.STATE,state)
        with self.assertRaisesRegex(C.P.ProofError,'query_window'):self.run_phase('verify')

    def test_viewer_cannot_confirm_unknown_without_marker_or_accept_foreign_rows(self):
        self.build_packet();row=next(r for r in self.wire.rows if r.get('model_group')==C.P.ALIASES[1])
        guard=row['metadata'].pop('guardrail_information')
        with self.assertRaisesRegex(C.P.ProofError,'viewer_failure'):self.run_phase('verify')
        row['metadata']['guardrail_information']=guard;self.wire.foreign_viewer=True
        with self.assertRaisesRegex(C.P.ProofError,'viewer_failure'):self.run_phase('verify')

    def test_own_zero_auth_audit_has_no_invented_http_or_chat_binding(self):
        self.build_packet();key=next(k for k in self.wire.keys.values()
            if k['user_id']==self.wire.actor_id and k['models']==[C.P.ALIASES[1]])
        audit={'request_id':'opaque-denied-native-row','user':self.wire.actor_id,'api_key':key['token'],
               'model_group':C.P.ALIASES[1],'status':'failure','spend':0,'metadata':None}
        self.wire.rows.append(audit)
        result=self.run_phase('verify');self.assertFalse(result['native_401_inferred'])
        self.assertFalse(result['unbound_denial_audit_chat_association_independently_proven'])
        audit['spend']=.1
        with self.assertRaisesRegex(C.P.ProofError,'unbound_failure_audit'):self.run_phase('verify')


class AdminReceiptTests(unittest.TestCase):
    def invoke(self, phase, *, error=None):
        temp = TemporaryDirectory(); self.addCleanup(temp.cleanup)
        private = Path(temp.name)
        if os.name == 'nt':
            import prove_gateway_auth as private_owner
            self.enterContext(patch.object(private_owner.stat, 'S_IMODE',
                side_effect=lambda mode: 0o700 if stat.S_ISDIR(mode) else 0o600))
        for name in ('PRIVATE', 'STATE', 'ADMIN_STATE'):
            value = private if name == 'PRIVATE' else private / (name.lower() + '.private.json')
            self.enterContext(patch.object(C, name, value))
        C.P.fixture.write_private(C.STATE, {'legacy': 'untouched'})
        original = C.STATE.read_bytes()
        async def execute(actual):
            self.assertEqual(actual, phase)
            if error is not None: raise error
            return {'status': 'baseline_ready', 'inference_issued': False, 'admin_source_sha256': {'actual.py': 'a' * 64}}
        output = io.StringIO()
        with patch.object(sys, 'argv', ['proof', '--phase', phase]), patch.object(C, 'execute', execute), redirect_stdout(output):
            code = C.main()
        self.assertEqual(C.STATE.read_bytes(), original)
        receipt = private / ('admin-unknown-' + phase.removeprefix('admin-') + '.safe.json')
        result = C.P.fixture.read_private(receipt)
        self.assertEqual(result, json.loads(output.getvalue()))
        self.assertEqual(result['proof'], C.ADMIN_PROOF)
        self.assertEqual(result['phase'], phase)
        self.assertIs(result['inference_issued'], False)
        self.assertIs(result['whole_goal_accepted'], False)
        self.assertIs(result['production_accepted'], False)
        return code, result

    def test_optin_success_preserves_legacy_state_and_source_receipt(self):
        code, result = self.invoke('admin-baseline')
        self.assertEqual(code, 0)
        self.assertIs(result['passed'], True)
        self.assertEqual(result['admin_source_sha256'], {'actual.py': 'a' * 64})
        self.assertFalse(C.ADMIN_STATE.exists())

    def test_optin_failure_keeps_raw_error_in_separate_private_state(self):
        private_error = 'private synthetic native diagnostic'
        code, result = self.invoke('admin-verify', error=C.P.ProofError(private_error))
        self.assertEqual(code, 1)
        self.assertIs(result['passed'], False)
        self.assertEqual(result['failure'], 'admin_unknown_contract_failed')
        self.assertNotIn(private_error, json.dumps(result))
        self.assertEqual(C.P.fixture.read_private(C.ADMIN_STATE)['admin_unknown_error']['message'], private_error)

    def test_native_source_closure_only_reads_consumed_source_files(self):
        import provision_admin
        budgets = HERE.parents[1] / 'deploy/openwebui-budgets'
        mounted = {'usage_guard_fixture.py': HERE / 'usage_guard_fixture.py',
                   'unknown_usage_guard.py': budgets / 'unknown_usage_guard.py'}
        def forbidden(*args, **kwargs): raise AssertionError('source closure must not perform runtime IO')
        with patch.object(C.P, 'MOUNTED_SOURCES', mounted), patch.object(provision_admin, 'SOURCE', budgets / 'admin_tools.py'), \
                patch.object(C.P.fixture, 'write_private', forbidden), patch.object(C.P.fixture, 'WebUI', forbidden), \
                patch.object(C.P.fixture, 'native_client', forbidden), patch.object(C.P, 'provider', forbidden):
            result = C.admin_sources()
        self.assertEqual(set(result['admin_source_sha256']), {'provision_admin.py', 'verify_admin_calls.py',
            'prove_office_delegation_readback.py', 'prove_office_readback.py', 'prove_office_compatibility.py',
            'mock_provider.py', 'capture_webui_auth.py'})
        self.assertEqual(set(result['admin_producer_sha256']), {'admin_tools.py', 'admin_ui.py', 'admin_policy.py'})
        for values in result.values():
            self.assertTrue(values)
            self.assertTrue(all(len(value) == 64 for value in values.values()))


class AdminCollectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        import test_mock_provider as provider_tests
        native = HERE.parents[1].with_name('corp-openweb-ui-goal584') / 'local/goal584/cost-display/open-webui/backend/open_webui'
        with patch.dict(os.environ, GOAL584_NATIVE_SOURCE_ROOT=str(native)):
            provider_tests.AdminResponsesProviderTests.setUpClass()
        cls.provider_tests = provider_tests

    def case(self):
        """Reuse actual native provider/context conversion, not a history builder."""
        from types import SimpleNamespace
        import base64
        from verify_admin_calls import FormParser
        H = self.provider_tests.AdminResponsesProviderTests
        helper = H(methodName='test_native_two_rounds_preserve_context_and_full_known_usage')
        helper.setUp(); self.addCleanup(helper.doCleanups)
        admin, actor, chat, answer, user = (str(uuid4()) for _ in range(5)); key = 'a' * 64
        import importlib.util
        ui_spec = importlib.util.spec_from_file_location('admin_collector_actual_ui', HERE.parents[1]/'deploy/openwebui-budgets/admin_ui.py')
        ui = importlib.util.module_from_spec(ui_spec); ui_spec.loader.exec_module(ui)
        public_row = {'user_id': actor, 'name': 'Synthetic employee', 'email': 'employee@example.invalid',
            'department': '', 'revision': 'c'*64, 'budget_usd': '6', 'spend_usd': '.332', 'remaining_usd': '5.668',
            'expense_status': 'unknown', 'models': [{'id': alias, 'label': alias, 'cap_usd': '2',
                'spend_usd': '.332' if index == 0 else '0', 'share_percent': '', 'blocked': bool(index),
                'expense_status': 'unavailable' if index == 0 else 'unknown'} for index,alias in enumerate(C.P.ALIASES)]}
        helper.embeds = [ui.render_editor([public_row], as_of='2026-11-08T00:00:00Z')]
        from prove_office_compatibility import expected_provider_body
        first = helper.first()
        first = expected_provider_body({**first, 'model': C.P.ALIASES[0], 'stream': True}, C.P.WIRES[0], provider_transport='buffered')
        code, emitted = helper.send(first); self.assertEqual(code, 200)
        second = helper.second(first, emitted)
        second = expected_provider_body({**second, 'model': C.P.ALIASES[0], 'stream': True}, C.P.WIRES[0], provider_transport='buffered')
        code, final_response = helper.send(second); self.assertEqual(code, 200)
        physical = copy.deepcopy(self.provider_tests.MOCK.REQUESTS)
        scopes = [dict(schema=1, category='personal', user_id=admin, model=C.P.ALIASES[0],
            chat_id=chat, root_chat_id=chat, answer_id=answer, root_answer_id=answer, call_id=str(uuid4())) for _ in range(2)]
        captures = []
        for payload, scope in zip((first, second), scopes):
            wire = copy.deepcopy(payload); wire.update(model=C.P.ALIASES[0], stream=True)
            captures.append(dict(body=wire, body_after_auth=copy.deepcopy(wire), route='/responses',
                native_auth_user_id=admin, native_auth_key_hash=key, attestation_present_before=True,
                provenance_removed_after=True, verified_cost_scope=scope))
        service_scope = {'call_id': str(uuid4()), 'category': 'service'}
        service_wire = {'model': 'gpt-6-luna', 'input': [{'role': 'user', 'content': H.intent}]}
        captures.append(dict(body=service_wire, body_after_auth=copy.deepcopy(service_wire), route='/responses',
            native_auth_user_id='service-payer', native_auth_key_hash='b'*64, attestation_present_before=True,
            provenance_removed_after=True, verified_cost_scope=service_scope))
        physical.append({'id': 'service-response', 'body': {**service_wire, 'model': 'goal584-fake-office-service'},
                         'lifecycle': {'terminal': True, 'outcome': 'completed'}})
        # Persist native converter output rather than synthesizing its tool pair.
        values = second['input']; call = copy.deepcopy(emitted['output'][0]); call['status'] = 'completed'
        result = copy.deepcopy(next(v for v in values if v.get('type') == 'function_call_output'))
        result.update(status='completed', embeds=copy.deepcopy(helper.embeds),
                      output=[{'type': 'input_text', 'text': helper.result_text}])
        response = {'id': answer, 'parentId': user, 'role': 'assistant', 'model': 'goal584-budget-admin',
                    'done': True, 'output': [call, result, *copy.deepcopy(final_response['output'])]}
        parent = {'id': user, 'parentId': None, 'childrenIds': [answer], 'role': 'user', 'content': H.intent}
        sent = {'id': answer, 'model': 'goal584-budget-admin', 'parent_id': None, 'user_message': copy.deepcopy(parent)}
        saved = {'id': chat, 'user_id': admin, 'chat': {'history': {'currentId': answer, 'messages': {user: parent, answer: response}}}}
        packet = {'schema': 1, 'admin_id': admin, 'actor_id': actor, 'model_id': 'goal584-budget-admin',
            'http_status': 200, 'task_ids': [], 'submitted': sent, 'raw_submission': json.dumps(sent),
            'acknowledgement': {'chat_id': chat}, 'raw_acknowledgement_base64': base64.b64encode(json.dumps({'chat_id': chat}).encode()).decode(),
            'stored_chat': saved, 'html': helper.embeds[0], 'html_sha256': sha256(helper.embeds[0].encode()).hexdigest()}
        # The existing pure parser independently reads that actual native embed.
        parser = FormParser(packet['html']); packet['rows'] = json.loads(parser.blocks[0])
        self.assertEqual(packet['rows'][0]['user_id'], actor)
        return SimpleNamespace(before={'provider': {'synthetic': True, 'control': {}, 'requests': []}, 'capture': {'requests': []}},
            provider={'synthetic': True, 'control': {}, 'requests': physical}, captured={'requests': captures},
            main_scopes=scopes, saved=saved, packet=packet, final=response, selected={'admin': {'id': admin}, 'actor_id': actor},
            admin=admin, chat=chat, answer=answer, key=key)

    def test_shared_join_and_existing_full_native_provider_grammar(self):
        data = self.case(); main, service = C.admin_calls(data.before, data.provider, data.captured)
        self.assertEqual(len(main), 2); self.assertEqual(service['provider']['id'], 'service-response')
        C.admin_context(main, data.final)
        chat, answer, _, rows = C.admin_browser(data.packet, data.saved, data.selected)
        self.assertEqual((chat, answer, rows[0]['user_id']), (data.chat, data.answer, data.selected['actor_id']))

    def test_full_skill_context_tool_result_and_prefix_must_not_be_repaired(self):
        for mutation in ('skill', 'result', 'extra', 'rewritten_prefix', 'forged_token'):
            data = self.case()
            if mutation == 'skill':
                for body in (data.captured['requests'][0]['body'], data.captured['requests'][0]['body_after_auth'], data.provider['requests'][0]['body']):
                    body['instructions'] = 'omitted native Skill'
            elif mutation == 'result':
                item = next(v for v in data.provider['requests'][1]['body']['input'] if v.get('type') == 'function_call_output'); item['output'] = '{}'
            elif mutation == 'extra': data.provider['requests'].append(copy.deepcopy(data.provider['requests'][0]))
            elif mutation == 'rewritten_prefix': data.before['provider']['requests'] = [{'id': 'lost-prior-call'}]
            else: data.captured['requests'][0]['auth_failure'] = {'status_code': 403}
            with self.subTest(mutation=mutation), self.assertRaises((C.P.ProofError, ValueError)):
                C.admin_calls(data.before, data.provider, data.captured)

    def test_native_stored_tool_result_must_equal_actual_next_request(self):
        data = self.case(); main, _ = C.admin_calls(data.before, data.provider, data.captured)
        data.final['output'][1]['output'][0]['text'] = '{}'
        with self.assertRaisesRegex(C.P.ProofError, 'tool_result_binding'): C.admin_context(main, data.final)

    def test_saved_embed_parser_rejects_forgery_before_any_native_finance(self):
        data = self.case(); data.packet['rows'] = []
        with self.assertRaises((AssertionError, C.P.ProofError)): C.admin_browser(data.packet, data.saved, data.selected)
        data.packet['html'] += '<script id="budget-data">[]</script>'
        data.packet['html_sha256'] = sha256(data.packet['html'].encode()).hexdigest()
        data.final['output'][1]['embeds'] = [data.packet['html']]
        with self.assertRaises((AssertionError, C.P.ProofError)): C.admin_browser(data.packet, data.saved, data.selected)

    def test_actual_cost_reader_and_native_counter_cardinality_scope_join(self):
        import importlib.util
        from types import SimpleNamespace
        from provenance import ProtocolError
        path = HERE.parents[1] / 'deploy/openwebui-budgets/tests/test_cost_readback.py'
        spec = importlib.util.spec_from_file_location('admin_actual_cost_fixture', path)
        T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)
        data = self.case(); main, _ = C.admin_calls(data.before, data.provider, data.captured)
        rows = []
        for index, scope in enumerate(data.main_scopes):
            r = T.row('admin-row-'+str(index), spend='.166', model=C.P.ALIASES[0], chat=data.chat,
                      answer=data.answer, call_id=scope['call_id'])
            r.update(user=data.admin, api_key=data.key, model_group=C.P.ALIASES[0])
            r['metadata']['spend_logs_metadata']['owui_budget'] = scope
            rows.append(r)
        owner = SimpleNamespace(requests=[], handler=None, payload=T.page(rows))
        async def read():
            return await C.P.read_cost_snapshot(T._MemoryReadSession(owner), base_url='http://native-fixture.invalid',
                read_key='private-viewer', user_id=data.admin, root_chat_id=data.chat, root_answer_id=data.answer,
                observed_call_ids=[s['call_id'] for s in data.main_scopes])
        cost = asyncio.run(read())
        user = {'user_id': data.admin, 'user_role': 'internal_user', 'models': [], 'max_budget': 2, 'spend': 0,
                'budget_duration': '30d', 'budget_reset_at': '2026-12-01T00:00:00Z'}
        key = {'token': data.key, 'user_id': data.admin, 'models': [C.P.ALIASES[0]], 'key_alias': 'native-known-assignment',
               'budget_duration': '30d', 'budget_reset_at': '2026-12-01T00:00:00Z', 'spend': 0, 'max_budget': 2, 'blocked': False}
        before = {'own': {'native': {'user': user, 'keys': {C.P.ALIASES[0]: key}, 'rows': []}},
                  'unknown': {'durable-marker': 'retained'}, 'old': {'staff': 'unchanged'}}
        after = copy.deepcopy(before); after['own']['native']['rows'] = rows
        after['own']['native']['user']['spend'] = after['own']['native']['keys'][C.P.ALIASES[0]]['spend'] = .332
        kwargs = dict(admin=data.admin, chat=data.chat, answer=data.answer)
        C.admin_native(before, after, main, cost, **kwargs)
        from dataclasses import replace
        with self.assertRaisesRegex(C.P.ProofError, 'cost_snapshot'):
            C.admin_native(before, after, main, replace(cost, user_id=str(uuid4())), **kwargs)
        with self.assertRaisesRegex(C.P.ProofError, 'cost_snapshot'):
            C.admin_native(before, after, main, replace(cost, root_chat_id=str(uuid4())), **kwargs)
        with self.assertRaisesRegex(C.P.ProofError, 'cost_snapshot'):
            C.admin_native(before, after, main, replace(cost, root_answer_id=str(uuid4())), **kwargs)
        for mutation in ('counter', 'foreign_scope', 'service_charge', 'old_marker', 'extra_row'):
            changed, calls = copy.deepcopy(after), copy.deepcopy(main)
            if mutation == 'counter': changed['own']['native']['user']['spend'] = .4
            elif mutation == 'foreign_scope': calls[0]['verified_cost_scope']['user_id'] = str(uuid4())
            elif mutation == 'service_charge': calls[0]['verified_cost_scope']['category'] = 'service'
            elif mutation == 'old_marker': changed['unknown'] = {}
            else: changed['own']['native']['rows'].append(copy.deepcopy(rows[0]))
            with self.subTest(mutation=mutation), self.assertRaises((C.P.ProofError, ProtocolError)):
                C.admin_native(before, changed, calls, cost, **kwargs)

    def test_rendered_native_counter_fields_cannot_be_forged(self):
        data = self.case(); rows = data.packet['rows']
        budget = {'spend': '.332', 'max_budget': '6', 'models': [
            {'model': m['id'], 'spend': m['spend_usd'], 'max_budget': m['cap_usd']} for m in rows[0]['models']]}
        C.admin_row_counters(rows, budget)
        changed = copy.deepcopy(rows); changed[0]['models'][1]['spend_usd'] = '9'
        with self.assertRaisesRegex(C.P.ProofError, 'render_model_counter'): C.admin_row_counters(changed, budget)
        changed = copy.deepcopy(rows); changed[0]['budget_usd'] = '9'
        with self.assertRaisesRegex(C.P.ProofError, 'render_counter'): C.admin_row_counters(changed, budget)


# Reuse the already-qualified native SDK/rate/Office IO component fixtures.
from test_office_compatibility import component, native


def test_admin_uses_existing_actual_native_service_finance_owner(component, monkeypatch):
    import test_office_compatibility as T
    import prove_office_readback as R
    from types import SimpleNamespace
    from mock_provider import ADMIN_USER_REQUEST
    before, after, terms = T.service_financial_fixture(component, monkeypatch)
    # The shared finance fixture omits the native /key/info token field, which
    # the whole-turn wire owner also binds to the observed authenticated key.
    before['key']['token'] = after['key']['token'] = terms['key_hash']
    call = copy.deepcopy(terms['dispatch'])
    wire = {'model': 'gpt-6-luna', 'input': [{'type': 'message', 'role': 'user', 'content': [
        {'type': 'input_text', 'text': ADMIN_USER_REQUEST}]}]}
    followups = ['Synthetic follow-up']
    call.update(wire_before_auth=wire, wire_after_auth=copy.deepcopy(wire))
    call['provider'].update(route='/v1/responses', usage=T.P.USAGE, lifecycle={'terminal': True, 'outcome': 'completed'},
        response={'id': terms['provider_id'], 'model': 'goal584-fake-office-service', 'status': 'completed', 'usage': T.P.USAGE,
            'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps({'follow_ups': followups})}]}]})
    d = {'validate_persisted_service_scope': terms['validate_scope'], 'validate_snapshot': terms['validate_rates'],
         'ResponsesAPIRequestUtils': SimpleNamespace(_decode_responses_api_response_id=terms['decode_response_id'])}
    kwargs = dict(actor=terms['actor'], payer=terms['payer'], chat=terms['chat_id'], descriptor=terms['descriptor'], d=d,
                  expected_user_request=ADMIN_USER_REQUEST)
    assert R.verify_service_turn(call, before, after, {'followUps': followups}, **kwargs)['physical_calls'] == 1
    changed = copy.deepcopy(after); changed['rows'][-1]['spend'] = .4
    import pytest
    with pytest.raises(C.P.ProofError): R.verify_service_turn(call, before, changed, {'followUps': followups}, **kwargs)
    changed = copy.deepcopy(call); changed['verified_cost_scope']['actor_id'] = str(uuid4())
    with pytest.raises(C.P.ProofError): R.verify_service_turn(changed, before, after, {'followUps': followups}, **kwargs)


if __name__=='__main__':unittest.main()
