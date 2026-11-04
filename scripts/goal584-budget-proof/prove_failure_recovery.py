"""Finite source candidate: native provider500 hold/release/recovery.

Run only inside a separately attested disposable native stand. No host driver or
workflow is supplied here. No retry/reset/restart, rate calculation or new ledger.
"""
from __future__ import annotations

import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import time
from uuid import uuid4

import prove_budget_overlap as overlap
from prove_native_budgets import NativeProof, ProofError, amount, close_amount, require
from prove_pricing_snapshots import SNAPSHOT_KEY, validate_snapshot

PROOF = 'goal584-native-provider500-recovery'
STATE = Path('/proof-private/failure-recovery.private.json')
MODEL = overlap.MODELS[0]
USAGE = {'prompt_tokens':10, 'completion_tokens':5, 'total_tokens':15}
SEMANTIC = {'model':MODEL, **overlap.BODY}
PHYSICAL = {k:v for k,v in SEMANTIC.items() if k!='stream'} | {'model':'goal584-fake-a'}
STAGES = ('prepare','calibration','create_recovery','hold','failure','released','recovery','settled','restore','complete')
RECOVERY_SECONDS = 15
NATIVE_FAILURE = {
    'proxy/hooks/proxy_track_cost_callback.py':'b387f30fc5c896661601b86be402c37aba7fb2990f804d75f60a330457cf754e',
    'proxy/spend_tracking/budget_reservation.py':'81a0bff3cb00210414f26e14ac9450980dc5f54277740a83029207a112672a8a',
    'proxy/spend_tracking/spend_tracking_utils.py':'52ce53917cdb6905abfe6dd61f2ffe9640e5198c9e443629177dcc727d24bd17',
    'proxy/spend_tracking/spend_counter_batch.py':'9ce9f2719d2af7e80dec004b7199b6213a373c1f4c52d78bb2921416659252af',
    'proxy/common_request_processing.py':'4dcc3a41f8179d14ea35d25d9669b89a78063ea162767ba358817d050d2be1d0',
    'litellm_core_utils/litellm_logging.py':'58da82171935240b9280d8c208d383e147e23fb2ad4818de6994934ebf21fe79',
    'litellm_core_utils/exception_mapping_utils.py':'3b5fed3377f6d004cd860483ced684e5602e7f9ed5d5c02c617577c1bfd5b4ca',
    'exceptions.py':'d4a4b46afc48d97c2bde978b04d348b4ce2fb039af009f565178d85fba71aa64',
}


def digest(value):
    return overlap.digest(value)


def failure_diagnostic(error,stage):
    """Fixed representation plus an owned-source coordinate; never error text."""
    known=(ProofError,AttributeError,TypeError,KeyError,ValueError,OSError,TimeoutError,
        RuntimeError,AssertionError,FileNotFoundError,PermissionError,UnicodeError)
    result={'stage':stage if stage in STAGES else 'prepare',
        'exception_class':type(error).__name__ if type(error) in known else 'other_exception'}
    try:
        owned=Path(__file__).resolve();trace=error.__traceback__
        while trace is not None:
            if owned.name=='prove_failure_recovery.py' and Path(trace.tb_frame.f_code.co_filename).resolve()==owned:
                result.update(source_basename='prove_failure_recovery.py',source_line=trace.tb_lineno)
            trace=trace.tb_next
    except Exception:pass
    return result


def metadata(row):
    value=row.get('metadata')
    if isinstance(value,str):
        try:value=json.loads(value)
        except (ValueError,UnicodeError):raise ProofError('failure_row_metadata') from None
    require(isinstance(value,dict),'failure_row_metadata')
    return value


def population(native):
    """Bounded representation adapter for the native /user/list public owner."""
    users=[];total=None
    for page in range(1,11):
        value=native.ok('GET','/user/list',query={'page':page,'page_size':100,'sort_by':'user_id','sort_order':'asc'})
        require(isinstance(value.get('users'),list) and type(value.get('total')) is int
            and 0<=value['total']<=1000 and type(value.get('total_pages')) is int
            and 0<=value['total_pages']<=10 and value.get('page')==page,'failure_population_page')
        if total is None:total=value['total']
        require(total==value['total'],'failure_population_changed')
        users.extend(row['user_id'] for row in value['users'])
        if page>=value['total_pages']:break
    require(len(users)==len(set(users))==total and all(isinstance(uid,str) for uid in users),'failure_population_scope')
    return sorted(users)


def history(native,users):
    # Existing GET/pagination/scope owner returns all rows, including failures.
    return {uid:{'profile':native.user_info(uid),'rows':sorted(native.logs(uid),key=lambda r:r['request_id'])} for uid in users}


def preserve_policy(current,before):
    """Compare full native DTOs; only existing spend/activity fields may vary."""
    def same(row,old,mutable):
        require(isinstance(row,dict) and set(row)==set(old)
            and all(row[k]==v for k,v in old.items() if k not in mutable),'failure_protected_policy_changed')
    require(set(current)==set(before)=={'user','key'},'failure_protected_policy_changed')
    require(isinstance(current['user'].get('keys'),list) and len(current['user']['keys'])==len(before['user']['keys'])==1,
        'failure_protected_policy_changed')
    key_mutable={'spend','total_spend','updated_at','last_active'}
    same(current['user']['keys'][0],before['user']['keys'][0],key_mutable)
    same(current['user'],before['user'],{'spend','updated_at','last_active','keys'})
    same(current['key'],before['key'],key_mutable)


class NativeCounters:
    """Read the same native coordination Redis through its existing SDK owner."""
    def __init__(self,config):
        from litellm.proxy import proxy_server
        from litellm.proxy.spend_tracking.spend_counter_batch import post_call_counter_keys
        self.keys=post_call_counter_keys
        self.redis=proxy_server.proxy_config._init_coordination_redis(config=config)
        require(self.redis is not None and self.redis.namespace is None and self.redis.get_ttl()==60,'failure_native_counter_owner')
        self.loop=asyncio.Runner()

    def __call__(self,uid,key_hash):
        def keys(token,user):
            return self.keys(token=token,user_id=user,team_id=None,org_id=None,end_user_id=None,tags=None,model_access_groups=None)
        key,=keys(key_hash,None);user,=keys(None,uid)
        async def read():
            return {'key':await self.redis.async_get_cache(key=key),'user':await self.redis.async_get_cache(key=user)}
        return self.loop.run(read())

    def close(self):
        try:self.loop.run(self.redis.disconnect())
        finally:self.loop.close()


class Recovery:
    def __init__(self,native,counters,private_state=STATE):
        self.n=native;self.counters=counters;self.path=private_state
        self.recovery_deadline=None
        self.state={'schema':1,'proof':PROOF,'stage':'prepare','attempts':{},'payers':{},'observations':[]}
        self.receipt={'schema':1,'proof':PROOF,'passed':False,'stage':'prepare','restoration':{}}

    def save(self,stage=None):
        if stage is not None:
            require(stage in STAGES,'failure_stage');self.state['stage']=self.receipt['stage']=stage
        overlap.write_private(self.path,self.state)

    def observe(self,label,value):
        self.state['observations'].append({'label':label,'monotonic':time.monotonic(),'value':copy.deepcopy(value)})
        self.save()
        return value

    def create(self,label,cap):
        from employee_budget_assignment import assignment_alias,assignment_metadata
        uid=str(uuid4());self.state['payers'][label]={'user_id':uid};self.save()
        self.n.ok('POST','/user/new',body={'user_id':uid,'user_role':'internal_user','models':[MODEL],
            'max_budget':overlap.cap(cap),'budget_duration':'30d','auto_create_key':False,'send_invite_email':False,'teams':[]})
        generated=self.n.ok('POST','/key/generate',body={'user_id':uid,'models':[MODEL],
            'key_alias':assignment_alias(uid,MODEL),'metadata':assignment_metadata(MODEL),'max_budget':overlap.cap(cap),
            'budget_duration':'30d','allowed_routes':['llm_api_routes']})
        token=generated.get('key');require(isinstance(token,str) and token.startswith('sk-'),'failure_created_key')
        payer=self.state['payers'][label]
        payer.update(key=token,key_hash=hashlib.sha256(token.encode()).hexdigest(),cap_usd=str(cap))
        self.n.keys[uid,MODEL]={'token':token};self.save()
        initial=self.snapshot(label)
        require(initial['rows']==[] and initial['budget']['user'].get('models')==[MODEL]
            and initial['budget']['user'].get('user_role')=='internal_user' and not initial['budget']['user'].get('teams')
            and len(initial['budget']['user'].get('keys',[]))==1
            and initial['budget']['key'].get('key_alias')==assignment_alias(uid,MODEL)
            and initial['budget']['key'].get('allowed_routes')==['llm_api_routes']
            and all(metadata(initial['budget']['key']).get(k)==v for k,v in assignment_metadata(MODEL).items()),'failure_created_policy')
        require(all(amount(row.get('max_budget'))==cap and amount(row.get('spend'))==0
            and row.get('budget_duration')=='30d' and isinstance(row.get('budget_reset_at'),str)
            for row in (*initial['budget'].values(),initial['budget']['user']['keys'][0]))
            and all(amount(key.get('total_spend'))==0 for key in (initial['budget']['key'],initial['budget']['user']['keys'][0])),
            'failure_created_money')
        payer['baseline']=initial;self.save()
        return payer

    def snapshot(self,label):
        payer=self.state['payers'][label];uid=payer['user_id']
        # Retain native packets before existing readers discard response wrappers.
        original=self.n.request
        def request(method,path,**kwargs):
            result=original(method,path,**kwargs)
            if method=='GET' and path=='/spend/logs/v2':
                self.observe('raw_spend_page',{'user_id':uid,'status':result[0],'payload':result[1]})
            if method=='GET' and path in ('/user/info','/key/info'):
                self.observe('raw_profile',{'route':path,'status':result[0],'payload':result[1]})
                if result[0]==200:
                    payload=result[1]
                    if path=='/user/info':
                        require(payload.get('user_id')==uid and isinstance(payload.get('user_info'),dict)
                            and payload['user_info'].get('user_id')==uid,'failure_user_dto_identity')
                    else:
                        selected=kwargs.get('query',{}).get('key')
                        require(selected in (payer['key'],payer['key_hash']) and payload.get('key')==selected,
                            'failure_key_dto_echo')
                        require(isinstance(payload.get('info'),dict) and 'token' not in payload['info'],
                            'failure_key_dto_token_field')
            return result
        self.n.request=request
        try:
            rows=self.n.logs(uid)
            budget={'user':self.n.user_info(uid),'key':self.n.key_info(uid,MODEL)}
        finally:self.n.request=original
        self.bind_budget(budget,payer)
        return self.observe(label+'_snapshot',{'budget':budget,
            'rows':rows,'live':self.counters(uid,payer['key_hash'])})

    def bind_budget(self,budget,payer):
        from employee_budget_assignment import assignment_alias,assignment_metadata
        user=budget['user'];uid=payer['user_id'];keys=user.get('keys')
        require(user.get('user_id')==uid and user.get('models')==[MODEL] and user.get('user_role')=='internal_user'
            and not user.get('teams') and isinstance(keys,list) and len(keys)==1 and isinstance(keys[0],dict),
            'failure_budget_user_binding')
        require(keys[0].get('token')==payer['key_hash'],'failure_embedded_key_hash')
        for key in (budget['key'],keys[0]):
            require(key.get('user_id')==uid and key.get('models')==[MODEL]
                and key.get('key_alias')==assignment_alias(uid,MODEL) and key.get('team_id') is None
                and key.get('allowed_routes')==['llm_api_routes'] and not key.get('blocked')
                and all(metadata(key).get(k)==v for k,v in assignment_metadata(MODEL).items()),'failure_budget_key_binding')
            require(amount(key.get('max_budget'))==amount(payer['cap_usd']) and key.get('budget_duration')=='30d'
                and isinstance(key.get('budget_reset_at'),str),'failure_budget_key_policy')

    def call(self,label,payer_label):
        require(label in ('calibration','failure','recovery') and label not in self.state['attempts'],'failure_repeat_dispatch')
        from provenance import encode_call
        payer=self.state['payers'][payer_label];uid=payer['user_id'];chat=str(uuid4());answer=str(uuid4())
        body={**copy.deepcopy(SEMANTIC),'litellm_metadata':{'owui_budget_provenance':encode_call(
            os.environ['OWUI_BUDGET_GATEWAY_SECRET'],user_id=uid,model=MODEL,chat_id=chat,answer_id=answer,
            root_chat_id=chat,root_answer_id=answer)}}
        self.state['attempts'][label]={'user_id':uid,'chat_id':chat,'answer_id':answer,'body':body,
            'capture_before':[r['_observation_id'] for r in overlap.capture()],'dispatch_attempted':True}
        self.save()
        if label=='recovery':
            require(self.recovery_deadline is not None and time.monotonic()<self.recovery_deadline,'failure_release_deadline')
        result=self.n.request('POST','/v1/chat/completions',token=os.environ['OWUI_BUDGET_GATEWAY_SECRET'],body=body,
            extra_headers={'X-OpenWebUI-User-Id':uid,'X-OpenWebUI-Task':''})
        self.state['attempts'][label]['response_returned_monotonic']=time.monotonic()
        status,payload,headers=result
        self.state['attempts'][label]['response']=[status,payload,list(headers.items())];self.save()
        return result

    def capture(self,label):
        from provenance import validate_persisted_scope
        attempt=self.state['attempts'][label]
        found=[r for r in overlap.capture() if r['_observation_id'] not in attempt['capture_before']
            and r.get('user_id')==attempt['user_id'] and r.get('verified_cost_scope',{}).get('chat_id')==attempt['chat_id']]
        require(len(found)==1,'failure_capture_cardinality');record=found[0]
        require(record.get('body')==record.get('body_after_auth')==SEMANTIC
            and not record.get('auth_failure') and record.get('provenance_removed_after') is True,'failure_capture_context')
        scope=validate_persisted_scope(record.get('verified_cost_scope'))
        require(scope['user_id']==attempt['user_id'] and scope['model']==MODEL
            and scope['chat_id']==scope['root_chat_id']==attempt['chat_id']
            and scope['answer_id']==scope['root_answer_id']==attempt['answer_id'],'failure_capture_scope')
        estimate=amount(record.get('native_estimated_max_cost_usd'))
        if 'reserve_usd' in self.state:require(close_amount(estimate,amount(self.state['reserve_usd'])),'failure_estimate_drift')
        attempt.update(capture=record,scope=scope,estimate_usd=str(estimate));self.save()
        return attempt

    def physical(self,labels,*,pending=False):
        value=self.observe('provider',overlap.provider())
        require(value.get('synthetic') is True and set(value)=={'synthetic','requests','control'},'failure_provider_shape')
        before=self.state['provider_before'];rows=value['requests']
        require(rows[:len(before)]==before and len(rows)<=len(before)+len(labels),'failure_extra_provider_dispatch')
        new=rows[len(before):]
        require(len({r.get('id') for r in rows})==len(rows),'failure_duplicate_provider_id')
        require(len(new)==len(labels),'failure_provider_cardinality')
        for label,row in zip(labels,new):
            overlap.request_id(row.get('id'))
            require(row.get('body')==PHYSICAL and type(row.get('created')) is int,'failure_provider_context')
            life=row.get('lifecycle',{})
            require(life.get('started') is True and life.get('chunks_sent')==0
                and type(life.get('started_monotonic')) in (int,float)
                and math.isfinite(life['started_monotonic']),'failure_provider_lifecycle')
            if label=='failure':
                require(row.get('usage') is None and 'response' not in row and life.get('response_status')==500
                    and life.get('usage_sent') is False,'failure_provider_before_usage')
                require(life.get('delay_ms')==3000 and life.get('after_first_chunk_delay_ms')==0,'failure_provider_delay')
                if pending:
                    require(life.get('terminal') is False and life.get('stage')=='before_headers_delay'
                        and life.get('headers_sent') is False and life.get('outcome') is None,'failure_provider_hold')
                else:
                    require(life.get('terminal') is True and life.get('stage')==life.get('outcome')=='controlled_error'
                        and life.get('headers_sent') is True,'failure_provider_terminal')
            else:
                expected={'id':row['id'],'object':'chat.completion','created':row['created'],'model':'goal584-fake-a',
                    'choices':[{'index':0,'message':{'role':'assistant','content':'Proof'},'finish_reason':'stop'}],'usage':USAGE}
                require(row.get('usage')==USAGE and row.get('response')==expected and life.get('response_status')==200
                    and life.get('terminal') is True and life.get('stage')==life.get('outcome')=='completed'
                    and life.get('headers_sent') is True and life.get('usage_sent') is True
                    and life.get('delay_ms')==life.get('after_first_chunk_delay_ms')==0,'failure_success_provider')
            if life.get('terminal') is True:
                require(type(life.get('terminal_monotonic')) in (int,float)
                    and math.isfinite(life['terminal_monotonic']) and life['terminal_monotonic']>=life['started_monotonic'],
                    'failure_provider_terminal_time')
            previous=self.state.setdefault('physical',{}).get(label)
            if previous is not None and previous['lifecycle']['terminal'] is True:
                require(previous==row,'failure_old_provider_changed')
            self.state['physical'][label]=copy.deepcopy(row)
        self.save();return new

    def verify(self,payer_label,labels,live_expected,*,complete=True):
        payer=self.state['payers'][payer_label];snapshot=self.snapshot(payer_label);rows=snapshot['rows']
        preserve_policy(snapshot['budget'],payer['baseline']['budget'])
        successes=[label for label in labels if label!='failure']
        expected=overlap.CALL_COST if successes else Decimal(0)
        require(len(successes)<=1,'failure_unbounded_successes')
        ready=True
        embedded=snapshot['budget']['user']['keys'][0]
        for row in (*snapshot['budget'].values(),embedded):
            current=amount(row.get('spend'));require(0<=current<=expected+Decimal('.000000001'),'failure_counter_surplus')
            ready &= close_amount(current,expected)
        for key in (snapshot['budget']['key'],embedded):
            total=amount(key.get('total_spend'))
            require(0<=total<=expected+Decimal('.000000001'),'failure_lifetime_surplus');ready &= close_amount(total,expected)
        require(set(snapshot['live'])=={'key','user'},'failure_live_counter_shape')
        for value in snapshot['live'].values():
            require(value is not None,'failure_missing_live_counter')
            observed=amount(value);require(observed>=0,'failure_negative_live_counter')
            # A terminal zero must never wait for a stale hold to expire.
            if live_expected==0:require(observed==0,'failure_orphan_hold')
            else:require(observed<=live_expected+Decimal('.000000001'),'failure_live_counter_surplus')
            ready &= close_amount(observed,live_expected)
        require(len(rows)<=len(labels) and len({r.get('request_id') for r in rows})==len(rows),'failure_extra_or_duplicate_row')
        seen=set()
        for row in rows:
            meta=metadata(row);scope=meta.get('spend_logs_metadata',{}).get('owui_budget')
            matches=[label for label in labels if self.state['attempts'][label].get('scope')==scope]
            require(len(matches)==1 and matches[0] not in seen,'failure_unknown_or_duplicate_row_scope');label=matches[0];seen.add(label)
            require(row.get('user')==payer['user_id'] and row.get('api_key')==payer['key_hash']
                and row.get('model_group')==MODEL and row.get('model_id')=='goal584-deployment-a'
                and row.get('session_id')==scope['chat_id'],'failure_row_identity')
            if label=='failure':
                error=meta.get('error_information',{})
                # Native metadata keeps the provider code; HTTP500 is checked at dispatch.
                require(row.get('status')==meta.get('status')=='failure' and amount(row.get('spend'))==0
                    and all(type(row.get(k)) is int and row[k]==0 for k in USAGE)
                    and error.get('error_class')=='InternalServerError' and error.get('error_code')=='proof_provider_500','failure_audit_shape')
            else:
                attempt=self.state['attempts'][label];status,response,_=attempt['response']
                require(status==200 and row.get('request_id')==response.get('id')==self.state['physical'][label]['id']
                    and row.get('status')=='success' and close_amount(row.get('spend'),overlap.CALL_COST)
                    and all(type(row.get(k)) is int and row[k]==v for k,v in USAGE.items())
                    and response.get('usage')==USAGE,'failure_success_row')
                rates=validate_snapshot(meta.get('spend_logs_metadata',{}).get(SNAPSHOT_KEY))
                require(rates['availability']=='available' and all(v>=0 for v in rates['rates'].values())
                    and rates['rates']['input_cost_per_token']==.01 and rates['rates']['output_cost_per_token']==.02,
                    'failure_success_frozen_rates')
            require(isinstance(row.get('request_id'),str) and row['request_id'] not in ('','None'),'failure_row_request_id')
        ready &= seen==set(labels)
        old=payer.setdefault('settled_rows',{})
        current={r['request_id']:r for r in rows}
        require(old.keys()<=current.keys() and all(current[k]==v for k,v in old.items()),'failure_old_row_changed')
        if complete and ready:payer['settled_rows']=copy.deepcopy(current);self.save()
        return snapshot if ready else None

    def restore(self):
        if 'original_control' not in self.state:return
        restore=copy.deepcopy(self.state['original_control'])
        # Existing provider optional controls accept None to remove the key.
        for key in ('response_status','after_first_chunk_delay_ms'):
            if key not in restore:restore[key]=None
        overlap.provider('POST','/__proof/control',restore)
        require(overlap.provider()['control']==self.state['original_control'],'failure_restore_controls')
        self.receipt['restoration']={'provider_controls_restored':True,'financial_history_retained':True};self.save()

    def execute(self):
        require(not self.path.exists(),'failure_fresh_private_state')
        initial=overlap.provider();self.observe('initial_provider',initial)
        require(initial.get('synthetic') is True and all(r.get('lifecycle',{}).get('terminal') is True for r in initial['requests']),
            'failure_provider_not_quiescent')
        from capture_webui_auth import MAX_RECORDS
        require(len(overlap.capture())+3<=MAX_RECORDS,'failure_capture_capacity')
        self.state.update(original_control=initial['control'],provider_before=initial['requests'],old_users=population(self.n))
        self.state['old_history']=history(self.n,self.state['old_users']);self.save()
        desired={'prompt_tokens':10,'completion_tokens':5,'delay_ms':0,'tool_round':False,'admin_mode':False,
            'title_mode':False,'native_tasks_mode':False,'response_status':200,'after_first_chunk_delay_ms':0}
        require(set(initial['control'])<=set(desired) and {'prompt_tokens','completion_tokens','delay_ms','tool_round','admin_mode','title_mode'}<=set(initial['control']),
            'failure_unsupported_provider_control')
        controls={k:desired[k] for k in initial['control']};controls.update(response_status=200,after_first_chunk_delay_ms=0)
        primary=None;primary_stage=None
        try:
            overlap.provider('POST','/__proof/control',controls)
            self.save('calibration');self.create('calibration',Decimal(20));self.call('calibration','calibration')
            attempt=self.capture('calibration');self.physical(['calibration'])
            require(attempt['response'][0]==200,'failure_calibration_response')
            reserve,budget=overlap.calibrated_caps(dict.fromkeys(overlap.MODELS,attempt['estimate_usd']))
            self.state.update(reserve_usd=str(reserve),budget_usd=str(budget));self.save()
            self.n.poll('failure calibration settlement',lambda:self.verify('calibration',['calibration'],overlap.CALL_COST))
            self.save('create_recovery');self.create('recovery',budget)
            self.save('hold');overlap.provider('POST','/__proof/control',{'response_status':500,'delay_ms':3000})
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(self.call,'failure','recovery')
                def held():
                    value=overlap.provider()
                    if len(value['requests'])==len(self.state['provider_before'])+1:return None
                    self.physical(['calibration','failure'],pending=True)
                    require(not future.done(),'failure_hold_client_finished')
                    self.capture('failure')
                    snapshot=self.verify('recovery',[],reserve)
                    require(snapshot is not None,'failure_hold_not_observed')
                    return {'provider_id':self.state['physical']['failure']['id'],'reserve_usd':str(reserve),'client_unfinished':True}
                witness_failure=None
                try:self.receipt['hold']=self.n.poll('failure actual provider/hold witness',held)
                except Exception as error:witness_failure=error
                try:result=future.result(timeout=45)
                except Exception:
                    if witness_failure is not None:raise witness_failure
                    raise
                if witness_failure is not None:raise witness_failure
            failed_at=self.state['attempts']['failure'].get('response_returned_monotonic')
            require(type(failed_at) in (int,float) and math.isfinite(failed_at),'failure_response_timestamp')
            self.save('failure');self.capture('failure');self.physical(['calibration','failure'])
            status,response,_=result
            require(status==500 and isinstance(response.get('error'),dict)
                and response['error'].get('type')=='internal_server_error','failure_native500_response')
            overlap.provider('POST','/__proof/control',{'response_status':200,'delay_ms':0})
            deadline=failed_at+RECOVERY_SECONDS
            self.recovery_deadline=deadline
            def released_audit():
                require(time.monotonic()<deadline,'failure_release_deadline')
                snapshot=self.verify('recovery',['failure'],Decimal(0))
                require(time.monotonic()<deadline,'failure_release_deadline')
                return snapshot
            released=self.n.poll('failure audit and released counters',released_audit)
            self.save('released');self.receipt['released']={'row_count':len(released['rows']),'native_spend_usd':'0','native_live_usd':'0'}
            self.save('recovery');require(time.monotonic()<deadline,'failure_release_deadline')
            self.call('recovery','recovery');self.capture('recovery');self.physical(['calibration','failure','recovery'])
            final=self.n.poll('failure recovery terminal accounting',lambda:self.verify('recovery',['failure','recovery'],overlap.CALL_COST))
            elapsed=time.monotonic()-failed_at
            require(elapsed<RECOVERY_SECONDS,'failure_recovery_waited_for_ttl')
            self.save('settled')
            require(history(self.n,self.state['old_users'])==self.state['old_history'],'failure_prior_financial_state_changed')
            require(population(self.n)==sorted(self.state['old_users']+[p['user_id'] for p in self.state['payers'].values()]),'failure_population_drift')
            require(self.verify('calibration',['calibration'],overlap.CALL_COST) is not None,'failure_calibration_history_missing')
            self.receipt.update(physical_calls=3,tested_payer_calls=2,final_rows=2,final_spend_usd=str(overlap.CALL_COST),
                key_lifetime_spend_usd=str(overlap.CALL_COST),recovery_seconds=elapsed,
                evidence_sha256=digest(final),holds_released_once_by_effect=True,not_a_general_failure_or_cancel_qualification=True)
        except Exception as error:primary=error;primary_stage=self.receipt['stage']
        finally:
            try:self.restore()
            except Exception as error:
                self.receipt['restoration']={'provider_controls_restored':False,'financial_history_retained':True}
                if primary is None:primary=error;primary_stage='restore'
        if primary:
            self.receipt['failure']=failure_diagnostic(primary,primary_stage)
            try:
                self.state['primary_failure']={'stage':primary_stage,'exception_class':type(primary).__name__,
                    'message':str(primary)[:4096]}
                self.save()
            except Exception:self.receipt['primary_failure_write_failed']=True
            raise primary
        self.save('complete');self.receipt['passed']=True;return self.receipt


def worker():
    import yaml
    # Reuse the accepted stand's DB/Redis/auth/provenance/models/retry owner.
    binding=overlap.worker('identity')
    config=yaml.safe_load(Path('/proof/config.yaml').read_bytes())
    require(config['general_settings'].get('disable_spend_logs') is False
        and config['general_settings'].get('disable_error_logs') in (None,False),'failure_config_profile')
    model=next(m for m in config['model_list'] if m['model_name']==MODEL)
    require(model['litellm_params']=={'model':'openai/goal584-fake-a','api_base':'http://provider:8000/v1',
        'api_key':'synthetic-provider-only-not-a-credential'} and model['model_info'].get('id')=='goal584-deployment-a'
        and model['model_info'].get('input_cost_per_token')==.01 and model['model_info'].get('output_cost_per_token')==.02,
        'failure_synthetic_model_profile')
    require(overlap.native_sdk.variant()==overlap.native_sdk.VARIANT,'failure_approved_native_variant')
    native_artifact=overlap.native_sdk.inspect_sources()
    package=Path(importlib.util.find_spec('litellm').origin).parent
    require({name:hashlib.sha256((package/name).read_bytes()).hexdigest() for name in NATIVE_FAILURE}==NATIVE_FAILURE,
        'failure_native_source_binding')
    native,_=overlap.proof();counters=NativeCounters(config);runner=Recovery(native,counters)
    runner.receipt['native_artifact']=native_artifact
    runner.receipt['native_failure_sha256']=NATIVE_FAILURE
    runner.receipt['existing_owner_identity']=binding
    failure=False
    try:runner.execute()
    except Exception as error:
        failure=True
        if 'failure' not in runner.receipt:runner.receipt['failure']=failure_diagnostic(error,runner.receipt['stage'])
    try:counters.close()
    except Exception as error:
        failure=True;runner.receipt['counter_reader_closed']=False
        if 'failure' not in runner.receipt:runner.receipt['failure']=failure_diagnostic(error,'restore')
    if failure:runner.receipt['passed']=False
    return runner.receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--worker-run',action='store_true',required=True)
    parser.parse_args();packet={'schema':1,'proof':PROOF,'passed':False,'result':None,'failure_code':None}
    try:
        result=worker();packet.update(passed=result.get('passed') is True,result=result)
        if not packet['passed']:packet['failure_code']='failure_recovery_verification_failed'
    except Exception as error:
        packet['failure_code']='failure_recovery_verification_failed'
        packet['result']={'stage':'prepare','failure':failure_diagnostic(error,'prepare')}
    print(json.dumps(overlap.safe(packet),allow_nan=False));return 0 if packet['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
