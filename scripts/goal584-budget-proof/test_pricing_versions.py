"""Finite publication/row/context tests; native HTTP and Docker remain external doubles."""
import ast
import base64
import copy
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
from decimal import Decimal
from email.message import Message
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit
import re

import yaml
import prove_native_budgets as native_owner
import prove_gateway_auth as private_owner
import prove_pricing_versions as M

BASE=yaml.safe_load(Path(__file__).with_name('litellm_config.yaml').read_bytes())
PROJECT='goal584-pricing-'+'a'*12
USER='af4769c2-5cbe-4d85-a519-c8b22f035ae0'
DECLARED='2026-11-03T12:00:00Z'
CALLBACK=Path(__file__).resolve().parents[2]/'deploy/openwebui-budgets/pricing_snapshot.py'


def approved_blobs(test):
    # Candidate Git-index bytes must match these frozen reviewed LF hashes.
    # CI's checked-out index is the tested commit; local WIP must be staged.
    paths={'pricing_snapshot.py':('deploy/openwebui-budgets/pricing_snapshot.py','64f67133962c780cbf6ae743863a7250fa6a427217c6f4981eaf860a799bad81'),
        'prove_pricing_catalog.py':('scripts/goal584-budget-proof/prove_pricing_catalog.py','1fc705d7348374428fe40690ae5973f05fec8bb206d9622a07a520ab671ad519')}
    values={}
    for name,(path,expected) in paths.items():
        try:raw=subprocess.check_output(['git','-c','gc.auto=0','show',':'+path],cwd=Path(__file__).resolve().parents[2],
            env=os.environ|{'GIT_NO_LAZY_FETCH':'1'},stderr=subprocess.PIPE)
        except subprocess.CalledProcessError:test.skipTest('Candidate Git-index blobs unavailable; no fetch permitted')
        test.assertEqual(M.sha(raw),expected);test.assertNotIn(b'\r\n',raw);values[name]=raw
    return values


def load_approved_catalog(test,root):
    import importlib.util
    files=approved_blobs(test)
    for name,raw in files.items():(root/name).write_bytes(raw)
    spec=importlib.util.spec_from_file_location('approved_catalog_for_version_test',root/'prove_pricing_catalog.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def budget(spend=0):
    common={'user_id':USER,'models':['goal584-a'],'max_budget':20,'spend':spend,'budget_duration':'1mo','budget_reset_at':'2026-12-01T00:00:00'}
    return {'user':common|{'user_role':'internal_user','teams':[]},'key':common|{'team_id':None,'allowed_routes':['llm_api_routes'],'expires':None}}


def state(count=1):
    approved={}
    for v in ('v1','v2'):M.approve(approved,M.publication(BASE,v,PROJECT,DECLARED),BASE)
    calls=[{'request_id':'chatcmpl-goal584-'+str(i+1)*32,'deployment_id':'goal584-price-a-'+M.EXPECTED[i][0],
        'cost':M.EXPECTED[i][1],'chat_id':USER+'-chat','root_answer_id':'goal584-proof-answer-'+str(i)} for i in range(count)]
    return {'schema':1,'proof':M.PROOF,'project':PROJECT,'user_id':USER,'key':'sk-fixture-private-key-000000',
        'key_hash':M.sha(b'sk-fixture-private-key-000000'),'base_config':copy.deepcopy(BASE),'native_artifact':M.catalog.native_sdk.identity(),
        'started_at':'2026-11-03T11:00:00+00:00','approved':approved,'calls':calls,'baseline_budget':budget(),'rows':[]}


def row(s,call):
    info=next(m['model_info'] for m in s['approved'][call['deployment_id']]['config']['model_list'] if m['model_name']=='goal584-a')
    fields=M.rate_fields(CALLBACK);rates=dict.fromkeys(fields,0.0);rates.update({k:info[k] for k in fields[:2]})
    meta={'chat_id':call['chat_id'],'root_answer_id':call['root_answer_id'],'call_kind':'synthetic_chat',
        'owui_billed_token_rates':{'schema':1,'availability':'available','observed_at_utc':'2026-11-03T12:01:00Z','rates':rates},
        'owui_tariff_descriptor':{'schema':1,'availability':'available','descriptor':info['owui_pricing']}}
    return {'request_id':call['request_id'],'user':USER,'api_key':s['key_hash'],'model':'openai/goal584-fake-a',
        'model_group':'goal584-a','model_id':call['deployment_id'],'status':'success','spend':float(call['cost']),**M.USAGE,
        'metadata':json.dumps({'spend_logs_metadata':meta},sort_keys=True)}


def physical(calls):
    rows=[]
    for c in calls:
        response={'id':c['request_id'],'object':'chat.completion','created':1793707200,'model':'goal584-fake-a',
            'choices':[{'index':0,'message':{'role':'assistant','content':'Proof'},'finish_reason':'stop'}],'usage':M.USAGE}
        rows.append({'id':c['request_id'],'created':1793707200,'body':copy.deepcopy(M.PHYSICAL_BODY),'usage':M.USAGE,
            'response':response,'lifecycle':{'started':True,'stage':'completed','started_monotonic':10.0,'headers_sent':True,
                'chunks_sent':0,'usage_sent':True,'terminal':True,'outcome':'completed','response_status':200,
                'delay_ms':0,'after_first_chunk_delay_ms':0,'terminal_monotonic':10.1}})
    return {'synthetic':True,'requests':rows,'control':{'prompt_tokens':10,'completion_tokens':5,'delay_ms':0,
        'tool_round':False,'admin_mode':False,'title_mode':False}}


class Response(io.BytesIO):
    def __init__(self,payload):
        super().__init__(json.dumps(payload).encode());self.code=self.status=200;self.headers=Message()


class FinanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.patches=[patch.object(M,'STATE',self.root/'state.private.json'),patch.object(M,'CALLBACK',CALLBACK)]
        if os.name=='nt':
            self.patches.append(patch.object(private_owner,'private_parent',lambda p:p.parent.mkdir(exist_ok=True)))
            self.patches.append(patch.object(private_owner.stat,'S_IMODE',return_value=0o600))
        for p in self.patches:p.start();self.addCleanup(p.stop)

    def native(self,s,rows=None,budgets=None,provider=None):
        n=M.NativeProof('http://127.0.0.1:4000','sk-synthetic-master-not-exported',60,{})
        n.started_at=datetime.fromisoformat(s['started_at']);queries=[]
        rows=[row(s,c) for c in s['calls']] if rows is None else rows
        values=budget(float(M.EXPECTED[len(s['calls'])-1][2])) if budgets is None else budgets
        def request(method,path,**kwargs):
            queries.append((method,path,kwargs))
            if path=='/spend/logs/v2':return 200,{'data':copy.deepcopy(rows),'total_pages':1},{}
            if path=='/user/info':return 200,{'user_info':copy.deepcopy(values['user']),'keys':[]},{}
            if path=='/key/info':return 200,{'info':copy.deepcopy(values['key'])},{}
            raise AssertionError('Unplanned native API '+path)
        n.request=request
        observed=physical(s['calls']) if provider is None else provider
        n.opener=types.SimpleNamespace(open=lambda request,timeout:Response(copy.deepcopy(observed)))
        return n,queries

    def test_three_actual_row_shapes_all7_rates_full_scope_and_private_write_readback(self):
        s=state(3);s['rows']=[row(s,c) for c in s['calls'][:2]]
        n,queries=self.native(s)
        result=M.settle(n,s)
        self.assertEqual((result['raw_row_count'],result['physical_calls']), (3,3))
        self.assertEqual(Decimal(result['key_spend']),Decimal('.8'))
        self.assertEqual([r['model_id'] for r in result['rows']],['goal584-price-a-v1','goal584-price-a-v1','goal584-price-a-v2'])
        self.assertTrue(all(r['descriptor']['descriptor']['declared_effective_until_utc'] is None for r in result['rows']))
        self.assertEqual(len(json.loads(M.STATE.read_text())['rows']),3)
        q=next(k for m,p,k in queries if p=='/spend/logs/v2')['query']
        self.assertEqual(q['user_id'],USER);self.assertEqual(q['start_date'],'2026-11-03 11:00:00')
        self.assertNotIn(s['key'],M.encoded(result).decode())

    def test_every_raw_row_must_match_scope_descriptor_rate_and_usage_no_zero_filter(self):
        for mutation in ('foreign_user','descriptor','rate','zero','extra','usage_type','native_id'):
            s=state();rows=[row(s,s['calls'][0])]
            if mutation=='foreign_user':rows[0]['user']='foreign'
            elif mutation=='zero':rows[0]['spend']=0;rows[0]['status']='failure'
            elif mutation=='extra':rows.append(copy.deepcopy(rows[0]));rows[-1]['request_id']='unknown'
            elif mutation=='usage_type':rows[0]['prompt_tokens']=10.0
            elif mutation=='native_id':rows[0]['model_id']='goal584-price-a-v2'
            else:
                meta=json.loads(rows[0]['metadata'])['spend_logs_metadata']
                if mutation=='descriptor':meta.pop('owui_tariff_descriptor')
                else:meta['owui_billed_token_rates']['rates']['input_cost_per_token']=.99
                rows[0]['metadata']=json.dumps({'spend_logs_metadata':meta})
            n,_=self.native(s,rows)
            with self.subTest(mutation=mutation),self.assertRaises(M.ProofError):M.settle(n,s)
            self.assertIn('raw_spend_pages',json.loads(M.STATE.read_text()))

    def test_old_full_row_and_all_provider_fields_are_immutable(self):
        for mutation in ('oldrow','body','response','extra_provider_field','control'):
            s=state(2);rows=[row(s,c) for c in s['calls']];s['rows']=copy.deepcopy(rows[:1]);p=physical(s['calls'])
            if mutation=='oldrow':rows[0]['metadata']+=' '
            elif mutation=='body':p['requests'][0]['body']['messages'][0]['content']='changed'
            elif mutation=='response':p['requests'][0]['response']['choices'][0]['message']['content']='changed'
            elif mutation=='extra_provider_field':p['requests'][0]['arbitrary']='foreign'
            else:p['control']['tool_round']=True
            n,_=self.native(s,rows,provider=p)
            with self.subTest(mutation=mutation),self.assertRaises(M.ProofError):M.settle(n,s)

    def test_drain_waits_only_readonly_counter_deficit_and_rejects_surplus(self):
        s=state();n,queries=self.native(s,budgets=budget(0));original=n.request;reads=[0]
        def request(method,path,**kwargs):
            code,payload,headers=original(method,path,**kwargs)
            if path=='/key/info':reads[0]+=1
            if reads[0]>=1 and path in ('/user/info','/key/info'):
                for key in ('info','user_info'):
                    if key in payload:payload[key]['spend']=.2
            return code,payload,headers
        n.request=request
        with patch.object(native_owner.time,'sleep',lambda _:None):M.settle(n,s)
        self.assertTrue(all(method=='GET' for method,_,_ in queries));self.assertGreater(reads[0],1)
        s=state();n,_=self.native(s,budgets=budget(.4))
        with self.assertRaisesRegex(M.ProofError,'version_counter_surplus'):M.settle(n,s)

    def test_input_exactly_matches_existing_native_infer_preparation(self):
        n=M.NativeProof('http://127.0.0.1:4000','synthetic-master',60,{})
        n.keys[USER,'goal584-a']={'token':'synthetic-key'};captured=[]
        def stop(method,path,**kwargs):captured.append(kwargs['body']);raise RuntimeError('stop before transport')
        n.request=stop
        with self.assertRaises(RuntimeError):n.infer(USER,'goal584-a')
        body=captured[0]
        self.assertEqual({k:v for k,v in body.items() if k not in ('model','metadata','stream')},
            {k:v for k,v in M.PHYSICAL_BODY.items() if k!='model'})
        self.assertIs(body['stream'],False)
        self.assertEqual(set(body['metadata']['spend_logs_metadata']),{'chat_id','root_answer_id','call_kind'})

    def test_known_provider_post_headers_completion_is_drained_without_new_model_call(self):
        s=state();n,queries=self.native(s);complete=physical(s['calls']);pending=copy.deepcopy(complete)
        life=pending['requests'][0]['lifecycle'];life.update(terminal=False,stage='headers_sent',usage_sent=False,outcome=None);life.pop('terminal_monotonic')
        count=[0]
        def opened(request,timeout):
            count[0]+=1;return Response(pending if count[0]==1 else complete)
        n.opener=types.SimpleNamespace(open=opened)
        with patch.object(native_owner.time,'sleep',lambda _:None):result=M.settle(n,s)
        self.assertEqual(result['physical_calls'],1);self.assertEqual(count[0],2)
        self.assertTrue(all(method=='GET' for method,_,_ in queries))

    def test_foreign_private_project_schema_or_key_binding_fails_before_native_access(self):
        for mutation in ('project','schema','key'):
            s=state()
            if mutation=='schema':s['schema']=True
            if mutation=='key':s['key_hash']='0'*64
            M.persist(s)
            with self.subTest(mutation=mutation),patch.object(M,'source_binding',return_value={}), \
                    patch.dict(os.environ,{'PROOF_PRICING_PROJECT':PROJECT}),patch.object(M,'native') as access:
                with self.assertRaises(M.ProofError):M.worker('drain',project='foreign' if mutation=='project' else PROJECT)
            access.assert_not_called()

    def test_missing_frozen_callback_is_an_explicit_integration_blocker(self):
        with patch.object(M,'CALLBACK_SHA256',None),self.assertRaisesRegex(M.ProofError,'version_callback_freeze_required'):M.source_binding()

    def test_real_prepare_persists_verified_empty_baseline_then_first_approve(self):
        from test_pricing_catalog import native_blob, fixture as catalog_fixture, source as catalog_source, status as catalog_status
        approved=load_approved_catalog(self,self.root)
        package=self.root/'litellm';package.mkdir();(package/'__init__.py').write_text("raise AssertionError('must not import')")
        for name in approved.NATIVE:
            p=package/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(native_blob(self,name))
        config=self.root/'config.yaml';config.write_text(yaml.safe_dump(BASE),encoding='utf8');original_config=config.read_bytes()
        attest=self.root/'attestation.private.json';M.write_private(attest,{'schema':1})
        n=M.NativeProof('http://127.0.0.1:4000','sk-synthetic-master-not-exported',60,{})
        calls=[];created={};token='sk-native-created-private-key-000000'
        def request(method,path,**kwargs):
            calls.append((method,path,copy.deepcopy(kwargs)))
            if path=='/user/new':
                created['user_id']=kwargs['body']['user_id']
                return 200,{'user_id':created['user_id']},{}
            if path=='/key/generate':return 200,{'key':token},{}
            if path in ('/user/info','/key/info'):
                values=budget()
                for v in values.values():v['user_id']=created['user_id']
                return (200,{'user_info':values['user'],'keys':[]},{}) if path=='/user/info' else (200,{'info':values['key']},{})
            if path=='/spend/logs/v2':return 200,{'data':[],'total_pages':1},{}
            if path=='/model/info':return 200,{'data':copy.deepcopy(BASE['model_list'])},{}
            src=catalog_source('S2',31)
            if path==approved.SOURCE:return 200,src,{}
            if path==approved.STATUS:return 200,catalog_status(src,False,31),{}
            raise AssertionError('Unplanned native operation '+path)
        n.request=request
        def provider(request,timeout):
            if request.full_url.endswith('/observations'):return Response(catalog_fixture('S1',{'S1':1,'S2':1}))
            self.assertEqual(request.full_url,'http://provider:8000/__proof/requests')
            return Response(physical([]))
        n.opener=types.SimpleNamespace(open=provider)
        with patch.object(M,'catalog',approved),patch.object(M,'CALLBACK',self.root/'pricing_snapshot.py'), \
                patch.object(M,'ATTEST',attest),patch.object(M,'CONFIG',config),patch.object(M,'native',return_value=n), \
                patch.object(approved,'profile'),patch.object(approved.native_sdk,'inspect_sources',return_value={'native_artifact':approved.native_sdk.identity()}), \
                patch.object(M.importlib.util,'find_spec',return_value=types.SimpleNamespace(origin=str(package/'__init__.py'))), \
                patch.dict(os.environ,{'PROOF_PRICING_PROJECT':PROJECT,'HOSTNAME':'a'*12}):
            prepared=M.worker('prepare',project=PROJECT)
            stored=M.read_private(M.STATE)
            self.assertEqual(prepared['stage'],'prepared');self.assertEqual(stored['rows'],[]);self.assertEqual(stored['provider_rows'],[])
            self.assertEqual(stored['raw_spend_pages'][-1]['payload']['data'],[])
            self.assertTrue(any(x['path']=='/requests' and x['payload']['requests']==[] for x in stored['fixture_api']))
            before=len(calls);approved_result=M.worker('approve','v1',PROJECT)
            self.assertEqual(len(calls),before,'First approve performs no inference or native mutation')
            self.assertEqual(approved_result['stage'],'approved');self.assertTrue(approved_result['same_id_changed_terms_rejected'])
            after=M.read_private(M.STATE);self.assertEqual(set(after['approved']),{'goal584-price-a-v1'})
            self.assertEqual(after['rows'],[]);self.assertEqual(after['provider_rows'],[])
        self.assertEqual([path for method,path,_ in calls if method=='POST'],['/user/new','/key/generate'])
        self.assertNotIn('/v1/chat/completions',[path for _,path,_ in calls])
        self.assertEqual(config.read_bytes(),original_config)

    def test_static_bindings_validate_exact_approved_git_bytes_and_reject_mutation(self):
        approved=load_approved_catalog(self,self.root)
        with patch.object(M,'catalog',approved),patch.object(M,'CALLBACK',self.root/'pricing_snapshot.py'):
            result=M.source_binding()
            self.assertEqual(result['callback_sha256'],M.CALLBACK_SHA256)
            self.assertEqual(result['catalog_sha256'],M.CATALOG_SHA256)
            for name in ('pricing_snapshot.py','prove_pricing_catalog.py'):
                p=self.root/name;raw=p.read_bytes();p.write_bytes(raw+b'\n')
                with self.subTest(mutation=name),self.assertRaisesRegex(M.ProofError,'version_frozen_sources'):M.source_binding()
                p.write_bytes(raw)

    def test_actual_worker_three_calls_getters_drain_and_no_repeat_dispatch(self):
        from test_pricing_catalog import native_blob, fixture as catalog_fixture, source as catalog_source, status as catalog_status
        package=self.root/'litellm';package.mkdir();(package/'__init__.py').write_text("raise AssertionError('no import')")
        for name in M.catalog.NATIVE:
            p=package/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(native_blob(self,name))
        s=state(0);M.persist(s);config=self.root/'config.yaml';dispatched=[];current_variant=['S1']
        n=M.NativeProof('http://127.0.0.1:4000','sk-synthetic-master-not-exported',60,{})
        def request(method,path,**kwargs):
            stored=json.loads(M.STATE.read_text());calls=stored['calls']
            if path=='/model/info':return 200,{'data':yaml.safe_load(config.read_bytes())['model_list']},{}
            src=catalog_source(current_variant[0],31)
            if path==M.catalog.SOURCE:return 200,src,{}
            if path==M.catalog.STATUS:return 200,catalog_status(src,False,31),{}
            if path=='/v1/chat/completions':
                self.assertEqual(kwargs['token'],s['key']);dispatched.append(copy.deepcopy(kwargs['body']))
                identifier='chatcmpl-goal584-'+str(len(dispatched))*32
                return 200,{'id':identifier,'usage':M.USAGE}, {'x-litellm-response-cost':M.EXPECTED[len(dispatched)-1][1]}
            if path=='/spend/logs/v2':return 200,{'data':[row(stored,c) for c in calls],'total_pages':1},{}
            values=budget(0 if not calls else float(M.EXPECTED[len(calls)-1][2]))
            if path=='/user/info':return 200,{'user_info':values['user'],'keys':[]},{}
            if path=='/key/info':return 200,{'info':values['key']},{}
            raise AssertionError('Unplanned worker HTTP '+path)
        n.request=request
        def provider(request,timeout):
            stored=json.loads(M.STATE.read_text())
            self.assertEqual(request.full_url,'http://provider:8000/__proof/requests')
            return Response(physical(stored['calls']))
        n.opener=types.SimpleNamespace(open=provider)
        with patch.object(M,'native',return_value=n),patch.object(M,'CONFIG',config), \
                patch.object(M,'source_binding',return_value={'integration_hashes_pending':True}), \
                patch.dict(os.environ,{'PROOF_PRICING_PROJECT':PROJECT,'HOSTNAME':'a'*12}), \
                patch.object(M.importlib.util,'find_spec',return_value=types.SimpleNamespace(origin=str(package/'__init__.py'))), \
                patch.object(M.catalog.native_sdk,'inspect_sources',return_value={'native_artifact':s['native_artifact']}):
            for label in M.LABELS:
                version=M.EXPECTED[M.LABELS.index(label)][0]
                config.write_text(yaml.safe_dump(s['approved']['goal584-price-a-'+version]['config']),encoding='utf8')
                current_variant[0]=label.split('_')[1]
                result=M.worker('call',label,PROJECT)
                self.assertEqual(result['stage'],label)
            self.assertEqual(M.worker('drain',project=PROJECT)['financial']['raw_row_count'],3)
            with self.assertRaisesRegex(M.ProofError,'version_call_order_or_retry'):M.worker('call','v2_S2',PROJECT)
        self.assertEqual(len(dispatched),3)
        saved=json.loads(M.STATE.read_text());self.assertEqual(saved['attempted'],list(M.LABELS))
        self.assertEqual(saved['inputs'],dispatched)
        self.assertEqual(Decimal(str(saved['budgets']['user']['spend'])),Decimal('.8'))


class PublicationTests(unittest.TestCase):
    def test_finite_publication_preserves_all_original_config_and_rejects_reused_id(self):
        registry={};v1=M.publication(BASE,'v1',PROJECT,DECLARED);M.approve(registry,v1,BASE)
        modified=copy.deepcopy(v1);modified['model_list'][0]['model_info']['input_cost_per_token']=.02
        with self.assertRaisesRegex(M.ProofError,'version_id_reused_with_changed_terms'):M.approve(registry,modified,BASE)
        v2=M.publication(BASE,'v2',PROJECT,DECLARED);M.approve(registry,v2,BASE)
        for candidate in (v1,v2):
            restored=copy.deepcopy(candidate)
            restored['model_list'][0]['model_info']=copy.deepcopy(BASE['model_list'][0]['model_info'])
            self.assertEqual(restored,BASE)
        wrong=copy.deepcopy(v2);wrong['model_list'][1]['litellm_params']['api_base']='https://paid.invalid'
        with self.assertRaises(M.ProofError):M.approve({},wrong,BASE)

    def test_real_inplace_write_preserves_inode_and_restores_original_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'config.yaml';original=b'original synthetic config\n';p.write_bytes(original);p.chmod(0o600)
            inode=p.stat().st_ino;M.overwrite(p,b'changed\n');self.assertEqual(p.stat().st_ino,inode)
            M.overwrite(p,original);self.assertEqual(p.read_bytes(),original);self.assertEqual(p.stat().st_ino,inode)

    def test_actual_callback_descriptor_validator_accepts_finite_synthetic_declarations(self):
        tree=ast.parse(CALLBACK.read_bytes());nodes=[]
        for n in tree.body:
            if getattr(n,'name',None) in ('_utc','_descriptor'):nodes.append(n)
            elif isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('DESCRIPTOR_FIELDS','_REFERENCE','_CREDENTIAL','_UTC') for t in n.targets):nodes.append(n)
        ns={'re':re,'datetime':datetime,'urlsplit':urlsplit,'unquote':unquote}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'actual-callback-descriptor.py','exec'),ns)
        for version in ('v1','v2'):
            d=M.publication(BASE,version,PROJECT,DECLARED)['model_list'][0]['model_info']['owui_pricing']
            self.assertEqual(ns['_descriptor'](d),d)


class HostTests(unittest.TestCase):
    def replay_host(self,mutation=None):
        """Execute real Host methods; replace only Git/Docker/worker packet IO."""
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);checkout=root/'checkout';checkout.mkdir();private=root/'private';private.mkdir()
            config=private/'config.yaml';original=yaml.safe_dump(BASE).encode();config.write_bytes(original)
            envfile=private/'proof.env';envfile.write_text('SYNTHETIC=1',encoding='utf8')
            revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=M.ROOT).decode().strip()
            approved=load_approved_catalog(self,root)
            for name,path in M.SOURCE_PATHS.items():
                raw=subprocess.check_output(['git','-c','gc.auto=0','show',':'+path],cwd=M.ROOT,
                    env=os.environ|{'GIT_NO_LAZY_FETCH':'1'})
                target=checkout/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
            # Model Docker's public resolved config using the actual base Compose
            # mounts plus the two proof workers supplied by the final overlay.
            volumes={}
            for relative in ('compose/goal584.native-budget-proof.yml','compose/goal584.pricing-proof.yml'):
                document=yaml.safe_load((M.ROOT/relative).read_bytes())
                for value in document['services']['proxy']['volumes']:
                    value=copy.deepcopy(value);source=value['source']
                    if source.startswith('${PROOF_CONFIG_FILE:'):value['source']=str(config.resolve())
                    elif source.startswith('${PROOF_PRIVATE_DIR:'):value['source']=str(private.resolve())
                    else:value['source']=str((checkout/'compose'/source).resolve())
                    volumes[value['target']]=value
            for name,path in M.SOURCE_PATHS.items():
                volumes.setdefault('/proof/'+name,{'type':'bind','source':str((checkout/path).resolve()),
                    'target':'/proof/'+name,'read_only':True})
            self.assertIn('/proof/litellm_auth.py',volumes)
            resolved={'services':{'proxy':{'volumes':list(volumes.values()),
                'environment':{'PROOF_MASTER_KEY':'sk-synthetic-master-not-exported'}}}}
            mounts=[{'Type':'bind','Source':m['source'],'Destination':m['target'],'RW':not m.get('read_only',False)}
                for m in volumes.values()]
            image='sha256:'+'c'*64
            args=types.SimpleNamespace(project=PROJECT,private_root=private,env_file=envfile,
                compose_file=['compose/goal584.native-budget-proof.yml','compose/goal584.pricing-proof.yml'])
            host=M.Host(args);commands=[];actions=[];world={'restarted':False,'calls':0}
            initial={'proxy':'1'*64,'postgres':'2'*64,'redis':'3'*64,'provider':'4'*64}
            def ids():
                values=dict(initial)
                if mutation=='nonproxy_changed_after_restart' and world['restarted']:values['provider']='5'*64
                return values
            def output(argv,**kwargs):
                commands.append(list(argv))
                if argv[:3]==['git','rev-parse','HEAD']:return revision.encode()
                if argv[0]=='git' and 'show' in argv:return (checkout/argv[-1].split(':',1)[1]).read_bytes()
                self.assertEqual(argv[-2:],['ps','-q']);return '\n'.join(ids().values()).encode()
            def packet(action,label):
                actions.append((action,label));result={}
                if action=='approve':
                    value=M.publication(BASE,label,PROJECT,DECLARED)
                    result={'declaration':value['model_list'][0]['model_info']['owui_pricing'],
                        'config_semantic_sha256':M.sha(M.encoded(value))}
                elif action=='identity':
                    info=yaml.safe_load(config.read_bytes())['model_list'][0]['model_info']
                    result={'identity':{'config_sha256':M.sha(original) if mutation=='old_config_identity' and label!='base' else M.sha(config.read_bytes()),
                        'worker_id_prefix':'1'*12,'model_A':info,'native_artifact':approved.native_sdk.identity()}}
                elif action=='call':
                    world['calls']+=1;result={'stage':label,'financial':{'physical_calls':world['calls'],'raw_row_count':world['calls']}}
                elif action=='drain':result={'stage':'drained','financial':{'physical_calls':world['calls'],'raw_row_count':world['calls']}}
                else:self.assertIn(action,('prepare','reload','restore_catalog'))
                return {'schema':1,'proof':M.PROOF,'passed':True,'action':action,'result':result,'failure_code':None}
            def run(argv,**kwargs):
                commands.append(list(argv))
                if argv[-3:]==['config','--format','json']:
                    value=copy.deepcopy(resolved)
                    if mutation=='compose_declares_extra_RW_bind':
                        value['services']['proxy']['volumes'].append({'type':'bind','source':str(root),'target':'/extra','read_only':False})
                    elif mutation=='compose_duplicate_destination':value['services']['proxy']['volumes'].append(copy.deepcopy(next(iter(volumes.values()))))
                elif argv[:2]==['docker','inspect']:
                    service=next(s for s,i in ids().items() if i==argv[-1]);identifier=ids()[service]
                    actual=copy.deepcopy(mounts) if service=='proxy' else []
                    if service=='proxy':
                        if mutation in ('extra_RW_bind','compose_declares_extra_RW_bind'):actual.append({'Type':'bind','Source':str(root),'Destination':'/extra','RW':True})
                        if mutation=='required_RW_bind':actual[0]['RW']=True
                        if mutation=='duplicate_bind_masks_RW':actual.insert(0,dict(actual[0],RW=True))
                        if mutation=='wrong_bind_source':actual[0]['Source']=str(root/'foreign')
                        if mutation=='missing_base_proof_bind':actual=[m for m in actual if m['Destination']!='/proof/litellm_auth.py']
                        if mutation=='private_read_only':next(m for m in actual if m['Destination']=='/proof-private')['RW']=False
                    if mutation=='inspected_duplicate_ID' and service=='provider':identifier=ids()['proxy']
                    if mutation=='inspected_foreign_ID' and service=='provider':identifier='6'*64
                    if mutation=='inspected_swapped_ID':
                        if service=='provider':identifier=ids()['redis']
                        elif service=='redis':identifier=ids()['provider']
                    value={'id':identifier,'service':service,'project':'foreign' if mutation=='foreign_project' else PROJECT,
                        'number':'1','network':PROJECT+'_proof','health':'healthy',
                        'image_ref':image if service=='proxy' else approved.IMAGES[service],
                        'image_id':('sha256:'+'d'*64 if mutation=='unbound_proxy_image_ID' else image) if service=='proxy' else 'sha256:'+ids()[service],
                        'mounts':actual,'command':approved.COMMAND if service=='proxy' else []}
                elif argv[-2:]==['restart','proxy'] or 'up' in argv:
                    if 'up' in argv:world['restarted']=True
                    return types.SimpleNamespace(returncode=0,stdout=b'',stderr=b'')
                elif '--worker-action' in argv:
                    action=argv[argv.index('--worker-action')+1];label=argv[argv.index('--label')+1] if '--label' in argv else None
                    value=packet(action,label)
                else:
                    self.assertIn('-c',argv);paths=argv[argv.index('-c')+2:]
                    value={p:M.sha((checkout/M.SOURCE_PATHS[p.removeprefix('/proof/')]).read_bytes()) for p in paths}
                return types.SimpleNamespace(returncode=0,stdout=json.dumps(value).encode(),stderr=b'')
            patches=[patch.object(M,'ROOT',checkout),patch.object(M,'catalog',approved),
                patch.dict(os.environ,{'PROOF_SOURCE_COMMIT':revision,'PROOF_NATIVE_VARIANT':approved.native_sdk.VARIANT,'PROOF_LITELLM_IMAGE':image}),
                patch.object(M.subprocess,'check_output',output),patch.object(M.subprocess,'run',run)]
            if os.name=='nt':patches += [patch.object(private_owner,'private_parent',lambda p:p.parent.mkdir(exist_ok=True)),
                patch.object(private_owner.stat,'S_IMODE',return_value=0o600)]
            for p in patches:p.start()
            error=None;receipt=None
            try:
                try:receipt=host.execute()
                except M.ProofError as e:error=str(e)
            finally:
                for p in reversed(patches):p.stop()
            self.assertEqual(config.read_bytes(),original)
            self.assertTrue(host.receipt['restoration']['original_bytes_equal'])
            return receipt,error,world,commands,actions

    def test_actual_host_execute_topology_restart_accepts_complete_compose_bind_set(self):
        receipt,error,world,commands,actions=self.replay_host()
        self.assertIsNone(error);self.assertTrue(receipt['passed']);self.assertEqual(world['calls'],3)
        self.assertEqual([label for action,label in actions if action=='call'],list(M.LABELS))
        self.assertEqual(sum(c[-2:]==['restart','proxy'] for c in commands),3)
        self.assertEqual(sum(c[-3:]==['config','--format','json'] for c in commands),4)
        self.assertEqual(receipt['restoration']['failures'],[])
        self.assertIn(('identity','base'),actions);self.assertEqual(actions[-1],('restore_catalog',None))

    def test_actual_host_execute_rejects_original_eight_topology_mutations(self):
        cases={'inspected_duplicate_ID':'version_host_inspect_ids','extra_RW_bind':'version_host_compose_bindings',
            'required_RW_bind':'version_host_compose_bindings','duplicate_bind_masks_RW':'version_host_duplicate_mount_destination',
            'foreign_project':'version_host_container_binding','unbound_proxy_image_ID':'version_host_native_image_id',
            'old_config_identity':'version_actual_publication_identity','nonproxy_changed_after_restart':'version_nonproxy_container_changed'}
        for mutation,expected in cases.items():
            with self.subTest(mutation=mutation):
                receipt,error,world,commands,actions=self.replay_host(mutation)
                self.assertIsNone(receipt);self.assertEqual(error,expected);self.assertEqual(world['calls'],0)
                if mutation not in ('old_config_identity','nonproxy_changed_after_restart'):
                    self.assertEqual(actions,[]);self.assertFalse(any(c[-2:]==['restart','proxy'] for c in commands))

    def test_actual_host_execute_rejects_mismatched_ids_and_compose_bind_variants(self):
        cases={'inspected_foreign_ID':'version_host_inspect_ids','inspected_swapped_ID':'version_host_inspect_ids',
            'wrong_bind_source':'version_host_compose_bindings','missing_base_proof_bind':'version_host_compose_bindings',
            'private_read_only':'version_host_compose_bindings','compose_declares_extra_RW_bind':'version_host_compose_bindings',
            'compose_duplicate_destination':'version_host_duplicate_mount_destination'}
        for mutation,expected in cases.items():
            with self.subTest(mutation=mutation):
                receipt,error,world,commands,actions=self.replay_host(mutation)
                self.assertIsNone(receipt);self.assertEqual(error,expected);self.assertEqual(world['calls'],0)
                self.assertEqual(actions,[]);self.assertFalse(any(c[-2:]==['restart','proxy'] for c in commands))

    def main_result(self,primary=None,writer_error=None):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);private=root/'private';private.mkdir();output=root/'output';output.mkdir()
            env=private/'proof.env';env.write_text('SYNTHETIC=1',encoding='utf8');env.chmod(0o600)
            config=private/'config.yaml';config.write_text('synthetic',encoding='utf8');config.chmod(0o600)
            target=output/'safe.json'
            class ExternalHost:
                def __init__(self,args):self.receipt={'stage':'publish_v1','passed':False}
                def execute(self):
                    if primary is not None:raise primary
                    self.receipt.update(stage='qualified',passed=True)
                    return self.receipt
            writes=[];original_write=Path.write_bytes
            def write(path,raw):
                if path==target:
                    writes.append(raw)
                    if writer_error is not None:raise writer_error
                return original_write(path,raw)
            argv=['probe','--project',PROJECT,'--env-file',str(env),'--private-root',str(private),
                '--compose-file','compose/goal584.native-budget-proof.yml','--receipt',str(target)]
            stdout,stderr=io.StringIO(),io.StringIO()
            with patch.object(sys,'argv',argv),patch.object(M,'Host',ExternalHost),patch.object(Path,'write_bytes',write), \
                    redirect_stdout(stdout),redirect_stderr(stderr):code=M.main()
            self.assertEqual(stderr.getvalue(),'');self.assertNotIn('Traceback',stdout.getvalue())
            self.assertNotIn('sk-private',stdout.getvalue());self.assertNotIn('private filesystem',stdout.getvalue())
            value=json.loads(stdout.getvalue())
            self.assertEqual(set(value),{'schema','proof','passed','action','result','failure_code'})
            return code,value,target.read_bytes() if target.exists() else None,writes

    def test_actual_unknown_descriptor_is_a_contract_failure_without_null_dereference(self):
        s=state();call=s['calls'][0]
        for value in ({'schema':1,'availability':'unknown','descriptor':None},None):
            with self.subTest(descriptor=value):
                native_row=row(s,call);meta=json.loads(native_row['metadata'])
                meta['spend_logs_metadata']['owui_tariff_descriptor']=value
                native_row['metadata']=json.dumps(meta)
                with patch.object(M,'CALLBACK',CALLBACK),self.assertRaisesRegex(M.ProofError,'^version_row_descriptor$'):
                    M.verified_row(native_row,s,call)

    def test_unknown_descriptor_exports_only_callback_owned_fixed_reason(self):
        s=state();call=s['calls'][0]
        for reason,code in (('selected_model_info','version_descriptor_selected_model_info'),
                ('sk-private-secret-000000','version_row_descriptor'),('arbitrary_private_text','version_row_descriptor')):
            with self.subTest(reason=reason):
                native_row=row(s,call);meta=json.loads(native_row['metadata'])
                meta['spend_logs_metadata']['owui_tariff_descriptor']={
                    'schema':1,'availability':'unknown','descriptor':None,'reason':reason}
                native_row['metadata']=json.dumps(meta)
                with patch.object(M,'CALLBACK',CALLBACK),self.assertRaises(M.ProofError) as caught:
                    M.verified_row(native_row,s,call)
                self.assertEqual(str(caught.exception),code)
                self.assertNotIn('private',str(caught.exception))

    def test_actual_worker_cli_failure_retains_source_location_without_private_exception(self):
        for error in (KeyError('sk-private-secret-000000'),M.ProofError('Expected JSON at /private/sk-private-secret-000000')):
            stdout,stderr=io.StringIO(),io.StringIO()
            with self.subTest(kind=type(error).__name__),patch.object(sys,'argv',
                    ['probe','--worker-action','call','--project',PROJECT]), \
                    patch.object(M,'worker',side_effect=error),redirect_stdout(stdout),redirect_stderr(stderr):
                code=M.main()
                value=json.loads(stdout.getvalue())
                self.assertEqual(code,1);self.assertFalse(value['passed'])
                self.assertEqual(value['failure_code'],'version_external_failure')
                self.assertEqual(set(value),{'schema','proof','passed','action','result','failure_code'})
                self.assertEqual(value['result']['stage'],'call')
                location=value['result']['failure_location']
                self.assertEqual(location['exception_type'],type(error).__name__)
                self.assertTrue(location['frames'])
                self.assertTrue(all(set(f)=={'source','line'} and f['source'] in M.SOURCE_PATHS
                    and type(f['line']) is int and f['line']>0 for f in location['frames']))
                self.assertEqual(stderr.getvalue(),'')
                for private in ('sk-private','Expected JSON','/private/','Traceback'):
                    self.assertNotIn(private,stdout.getvalue())

    def test_failure_location_does_not_export_arbitrary_exception_type_or_file_path(self):
        external=type('sk-private-secret-000000',(Exception,),{})
        self.assertEqual(M.failure_location(external('/private/sk-private-secret-000000')),
            {'exception_type':'ExternalError','frames':[]})

    def test_actual_main_final_writer_failure_preserves_primary_and_closed_safe_packet(self):
        for error in (OSError('private filesystem sk-private-secret-000000'),M.ProofError('private filesystem sk-private-secret-000000')):
            with self.subTest(writer=type(error).__name__):
                code,value,raw,writes=self.main_result(M.ProofError('version_primary_failure'),error)
                self.assertEqual(code,1);self.assertIs(value['passed'],False)
                self.assertEqual(value['failure_code'],'version_primary_failure')
                self.assertEqual(value['result'],{'stage':'publish_v1','receipt_write_failure':'version_receipt_write_failed'})
                self.assertIsNone(raw);self.assertEqual(len(writes),1)

    def test_actual_main_success_requires_final_receipt_write_success(self):
        code,value,raw,writes=self.main_result()
        self.assertEqual(code,0);self.assertTrue(value['passed']);self.assertEqual(json.loads(raw),value)
        code,value,raw,writes=self.main_result(writer_error=OSError('private filesystem sk-private-secret-000000'))
        self.assertEqual(code,1);self.assertFalse(value['passed']);self.assertEqual(value['failure_code'],'version_receipt_write_failed')
        self.assertEqual(value['result'],{'stage':'qualified','receipt_write_failure':'version_receipt_write_failed'})
        self.assertIsNone(raw);self.assertEqual(len(writes),1)

    def test_worker_protocol_rejects_extra_fields_and_boolean_schema(self):
        args=types.SimpleNamespace(project=PROJECT,private_root=Path('/proof-private'),env_file=Path('private.env'),compose_file=[])
        host=M.Host(args)
        base={'schema':1,'proof':M.PROOF,'passed':True,'action':'prepare','result':{},'failure_code':None}
        for mutation in ('extra','bool'):
            value=copy.deepcopy(base)
            if mutation=='extra':value['arbitrary_private_header']='secret'
            else:value['schema']=True
            result=types.SimpleNamespace(returncode=0,stdout=json.dumps(value).encode(),stderr=b'')
            with self.subTest(mutation=mutation),patch.object(M.subprocess,'run',return_value=result),self.assertRaisesRegex(M.ProofError,'version_worker_protocol'):host.invoke('prepare')

    def test_same_id_guard_precedes_any_host_write_or_restart(self):
        with tempfile.TemporaryDirectory() as d:
            private=Path(d);p=private/'config.yaml';raw=yaml.safe_dump(BASE).encode();p.write_bytes(raw)
            args=types.SimpleNamespace(project=PROJECT,private_root=private,env_file=private/'env',compose_file=[])
            host=M.Host(args)
            host.topology=lambda:{'id':'a'*64,'image_id':'sha256:'+'b'*64}
            def invoke(action,label=None):
                if action=='prepare':return {}
                if action=='approve':raise M.ProofError('version_id_reused_with_changed_terms')
                raise AssertionError('No later worker action allowed')
            host.invoke=invoke
            with patch.object(M,'write_private'),patch.object(M,'overwrite') as write,patch.object(host,'restart') as restart:
                with self.assertRaisesRegex(M.ProofError,'version_id_reused_with_changed_terms'):host.execute()
            write.assert_not_called();restart.assert_not_called();self.assertEqual(p.read_bytes(),raw)

    def test_primary_failure_survives_restore_write_restart_and_controller_failure(self):
        with tempfile.TemporaryDirectory() as d:
            private=Path(d);p=private/'config.yaml';p.write_text(yaml.safe_dump(BASE),encoding='utf8')
            args=types.SimpleNamespace(project=PROJECT,private_root=private,env_file=private/'env',compose_file=[])
            host=M.Host(args);host.topology=lambda:{'id':'a'*64,'image_id':'sha256:'+'b'*64}
            value=M.publication(BASE,'v1',PROJECT,DECLARED)
            def invoke(action,label=None):
                if action=='prepare':return {}
                if action=='approve':return {'declaration':value['model_list'][0]['model_info']['owui_pricing'],'config_semantic_sha256':M.sha(M.encoded(value))}
                raise M.ProofError('version_controller_unavailable')
            host.invoke=invoke
            with patch.object(M,'write_private'),patch.object(host,'restart',side_effect=M.ProofError('version_primary_restart_failure')):
                with self.assertRaisesRegex(M.ProofError,'version_primary_restart_failure'):host.execute()
            self.assertIn('config_or_restart_restore_failed',host.receipt['restoration']['failures'])
            self.assertIn('catalog_restore_failed',host.receipt['restoration']['failures'])
            self.assertEqual(host.receipt['stage'],'publish_v1')
            self.assertTrue(host.receipt['restoration']['original_bytes_equal'])


class NativeGetterTests(unittest.TestCase):
    def test_actual_native_model_info_getter_preserves_explicit_terms_over_reference_prices(self):
        cache=Path(os.environ.get('GOAL584_LITELLM_SOURCE',Path(__file__).resolve().parents[2]/'local/goal584/litellm/upstream'))
        if not cache.is_dir():self.skipTest('Read-only pinned native cache unavailable; set GOAL584_LITELLM_SOURCE')
        try:raw=subprocess.check_output(['git','-c','gc.auto=0','show',M.catalog.native_sdk.BASE_REVISION+':litellm/proxy/proxy_server.py'],cwd=cache,env=os.environ|{'GIT_NO_LAZY_FETCH':'1'},stderr=subprocess.PIPE)
        except subprocess.CalledProcessError:self.skipTest('Exact cached native Git blob unavailable')
        self.assertEqual(M.sha(raw),'227a704e5c9e7bdd0569f80d520aa670bde32397d0983e165089c63dcb775b4e')
        node=next(n for n in ast.parse(raw).body if getattr(n,'name',None)=='_enrich_model_info_with_litellm_data')
        node.returns=None
        for a in node.args.args:a.annotation=None
        from types import MappingProxyType
        ns={'MappingProxyType':MappingProxyType,'Final':object,'get_litellm_model_info':lambda **k:{'input_cost_per_token':.99,'output_cost_per_token':.99},
            'cost_map_omits_token_price':lambda *a:False,'_pricing_override_stamps':lambda *a:{},
            'remove_sensitive_info_from_deployment':lambda model,**k:model}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'native-model-getter.py','exec'),ns)
        model=M.publication(BASE,'v1',PROJECT,DECLARED)['model_list'][0]
        result=ns['_enrich_model_info_with_litellm_data'](copy.deepcopy(model))
        self.assertEqual(result['model_info'],model['model_info'])


if __name__=='__main__':unittest.main()
