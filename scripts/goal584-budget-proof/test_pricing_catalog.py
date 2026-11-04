"""Source-rehearsed native catalog sequencing; HTTP/process boundaries are doubles."""
import ast
from collections import deque
import copy
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta, timezone
from email.message import Message
import hashlib
import importlib.util
import io
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch, AsyncMock
from urllib.parse import urlsplit

import prove_gateway_auth as private_owner
import prove_pricing_catalog as M


class Response(io.BytesIO):
    def __init__(self, status, value):
        super().__init__(json.dumps(value).encode())
        self.code = self.status = status
        self.headers = Message();self.headers['Content-Type'] = 'application/json'


def fixture(variant='S1', counts=None):
    counts = dict.fromkeys(M.DOCUMENTS, 0) | (counts or {})
    return {'synthetic': True, 'variant': variant, 'native_revision': M.native_sdk.BASE_REVISION,
        'corpus_sha256': M.NATIVE['model_prices_and_context_window_backup.json'], 'corpus_git_blob': M.BACKUP_BLOB,
        'corpus_entry_count': 4460, 'request_count': sum(counts.values()), 'requests_by_variant': counts,
        'documents': {k: {'sha256': h, 'native_git_blob': blob, 'bytes': size, 'etag': '"'+h+'"'} for k,(h,blob,size) in M.DOCUMENTS.items()}}


def source(variant=None, seconds=0):
    return {'source': 'remote' if variant else 'local', 'url': M.CATALOG if variant else None,
        'is_env_forced': variant is None, 'fallback_reason': None, 'model_count': 4464,
        'loaded_at': (datetime(2026,11,3,12,tzinfo=timezone.utc)+timedelta(seconds=seconds)).isoformat(),
        'source_revision': M.DOCUMENTS[variant][1] if variant else M.BACKUP_BLOB,
        'etag': '"'+M.DOCUMENTS[variant][0]+'"' if variant else None}


def status(src, scheduled=False, seconds=None):
    last = None if seconds is None else datetime(2026,11,3,12,tzinfo=timezone.utc)+timedelta(seconds=seconds)
    return {'scheduled': scheduled, 'interval_hours': 1 if scheduled else None,
        'last_run': last.isoformat() if last else None, 'next_run': (last+timedelta(hours=1)).isoformat() if last and scheduled else None,
        'source_revision': src['source_revision'], 'etag': src['etag']}


def frame(tag, method, path, payload, code=200, body=None):
    return {'tag': tag, 'method': method, 'path': path, 'payload': payload, 'code': code, 'body': body}


def capture(tag, src, state, catalog):
    return [frame(tag+'.source','GET',M.SOURCE,src), frame(tag+'.status','GET',M.STATUS,state),
        frame(tag+'.catalog','GET','/__proof/catalog/observations',catalog),
        frame(tag+'.physical','GET','/__proof/requests',{'synthetic':True,'requests':[],'control':{'unchanged':True}})]


def frames(boot_remote=False):
    boot = 1 if boot_remote else 0
    local, s1, s2 = source('S1' if boot_remote else None),source('S1',30),source('S2',31)
    q=[frame('schema','GET','/openapi.json',{'info':{'version':'1.105.1'},'paths':{}})]
    q+=capture('baseline',local,status(local),fixture(counts={'S1':boot}))
    q+=[frame('schedule','POST',M.SCHEDULE+'?hours=1',{'status':'success','interval_hours':1})]
    q+=capture('pending',local,status(local,True),fixture(counts={'S1':boot}))
    q+=capture('first',s1,status(s1,True,30),fixture(counts={'S1':boot+1}))
    q+=[frame('S2.control','POST','/__proof/catalog/control',fixture('S2',{'S1':boot+1}),body={'variant':'S2'}),
        frame('S2.reload','POST',M.RELOAD,{'status':'success','source_revision':s2['source_revision'],'etag':s2['etag']})]
    counts={'S1':boot+1,'S2':1}
    q+=capture('S2',s2,status(s2,True,31),fixture('S2',counts))
    for variant in ('invalid','truncated'):
        q+=[frame(variant+'.control','POST','/__proof/catalog/control',fixture(variant,counts),body={'variant':variant})]
        q+=capture(variant+'.before',s2,status(s2,True,31),fixture(variant,counts))
        q+=[frame(variant+'.reload','POST',M.RELOAD,{'detail':'Native parse failure; current map kept'},502)]
        counts=counts|{variant:1}
        q+=capture(variant+'.after',s2,status(s2,True,31),fixture(variant,counts))
    q+=restore_frames(s2,counts,catalog_owned=True)
    return q


def restore_frames(src, counts, catalog_owned):
    q=[frame('cancel','DELETE',M.SCHEDULE,{'status':'success'})]
    if catalog_owned:q+=[frame('restore.control','POST','/__proof/catalog/control',fixture('S1',counts),body={'variant':'S1'})]
    q+=capture('restored',src,status(src,False,31 if src==source('S2',31) else 30),fixture('S1',counts))
    return q


class ScriptedHTTP:
    """Reviewable HTTP transcript, not a replacement native schedule implementation."""
    def __init__(self, queue, after=None):
        self.queue=deque(copy.deepcopy(queue));self.calls=[];self.after=after

    def open(self, request, timeout):
        self.calls.append((request.get_method(),request.full_url,request.headers,request.data))
        if not self.queue:raise AssertionError('Unplanned external HTTP call')
        item=self.queue.popleft();parsed=urlsplit(request.full_url)
        actual=parsed.path+('?' + parsed.query if parsed.query else '')
        if (request.get_method(),actual)!=(item['method'],item['path']):raise AssertionError('Unexpected external HTTP operation '+actual)
        if request.data is not None and json.loads(request.data)!=item['body']:raise AssertionError('Unexpected external HTTP body')
        if self.after:self.after(item)
        return Response(item['code'],item['payload'])


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        # Windows lacks POSIX permission bits; retain actual atomic write/fsync/bytes.
        if os.name=='nt':
            guard=patch.object(private_owner,'private_parent',lambda p:p.parent.mkdir(exist_ok=True))
            guard.start();self.addCleanup(guard.stop)

    def coordinator(self, queue, after=None):
        native=M.NativeProof('http://127.0.0.1:4000','sk-synthetic-private-master-000000',120,{})
        native.opener=ScriptedHTTP(queue,after)
        receipt={'observations':[],'stage':'preflight'}
        return M.Coordinator(native,self.root/'state.private.json',receipt)

    def test_actual_http_owner_sequence_pending_first_poll_and_private_safe_packets(self):
        for remote in (False,True):
            with self.subTest(boot_remote=remote),patch.object(M.time,'sleep',lambda _:None):
                c=self.coordinator(frames(remote));c.run()
                self.assertFalse(c.native.opener.queue)
                self.assertEqual(c.receipt['stage'],'observed')
                self.assertEqual(c.receipt['restoration']['failures'],[])
                self.assertFalse(c.receipt['restoration']['active_native_map_restored'])
                self.assertEqual(c.receipt['observations'][-1]['source']['source_revision'],M.DOCUMENTS['S2'][1])
                self.assertEqual(c.receipt['observations'][-1]['catalog']['variant'],'S1')
                private=json.loads(c.path.read_text());self.assertEqual(private['proof'],M.PROOF)
                self.assertGreater(len(private['api']),0)
                text=M.encoded(c.receipt).decode();self.assertNotIn('sk-synthetic',text);self.assertNotIn('Authorization',text)
                for method,url,headers,data in c.native.opener.calls:
                    self.assertNotIn('/chat/',url)
                    if url.startswith('http://provider:'):self.assertNotIn('Authorization',headers)

    def test_foreign_existing_schedule_fails_without_any_restoration_mutation(self):
        q=frames();q[2]['payload']['scheduled']=True;q[2]['payload']['interval_hours']=1
        c=self.coordinator(q[:5])
        with self.assertRaisesRegex(M.ProofError,'catalog_not_fresh'):c.run()
        self.assertFalse(c.claimed)
        self.assertFalse(c.receipt['restoration']['attempted'])
        self.assertTrue(all(method=='GET' for method,*_ in c.native.opener.calls))

    def test_missing_native_route_fails_before_claim(self):
        q=frames();q[1].update(code=404,payload={'detail':'Not Found'})
        c=self.coordinator(q[:5])
        with self.assertRaisesRegex(M.ProofError,'catalog_native_read_status'):c.run()
        self.assertFalse(c.claimed)

    def test_late_http_completion_is_not_a_success_even_with_ready_payload(self):
        q=frames();cut=next(i for i,x in enumerate(q) if x['tag']=='first.physical')
        q=q[:cut+1]+restore_frames(source('S1',30),{'S1':1},False)
        clock=[0.0]
        def after(item):
            if item['tag']=='first.physical':clock[0]=121.0
        c=self.coordinator(q,after)
        with patch.object(M.time,'monotonic',lambda:clock[0]),patch.object(M.time,'sleep',lambda _:None):
            with self.assertRaisesRegex(M.ProofError,'catalog_late_poll_completion'):c.run()
        self.assertEqual(c.receipt['stage'],'first_native_poll')
        self.assertEqual(c.receipt['restoration']['failures'],[])

    def test_native_success_without_fetch_delta_or_last_run_is_not_accepted(self):
        q=frames();cut=next(i for i,x in enumerate(q) if x['tag']=='first.physical')
        q=q[:cut+1]+restore_frames(source('S1',30),{},False)
        for item in q:
            if item['tag']=='first.catalog':item['payload']['requests_by_variant']['S1']=0;item['payload']['request_count']=0
        c=self.coordinator(q)
        with patch.object(M.time,'sleep',lambda _:None):
            with self.assertRaises(Exception):c.run()
        self.assertNotEqual(c.receipt['stage'],'observed')

    def test_foreign_private_metadata_is_retained_before_strict_rejection_not_exported(self):
        q=frames();cut=next(i for i,x in enumerate(q) if x['tag']=='first.physical')
        q=q[:cut+1]+restore_frames(source('S1',30),{'S1':1},False)
        for item in q:
            if item['tag']=='first.source':item['payload']['private_extra']='sk-private-should-not-leak-123456'
        c=self.coordinator(q)
        with patch.object(M.time,'sleep',lambda _:None):
            with self.assertRaisesRegex(M.ProofError,'catalog_source_shape'):c.run()
        self.assertIn('sk-private-should-not-leak',c.path.read_text())
        self.assertNotIn('sk-private-should-not-leak',M.encoded(c.receipt).decode())

    def test_primary_failure_survives_cancel_and_fixture_restore_failure(self):
        q=frames();cut=next(i for i,x in enumerate(q) if x['tag']=='S2.reload')
        q=q[:cut+1]+restore_frames(source('S2',31),{'S1':1,'S2':1},True)
        q[cut]['code']=500
        for item in q:
            if item['tag'] in ('cancel','restore.control'):item['code']=503
        c=self.coordinator(q)
        with patch.object(M.time,'sleep',lambda _:None):
            with self.assertRaisesRegex(M.ProofError,'catalog_manual_reload_failed'):c.run()
        self.assertIn('cancel_failed',c.receipt['restoration']['failures'])
        self.assertIn('catalog_restore_failed',c.receipt['restoration']['failures'])
        self.assertEqual(c.receipt['stage'],'manual_S2')

    def test_invalid_fetch_is_not_allowed_to_change_source_or_persisted_last_run(self):
        q=frames();cut=next(i for i,x in enumerate(q) if x['tag']=='invalid.after.physical')
        q=q[:cut+1]+restore_frames(source('S2',31),{'S1':1,'S2':1,'invalid':1},True)
        for item in q:
            if item['tag']=='invalid.after.status':item['payload']['last_run']='2026-11-03T12:00:32+00:00';item['payload']['next_run']='2026-11-03T13:00:32+00:00'
        c=self.coordinator(q)
        with patch.object(M.time,'sleep',lambda _:None):
            with self.assertRaisesRegex(M.ProofError,'catalog_invalid_fetch_changed_native_state'):c.run()

    def test_extra_api_or_body_is_refused_before_external_io(self):
        c=self.coordinator([])
        for method,path,kwargs in [('POST','/user/new',{}),('GET',M.SOURCE,{'query':{'url':'https://example.invalid'}}),('POST',M.RELOAD,{'body':{'model':'paid'}})]:
            with self.subTest(path=path),self.assertRaises(M.ProofError):c.native_request(method,path,**kwargs)
        self.assertEqual(c.native.opener.calls,[])

    def test_unexpected_physical_call_and_unknown_document_etag_fail_immediately(self):
        for mutation in ('physical','etag'):
            q=frames();cut=next(i for i,x in enumerate(q) if x['tag']=='first.physical')
            q=q[:cut+1]+restore_frames(source('S1',30),{'S1':1},False)
            for item in q:
                if mutation=='physical' and item['tag']=='first.physical':item['payload']['requests']=[{'private_body':'never export'}]
                if mutation=='etag' and item['tag']=='first.catalog':item['payload']['documents']['S1']['etag']='"foreign"'
            c=self.coordinator(q)
            with self.subTest(mutation=mutation),patch.object(M.time,'sleep',lambda _:None),self.assertRaises(M.ProofError):c.run()
            self.assertNotIn('never export',M.encoded(c.receipt).decode())

    def test_private_write_failure_preserves_primary_and_attempts_both_restorations(self):
        q=frames();cut=next(i for i,x in enumerate(q) if x['tag']=='S2.reload')
        q=q[:cut+1]+restore_frames(source('S2',31),{'S1':1,'S2':1},True)
        broken=[False]
        def after(item):
            if item['tag']=='S2.reload':broken[0]=True
        c=self.coordinator(q,after);save=c.save
        def write():
            if broken[0]:raise OSError('private path must never become public error')
            save()
        with patch.object(c,'save',write),patch.object(M.time,'sleep',lambda _:None):
            with self.assertRaisesRegex(OSError,'private path'):c.run()
        methods=[(m,urlsplit(url).path) for m,url,*_ in c.native.opener.calls]
        self.assertIn(('DELETE',M.SCHEDULE),methods)
        self.assertIn(('POST','/__proof/catalog/control'),methods)
        self.assertEqual(c.receipt['stage'],'manual_S2')
        self.assertNotIn('private path',M.encoded(c.receipt).decode())
        self.assertIn('cancel_failed',c.receipt['restoration']['failures'])
        self.assertIn('catalog_restore_failed',c.receipt['restoration']['failures'])

    def test_invalid_output_path_does_not_write_a_failure_packet_elsewhere(self):
        argv=['probe','--project','goal584-pricing-'+'a'*12,'--attestation',str(self.root/'attestation'),
            '--private-state',str(self.root/'state'),'--receipt',str(self.root.parent/'outside.private.json')]
        with patch.object(M,'PRIVATE',self.root),patch.object(sys,'argv',argv),patch.object(M,'write_private') as write,patch('builtins.print'):
            self.assertEqual(M.main(),1)
        write.assert_not_called()

    def test_cancel_cannot_clear_history_or_fixture_counter_observations(self):
        for mutation in ('last_run','counts'):
            q=frames()
            for item in q:
                if mutation=='last_run' and item['tag']=='restored.status':item['payload']['last_run']=None
                if mutation=='counts' and item['tag']=='restored.catalog':item['payload']['requests_by_variant']['invalid']=0;item['payload']['request_count']-=1
            c=self.coordinator(q)
            with self.subTest(mutation=mutation),patch.object(M.time,'sleep',lambda _:None),self.assertRaisesRegex(M.ProofError,'catalog_restoration_failed'):c.run()
            self.assertIn('restore_readback_failed',c.receipt['restoration']['failures'])

    def main_result(self, queue, final_error=None):
        """Actual main/coordinator/private state writes; only external preflight/HTTP doubled."""
        directory = self.root/('main-'+str(len(list(self.root.iterdir()))))
        directory.mkdir()
        config = directory/'config.yaml';config.write_text('{}',encoding='utf8')
        target = directory/'receipt.safe.json'
        argv=['probe','--project','goal584-pricing-'+'a'*12,'--attestation',str(directory/'attestation.private.json'),
            '--private-state',str(directory/'state.private.json'),'--receipt',str(target)]
        native=M.NativeProof('http://127.0.0.1:4000','sk-private-master-must-not-escape-000000',120,{})
        native.opener=ScriptedHTTP(queue)
        writes=[];original_write=M.write_private
        def writer(path,value):
            if path==target:
                writes.append(copy.deepcopy(value))
                if final_error is not None:raise final_error
            original_write(path,value)
        stdout,stderr=io.StringIO(),io.StringIO()
        with patch.object(M,'PRIVATE',directory),patch.object(M,'CONFIG',config),patch.object(sys,'argv',argv), \
                patch.dict(os.environ,{'PROOF_MASTER_KEY':'sk-private-master-must-not-escape-000000'}), \
                patch.object(M,'profile'),patch.object(M,'read_private',return_value={'source_commit':'a'*40,'native_artifact':{'variant':'external-preflight-double'}}), \
                patch.object(M,'NativeProof',return_value=native),patch.object(M,'write_private',side_effect=writer), \
                patch.object(M.time,'sleep',lambda _:None),redirect_stdout(stdout),redirect_stderr(stderr):
            code=M.main()
        self.assertFalse(native.opener.queue,'Restoration/HTTP transcript must finish before final writer')
        self.assertTrue((directory/'state.private.json').is_file())
        self.assertEqual(stderr.getvalue(),'')
        self.assertNotIn('Traceback',stdout.getvalue())
        self.assertNotIn('sk-private',stdout.getvalue())
        self.assertNotIn('private filesystem detail',stdout.getvalue())
        return code,json.loads(stdout.getvalue()),target,writes

    def test_actual_main_primary_error_survives_final_writer_failures_without_traceback(self):
        q=frames();cut=next(i for i,x in enumerate(q) if x['tag']=='S2.reload')
        q=q[:cut+1]+restore_frames(source('S2',31),{'S1':1,'S2':1},True);q[cut]['code']=500
        for error in (OSError('private filesystem detail sk-private-error-000000000'),
                      M.ProofError('private filesystem detail sk-private-error-000000000')):
            with self.subTest(writer=type(error).__name__):
                code,summary,target,writes=self.main_result(q,error)
                self.assertEqual(code,1)
                self.assertEqual(summary,{'proof':M.PROOF,'passed':False,'stage':'manual_S2',
                    'failure_code':'catalog_manual_reload_failed','receipt_write_failure':'catalog_receipt_write_failed'})
                self.assertEqual(len(writes),1)
                self.assertEqual(writes[0]['failure_code'],'catalog_manual_reload_failed')
                self.assertEqual(writes[0]['restoration']['failures'],[])
                self.assertFalse(target.exists())

    def test_actual_main_success_requires_successful_final_receipt_write(self):
        code,summary,target,writes=self.main_result(frames())
        self.assertEqual(code,0)
        self.assertEqual(summary,{'proof':M.PROOF,'passed':True,'stage':'observed'})
        self.assertTrue(json.loads(target.read_text(encoding='utf8'))['passed'])
        self.assertEqual(len(writes),1)
        code,summary,target,writes=self.main_result(frames(),OSError('private filesystem detail sk-private-error-000000000'))
        self.assertEqual(code,1)
        self.assertEqual(summary,{'proof':M.PROOF,'passed':False,'stage':'observed',
            'failure_code':'catalog_receipt_write_failed','receipt_write_failure':'catalog_receipt_write_failed'})
        self.assertFalse(target.exists())
        self.assertEqual(len(writes),1,'No evidence-writer retry or new native operation')


def native_blob(test,path):
    root=Path(os.environ.get('GOAL584_LITELLM_SOURCE',Path(__file__).resolve().parents[2]/'local/goal584/litellm/upstream'))
    if not root.is_dir():test.skipTest('Exact read-only d665 cache unavailable; set GOAL584_LITELLM_SOURCE')
    try:return subprocess.check_output(['git','-c','gc.auto=0','show',M.native_sdk.BASE_REVISION+':litellm/'+path],cwd=root,env=os.environ|{'GIT_NO_LAZY_FETCH':'1'},stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:test.skipTest('Exact cached native Git blob unavailable; no fetch allowed')


class ProfileTests(unittest.TestCase):
    def test_real_mounted_and_installed_bytes_reject_foreign_project_routes_and_mutations(self):
        import yaml
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);package=root/'litellm';package.mkdir();(package/'__init__.py').write_text("raise AssertionError('must not import')")
            manifest=M.native_sdk.load_manifest()
            for path in {p.removeprefix('litellm/'):v for p,v in manifest['native_export_sha256'].items()}|M.NATIVE:
                target=package/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(native_blob(self,path))
            config=yaml.safe_load((Path(__file__).with_name('litellm_config.yaml')).read_bytes())
            config_path=root/'config.yaml';config_path.write_text(yaml.safe_dump(config),encoding='utf8')
            worker=root/'proof';worker.mkdir()
            (worker/'prove_pricing_catalog.py').write_bytes(Path(M.__file__).read_bytes())
            repo=Path(__file__).resolve().parents[2]
            for name in M.HELPERS:
                path=('deploy/litellm-patches/positive-floor-v1.105.1/' if name in ('native_floor_identity.py','manifest.json') else 'scripts/goal584-budget-proof/')+name
                raw = subprocess.check_output(['git','-c','gc.auto=0','show',':'+path],cwd=repo,env=os.environ|{'GIT_NO_LAZY_FETCH':'1'})
                self.assertEqual(hashlib.sha256(raw).hexdigest(), M.HELPERS[name])
                (worker/name).write_bytes(raw)
            project='goal584-pricing-'+'a'*12
            env={'PROOF_PRICING_PROJECT':project,'PROOF_SOURCE_COMMIT':'9'*40,'HOSTNAME':'1'*12,
                'LITELLM_MODEL_COST_MAP_URL':M.CATALOG,'LITELLM_LOCAL_MODEL_COST_MAP':'false','DATABASE_URL':'postgresql://goal584:synthetic-private@postgres:5432/goal584_pricing'}
            containers={s:{'id':str(i)*64,'number':'1','image_ref':M.native_sdk.image_ref() if s=='proxy' else M.IMAGES[s],
                'image_id':'sha256:'+str(i)*64,'network':project+'_proof','health':'healthy'} for i,s in enumerate(('proxy','postgres','redis','provider'),1)}
            with patch.object(M,'PRIVATE',root),patch.object(M,'CONFIG',config_path),patch.object(M,'version',return_value='1.105.1'), \
                    patch.object(M,'__file__',str(worker/'prove_pricing_catalog.py')),patch.object(M.native_sdk,'__file__',str(worker/'native_floor_identity.py')), \
                    patch.object(M.importlib.util,'find_spec',return_value=types.SimpleNamespace(origin=str(package/'__init__.py'))):
                attest={'schema':1,'proof':M.PROOF,'project':project,'source_commit':'9'*40,'containers':containers,'proxy_command':M.COMMAND,
                    'config_sha256':hashlib.sha256(config_path.read_bytes()).hexdigest(),'files_sha256':M.source_files(),
                    'provider_sha256':M.PROVIDER_SHA,'native_artifact':M.native_sdk.identity()}
                args=types.SimpleNamespace(project=project)
                M.profile(args,attest,config,env)
                for change in ('project','route','credential_url','extra_service','corpus','source_hash'):
                    a,c,e=copy.deepcopy(attest),copy.deepcopy(config),dict(env)
                    if change=='project':e['PROOF_PRICING_PROJECT']='existing-webui'
                    elif change=='route':c['model_list'][0]['litellm_params']['api_base']='https://paid.example.invalid/v1'
                    elif change=='credential_url':e['LITELLM_MODEL_COST_MAP_URL']='http://secret@provider:8000/__proof/catalog'
                    elif change=='extra_service':a['containers']['webui']=a['containers']['proxy']
                    elif change=='corpus':(package/'model_prices_and_context_window_backup.json').write_text('{}')
                    elif change=='source_hash':a['files_sha256']['prove_native_budgets.py']='0'*64
                    with self.subTest(change=change),self.assertRaises(M.ProofError):M.profile(args,a,c,e)
                    if change=='corpus':(package/'model_prices_and_context_window_backup.json').write_bytes(native_blob(self,'model_prices_and_context_window_backup.json'))


class NativeSourceTests(unittest.IsolatedAsyncioTestCase):
    def test_actual_catalog_routes_are_callable_but_intentionally_hidden_from_openapi(self):
        tree = ast.parse(native_blob(self,'proxy/proxy_server.py'))
        expected = {(M.SOURCE,'get'),(M.STATUS,'get'),(M.SCHEDULE,'post'),(M.SCHEDULE,'delete'),(M.RELOAD,'post')}
        found = set()
        for node in tree.body:
            for decorator in getattr(node,'decorator_list',[]):
                if not isinstance(decorator,ast.Call) or not isinstance(decorator.func,ast.Attribute) or not decorator.args:
                    continue
                path = decorator.args[0]
                if not isinstance(path,ast.Constant) or (path.value,decorator.func.attr) not in expected:
                    continue
                hidden = next((item.value for item in decorator.keywords if item.arg=='include_in_schema'),None)
                self.assertIsInstance(hidden,ast.Constant)
                self.assertIs(hidden.value,False)
                found.add((path.value,decorator.func.attr))
        self.assertEqual(found,expected)

    def owner(self):
        from dataclasses import dataclass
        from typing import Final
        src=native_blob(self,'proxy/common_utils/periodic_reload_schedule.py')
        self.assertEqual(hashlib.sha256(src).hexdigest(),M.NATIVE['proxy/common_utils/periodic_reload_schedule.py'])
        tree=ast.parse(src);nodes=[n for n in tree.body if getattr(n,'name',None) in ('ReloadSchedule','pod_reload_is_due','next_run_at','reload_schedule_status')]
        ns={'dataclass':dataclass,'datetime':datetime,'timedelta':timedelta,'ReloadScheduleStatus':dict,'verbose_proxy_logger':logging.getLogger('native-schedule')}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'native-schedule.py','exec'),ns)
        return ns

    def test_actual_native_first_poll_due_and_hour_recurrence_edges(self):
        n=self.owner();Schedule=n['ReloadSchedule'];now=datetime.now(timezone.utc)
        args={'pod_applied_revision':0,'pod_data_loaded_at':now,'current_time':now,'description':'fixture'}
        self.assertTrue(n['pod_reload_is_due'](schedule=Schedule(interval_hours=1),**args))
        self.assertFalse(n['pod_reload_is_due'](schedule=Schedule(interval_hours=1,last_run_at=now),**args))
        self.assertTrue(n['pod_reload_is_due'](schedule=Schedule(interval_hours=1,last_run_at=now),**(args|{'current_time':now+timedelta(hours=1)})))
        self.assertTrue(n['pod_reload_is_due'](schedule=Schedule(reload_revision=1),**args))

    def test_actual_native_adoption_installs_catalog_before_registration_replay(self):
        from typing import Final
        src=native_blob(self,'litellm_core_utils/get_model_cost_map.py')
        self.assertEqual(hashlib.sha256(src).hexdigest(),M.NATIVE['litellm_core_utils/get_model_cost_map.py'])
        node=next(n for n in ast.parse(src).body if getattr(n,'name',None)=='adopt_model_cost_map')
        module=types.ModuleType('litellm');events=[];new={'goal584-fake-a':{'input_cost_per_token':.02}}
        module.model_cost={'old':{}}
        def marker(name):
            def call(*args,**kwargs):
                self.assertIs(module.model_cost,new);events.append(name)
            return call
        module.utils=types.SimpleNamespace(_invalidate_model_cost_lowercase_map=marker('invalidate'),reapply_runtime_model_cost_registrations=marker('reapply'))
        module.add_known_models=marker('known')
        ns={'Final':Final}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'native-adoption.py','exec'),ns)
        with patch.dict(sys.modules,{'litellm':module}):self.assertEqual(ns['adopt_model_cost_map'](new),1)
        self.assertEqual(events,['invalidate','known','reapply'])

    async def test_actual_admin_guard_and_valid_adoption_precedes_status_write_failure(self):
        src=native_blob(self,'proxy/proxy_server.py');self.assertEqual(hashlib.sha256(src).hexdigest(),'227a704e5c9e7bdd0569f80d520aa670bde32397d0983e165089c63dcb775b4e')
        tree=ast.parse(src);names=('reload_model_cost_map','schedule_model_cost_map_reload','cancel_model_cost_map_reload')
        nodes=[n for n in tree.body if getattr(n,'name',None) in names]
        for n in nodes:
            n.decorator_list=[]
            for a in n.args.args:a.annotation=None;a.type_comment=None
            n.args.defaults=[];n.returns=None
        from fastapi import HTTPException
        class Unavailable:
            reason='Controlled synthetic invalid JSON'
        events=[]
        result=types.SimpleNamespace(model_cost_map={'synthetic':{}},source_revision='fixture')
        async def stamp(*args):events.append('status');raise RuntimeError('private DB detail must not escape safe packet')
        namespace={'UserAPIKeyAuth':object,'LitellmUserRoles':types.SimpleNamespace(PROXY_ADMIN='admin'),
            'HTTPException':HTTPException,'prisma_client':object(),'litellm':types.SimpleNamespace(model_cost_map_url=M.CATALOG),
            'proxy_config':types.SimpleNamespace(),'Final':object,'MODEL_COST_MAP_RELOAD_PARAM_NAME':'native',
            'utc_now':lambda:datetime.now(timezone.utc),'_swap_in_model_cost_map':lambda value:events.append('adopt') or len(value),
            'record_manual_reload':stamp,'write_reload_interval':AsyncMock(),'clear_reload_interval':AsyncMock(),
            'verbose_proxy_logger':types.SimpleNamespace(info=lambda *a:None,exception=lambda *a:None)}
        module=types.ModuleType('litellm.litellm_core_utils.get_model_cost_map')
        module.ModelCostMapReloadUnavailable=Unavailable;module.refetch_model_cost_map=AsyncMock(return_value=result)
        module.get_model_cost_map_provenance=lambda:{'source_revision':'fixture','etag':'fixture'}
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'native-proxy.py','exec'),namespace)
        for name in names:
            with self.subTest(route=name),self.assertRaises(HTTPException) as denied:
                if name=='schedule_model_cost_map_reload':await namespace[name](1,types.SimpleNamespace(user_role='user'))
                else:await namespace[name](types.SimpleNamespace(user_role='user'))
            self.assertEqual(denied.exception.status_code,403)
        with patch.dict(sys.modules,{'litellm.litellm_core_utils.get_model_cost_map':module}):
            with self.assertRaises(HTTPException) as failed:await namespace['reload_model_cost_map'](types.SimpleNamespace(user_role='admin'))
        self.assertEqual(failed.exception.status_code,500)
        self.assertEqual(events,['adopt','status'])
        self.assertTrue(hasattr(namespace['proxy_config'],'model_cost_map_loaded_at'))
        events.clear();module.refetch_model_cost_map=AsyncMock(return_value=Unavailable())
        with patch.dict(sys.modules,{'litellm.litellm_core_utils.get_model_cost_map':module}):
            with self.assertRaises(HTTPException) as rejected:await namespace['reload_model_cost_map'](types.SimpleNamespace(user_role='admin'))
        self.assertEqual(rejected.exception.status_code,502)
        self.assertEqual(events,[])


if __name__=='__main__':unittest.main()
