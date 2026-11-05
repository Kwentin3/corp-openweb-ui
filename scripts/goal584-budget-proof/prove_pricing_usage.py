"""Finite native Responses usage evidence; unknown usage is observation, not policy.

Run only in the separately attested four-service pricing stand after versions.
No calculator, new ledger, callback changes, retry, reset or provider selection.
"""
from __future__ import annotations

import argparse
import base64
import copy
from datetime import datetime, timezone
from decimal import Decimal
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import time
from uuid import UUID, uuid4

import prove_pricing_versions as versions
from prove_native_budgets import ProofError, close_amount, require
from prove_gateway_auth import read_private, write_private

PROOF='goal584-native-pricing-used-categories'
ROOT=versions.ROOT
STATE=versions.PRIVATE/'pricing-usage.private.json'
SOURCE_PATHS=versions.SOURCE_PATHS|{'prove_pricing_usage.py':'scripts/goal584-budget-proof/prove_pricing_usage.py'}
ALIASES=('goal584-usage','goal584-usage-absent','goal584-usage-null')
WIRES=('goal584-fake-usage','goal584-fake-usage-absent','goal584-fake-usage-null')
LABELS=('positive_v1','positive_v2','usage_absent','usage_null')
RAW_USAGE={'input_tokens':10,'output_tokens':5,'total_tokens':15,
    'input_tokens_details':{'cached_tokens':6},'output_tokens_details':{'reasoning_tokens':2}}
NATIVE=versions.catalog.NATIVE|{
    'router.py':'2bcf70b609d63f231667eace7191a497a5a5179a74741fa5bdb9413d4533fbcd',
    'responses/main.py':'8145d27e6d2dcb81c7fd4473376dcb0ef30524bd7f4c1ff8a324b6c5b04ccdfb',
    'responses/utils.py':'7868c7db9bf7835249a4a8a2573559881f18cf5988c0c33e0dd599821648dc99',
    'cost_calculator.py':'6dd7a7f7a0be8abe172e8efd01a1aae541d56b71d57ccc296d18f880685d104f',
    'litellm_core_utils/llm_cost_calc/utils.py':'9b936ab501e0937a704970a2171288722a79b40f5d30c570bb999c70a0a40a55',
    'litellm_core_utils/litellm_logging.py':'58da82171935240b9280d8c208d383e147e23fb2ad4818de6994934ebf21fe79',
    'proxy/spend_tracking/spend_tracking_utils.py':'52ce53917cdb6905abfe6dd61f2ffe9640e5198c9e443629177dcc727d24bd17',
    'proxy/litellm_pre_call_utils.py':'8cb60a5bb2e3d521dce4ded40020b02106d821837b0928a8e36c6dbede4b82c8',
    'proxy/hooks/responses_id_security.py':'7a248a55712f7ff17b1375e18784ec5e411d09bc8a63aea3083798c3cfe4a4b8',
    'proxy/common_utils/encrypt_decrypt_utils.py':'454c5aace6c7c0d929db5309c3a6cdd949f212863f1a37f0b08ede749f217ebe',
    'litellm_core_utils/llm_cost_calc/guardrail_cost.py':'0073388494a89d636ea7f5bd3ee5d14d89c018403faad39814a0327ae9405246'}
sha=versions.sha
encoded=versions.encoded


def save(state):
    encoded(state);write_private(STATE,state)


def declaration(alias,version):
    # Finite agreed fixture terms, not a price lookup or usage classifier.
    require(alias in ALIASES and version in ('v1','v2'),'usage_declaration_profile')
    return {'schema':1,'deployment_id':alias+'-'+version,'currency':'USD',
        'source_ref':'fixture:usage-agreed-'+alias+'-'+version,
        'source_url':'https://example.invalid/goal584/usage/agreed/'+alias+'/'+version,
        'source_checked_at_utc':'2026-11-04T00:00:00Z','declared_effective_from_utc':'2026-11-04T00:00:00Z',
        'declared_effective_until_utc':None,'activation_ref':'fixture:usage-activation-'+alias+'-'+version,
        'qualified_usage':'text_cache_reasoning'}


def configuration(base,version):
    require(version in ('v1','v2'),'usage_configuration_version')
    require({m['model_name'] for m in base['model_list']}=={'goal584-a','goal584-b'},'usage_base_models')
    result=copy.deepcopy(base)
    for index,(alias,wire) in enumerate(zip(ALIASES,WIRES)):
        identifier=alias+'-'+(version if index==0 else 'v1')
        result['model_list'].append({'model_name':alias,'litellm_params':{'model':'openai/'+wire,
            'api_base':'http://provider:8000/v1','api_key':'synthetic-provider-only-not-a-credential'},
            'model_info':{'id':identifier,'mode':'responses','max_input_tokens':10,'max_output_tokens':16,'max_tokens':26,
                'input_cost_per_token':.01,'output_cost_per_token':.02,
                'cache_read_input_token_cost':.001 if version=='v1' or index else .009,
                'output_cost_per_reasoning_token':.03 if version=='v1' or index else .09,
                'owui_pricing':declaration(alias,version if index==0 else 'v1')}})
    return result


def fixture(native,state):
    owner=versions.catalog.Coordinator(native,STATE,{'stage':'usage','observations':[]})
    owner.private=state
    return owner


def population(native):
    # Thin DTO adapter; native GET owns authorization/filtering/pagination.
    users=[];total=None
    for page in range(1,11):
        value=native.ok('GET','/user/list',query={'page':page,'page_size':100,'sort_by':'user_id','sort_order':'asc'})
        require(isinstance(value.get('users'),list) and type(value.get('total')) is int
            and 0<=value['total']<=16 and type(value.get('total_pages')) is int
            and 0<=value['total_pages']<=10 and value.get('page')==page,'usage_population_page')
        if total is None:total=value['total']
        require(total==value['total'],'usage_population_changed')
        users.extend(row['user_id'] for row in value['users'])
        if page>=value['total_pages']:break
    require(len(users)==len(set(users))==total and all(type(uid) is str for uid in users),'usage_population_identity')
    return sorted(users)


def histories(native,users):
    result={}
    for uid in users:
        profile=native.user_info(uid)
        require(isinstance(profile.get('keys'),list),'usage_old_keys')
        profile['keys']=sorted(profile['keys'],key=lambda row:row['token'])
        result[uid]={'profile':profile,'rows':sorted(native.logs(uid),key=lambda row:row['request_id'])}
    return result


def policy(value):
    mutable={'spend','total_spend','updated_at','last_active','last_used_at'}
    result=copy.deepcopy(value)
    for row in (result['user'],*result['keys'].values(),*result['user']['keys']):
        for field in mutable:row.pop(field,None)
    return result


def budget(native,state):
    user=native.user_info(state['user_id']);keys={}
    require(user.get('user_id')==state['user_id'] and user.get('user_role')=='internal_user'
        and user.get('models')==list(ALIASES) and not user.get('teams'),'usage_user_identity')
    embedded=user.get('keys');require(isinstance(embedded,list) and len(embedded)==3,'usage_embedded_keys')
    user['keys']=sorted(embedded,key=lambda item:item.get('token',''))
    for alias in ALIASES:
        key=state['keys'][alias];payload=native.ok('GET','/key/info',query={'key':key['hash']});info=payload.get('info')
        require(payload.get('key')==key['hash'] and isinstance(info,dict) and 'token' not in info
            and info.get('user_id')==state['user_id'] and info.get('models')==[alias]
            and info.get('team_id') is None and info.get('allowed_routes')==['llm_api_routes'],'usage_key_identity')
        require(sum(item.get('token')==key['hash'] and item.get('user_id')==state['user_id']
            and item.get('models')==[alias] for item in embedded)==1,'usage_embedded_identity')
        keys[alias]=info
    for row in (user,*keys.values(),*embedded):
        require(close_amount(row.get('max_budget'),Decimal(20)) and row.get('budget_duration')=='1mo'
            and isinstance(row.get('budget_reset_at'),str),'usage_caps_period')
        for name in ('spend','total_spend'):
            if name in row:
                amount=Decimal(str(row[name]));require(amount.is_finite() and 0<=amount<=20,'usage_invalid_counter')
    return {'user':user,'keys':keys}


def identity(native,state,label):
    import yaml
    versions.source_binding()
    require(label in ('base','v1','v2') and state['project']==os.environ.get('PROOF_PRICING_PROJECT'),'usage_identity_label')
    expected=state['base'] if label=='base' else configuration(state['base'],label)
    require(yaml.safe_load(versions.CONFIG.read_bytes())==expected,'usage_config_readback')
    package=Path(importlib.util.find_spec('litellm').origin).parent
    require({name:sha((package/name).read_bytes()) for name in NATIVE}==NATIVE,'usage_native_sources')
    sdk=versions.catalog.native_sdk.inspect_sources()
    require(sdk['native_artifact']==state['native_artifact'],'usage_native_artifact')
    rows=native.ok('GET','/model/info').get('data')
    require(isinstance(rows,list) and len(rows)==len(expected['model_list'])
        and {row['model_name'] for row in rows}=={m['model_name'] for m in expected['model_list']},'usage_model_set')
    actual={row['model_name']:row['model_info'] for row in rows}
    for model in expected['model_list']:
        require(all(actual[model['model_name']].get(key)==value for key,value in model['model_info'].items()),'usage_model_info')
    source=versions.catalog.source_projection(native.ok('GET',versions.catalog.SOURCE))
    schedule=versions.catalog.status_projection(native.ok('GET',versions.catalog.STATUS))
    require({k:v for k,v in source.items() if k not in ('loaded_at','model_count')}=={k:v for k,v in state['source'].items() if k not in ('loaded_at','model_count')}
        and schedule==state['schedule'] and not schedule['scheduled'],'usage_source_schedule_changed')
    return {'config_sha256':sha(versions.CONFIG.read_bytes()),'config_semantic_sha256':sha(encoded(expected)),
        'worker_id_prefix':os.environ.get('HOSTNAME'),'native_artifact':sdk['native_artifact'],
        'server_runtime_model_count':source['model_count'],
        'native_sources':NATIVE,'source_schedule_sha256':sha(encoded([source,schedule])),
        'bindings':{name:sha((Path('/proof')/name).read_bytes()) for name in SOURCE_PATHS}}


def scalar(value):
    kinds={type(None):'missing',bool:'bool',int:'int',float:'float',str:'str',dict:'dict',list:'list'}
    return {'type':kinds.get(type(value),'other'),**({'value':value} if type(value) in (int,float)
        and abs(value)<=1_000_000_000 and math.isfinite(value) else {})}


def valid_usage(value):
    return isinstance(value,dict) and all(type(value.get(key)) is int and value[key]==RAW_USAGE[key]
        for key in ('input_tokens','output_tokens','total_tokens')) and all(isinstance(value.get(key),dict)
        and type(value[key].get(field)) is int and value[key][field]==expected
        for key,field,expected in (('input_tokens_details','cached_tokens',6),('output_tokens_details','reasoning_tokens',2)))


def usage_observation(value):
    usage=value if isinstance(value,dict) else {}
    result={key:scalar(usage.get(key)) for key in ('input_tokens','output_tokens','total_tokens')}
    for detail,field in (('input_tokens_details','cached_tokens'),('output_tokens_details','reasoning_tokens')):
        nested=usage.get(detail);result[field]=scalar(nested.get(field) if isinstance(nested,dict) else None)
    return result


def row_metadata(row):
    value=row.get('metadata')
    try:return json.loads(value) if isinstance(value,str) else value
    except (ValueError,UnicodeError):return None


def row_observation(row):
    meta=row_metadata(row);inner=meta.get('spend_logs_metadata') if isinstance(meta,dict) else None
    rates=inner.get('owui_billed_token_rates') if isinstance(inner,dict) else None
    descriptor=inner.get('owui_tariff_descriptor') if isinstance(inner,dict) else None
    error=meta.get('error_information') if isinstance(meta,dict) else None;error=error if isinstance(error,dict) else {}
    availability=lambda value:value if value in ('available','unknown','partial') else 'other'
    return {'request_id_sha256':sha(encoded(row.get('request_id'))),'full_row_sha256':sha(encoded(row)),
        'status':row.get('status') if row.get('status') in ('success','failure') else 'other','spend':scalar(row.get('spend')),
        'usage':{key:scalar(row.get(key)) for key in versions.USAGE},
        'rate_availability':availability(rates.get('availability')) if isinstance(rates,dict) else 'missing',
        'descriptor_availability':availability(descriptor.get('availability')) if isinstance(descriptor,dict) else 'missing',
        'descriptor_reason':descriptor.get('reason') if isinstance(descriptor,dict) and descriptor.get('reason') in versions.descriptor_unknown_reasons() else 'other',
        'error_class':error.get('error_class') if error.get('error_class') in ('InternalServerError','BadRequestError','BudgetExceededError','ValueError','TypeError','ResponseValidationError') else 'other' if error.get('error_class') is not None else 'missing',
        'error_code':error.get('error_code') if error.get('error_code') in ('400','422','500') else 'other' if error.get('error_code') is not None else 'missing',
        'rates':{key:scalar(rates.get('rates',{}).get(key)) for key in versions.rate_fields()} if isinstance(rates,dict) and isinstance(rates.get('rates'),dict) else None,
        'model_group':row.get('model_group') if row.get('model_group') in ALIASES else 'other',
        'lineage_present':isinstance(inner,dict) and all(isinstance(inner.get(key),str) for key in ('chat_id','root_answer_id','call_kind'))}


def valid_response_id(value):
    return type(value) is str and value.startswith('resp_') and 5<len(value)<=4096 and all(32<ord(c)<127 for c in value)


def physical_response_identity(call):
    record=call.get('provider_record');response=record.get('response') if isinstance(record,dict) else None
    return isinstance(record,dict) and isinstance(response,dict) and valid_response_id(call.get('provider_id')) \
        and record.get('id')==response.get('id')==call['provider_id']


def positive_row_diagnostic(row,state,call):
    # Fixed safe failure evidence only; the validator below owns acceptance.
    payload=call['response'];identifier=lambda value:sha(encoded(value)) if type(value) is str and len(value)<=4096 else None
    record=call.get('provider_record');record=record if isinstance(record,dict) else {}
    response=record.get('response');response=response if isinstance(response,dict) else {}
    try:cost_matches=bool(close_amount(row.get('spend'),Decimal(call['cost'])))
    except Exception:cost_matches=False
    checks={'response_id_shape':valid_response_id(row.get('request_id')) and valid_response_id(payload.get('id')),
        'response_id':row.get('request_id')==payload.get('id'),'physical_response_id':physical_response_identity(call),
        'user':row.get('user')==state['user_id'],'key':row.get('api_key')==state['keys'][ALIASES[0]]['hash'],
        'model_group':row.get('model_group')==ALIASES[0],'model_id':row.get('model_id')==call['deployment'],
        'model':row.get('model') in (ALIASES[0],WIRES[0],'openai/'+WIRES[0]),'status':row.get('status')=='success','cost':cost_matches,
        **{key:type(row.get(key)) is int and row[key]==value for key,value in versions.USAGE.items()}}
    try:observation=row_observation(row)
    except Exception:observation=None
    return {'checks':checks,'row':observation,'identity_sha256':{
        'row_response':identifier(row.get('request_id')),'client_response':identifier(payload.get('id')),
        'physical_response':identifier(call.get('provider_id')),'retained_record_id':identifier(record.get('id')),
        'retained_record_response':identifier(response.get('id')),'row_deployment':identifier(row.get('model_id')),
        'expected_deployment':identifier(call['deployment']),'row_model':identifier(row.get('model'))}}


def positive_row(row,state,call):
    # Proxy ID security owns the advertised ID; preserve it opaque. Existing physical()
    # binds each serial dispatch to its immutable terminal provider record before this read.
    payload=call['response']
    try:
        require(valid_response_id(row.get('request_id')) and valid_response_id(payload.get('id'))
            and row.get('request_id')==payload.get('id') and physical_response_identity(call)
            and row.get('user')==state['user_id'] and row.get('api_key')==state['keys'][ALIASES[0]]['hash']
            and row.get('model_group')==ALIASES[0] and row.get('model_id')==call['deployment']
            and row.get('model') in (ALIASES[0],WIRES[0],'openai/'+WIRES[0])
            and row.get('status')=='success' and close_amount(row.get('spend'),Decimal(call['cost']))
            and all(type(row.get(key)) is int and row[key]==value for key,value in versions.USAGE.items()),'usage_positive_identity_cost')
    except ProofError as error:
        if error.args==('usage_positive_identity_cost',):
            try:error.positive_row_diagnostic=positive_row_diagnostic(row,state,call)
            except Exception:pass  # Diagnostic failure must retain the original proof failure.
        raise
    inner=versions.decode_metadata(row)
    require(all(inner.get(key)==value for key,value in call['lineage'].items()) and row.get('session_id')==call['lineage']['chat_id'],'usage_positive_lineage')
    snapshot=inner.get('owui_billed_token_rates')
    require(isinstance(snapshot,dict) and type(snapshot.get('schema')) is int and snapshot.get('schema')==1 and snapshot.get('availability')=='available'
        and isinstance(snapshot.get('rates'),dict) and set(snapshot['rates'])==set(versions.rate_fields()),'usage_snapshot_schema')
    versions.catalog.utc(snapshot['observed_at_utc']);rates=snapshot['rates']
    expected={'input_cost_per_token':.01,'output_cost_per_token':.02,'cache_read_input_token_cost':.001 if call['label']=='positive_v1' else .009,
        'output_cost_per_reasoning_token':.03 if call['label']=='positive_v1' else .09}
    require(all(type(value) in (int,float) and math.isfinite(value) and value>=0 for value in rates.values())
        and all(rates[key]==value for key,value in expected.items()),'usage_protected_native_rates')
    descriptor=inner.get('owui_tariff_descriptor')
    expected_descriptor=declaration(ALIASES[0],'v1' if call['label']=='positive_v1' else 'v2')
    require(type(descriptor) is dict and set(descriptor)=={'schema','availability','descriptor'}
        and type(descriptor.get('schema')) is int and descriptor['schema']==1 and descriptor.get('availability')=='available'
        and type(descriptor.get('descriptor')) is dict and encoded(descriptor['descriptor'])==encoded(expected_descriptor),
        'usage_positive_descriptor')
    require(versions.catalog.utc(snapshot['observed_at_utc'])>=versions.catalog.utc(expected_descriptor['declared_effective_from_utc']),
        'usage_before_declared_interval')
    return row_observation(row)|{'rates':copy.deepcopy(rates),'deployment_id':call['deployment'],'descriptor':copy.deepcopy(descriptor),
        'native_response_id_sha256':sha(encoded(payload['id'])),'provider_response_id_sha256':sha(encoded(call['provider_id']))}


def physical(native,state):
    current=fixture(native,state).provider('/requests');old=state['provider_before']
    require(current.get('synthetic') is True and current.get('control')==old['control'] and isinstance(current.get('requests'),list),'usage_provider_control')
    rows=current['requests'];prefix=old['requests'];calls=state['calls']
    require(len(rows)==len(prefix)+len(calls) and encoded(rows[:len(prefix)])==encoded(prefix)
        and len({row.get('id') for row in rows})==len(rows),'usage_provider_prefix_or_count')
    ready=True
    for record,call in zip(rows[len(prefix):],calls):
        index=ALIASES.index(call['alias']);body={'model':WIRES[index],'input':'Hi','max_output_tokens':16,'store':False,'stream':False}
        require(encoded(record.get('body'))==encoded(body) and isinstance(record.get('id'),str),'usage_provider_full_context')
        require(record.get('usage')==(RAW_USAGE if index==0 else None),'usage_provider_raw_usage')
        if index==0:require(valid_usage(record.get('usage')),'usage_provider_usage_types')
        life=record.get('lifecycle',{});require(life.get('response_status')==200,'usage_provider_http_status')
        ready &= life.get('terminal') is True
        if life.get('terminal') is True:
            require(life.get('outcome')=='completed' and isinstance(record.get('response'),dict),'usage_provider_terminal')
            response=record['response'];expected={'id':record['id'],'model':WIRES[index],'object':'response','status':'completed','error':None}
            require(all(key in response and response[key]==value for key,value in expected.items()),'usage_provider_response_identity')
            require(('usage' not in record['response']) if index==1 else record['response'].get('usage')==(RAW_USAGE if index==0 else None),'usage_provider_presence')
            if index==2:require('usage' in record['response'] and record['response']['usage'] is None,'usage_provider_explicit_null')
            require(life.get('usage_sent') is (index==0),'usage_provider_usage_sent')
            if index==0:require(valid_usage(record['response'].get('usage')),'usage_provider_response_usage_types')
        if 'provider_record' in call:require(encoded(call['provider_record'])==encoded(record),'usage_old_provider_changed')
        if life.get('terminal') is True:call.update(provider_id=record['id'],provider_record=copy.deepcopy(record))
    save(state);return ready


def observe(native,state):
    if not physical(native,state):return None
    ready=True;rows=native.logs(state['user_id']);current=budget(native,state)
    require(population(native)==sorted(state['old_users']+[state['user_id']])
        and encoded(histories(native,state['old_users']))==encoded(state['old_history']),'usage_old_history_changed')
    require(encoded(policy(current))==encoded(policy(state['baseline_budget'])),'usage_policy_changed')
    previous={row['request_id']:row for row in state.get('settled_rows',[])}
    require(all(any(encoded(row)==encoded(old) for row in rows) for old in previous.values()),'usage_old_row_changed')
    require(all(row.get('user')==state['user_id'] and row.get('api_key') in {key['hash'] for key in state['keys'].values()} for row in rows),'usage_foreign_raw_row')
    positives=[call for call in state['calls'] if call['alias']==ALIASES[0]];expected=Decimal(('0','.166','.500')[len(positives)])
    positive_rows=[row for row in rows if row.get('api_key')==state['keys'][ALIASES[0]]['hash']]
    require(len(positive_rows)<=len(positives) and len({row.get('request_id') for row in rows})==len(rows),'usage_extra_duplicate_row')
    projections=[]
    for row in positive_rows:
        matches=[call for call in positives if call['response'].get('id')==row.get('request_id')]
        require(len(matches)==1,'usage_unknown_positive_row');projections.append(positive_row(row,state,matches[0]))
    key=current['keys'][ALIASES[0]];embedded=next(row for row in current['user']['keys'] if row['token']==state['keys'][ALIASES[0]]['hash'])
    for row in (key,embedded):
        for name in ('spend','total_spend'):
            value=Decimal(str(row.get(name)));require(value.is_finite() and 0<=value<=expected+Decimal('.000000001'),'usage_positive_counter_surplus')
            ready &= close_amount(value,expected)
    if len(state['calls'])<=2:
        value=Decimal(str(current['user'].get('spend')));require(value.is_finite() and 0<=value<=expected+Decimal('.000000001'),'usage_user_counter_surplus')
        ready &= close_amount(value,expected)
    else:require(Decimal(str(current['user']['spend']))>=expected-Decimal('.000000001'),'usage_positive_user_spend_lost')
    state.setdefault('raw_observations',[]).append({'rows':rows,'budget':current});save(state)
    if not ready or len(positive_rows)!=len(positives):return None
    state['settled_rows']=rows;save(state)
    return {'physical_calls':len(state['calls']),'raw_row_count':len(rows),'positive_rows':projections,
        'all_rows':[row_observation(row)|{'native_key_slot':next(i for i,alias in enumerate(ALIASES) if row['api_key']==state['keys'][alias]['hash'])} for row in rows],'counters':{'user':scalar(current['user'].get('spend')),
        'keys':{alias:{field:scalar(row.get(field)) for field in ('spend','total_spend')} for alias,row in current['keys'].items()}},
        'old_history_sha256':sha(encoded(state['old_history'])),'protected_policy_sha256':sha(encoded(policy(current))),
        'unknown_rows_finality':False if len(state['calls'])>2 else True}


def worker(action,label,project):
    import yaml
    if action=='prepare':
        require(not STATE.exists(),'usage_fresh_private_state');base=yaml.safe_load(versions.CONFIG.read_bytes())
        versions.catalog.profile(argparse.Namespace(project=project),read_private(versions.ATTEST),base)
        flat=read_private(versions.STATE)
        require(flat['proof']==versions.PROOF and flat['project']==project and len(flat['calls'])==len(flat['rows'])==3
            and base64.b64decode(flat['base_bytes'])==versions.CONFIG.read_bytes(),'usage_requires_restored_versions')
        native=versions.native();native.started_at=datetime(1970,1,1,tzinfo=timezone.utc)
        state={'schema':1,'proof':PROOF,'project':project,'base':base,'started_at':native.started_at.isoformat(),
            'native_artifact':versions.catalog.native_sdk.identity(),'calls':[],'keys':{}}
        state['source']=versions.catalog.source_projection(native.ok('GET',versions.catalog.SOURCE))
        state['schedule']=versions.catalog.status_projection(native.ok('GET',versions.catalog.STATUS))
        require(not state['schedule']['scheduled'],'usage_active_schedule')
        observed=versions.catalog.catalog_projection(fixture(native,state).provider('/observations'))
        selected=[name for name in ('S1','S2') if state['source']['source_revision']==versions.catalog.DOCUMENTS[name][1]
            and state['source']['etag']=='"'+versions.catalog.DOCUMENTS[name][0]+'"']
        require(len(selected)==1 and observed['variant'] in ('S1','S2'),'usage_reference_fixture_binding')
        state['reference_fixture']={'original':observed['variant'],'source':selected[0],'arm_attempted':False};save(state)
        state['old_users']=population(native);state['old_history']=histories(native,state['old_users'])
        state['provider_before']=fixture(native,state).provider('/requests');before=identity(native,state,'base')
        state['user_id']=str(uuid4());save(state)
        native.ok('POST','/user/new',body={'user_id':state['user_id'],'user_role':'internal_user','models':list(ALIASES),
            'max_budget':20,'budget_duration':'1mo','auto_create_key':False,'send_invite_email':False,'teams':[]})
        for alias in ALIASES:
            key=native.ok('POST','/key/generate',body={'user_id':state['user_id'],'models':[alias],'max_budget':20,'budget_duration':'1mo',
                'duration':None,'key_alias':project+'-'+alias,'allowed_routes':['llm_api_routes']}).get('key')
            require(isinstance(key,str) and key.startswith('sk-'),'usage_minted_key');state['keys'][alias]={'token':key,'hash':sha(key.encode())};save(state)
        state['baseline_budget']=budget(native,state);require(native.logs(state['user_id'])==[],'usage_fresh_rows');save(state)
        return {'identity':before,'initial':native.poll('usage initial accounting',lambda:observe(native,state))}
    state=read_private(STATE);require(type(state.get('schema')) is int and state['schema']==1 and state.get('proof')==PROOF
        and state.get('project')==project==os.environ.get('PROOF_PRICING_PROJECT') and str(UUID(state['user_id']))==state['user_id']
        and set(state['keys'])==set(ALIASES) and all(sha(key['token'].encode())==key['hash'] for key in state['keys'].values()),'usage_private_scope')
    native=versions.native(state)
    if action=='reference_fixture':
        require(label in ('source','original'),'usage_reference_fixture_label')
        reference=state['reference_fixture'];target=reference[label]
        require(target in ('S1','S2'),'usage_reference_fixture_variant')
        if label=='source':reference['arm_attempted']=True;save(state)
        owner=fixture(native,state);before=versions.catalog.catalog_projection(owner.provider('/observations'))['variant']
        result=owner.provider('/control',{'variant':target}) if before!=target else owner.provider('/observations')
        require(versions.catalog.catalog_projection(result)['variant']==target,'usage_reference_fixture_readback')
        return {'variant':target,'original_variant':reference['original'],'source_variant':reference['source'],'changed':before!=target}
    if action=='identity':return {'identity':identity(native,state,label)}
    if action=='call':
        require(len(state['calls'])<4 and LABELS[len(state['calls'])]==label,'usage_call_order_or_retry')
        identity(native,state,'v1' if label=='positive_v1' else 'v2')
        index=0 if len(state['calls'])<2 else len(state['calls'])-1;chat,root=str(uuid4()),str(uuid4())
        call={'label':label,'alias':ALIASES[index],'lineage':{'chat_id':chat,'root_answer_id':root,'call_kind':'synthetic_pricing_usage'}}
        call['deployment']=ALIASES[index]+'-'+('v2' if label=='positive_v2' else 'v1')
        if index==0:call['cost']='.166' if label=='positive_v1' else '.334'
        body={'model':call['alias'],'input':'Hi','max_output_tokens':16,'store':False,'stream':False,
            'litellm_metadata':{'session_id':chat,'spend_logs_metadata':call['lineage']}}
        call['body']=body;state['calls'].append(call);save(state)
        status,response,headers=native.request('POST','/v1/responses',token=state['keys'][call['alias']]['token'],body=body)
        call.update(http_status=status,response=response,returned_monotonic=time.monotonic());save(state)
        if index==0:
            require(status==200 and isinstance(response.get('id'),str) and valid_usage(response.get('usage')),'usage_positive_response')
            if headers.get('x-litellm-response-cost') not in (None,'','None'):require(close_amount(headers['x-litellm-response-cost'],Decimal(call['cost'])),'usage_positive_cost_header')
        end=time.monotonic()+(3 if index else 0)
        def observed():
            value=observe(native,state)
            return value if value is not None and time.monotonic()>=end else None
        result=native.poll('usage native rows and terminal provider',observed)
        return {'label':label,'http_status':status,'response_id_sha256':sha(encoded(response.get('id'))),
            'response_usage_present':'usage' in response,'response_usage':scalar(response.get('usage')),
            'response_usage_fields':usage_observation(response.get('usage')),
            'provider_response_usage_present':'usage' in call['provider_record']['response'],
            'provider_response_usage':scalar(call['provider_record']['response'].get('usage')),
            'provider_response_usage_fields':usage_observation(call['provider_record']['response'].get('usage')),
            'observation_seconds':time.monotonic()-call['returned_monotonic'],'financial':result}
    if action=='drain':return {'financial':native.poll('usage positive accounting and terminal requests',lambda:observe(native,state))}
    raise ProofError('usage_worker_action')


class UsageHost(versions.Host):
    WORKER_FILE='prove_pricing_usage.py'
    PROOF=PROOF
    SOURCE_PATHS=SOURCE_PATHS

    def execute(self):
        import yaml
        original=self.config.read_bytes();attempted=False;reference_attempted=False;failure=None
        try:
            initial=self.topology();self.invoke('prepare')
            self.receipt['stage']='arm_reference_fixture';reference_attempted=True;self.invoke('reference_fixture','source')
            for version,label in (('v1','positive_v1'),('v2','positive_v2')):
                self.receipt['stage']='drain_'+version;self.invoke('drain')
                raw=yaml.safe_dump(configuration(yaml.safe_load(original),version),sort_keys=False,allow_unicode=True).encode()
                attempted=True;self.receipt['stage']='publish_'+version;versions.overwrite(self.config,raw)
                proxy=self.restart();observed=self.invoke('identity',version)['identity']
                require(proxy['image_id']==initial['image_id'] and observed['config_sha256']==sha(raw)
                    and observed['worker_id_prefix']==proxy['id'][:12],'usage_actual_publication')
                self.receipt['stage']=label;self.invoke('call',label)
            for label in LABELS[2:]:self.receipt['stage']=label;self.invoke('call',label)
            final=self.invoke('drain')['financial'];require(final['physical_calls']==4,'usage_exact_four_dispatches')
            self.receipt.update(final=final,unknown_rows_finality=False,negative_cases_are_policy_qualification=False)
        except Exception as error:
            failure=error;self.receipt['primary_failure']=next((item['result']['failure'] for item in reversed(self.receipt['workers'])
                if item.get('passed') is False and isinstance(item.get('result'),dict) and isinstance(item['result'].get('failure'),dict)),failure_location(error))
        finally:
            errors=[]
            if attempted:
                try:self.invoke('drain')
                except Exception:errors.append('pre_restore_drain_failed')
                try:self.invoke('reference_fixture','source')
                except Exception:errors.append('reference_fixture_rearm_failed')
                try:
                    versions.overwrite(self.config,original);self.restart();restored=self.invoke('identity','base')['identity']
                    require(restored['config_sha256']==sha(original),'usage_restore_readback')
                except Exception:errors.append('config_restore_failed')
                else:
                    try:self.invoke('drain')
                    except Exception:errors.append('post_restore_history_failed')
            reference_restored=not reference_attempted
            if reference_attempted:
                try:self.invoke('reference_fixture','original');reference_restored=True
                except Exception:errors.append('reference_fixture_restore_failed')
            try:equal=self.config.read_bytes()==original
            except Exception:equal=False;errors.append('config_read_failed')
            self.receipt['restoration']={'original_bytes_equal':equal,'failures':errors,
                'reference_fixture_restored':reference_restored,'unknown_rows_finality':False}
            if failure is None and (errors or not equal):failure=ProofError('usage_restoration_failed')
        if failure:raise failure
        self.receipt.update(passed=True,stage='observed_native_used_categories');return self.receipt


def failure_location(error):
    result={'exception_class':type(error).__name__ if type(error) in (ProofError,TypeError,ValueError,KeyError,OSError,TimeoutError,AssertionError) else 'other','frames':[]}
    trace=error.__traceback__
    while trace:
        name=Path(trace.tb_frame.f_code.co_filename).name
        if name in SOURCE_PATHS:result['frames'].append({'source':name,'line':trace.tb_lineno})
        trace=trace.tb_next
    result['frames']=result['frames'][-8:]
    if type(error) is ProofError and error.args==('usage_positive_identity_cost',) and isinstance(getattr(error,'positive_row_diagnostic',None),dict):
        result['positive_row']=error.positive_row_diagnostic
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker-action',choices=('prepare','identity','call','drain','reference_fixture'));parser.add_argument('--label')
    parser.add_argument('--project',required=True);parser.add_argument('--env-file',type=Path)
    parser.add_argument('--private-root',type=Path);parser.add_argument('--receipt',type=Path)
    parser.add_argument('--compose-file',action='append');args=parser.parse_args()
    packet={'schema':1,'proof':PROOF,'passed':False,'action':args.worker_action,'result':None,'failure_code':None};host=None
    try:
        if args.worker_action:packet['result']=worker(args.worker_action,args.label,args.project)
        else:
            require(re.fullmatch('goal584-pricing-[0-9a-f]{12}',args.project) and args.env_file and args.env_file.is_file()
                and not args.env_file.is_symlink() and args.private_root and args.private_root.is_absolute()
                and args.private_root.is_dir() and not args.private_root.is_symlink() and args.receipt and not args.receipt.exists()
                and not args.receipt.is_symlink() and not args.receipt.parent.is_symlink()
                and not args.receipt.resolve().is_relative_to(args.private_root.resolve())
                and not args.private_root.resolve().is_relative_to(args.receipt.parent.resolve()) and args.compose_file
                and all((ROOT/p).resolve().is_relative_to(ROOT) and (ROOT/p).is_file() for p in args.compose_file),'usage_host_arguments')
            if os.name=='posix':require(all(stat.S_IMODE(p.stat().st_mode)&0o077==0 for p in (args.private_root,args.env_file,args.private_root/'config.yaml')),'usage_private_modes')
            host=UsageHost(args);packet['result']=host.execute()
        packet['passed']=True
    except Exception as error:
        packet['failure_code']='usage_verification_failed';packet['result']=host.receipt if host else {'failure':failure_location(error)}
        if args.worker_action and STATE.exists():
            try:
                private=read_private(STATE);private.setdefault('primary_failure',{'class':type(error).__name__,'message':str(error)});save(private)
            except Exception:packet['result']['primary_private_write_failed']=True
    try:
        raw=encoded(packet);require(not re.search(rb'(?:sk-|gw-|Bearer\s)[A-Za-z0-9_-]{12,}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',raw),'usage_public_credentials')
        if host:args.receipt.parent.mkdir(parents=True,exist_ok=True);args.receipt.write_bytes(raw+b'\n')
    except Exception:
        packet={'schema':1,'proof':PROOF,'passed':False,'action':args.worker_action,
            'result':{'primary_failure':(packet.get('result') or {}).get('primary_failure') or (packet.get('result') or {}).get('failure'),
                'receipt_write_failed':True},'failure_code':packet['failure_code'] or 'usage_receipt_write_failed'}
        raw=encoded(packet)
    print(raw.decode());return 0 if packet['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
