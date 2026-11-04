"""Real usage validators/Host; native HTTP, Docker/Git and private writes are IO doubles."""
import ast
import base64
import copy
from contextlib import redirect_stdout
from datetime import datetime, timezone
from enum import Enum
from functools import lru_cache
import json
import io
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
from typing import TypedDict
import unittest
from unittest.mock import patch

import yaml
import prove_pricing_usage as M
import prove_native_budgets as native_owner
from test_pricing_catalog import source, status, Response, fixture as catalog_fixture

V=M.versions
REPO=M.ROOT
BASE=yaml.safe_load((REPO/'scripts/goal584-budget-proof/litellm_config.yaml').read_bytes())
USER='af4769c2-5cbe-4d85-a519-c8b22f035ae0'
OLD='df4769c2-5cbe-4d85-a519-c8b22f035ae0'
PROJECT='goal584-pricing-'+'a'*12
CONTROL={'prompt_tokens':10,'completion_tokens':5,'delay_ms':0,'tool_round':False,'admin_mode':False,'title_mode':False}


@lru_cache(None)
def native_blob(name):
    return subprocess.check_output(['git','-c','gc.auto=0','show',
        'd665dc1a6315847fcad6cc2c1264ceb47c06abce:litellm/'+name],
        cwd=REPO/'local/goal584/litellm/upstream',env=os.environ|{'GIT_NO_LAZY_FETCH':'1'})


@lru_cache(None)
def codec():
    raw=native_blob('responses/utils.py');assert M.sha(raw)==M.NATIVE['responses/utils.py']
    cls=next(n for n in ast.parse(raw).body if isinstance(n,ast.ClassDef) and n.name=='ResponsesAPIRequestUtils')
    cls.body=[n for n in cls.body if getattr(n,'name',None) in ('_build_responses_api_response_id','_decode_responses_api_response_id')]
    enums=next(n for n in ast.parse(native_blob('types/utils.py')).body if isinstance(n,ast.ClassDef) and n.name=='SpecialEnums')
    decoded=next(n for n in ast.parse(native_blob('types/responses/main.py')).body if isinstance(n,ast.ClassDef) and n.name=='DecodedResponseId')
    ns={'Enum':Enum,'TypedDict':TypedDict,'base64':base64,'verbose_logger':logging.getLogger(__name__)}
    exec(compile(ast.Module(body=[enums,decoded,cls],type_ignores=[]),'exact-pinned-native-id-owner','exec',
        flags=__import__('__future__').annotations.compiler_flag),ns)
    return ns['ResponsesAPIRequestUtils']


def state(count=2):
    calls=[]
    for i,label in enumerate(M.LABELS[:count]):
        index=0 if i<2 else i-1;deployment=M.ALIASES[index]+'-'+('v2' if i==1 else 'v1')
        pid='resp_goal584_'+str(i+1)*32
        response={'id':codec()._build_responses_api_response_id('openai',deployment,pid),'usage':copy.deepcopy(M.RAW_USAGE)}
        calls.append({'label':label,'alias':M.ALIASES[index],'deployment':deployment,'provider_id':pid,'response':response,
            'cost':'.166' if i==0 else '.334','lineage':{'chat_id':USER+'-chat-'+str(i),'root_answer_id':'answer-'+str(i),'call_kind':'synthetic_pricing_usage'}})
    return {'schema':1,'proof':M.PROOF,'project':PROJECT,'user_id':USER,'base':copy.deepcopy(BASE),
        'started_at':'1970-01-01T00:00:00+00:00','calls':calls,'keys':{a:{'token':'sk-synthetic-'+str(i)*20,
        'hash':M.sha(('sk-synthetic-'+str(i)*20).encode())} for i,a in enumerate(M.ALIASES)},
        'provider_before':{'synthetic':True,'control':copy.deepcopy(CONTROL),'requests':[]},'old_users':[OLD],
        'old_history':{OLD:{'profile':{'user_id':OLD,'keys':[],'spend':.4},'rows':[{'request_id':'old','user':OLD,'spend':.4}]}},'settled_rows':[]}


def budget(s,spend=.5):
    common={'user_id':USER,'max_budget':20,'budget_duration':'1mo','budget_reset_at':'2026-12-01T00:00:00'}
    keys={a:common|{'models':[a],'spend':spend if i==0 else 0.,'total_spend':spend if i==0 else 0.,
        'team_id':None,'allowed_routes':['llm_api_routes']} for i,a in enumerate(M.ALIASES)}
    embedded=sorted([v|{'token':s['keys'][a]['hash']} for a,v in keys.items()],key=lambda r:r['token'])
    return {'user':common|{'user_role':'internal_user','models':list(M.ALIASES),'teams':[],
        'keys':embedded,'spend':spend},'keys':keys}


def row(s,c):
    rates=dict(zip(V.rate_fields(REPO/'deploy/openwebui-budgets/pricing_snapshot.py'),(.01,.02,
        .001 if c['label']=='positive_v1' else .009,.001 if c['label']=='positive_v1' else .009,.01,.01,
        .03 if c['label']=='positive_v1' else .09)))
    inner=c['lineage']|{'owui_billed_token_rates':{'schema':1,'availability':'available',
        'observed_at_utc':'2026-11-04T12:00:00Z','rates':rates},'owui_tariff_descriptor':{
        'schema':1,'availability':'unknown','descriptor':None,'reason':'eligibility'}}
    return {'request_id':c['response']['id'],'user':USER,'api_key':s['keys'][M.ALIASES[0]]['hash'],
        'model':'openai/'+M.WIRES[0],'model_group':M.ALIASES[0],'model_id':c['deployment'],'session_id':c['lineage']['chat_id'],
        'status':'success','spend':float(c['cost']),**V.USAGE,'metadata':json.dumps({'spend_logs_metadata':inner})}


def physical(s):
    result=copy.deepcopy(s['provider_before'])
    for i,c in enumerate(s['calls']):
        index=M.ALIASES.index(c['alias']);usage=copy.deepcopy(M.RAW_USAGE) if index==0 else None
        response={'id':c['provider_id'],'model':M.WIRES[index],'object':'response','status':'completed','error':None,'usage':usage}
        if index==1:response.pop('usage')
        result['requests'].append({'id':c['provider_id'],'body':{'model':M.WIRES[index],'input':'Hi',
            'max_output_tokens':16,'store':False,'stream':False},'usage':usage,'response':response,
            'lifecycle':{'terminal':True,'outcome':'completed','response_status':200,'usage_sent':index==0}})
    return result


class UsageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.saved=[]
        module=ModuleType('litellm.responses.utils');module.ResponsesAPIRequestUtils=codec()
        self.patches=[patch.dict(sys.modules,{'litellm.responses.utils':module}),
            patch.object(M,'write_private',side_effect=lambda path,value:self.saved.append(copy.deepcopy(value))),
            patch.object(V.catalog,'write_private',side_effect=lambda path,value:self.saved.append(copy.deepcopy(value))),
            patch.object(M,'STATE',self.root/'state.private.json'),
            patch.object(V,'CALLBACK',REPO/'deploy/openwebui-budgets/pricing_snapshot.py')]
        for p in self.patches:p.start();self.addCleanup(p.stop)

    def native(self,s,rows=None,values=None,provider=None):
        n=M.versions.NativeProof('http://127.0.0.1:4000','sk-synthetic-not-exported',1,{})
        n.started_at=datetime(1970,1,1,tzinfo=timezone.utc);queries=[]
        rows=[row(s,c) for c in s['calls'][:2]] if rows is None else rows
        values=budget(s,.166 if len(s['calls'])==1 else .5) if values is None else values
        s.setdefault('baseline_budget',budget(s,0.))
        def request(method,path,**kw):
            queries.append((method,path,kw))
            if path=='/spend/logs/v2':value={'data':rows if kw['query']['user_id']==USER else s['old_history'][OLD]['rows'],'total_pages':1}
            elif path=='/user/info':
                profile=values['user'] if kw['query']['user_id']==USER else s['old_history'][OLD]['profile']
                value={'user_info':{k:v for k,v in profile.items() if k!='keys'},'keys':profile['keys']}
            elif path=='/key/info':
                alias=next(a for a in M.ALIASES if s['keys'][a]['hash']==kw['query']['key']);value={'key':s['keys'][alias]['hash'],'info':values['keys'][alias]}
            elif path=='/user/list':value={'users':[{'user_id':OLD},{'user_id':USER}],'page':1,'total':2,'total_pages':1}
            else:raise AssertionError('Unplanned native IO '+path)
            return 200,copy.deepcopy(value),{}
        n.request=request
        n.opener=SimpleNamespace(open=lambda request,timeout:Response(200,provider if provider is not None else physical(s)))
        return n,queries

    def test_configuration_preserves_base_and_changes_only_explicit_used_terms(self):
        before=copy.deepcopy(BASE);v1=M.configuration(BASE,'v1');v2=M.configuration(BASE,'v2')
        self.assertEqual(BASE,before);self.assertEqual(v1['model_list'][:2],BASE['model_list'])
        self.assertEqual({k:v for k,v in v1.items() if k!='model_list'},{k:v for k,v in BASE.items() if k!='model_list'})
        self.assertEqual([v['model_name'] for v in v1['model_list'][2:]],list(M.ALIASES))
        left,right=v1['model_list'][2],v2['model_list'][2]
        self.assertEqual(left['litellm_params'],{'model':'openai/'+M.WIRES[0],'api_base':'http://provider:8000/v1','api_key':'synthetic-provider-only-not-a-credential'})
        self.assertEqual(left['model_info']|{'id':right['model_info']['id'],'cache_read_input_token_cost':.009,'output_cost_per_reasoning_token':.09},right['model_info'])
        self.assertEqual(v1['model_list'][3:],v2['model_list'][3:])
        with self.assertRaises(M.ProofError):M.configuration(BASE,'v3')

    def test_positive_rows_use_actual_native_id_owner_and_preserve_old_rows(self):
        s=state();n,queries=self.native(s);first=M.observe(n,s)
        self.assertEqual(first['raw_row_count'],2);self.assertEqual(len(first['positive_rows']),2)
        self.assertEqual(first['positive_rows'][0]['rates']['cache_read_input_token_cost'],.001)
        self.assertEqual(first['positive_rows'][1]['rates']['output_cost_per_reasoning_token'],.09)
        self.assertEqual(first['old_history_sha256'],M.sha(M.encoded(s['old_history'])))
        self.assertTrue(all(m=='GET' for m,_,_ in queries));self.assertTrue(self.saved)
        changed=[row(s,c) for c in s['calls']];changed[0]['metadata']+=' '
        n,_=self.native(s,rows=changed)
        with self.assertRaisesRegex(M.ProofError,'usage_old_row_changed'):M.observe(n,s)

    def test_row_mutations_reject_caller_model_key_lineage_rate_and_usage(self):
        expected={'user':'Native spend API crossed user scope','key':'usage_foreign_raw_row',
            'lineage':'usage_positive_lineage','rates':'usage_protected_native_rates',
            'missing_rate':'usage_snapshot_schema','counter':'usage_positive_counter_surplus'}
        for mutation in ('user','key','model','deployment','provider_id','lineage','rates','usage_type','missing_rate','counter'):
            with self.subTest(mutation=mutation):
                s=state(1);r=row(s,s['calls'][0]);values=budget(s,.166)
                if mutation=='user':r['user']=OLD
                elif mutation=='key':r['api_key']='foreign'
                elif mutation=='model':r['model_group']='foreign'
                elif mutation=='deployment':r['model_id']='foreign'
                elif mutation=='provider_id':s['calls'][0]['provider_id']='foreign'
                elif mutation=='usage_type':r['prompt_tokens']=10.0
                elif mutation=='counter':values['keys'][M.ALIASES[0]]['spend']=.3
                else:
                    meta=json.loads(r['metadata']);inner=meta['spend_logs_metadata']
                    if mutation=='lineage':inner['root_answer_id']='foreign'
                    elif mutation=='rates':inner['owui_billed_token_rates']['rates']['cache_read_input_token_cost']=.9
                    else:inner['owui_billed_token_rates']['rates'].pop('cache_creation_input_token_cost')
                    r['metadata']=json.dumps(meta)
                n,_=self.native(s,rows=[r],values=values)
                with self.assertRaisesRegex(M.ProofError,expected.get(mutation,'usage_positive_identity_cost')):M.observe(n,s)

    def test_old_native_profile_and_raw_history_are_independently_immutable(self):
        for changed in ('profile','row'):
            with self.subTest(changed=changed):
                s=state();n,_=self.native(s);original=n.request
                def request(method,path,**kw):
                    code,value,headers=original(method,path,**kw)
                    if changed=='profile' and path=='/user/info' and kw['query']['user_id']==OLD:value['user_info']['spend']=.41
                    if changed=='row' and path=='/spend/logs/v2' and kw['query']['user_id']==OLD:value['data'][0]['spend']=.41
                    return code,value,headers
                n.request=request
                with self.assertRaisesRegex(M.ProofError,'usage_old_history_changed'):M.observe(n,s)

    def test_physical_mutations_reject_before_row_reads_and_pending_does_not_settle(self):
        for mutation in ('cached_float','reasoning_bool','body','control','prefix','duplicate'):
            with self.subTest(mutation=mutation):
                s=state();p=physical(s)
                if mutation=='cached_float':p['requests'][0]['usage']['input_tokens_details']['cached_tokens']=6.0
                elif mutation=='reasoning_bool':p['requests'][0]['usage']['output_tokens_details']['reasoning_tokens']=True
                elif mutation=='body':p['requests'][0]['body']['input']='Other'
                elif mutation=='control':p['control']['tool_round']=True
                elif mutation=='prefix':s['provider_before']['requests']=[{'foreign':True}]
                else:p['requests'][1]['id']=p['requests'][0]['id']
                n,q=self.native(s,provider=p)
                with self.assertRaises(M.ProofError):M.observe(n,s)
                self.assertFalse(q)
        s=state(1);p=physical(s);p['requests'][0]['lifecycle'].update(terminal=False,outcome=None,usage_sent=False);n,q=self.native(s,provider=p)
        self.assertIsNone(M.observe(n,s));self.assertFalse(q)

    def test_unknown_rows_are_observations_with_no_final_queue_or_free_claim(self):
        s=state(4);rows=[row(s,c) for c in s['calls'][:2]]
        n,_=self.native(s,rows=rows);first=M.observe(n,s)
        self.assertFalse(first['unknown_rows_finality']);self.assertEqual(first['raw_row_count'],2)
        late={'request_id':'late-negative','user':USER,'api_key':s['keys'][M.ALIASES[1]]['hash'],
            'model_group':M.ALIASES[1],'status':'failure','spend':.25,'prompt_tokens':9,'completion_tokens':1,'total_tokens':10,'metadata':'{}'}
        n,_=self.native(s,rows=rows+[late]);second=M.observe(n,s)
        self.assertEqual(second['raw_row_count'],3);self.assertFalse(second['unknown_rows_finality'])
        self.assertEqual(second['all_rows'][-1]['spend']['value'],.25)
        self.assertNotIn('negative_cases_are_policy_qualification',second)

    def test_terminal_usage_is_typed_and_matches_usage_sent(self):
        for mutation in ('response_cached_float','positive_not_sent','negative_sent','missing_null_usage',
                         'foreign_id','foreign_model','foreign_status','foreign_object','foreign_error'):
            with self.subTest(mutation=mutation):
                s=state(4);p=physical(s)
                if mutation=='response_cached_float':
                    p['requests'][0]['response']['usage']=copy.deepcopy(M.RAW_USAGE)
                    p['requests'][0]['response']['usage']['input_tokens_details']['cached_tokens']=6.0
                elif mutation=='positive_not_sent':p['requests'][0]['lifecycle']['usage_sent']=False
                elif mutation=='negative_sent':p['requests'][2]['lifecycle']['usage_sent']=True
                elif mutation=='missing_null_usage':p['requests'][3]['response'].pop('usage')
                else:p['requests'][3]['response'][mutation.removeprefix('foreign_')]='foreign'
                n,_=self.native(s,provider=p)
                with self.assertRaises(M.ProofError):M.physical(n,s)

    def test_repeated_call_is_rejected_before_any_transport(self):
        s=state(4)
        with patch.object(M,'read_private',return_value=s),patch.dict(os.environ,{'PROOF_PRICING_PROJECT':PROJECT,'PROOF_MASTER_KEY':'sk-synthetic-master-for-local-tests'}), \
                patch.object(V.NativeProof,'request',side_effect=AssertionError('transport must not run')) as transport:
            with self.assertRaisesRegex(M.ProofError,'usage_call_order_or_retry'):M.worker('call','positive_v1',PROJECT)
        transport.assert_not_called()

    def test_two_actual_worker_errors_preserve_first_private_failure_and_safe_packets(self):
        private=state(4);private['schema']=True;M.STATE.write_text('{}')
        def persist(path,value):private.clear();private.update(copy.deepcopy(value))
        packets=[]
        with patch.object(M,'read_private',side_effect=lambda path:copy.deepcopy(private)), \
                patch.object(M,'write_private',side_effect=persist), \
                patch.dict(os.environ,{'PROOF_PRICING_PROJECT':PROJECT,'PROOF_MASTER_KEY':'sk-synthetic-master-for-local-tests'}), \
                patch.object(V.NativeProof,'request',side_effect=AssertionError('transport must not run')) as transport:
            for action,label in (('identity','base'),('call','positive_v1')):
                output=io.StringIO()
                with patch.object(sys,'argv',['prove_pricing_usage.py','--worker-action',action,'--label',label,'--project',PROJECT]),redirect_stdout(output):
                    self.assertEqual(M.main(),1)
                packets.append(json.loads(output.getvalue()))
                if action=='identity':
                    first=copy.deepcopy(private['primary_failure']);private['schema']=1
                    self.assertEqual(first['message'],'usage_private_scope')
            self.assertEqual(private['primary_failure'],first)
        transport.assert_not_called()
        for packet in packets:
            self.assertFalse(packet['passed']);self.assertEqual(packet['failure_code'],'usage_verification_failed')
            self.assertNotIn('message',packet['result']['failure'])
            self.assertTrue(packet['result']['failure']['frames'])
            self.assertNotIn('sk-synthetic',M.encoded(packet).decode())

    def test_identity_uses_real_native_source_config_and_catalog_validators(self):
        package=self.root/'litellm';package.mkdir();mount=self.root/'proof';mount.mkdir()
        paths=set(M.NATIVE)|{p.removeprefix('litellm/') for p in V.catalog.native_sdk.load_manifest()['native_export_sha256']}
        for name in paths:
            target=package/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(native_blob(name))
        for name,path in M.SOURCE_PATHS.items():(mount/name).write_bytes((REPO/path).read_bytes())
        config=self.root/'config.yaml';active=M.configuration(BASE,'v1');config.write_text(yaml.safe_dump(active))
        initial=source('S2');schedule=status(initial)
        s=state();s.update(source=initial,schedule=schedule)
        n=V.NativeProof('http://127.0.0.1:4000','synthetic',1,{})
        def request(method,path,**kw):
            self.assertEqual(method,'GET')
            if path=='/model/info':value={'data':[{'model_name':m['model_name'],'model_info':m['model_info']} for m in active['model_list']]}
            elif path==V.catalog.SOURCE:value=source('S2',seconds=30)|{'model_count':initial['model_count']+7}
            elif path==V.catalog.STATUS:value=copy.deepcopy(schedule)
            else:raise AssertionError(path)
            if mutation=='model' and path=='/model/info':value=copy.deepcopy(value);value['data'][-1]['model_info']['id']='foreign'
            if mutation=='source_revision' and path==V.catalog.SOURCE:value=source('S1',seconds=30)
            if mutation=='source_etag' and path==V.catalog.SOURCE:value['etag']=source('S1')['etag']
            if mutation=='schedule' and path==V.catalog.STATUS:value['last_run']='2026-11-04T12:00:00Z'
            return 200,value,{}
        n.request=request
        def mapped_path(value):return mount if str(value)=='/proof' else Path(value)
        with patch.object(V,'CONFIG',config),patch.object(M,'Path',side_effect=mapped_path), \
                patch.object(M.importlib.util,'find_spec',return_value=SimpleNamespace(origin=str(package/'__init__.py'))), \
                patch.dict(os.environ,{'PROOF_PRICING_PROJECT':PROJECT,'PROOF_NATIVE_VARIANT':'stock','PROOF_LITELLM_IMAGE':V.catalog.native_sdk.BASE_IMAGE}):
            s['native_artifact']=V.catalog.native_sdk.identity();mutation=None
            baseline=M.identity(n,s,'v1');self.assertEqual(baseline['native_sources'],M.NATIVE)
            self.assertEqual(baseline['server_runtime_model_count'],initial['model_count']+7)
            for mutation,code in (('model','usage_model_info'),('source_revision','usage_source_schedule_changed'),
                                 ('source_etag','catalog_source_binding'),('schedule','usage_source_schedule_changed'),
                                 ('native','usage_native_sources'),('config','usage_config_readback')):
                with self.subTest(mutation=mutation):
                    if mutation=='native':(package/'router.py').write_bytes(b'foreign')
                    if mutation=='config':config.write_text(yaml.safe_dump(BASE))
                    with self.assertRaisesRegex(M.ProofError,code):M.identity(n,s,'v1')
                    (package/'router.py').write_bytes(native_blob('router.py'));config.write_text(yaml.safe_dump(active))

    def test_real_reference_fixture_arms_source_s2_and_restores_original_s1_after_partial_io(self):
        for partial in (False,True):
            with self.subTest(partial=partial):
                private=state();private['reference_fixture']={'original':'S1','source':'S2','arm_attempted':False}
                world={'variant':'S1'};controls=[]
                def persist(path,value):private.clear();private.update(copy.deepcopy(value))
                def http(request,timeout):
                    self.assertEqual(request.full_url.split('/__proof/catalog')[0],'http://provider:8000')
                    if request.data is not None:
                        target=json.loads(request.data)['variant'];controls.append(target)
                        if target=='S2':self.assertTrue(private['reference_fixture']['arm_attempted'])
                        world['variant']=target
                        if partial and target=='S2':raise OSError('synthetic partial control write')
                    return Response(200,catalog_fixture(world['variant']))
                with patch.object(M,'read_private',side_effect=lambda path:copy.deepcopy(private)), \
                        patch.object(M,'write_private',side_effect=persist),patch.object(V.catalog,'write_private',side_effect=persist), \
                        patch.object(native_owner,'build_opener',return_value=SimpleNamespace(open=http)), \
                        patch.dict(os.environ,{'PROOF_PRICING_PROJECT':PROJECT,'PROOF_MASTER_KEY':'sk-synthetic-master-for-local-tests'}), \
                        patch.object(V.NativeProof,'request',side_effect=AssertionError('No native model/API operation permitted')) as native:
                    if partial:
                        with self.assertRaisesRegex(M.ProofError,'catalog_fixture_http'):M.worker('reference_fixture','source',PROJECT)
                    else:
                        self.assertEqual(M.worker('reference_fixture','source',PROJECT)['variant'],'S2')
                        self.assertFalse(M.worker('reference_fixture','source',PROJECT)['changed'])
                        self.assertEqual(controls,['S2'])
                    self.assertEqual(world['variant'],'S2');self.assertTrue(private['reference_fixture']['arm_attempted'])
                    restored=M.worker('reference_fixture','original',PROJECT)
                    self.assertEqual(restored,{'variant':'S1','original_variant':'S1','source_variant':'S2','changed':True})
                    self.assertEqual(world['variant'],'S1');self.assertEqual(controls,['S2','S1']);native.assert_not_called()


class UsageHostTests(unittest.TestCase):
    def replay(self,mutation=None):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);checkout=root/'checkout';checkout.mkdir();private=root/'private';private.mkdir()
            config=private/'config.yaml';original=yaml.safe_dump(BASE).encode();config.write_bytes(original)
            env=private/'proof.env';env.write_text('SYNTHETIC=1')
            for name,path in M.SOURCE_PATHS.items():
                target=checkout/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((REPO/path).read_bytes())
            volumes=[{'type':'bind','source':str(config),'target':'/proof/config.yaml','read_only':True},
                {'type':'bind','source':str(private),'target':'/proof-private','read_only':False}]
            volumes += [{'type':'bind','source':str(checkout/path),'target':'/proof/'+name,'read_only':True} for name,path in M.SOURCE_PATHS.items()]
            mounts=[{'Type':'bind','Source':m['source'],'Destination':m['target'],'RW':not m['read_only']} for m in volumes]
            args=SimpleNamespace(project=PROJECT,private_root=private,env_file=env,compose_file=['compose/goal584.native-budget-proof.yml','compose/goal584.pricing-proof.yml'])
            host=M.UsageHost(args);image='sha256:'+'c'*64;ids={s:str(i)*64 for i,s in enumerate(('proxy','postgres','provider','redis'),1)}
            actions=[];published=[];world={'variant':'S1','proxy_source':'S2','source_arms':0}
            drains=[0,1,2,2] if mutation in ('worker_failure','worker_and_restore_failure','worker_and_reference_restore_failure') else [0,1,4,4,4]
            def output(argv,**kwargs):
                if argv[:3]==['git','rev-parse','HEAD']:return ('a'*40).encode()
                if argv[0]=='git':
                    value=(checkout/argv[-1].split(':',1)[1]).read_bytes()
                    return value+b'foreign' if mutation=='source' else value
                return '\n'.join(ids.values()).encode()
            def run(argv,**kwargs):
                if argv[:2]==['docker','inspect']:
                    service=next(s for s,i in ids.items() if i==argv[-1]);value={'id':ids[service],'service':service,'project':PROJECT,
                        'number':'1','network':PROJECT+'_proof','health':'healthy','image_ref':image if service=='proxy' else V.catalog.IMAGES[service],
                        'image_id':image,'mounts':mounts if service=='proxy' else [],'command':V.catalog.COMMAND if service=='proxy' else []}
                elif argv[-3:]==['config','--format','json']:value={'services':{'proxy':{'volumes':volumes}}}
                elif argv[-2:]==['restart','proxy'] or 'up' in argv:
                    world['proxy_source']=world['variant']
                    published.append(config.read_bytes());return SimpleNamespace(returncode=0,stdout=b'')
                elif '--worker-action' in argv:
                    action=argv[argv.index('--worker-action')+1];label=argv[argv.index('--label')+1] if '--label' in argv else None;actions.append((action,label))
                    value={}
                    failed=False
                    if action=='identity':
                        self.assertEqual(world['proxy_source'],'S2','Native proxy would reject changed source revision')
                        value={'identity':{'config_sha256':M.sha(config.read_bytes()),'worker_id_prefix':ids['proxy'][:12]}}
                    elif action=='reference_fixture':
                        if label=='source':
                            world['source_arms']+=1
                            if mutation=='reference_rearm_failure' and world['source_arms']==2:failed=True
                            else:world['variant']='S2'
                            if mutation in ('partial_arm','partial_arm_restore_failure') and world['source_arms']==1:failed=True
                        else:
                            if mutation in ('partial_arm_restore_failure','worker_and_reference_restore_failure'):failed=True
                            else:world['variant']='S1'
                        value={'variant':world['variant'],'original_variant':'S1','source_variant':'S2'}
                    elif action=='drain':
                        dispatches=drains.pop(0);value={'financial':{'physical_calls':3 if mutation=='wrong_dispatch_count' and dispatches==4 else dispatches}}
                        if mutation=='before_publication_failure' and dispatches==0:failed=True
                    failed |= action=='call' and label=='positive_v2' and mutation in ('worker_failure','worker_and_restore_failure','worker_and_reference_restore_failure')
                    if failed:
                        line=123 if action=='call' else 211 if label=='source' else 312 if label=='original' else 411
                        value={'failure':{'exception_class':'ProofError','frames':[{'source':'prove_pricing_usage.py','line':line}]}}
                    value={'schema':1,'proof':M.PROOF,'passed':not failed,'action':action,'result':value,'failure_code':'usage_verification_failed' if failed else None}
                    if mutation=='protocol':value['schema']=True
                    if mutation=='old_config' and action=='identity' and label=='v1':value['result']['identity']['config_sha256']=M.sha(original)
                    if mutation in ('restore_failure','worker_and_restore_failure') and action=='identity' and label=='base':value['result']['identity']['config_sha256']='foreign'
                    return SimpleNamespace(returncode=1 if failed else 0,stdout=json.dumps(value).encode())
                else:value={p:M.sha((checkout/M.SOURCE_PATHS[p.removeprefix('/proof/')]).read_bytes()) for p in argv[argv.index('-c')+2:]}
                return SimpleNamespace(returncode=0,stdout=json.dumps(value).encode())
            with patch.object(V,'ROOT',checkout),patch.object(M,'ROOT',checkout), \
                    patch.dict(os.environ,{'PROOF_SOURCE_COMMIT':'a'*40,'PROOF_NATIVE_VARIANT':V.catalog.native_sdk.VARIANT,'PROOF_LITELLM_IMAGE':image}), \
                    patch.object(V.subprocess,'check_output',side_effect=output),patch.object(V.subprocess,'run',side_effect=run):
                error=None
                try:host.execute()
                except M.ProofError as exc:error=str(exc)
            self.assertEqual(config.read_bytes(),original)
            expected_variant='S2' if mutation in ('partial_arm_restore_failure','worker_and_reference_restore_failure') else 'S1'
            self.assertEqual(world['variant'],expected_variant)
            return host.receipt,error,actions,[yaml.safe_load(raw) for raw in published]

    def test_real_host_uses_exact_publications_protocol_and_restores_original_bytes(self):
        receipt,error,actions,published=self.replay()
        self.assertIsNone(error);self.assertTrue(receipt['passed']);self.assertFalse(receipt['unknown_rows_finality'])
        self.assertFalse(receipt['negative_cases_are_policy_qualification'])
        self.assertEqual([label for action,label in actions if action=='call'],list(M.LABELS))
        self.assertEqual(published,[M.configuration(BASE,'v1')]*2+[M.configuration(BASE,'v2')]*2+[BASE]*2)
        self.assertEqual(receipt['restoration'],{'original_bytes_equal':True,'failures':[],
            'reference_fixture_restored':True,'unknown_rows_finality':False})
        self.assertEqual(actions[:3],[('prepare',None),('reference_fixture','source'),('drain',None)])
        self.assertEqual(actions[-4:],[('reference_fixture','source'),('identity','base'),('drain',None),('reference_fixture','original')])

    def test_real_host_rejects_source_protocol_and_restoration_without_retry(self):
        for mutation in ('source','protocol','old_config','wrong_dispatch_count','worker_failure','restore_failure','worker_and_restore_failure'):
            with self.subTest(mutation=mutation):
                receipt,error,actions,published=self.replay(mutation)
                self.assertIsNotNone(error);self.assertFalse(receipt['passed']);self.assertTrue(receipt['restoration']['original_bytes_equal'])
                self.assertLessEqual(sum(label=='positive_v2' for action,label in actions if action=='call'),1)
                if mutation in ('worker_failure','worker_and_restore_failure'):
                    self.assertEqual(receipt['primary_failure']['frames'],[{'source':'prove_pricing_usage.py','line':123}])
                    self.assertEqual([l for a,l in actions if a=='call'],['positive_v1','positive_v2'])
                if mutation=='worker_and_restore_failure':self.assertIn('config_restore_failed',receipt['restoration']['failures'])

    def test_reference_partial_arm_failure_restores_original_without_gratuitous_restart(self):
        for mutation in ('partial_arm','before_publication_failure','partial_arm_restore_failure','reference_rearm_failure','worker_and_reference_restore_failure'):
            with self.subTest(mutation=mutation):
                receipt,error,actions,published=self.replay(mutation)
                self.assertIsNotNone(error);self.assertFalse(receipt['passed'])
                self.assertTrue(receipt['restoration']['original_bytes_equal'])
                self.assertEqual(actions[-1],('reference_fixture','original'))
                calls=[label for action,label in actions if action=='call']
                self.assertEqual(len(calls),len(set(calls)))
                if mutation in ('partial_arm','before_publication_failure','partial_arm_restore_failure'):
                    self.assertEqual(published,[]);self.assertFalse(any(a=='call' for a,_ in actions))
                    self.assertEqual(sum((a,l)==('reference_fixture','source') for a,l in actions),1)
                if mutation in ('partial_arm_restore_failure','worker_and_reference_restore_failure'):
                    self.assertFalse(receipt['restoration']['reference_fixture_restored'])
                    self.assertIn('reference_fixture_restore_failed',receipt['restoration']['failures'])
                    line=211 if mutation=='partial_arm_restore_failure' else 123
                    self.assertEqual(receipt['primary_failure']['frames'],[{'source':'prove_pricing_usage.py','line':line}])
                else:self.assertTrue(receipt['restoration']['reference_fixture_restored'])
                if mutation=='reference_rearm_failure':
                    self.assertIn('reference_fixture_rearm_failed',receipt['restoration']['failures'])
                    self.assertEqual(error,'usage_restoration_failed')
                    self.assertEqual(actions[-4:],[('reference_fixture','source'),('identity','base'),('drain',None),('reference_fixture','original')])


if __name__=='__main__':unittest.main()
