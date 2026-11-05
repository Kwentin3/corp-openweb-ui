"""Batch collector joins real public clients/provenance/cost reader over HTTP leaves."""
import copy
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sys
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
        self.run_phase('baseline')
        self.initial_requests=len(self.wire.requests)

    def tearDown(self):
        setup_tests.UnknownGuiSetupTests.tearDown(self)

    def run_phase(self,phase):
        return self.loop.run_until_complete(C.execute(phase))

    def build_packet(self):
        packet={'schema':1,'actor_id':self.wire.actor_id,'calls':[],
                'foreign_chat_status':404,'office_settings_before':{'unchanged':True},'office_settings_after':{'unchanged':True}}
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
                record['body']['input']=[{'type':'message','role':'user','content':[{'type':'input_text','text':'Hi'}]}]
                row=self.wire.rows[-1]
                if slot:
                    row.update(prompt_tokens=0,completion_tokens=0,total_tokens=0)
                ownkey=self.wire.keys[row['api_key']];ownkey['total_spend']=ownkey['spend']
            u={'id':user,'parentId':None,'role':'user','content':'Hi','childrenIds':[answer]}
            packet['calls'].append({'model':alias,'chat_id':chat,'submitted':{'model':alias,'stream':False,'id':answer,
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
        self.assertFalse(result['unknown_cost_finality']);self.assertFalse(result['production_accepted'])
        self.assertEqual(len(self.wire.physical),5)
        self.assertTrue(all(method=='GET' for method,_,_ in self.wire.requests[before:]))
        self.assertEqual(self.network_attempts,[])

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


if __name__=='__main__':unittest.main()
