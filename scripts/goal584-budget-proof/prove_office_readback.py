"""Private proxy readback only; no Send, tool loop, config or budget mutation.

The host binds the native-context packet producer to actual Docker/Git/image
readback. Packet hashes alone do not prove origin. Live auth/provider evidence
never reconstructs cost Filter pre/post bodies or claims Office acceptance.
"""
from __future__ import annotations
import argparse
import base64
import copy
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path
import re

import prove_office_compatibility as proof
from prove_native_budgets import ProofError, amount, protected_r, require

PRIVATE = Path('/proof-private')
COMMON, OFFICE = PRIVATE / 'webui-state.private.json', PRIVATE / 'office-state.private.json'
STATE, BROWSER = PRIVATE / 'office-readback.private.json', PRIVATE / 'office-browser.private.json'
CONTEXT = PRIVATE / 'office-native-context.private.json'
OFFICE_FILTER = Path('/proof/officecli_auto_attach_filter.py')
MAX_BYTES = 16 * 1024 * 1024


def dependencies():
    from provision_webui import WebUI, native_client, read_private, write_private, OPERATOR_STATE
    from prove_service_tasks import provider
    from prove_pricing_snapshots import validate_snapshot, no_credentials, private_credentials
    from provenance import validate_persisted_scope, validate_persisted_service_scope
    from litellm.responses.utils import ResponsesAPIRequestUtils
    import capture_webui_auth as capture
    return locals()


def inventory(native, office):
    """Bounded actual user/key inventories and ALL NativeProof raw log pages."""
    users, page, total = [], 1, None
    while True:
        result = native.ok('GET', '/user/list', query={'page': page, 'page_size': 100})
        require(type(result.get('total_pages')) is int and 0 <= result['total_pages'] <= 10
                and result.get('page') == page and isinstance(result.get('users'), list), 'office_user_inventory')
        require(total is None or total == result['total'], 'office_user_inventory_changed')
        total = result['total']; users.extend(row['user_id'] for row in result['users'])
        if page >= result['total_pages']: break
        page += 1
    require(len(users) == len(set(users)) == total, 'office_user_inventory_incomplete')
    actor, payer = office['users'][0]['id'], office['service_fixture']['payer_id']
    hashes = {actor: office['office_setup']['budget']['models'][0]['key_hash'],
              payer: office['service_fixture']['key_hash']}
    require(actor != payer and set(hashes) <= set(users), 'office_readback_payers')
    owners = {}
    for uid in sorted(users):
        keys, page, total = [], 1, None
        while True:
            result = native.ok('GET', '/key/list', query={'user_id': uid, 'page': page, 'size': 100,
                'return_full_object': 'true', 'substring_matching': 'false',
                'include_team_keys': 'false', 'include_created_by_keys': 'false'})
            require(type(result.get('total_pages')) is int and 0 <= result['total_pages'] <= 10
                    and result.get('current_page') == page and isinstance(result.get('keys'), list), 'office_key_inventory')
            require(total is None or total == result['total_count'], 'office_key_inventory_changed')
            total = result['total_count']; keys.extend(result['keys'])
            if page >= result['total_pages']: break
            page += 1
        require(len(keys) == len({k['token'] for k in keys}) == total
                and all(k['user_id'] == uid for k in keys), 'office_key_inventory_incomplete')
        owners[uid] = {'user': native.user_info(uid), 'keys': sorted(keys, key=lambda k: k['token']),
                       'rows': sorted(native.logs(uid), key=lambda r: r['request_id'])}
        require(owners[uid]['user'].get('user_id') == uid, 'office_user_inventory_scope')
    selected = {}
    for uid, key_hash in hashes.items():
        matches = [k for k in owners[uid]['keys'] if k['token'] == key_hash]
        require(len(matches) == len(owners[uid]['keys']) == 1, 'office_readback_assignment')
        selected[uid] = {'user': owners[uid]['user'], 'key': matches[0], 'rows': owners[uid]['rows']}
    old = {}
    for uid, owner in owners.items():
        if uid in hashes: continue
        # protected_r's user/key projections are independent. For an unkeyed
        # native user, use the actual primary key only to obtain its user half.
        anchor = owner['keys'][0] if owner['keys'] else selected[actor]['key']
        old[uid] = {'user': protected_r(owner['user'], anchor)['user'], 'spend': owner['user'].get('spend'),
                    'keys': [dict(protected=protected_r(owner['user'], k)['key'], spend=k.get('spend')) for k in owner['keys']],
                    'rows': owner['rows']}
    return {'raw_owners': owners, 'primary': dict(selected[actor], old_payers=old), 'service': selected[payer]}


def native_converter(packet, office):
    require(packet.get('schema') == 1 and packet.get('module_sha256') == {
        k: proof.WEBUI_MODULES[k] for k in ('utils/tools.py', 'routers/openai.py')}
        and packet.get('source_body_sha256') == proof.digest(office['office_setup']['openapi']), 'office_native_context_source')
    cases = {}
    for case in packet['reasoning_cases']:
        key = proof.digest(case['input_reasoning'])
        require(key not in cases or cases[key] == case['native_input'], 'office_native_reasoning_ambiguous')
        cases[key] = case['native_input']
    def convert(body):
        reasoning = body['messages'][0]['output']
        require(body == {'messages': [{'role': 'assistant', 'output': reasoning}]}
                and proof.digest(reasoning) in cases, 'office_native_reasoning_missing')
        return {'input': copy.deepcopy(cases[proof.digest(reasoning)])}
    return convert


def wire_calls(before, provider, capture, office):
    require(provider['requests'][:len(before['provider']['requests'])] == before['provider']['requests']
            and capture['requests'][:len(before['capture']['requests'])] == before['capture']['requests'], 'office_prior_context_changed')
    physical = provider['requests'][len(before['provider']['requests']):]
    observed = capture['requests'][len(before['capture']['requests']):]
    require(len(physical) == len(observed) == 4, 'office_readback_physical_calls')
    calls, service, matched = [], [], set()
    for row in observed:
        wire = row['body']; model = wire['model']
        require(model in (proof.MODEL, 'gpt-6-luna'), 'office_unexpected_observation')
        target = 'goal584-fake-office' if model == proof.MODEL else 'goal584-fake-office-service'
        matches = [p for p in physical if p['body'] == {**wire, 'model': target}]
        require(len(matches) == 1 and matches[0]['id'] not in matched, 'office_provider_join')
        p = copy.deepcopy(matches[0]); matched.add(p['id'])
        p['lifecycle'] = {k: p['lifecycle'][k] for k in ('terminal', 'outcome')}
        call = {'wire_before_auth': wire, 'wire_after_auth': row['body_after_auth'],
            'auth_user_id': row['native_auth_user_id'], 'auth_key_hash': row['native_auth_key_hash'],
            'attestation_present_before': row['attestation_present_before'], 'provenance_removed_after': row['provenance_removed_after'],
            'route': row['route'], 'verified_cost_scope': row['verified_cost_scope'], 'provider': p}
        require(not row.get('auth_failure'), 'office_readback_auth_failed')
        (calls if model == proof.MODEL else service).append(call)
    require(len(calls) == 3 and len(service) == 1, 'office_readback_call_partition')
    return calls, service[0]


def wire_diagnostic(before, provider, capture, *, expected_instruction, secrets, no_credentials):
    """Complete bounded synthetic projections, never an admission/finance result.

    Reuse the actual observer's projection without repairing instruction channels
    or joining away differing requests. Auth credentials/inventories stay private.
    """
    observed = {}
    for name, current in (('provider', provider), ('capture', capture)):
        old, rows = before[name]['requests'], current['requests']
        require(rows[:len(old)] == old, 'office_diagnostic_prior_context')
        observed[name] = rows[len(old):]
        require(len(observed[name]) <= 8, 'office_diagnostic_count')
    def wire(body, allowed):
        require(body.get('model') in allowed, 'office_diagnostic_synthetic_model')
        return proof.responses_projection(body)
    def channels(body):
        return {'instructions': {'present': 'instructions' in body, 'value': body.get('instructions')},
            'input_messages': [copy.deepcopy(v) for v in body.get('input', [])
                if isinstance(v, dict) and v.get('type', 'message') == 'message']}
    auth, physical = [], []
    for row in observed['capture']:
        first = wire(row['body'], (proof.MODEL, 'gpt-6-luna'))
        after = wire(row['body_after_auth'], (proof.MODEL, 'gpt-6-luna'))
        auth.append({'route': row['route'], 'before_auth': first, 'after_auth': after,
            'instruction_channels': {'before_auth': channels(first), 'after_auth': channels(after)},
            'attestation_present_before': row.get('attestation_present_before'),
            'provenance_removed_after': row.get('provenance_removed_after')})
    for row in observed['provider']:
        body = wire(row['body'], ('goal584-fake-office', 'goal584-fake-office-service'))
        response = row.get('response') or {}
        physical.append({'route': row['route'], 'request': body, 'instruction_channels': channels(body),
            'response': {k: copy.deepcopy(response[k]) for k in ('id', 'model', 'status', 'instructions', 'output', 'usage') if k in response},
            'lifecycle': {k: row.get('lifecycle', {}).get(k) for k in ('terminal', 'outcome')}})
    packet = {'schema': 1, 'phase': 'diagnostic', 'status': 'collected_synthetic_wire_diagnostic',
        'passed': True, 'native_office_accepted': False, 'validation_passed': False,
        'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'expected_instruction': expected_instruction, 'auth_observations': auth, 'provider_observations': physical,
        'limits': ['source-bound observation only; no Filter pre/post or financial acceptance']}
    require(len(json.dumps(packet, allow_nan=False).encode()) <= 1024 * 1024, 'office_diagnostic_bound')
    no_credentials(packet, secrets)
    return packet


def verify(before, after, provider, capture, saved, browser, packet, office, d):
    calls, service = wire_calls(before, provider, capture, office)
    actor, payer = office['users'][0]['id'], office['service_fixture']['payer_id']
    chat, answer, source = (browser[k] for k in ('chat_id', 'answer_id', 'source_message_id'))
    messages = saved['chat']['history']['messages']; final = messages[answer]; request = messages[final['parentId']]
    require(saved['id'] == chat and saved['user_id'] == actor and messages[source].get('id') == source
            and final.get('id') == answer and messages[source]['role'] == 'assistant'
            and messages[source]['content'] == proof.SOURCE and request['role'] == 'user'
            and request['content'] == proof.USER_REQUEST and request['parentId'] == source
            and final['role'] == 'assistant' and final['model'] == proof.MODEL and final['done'] is True
            and not final.get('error') and browser['file_id'] in final['content'], 'office_saved_chat')
    first_id = next(v['call_id'] for v in calls[0]['provider']['response']['output'] if v['type'] == 'function_call')
    exported = json.loads(next(v['output'] for v in calls[1]['wire_before_auth']['input']
                               if v.get('type') == 'function_call_output' and v['call_id'] == first_id))
    require(exported['result_file_id'] == browser['file_id'] and exported['source_message_id'] == source
            and exported['source_content_sha256'] == proof.SOURCE_SHA256, 'office_export_source')
    images = [v['image_url'] for v in proof._nodes(calls[2]['wire_before_auth']['input']) if v.get('type') == 'input_image']
    require(len(images) == 1 and images[0].startswith('data:image/png;base64,'), 'office_render_image_context')
    png = base64.b64decode(images[0].partition(',')[2], validate=True)
    key = before['finance']['primary']['key']['token']
    scopes = proof.verify_wire_calls(calls, actor=actor, key_hash=key, chat_id=chat, answer_id=answer,
        wire_model='goal584-fake-office', native_specs=packet['native_specs'], exported=exported, png=png,
        native_responses_payload=native_converter(packet, office),
        expected_instruction=proof.office_instruction(OFFICE_FILTER.read_bytes()))
    main = proof.verify_finance(before['finance']['primary'], after['primary'], calls_by_provider=scopes,
        actor=actor, key_hash=key, chat_id=chat, answer_id=answer, wire_model='goal584-fake-office',
        deployment_id='goal584-office-primary', validate_scope=d['validate_persisted_scope'],
        validate_rates=d['validate_snapshot'], decode_response_id=d['ResponsesAPIRequestUtils']._decode_responses_api_response_id)
    p, wire = service['provider'], service['wire_before_auth']
    require(wire == service['wire_after_auth'] and service['auth_user_id'] == payer
            and service['auth_key_hash'] == before['finance']['service']['key']['token']
            and service['attestation_present_before'] is True and service['provenance_removed_after'] is True
            and service['route'] in ('/responses', '/v1/responses', '/openai/v1/responses')
            and p['route'] == '/v1/responses' and p['usage'] == p['response']['usage'] == proof.USAGE
            and p['response']['model'] == 'goal584-fake-office-service'
            and p['response']['id'] == p['id'] and p['response']['status'] == 'completed'
            and p['lifecycle'] == {'terminal': True, 'outcome': 'completed'}, 'office_service_wire')
    texts = [v['text'] for v in proof._nodes(p['response']['output']) if v.get('type') == 'output_text']
    followups = json.loads(texts[0])['follow_ups'] if len(texts) == 1 else None
    require(isinstance(followups, list) and followups and all(isinstance(v, str) and v for v in followups)
            and final.get('followUps') == followups, 'office_saved_followups')
    task = proof.verify_service_finance(before['finance']['service'], after['service'], actor=actor, payer=payer,
        key_hash=before['finance']['service']['key']['token'], chat_id=chat, provider_id=p['id'], verified_scope=service['verified_cost_scope'],
        wire_model='goal584-fake-office-service', deployment_id='goal584-office-service', descriptor=before['descriptor'],
        validate_scope=d['validate_persisted_service_scope'], validate_rates=d['validate_snapshot'],
        decode_response_id=d['ResponsesAPIRequestUtils']._decode_responses_api_response_id)
    require(set(before['finance']['raw_owners']) == set(after['raw_owners']), 'office_payer_inventory_changed')
    return {'primary': main, 'service': task, 'provider_calls': 4, 'saved_chat_verified': True}


def run(phase, d):
    common, office = d['read_private'](COMMON), d['read_private'](OFFICE)
    require(office.get('stage') == 'setup_complete' and office['office_service_setup']['stage'] == 'readback_ready', 'office_not_prepared')
    native = d['native_client'](common)
    operator = d['read_private'](d['OPERATOR_STATE'])
    native.started_at = min(datetime.fromisoformat(common['started_at_utc']), datetime.fromisoformat(operator['started_at'])) - timedelta(minutes=1)
    def contexts():
        with d['capture'].capture_lock(): captured = d['capture']._read_locked()
        return d['provider'](), captured
    if phase == 'diagnostic':
        state = d['read_private'](STATE)
        provider, captured = contexts()
        secrets = [value for owner in (common, office, operator) for value in d['private_credentials'](owner)]
        return wire_diagnostic(state, provider, captured,
            expected_instruction=proof.office_instruction(OFFICE_FILTER.read_bytes()),
            secrets=secrets, no_credentials=d['no_credentials'])
    if phase == 'baseline':
        require(not STATE.exists(), 'office_readback_baseline_exists')
        finance = inventory(native, office); provider, captured = contexts()
        require(not finance['primary']['rows'] and not finance['service']['rows'], 'office_fresh_payers_have_rows')
        models = native.ok('GET', '/model/info')['data']
        model, = [m for m in models if m['model_name'] == 'gpt-6-luna']
        state = {'schema': 1, 'stage': 'baseline', 'prepared_sha256': proof.digest(office), 'finance': finance,
            'provider': provider, 'capture': captured, 'descriptor': model['model_info']['owui_pricing'],
            'history_start_utc': native.started_at.isoformat()}
        result = {'baseline_payers': len(finance['raw_owners']), 'history_start_utc': state['history_start_utc']}
    else:
        state = d['read_private'](STATE)
        require(state.get('stage') == 'baseline' and state['prepared_sha256'] == proof.digest(office)
                and state['history_start_utc'] == native.started_at.isoformat(), 'office_readback_baseline_changed')
        browser, packet = d['read_private'](BROWSER), d['read_private'](CONTEXT)
        def settled():
            saved = d['WebUI']().ok('GET', '/api/v1/chats/' + browser['chat_id'], token=office['users'][0]['token'])
            after = inventory(native, office); provider, captured = contexts()
            state['last_observation'] = dict(after=after, provider=provider, capture=captured, saved_chat=saved)
            require(len(json.dumps(state, allow_nan=False).encode()) <= MAX_BYTES, 'office_readback_private_bound')
            d['write_private'](STATE, state)  # Retain the actual failed/partial readback too.
            try: result = verify(state, after, provider, captured, saved, browser, packet, office, d)
            except ProofError as error:
                code = str(error)
                state['failure_code'] = code if re.fullmatch(r'office_[a-z_]+', code) else 'office_readback_failed'
                d['write_private'](STATE, state)
                waiting = {'office_row_count': ('primary', 3), 'office_service_row_count': ('service', 1)}
                if code in waiting:
                    owner, expected = waiting[code]
                    if 0 <= len(after[owner]['rows']) - len(state['finance'][owner]['rows']) < expected: return None
                counters = {'office_native_spend_delta': ('primary', Decimal('.60')),
                            'office_service_native_spend_delta': ('service', Decimal('.20'))}
                if code in counters:
                    owner, expected = counters[code]
                    deltas = [amount(after[owner][k]['spend']) - amount(state['finance'][owner][k]['spend']) for k in ('user', 'key')]
                    if all(0 <= value <= expected for value in deltas) and any(value < expected for value in deltas): return None
                raise
            return result, after, provider, captured, saved
        result, after, provider, captured, saved = native.poll('Office complete raw native rows and counters', settled)
        state.pop('last_observation', None)
        state.pop('failure_code', None)
        state.update(stage='verified_readback', after=after, provider_after=provider, capture_after=captured,
                     saved_chat=saved, browser=browser, native_context=packet)
    require(len(json.dumps(state, allow_nan=False).encode()) <= MAX_BYTES, 'office_readback_private_bound')
    d['write_private'](STATE, state)
    result = {'schema': 1, 'phase': phase, 'passed': True, 'native_office_accepted': False,
        'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'live_filter_prepost_qualified': False, 'readback_sha256': proof.digest(state), **result}
    d['no_credentials'](result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--phase', choices=('baseline', 'verify', 'diagnostic'), required=True)
    args = parser.parse_args()
    d = None
    try:
        d = dependencies()
        result = run(args.phase, d)
    except Exception as error:
        code = str(error) if isinstance(error, ProofError) else ''
        result = {'schema': 1, 'phase': args.phase, 'passed': False, 'native_office_accepted': False,
                  'failure_code': code if re.fullmatch(r'office_[a-z_]+', code) else 'office_readback_failed'}
        if code == 'office_service_dispatch_binding' and hasattr(error, 'office_service_binding') and d is not None:
            atoms = getattr(error, 'office_service_binding_atoms', None)
            if isinstance(atoms, dict) and set(atoms) == proof.SERVICE_BINDING_ATOMS and all(type(v) is bool for v in atoms.values()):
                result['binding_atoms'] = atoms
            stage = 'serialization'
            try:
                binding = error.office_service_binding
                size = len(json.dumps(binding, allow_nan=False).encode())
                result['binding_diagnostic_bytes'] = size
                stage = 'size'
                require(size <= 4096, 'office_binding_diagnostic_bound')
                stage = 'private_read'
                secrets = [value for path in (COMMON, OFFICE, d['OPERATOR_STATE'])
                           for value in d['private_credentials'](d['read_private'](path))]
                stage = 'credential_check'
                d['no_credentials'](binding, secrets)
            except Exception:
                result['binding_diagnostic_collected'] = False
                result['binding_diagnostic_suppression_stage'] = stage
            else:
                result['binding_diagnostic_collected'] = True
                result['binding_diagnostic'] = binding
    print(json.dumps(result, allow_nan=False)); return 0 if result['passed'] else 1


if __name__ == '__main__': raise SystemExit(main())
