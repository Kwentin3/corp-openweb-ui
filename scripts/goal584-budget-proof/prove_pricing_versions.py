"""Finite synthetic native tariff publication; host Compose + protected worker CLI.

No LiteLLM import, cost calculation, model retry, ledger or scheduler. Parent
must freeze the callback hash and wire the dedicated stand before native use.
"""
from __future__ import annotations

import argparse
import ast
import base64
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
import stat
import subprocess
import time
from uuid import UUID, uuid4

import prove_pricing_catalog as catalog
from prove_native_budgets import NativeProof, ProofError, close_amount, require
from prove_gateway_auth import read_private, write_private
from prove_budget_overlap import Coordinator as ComposeDriver

ROOT = Path(__file__).resolve().parent.parent.parent
PRIVATE = Path('/proof-private')
STATE = PRIVATE/'pricing-versions.private.json'
ATTEST = PRIVATE/'catalog-attestation.private.json'
CONFIG = Path('/proof/config.yaml')
CALLBACK = Path('/proof/pricing_snapshot.py')
PROOF = 'goal584-controlled-pricing-versions'
# Exact LF Git blobs from approved integration commit 0fccfc4f39ab06fb8e69e5d4eb27f2b4029661e1.
CALLBACK_SHA256 = '9bff480f9939e46f84c6dc2673315e61f2404297c39d734b796774600a9881d6'
CATALOG_SHA256 = '48b0f92892d1071f0dc229d1277d56b9bb3b8eb70397e3a347ad84f25cbedc6a'
LABELS = ('v1_S1', 'v1_S2', 'v2_S2')
EXPECTED = (('v1', '.20', '.20'), ('v1', '.20', '.40'), ('v2', '.40', '.80'))
USAGE = {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}
PHYSICAL_BODY = {'messages': [{'role': 'user', 'content': 'Hi'}], 'model': 'goal584-fake-a', 'max_tokens': 5}
TOKEN_ID = re.compile('chatcmpl-goal584-[0-9a-f]{32}')
SOURCE_PATHS = {'prove_pricing_versions.py':'scripts/goal584-budget-proof/prove_pricing_versions.py',
    'prove_pricing_catalog.py':'scripts/goal584-budget-proof/prove_pricing_catalog.py',
    'prove_budget_overlap.py':'scripts/goal584-budget-proof/prove_budget_overlap.py',
    'prove_native_budgets.py':'scripts/goal584-budget-proof/prove_native_budgets.py',
    'prove_gateway_auth.py':'scripts/goal584-budget-proof/prove_gateway_auth.py',
    'native_floor_identity.py':'deploy/litellm-patches/positive-floor-v1.105.1/native_floor_identity.py',
    'manifest.json':'deploy/litellm-patches/positive-floor-v1.105.1/manifest.json',
    'pricing_snapshot.py':'deploy/openwebui-budgets/pricing_snapshot.py'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return catalog.encoded(value)


def rate_fields(path=None):
    path=CALLBACK if path is None else path
    tree = ast.parse(path.read_bytes())
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t,ast.Name) and t.id=='RATE_FIELDS' for t in n.targets))
    fields = ast.literal_eval(node.value)
    require(isinstance(fields, tuple) and len(fields) == len(set(fields)) == 7 and all(isinstance(v,str) for v in fields), 'version_rate_schema')
    return fields


def source_binding():
    require(isinstance(CALLBACK_SHA256,str) and re.fullmatch('[0-9a-f]{64}',CALLBACK_SHA256), 'version_callback_freeze_required')
    require(sha(CALLBACK.read_bytes()) == CALLBACK_SHA256 and sha(Path(catalog.__file__).read_bytes()) == CATALOG_SHA256, 'version_frozen_sources')
    return {'callback_sha256': CALLBACK_SHA256, 'catalog_sha256': CATALOG_SHA256,
        'worker_sha256': sha(Path(__file__).read_bytes()), 'rate_fields': rate_fields()}


def base64_bytes(value):
    return base64.b64encode(value).decode('ascii')


def publication(base, version, project, declared_at):
    """Only two finite approved fixture terms; no arbitrary pricing input."""
    require(version in ('v1','v2') and re.fullmatch('goal584-pricing-[0-9a-f]{12}',project), 'version_publication_profile')
    catalog.utc(declared_at)
    value = copy.deepcopy(base)
    model = next(m for m in value['model_list'] if m['model_name']=='goal584-a')
    identifier = 'goal584-price-a-'+version
    descriptor = {'schema':1, 'deployment_id':identifier, 'currency':'USD', 'source_ref':'fixture:agreed-'+version,
        'source_url':'https://example.invalid/goal584/agreed/'+version, 'source_checked_at_utc':declared_at,
        'declared_effective_from_utc':declared_at, 'declared_effective_until_utc':None,
        'activation_ref':project+'-'+version, 'qualified_usage':'flat_input_output'}
    model['model_info'].update(id=identifier, input_cost_per_token=.01 if version=='v1' else .02,
        output_cost_per_token=.02 if version=='v1' else .04, owui_pricing=descriptor)
    # All other original config, A route/params and B remain equal, not rebuilt.
    return value


def approve(approved, value, base):
    model = next(m for m in value['model_list'] if m['model_name']=='goal584-a')
    identifier = model['model_info']['id']
    require(identifier in ('goal584-price-a-v1','goal584-price-a-v2'), 'version_approved_id')
    digest = sha(encoded(value))
    require(identifier not in approved or approved[identifier]['config_sha256']==digest, 'version_id_reused_with_changed_terms')
    descriptor=model['model_info'].get('owui_pricing',{})
    require(value==publication(base,identifier.rsplit('-',1)[1],descriptor.get('activation_ref','').rsplit('-',1)[0],descriptor.get('source_checked_at_utc')),
        'version_publication_changed_protected_config')
    approved.setdefault(identifier, {'config_sha256':digest,'config':copy.deepcopy(value)})
    return approved[identifier]


def persist(state):
    encoded(state);write_private(STATE,state)


def native(state=None):
    master = os.environ.get('PROOF_MASTER_KEY','')
    require(master.startswith('sk-') and len(master)>=20,'version_private_master')
    result = NativeProof('http://127.0.0.1:4000',master,60,{})
    if state:result.started_at=datetime.fromisoformat(state['started_at'])
    return result


def fixture(native, state):
    helper = catalog.Coordinator(native,STATE,{'stage':'version','observations':[]})
    helper.private = state
    return helper


def identity(n, state, selected):
    import yaml
    source_binding()
    require(selected in ('base','v1','v2'),'version_identity_label')
    require(os.environ.get('PROOF_PRICING_PROJECT')==state['project'] and re.fullmatch('[0-9a-f]{12}',os.environ.get('HOSTNAME','')),'version_worker_project')
    actual = yaml.safe_load(CONFIG.read_bytes())
    expected = state['base_config'] if selected=='base' else state['approved']['goal584-price-a-'+selected]['config']
    require(actual==expected,'version_config_readback')
    package=Path(importlib.util.find_spec('litellm').origin).parent
    require({p:sha((package/p).read_bytes()) for p in catalog.NATIVE}==catalog.NATIVE,'version_native_sources')
    sdk=catalog.native_sdk.inspect_sources()
    require(sdk['native_artifact']==state['native_artifact'],'version_native_artifact')
    rows=n.ok('GET','/model/info').get('data')
    require(isinstance(rows,list) and len(rows)==2 and {r['model_name'] for r in rows}=={'goal584-a','goal584-b'},'version_native_model_set')
    models={r['model_name']:r['model_info'] for r in rows}
    for m in expected['model_list']:
        info=models[m['model_name']]
        for key in ('id','input_cost_per_token','output_cost_per_token'):
            require(info.get(key)==m['model_info'][key],'version_native_model_info')
        if m['model_name']=='goal584-a' and selected!='base':
            require(info.get('owui_pricing')==m['model_info']['owui_pricing'],'version_native_descriptor')
    source=catalog.source_projection(n.ok('GET',catalog.SOURCE))
    status=catalog.status_projection(n.ok('GET',catalog.STATUS))
    require(not status['scheduled'],'version_unexpected_schedule')
    observation={'config_sha256':sha(CONFIG.read_bytes()), 'config_semantic_sha256':sha(encoded(actual)),
        'worker_id_prefix':os.environ['HOSTNAME'],'native_artifact':sdk['native_artifact'],
        'model_A':{k:models['goal584-a'].get(k) for k in ('id','input_cost_per_token','output_cost_per_token','owui_pricing')},
        'model_B_sha256':sha(encoded(next(m for m in actual['model_list'] if m['model_name']=='goal584-b'))),
        'source':source,'status':status,'bindings':source_binding()}
    state.setdefault('identities',[]).append(observation);persist(state)
    return observation


def budgets(n,state):
    user=n.user_info(state['user_id'])
    key=n.ok('GET','/key/info',query={'key':state['key']}).get('info')
    require(isinstance(key,dict) and user.get('user_id')==key.get('user_id')==state['user_id']
        and user.get('user_role')=='internal_user' and user.get('models')==key.get('models')==['goal584-a']
        and not user.get('teams') and key.get('team_id') is None and key.get('allowed_routes')==['llm_api_routes'], 'version_budget_identity')
    for row in (user,key):
        require(close_amount(row.get('max_budget'),Decimal(20)) and row.get('budget_duration')=='1mo' and isinstance(row.get('budget_reset_at'),str),'version_budget_caps_period')
    return {'user':user,'key':key}


def protected(budget):
    omit={'spend','total_spend','updated_at','last_active','keys'}
    return {table:{k:v for k,v in row.items() if k not in omit} for table,row in budget.items()}


def decode_metadata(row):
    value=row.get('metadata');value=json.loads(value) if isinstance(value,str) else value
    require(isinstance(value,dict) and isinstance(value.get('spend_logs_metadata'),dict),'version_row_metadata')
    return value['spend_logs_metadata']


def logged_rows(n,state):
    """Keep actual pages before the unchanged native GET owner validates scope."""
    original=n.request
    def observed(method,path,**kwargs):
        result=original(method,path,**kwargs)
        if method=='GET' and path=='/spend/logs/v2':
            state.setdefault('raw_spend_pages',[]).append({'status':result[0],'payload':result[1]});persist(state)
        return result
    n.request=observed
    try:return n.logs(state['user_id'])
    finally:n.request=original


def verified_row(row,state,call):
    require(row.get('request_id')==call['request_id'] and row.get('user')==state['user_id']
        and row.get('api_key')==state['key_hash'] and row.get('status')=='success'
        and row.get('model_group')=='goal584-a' and row.get('model_id')==call['deployment_id']
        and row.get('model') in ('goal584-a','goal584-fake-a','openai/goal584-fake-a')
        and close_amount(row.get('spend'),Decimal(call['cost']))
        and all(type(row.get(k)) is int and row[k]==v for k,v in USAGE.items()),'version_row_identity_cost_usage')
    meta=decode_metadata(row)
    require(set(meta)=={'chat_id','root_answer_id','call_kind','owui_billed_token_rates','owui_tariff_descriptor'}
        and meta['chat_id']==call['chat_id'] and meta['root_answer_id']==call['root_answer_id']
        and meta['call_kind']=='synthetic_chat','version_row_lineage')
    snapshot=meta['owui_billed_token_rates']
    require(set(snapshot)=={'schema','availability','observed_at_utc','rates'} and type(snapshot['schema']) is int
        and snapshot['schema']==1 and snapshot['availability']=='available' and set(snapshot['rates'])==set(rate_fields()),'version_rate_snapshot')
    catalog.utc(snapshot['observed_at_utc'])
    require(all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in snapshot['rates'].values()),'version_native_rates')
    terms=state['approved'][call['deployment_id']]['config']['model_list']
    info=next(m['model_info'] for m in terms if m['model_name']=='goal584-a')
    require(all(snapshot['rates'][k]==info[k] for k in ('input_cost_per_token','output_cost_per_token')),'version_native_rate_mismatch')
    descriptor=meta['owui_tariff_descriptor']
    require(type(descriptor.get('schema')) is int and type(descriptor.get('descriptor',{}).get('schema')) is int
        and descriptor=={'schema':1,'availability':'available','descriptor':info['owui_pricing']},'version_row_descriptor')
    require(catalog.utc(snapshot['observed_at_utc'])>=catalog.utc(info['owui_pricing']['declared_effective_from_utc']), 'version_call_before_declared_interval')
    return {'request_id':row['request_id'],'user_id':state['user_id'],'key_hash':state['key_hash'],'model_id':row['model_id'],
        'model':row['model'],'model_group':row['model_group'],'status':row['status'],'spend_usd':str(row['spend']),
        'usage':USAGE,'lineage':{k:meta[k] for k in ('chat_id','root_answer_id','call_kind')},
        'rates':snapshot,'descriptor':meta['owui_tariff_descriptor'],'full_row_sha256':sha(encoded(row))}


def settle(n,state):
    previous={r['request_id']:r for r in state.get('rows',[])}
    calls={c['request_id']:c for c in state['calls']}
    expected=Decimal(EXPECTED[len(calls)-1][2]) if calls else Decimal(0)
    def ready():
        rows=logged_rows(n,state);budget=budgets(n,state)
        physical=fixture(n,state).provider('/requests')
        state.setdefault('raw_observations',[]).append({'rows':rows,'budgets':budget,'provider':physical});persist(state)
        require(len(rows)<=len(calls) and len({r.get('request_id') for r in rows})==len(rows),'version_extra_or_duplicate_row')
        current={r['request_id']:r for r in rows}
        require(previous.keys()<=current.keys() and all(encoded(current[k])==encoded(v) for k,v in previous.items()),'version_old_row_changed')
        require(protected(budget)==protected(state['baseline_budget']),'version_protected_budget_changed')
        for row in rows:
            require(row.get('request_id') in calls,'version_unknown_raw_row')
            verified_row(row,state,calls[row['request_id']])
        require(set(physical)=={'synthetic','requests','control'} and physical['synthetic'] is True
            and physical['control']=={'prompt_tokens':10,'completion_tokens':5,'delay_ms':0,'tool_round':False,'admin_mode':False,'title_mode':False}
            and len(physical['requests'])==len(calls),'version_extra_provider_call')
        found=set()
        provider_ready=True
        for item in physical['requests']:
            life=item.get('lifecycle',{})
            completed=life.get('terminal') is True
            require(set(item) in ({'id','created','body','usage','lifecycle'},{'id','created','body','usage','lifecycle','response'}) and item['id'] in calls and item['id'] not in found
                and type(item['created']) is int and item['created']>=0 and item['body']==PHYSICAL_BODY
                and item['usage']==USAGE and all(type(v) is int for v in item['usage'].values())
                and life.get('started') is True and life.get('response_status')==200
                and all(type(life[k]) is int and life[k]==0 for k in ('chunks_sent','delay_ms','after_first_chunk_delay_ms'))
                and type(life.get('started_monotonic')) in (int,float) and math.isfinite(life['started_monotonic']),'version_provider_context_identity')
            expected_response={'id':item['id'],'object':'chat.completion','created':item['created'],'model':'goal584-fake-a',
                'choices':[{'index':0,'message':{'role':'assistant','content':'Proof'},'finish_reason':'stop'}],'usage':USAGE}
            require('response' not in item or item['response']==expected_response,'version_provider_response_changed')
            common={'started','stage','started_monotonic','headers_sent','chunks_sent','usage_sent','terminal','outcome','response_status','delay_ms','after_first_chunk_delay_ms'}
            if completed:
                require(set(life)==common|{'terminal_monotonic'} and all(life[k] is True for k in ('headers_sent','usage_sent','terminal'))
                    and life['stage']==life['outcome']=='completed' and item.get('response')==expected_response
                    and type(life['terminal_monotonic']) in (int,float) and math.isfinite(life['terminal_monotonic'])
                    and life['terminal_monotonic']>=life['started_monotonic'],'version_provider_completion')
            else:
                require(set(life)==common and life['terminal'] is False and life['outcome'] is None
                    and life['stage']=='headers_sent' and life['headers_sent'] is True and life['usage_sent'] is False,'version_provider_pending_shape')
                provider_ready=False
            found.add(item['id'])
        previous_provider={r['id']:r for r in state.get('provider_rows',[])}
        current_provider={r['id']:r for r in physical['requests']}
        require(previous_provider.keys()<=current_provider.keys() and all(encoded(current_provider[k])==encoded(v) for k,v in previous_provider.items()),'version_old_provider_changed')
        for row in budget.values():
            observed=Decimal(str(row.get('spend')))
            require(observed.is_finite() and 0<=observed<=expected+Decimal('.000000001'),'version_counter_surplus')
        if not provider_ready or len(rows)!=len(calls) or any(not close_amount(row.get('spend'),expected) for row in budget.values()):return None
        if n.poll_deadline is not None:require(time.monotonic()<n.poll_deadline,'version_late_settlement')
        state['rows']=rows;state['budgets']=budget;state['provider_rows']=physical['requests'];persist(state)
        return {'rows':[verified_row(r,state,calls[r['request_id']]) for r in rows], 'user_spend':str(budget['user']['spend']),
            'key_spend':str(budget['key']['spend']), 'raw_row_count':len(rows),'physical_calls':len(found),
            'protected_budget_sha256':sha(encoded(protected(budget))),'provider_body':PHYSICAL_BODY}
    return n.poll('version full history and counters',ready)


def worker(action,label=None,project=None):
    import yaml
    source_binding()
    if action=='prepare':
        require(not STATE.exists(),'version_fresh_private_state')
        attest=read_private(ATTEST);base=yaml.safe_load(CONFIG.read_bytes())
        catalog.profile(argparse.Namespace(project=project),attest,base)
        n=native();state={'schema':1,'proof':PROOF,'project':project,'base_config':base,'base_bytes':base64_bytes(CONFIG.read_bytes()),
            'native_artifact':catalog.native_sdk.identity(),'started_at':n.started_at.isoformat(),'approved':{},'calls':[]}
        obs=catalog.catalog_projection(fixture(n,state).provider('/observations'))
        require(obs['variant']=='S1' and not catalog.status_projection(n.ok('GET',catalog.STATUS))['scheduled']
            and catalog.source_projection(n.ok('GET',catalog.SOURCE))['source_revision']==catalog.DOCUMENTS['S2'][1],'version_requires_completed_catalog_gate')
        baseline_provider=fixture(n,state).provider('/requests')
        require(baseline_provider['requests']==[],'version_fresh_inference_history')
        user=str(uuid4());state['user_id']=user;persist(state)
        n.ok('POST','/user/new',body={'user_id':user,'user_role':'internal_user','models':['goal584-a'],'max_budget':20,
            'budget_duration':'1mo','auto_create_key':False,'send_invite_email':False,'teams':[]})
        result=n.ok('POST','/key/generate',body={'user_id':user,'models':['goal584-a'],'max_budget':20,'budget_duration':'1mo',
            'duration':None,'key_alias':project+'-versions','allowed_routes':['llm_api_routes']})
        token=result.get('key');require(isinstance(token,str) and token.startswith('sk-'),'version_generated_key')
        state.update(key=token,key_hash=sha(token.encode()));persist(state)
        state['baseline_budget']=budgets(n,state);persist(state)
        baseline_rows=logged_rows(n,state)
        require(baseline_rows==[] and all(Decimal(str(v.get('spend')))==0 for v in state['baseline_budget'].values()),'version_initial_native_spend')
        state.update(rows=baseline_rows,provider_rows=baseline_provider['requests']);persist(state)
        return {'stage':'prepared','user_id':user,'key_hash':state['key_hash'],'identity':identity(n,state,'base')}
    state=read_private(STATE)
    require(type(state.get('schema')) is int and state['schema']==1 and state.get('proof')==PROOF
        and state.get('project')==project==os.environ.get('PROOF_PRICING_PROJECT')
        and str(UUID(state['user_id']))==state['user_id'] and sha(state['key'].encode())==state['key_hash'],'version_private_proof')
    n=native(state)
    if action=='approve':
        require(label in ('v1','v2'),'version_approve_label')
        require(len(state['calls'])==(0 if label=='v1' else 2) and len(state['rows'])==len(state['calls']),'version_publication_requires_drain')
        value=publication(state['base_config'],label,state['project'],datetime.now(timezone.utc).isoformat().replace('+00:00','Z'))
        approved=approve(state['approved'],value,state['base_config']);persist(state)
        if label=='v1':
            reuse=copy.deepcopy(value);next(m for m in reuse['model_list'] if m['model_name']=='goal584-a')['model_info']['input_cost_per_token']=.02
            try:approve(state['approved'],reuse,state['base_config'])
            except ProofError as e:require(str(e)=='version_id_reused_with_changed_terms','version_wrong_reuse_rejection')
            else:raise ProofError('version_reuse_guard_failed')
        descriptor=next(m['model_info']['owui_pricing'] for m in value['model_list'] if m['model_name']=='goal584-a')
        return {'stage':'approved','version':label,'declaration':descriptor,'config_semantic_sha256':approved['config_sha256'],'same_id_changed_terms_rejected':label=='v1'}
    if action=='identity':return {'stage':'identity','identity':identity(n,state,label)}
    if action=='reload':
        require(label in ('S1','S2'),'version_catalog_label')
        helper=fixture(n,state)
        require(catalog.catalog_projection(helper.provider('/control',{'variant':label}))['variant']==label,'version_catalog_control')
        result=n.ok('POST',catalog.RELOAD)
        require(result.get('source_revision')==catalog.DOCUMENTS[label][1] and result.get('etag')=='"'+catalog.DOCUMENTS[label][0]+'"','version_native_reload')
        return {'stage':'reloaded','source':catalog.source_projection(n.ok('GET',catalog.SOURCE))}
    if action=='call':
        require(label in LABELS and len(state['calls'])==LABELS.index(label) and label not in state.get('attempted',[]),'version_call_order_or_retry')
        index=LABELS.index(label);selected,cost,_=EXPECTED[index];identity(n,state,selected)
        require(catalog.source_projection(n.ok('GET',catalog.SOURCE))['source_revision']==catalog.DOCUMENTS[label.split('_')[1]][1],'version_call_catalog_source')
        root=n.run_id+'-answer-'+uuid4().hex[:12];chat=state['user_id']+'-chat'
        body={'model':'goal584-a','messages':[{'role':'user','content':'Hi'}],'max_tokens':5,'stream':False,
            'metadata':{'session_id':chat,'spend_logs_metadata':{'chat_id':chat,'root_answer_id':root,'call_kind':'synthetic_chat'}}}
        state.setdefault('attempted',[]).append(label);state.setdefault('inputs',[]).append(body);persist(state)
        code,result,headers=n.request('POST','/v1/chat/completions',token=state['key'],body=body)
        state.setdefault('responses',[]).append({'status':code,'payload':result});persist(state)
        require(code==200 and isinstance(result.get('id'),str) and TOKEN_ID.fullmatch(result['id']) and result.get('usage')==USAGE
            and all(type(v) is int for v in result['usage'].values()),'version_native_response')
        if headers.get('x-litellm-response-cost') not in (None,'','None'):
            require(close_amount(headers['x-litellm-response-cost'],Decimal(cost)),'version_native_cost_header')
        require(all(c['request_id']!=result['id'] for c in state['calls']),'version_duplicate_native_id')
        state['calls'].append({'request_id':result['id'],'deployment_id':'goal584-price-a-'+selected,'cost':cost,'chat_id':chat,'root_answer_id':root});persist(state)
        return {'stage':label,'financial':settle(n,state)}
    if action=='drain':return {'stage':'drained','financial':settle(n,state)}
    if action=='restore_catalog':
        require(catalog.catalog_projection(fixture(n,state).provider('/control',{'variant':'S1'}))['variant']=='S1','version_restore_catalog')
        return {'stage':'catalog_restored','scope':'fixture S1 only; no global native map rollback'}
    raise ProofError('version_unknown_worker_action')


def overwrite(path,raw):
    before=path.stat();require(not path.is_symlink() and len(raw)<=128*1024,'version_config_path')
    with path.open('r+b') as handle:handle.seek(0);handle.write(raw);handle.truncate();handle.flush();os.fsync(handle.fileno())
    require(path.read_bytes()==raw and path.stat().st_ino==before.st_ino,'version_config_inode_readback')


class Host(ComposeDriver):
    def __init__(self,args):
        super().__init__(args);self.receipt={'schema':1,'proof':PROOF,'passed':False,'stage':'bind','workers':[],'restoration':{}}
        self.private=args.private_root;self.config=self.private/'config.yaml'
        self.owned_services=None

    def invoke(self,action,label=None):
        command=self.command+['exec','-T','--index','1','proxy','python','-B','/proof/prove_pricing_versions.py','--worker-action',action,'--project',self.args.project]
        if label:command+=['--label',label]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=90)
        require(len(result.stdout)<=catalog.MAX_BYTES,'version_worker_packet_size')
        try:value=json.loads(result.stdout)
        except (ValueError,UnicodeError):raise ProofError('version_worker_packet_json') from None
        require(isinstance(value,dict) and set(value)=={'schema','proof','passed','action','result','failure_code'}
            and type(value['schema']) is int and value['schema']==1 and type(value['passed']) is bool and value['proof']==PROOF and value['action']==action,'version_worker_protocol')
        self.receipt['workers'].append(value)
        require(result.returncode==0 and value['passed'] is True,'version_worker_failed')
        return value['result']

    def topology(self):
        require(isinstance(CALLBACK_SHA256,str) and re.fullmatch('[0-9a-f]{64}',CALLBACK_SHA256),'version_callback_freeze_required')
        revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,timeout=10).decode().strip()
        require(revision==os.environ.get('PROOF_SOURCE_COMMIT'),'version_host_tested_git')
        expected={}
        for name,path in SOURCE_PATHS.items():
            raw=(ROOT/path).read_bytes()
            require(raw==subprocess.check_output(['git','-c','gc.auto=0','show',revision+':'+path],cwd=ROOT,timeout=10,env={**os.environ,'GIT_NO_LAZY_FETCH':'1'}),'version_host_source_git_drift')
            expected[name]=sha(raw)
        require(expected['pricing_snapshot.py']==CALLBACK_SHA256 and expected['prove_pricing_catalog.py']==CATALOG_SHA256
            and all(expected[k]==v for k,v in catalog.HELPERS.items()),'version_host_frozen_sources')
        ids=subprocess.check_output(self.command+['ps','-q'],cwd=ROOT,timeout=15).decode().split()
        require(len(ids)==len(set(ids))==4 and all(re.fullmatch('[0-9a-f]{64}',v) for v in ids),'version_host_four_containers')
        template='{"id":"{{.Id}}","image_ref":"{{.Config.Image}}","image_id":"{{.Image}}","health":"{{.State.Health.Status}}","project":"{{index .Config.Labels "com.docker.compose.project"}}","service":"{{index .Config.Labels "com.docker.compose.service"}}","number":"{{index .Config.Labels "com.docker.compose.container-number"}}","network":"{{.HostConfig.NetworkMode}}","mounts":{{json .Mounts}},"command":{{json .Config.Cmd}}}'
        rows=[self.run_json(['docker','inspect','--format',template,v]) for v in ids]
        require(all(r['id']==identifier for identifier,r in zip(ids,rows))
            and len({r['id'] for r in rows})==4 and {r['id'] for r in rows}==set(ids),'version_host_inspect_ids')
        require({r['service'] for r in rows}=={'proxy','postgres','provider','redis'} and all(r['project']==self.args.project
            and r['number']=='1' and r['network']==self.args.project+'_proof' and r['health']=='healthy'
            and r['image_ref']==(catalog.native_sdk.image_ref() if r['service']=='proxy' else catalog.IMAGES[r['service']]) for r in rows),'version_host_container_binding')
        proxy=next(r for r in rows if r['service']=='proxy')
        if catalog.native_sdk.variant()!='stock':
            require(proxy['image_id']==catalog.native_sdk.image_ref(),'version_host_native_image_id')
        services={r['service']:(r['id'],r['image_id']) for r in rows if r['service']!='proxy'}
        if self.owned_services is None:self.owned_services=services
        require(services==self.owned_services,'version_nonproxy_container_changed')
        require(proxy['command']==catalog.COMMAND,'version_host_proxy_command')
        # Compose owns the complete mount set, including the base proof helpers.
        # Resolved configuration contains private environment values; retain only
        # proxy volumes and never pass the full document to evidence or safe().
        result=subprocess.run(self.command+['config','--format','json'],cwd=ROOT,capture_output=True,timeout=30)
        require(result.returncode==0 and len(result.stdout)<=catalog.MAX_BYTES,'version_host_compose_config')
        try:volumes=json.loads(result.stdout)['services']['proxy']['volumes']
        except (ValueError,UnicodeError,KeyError,TypeError):raise ProofError('version_host_compose_config') from None
        require(isinstance(volumes,list) and all(isinstance(m,dict) for m in volumes),'version_host_compose_volumes')
        declared=[m for m in volumes if m.get('type')=='bind']
        require(len({m.get('target') for m in volumes})==len(volumes)
            and len({m.get('Destination') for m in proxy['mounts']})==len(proxy['mounts']),'version_host_duplicate_mount_destination')
        mounts={m['Destination']:m for m in proxy['mounts'] if m['Type']=='bind'}
        require(set(mounts)=={m['target'] for m in declared} and all(
            Path(mounts[m['target']]['Source']).resolve()==Path(m['source']).resolve()
            and type(mounts[m['target']]['RW']) is bool and type(m.get('read_only',False)) is bool
            and mounts[m['target']]['RW'] is (not m.get('read_only',False))
            and mounts[m['target']]['RW'] is (m['target']=='/proof-private') for m in declared),'version_host_compose_bindings')
        require('/proof/config.yaml' in mounts and Path(mounts['/proof/config.yaml']['Source']).resolve()==self.config.resolve()
            and mounts['/proof/config.yaml']['RW'] is False and '/proof-private' in mounts
            and Path(mounts['/proof-private']['Source']).resolve()==self.private.resolve()
            and mounts['/proof-private']['RW'] is True,'version_host_private_mounts')
        require(all('/proof/'+name in mounts and Path(mounts['/proof/'+name]['Source']).resolve()==(ROOT/path).resolve()
            and mounts['/proof/'+name]['RW'] is False for name,path in SOURCE_PATHS.items()),'version_host_source_mounts')
        code='import hashlib,json,pathlib,sys;print(json.dumps({p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in sys.argv[1:]}))'
        actual=self.run_json(self.command+['exec','-T','--index','1','proxy','python','-B','-c',code,*('/proof/'+n for n in expected)])
        require(actual=={'/proof/'+n:h for n,h in expected.items()},'version_actual_worker_source_readback')
        safe=[{k:r[k] for k in ('id','service','number','image_ref','image_id','health','network')} for r in rows]
        self.receipt.setdefault('topologies',[]).append(safe)
        return proxy

    def restart(self):
        for argv,timeout in ((['restart','proxy'],90),(['up','-d','--no-deps','--wait','--wait-timeout','180','proxy'],210)):
            result=subprocess.run(self.command+argv,cwd=ROOT,capture_output=True,timeout=timeout)
            require(result.returncode==0,'version_proxy_restart')
        return self.topology()

    def execute(self):
        import yaml
        original=self.config.read_bytes();require(0<len(original)<=128*1024,'version_original_config_size')
        attempted=False;failure=None
        try:
            before=self.topology();self.invoke('prepare')
            write_private(self.private/'pricing-original.private.json',{'schema':1,'bytes':base64_bytes(original)})
            for version,labels in (('v1',('v1_S1','v1_S2')),('v2',('v2_S2',))):
                if version=='v2':self.invoke('drain')
                self.receipt['stage']='approve_'+version
                approved=self.invoke('approve',version)
                candidate=publication(yaml.safe_load(original),version,self.args.project,approved['declaration']['source_checked_at_utc'])
                require(next(m['model_info']['owui_pricing'] for m in candidate['model_list'] if m['model_name']=='goal584-a')==approved['declaration'],'version_approved_declaration')
                raw=yaml.safe_dump(candidate,sort_keys=False,allow_unicode=True).encode('utf8')
                require(sha(encoded(yaml.safe_load(raw)))==approved['config_semantic_sha256'],'version_publication_hash')
                attempted=True;self.receipt['stage']='publish_'+version;overwrite(self.config,raw)
                proxy=self.restart();observed=self.invoke('identity',version)['identity']
                require(observed['config_sha256']==sha(raw) and observed['worker_id_prefix']==proxy['id'][:12]
                    and proxy['image_id']==before['image_id'],'version_actual_publication_identity')
                self.receipt.setdefault('publications',[]).append({'version':version,'config_sha256':sha(raw),
                    'deployment_id':observed['model_A']['id'],'observed_identity':observed,
                    'declaration_is_not_atomic_activation':True})
                for label in labels:
                    self.receipt['stage']='reload_'+label;self.invoke('reload',label.split('_')[1])
                    self.receipt['stage']='call_'+label;self.invoke('call',label)
            self.receipt['stage']='qualified';self.receipt['final']=self.invoke('drain')
            self.receipt['v1_retirement']={'old_deployment_id':'goal584-price-a-v1','declared_until_stays_null':True,
                'observed_retired_before_v2':True,'not_an_atomic_global_cutover':True}
        except Exception as error:failure=error
        finally:
            errors=[]
            if attempted:
                try:overwrite(self.config,original);self.restart();value=self.invoke('identity','base')['identity'];require(value['config_sha256']==sha(original),'version_original_restore')
                except Exception:errors.append('config_or_restart_restore_failed')
                try:self.invoke('restore_catalog')
                except Exception:errors.append('catalog_restore_failed')
            try:original_equal=self.config.read_bytes()==original
            except Exception:original_equal=False;errors.append('original_config_readback_failed')
            self.receipt['restoration']={'attempted':attempted,'failures':errors,'original_bytes_equal':original_equal,
                'native_global_map_restored':False}
            if failure is None and errors:failure=ProofError('version_restoration_failed')
        if failure:raise failure
        self.receipt['passed']=True
        return self.receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker-action',choices=('prepare','approve','identity','reload','call','drain','restore_catalog'))
    parser.add_argument('--label');parser.add_argument('--project',required=True)
    parser.add_argument('--env-file',type=Path);parser.add_argument('--private-root',type=Path)
    parser.add_argument('--compose-file',action='append',default=[]);parser.add_argument('--receipt',type=Path)
    args=parser.parse_args();packet={'schema':1,'proof':PROOF,'passed':False,'action':args.worker_action,'result':None,'failure_code':None};host=None
    try:
        if args.worker_action:packet['result']=worker(args.worker_action,args.label,args.project)
        else:
            require(re.fullmatch('goal584-pricing-[0-9a-f]{12}',args.project) and args.env_file and args.env_file.is_file() and not args.env_file.is_symlink()
                and args.private_root and args.private_root.is_absolute() and args.private_root.is_dir() and not args.private_root.is_symlink()
                and args.receipt and not args.receipt.exists() and not args.receipt.is_symlink() and not args.receipt.parent.is_symlink()
                and not args.receipt.resolve().is_relative_to(args.private_root.resolve()) and not args.private_root.resolve().is_relative_to(args.receipt.parent.resolve())
                and args.compose_file and all((ROOT/p).resolve().is_relative_to(ROOT) and (ROOT/p).is_file() for p in args.compose_file),'version_host_arguments')
            if os.name=='posix':require(all(stat.S_IMODE(p.stat().st_mode)&0o077==0 for p in (args.private_root,args.env_file,args.private_root/'config.yaml')),'version_host_private_modes')
            host=Host(args);packet['result']=host.execute()
        packet['passed']=True
    except Exception as e:
        packet['failure_code']=str(e) if isinstance(e,ProofError) and re.fullmatch('[a-z_]{1,80}',str(e)) else 'version_external_failure'
        if host:packet['result']=host.receipt
    try:
        raw=encoded(packet)
        require(not re.search(rb'(?:sk-|gw-|Bearer\s)[A-Za-z0-9_-]{12,}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',raw),'version_public_credentials')
        if host:
            args.receipt.parent.mkdir(parents=True,exist_ok=True);args.receipt.write_bytes(raw+b'\n')
    except Exception:
        result=packet.get('result')
        stage=result.get('stage') if isinstance(result,dict) else None
        packet['passed']=False
        packet['failure_code']=packet['failure_code'] or 'version_receipt_write_failed'
        packet['result']={'receipt_write_failure':'version_receipt_write_failed'}
        if isinstance(stage,str) and re.fullmatch('[a-zA-Z0-9_]{1,80}',stage):packet['result']['stage']=stage
        raw=encoded(packet)
    print(raw.decode());return 0 if packet['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
