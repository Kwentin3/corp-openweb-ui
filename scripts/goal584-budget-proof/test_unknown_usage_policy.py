"""Real client/provenance/readback owners over memory HTTP leaves; no native claim."""
import asyncio
import copy
from contextlib import redirect_stdout
from hashlib import sha256
import importlib.util
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import stat
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

HERE=Path(__file__).resolve().parent;BUDGETS=HERE.parents[1]/'deploy/openwebui-budgets'
sys.path[:0]=[str(HERE),str(BUDGETS)]
for name,file in (('employee_budget_assignment','assignment.py'),('employee_budget_admin_contract','admin_contract.py'),
                  ('employee_budget_admin_client','admin_client.py'),('employee_budget_provenance','provenance.py'),
                  ('employee_budget_cost_readback','cost_readback.py')):
    if name not in sys.modules:
        spec=importlib.util.spec_from_file_location(name,BUDGETS/file);module=importlib.util.module_from_spec(spec)
        sys.modules[name]=module;spec.loader.exec_module(module)
import prove_unknown_usage_policy as P
import prove_native_budgets as native_owner
import prove_gateway_auth as private_owner
import prove_service_tasks as provider_owner


class Response(BytesIO):
    headers={}
    def __init__(self,status,value):super().__init__(json.dumps(value).encode());self.code=self.status=status;self.content=self
    async def __aenter__(self):return self
    async def __aexit__(self,*args):self.close()
    async def iter_chunked(self,size):yield self.read()


class Wire:
    """Explicit native/provider HTTP result doubles, not a second budget implementation."""
    def __init__(self):
        self.operator='sk-'+'operator'*8;self.gateway='gw-'+'gateway'*8;self.viewer='sk-'+'viewer'*8
        self.viewer_id=str(uuid4());self.users={};self.keys={};self.rows=[];self.physical=[];self.attempts=[];self.requests=[]
        self.models=[{'model_name':a,'litellm_params':{'model':'openai/'+w,'api_base':'http://provider:8000/v1'},
            'model_info':{'id':a+'-v1','mode':'responses','input_cost_per_token':.01,'output_cost_per_token':.02,
                'cache_read_input_token_cost':.001,'output_cost_per_reasoning_token':.03}} for a,w in zip(P.ALIASES,P.WIRES)]
        self.ignore_block=False;self.false_action=False;self.wrong_nonce=False;self.change_old=False
        self.extra_dispatch=False;self.unknown_positive=False;self.optout=False;self.foreign_viewer=False;self.viewer_codes=[]

    def handle(self,method,url,headers,body=None,params=None):
        parsed=urlsplit(url);path=parsed.path;query=params or {k:v[0] for k,v in parse_qs(parsed.query).items()}
        headers={k.lower():v for k,v in headers.items()};self.requests.append((method,path,copy.deepcopy(body)))
        if parsed.hostname=='provider':
            assert method=='GET' and path=='/__proof/requests'
            return 200,{'synthetic':True,'control':{'tool_round':False},'requests':copy.deepcopy(self.physical)}
        if path==P.SESSION_ROUTE:
            assert method=='GET' and headers['authorization']=='Bearer '+self.viewer
            rows=[copy.deepcopy(r) for r in self.rows if r.get('session_id')==query['session_id']]
            if self.foreign_viewer and rows:rows[0]['user']=str(uuid4())
            return 200,{'data':rows,'total':len(rows),'total_pages':int(bool(rows)),'page':int(query['page']),'page_size':100}
        if path!='/v1/responses':assert headers['authorization']=='Bearer '+self.operator
        if path=='/model/info':return 200,{'data':copy.deepcopy(self.models)}
        if path=='/user/info':
            uid=query['user_id']
            if uid==self.viewer_id:return 200,{'user_info':{'user_id':uid,'user_role':'proxy_admin_viewer'},'keys':[]}
            if uid not in self.users:return 404,{'error':'not found'}
            return 200,{'user_info':copy.deepcopy(self.users[uid]),'teams':[],
                'keys':[copy.deepcopy(k) for k in self.keys.values() if k['user_id']==uid]}
        if path=='/key/list':
            rows=[copy.deepcopy(k) for k in self.keys.values() if k['user_id']==query['user_id']]
            return 200,{'keys':rows,'current_page':1,'total_count':len(rows),'total_pages':int(bool(rows))}
        if path=='/user/new':
            assert method=='POST' and body['user_id'] not in self.users
            self.users[body['user_id']]=copy.deepcopy(body)|{'team_id':None,'budget_reset_at':'2099-01-01T00:00:00Z'}
            return 200,{'user_id':body['user_id']}
        if path=='/key/generate':
            key=copy.deepcopy(body);token=key.pop('key');key.update(token=sha256(token.encode()).hexdigest(),expires=None,
                budget_reset_at='2099-01-01T00:00:00Z');self.keys[key['token']]=key
            if self.optout:key['metadata']['disable_global_guardrails']=True
            return 200,{'key':token}
        if path=='/key/info':
            if query['key']==sha256(self.viewer.encode()).hexdigest():
                return 200,{'key':query['key'],'info':{'user_id':self.viewer_id,'allowed_routes':[P.SESSION_ROUTE]}}
            key=copy.deepcopy(self.keys[query['key']]);key.pop('token');return 200,{'key':query['key'],'info':key}
        if path=='/spend/logs/v2':return 200,{'data':[copy.deepcopy(r) for r in self.rows if r['user']==query['user_id']],'total_pages':1}
        assert method=='POST' and path=='/v1/responses'
        assert headers['authorization']=='Bearer '+self.gateway and headers[P.TASK_HEADER.lower()]==''
        uid=headers[P.USER_ID_HEADER.lower()];alias=body['model'];key=next(k for k in self.keys.values() if k['user_id']==uid and k['models']==[alias])
        claims=P.decode_call(body['litellm_metadata'][P.PROVENANCE_FIELD],self.gateway,user_id=uid,model=alias)
        assert {k:v for k,v in body.items() if k!='litellm_metadata'}=={'model':alias,'input':'Hi','max_output_tokens':16,'store':False,'stream':False}
        self.attempts.append((uid,alias,claims['jti']))
        if key['blocked']:
            if self.extra_dispatch:self.physical.append({'id':'forbidden'})
            return 401,{'error':{'type':'auth_error','message':P.BLOCK_MESSAGE}}
        index=P.ALIASES.index(alias);pid='resp_goal584_'+uuid4().hex
        output={'id':pid,'model':P.WIRES[index],'object':'response','status':'completed','error':None,
            'output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':'Proof'}]}]}
        if index!=1:output['usage']=copy.deepcopy(P.RAW_USAGE) if index==0 else None
        record={'id':pid,'id_kind':'provider_response','route':'/v1/responses','body':{k:v for k,v in body.items() if k!='litellm_metadata'}|{'model':P.WIRES[index]},
            'usage':copy.deepcopy(P.RAW_USAGE) if index==0 else None,'response':copy.deepcopy(output),
            'lifecycle':{'terminal':True,'outcome':'completed','response_status':200}}
        self.physical.append(record)
        scope={'schema':1,'user_id':uid,'model':alias,'category':'personal','call_id':claims['jti'],
            **{k:claims[k] for k in ('chat_id','answer_id','root_chat_id','root_answer_id')}}
        if self.wrong_nonce:scope['call_id']=str(uuid4())
        if self.change_old and self.rows:self.rows[0]['spend']=.7
        cost=.166 if index==0 else .1 if self.unknown_positive else 0
        self.rows.append({'request_id':'opaque-native-log-'+uuid4().hex,'user':uid,'api_key':key['token'],
            'session_id':claims['root_chat_id'],'model_group':alias,'model_id':alias+'-v1','status':'success','spend':cost,
            'prompt_tokens':10,'completion_tokens':5,'total_tokens':15,'metadata':{'spend_logs_metadata':{'owui_budget':scope},
            'guardrail_information':[{'guardrail_name':'owui_budget_usage','guardrail_action':'allow' if index==0 or self.false_action else 'block',
                'violation_categories':[] if index==0 else ['usage_unavailable']}]}})
        self.users[uid]['spend']+=cost;key['spend']+=cost
        if index and not self.ignore_block:key['blocked']=True
        # Advertised/native log/provider IDs deliberately differ. Only nonce
        # and the actual physical prefix bind the primitive's proof.
        response=copy.deepcopy(output);response['id']='resp_security_'+uuid4().hex
        if index:response['usage']=None
        return 200,response

    def open(self,request,timeout):
        return Response(*self.handle(request.get_method(),request.full_url,dict(request.header_items()),
            json.loads(request.data) if request.data else None))

    def session(self,*,trust_env):
        assert trust_env is False;wire=self
        class Session:
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            def request(self,method,url,*,params,json,headers,allow_redirects,timeout):
                assert allow_redirects is False;return Response(*wire.handle(method,url,headers,json,params))
            def get(self,url,*,params,headers,allow_redirects,timeout):
                assert allow_redirects is False;return Response(*wire.handle('GET',url,headers,params=params))
        return Session()


class UnknownUsageTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);private=Path(self.temp.name)/'private';private.mkdir(mode=0o700)
        # Model only the deployed readonly filename aliases, retaining exact
        # source bytes and the already imported real implementation objects.
        for name in ('employee_budget_assignment','employee_budget_admin_contract','employee_budget_admin_client',
                     'employee_budget_provenance','employee_budget_cost_readback'):
            owner=sys.modules[name];alias=Path(self.temp.name)/(name+'.py')
            alias.write_bytes(Path(owner.__file__).read_bytes())
            self.enterContext(patch.object(owner,'__file__',str(alias)))
        self.wire=Wire()
        if os.name=='nt':self.enterContext(patch.object(private_owner.stat,'S_IMODE',side_effect=lambda m:0o700 if stat.S_ISDIR(m) else 0o600))
        operator=private/'operator.private.json';webui=private/'webui.private.json'
        P.fixture.write_private(operator,{'schema':1,'operator_token':self.wire.operator})
        P.fixture.write_private(webui,{'schema':1,'cost_reader':{'key':self.wire.viewer,'user_id':self.wire.viewer_id}})
        self.state=private/'policy.private.json';self.receipt=private/'policy.safe.json'
        mounted={n:private/n for n in P.MOUNTED_SOURCES}
        for p in mounted.values():p.write_text('# source hash IO leaf\n')
        original=P.fixture.native_client
        def client():
            n=original();n.timeout=.02;return n
        for target,name,value in ((P,'STATE',self.state),(P,'RECEIPT',self.receipt),(P,'WEBUI_STATE',webui),(P,'MOUNTED_SOURCES',mounted),
                (P.fixture,'OPERATOR_STATE',operator),(P.fixture,'native_client',client),(P,'ClientSession',self.wire.session),
                (native_owner,'build_opener',lambda *a:self.wire),(provider_owner,'build_opener',lambda *a:self.wire)):
            self.enterContext(patch.object(target,name,value))
        self.enterContext(patch.dict(os.environ,{'OWUI_BUDGET_GATEWAY_SECRET':self.wire.gateway}))

    def run_proof(self):return asyncio.run(P.execute({'schema':1,'proof':P.PROOF,'passed':False}))

    def test_real_admin_provenance_readback_and_private_public_boundaries(self):
        result=self.run_proof();self.assertTrue(result['passed']);self.assertEqual(result['known_positive_total'],'.332')
        self.assertEqual(len(self.wire.users),2);self.assertEqual(len(self.wire.keys),6)
        self.assertEqual(len(self.wire.physical),5);self.assertEqual(len(self.wire.attempts),7)
        self.assertEqual(len({n for _,_,n in self.wire.attempts}),7)
        self.assertEqual(sum(k['blocked'] for k in self.wire.keys.values()),3)
        private=P.fixture.read_private(self.state);self.assertEqual(private['stage'],'complete')
        self.assertEqual(len(private['calls']),7);self.assertEqual(len(private['snapshots']),7)
        self.assertEqual(len(result['source_sha256']),13);self.assertEqual(set(result['mounted_source_sha256']),set(P.MOUNTED_SOURCES))
        P.no_credentials(result,[self.wire.operator,self.wire.gateway,self.wire.viewer])
        self.assertFalse(result['unknown_cost_finality']);self.assertFalse(result['explicit_zero_runtime_qualified'])
        self.assertFalse(result['browser_or_chat_ancestry_qualified'])
        writes=[p for m,p,_ in self.wire.requests if m=='POST']
        self.assertEqual(writes.count('/user/new'),2);self.assertEqual(writes.count('/key/generate'),6)
        self.assertEqual(writes.count('/v1/responses'),7)
        self.assertFalse(any(p in ('/key/block','/key/unblock','/key/update','/__proof/reset','/__proof/control') for p in writes))

    def test_external_route_stops_before_any_native_mutation(self):
        self.wire.models[1]['litellm_params']['api_base']='https://paid.invalid/v1'
        with self.assertRaisesRegex(P.ProofError,'unknown_non_synthetic'):self.run_proof()
        self.assertFalse(any(m=='POST' for m,_,_ in self.wire.requests))

    def lag_positive_counters(self, *, converge):
        original=self.wire.handle;observations=[]
        def handle(method,url,*args,**kwargs):
            status,value=original(method,url,*args,**kwargs);path=urlsplit(url).path
            if len(self.wire.attempts)==1 and path=='/user/info' and value.get('user_info',{}).get('spend')==.166:
                observations.append('user')
                if not converge or len(observations)==1:value['user_info']['spend']=0
            if len(self.wire.attempts)==1 and path=='/key/info' and value.get('info',{}).get('spend')==.166:
                if not converge or len(observations)<=2:value['info']['spend']=0
            return status,value
        self.enterContext(patch.object(self.wire,'handle',side_effect=handle))
        return observations

    def test_existing_row_waits_for_user_then_target_key_counter_without_redispatch(self):
        observations=self.lag_positive_counters(converge=True);original=P.fixture.native_client
        def client():
            native=original();native.timeout=.5;return native
        with patch.object(P.fixture,'native_client',side_effect=client):result=self.run_proof()
        self.assertTrue(result['passed']);self.assertGreaterEqual(len(observations),3)
        self.assertEqual(len(self.wire.attempts),7);self.assertEqual(len(self.wire.physical),5)

    def test_existing_row_with_unsettled_counters_times_out_without_redispatch(self):
        observations=self.lag_positive_counters(converge=False)
        with self.assertRaisesRegex(P.ProofError,'Native persistence polling deadline expired|Timed out waiting for native unknown Usage row'):
            self.run_proof()
        self.assertGreaterEqual(len(observations),2);self.assertEqual(len(self.wire.rows),1)
        self.assertEqual(len(self.wire.attempts),1);self.assertEqual(len(self.wire.physical),1)
        self.assertEqual(P.fixture.read_private(self.state)['stage'],'provider_observed')

    def test_admin_optout_is_rejected_before_inference(self):
        self.wire.optout=True
        with self.assertRaisesRegex(P.ProofError,'unknown_assignment_admin'):self.run_proof()
        self.assertEqual(self.wire.attempts,[])

    def test_marker_ack_without_committed_block_cannot_pass(self):
        self.wire.ignore_block=True
        with self.assertRaises(P.ProofError):self.run_proof()
        self.assertTrue(self.state.exists())

    def test_block_failed_or_missing_typed_marker_cannot_pass(self):
        self.wire.false_action=True
        with self.assertRaisesRegex(P.ProofError,'unknown_native_guardrail_telemetry'):self.run_proof()

    def test_false_signed_nonce_is_not_joined_by_an_encoded_response_id(self):
        self.wire.wrong_nonce=True
        with self.assertRaises(P.ProofError):self.run_proof()

    def test_old_history_mutation_rejects(self):
        self.wire.change_old=True
        with self.assertRaises(P.ProofError):self.run_proof()

    def test_denial_cannot_dispatch_an_extra_provider_call(self):
        self.wire.extra_dispatch=True
        with self.assertRaisesRegex(P.ProofError,'unknown_denial_dispatched'):self.run_proof()

    def test_foreign_cost_viewer_scope_is_not_a_confirmed_amount(self):
        self.wire.foreign_viewer=True
        with self.assertRaisesRegex(P.ProofError,'unknown_viewer_wrong_failure'):self.run_proof()

    def test_native_unknown_amount_is_not_accepted_as_final_known_money(self):
        self.wire.unknown_positive=True
        with self.assertRaisesRegex(P.ProofError,'unknown_unexpected_native_amount'):self.run_proof()

    def test_late_source_failure_never_publishes_passed_true(self):
        next(iter(P.MOUNTED_SOURCES.values())).unlink()
        stdout=StringIO()
        with redirect_stdout(stdout):status=P.main()
        packet=json.loads(stdout.getvalue());self.assertEqual(status,1);self.assertFalse(packet['passed'])
        self.assertTrue(self.state.exists());self.assertFalse(P.fixture.read_private(self.receipt)['passed'])

    def test_fixed_own_failure_code_is_retained_without_raw_error_text(self):
        with patch.object(P,'execute',side_effect=P.ProofError('unknown_provider_context')),redirect_stdout(StringIO()) as output:
            self.assertEqual(P.main(),1)
        self.assertEqual(json.loads(output.getvalue())['failure'],'unknown_provider_context')

    def test_late_real_secret_check_does_not_publish_passed_true(self):
        original=P.digest
        def digest(value):
            return self.wire.operator if isinstance(value,list) and value and 'alias' in value[0] else original(value)
        with patch.object(P,'digest',side_effect=digest),redirect_stdout(StringIO()) as output:
            self.assertEqual(P.main(),1)
        packet=json.loads(output.getvalue());self.assertFalse(packet['passed'])
        self.assertNotIn(self.wire.operator,output.getvalue());self.assertTrue(self.state.exists())

    def test_native_client_error_code_has_fixed_namespace(self):
        with patch.object(P,'execute',side_effect=P.BudgetAdminError('invalid_assignment')),redirect_stdout(StringIO()) as output:
            self.assertEqual(P.main(),1)
        self.assertEqual(json.loads(output.getvalue())['failure'],'unknown_native_invalid_assignment')

    def test_transport_failure_retains_attempt_scope_without_claiming_a_response(self):
        original=self.wire.handle
        def handle(method,url,*args,**kwargs):
            if urlsplit(url).path=='/v1/responses':raise OSError('private transport detail')
            return original(method,url,*args,**kwargs)
        with patch.object(self.wire,'handle',side_effect=handle),redirect_stdout(StringIO()) as output:
            self.assertEqual(P.main(),1)
        state=P.fixture.read_private(self.state)
        self.assertEqual(state['stage'],'dispatching');self.assertEqual(len(state['user_ids']),2)
        self.assertEqual(len(state['calls']),1);self.assertIsNone(state['calls'][0]['response'])
        self.assertTrue(state['calls'][0]['scope']['call_id'])
        self.assertNotIn('private transport detail',output.getvalue())


if __name__=='__main__':unittest.main()
