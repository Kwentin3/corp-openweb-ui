"""Native source seams and offline coordinator faults; no runtime/Redis proof."""
import ast
import asyncio
import copy
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from typing import SupportsInt, SupportsIndex
from collections.abc import Mapping
import unittest
from unittest.mock import patch
from uuid import uuid4

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import prove_budget_overlap as p


class NativeFixture(p.NativeProof):
    """Run the actual native proof API/projection helpers; double only HTTP."""
    def __init__(self):
        super().__init__('http://127.0.0.1:4000', 'private-test-operator', 1, {})
        self.uid = str(uuid4())
        self.user = {'user_id':self.uid, 'user_role':'internal_user', 'models':list(p.MODELS), 'spend':0,
                     'max_budget':2, 'budget_duration':'30d', 'budget_reset_at':'2026-12-03T01:02:03Z'}
        self.key_rows, self.journal, self.calls, self.reads = [], [], [], []
        self.state = {'users':{'one':self.uid}, 'user_caps':{self.uid:'2'}, 'keys':{}}
        for n, model in enumerate(p.MODELS):
            token='private-fixture-token-'+str(n)
            key_hash=hashlib.sha256(token.encode()).hexdigest()
            self.state['keys'][self.uid+'|'+model]={'token':token,'hash':key_hash,'alias':'expected-'+model,'cap':'1'}
            self.keys[self.uid,model]=self.state['keys'][self.uid+'|'+model]
            self.key_rows.append({'token':key_hash,'user_id':self.uid,'models':[model],'key_alias':'expected-'+model,
                'spend':0,'max_budget':1,'budget_duration':'30d','budget_reset_at':'2026-12-03T01:02:04Z',
                'blocked':False,'metadata':{'assignment':'synthetic-fixture'},'team_id':None})
        self.state['created']=p.old_snapshot(self,[self.uid])

    def request(self, method, path, *, query=None, **kwargs):
        self.reads.append((method,path))
        if method != 'GET': raise AssertionError('Settlement must be read-only')
        if path == '/user/info': payload={'user_info':self.user,'keys':self.key_rows}
        elif path == '/key/info':
            key_hash=hashlib.sha256(query['key'].encode()).hexdigest()
            payload={'info':next(row for row in self.key_rows if row['token']==key_hash)}
        elif path == '/spend/logs/v2': payload={'data':self.journal,'total_pages':1}
        else: raise AssertionError('Unexpected native read')
        return 200,copy.deepcopy(payload),{}

    def admit(self, model):
        identifier='chatcmpl-goal584-'+uuid4().hex
        scope={'chat_id':str(uuid4()),'call_id':str(uuid4()),'user_id':self.uid,'model':model}
        self.calls.append({'provider_id':identifier,'outcome':'success','user_id':self.uid,'model':model,'scope':scope})
        key=next(row for row in self.key_rows if row['models']==[model])
        self.user['spend']+=.2; key['spend']+=.2
        self.journal.append({'request_id':identifier,'user':self.uid,'api_key':key['token'],'model_group':model,
            'session_id':scope['chat_id'],'metadata':{'spend_logs_metadata':{'owui_budget':scope}},'spend':.2,
            'status':'success','prompt_tokens':10,'completion_tokens':5,'total_tokens':15})

    def reconcile(self):
        with patch.object(p,'results',return_value=self.calls):
            return p.reconcile(self,self.state)


class NativeSeamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=HERE.parents[1]/'local/goal584/litellm/upstream/litellm/proxy/spend_tracking/budget_reservation.py'
        if not path.exists():raise unittest.SkipTest('Pinned native source unavailable; no runtime proof implied')
        source=ast.parse(path.read_text(encoding='utf-8'))
        names={'_estimate_output_tokens','_requested_output_tokens','_is_input_only_route','_to_int','_get_budget_counters','_BudgetCounter'}
        nodes=[node for node in source.body if getattr(node,'name',None) in names or isinstance(node,ast.AnnAssign)
               and isinstance(node.target,ast.Name) and node.target.id in ('DEFAULT_MAX_OUTPUT_TOKENS_FALLBACK','_OUTPUT_TOKEN_FIELDS')]
        cls.ns={'__name__':__name__,'dataclass':dataclass,'Mapping':Mapping,'SupportsInt':SupportsInt,'SupportsIndex':SupportsIndex}
        async def absent(**kwargs):return None
        async def empty(**kwargs):return []
        cls.ns.update(_get_budget_limit_counters=lambda **kwargs:[],_get_end_user_budget_counter=absent,
            _get_tag_budget_counters=empty,_get_model_access_group_budget_counters=empty,
            _get_team_member_budget_counter=absent,_get_org_budget_counter=absent,_get_project_budget_counter=absent)
        execute=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*nodes],type_ignores=[])
        exec(compile(ast.fix_missing_locations(execute),'pinned-native-budget-reservation','exec'),cls.ns)

    def test_actual_native_output_ceiling_clamps_requested_max_tokens(self):
        owner=self.ns['_estimate_output_tokens']
        self.assertEqual(owner({'max_tokens':5},'/v1/chat/completions',{'max_output_tokens':5}),5)
        self.assertEqual(owner({'max_tokens':999999},'/v1/chat/completions',{'max_output_tokens':5}),5)
        self.assertEqual(owner({},'/v1/chat/completions',{'max_output_tokens':5}),5)
        self.assertEqual(owner({'max_tokens':999999},'/v1/embeddings',{'max_output_tokens':5}),0)

    def test_actual_native_counter_selection_same_key_and_shared_user_across_models(self):
        uid=str(uuid4())
        user=SimpleNamespace(user_id=uid,max_budget=1.2,spend=0)
        async def counters(token):
            return await self.ns['_get_budget_counters']({},SimpleNamespace(token=token,max_budget=1.2,spend=0,budget_limits=None),
                None,user,None,None,None)
        first=asyncio.run(counters('a'*64));same=asyncio.run(counters('a'*64));other=asyncio.run(counters('b'*64))
        self.assertEqual([v.counter_key for v in first],['spend:key:'+'a'*64,'spend:user:'+uid])
        self.assertEqual([v.counter_key for v in first],[v.counter_key for v in same])
        self.assertNotEqual(first[0].counter_key,other[0].counter_key)
        self.assertEqual(first[1].counter_key,other[1].counter_key)


class EvidenceTests(unittest.TestCase):
    def test_prepare_and_finally_restore_do_not_introduce_unremovable_optional_provider_controls(self):
        users=[str(uuid4()) for _ in range(6)]
        webui={'schema':1,'admin':{'id':users[0]},'users':[{'id':users[1]},{'id':users[2]}],
               'bootstrap_fixture':{'employee':{'id':users[3]}},'service_fixture':{'payer_id':users[4]}}
        original={'prompt_tokens':10,'completion_tokens':5,'delay_ms':0,'tool_round':False,'admin_mode':True,'title_mode':False}
        control=dict(original)
        def provider(method='GET',path=None,body=None):
            if method=='POST':control.update(body)
            return {'synthetic':True,'control':dict(control),'requests':[]}
        native=SimpleNamespace(poll=lambda label,fn:{})
        real_read=p.read_private
        with tempfile.TemporaryDirectory() as directory,patch.object(p,'STATE',Path(directory)/'state.private.json'), \
             patch.object(p,'read_private',side_effect=lambda path:webui if path.name=='webui-state.private.json' else real_read(path)), \
             patch.object(p,'provider',side_effect=provider),patch.object(p,'capture',return_value=[]), \
             patch.object(p,'old_snapshot',return_value={}),patch.object(p,'create'), \
             patch.object(p,'call',return_value={'native_estimate_usd':'.8'}), \
             patch.object(p,'native_write_private',side_effect=lambda path,value:path.write_text(json.dumps(value),encoding='utf-8')), \
             patch.object(p,'native_read_private',side_effect=lambda path:json.loads(path.read_text(encoding='utf-8'))), \
             patch.object(p,'proof',return_value=(native,{})):
            p.prepare(native,{'users':[users[5]],'operator_user':'synthetic-operator'})
            self.assertEqual(set(control),set(original))
            self.assertFalse(control['admin_mode'])
            self.assertTrue(p.worker('restore')['controls_restored'])
        self.assertEqual(control,original)

    def test_calibration_requires_actual_matching_estimates_strictly_above_actual_cost(self):
        reserve,budget=p.calibrated_caps(dict(zip(p.MODELS,['.8','.8'])))
        self.assertEqual((reserve,budget),(Decimal('.8'),Decimal('1.3')))
        self.assertGreater(budget,reserve+p.CALL_COST)
        self.assertLess(budget,2*reserve)
        for estimates in (['.2','.2'],['.1','.1'],['.8','.81'],['NaN','NaN'],['5','5']):
            with self.subTest(estimates=estimates),self.assertRaises(p.ProofError):
                p.calibrated_caps(dict(zip(p.MODELS,estimates)))
        reserve,budget=p.calibrated_caps(dict(zip(p.MODELS,['.21','.21'])))
        self.assertEqual(budget,Decimal('.415'))
        self.assertLess(float(reserve)+float(p.CALL_COST),p.cap(budget))
        self.assertLess(budget,2*reserve)

    def test_creation_retains_api_reset_and_policy_using_actual_native_read_helpers(self):
        class GeneratedNative(NativeFixture):
            def request(self,method,path,*,body=None,**kwargs):
                if method=='POST' and path=='/user/new':
                    self.user.update({key:body[key] for key in ('user_id','user_role','models','max_budget','budget_duration')})
                    return 200,{},{}
                if method=='POST' and path=='/key/generate':
                    token='sk-synthetic-fixture-'+str(len(self.key_rows))
                    self.key_rows.append({'token':hashlib.sha256(token.encode()).hexdigest(),
                        **{key:body[key] for key in ('user_id','models','key_alias','max_budget','budget_duration','metadata')},
                        'spend':0,'blocked':False,'team_id':None,'budget_reset_at':'2026-12-04T03:04:05Z'})
                    return 200,{'key':token},{}
                return super().request(method,path,**kwargs)
        native=GeneratedNative();native.key_rows=[];native.keys={}
        state={'users':{'one':native.uid},'keys':{}}
        saved=[]
        spec=importlib.util.spec_from_file_location('employee_budget_assignment',p.ROOT/p.SOURCE_PATHS['employee_budget_assignment.py'])
        assignment=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(assignment)
        with patch.dict(sys.modules,{'employee_budget_assignment':assignment}), \
             patch.object(p,'write_private',side_effect=lambda path,value:saved.append(copy.deepcopy(value))):
            p.create(native,state,'one',Decimal(2),Decimal(1))
        self.assertEqual(state['created'],p.old_snapshot(native,[native.uid]))
        self.assertEqual(state['created'][native.uid]['user']['budget_reset_at'],'2026-12-03T01:02:03Z')
        self.assertEqual({key['budget_reset_at'] for key in state['created'][native.uid]['keys']},{'2026-12-04T03:04:05Z'})
        self.assertEqual(saved[-1]['created'],state['created'])
        self.assertIn(('GET','/key/info'),native.reads)
        with patch.object(p,'results',return_value=[]):self.assertIsNotNone(p.reconcile(native,state))

    def test_actual_provider_arrival_requires_exact_context_and_unfinished_lifecycle(self):
        state={'key_before_ids':['chatcmpl-goal584-'+'a'*32]}
        row={'id':'chatcmpl-goal584-'+'b'*32,'body':{'model':'goal584-fake-a',**{k:v for k,v in p.BODY.items() if k!='stream'}},
             'lifecycle':{'started':True,'terminal':False}}
        with patch.object(p,'provider',return_value={'requests':[row]}):
            self.assertEqual(p.held_witness(state,'key')['terminal'],False)
        for mutate in (lambda r:r['lifecycle'].update(terminal=True),lambda r:r['lifecycle'].update(started=False),
                       lambda r:r['body'].update(messages=[])):
            changed=json.loads(json.dumps(row));mutate(changed)
            with patch.object(p,'provider',return_value={'requests':[changed]}),self.assertRaises(p.ProofError):
                p.held_witness(state,'key')
        with patch.object(p,'provider',return_value={'requests':[row,row]}),self.assertRaises(p.ProofError):p.held_witness(state,'key')
        with patch.object(p,'provider',return_value={'requests':[]}):self.assertIsNone(p.held_witness(state,'key'))

    def test_provider_and_credentials_do_not_become_receipt_fields(self):
        for value in ('sk-'+'x'*32,'gw-'+'x'*32,'eyJaaa.bbb.ccc'):
            with self.assertRaises(p.ProofError):p.safe({'native':value})
            with self.assertRaises(p.ProofError):p.request_id(value)
        self.assertEqual(p.safe({'scope':'key','native_estimate_usd':'.8'}),{'scope':'key','native_estimate_usd':'.8'})

    def test_reconcile_native_rows_and_counters_rejects_foreign_hash_cost_scope_and_duplicates(self):
        native=NativeFixture()
        for model in p.MODELS:native.admit(model)
        self.assertEqual(len(native.reconcile()['positive_rows']),2)
        for field,value in [('api_key','z'*64),('user',str(uuid4())),('spend',.4),('session_id',str(uuid4()))]:
            old=native.journal[0][field];native.journal[0][field]=value
            with self.subTest(field=field),self.assertRaises(p.ProofError):native.reconcile()
            native.journal[0][field]=old
        native.journal.append(native.journal[0])
        with self.assertRaises(p.ProofError):native.reconcile()

    def test_creation_projection_rejects_all_nonspend_mutations_and_population_changes(self):
        native=NativeFixture()
        self.assertIsNotNone(native.reconcile())
        user_changes={'user_id':str(uuid4()),'user_role':'proxy_admin','models':[], 'max_budget':2.000000001,
                      'budget_duration':'1mo','budget_reset_at':'changed-reset'}
        key_changes={'token':'f'*64,'user_id':str(uuid4()),'models':[p.MODELS[1]],'key_alias':'changed-alias',
                     'max_budget':1.000000001,'budget_duration':'1mo','budget_reset_at':'changed-reset',
                     'blocked':True,'metadata':{'private':'changed'},'team_id':'other-team'}
        for row, changes in ((native.user,user_changes),(native.key_rows[0],key_changes)):
            for field,value in changes.items():
                old=row[field];row[field]=value
                with self.subTest(field=field),self.assertRaisesRegex(p.ProofError,'identity or policy changed'):
                    native.reconcile()
                row[field]=old
        native.key_rows.append(copy.deepcopy(native.key_rows[0]))
        with self.assertRaises(p.ProofError):native.reconcile()
        native.key_rows.pop(); saved=native.key_rows.pop()
        with self.assertRaises(p.ProofError):native.reconcile()
        native.key_rows.append(saved)
        self.assertIsNotNone(native.reconcile())
        self.assertTrue(all(method=='GET' for method,path in native.reads))

    def test_untouched_zero_is_exact_but_expected_positive_counter_keeps_native_float_tolerance(self):
        native=NativeFixture()
        for target in (native.user,native.key_rows[0],native.key_rows[1]):
            target['spend']=1e-12
            with self.assertRaisesRegex(p.ProofError,'untouched'):native.reconcile()
            target['spend']=0
        for _ in range(3):native.admit(p.MODELS[0])
        self.assertEqual(native.user['spend'],0.6000000000000001)
        self.assertIsNotNone(native.reconcile())
        native.user['spend']=.6-1e-9
        self.assertIsNotNone(native.reconcile())
        native.key_rows[1]['spend']=1e-12
        with self.assertRaisesRegex(p.ProofError,'untouched'):native.reconcile()

    def test_lag_is_pending_but_later_surplus_identity_or_extra_row_always_fails(self):
        native=NativeFixture();native.admit(p.MODELS[0])
        native.user['spend']=0
        self.assertIsNone(native.reconcile())
        for value in (.21,.4,-.01):
            native.key_rows[0]['spend']=value
            with self.subTest(value=value),self.assertRaises(p.ProofError):native.reconcile()
        native.key_rows[0]['spend']=.2
        native.key_rows[1]['key_alias']='changed-after-lag'
        with self.assertRaises(p.ProofError):native.reconcile()
        native.key_rows[1]['key_alias']='expected-'+p.MODELS[1]
        native.journal.append({**native.journal[0],'request_id':'chatcmpl-goal584-'+uuid4().hex})
        with self.assertRaises(p.ProofError):native.reconcile()
        native.journal.pop(); row=native.journal.pop(); native.user['spend']=.2
        self.assertIsNone(native.reconcile())
        native.journal.append(row);native.key_rows[0]['spend']=0
        self.assertIsNone(native.reconcile())
        native.key_rows[0]['spend']=.2
        self.assertIsNotNone(native.reconcile())


class CoordinatorTests(unittest.TestCase):
    def test_installed_worker_path_does_not_require_repository_parent_depth(self):
        tree=ast.parse(Path(p.__file__).read_text(encoding='utf-8'))
        node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ROOT' for t in n.targets))
        namespace={'__file__':'/proof/prove_budget_overlap.py','Path':Path}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'actual-worker-install-path','exec'),namespace)
        self.assertTrue(namespace['ROOT'].is_absolute())

    def coordinator(self,fail=None,done=False,mismatch=False):
        actions=[]
        class Fake(p.Coordinator):
            def topology(self):return {'containers':['one','two']}
            def invoke(self,index,action,**values):
                actions.append(action)
                case=values.get('case') or values.get('label','key_hold').split('_')[0]
                identifier='chatcmpl-goal584-'+('a' if case=='key' else 'b')*32
                if action=='witness':return {'provider_id':identifier,'terminal':False}
                if action==fail:raise p.ProofError('bounded native late failure')
                if action=='call':return {'provider_id':'wrong' if mismatch else identifier}
                return {}
        class Deferred:
            def __init__(self,fn,args,kwargs):self.fn,self.args,self.kwargs=fn,args,kwargs
            def done(self):return done
            def result(self,timeout):
                actions.append('await_held_settlement')
                return self.fn(*self.args,**self.kwargs)
        class Executor:
            def __init__(self,**kwargs):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def submit(self,fn,*args,**kwargs):return Deferred(fn,args,kwargs)
        args=SimpleNamespace(project='goal584-overlap',env_file=Path('private.env'),compose_file=['compose/goal584.native-budget-proof.yml'])
        return Fake(args),actions,Executor

    def test_coordinator_finally_settles_held_request_before_restoring_controls_on_late_failure(self):
        coordinator,actions,executor=self.coordinator(fail='contend')
        with patch.object(p,'ThreadPoolExecutor',executor),self.assertRaisesRegex(p.ProofError,'late failure'):
            coordinator.execute({})
        self.assertLess(actions.index('await_held_settlement'),actions.index('restore'))
        self.assertNotIn('resume',actions)

    def test_coordinator_rejects_settled_future_or_different_actual_response_identity(self):
        for flags in (dict(done=True),dict(mismatch=True)):
            coordinator,actions,executor=self.coordinator(**flags)
            with patch.object(p,'ThreadPoolExecutor',executor),self.assertRaises(p.ProofError):coordinator.execute({})
            self.assertIn('await_held_settlement',actions)
            self.assertEqual(actions[-1],'restore')

    def test_coordinator_uses_distinct_exec_indexes_and_requires_both_cases_before_final(self):
        coordinator,actions,executor=self.coordinator()
        receipt={}
        with patch.object(p,'ThreadPoolExecutor',executor):coordinator.execute(receipt)
        self.assertEqual(actions.count('contend'),2)
        self.assertEqual(actions.count('resume'),2)
        self.assertEqual(actions[-2:],['final','restore'])
        with patch.object(coordinator,'run_json',return_value={}) as command:
            p.Coordinator.invoke(coordinator,2,'contend',case='key')
        argv=command.call_args.args[0]
        self.assertEqual(argv[argv.index('--index')+1],'2')
        self.assertNotIn('http://', ' '.join(argv))

    def test_topology_binds_distinct_container_ids_ordinal_image_health_and_source(self):
        args=SimpleNamespace(project='goal584-overlap',env_file=Path('private.env'),compose_file=[],private_root=Path('/private-fixture'))
        coordinator=p.Coordinator(args)
        rows=[dict(id=str(i)*64,image_ref=p.IMAGE,image_id='sha256:'+'f'*64,health='healthy',number=str(i),
            project=args.project,service='proxy',network_mode=args.project+'_proof',private_mount=str(args.private_root),command=['--config','/proof/config.yaml',
            '--host','0.0.0.0','--port','4000','--num_workers','1','--telemetry','false']) for i in (1,2)]
        identity={'files_sha256':{name:hashlib.sha256((p.ROOT/path).read_bytes()).hexdigest() for name,path in p.SOURCE_PATHS.items()},
                  'config_sha256':'a'*64,'database_url_sha256':'b'*64}
        provider_source={'mock_provider.py':hashlib.sha256((p.ROOT/p.PROVIDER_SOURCE).read_bytes()).hexdigest()}
        with patch.object(p.subprocess,'run',return_value=subprocess.CompletedProcess([],0,b'1'*64+b'\n'+b'2'*64+b'\n',b'')), \
             patch.object(coordinator,'run_json',side_effect=[*rows,provider_source]),patch.object(coordinator,'invoke',return_value=identity):
            observed=coordinator.topology()
            self.assertEqual(len(observed['containers']),2)
            self.assertEqual(observed['provider_source_sha256'],provider_source)
        for field,value in [('number','1'),('image_ref','foreign'),('health','unhealthy'),('network_mode','foreign'),('private_mount','foreign')]:
            changed=[dict(r) for r in rows];changed[1][field]=value
            with patch.object(p.subprocess,'run',return_value=subprocess.CompletedProcess([],0,b'1'*64+b'\n'+b'2'*64+b'\n',b'')), \
                 patch.object(coordinator,'run_json',side_effect=changed),self.assertRaises(p.ProofError):coordinator.topology()
        with patch.object(p.subprocess,'run',return_value=subprocess.CompletedProcess([],0,b'1'*64+b'\n'+b'2'*64+b'\n',b'')), \
             patch.object(coordinator,'run_json',side_effect=[*rows,{'mock_provider.py':'foreign'}]), \
             patch.object(coordinator,'invoke',return_value=identity),self.assertRaisesRegex(p.ProofError,'Provider mounted source'):
            coordinator.topology()

    def test_custom_import_and_callback_closure_has_existing_readonly_mounts(self):
        import yaml
        mounted={}
        for filename in ('goal584.native-budget-proof.yml','goal584.webui-proof.yml'):
            compose=yaml.safe_load((p.ROOT/'compose'/filename).read_text(encoding='utf-8'))
            for entry in compose['services']['proxy'].get('volumes',[]):
                if isinstance(entry,dict) and entry.get('read_only'):
                    mounted[entry['target']]=entry['source']
        for name,path in p.SOURCE_PATHS.items():
            if name=='prove_budget_overlap.py':continue  # The new parent overlay owns this mount.
            self.assertEqual(mounted.get('/proof/'+name),'../'+path)
        names={Path(name).stem for name in p.SOURCE_PATHS}
        project_modules={path.stem for path in HERE.glob('*.py')}|{Path(target).stem for target in mounted if target.endswith('.py')}
        for path in p.SOURCE_PATHS.values():
            tree=ast.parse((p.ROOT/path).read_text(encoding='utf-8'))
            imports={node.module for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)}
            self.assertFalse((imports & project_modules)-names)
        config=yaml.safe_load((HERE/'litellm_config.yaml').read_text(encoding='utf-8'))
        self.assertEqual(config['litellm_settings']['callbacks'],['budget_errors.handler','pricing_snapshot.handler'])
        for callback in config['litellm_settings']['callbacks']:
            self.assertIn(callback.split('.')[0]+'.py',p.SOURCE_PATHS)
        provider_compose=yaml.safe_load((p.ROOT/'compose/goal584.native-budget-proof.yml').read_text(encoding='utf-8'))
        entry=provider_compose['services']['provider']['volumes'][0]
        self.assertEqual((entry['source'],entry['target'],entry['read_only']),('../'+p.PROVIDER_SOURCE,'/proof/mock_provider.py',True))

    def test_worker_identity_requires_actual_current_callback_configuration(self):
        import yaml
        config=yaml.safe_load((HERE/'litellm_config.yaml').read_text(encoding='utf-8'))
        config['general_settings']['custom_auth']='capture_webui_auth.gateway_auth'
        with tempfile.TemporaryDirectory() as directory:
            mount=Path(directory)
            for name,path in p.SOURCE_PATHS.items():(mount/name).write_bytes((p.ROOT/path).read_bytes())
            def mounted(path):
                return mount/'config.yaml' if str(path)=='/proof/config.yaml' else mount
            for callbacks,valid in ((['budget_errors.handler','pricing_snapshot.handler'],True),
                    (['budget_errors.handler'],False),(['pricing_snapshot.handler','budget_errors.handler'],False)):
                config['litellm_settings']['callbacks']=callbacks
                (mount/'config.yaml').write_text(yaml.safe_dump(config),encoding='utf-8')
                native=SimpleNamespace(schema=lambda:None)
                with self.subTest(callbacks=callbacks),patch.object(p,'proof',return_value=(native,{})), \
                     patch.object(p,'Path',side_effect=mounted),patch.dict(p.os.environ,
                        {'DATABASE_URL':'postgresql://fixture:private-test@postgres:5432/goal584','OWUI_BUDGET_REQUIRE_PROVENANCE':'true'}):
                    if valid:self.assertEqual(set(p.worker('identity')['files_sha256']),set(p.SOURCE_PATHS))
                    else:
                        with self.assertRaisesRegex(p.ProofError,'configuration differs'):p.worker('identity')

    def test_unsafe_private_output_is_rejected_before_docker_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);private=root/'private';private.mkdir(mode=0o700)
            env=root/'proof.env';env.write_text('PROOF_PRIVATE_DIR='+str(private)+'\n',encoding='utf-8');env.chmod(0o600)
            output=private/'not-public.json'
            argv=['proof','--env-file',str(env),'--project','goal584-overlap','--compose-file','compose/goal584.native-budget-proof.yml','--receipt',str(output)]
            with patch.object(sys,'argv',argv),patch.object(p.Coordinator,'execute') as execute,patch('sys.stdout',new=io.StringIO()):
                self.assertEqual(p.main(),1)
            execute.assert_not_called();self.assertFalse(output.exists())


if __name__=='__main__':unittest.main()
