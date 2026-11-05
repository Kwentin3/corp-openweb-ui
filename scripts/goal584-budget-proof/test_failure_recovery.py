"""Actual finite coordinator + pinned native failure methods; external IO only."""
from __future__ import annotations

import ast
import asyncio
from contextlib import ExitStack, redirect_stdout
import copy
import enum
from datetime import datetime, timezone
from decimal import Decimal
from email.message import Message
import hashlib
import importlib.util
import io
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
from types import ModuleType, SimpleNamespace
from typing import Final, cast
import unittest
from unittest.mock import patch
from uuid import uuid4
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import prove_failure_recovery as M
import prove_gateway_auth as private_owner

ROOT=Path(__file__).resolve().parents[2]
CACHE=Path(os.environ.get('GOAL584_LITELLM_SOURCE_ROOT',ROOT/'local/goal584/litellm/upstream'))
SECRET='gw-synthetic-proof-secret-never-exported'
# Observed Native56 proxy audit data; the native estimator algorithm is tested below.
PROXY_FAILURE_USAGE={'prompt_tokens':88,'completion_tokens':0,'total_tokens':88}


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value);return value


PROVENANCE=module('failure_test_provenance',ROOT/'deploy/openwebui-budgets/provenance.py')
ASSIGNMENT=module('failure_test_assignment',ROOT/'deploy/openwebui-budgets/assignment.py')


class World:
    """HTTP/Redis/capture/provider IO double, not a substitute coordinator."""
    def __init__(self,mutation=None):
        self.mutation=mutation;self.control={'prompt_tokens':10,'completion_tokens':5,'delay_ms':0,
            'tool_round':False,'admin_mode':True,'title_mode':False}
        self.original=copy.deepcopy(self.control);self.requests=[];self.captures=[];self.http=[]
        self.users={};self.keys={};self.rows={};self.live={};self.release=threading.Event();self.offset=0
        self.failed_uid=None;self.failed_terminal=False;self.restore_failure=False
        self.audit_reads=0
        self.money_lag_reads=0
        self.uid=str(uuid4());self.users[self.uid]={'user_id':self.uid,'user_role':'internal_user','models':[M.MODEL],
            'spend':1,'max_budget':20,'budget_duration':'30d','budget_reset_at':'2026-12-03T00:00:00Z','teams':[]}
        self.rows[self.uid]=[{'request_id':'existing-native-row','user':self.uid,'spend':1,'status':'success','metadata':{'private_history':'keep'}}]
        self.native=M.NativeProof('http://127.0.0.1:4000','operator-private-key',.12,{})
        self.native.request=self.request_with_headers

    def request_with_headers(self,*args,**kwargs):
        status,payload,values=self.http_request(*args,**kwargs)
        headers=Message()
        for key,value in values.items():headers.add_header(key,value)
        return status,payload,headers

    def counter(self,uid,key_hash):
        value=self.live.get(uid,0)
        if self.failed_terminal and uid==self.failed_uid:
            if self.mutation=='orphan_hold':value=.8
            if self.mutation=='double_refund':value=-.8
            if self.mutation=='missing_counter':value=None
        result={'key':value,'user':value}
        if uid==self.failed_uid and not self.failed_terminal:self.release.set()
        return result

    def provider(self,method='GET',path=None,body=None):
        if method=='POST':
            assert path=='/__proof/control'
            if self.restore_failure and body.get('admin_mode') is True:raise OSError('private '+SECRET)
            for key,value in body.items():
                if value is None:self.control.pop(key,None)
                else:self.control[key]=value
        rows=copy.deepcopy(self.requests)
        if self.mutation=='old_provider_changed' and len(rows)==3:rows[0]['extra_mutation']='changed'
        if self.mutation=='wrong_failure_body' and len(rows)>=2:rows[1]['body']['messages'][0]['content']='changed'
        if self.mutation=='extra_dispatch' and len(rows)>=2:rows.append({**copy.deepcopy(rows[1]),'id':'chatcmpl-goal584-'+uuid4().hex})
        if self.mutation=='nonterminal_failure' and self.failed_terminal:
            rows[1]['lifecycle'].update(terminal=False,stage='headers_sent',outcome=None)
        return {'synthetic':True,'requests':rows,'control':copy.deepcopy(self.control)}

    def http_request(self,method,path,query=None,body=None,**kwargs):
        self.http.append((method,path,copy.deepcopy(body)))
        if path=='/user/list':
            users=[{'user_id':uid} for uid in sorted(self.users)]
            return 200,{'users':users,'page':1,'page_size':100,'total_pages':1,'total':len(users)},{}
        if path=='/user/new':
            uid=body['user_id'];self.users[uid]={**copy.deepcopy(body),'spend':0,'budget_reset_at':'2026-12-03T00:00:00Z'}
            self.rows[uid]=[];return 200,{},{}
        if path=='/key/generate':
            uid=body['user_id'];token='sk-synthetic-native-key-'+uuid4().hex;key_hash=hashlib.sha256(token.encode()).hexdigest()
            self.keys[uid]={'token':key_hash,**copy.deepcopy(body),'spend':0,'total_spend':0,'blocked':False,'team_id':None,
                'budget_reset_at':'2026-12-03T00:00:00Z','model_max_budget':{}}
            return 200,{'key':token},{}
        if path=='/user/info':
            uid=query['user_id'];user=copy.deepcopy(self.users[uid]);keys=[] if uid not in self.keys else [copy.deepcopy(self.keys[uid])]
            for embedded in keys:embedded['team_alias']='None'
            if uid!=self.uid:
                if self.mutation=='foreign_user_dto':user['user_id']=str(uuid4())
                if self.mutation=='missing_user_dto_id':user.pop('user_id')
                if self.mutation=='foreign_embedded_token':keys[0]['token']='c'*64
                if self.mutation=='missing_embedded_token':keys[0].pop('token')
                if self.mutation=='foreign_embedded_user':keys[0]['user_id']=str(uuid4())
                if self.mutation=='foreign_embedded_model':keys[0]['models']=['goal584-b']
                if self.mutation=='foreign_embedded_alias':keys[0]['key_alias']='foreign-alias'
                if self.mutation=='negative_embedded_money':keys[0].update(spend=-100,total_spend=-100)
                if self.mutation=='missing_embedded_money':keys[0].pop('total_spend')
            if self.mutation=='old_row_changed' and len(self.requests)==3 and uid==self.uid:self.rows[uid][0]['metadata']['private_history']='changed'
            if self.mutation=='policy_changed' and uid==self.failed_uid and self.failed_terminal:user['max_budget']=50
            if self.mutation=='extra_key' and uid==self.failed_uid and self.failed_terminal:keys.append({**copy.deepcopy(keys[0]),'token':'b'*64})
            if self.mutation=='unexpected_user_field' and uid==self.failed_uid and self.failed_terminal:user['unexpected_owner_field']='changed'
            if uid==self.failed_uid and len(self.requests)==3:
                self.money_lag_reads+=1
                if self.mutation=='embedded_money_lag' and self.money_lag_reads==1:keys[0].update(spend=0,total_spend=0)
                if self.mutation=='embedded_spend_surplus':keys[0]['spend']=.4
                if self.mutation=='embedded_lifetime_surplus':keys[0]['total_spend']=.4
                if self.mutation=='embedded_negative_after_success':keys[0].update(spend=-100,total_spend=-100)
            return 200,{'user_id':uid,'user_info':user,'keys':keys},{}
        if path=='/key/info':
            key=query['key'];key_hash=hashlib.sha256(key.encode()).hexdigest() if key.startswith('sk-') else key
            value=next(v for v in self.keys.values() if v['token']==key_hash)
            value=copy.deepcopy(value)
            value.pop('token')  # Native info_key_fn removes it before the response.
            value['status']='active'
            if self.mutation=='foreign_key_info_token':value['token']='b'*64
            if self.mutation=='unexpected_key_field' and value['user_id']==self.failed_uid and self.failed_terminal:value['unexpected_owner_field']='changed'
            if self.mutation=='reset_changed' and value['user_id']==self.failed_uid and self.failed_terminal:value['budget_reset_at']='2027-01-01T00:00:00Z'
            payload={'key':key,'info':value}
            if self.mutation=='foreign_key_echo':payload['key']='b'*64
            if self.mutation=='missing_key_echo':payload.pop('key')
            return 200,payload,{}
        if path=='/spend/logs/v2':
            uid=query['user_id'];rows=copy.deepcopy(self.rows[uid])
            if uid==self.failed_uid and self.failed_terminal:
                self.audit_reads+=1
                if self.mutation=='audit_delay' and self.audit_reads==1:rows=[]
                if self.mutation in ('audit_deadline_missing','audit_deadline_ready'):
                    self.offset=16
                    if self.mutation=='audit_deadline_missing':rows=[]
            if self.mutation=='calibration_row_missing' and len(self.requests)==3 and uid!=self.failed_uid and uid!=self.uid:rows=[]
            return 200,{'data':rows,'total_pages':1},{}
        assert method=='POST' and path=='/v1/chat/completions'
        return self.completion(body)

    def completion(self,body):
        claims=PROVENANCE.decode_call(body['litellm_metadata']['owui_budget_provenance'],SECRET,
            user_id=kwargs_uid(body),model=M.MODEL)
        uid=claims['sub'];key=self.keys[uid]
        scope={'schema':1,'user_id':uid,'model':M.MODEL,'category':'personal','call_id':claims['jti'],
            **{k:claims[k] for k in ('chat_id','answer_id','root_chat_id','root_answer_id')}}
        semantic={k:v for k,v in body.items() if k!='litellm_metadata'}
        record={'_observation_id':str(uuid4()),'user_id':uid,'body':semantic,'body_after_auth':copy.deepcopy(semantic),
            'verified_cost_scope':scope,'provenance_removed_after':True,'native_estimated_max_cost_usd':.8}
        self.captures.append(record)
        if self.mutation=='changed_capture_context':record['body_after_auth']={**semantic,'max_tokens':6}
        failure=self.control.get('response_status')==500
        identifier='chatcmpl-goal584-'+uuid4().hex;created=1793664000
        result={'id':identifier,'object':'chat.completion','created':created,'model':'goal584-fake-a',
            'choices':[{'index':0,'message':{'role':'assistant','content':'Proof'},'finish_reason':'stop'}],'usage':M.USAGE}
        physical={'id':identifier,'created':created,'body':copy.deepcopy(M.PHYSICAL),'usage':None if failure else M.USAGE,
            'lifecycle':{'started':True,'stage':'before_headers_delay' if failure else 'completed','started_monotonic':10.0,
                'headers_sent':not failure,'chunks_sent':0,'usage_sent':not failure,'terminal':not failure,
                'outcome':None if failure else 'completed','response_status':500 if failure else 200,
                'delay_ms':3000 if failure else 0,'after_first_chunk_delay_ms':0}}
        if not failure:physical.update(response=result);physical['lifecycle']['terminal_monotonic']=10.1
        self.requests.append(physical)
        self.live[uid]=.8
        if failure:
            self.failed_uid=uid
            if not self.release.wait(timeout=2):raise AssertionError('Hold observer never read native counters')
            physical['lifecycle'].update(stage='controlled_error',headers_sent=True,terminal=True,outcome='controlled_error',terminal_monotonic=10.1)
            self.live[uid]=0;self.failed_terminal=True
            row=self.row(uid,scope,'native-failure-'+uuid4().hex,False)
            if self.mutation=='paid_failure':row['spend']=.1
            if self.mutation=='usage_failure':row['prompt_tokens']=1
            if self.mutation=='foreign_scope':row['metadata']['spend_logs_metadata']['owui_budget']['user_id']=str(uuid4())
            if self.mutation=='foreign_key':row['api_key']='f'*64
            if self.mutation=='unknown_error':row['metadata']['error_information']['error_class']='BudgetExceededError'
            if self.mutation!='missing_audit':self.rows[uid].append(row)
            if self.mutation=='double_event':self.rows[uid].append({**copy.deepcopy(row),'request_id':'different-native-failure'})
            self.restore_failure=self.mutation in ('primary_and_restore_failure','restore_only_failure')
            if self.mutation=='primary_and_restore_failure':self.rows[uid][0]['spend']=.1
            return (422 if self.mutation=='wrong_native_error' else 500),{'error':{'type':'internal_server_error','message':'private '+SECRET}},{}
        self.live[uid]=.2;self.users[uid]['spend']=.2;key['spend']=key['total_spend']=.2
        if self.failed_terminal:
            if self.mutation=='late_recovery':self.offset=20
            if self.mutation=='double_charge':self.users[uid]['spend']=key['spend']=key['total_spend']=.4
            if self.mutation=='old_failure_row_changed':self.rows[uid][0]['extra_mutation']='changed'
        self.rows[uid].append(self.row(uid,scope,identifier,True))
        return 200,copy.deepcopy(result),{'x-litellm-response-cost':'.2'}

    def row(self,uid,scope,identifier,success):
        meta={'spend_logs_metadata':{'owui_budget':copy.deepcopy(scope)}}
        if not success:meta.update(status='failure',error_information={'error_class':'InternalServerError','error_code':'proof_provider_500'})
        else:
            fields=ast.literal_eval(next(node.value for node in ast.parse((ROOT/'deploy/openwebui-budgets/pricing_snapshot.py').read_bytes()).body
                if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='RATE_FIELDS' for target in node.targets)))
            rates=dict.fromkeys(fields,0.0);rates.update(input_cost_per_token=.01,output_cost_per_token=.02)
            meta['spend_logs_metadata']['owui_billed_token_rates']={'schema':1,'availability':'available',
                'observed_at_utc':'2026-11-04T00:00:00Z','rates':rates}
            if self.mutation=='missing_frozen_rates':meta['spend_logs_metadata'].pop('owui_billed_token_rates')
        return {'request_id':identifier,'user':uid,'api_key':self.keys[uid]['token'],'model_group':M.MODEL,
            'model_id':'goal584-deployment-a','session_id':scope['chat_id'],'status':'success' if success else 'failure',
            'spend':.2 if success else 0,**(M.USAGE if success else PROXY_FAILURE_USAGE),'metadata':meta}


def kwargs_uid(body):
    import jwt
    return jwt.decode(body['litellm_metadata']['owui_budget_provenance'],options={'verify_signature':False})['sub']


class CoordinatorTests(unittest.TestCase):
    def replay(self,mutation=None,*,failure_usage_estimator=...):
        world=World(mutation)
        world.estimator_calls=[]
        def estimate(**kwargs):
            self.assertEqual(kwargs,{'request_input':world.requests[1]['body']['messages'],'system_input':None})
            self.assertEqual(kwargs['request_input'],M.PHYSICAL['messages'])
            world.estimator_calls.append(copy.deepcopy(kwargs))
            return SimpleNamespace(**PROXY_FAILURE_USAGE) if failure_usage_estimator is ... else failure_usage_estimator(**kwargs)
        with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
            path=Path(directory)/'failure.private.json';runner=M.Recovery(world.native,world.counter,path,
                failure_usage_estimator=None if failure_usage_estimator is None else estimate)
            stack.enter_context(patch.dict(sys.modules,{'provenance':PROVENANCE,'employee_budget_assignment':ASSIGNMENT}))
            rates=ast.literal_eval(next(node.value for node in ast.parse((ROOT/'deploy/openwebui-budgets/pricing_snapshot.py').read_bytes()).body
                if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='RATE_FIELDS' for target in node.targets)))
            stack.enter_context(patch.dict(sys.modules,{'pricing_snapshot':SimpleNamespace(RATE_FIELDS=rates)}))
            stack.enter_context(patch.dict(os.environ,{'OWUI_BUDGET_GATEWAY_SECRET':SECRET}))
            stack.enter_context(patch.object(M.overlap,'provider',world.provider))
            stack.enter_context(patch.object(M.overlap,'capture',lambda:copy.deepcopy(world.captures)))
            real_write=M.overlap.write_private
            def write(private_path,value):
                if mutation=='failure_private_write' and 'primary_failure' in value:raise OSError('private '+SECRET)
                real_write(private_path,value)
                if mutation=='before_recovery_deadline' and value['stage']=='recovery':world.offset=16
                if mutation=='body_persist_deadline' and value['stage']=='recovery' and 'recovery' in value['attempts']:world.offset=16
                if mutation=='failure_response_persist_deadline' and 'response' in value['attempts'].get('failure',{}) and len(world.requests)==2:
                    world.offset=16
            stack.enter_context(patch.object(M.overlap,'write_private',write))
            if os.name=='nt':
                stack.enter_context(patch.object(private_owner,'private_parent',lambda p:p.parent.mkdir(exist_ok=True)))
                stack.enter_context(patch.object(private_owner.stat,'S_IMODE',return_value=0o600))
                # Windows fixture IO avoids concurrent destination rename failures;
                # retain the real bounded writer and all save/clock hooks above.
                stack.enter_context(patch.object(M.overlap,'native_write_private',
                    lambda p,value:p.write_text(json.dumps(value,allow_nan=False)+'\n',encoding='utf8')))
            real_clock=time.monotonic
            stack.enter_context(patch.object(M.time,'monotonic',lambda:real_clock()+world.offset))
            result=None;error=None
            try:result=runner.execute()
            except Exception as value:error=value
            self.assertTrue(path.exists())
            saved=json.loads(path.read_bytes());self.assertEqual(saved['proof'],M.PROOF)
            if mutation not in ('primary_and_restore_failure','restore_only_failure'):self.assertEqual(world.control,world.original)
            return world,runner,result,error,saved

    def test_actual_execute_three_dispatches_uses_native_readers_preserves_all_inputs_and_restores_controls(self):
        world,runner,result,error,saved=self.replay()
        self.assertIsNone(error);self.assertTrue(result['passed']);self.assertEqual(result['physical_calls'],3)
        self.assertEqual(result['hold'],{'provider_id':world.requests[1]['id'],'reserve_usd':'0.8','client_unfinished':True})
        self.assertEqual(result['released']['native_spend_usd'],'0');self.assertEqual(result['final_spend_usd'],'0.20')
        self.assertEqual(len(saved['attempts']),3);self.assertEqual(len(world.requests),3)
        self.assertNotEqual(world.rows[world.failed_uid][0]['request_id'],world.requests[1]['id'])
        self.assertEqual(world.users[world.failed_uid]['spend'],.2);self.assertEqual(world.keys[world.failed_uid]['total_spend'],.2)
        self.assertEqual(world.rows[world.uid][0]['metadata'],{'private_history':'keep'})
        for row in world.requests:self.assertEqual(row['body'],M.PHYSICAL)
        self.assertTrue(world.estimator_calls)
        self.assertEqual({key:world.rows[world.failed_uid][0][key] for key in M.USAGE},PROXY_FAILURE_USAGE)
        calls=[body for method,path,body in world.http if path=='/v1/chat/completions']
        self.assertEqual(len(calls),3)
        for body in calls:self.assertEqual({k:v for k,v in body.items() if k!='litellm_metadata'},M.SEMANTIC)
        allowed_posts={'/user/new','/key/generate','/v1/chat/completions'}
        self.assertTrue(all(path in allowed_posts for method,path,body in world.http if method=='POST'))
        self.assertEqual(result['restoration'],{'provider_controls_restored':True,'financial_history_retained':True})
        public=json.dumps(M.overlap.safe(result),allow_nan=False)
        self.assertNotIn(SECRET,public);self.assertNotIn('private_history',public)
        with self.assertRaisesRegex(M.ProofError,'failure_repeat_dispatch'):runner.call('failure','recovery')

    def test_actual_execute_rejects_paid_orphan_double_duplicate_missing_foreign_and_old_record_mutations(self):
        cases={'paid_failure':'failure_audit_shape','usage_failure':'failure_audit_shape','unknown_error':'failure_audit_shape',
            'foreign_scope':'failure_unknown_or_duplicate_row_scope','foreign_key':'failure_row_identity',
            'orphan_hold':'failure_orphan_hold','double_refund':'failure_negative_live_counter','missing_counter':'failure_missing_live_counter',
            'double_event':'failure_extra_or_duplicate_row','missing_audit':'Timed out',
            'extra_dispatch':'failure_extra_provider_dispatch','wrong_failure_body':'failure_provider_context',
            'nonterminal_failure':'failure_provider_terminal','wrong_native_error':'failure_native500_response',
            'double_charge':'failure_counter_surplus','old_failure_row_changed':'failure_old_row_changed',
            'old_row_changed':'failure_prior_financial_state_changed','old_provider_changed':'failure_old_provider_changed',
            'calibration_row_missing':'failure_old_row_changed','policy_changed':'failure_protected_policy_changed',
            'extra_key':'failure_budget_user_binding','unexpected_user_field':'failure_protected_policy_changed',
            'unexpected_key_field':'failure_protected_policy_changed','reset_changed':'failure_protected_policy_changed',
            'missing_frozen_rates':'Native pricing snapshot schema differs','changed_capture_context':'failure_capture_context',
            'late_recovery':'failure_recovery_waited_for_ttl'}
        for mutation,code in cases.items():
            with self.subTest(mutation=mutation):
                world,runner,result,error,saved=self.replay(mutation)
                self.assertIsNone(result);self.assertIsInstance(error,M.ProofError);self.assertIn(code,str(error))
                self.assertLessEqual(len(world.requests),3)
                self.assertTrue(saved['observations'])

    def test_primary_financial_failure_survives_restore_io_failure(self):
        world,runner,result,error,saved=self.replay('primary_and_restore_failure')
        self.assertIsNone(result);self.assertEqual(str(error),'failure_audit_shape')
        self.assertIs(runner.receipt['restoration']['provider_controls_restored'],False)
        self.assertEqual(runner.receipt['failure']['exception_class'],'ProofError')
        self.assertEqual(saved['primary_failure']['message'],'failure_audit_shape')

    def test_zero_live_counters_allow_transient_audit_deficit_inside_bound(self):
        world,runner,result,error,saved=self.replay('audit_delay')
        self.assertIsNone(error);self.assertTrue(result['passed']);self.assertGreaterEqual(world.audit_reads,2)
        self.assertEqual(len(world.requests),3);self.assertLess(result['recovery_seconds'],15)
        self.assertEqual(result['released']['row_count'],1)

    def test_created_dtos_are_bound_before_freezing_baseline_or_dispatch(self):
        cases={'foreign_user_dto':'failure_user_dto_identity','missing_user_dto_id':'failure_user_dto_identity',
            'foreign_key_info_token':'failure_key_dto_token_field','foreign_key_echo':'failure_key_dto_echo',
            'missing_key_echo':'failure_key_dto_echo','foreign_embedded_token':'failure_embedded_key_hash',
            'missing_embedded_token':'failure_embedded_key_hash','foreign_embedded_user':'failure_budget_key_binding',
            'foreign_embedded_model':'failure_budget_key_binding','foreign_embedded_alias':'failure_budget_key_binding',
            'negative_embedded_money':'failure_created_money','missing_embedded_money':'Native amount is missing or invalid'}
        for mutation,code in cases.items():
            with self.subTest(mutation=mutation):
                world,runner,result,error,saved=self.replay(mutation)
                self.assertIsNone(result);self.assertIsInstance(error,M.ProofError);self.assertEqual(str(error),code)
                self.assertEqual(len(world.requests),0)
                self.assertNotIn('baseline',saved['payers']['calibration'])

    def test_embedded_money_requires_settlement_and_rejects_negative_or_surplus(self):
        world,runner,result,error,saved=self.replay('embedded_money_lag')
        self.assertIsNone(error);self.assertTrue(result['passed']);self.assertGreaterEqual(world.money_lag_reads,2)
        for mutation,code in (('embedded_spend_surplus','failure_counter_surplus'),
                              ('embedded_lifetime_surplus','failure_lifetime_surplus'),
                              ('embedded_negative_after_success','failure_counter_surplus')):
            with self.subTest(mutation=mutation):
                world,runner,result,error,saved=self.replay(mutation)
                self.assertIsNone(result);self.assertEqual(str(error),code)

    def test_failure_http_return_timestamp_precedes_private_persistence_deadline(self):
        world,runner,result,error,saved=self.replay('failure_response_persist_deadline')
        self.assertIsNone(result);self.assertEqual(str(error),'failure_release_deadline')
        self.assertEqual(len(world.requests),2)
        self.assertNotIn('recovery',saved['attempts'])
        observed=saved['attempts']['failure']['response_returned_monotonic']
        self.assertGreater(M.time.monotonic()+world.offset-observed,15)

    def test_native_failure_usage_requires_valid_estimator_exact_row_and_unchanged_context_before_recovery(self):
        cases=(('missing_owner',None,'failure_native_usage_owner'),
            ('none',lambda **kwargs:None,'failure_native_usage_estimate'),
            ('missing',lambda **kwargs:SimpleNamespace(prompt_tokens=88,completion_tokens=0),'failure_native_usage_estimate'),
            ('float',lambda **kwargs:SimpleNamespace(prompt_tokens=88.0,completion_tokens=0,total_tokens=88),'failure_native_usage_estimate'),
            ('bool',lambda **kwargs:SimpleNamespace(prompt_tokens=True,completion_tokens=0,total_tokens=1),'failure_native_usage_estimate'),
            ('zero',lambda **kwargs:SimpleNamespace(prompt_tokens=0,completion_tokens=0,total_tokens=0),'failure_native_usage_estimate'),
            ('completion',lambda **kwargs:SimpleNamespace(prompt_tokens=88,completion_tokens=1,total_tokens=89),'failure_native_usage_estimate'),
            ('badtotal',lambda **kwargs:SimpleNamespace(prompt_tokens=88,completion_tokens=0,total_tokens=89),'failure_native_usage_estimate'),
            ('foreign_positive',lambda **kwargs:SimpleNamespace(prompt_tokens=87,completion_tokens=0,total_tokens=87),'failure_audit_shape'))
        for label,estimator,code in cases:
            with self.subTest(case=label):
                world,runner,result,error,saved=self.replay(failure_usage_estimator=estimator)
                self.assertIsNone(result);self.assertIsInstance(error,M.ProofError)
                self.assertEqual(str(error),code);self.assertEqual(len(world.requests),2)
                self.assertNotIn('recovery',saved['attempts'])
        world,runner,result,error,saved=self.replay('wrong_failure_body')
        self.assertIsNone(result);self.assertEqual(str(error),'failure_provider_context')
        self.assertEqual(len(world.requests),2);self.assertEqual(world.estimator_calls,[])
        self.assertNotIn('recovery',saved['attempts'])

    def test_deadline_rejects_missing_late_ready_audit_and_delay_after_read_before_second_dispatch(self):
        for mutation in ('audit_deadline_missing','audit_deadline_ready','before_recovery_deadline','body_persist_deadline'):
            with self.subTest(mutation=mutation):
                world,runner,result,error,saved=self.replay(mutation)
                self.assertIsNone(result);self.assertIsInstance(error,M.ProofError)
                self.assertEqual(str(error),'failure_release_deadline')
                self.assertEqual(len(world.requests),2)
                self.assertEqual(sum(path=='/v1/chat/completions' for method,path,body in world.http),2)
                if mutation!='body_persist_deadline':self.assertNotIn('recovery',saved['attempts'])
                else:self.assertNotIn('response',saved['attempts']['recovery'])

    def test_safe_primary_coordinate_points_to_actual_failed_guard_and_private_writer_cannot_replace_it(self):
        world,runner,result,error,saved=self.replay('paid_failure')
        diagnostic=runner.receipt['failure']
        self.assertEqual(set(diagnostic),{'stage','exception_class','source_basename','source_line','audit'})
        self.assertIs(diagnostic['audit']['checks']['spend_zero'],False)
        self.assertEqual(diagnostic['stage'],'failure');self.assertEqual(diagnostic['exception_class'],'ProofError')
        self.assertEqual(diagnostic['source_basename'],'prove_failure_recovery.py')
        guard=next(node for node in ast.walk(ast.parse(Path(M.__file__).read_bytes())) if isinstance(node,ast.Call)
            and isinstance(node.func,ast.Name) and node.func.id=='require'
            and any(isinstance(arg,ast.Constant) and arg.value=='failure_audit_shape' for arg in node.args))
        self.assertLessEqual(guard.lineno,diagnostic['source_line']);self.assertLessEqual(diagnostic['source_line'],guard.end_lineno)
        self.assertEqual(saved['primary_failure']['message'],'failure_audit_shape')
        # Same primary financial violation, followed by a broken private writer.
        original=World.row
        def paid(world,*args,**kwargs):
            row=original(world,*args,**kwargs)
            if row['status']=='failure':row['spend']=.1
            return row
        with patch.object(World,'row',paid):world,runner,result,error,saved=self.replay('failure_private_write')
        self.assertEqual(str(error),'failure_audit_shape');self.assertTrue(runner.receipt['primary_failure_write_failed'])
        self.assertEqual(runner.receipt['failure']['exception_class'],'ProofError')
        self.assertEqual(runner.receipt['failure']['audit'],diagnostic['audit'])

    def test_actual_compound_guard_diagnostic_distinguishes_types_values_and_never_exports_private_fields(self):
        original=World.row
        cases=(
            ('paid',{'spend':.1},{},'spend_zero',('spend',{'type':'float','value':.1})),
            ('usage_missing',{'prompt_tokens':None},{},'prompt_tokens_matches_estimate',('prompt_tokens',{'type':'missing'})),
            ('usage_float',{'prompt_tokens':88.0},{},'prompt_tokens_matches_estimate',('prompt_tokens',{'type':'float','value':88.0})),
            ('usage_bool',{'prompt_tokens':False},{},'prompt_tokens_matches_estimate',('prompt_tokens',{'type':'bool'})),
            ('usage_foreign_positive',{'prompt_tokens':1},{},'prompt_tokens_matches_estimate',('prompt_tokens',{'type':'int','value':1})),
            ('completion_nonzero',{'completion_tokens':1},{},'completion_tokens_matches_estimate',('completion_tokens',{'type':'int','value':1})),
            ('total_foreign_positive',{'total_tokens':1},{},'total_tokens_matches_estimate',('total_tokens',{'type':'int','value':1})),
            ('class',{}, {'error_class':SECRET},'error_class_native',None),
            ('foreign_code',{}, {'error_code':SECRET},'error_code_expected','other'),
            ('http_code',{}, {'error_code':'500'},'error_code_expected','http_500'),
            ('missing_code',{}, {'error_code':None},'error_code_expected','missing'),
        )
        expected_checks={'row_status_failure','metadata_status_failure','spend_zero',
            *(key+'_matches_estimate' for key in M.USAGE),'error_class_native','error_code_expected'}
        for label,fields,info,failed,projection in cases:
            def changed(world,*args,**kwargs):
                row=original(world,*args,**kwargs)
                if row['status']=='failure':
                    row.update(fields);row['metadata']['error_information'].update(info,error_message=SECRET)
                    row['metadata']['raw_private']={'sourceText':SECRET,'key':SECRET,'payer':SECRET,'scope':SECRET}
                    if label in ('usage_missing','missing_code'):
                        (row if label=='usage_missing' else row['metadata']['error_information']).pop(
                            'prompt_tokens' if label=='usage_missing' else 'error_code')
                return row
            with self.subTest(case=label),patch.object(World,'row',changed):
                world,runner,result,error,saved=self.replay()
                self.assertIsNone(result);self.assertIsInstance(error,M.ProofError)
                self.assertEqual(str(error),'failure_audit_shape');self.assertEqual(len(world.requests),2)
                diagnostic=runner.receipt['failure'];audit=diagnostic['audit']
                self.assertEqual(set(audit),{'checks','row_status','metadata_status','spend','usage','usage_expected','error_code_kind'})
                self.assertEqual(audit['usage_expected'],{key:{'type':'int','value':value} for key,value in PROXY_FAILURE_USAGE.items()})
                self.assertEqual(set(audit['checks']),expected_checks)
                self.assertEqual({key for key,value in audit['checks'].items() if value is False},{failed})
                self.assertTrue(all(type(value) is bool for value in audit['checks'].values()))
                self.assertEqual(audit['row_status'],'failure');self.assertEqual(audit['metadata_status'],'failure')
                self.assertEqual(set(audit['usage']),set(M.USAGE))
                if isinstance(projection,tuple):
                    key,value=projection;self.assertEqual(audit['spend'] if key=='spend' else audit['usage'][key],value)
                self.assertEqual(audit['error_code_kind'],projection if isinstance(projection,str) else 'controlled_provider')
                serialized=json.dumps(runner.receipt,allow_nan=False)
                self.assertNotIn(SECRET,serialized)
                for private in ('raw_private','sourceText','error_message','owui_budget','api_key','session_id'):
                    self.assertNotIn(private,json.dumps(diagnostic))
                self.assertEqual(saved['primary_failure']['message'],'failure_audit_shape')

    def test_diagnostic_projection_bounds_malformed_scalars_and_requires_owned_guard_frame(self):
        cases=((None,'missing',False),(False,'bool',False),('private '+SECRET,'str',False),
            ({'sourceText':SECRET},'dict',False),([SECRET],'list',False),(Decimal(0),'other',False),
            (0,'int',True),(1_000_000_000,'int',True),(-1_000_000_000,'int',True),(.5,'float',True),
            (1_000_000_001,'int',False),(10**10000,'int',False),(float('nan'),'float',False),
            (float('inf'),'float',False),(-float('inf'),'float',False))
        for value,kind,bounded in cases:
            # Direct malformed-data seam avoids feeding invalid JSON to the real
            # private writer; actual coordinator rejection is covered above.
            with self.subTest(kind=kind,bounded=bounded):
                row={'spend':value,**dict.fromkeys(M.USAGE,value),'status':SECRET}
                audit=M.audit_shape_diagnostic(row,{'status':SECRET,'error_information':[SECRET]},dict.fromkeys(M.USAGE,value))
                for scalar in (audit['spend'],*audit['usage'].values(),*audit['usage_expected'].values()):
                    self.assertEqual(scalar,{'type':kind,**({'value':value} if bounded else {})})
                self.assertEqual(audit['row_status'],'other');self.assertEqual(audit['metadata_status'],'other')
                self.assertEqual(audit['error_code_kind'],'missing')
                self.assertIs(audit['checks']['error_class_native'],False)
                self.assertIs(audit['checks']['error_code_expected'],False)
                self.assertNotIn(SECRET,json.dumps(audit,allow_nan=False))
        missing=M.audit_shape_diagnostic({}, {},None)
        self.assertEqual(missing['usage_expected'],{key:{'type':'missing'} for key in M.USAGE})
        self.assertTrue(all(missing['checks'][key+'_matches_estimate'] is None for key in M.USAGE))
        try:raise M.ProofError('failure_audit_shape')
        except M.ProofError as error:diagnostic=M.failure_diagnostic(error,'failure')
        self.assertNotIn('audit',diagnostic)

    def test_restore_only_error_keeps_actual_safe_class_coordinate_and_raw_text_private(self):
        world,runner,result,error,saved=self.replay('restore_only_failure')
        self.assertIsNone(result);self.assertIsInstance(error,OSError)
        self.assertEqual(runner.receipt['failure']['exception_class'],'OSError')
        self.assertEqual(runner.receipt['failure']['stage'],'restore')
        self.assertEqual(runner.receipt['failure']['source_basename'],'prove_failure_recovery.py')
        self.assertIn(SECRET,saved['primary_failure']['message'])
        self.assertNotIn(SECRET,json.dumps(runner.receipt))

    def test_fresh_state_refuses_repeat_before_any_owner_access(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'existing';path.write_text('{}',encoding='utf8')
            runner=M.Recovery(None,None,path)
            with patch.object(M.overlap,'provider') as provider,self.assertRaisesRegex(M.ProofError,'failure_fresh_private_state'):
                runner.execute()
            provider.assert_not_called();self.assertEqual(path.read_bytes(),b'{}')

    def test_public_main_failure_packet_suppresses_all_external_error_text(self):
        unsafe=type('private_'+SECRET,(Exception,),{})
        for error,classification in ((M.ProofError('private '+SECRET),'ProofError'),(OSError('private '+SECRET),'OSError'),
                                     (TypeError('private '+SECRET),'TypeError'),(unsafe('private '+SECRET),'other_exception')):
            output=io.StringIO()
            with patch.object(sys,'argv',['proof','--worker-run']),patch.object(M,'worker',side_effect=error),redirect_stdout(output):
                self.assertEqual(M.main(),1)
            value=json.loads(output.getvalue());self.assertEqual(set(value),{'schema','proof','passed','result','failure_code'})
            self.assertEqual(value['failure_code'],'failure_recovery_verification_failed');self.assertFalse(value['passed'])
            diagnostic=value['result']['failure']
            self.assertEqual(diagnostic['stage'],'prepare');self.assertEqual(diagnostic['exception_class'],classification)
            self.assertEqual(diagnostic['source_basename'],'prove_failure_recovery.py')
            self.assertIs(type(diagnostic['source_line']),int)
            self.assertNotIn(SECRET,output.getvalue())
            self.assertNotIn(str(ROOT),output.getvalue());self.assertNotIn('message',diagnostic)


class NativeSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CACHE.is_dir():raise unittest.SkipTest('Pinned native cache unavailable')
        cls.sources={}
        dto_sources={'proxy/management_endpoints/internal_user_endpoints.py':'0e5673e8a99d1958878f1a0887f1184e2e2919d27db01689861232011fd3a17e',
            'proxy/management_endpoints/key_management_endpoints.py':'c9c644c2a93e20ef9d850454ddb4b23bf1db4823b66be415b9a13a5da045b4de',
            'proxy/auth/route_checks.py':'e159ec69303ba8654062e368ee79376cc5427d9b7999d13942ab8eacae703422',
            'proxy/_types.py':'2ef3c788ab6267bd3ba8bcaf336712cba9f67d49256bdfeb0a516c5de1525500'}
        for relative,expected in (M.NATIVE_FAILURE|dto_sources).items():
            raw=subprocess.check_output(['git','-c','gc.auto=0','show',M.overlap.native_sdk.BASE_REVISION+':litellm/'+relative],
                cwd=CACHE,env=os.environ|{'GIT_NO_LAZY_FETCH':'1'})
            if hashlib.sha256(raw).hexdigest()!=expected:raise AssertionError('Native source freeze differs')
            cls.sources[relative]=ast.parse(raw)

    def execute(self,nodes,ns):
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'exact-pinned-failure-owner','exec',
            flags=__import__('__future__').annotations.compiler_flag),ns)

    def test_pinned_proxy_failure_usage_owner_counts_actual_messages_with_native_tokenizer_boundary(self):
        calls=[];constructed=[];count=37
        def tokens(**kwargs):calls.append(copy.deepcopy(kwargs));return count
        def usage(**kwargs):constructed.append(kwargs);return SimpleNamespace(**kwargs)
        ns={'Final':Final,'litellm':SimpleNamespace(token_counter=tokens),'Usage':usage}
        self.execute([copy.deepcopy(node) for node in self.sources['proxy/utils.py'].body
            if getattr(node,'name',None) in ('_system_prompt_text','_count_request_input_tokens','_estimate_dispatched_failure_usage')],ns)
        model='openai/goal584-fake-a';messages=copy.deepcopy(M.PHYSICAL['messages'])
        result=ns['_estimate_dispatched_failure_usage'](model=model,request_input=messages,system_input=None)
        self.assertEqual(calls,[{'model':model,'messages':messages,'use_default_image_token_count':True}])
        self.assertEqual(constructed,[{'prompt_tokens':37,'completion_tokens':0,'total_tokens':37}])
        self.assertEqual(vars(result),constructed[0]);self.assertEqual(messages,M.PHYSICAL['messages'])
        # Independent tokenizer results must propagate; no fixture count of 88
        # belongs to the production estimator or the proof's expected usage.
        calls.clear();count=91
        result=ns['_estimate_dispatched_failure_usage'](model=model,request_input=messages,system_input='system text')
        self.assertEqual(calls,[{'model':model,'text':'system text'},
            {'model':model,'messages':messages,'use_default_image_token_count':True}])
        self.assertEqual(vars(result),{'prompt_tokens':182,'completion_tokens':0,'total_tokens':182})
        for count in (0,-1):
            with self.subTest(tokenizer_result=count):
                self.assertIsNone(ns['_estimate_dispatched_failure_usage'](model=model,request_input=messages,system_input=None))
        def unavailable(**kwargs):raise RuntimeError(SECRET)
        ns['litellm'].token_counter=unavailable
        self.assertIsNone(ns['_estimate_dispatched_failure_usage'](model=model,request_input=messages,system_input=None))
        # Worker binds the helper to the validated provider model inside the
        # native image, rather than tokenizing on the host or using row usage.
        tree=ast.parse(Path(M.__file__).read_bytes());worker=next(node for node in tree.body if getattr(node,'name',None)=='worker')
        binding=next(node for node in ast.walk(worker) if isinstance(node,ast.Call)
            and isinstance(node.func,ast.Name) and node.func.id=='partial')
        self.assertEqual(binding.args[0].id,'_estimate_dispatched_failure_usage')
        self.assertEqual(ast.dump(binding.keywords[0].value,include_attributes=False),
            ast.dump(ast.parse("model['litellm_params']['model']",mode='eval').body,include_attributes=False))

    def test_native_route_gate_old_operator_denies_population_explicit_read_allows_and_other_denials_remain(self):
        from fastapi import HTTPException, status
        ns={'enum':enum,'Final':Final,'re':re,'HTTPException':HTTPException,'status':status}
        self.execute([copy.deepcopy(node) for node in self.sources['proxy/_types.py'].body
            if isinstance(node,ast.ClassDef) and node.name in ('KeyManagementRoutes','LiteLLMRoutes')],ns)
        tree=self.sources['proxy/auth/route_checks.py']
        owner=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='RouteChecks')
        names={'should_call_route','is_virtual_key_allowed_to_call_route','_route_matches_allowed_route',
            'route_matches_wildcard_pattern','check_route_access','_route_matches_pattern','_is_wildcard_pattern',
            '_get_request_method','is_auth_enforced_pass_through_route','_is_get_mcp_server_discovery_route'}
        selected=ast.ClassDef(name='RouteChecks',bases=[],keywords=[],decorator_list=[],
            body=[copy.deepcopy(node) for node in owner.body if getattr(node,'name',None) in names])
        enforced=next(node for node in tree.body if isinstance(node,ast.AnnAssign)
            and isinstance(node.target,ast.Name) and node.target.id=='_AUTH_ENFORCED_PASS_THROUGH_ROUTE_GROUPS')
        self.execute([copy.deepcopy(enforced),selected],ns);gate=ns['RouteChecks']
        # Only the stand's empty external passthrough registry is doubled. Native
        # route groups, exact/prefix/pattern/wildcard decisions all execute above.
        registry=ModuleType('litellm.proxy.pass_through_endpoints.pass_through_endpoints')
        registry.InitPassThroughEndpointHelpers=SimpleNamespace(
            is_registered_pass_through_route=lambda **kwargs:False,
            get_registered_pass_through_route=lambda **kwargs:None)
        class GateHTTP:
            def __init__(self,routes):self.routes=routes;self.requests=[];self.statuses=[]
            def open(self,request,timeout):
                parts=urlsplit(request.full_url)
                self.requests.append((request.get_method(),parts.path,parse_qs(parts.query)))
                try:gate.is_virtual_key_allowed_to_call_route(route=parts.path,
                    valid_token=SimpleNamespace(allowed_routes=self.routes,metadata={},user_role='proxy_admin'),
                    request=SimpleNamespace(method=request.get_method()))
                except HTTPException as error:
                    self.statuses.append(error.status_code)
                    raise HTTPError(request.full_url,error.status_code,'offline-native-route-denial',Message(),
                        io.BytesIO(json.dumps({'detail':error.detail}).encode())) from None
                self.statuses.append(200)
                value={'users':[],'page':1,'page_size':100,'total_pages':0,'total':0}
                stream=io.BytesIO(json.dumps(value).encode());stream.code=200;stream.headers=Message()
                return stream
        old=['/openapi.json','/user/new','/user/update','/user/info',
            '/key/generate','/key/update','/key/info','/key/list','/spend/logs/v2']
        self.assertEqual([route for route in private_owner.OPERATOR_ROUTES if route not in ('/user/list','/key/block')],old)
        self.assertEqual(private_owner.OPERATOR_ROUTES.count('/user/list'),1)
        self.assertEqual(private_owner.OPERATOR_ROUTES.count('/key/block'),1)
        with patch.dict(sys.modules,{registry.__name__:registry}):
            for routes,expected_status in ((old,403),(private_owner.OPERATOR_ROUTES,200)):
                with self.subTest(operator_routes=routes):
                    native=M.NativeProof('http://127.0.0.1:4000','synthetic-operator-placeholder',1,{})
                    transport=GateHTTP(routes);native.opener=transport
                    if expected_status==403:
                        with self.assertRaises(M.ProofError):M.population(native)
                    else:self.assertEqual(M.population(native),[])
                    self.assertEqual(transport.statuses,[expected_status])
                    self.assertEqual(transport.requests,[('GET','/user/list',{'page':['1'],'page_size':['100'],
                        'sort_by':['user_id'],'sort_order':['asc']})])
            for routes,role,route,method in (
                (private_owner.OPERATOR_ROUTES,'proxy_admin','/v1/chat/completions','POST'),
                (private_owner.OPERATOR_ROUTES,'proxy_admin','/user/delete','POST'),
                (private_owner.OPERATOR_ROUTES,'proxy_admin','/key/delete','POST'),
                (private_owner.OPERATOR_ROUTES,'proxy_admin','/user/listing','GET'),
                (['llm_api_routes'],'internal_user','/user/list','GET'),
                (['llm_api_routes'],'internal_user','/key/block','POST'),
                (['llm_api_routes'],'internal_user','/user/delete','POST')):
                with self.subTest(role=role,route=route),self.assertRaises(HTTPException) as denied:
                    gate.is_virtual_key_allowed_to_call_route(route=route,
                        valid_token=SimpleNamespace(allowed_routes=routes,metadata={},user_role=role),
                        request=SimpleNamespace(method=method))
                self.assertEqual(denied.exception.status_code,403)
            self.assertTrue(gate.is_virtual_key_allowed_to_call_route(route='/v1/chat/completions',
                valid_token=SimpleNamespace(allowed_routes=['llm_api_routes'],metadata={},user_role='internal_user'),
                request=SimpleNamespace(method='POST')))
            self.assertTrue(gate.is_virtual_key_allowed_to_call_route(route='/key/block',
                valid_token=SimpleNamespace(allowed_routes=private_owner.OPERATOR_ROUTES,metadata={},user_role='proxy_admin'),
                request=SimpleNamespace(method='POST')))

    def test_actual_native_release_finalizes_once_and_failure_hook_passes_zero_audit_to_native_writer(self):
        tree=self.sources['proxy/spend_tracking/budget_reservation.py']
        adjustments=[]
        async def redis_adjust(**kwargs):adjustments.append(kwargs);return ()
        ns={'Final':Final,'_set_reserved_entries_actual_cost':redis_adjust}
        self.execute([n for n in tree.body if getattr(n,'name',None) in ('reconcile_budget_reservation','release_budget_reservation')],ns)
        reservation={'reserved_cost':.8,'entries':[{'counter_key':'native-key','reserved_cost':.8}], 'finalized':False}
        import httpx,openai
        ns.update(openai=openai,httpx=httpx)
        self.execute([n for n in self.sources['exceptions.py'].body if getattr(n,'name',None)=='InternalServerError'],ns)
        error=ns['InternalServerError']('Controlled synthetic provider failure','openai',M.MODEL)
        logging_owner=next(n for n in self.sources['litellm_core_utils/litellm_logging.py'].body
            if isinstance(n,ast.ClassDef) and n.name=='StandardLoggingPayloadSetup')
        error_info=copy.deepcopy(next(n for n in logging_owner.body if getattr(n,'name',None)=='get_error_information'))
        error_info.decorator_list=[]
        ns.update(is_expected_client_error=lambda error:False,_redact_string=lambda value:value,
            validate_rate_limit_category=lambda value:None,validate_rate_limit_type=lambda value:None,
            BudgetExceededError=type('BudgetExceededError',(Exception,),{}),_get_provider_request_id=lambda error:None,
            normalize_error=lambda *args:None,StandardLoggingPayloadErrorInformation=dict)
        self.execute([error_info],ns)
        constants=ModuleType('litellm.constants');constants.MAXIMUM_TRACEBACK_LINES_TO_LOG=100
        root_module=ModuleType('litellm');root_module.__path__=[];root_module.log_client_error_tracebacks=False
        ns['litellm']=root_module
        writes=[]
        async def write(**kwargs):writes.append({k:copy.deepcopy(v) if k!='completion_response' else v for k,v in kwargs.items()})
        async def enrich(**kwargs):return kwargs['metadata']
        async def release(**kwargs):await ns['release_budget_reservation'](**kwargs)
        hooks=self.sources['proxy/hooks/proxy_track_cost_callback.py'];owner=next(n for n in hooks.body if isinstance(n,ast.ClassDef) and n.name=='_ProxyDBLogger')
        callback=ast.ClassDef(name='_ProxyDBLogger',bases=[],keywords=[],decorator_list=[],body=[n for n in owner.body if getattr(n,'name',None)=='async_post_call_failure_hook'])
        ns.update(_release_budget_reservation=release,verbose_proxy_logger=logging.getLogger(__name__),Final=Final,cast=cast,
            datetime=datetime,StandardLoggingPayloadErrorInformation=dict,should_suppress_spend_log_tracebacks=lambda:True,
            _sanitize_error_information_for_spend_logs=lambda value,**kwargs:value,_proxy_stamped_used_client_oauth_token=lambda *args:False,
            guardrail_information_cost=lambda value:0,litellm=SimpleNamespace(Usage=type('Usage',(),{})),
            StandardLoggingPayloadSetup=SimpleNamespace(get_error_information=ns['get_error_information']),
            RouteChecks=SimpleNamespace(is_llm_api_route=lambda **kwargs:True),
            LiteLLMProxyRequestSetup=SimpleNamespace(get_sanitized_user_information_from_key=lambda **kwargs:{'user_api_key_user_id':'payer'},
                get_logged_api_key=lambda user_api_key_dict:'a'*64))
        self.execute([callback],ns);klass=ns['_ProxyDBLogger'];klass._should_track_errors_in_db=staticmethod(lambda:True)
        klass._enrich_failure_metadata_unless_db_stalled=staticmethod(enrich)
        logger=klass();logger._spend_writer=lambda:SimpleNamespace(update_database=write)
        auth=SimpleNamespace(budget_reservation=reservation,request_route='/v1/chat/completions',user_id='payer',
            end_user_id=None,team_id=None,org_id=None,project_id=None)
        scope={'call_id':'signed-native-call'}
        request={'model':M.MODEL,'metadata':{'spend_logs_metadata':{'owui_budget':scope}},'litellm_call_id':'native-error-request'}
        ns['litellm']=root_module;root_module.Usage=type('Usage',(),{})
        with patch.dict(sys.modules,{'litellm':root_module,'litellm.constants':constants}):
            asyncio.run(logger.async_post_call_failure_hook(request,error,auth))
        asyncio.run(ns['release_budget_reservation'](reservation))
        self.assertTrue(reservation['finalized']);self.assertEqual(len(adjustments),1);self.assertEqual(adjustments[0]['actual_cost'],0)
        self.assertEqual(len(writes),1);written=writes[0]
        self.assertEqual(written['response_cost'],0);self.assertEqual(written['user_id'],'payer')
        meta=written['kwargs']['litellm_params']['metadata']
        self.assertEqual(meta['spend_logs_metadata']['owui_budget'],scope)
        self.assertEqual(meta['status'],'failure')
        self.assertEqual(meta['error_information']['error_class'],'InternalServerError')
        self.assertEqual(meta['error_information']['error_code'],'500')
        self.assertEqual(error.type,'internal_server_error');self.assertEqual(error.status_code,500)
        spend=self.sources['proxy/spend_tracking/spend_tracking_utils.py']
        self.execute([n for n in spend.body if getattr(n,'name',None)=='get_spend_logs_id'],ns)
        ns['CallTypes']=SimpleNamespace(aretrieve_batch=SimpleNamespace(value='aretrieve_batch'))
        self.assertEqual(ns['get_spend_logs_id']('acompletion',{'result':str(error)},written['kwargs']),'native-error-request')

    def test_real_provider_http500_code_survives_sdk_native_mapping_and_zero_audit_json(self):
        import httpx,openai,traceback
        from http.server import ThreadingHTTPServer
        provider=module('failure_real_http_provider',ROOT/'scripts/goal584-budget-proof/mock_provider.py')
        provider.CONTROL.update(response_status=500,delay_ms=0)
        server=ThreadingHTTPServer(('127.0.0.1',0),provider.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();sdk_error=None
        try:
            with openai.OpenAI(base_url='http://127.0.0.1:'+str(server.server_port)+'/v1',api_key='synthetic-loopback-only',
                    max_retries=0,http_client=httpx.Client(trust_env=False,timeout=5)) as client:
                try:client.chat.completions.create(model='goal584-fake-a',messages=[{'role':'user','content':'Hi'}],max_tokens=5)
                except openai.InternalServerError as error:sdk_error=error
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)
        self.assertFalse(thread.is_alive());self.assertIsNotNone(sdk_error)
        self.assertEqual(sdk_error.status_code,500);self.assertEqual(sdk_error.code,'proof_provider_500')
        self.assertEqual(len(provider.REQUESTS),1);self.assertIsNone(provider.REQUESTS[0]['usage'])
        ns={'openai':openai,'httpx':httpx,'Final':Final,'re':re,'json':json,'traceback':traceback}
        self.execute([node for node in self.sources['exceptions.py'].body if getattr(node,'name',None)=='InternalServerError'],ns)
        native_error=ns['InternalServerError']
        self.execute([node for node in self.sources['litellm_core_utils/exception_mapping_utils.py'].body
            if getattr(node,'name',None) in ('ExceptionCheckers','get_error_message','_litellm_proxy_response','_map_openai_exception')],ns)
        ns['litellm']=SimpleNamespace(InternalServerError=native_error,log_client_error_tracebacks=False)
        mapped=None
        try:ns['_map_openai_exception'](model=M.MODEL,original_exception=sdk_error,custom_llm_provider='openai',
            error_str=str(sdk_error),exception_type=type(sdk_error).__name__,exception_provider='OpenAIException',extra_information='')
        except native_error as error:mapped=error
        self.assertIsNotNone(mapped);self.assertEqual(mapped.status_code,500)
        self.assertEqual(mapped.code,'proof_provider_500');self.assertEqual(mapped.type,'internal_server_error')
        owner=next(node for node in self.sources['litellm_core_utils/litellm_logging.py'].body
            if isinstance(node,ast.ClassDef) and node.name=='StandardLoggingPayloadSetup')
        methods=[]
        for name in ('get_error_information','get_usage_as_dict'):
            node=copy.deepcopy(next(node for node in owner.body if getattr(node,'name',None)==name))
            node.decorator_list=[];methods.append(node)
        ns.update(is_expected_client_error=lambda error:False,_redact_string=lambda value:value,
            validate_rate_limit_category=lambda value:None,validate_rate_limit_type=lambda value:None,
            BudgetExceededError=type('UnrelatedBudgetExceededError',(Exception,),{}),_get_provider_request_id=lambda error:None,
            normalize_error=lambda *args:None,StandardLoggingPayloadErrorInformation=dict)
        self.execute(methods,ns)
        constants=ModuleType('litellm.constants');constants.MAXIMUM_TRACEBACK_LINES_TO_LOG=100
        with patch.dict(sys.modules,{'litellm.constants':constants}):info=ns['get_error_information'](original_exception=mapped)
        usage=ns['get_usage_as_dict'](response_obj={},combined_usage_object=None)
        self.assertEqual(usage,dict.fromkeys(M.USAGE,0));self.assertTrue(all(type(v) is int for v in usage.values()))
        self.assertEqual(info['error_class'],'InternalServerError');self.assertEqual(info['error_code'],'proof_provider_500')
        # Cross the existing external row-IO seam with the real native error DTO;
        # actual coordinator and canonical private JSON readback remain exercised.
        original=World.row
        def actual_error_row(world,*args,**kwargs):
            row=original(world,*args,**kwargs)
            if row['status']=='failure':row['metadata']['error_information']=copy.deepcopy(info)
            return row
        with patch.object(World,'row',actual_error_row):world,runner,result,error,saved=CoordinatorTests().replay()
        self.assertIsNone(error);self.assertTrue(result['passed']);self.assertEqual(len(world.requests),3)
        rows=saved['payers']['recovery']['settled_rows'].values();failure=next(row for row in rows if row['status']=='failure')
        self.assertEqual(failure['spend'],0);self.assertEqual(failure['metadata']['error_information']['error_code'],'proof_provider_500')
        self.assertEqual({key:failure[key] for key in M.USAGE},PROXY_FAILURE_USAGE)
        self.assertTrue(all(type(failure[key]) is int for key in M.USAGE))
        for change in ('code','class','spend','usage'):
            def rejected_error_row(world,*args,**kwargs):
                row=actual_error_row(world,*args,**kwargs)
                if row['status']=='failure':
                    if change=='code':row['metadata']['error_information']['error_code']='foreign_provider_code'
                    elif change=='class':row['metadata']['error_information']['error_class']='BudgetExceededError'
                    elif change=='spend':row['spend']=.1
                    else:row['prompt_tokens']=1
                return row
            with self.subTest(mutation=change),patch.object(World,'row',rejected_error_row):
                world,runner,result,error,saved=CoordinatorTests().replay()
                self.assertIsNone(result);self.assertIsInstance(error,M.ProofError)
                self.assertEqual(str(error),'failure_audit_shape');self.assertEqual(len(world.requests),2)

    def test_native_counter_key_public_owner_returns_only_key_and_user_for_this_scope(self):
        tree=self.sources['proxy/spend_tracking/spend_counter_batch.py'];ns={'Final':Final,'frozenset':frozenset}
        self.execute([n for n in tree.body if getattr(n,'name',None) in ('_iter_entity_counter_keys','post_call_counter_keys')],ns)
        result=ns['post_call_counter_keys'](token='a'*64,user_id='payer',team_id=None,org_id=None,end_user_id=None,
            tags=None,model_access_groups=None)
        self.assertEqual(result,{'spend:key:'+'a'*64,'spend:user:payer'})

    def test_exact_native_user_key_projections_keep_embedded_hash_but_strip_standalone_token_and_echo_lookup(self):
        user_source=self.sources['proxy/management_endpoints/internal_user_endpoints.py']
        ns={'Final':Final,'BaseModel':type('BaseModel',(),{}),'_redact_scim_enterprise_metadata':lambda value:value,
            'UserInfoResponse':lambda **kwargs:kwargs}
        self.execute([n for n in user_source.body if getattr(n,'name',None) in ('_process_keys_for_user_info','_build_user_info_response')],ns)
        raw={'user_id':'payer','models':[M.MODEL],'token':'a'*64,'key_alias':'minted-alias','spend':.2,'total_spend':.2,'team_id':None}
        record=SimpleNamespace(token=raw['token'],model_dump=lambda:copy.deepcopy(raw))
        constants=ModuleType('litellm.constants');constants.UI_SESSION_TOKEN_TEAM_ID='litellm-dashboard'
        proxy=ModuleType('litellm.proxy');proxy.proxy_server=SimpleNamespace(general_settings={},litellm_master_key_hash='different-master')
        with patch.dict(sys.modules,{'litellm.constants':constants,'litellm.proxy':proxy,
            'litellm.proxy.proxy_server':proxy.proxy_server}):
            packet=ns['_build_user_info_response']('payer',{'user_id':'payer','models':[M.MODEL],'metadata':{}},[record],[],None)
        self.assertEqual(packet['user_id'],packet['user_info']['user_id'])
        self.assertEqual(packet['keys'][0],raw|{'team_alias':'None'})
        source=self.sources['proxy/management_endpoints/key_management_endpoints.py']
        owner=next(n for n in source.body if getattr(n,'name',None)=='info_key_fn')
        project=[n for n in ast.walk(owner) if isinstance(n,ast.AnnAssign)
            and isinstance(n.target,ast.Name) and n.target.id in ('key_info_dict','key_token_hash')]
        terminal=next(n for n in ast.walk(owner) if isinstance(n,ast.Return) and isinstance(n.value,ast.Dict)
            and any(isinstance(k,ast.Constant) and k.value=='info' for k in n.value.keys))
        wrapper=ast.parse('async def native_key_projection():\n    pass').body[0];wrapper.body=[*project,terminal]
        async def permission_projection(value,client):return value
        ns.update(key_info=record,key='a'*64,prisma_client=None,attach_object_permission_to_dict=permission_projection)
        self.execute([wrapper],ns);key_packet=asyncio.run(ns['native_key_projection']())
        self.assertEqual(key_packet['key'],'a'*64);self.assertNotIn('token',key_packet['info'])
        self.assertEqual(key_packet['info']['user_id'],'payer');self.assertEqual(key_packet['info']['total_spend'],.2)

    def test_actual_counter_adapter_uses_native_key_owner_and_read_only_same_loop_redis(self):
        tree=self.sources['proxy/spend_tracking/spend_counter_batch.py'];ns={'Final':Final}
        self.execute([n for n in tree.body if getattr(n,'name',None) in ('_iter_entity_counter_keys','post_call_counter_keys')],ns)
        class RedisIO:
            namespace=None
            def __init__(self):self.reads=[];self.closed=False
            def get_ttl(self):return 60
            async def async_get_cache(self,key):self.reads.append(key);return .8
            async def disconnect(self):self.closed=True
        redis=RedisIO();config={'general_settings':{'coordination_redis':{'host':'redis','port':6379}}};seen=[]
        def factory(config):seen.append(config);return redis
        package=ModuleType('litellm');package.__path__=[]
        proxy=ModuleType('litellm.proxy');proxy.__path__=[];proxy.proxy_server=SimpleNamespace(proxy_config=SimpleNamespace(_init_coordination_redis=factory))
        tracking=ModuleType('litellm.proxy.spend_tracking');tracking.__path__=[]
        batch=ModuleType('litellm.proxy.spend_tracking.spend_counter_batch');batch.post_call_counter_keys=ns['post_call_counter_keys']
        with patch.dict(sys.modules,{'litellm':package,'litellm.proxy':proxy,'litellm.proxy.spend_tracking':tracking,
            'litellm.proxy.spend_tracking.spend_counter_batch':batch}):
            owner=M.NativeCounters(config)
            try:
                for _ in range(2):self.assertEqual(owner('payer','a'*64),{'key':.8,'user':.8})
            finally:owner.close()
        self.assertEqual(seen,[config]);self.assertTrue(redis.closed)
        self.assertEqual(redis.reads,['spend:key:'+'a'*64,'spend:user:payer']*2)


if __name__=='__main__':unittest.main()
