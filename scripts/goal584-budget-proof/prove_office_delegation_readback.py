"""Private, bounded readback of one ordinary delegated Office UI turn.

Native inventories, financial validation, provenance, descriptor validation and
cost snapshot remain existing owners. This module neither issues inference nor
changes native configuration, Tasks, Files, budgets or model history.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import copy
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import prove_office_readback as existing
import prove_office_compatibility as proof
from prove_native_budgets import ProofError, amount, protected_r, require

PRIVATE = Path('/proof-private')
COMMON, OFFICE = PRIVATE / 'webui-state.private.json', PRIVATE / 'office-state.private.json'
STATE = PRIVATE / 'office-delegation-readback.private.json'
BROWSER = PRIVATE / 'office-delegation-browser.private.json'
CONTEXT = PRIVATE / 'office-delegation-native-context.private.json'
GUIDE = PRIVATE / 'office-word-guide.private.json'
QUALIFICATION = PRIVATE / 'office-qualification.safe.json'
MAX_BYTES = 32 * 1024 * 1024
MODELS = ('gpt-6.1-sol', 'gpt-6.1-terra')
WIRES = dict(zip(MODELS, ('goal584-fake-delegated-parent', 'goal584-fake-delegated-worker')))
DEPLOYMENTS = dict(zip(MODELS, ('goal584-delegated-parent', 'goal584-delegated-worker')))
ORDER = (('create_tasks', 'view_skill', 'run_sub_agent', 'update_task', 'update_task'),
         ('load_officecli_skill', 'inspect_office_document', 'apply_office_batch', 'inspect_office_document', 'render_office_file'))
QUOTA_PHASES = ('quota-baseline', 'quota-status', 'quota-quiesce', 'quota-verify', 'quota-restore')


def host_quota_phase(fixture, phase, mutation, *, timeout=80):
    """One fixed attached quota phase; client timeout never authorizes a second write."""
    require(phase in QUOTA_PHASES and 0 < timeout <= 100, 'office_quota_host_phase')
    mutation(True)
    try:
        result = subprocess.run(fixture.command + ['exec', '-T', 'proxy', 'python', '-B',
            '/proof/prove_office_delegation_readback.py', '--phase', phase], capture_output=True, timeout=timeout)
        require(0 < len(result.stdout) <= 64 * 1024, 'office_quota_native_completion')
        packet = json.loads(result.stdout)
        require(isinstance(packet, dict) and type(packet.get('schema')) is int and packet['schema'] == 1
                and packet.get('phase') == phase and type(packet.get('passed')) is bool
                and packet.get('source_sha256') == sha256(Path(__file__).read_bytes()).hexdigest()
                and packet.get('native_office_accepted') is False
                and result.returncode == (0 if packet['passed'] else 1), 'office_quota_native_completion')
    except BaseException:
        # The owning Compose teardown is the remaining participant stop. It is
        # not cap restoration evidence; no retry/second cap write is authorized.
        raise ProofError('office_quota_mutation_unconfirmed') from None
    mutation(False)
    return packet


def host_quota_restore(phase):
    """Order existing native journal/readback owners, without reading root-owned state on host."""
    status = phase('quota-status')
    require(status.get('passed') is True and type(status.get('quota_present')) is bool, 'office_quota_restore_status')
    if not status['quota_present']:
        return {'required': False, 'confirmed': True}
    quiescent = phase('quota-quiesce')
    require(quiescent.get('passed') is True, 'office_quota_restore_quiescence')
    restored = phase('quota-restore')
    require(restored.get('passed') is True and restored.get('quota_stage') == 'restored', 'office_quota_restore_readback')
    return {'required': True, 'confirmed': True, 'quota_stage': 'restored'}


def dependencies():
    d = existing.dependencies()
    from employee_budget_cost_readback import read_cost_snapshot
    from aiohttp import ClientSession
    from provision_cost_display import FILTER_ID
    from provision_webui import delegated_source_docx, WORKFLOW_SKILL_SHA256
    from mock_provider import DELEGATED_USER_REQUEST, delegated_responses_input, delegated_responses_step
    return {**d, **locals()}


def selected(office):
    value = office['office_delegation_setup']
    require(office.get('stage') == 'setup_complete' and value.get('stage') == 'readback_ready'
            and office.get('office_service_setup', {}).get('stage') == 'readback_ready', 'office_delegation_not_prepared')
    require(value['tool_valves']['DEFAULT_MODEL'] == 'corporate-office-worker'
            and value['tool_valves']['APPLY_INLET_FILTERS'] is True, 'office_delegation_tool_owner')
    return value


def inventory(native, office, *, worker_cap=Decimal(1000)):
    """Select the two actual assignment keys without omitting any raw owner row."""
    setup = selected(office); actor = setup['actor']['id']; payer = office['service_fixture']['payer_id']
    owners = existing.inventory_owners(native)
    require(actor != payer and {actor, payer} <= set(owners), 'office_delegation_payers')
    assignments = {m['model']: m['key_hash'] for m in setup['budget']['models']}
    require(set(assignments) == set(MODELS) and len(set(assignments.values())) == 2, 'office_delegation_assignments')
    keys = {k['token']: k for k in owners[actor]['keys']}
    require(set(keys) == set(assignments.values()) and amount(owners[actor]['user']['max_budget']) == Decimal(2000),
            'office_delegation_assignments')
    old = {}
    for uid, owner in owners.items():
        if uid in (actor, payer): continue
        anchor = owner['keys'][0] if owner['keys'] else next(iter(keys.values()))
        old[uid] = {'user': protected_r(owner['user'], anchor)['user'], 'spend': owner['user'].get('spend'),
                    'keys': [dict(protected=protected_r(owner['user'], k)['key'], spend=k.get('spend')) for k in owner['keys']],
                    'rows': owner['rows']}
    require(bool(old), 'office_delegation_old_payers')
    personal = {}
    for model, key_hash in assignments.items():
        key = keys[key_hash]
        require(key['models'] == [model] and key['user_id'] == actor
                and amount(key['max_budget']) == (worker_cap if model == MODELS[1] else Decimal(1000)),
                'office_delegation_assignment_owner')
        personal[model] = dict(user=owners[actor]['user'], key=key,
            rows=[r for r in owners[actor]['rows'] if r.get('api_key') == key_hash], old_payers=old)
    require(all(r.get('api_key') in keys for r in owners[actor]['rows']), 'office_delegation_unassigned_row')
    service_keys = [k for k in owners[payer]['keys'] if k['token'] == office['service_fixture']['key_hash']]
    require(len(service_keys) == len(owners[payer]['keys']) == 1, 'office_delegation_service_key')
    return {'raw_owners': owners, 'personal': personal,
            'service': dict(user=owners[payer]['user'], key=service_keys[0], rows=owners[payer]['rows'])}


def descriptors(models):
    result = {}
    for model, cap in zip(MODELS, (12000, 6000)):
        rows = [m for m in models if m.get('model_name') == model]
        require(len(rows) == 1, 'office_delegation_descriptor')
        row = rows[0]; info, params = row['model_info'], row['litellm_params']
        require(info['id'] == DEPLOYMENTS[model] and info['mode'] == 'responses'
                and info['supports_native_streaming'] is False and info['max_output_tokens'] == cap
                and params['model'] == 'openai/' + WIRES[model], 'office_delegation_descriptor')
        result[model] = copy.deepcopy(row)
    service, = [m for m in models if m.get('model_name') == 'gpt-6-luna']
    result['service'] = copy.deepcopy(service)
    return result


def join_responses_call(row, physical, *, wire_model, provider_transport):
    """Join one actual auth observation to its whole physical Responses body."""
    wire = row['body']
    require(wire == row['body_after_auth'] and not row.get('auth_failure')
            and row['attestation_present_before'] is True and row['provenance_removed_after'] is True
            and row['route'] in ('/responses', '/v1/responses', '/openai/v1/responses'), 'office_delegation_auth_context')
    expected = proof.expected_provider_body(wire, wire_model, provider_transport=provider_transport)
    matches = [p for p in physical if p['body'] == expected]
    require(len(matches) == 1, 'office_delegation_provider_join')
    p = copy.deepcopy(matches[0])
    p['lifecycle'] = {k: p['lifecycle'][k] for k in ('terminal', 'outcome')}
    return dict(wire_before_auth=wire, wire_after_auth=row['body_after_auth'],
        auth_user_id=row['native_auth_user_id'], auth_key_hash=row['native_auth_key_hash'],
        attestation_present_before=True, provenance_removed_after=True, route=row['route'],
        verified_cost_scope=row['verified_cost_scope'], provider=p)


def calls(before, provider, captured):
    for name, current in (('provider', provider), ('capture', captured)):
        old = before[name]['requests']
        require(current['requests'][:len(old)] == old, 'office_delegation_prior_context')
    physical = provider['requests'][len(before['provider']['requests']):]
    observed = captured['requests'][len(before['capture']['requests']):]
    require(len(physical) == len(observed) == 13, 'office_delegation_physical_calls')
    groups = {m: [] for m in (*MODELS, 'gpt-6-luna')}; used, nonces = set(), set()
    for row in observed:
        wire = row['body']; model = wire.get('model')
        require(model in groups, 'office_delegation_auth_context')
        target = WIRES.get(model, 'goal584-fake-office-service')
        call = join_responses_call(row, physical, wire_model=target,
                                  provider_transport='buffered' if model == MODELS[0] else 'native')
        require(call['provider']['id'] not in used, 'office_delegation_provider_join')
        used.add(call['provider']['id'])
        scope = row['verified_cost_scope']
        require(scope['call_id'] not in nonces, 'office_delegation_nonce')
        nonces.add(scope['call_id'])
        groups[model].append(call)
    require([len(groups[m]) for m in (*MODELS, 'gpt-6-luna')] == [6, 6, 1] and len(used) == 13,
            'office_delegation_call_partition')
    return groups


def text_strings(value):
    """Read actual textual model-context leaves; never decode opaque reasoning."""
    if isinstance(value, str): yield value
    elif isinstance(value, list):
        for child in value: yield from text_strings(child)
    elif isinstance(value, dict):
        for key, child in value.items():
            if key not in ('encrypted_content', 'image_url'): yield from text_strings(child)


def task_pairs(wire):
    items = wire['input']; pairs = []
    calls = [v for v in items if v.get('type') == 'function_call']
    results = [v for v in items if v.get('type') == 'function_call_output']
    require(len(calls) == len(results) and len({c['call_id'] for c in calls}) == len(calls), 'office_delegation_tool_pairs')
    for c, r in zip(calls, results):
        require(c['call_id'] == r['call_id'], 'office_delegation_tool_pairs')
        pairs.append((c, r))
    return pairs


def select_render_image(wire, render_call, *, file_id):
    """Read the pinned Tool's native render continuation without rewriting it."""
    pairs = task_pairs(wire)
    require(len(pairs) == 5 and isinstance(render_call, dict)
            and render_call.get('name') == 'render_office_file'
            and sum(c.get('name') == 'render_office_file' for c, _ in pairs) == 1,
            'office_delegation_render_call')
    call, result = pairs[-1]
    require(all(call.get(k) == render_call.get(k) for k in ('call_id', 'name', 'arguments'))
            and json.loads(call['arguments']) == {'file_id': file_id, 'format': 'docx', 'grid': 2}
            and result.get('output') == 'render_office_file: Image file read successfully.',
            'office_delegation_render_binding')
    items = wire['input']; index = items.index(result)
    require(index > 0 and items[index - 1] == call and len(items) == index + 2,
            'office_delegation_render_suffix')
    carrier = items[index + 1]; parts = carrier.get('content')
    require(set(carrier) == {'type', 'role', 'content'} and carrier['type'] == 'message'
            and carrier['role'] == 'user' and isinstance(parts, list) and len(parts) == 3
            and parts[0] == {'type': 'input_text', 'text': 'Here are the images from the tool results above. Please analyze them.'}
            and parts[2] == {'type': 'input_text', 'text': '\n\n[Iteration 6/12]'}
            and isinstance(parts[1], dict) and set(parts[1]) == {'type', 'image_url', 'detail'}
            and parts[1]['type'] == 'input_image' and parts[1]['detail'] == 'auto'
            and isinstance(parts[1]['image_url'], str) and parts[1]['image_url'].startswith('data:image/png;base64,')
            and len(parts[1]['image_url']) <= 12 * 1024 * 1024
            and sum(v.get('type') == 'input_image' for v in proof._nodes(items)) == 1,
            'office_delegation_render_carrier')
    try: png = base64.b64decode(parts[1]['image_url'].partition(',')[2], validate=True)
    except (ValueError, TypeError):
        require(False, 'office_delegation_png')
    require(24 <= len(png) <= 8 * 1024 * 1024 and png.startswith(b'\x89PNG\r\n\x1a\n')
            and png[12:16] == b'IHDR', 'office_delegation_png')
    return png, carrier


def verify_guide(actual, browser, context):
    """Join actual Tool text to the existing source-bound CLI qualification."""
    for path in (GUIDE, QUALIFICATION):
        require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= MAX_BYTES,
                'office_delegation_guide_packet')
    raw = GUIDE.read_bytes(); qualification_raw = QUALIFICATION.read_bytes()
    packet, qualification = json.loads(raw), json.loads(qualification_raw)
    binding = context['binding']; expected = binding['word_guide_binding']; output = packet['output']
    require(qualification.get('stage') == 'complete' and qualification.get('preflight_passed') is True
            and qualification['word_guide'] == expected
            and sha256(qualification_raw).hexdigest() == binding['qualification_receipt_sha256']
            and sha256(raw).hexdigest() == expected['packet_sha256'] and len(raw) == expected['packet_bytes'],
            'office_delegation_guide_qualification')
    require(packet['schema'] == 1 and packet['source_commit'] == binding['source_commit']
            and re.fullmatch('[0-9a-f]{40}', packet['source_commit'])
            and packet['qualification_image_id'] == expected['image_id']
            and packet['office_image_id'] == browser['running']['office']['image_id']
            and packet['version'] == expected['version'] == '1.0.152'
            and packet['modules'] == expected['modules'] == browser['running']['office']['modules']
            and packet['binary_sha256'] == expected['binary_sha256'] == browser['running']['office']['binary_sha256']
            and output['command'] == expected['command'] == ['/usr/local/bin/officecli', 'load_skill', 'word']
            and output['auto_resident_disabled'] is True and isinstance(output['diagnostics'], str),
            'office_delegation_guide_source')
    require(isinstance(output['text'], str) and output['text']
            and output['content_sha256'] == expected['content_sha256'] == sha256(output['text'].encode()).hexdigest()
            and len(output['text'].encode()) == expected['text_bytes']
            and actual['content'] == output['text'] and actual['content_sha256'] == output['content_sha256'],
            'office_delegation_complete_guide')


def capacity_observations(rows, declared):
    """Existing SDK inspection/token counter only; no provider/budget substitute."""
    from importlib.metadata import version
    import inspect
    try:
        import litellm
        from litellm.responses.litellm_completion_transformation.transformation import LiteLLMCompletionResponsesConfig as C
    except ImportError:
        raise ProofError('office_delegation_capacity_runtime_unavailable') from None
    require(version('litellm') == '1.105.1', 'office_delegation_capacity_source')
    raw = Path(inspect.getfile(C)).read_bytes().replace(b'\r\n', b'\n')
    require(sha256(raw).hexdigest() == '9fa643ec5861da4ac1b6b511291edda8278895845ca9014594df7af02f2c4eb5',
            'office_delegation_capacity_source')
    require(isinstance(rows, list) and len(rows) <= 32, 'office_delegation_capacity_bound')
    result = []
    for row in rows:
        wire = row['body']; model = wire.get('model')
        if model not in MODELS: continue
        before = proof.digest(wire); observed = copy.deepcopy(wire)
        messages = C.transform_responses_api_input_to_messages(input=observed['input'], responses_api_request=observed, replay_reasoning=False)
        tools, _ = C.transform_responses_api_tools_to_chat_completion_tools(observed.get('tools', []))
        count = litellm.token_counter(model=model, messages=messages, tools=tools)
        info = declared[model]['model_info']; output = wire['max_output_tokens']
        require(proof.digest(wire) == before and type(count) is int and count > 0
                and type(info['max_input_tokens']) is int and type(info['max_output_tokens']) is int
                and type(output) is int and 0 < output <= info['max_output_tokens'] and count <= info['max_input_tokens'],
                'office_delegation_declared_capacity')
        result.append(dict(model=model, native_capacity_estimate=count, declared_max_input_tokens=info['max_input_tokens'],
            request_max_output_tokens=output, declared_max_output_tokens=info['max_output_tokens'],
            native_reservation_estimate_usd=row.get('native_estimated_max_cost_usd')))
    return dict(source_sha256=sha256(raw).hexdigest(), kind='native_sdk_inspection_estimate_not_provider_exact', calls=result)


def verify_context(groups, office, browser, context, d, provider_requests, *, quota=False):
    setup = selected(office); actor = setup['actor']['id']; chat, answer = browser['chat_id'], browser['answer_id']
    require(context.get('schema') == 1 and isinstance(context.get('packets'), list) and context['packets'],
            'office_delegation_native_context_shape')
    personal = [c for m in MODELS for c in groups[m]]
    require(set(context['provider_ids']) == {c['provider']['id'] for c in personal}
            and len(context['provider_ids']) == (6 if quota else 12), 'office_delegation_native_context_provider_ids')
    cases, specs = {}, None
    for packet in context['packets']:
        convert = existing.native_converter(packet, office)
        if specs is not None:
            try:
                for actual, expected in ((specs, packet['native_specs']), (packet['native_specs'], specs)):
                    proof.verify_schemas([{'type': 'function', **spec, 'strict': spec.get('strict', False)}
                                          for spec in actual], expected)
            except ProofError:
                raise ProofError('office_delegation_native_context_specs') from None
        specs = packet['native_specs']
        for case in packet['reasoning_cases']:
            key = proof.digest(case['input_reasoning']); converted = convert({'messages': [{'role': 'assistant', 'output': case['input_reasoning']}]})['input']
            require(key not in cases or cases[key] == converted, 'office_delegation_native_context_reasoning_duplicate')
            cases[key] = converted
    expected_cases = {proof.digest([v for v in c['provider']['response']['output'] if v.get('type') == 'reasoning']) for c in groups[MODELS[0]]}
    require(set(cases) == expected_cases, 'office_delegation_native_context_cases')
    skill = setup['skill']['content']; workflow = office['office_setup']['workflow_skill']['content']
    require(sha256(workflow.encode()).hexdigest() == d['WORKFLOW_SKILL_SHA256'], 'office_delegation_workflow_source')
    for group_index, model in enumerate(MODELS):
        history = groups[model]; initial = None
        for index, call in enumerate(history):
            wire, p = call['wire_before_auth'], call['provider']; scope = d['validate_persisted_scope'](call['verified_cost_scope'])
            prior_requests = provider_requests[:next(i for i, row in enumerate(provider_requests) if row['id'] == p['id'])] if quota else provider_requests
            choice = d['delegated_responses_step'](p['body'], d['delegated_responses_input'](p['body']), parent_requests=prior_requests)
            key_hash = next(m['key_hash'] for m in setup['budget']['models'] if m['model'] == model)
            require(call['auth_user_id'] == actor and call['auth_key_hash'] == key_hash
                    and scope['model'] == model and scope['user_id'] == actor and scope['category'] == 'personal'
                    and scope['chat_id'] == scope['root_chat_id'] == chat
                    and scope['answer_id'] == scope['root_answer_id'] == answer, 'office_delegation_scope')
            require(wire.get('store', False) is False and not wire.get('previous_response_id') and not wire.get('background', False)
                    and p['route'] == '/v1/responses' and p['usage'] == p['response']['usage'] == proof.USAGE
                    and p['response']['id'] == p['id'] and p['response']['model'] == WIRES[model]
                    and p['response']['status'] == 'completed' and p['lifecycle'] == {'terminal': True, 'outcome': 'completed'},
                    'office_delegation_provider_response')
            if initial is None: initial = wire
            require({k: v for k, v in wire.items() if k != 'input'} == {k: v for k, v in initial.items() if k != 'input'},
                    'office_delegation_parameters')
            if group_index == 0: proof.verify_instruction(wire, workflow)
            else:
                proof.verify_schemas(wire['tools'], specs)
                systems = [v for v in wire['input'] if v.get('role') in ('system', 'developer')]
                require(sum(t.count(skill) for t in text_strings(systems)) == 1
                        and sum(t.count(skill) for t in text_strings(wire)) == 1, 'office_delegation_full_template')
                require(not any(v.get('type') == 'reasoning' for v in wire['input']), 'office_delegation_worker_native_baseline')
                texts = '\n'.join(text_strings(wire['input']))
                require(all(value in texts for value in ('Ada Example', 'G584-2026', setup['source_file']['id'])),
                        'office_delegation_worker_facts')
            pairs = task_pairs(wire)
            require(len(pairs) == index and all(c['name'].endswith(ORDER[group_index][i]) for i, (c, _) in enumerate(pairs)),
                    'office_delegation_tool_order')
            requested = [v for v in p['response']['output'] if v.get('type') == 'function_call']
            require(len(requested) == (1 if index < 5 else 0)
                    and (not requested or requested[0]['name'].endswith(ORDER[group_index][index])), 'office_delegation_requested_tool')
            if requested:
                require(requested[0]['name'] == choice[0] and json.loads(requested[0]['arguments']) == choice[1],
                        'office_delegation_actual_choice')
            else:
                if quota:
                    from mock_provider import DELEGATED_QUOTA_REFUSAL
                    require(choice == (None, None, DELEGATED_QUOTA_REFUSAL)
                            and any(n.get('type') == 'output_text' and n.get('text') == DELEGATED_QUOTA_REFUSAL['text']
                                    for n in proof._nodes(p['response']['output'])), 'office_delegation_actual_choice')
                else:
                    require(choice == (None, None, browser['file_id']) and any(
                    n.get('type') == 'output_text' and n.get('text') == '[Download](/api/v1/files/' + browser['file_id'] + '/content)'
                    for n in proof._nodes(p['response']['output'])), 'office_delegation_actual_choice')
            if index:
                prior = history[index - 1]; previous = prior['wire_before_auth']['input']
                if group_index == 0:
                    require(wire['input'][:len(previous)] == previous, 'office_delegation_history_prefix')
                else:
                    require(pairs[:-1] == task_pairs(prior['wire_before_auth']), 'office_delegation_tool_history')
                raw = prior['provider']['response']['output']; previous_call = next(v for v in raw if v.get('type') == 'function_call')
                current_call, result = pairs[-1]
                require(all(current_call[k] == previous_call[k] for k in ('call_id', 'name', 'arguments')),
                        'office_delegation_tool_result_binding')
                if group_index == 0:
                    raw_reasoning = [v for v in raw if v.get('type') == 'reasoning']
                    reasoning = cases[proof.digest(raw_reasoning)] if raw_reasoning else []
                    actual, expected = wire['input'][len(previous):], reasoning + [current_call, result]
                    if actual != expected:
                        shapes = {}
                        for label, items in (('actual', actual), ('expected', expected)):
                            shapes[label] = {'count': len(items), 'sha256': proof.digest(items),
                                'types': [v.get('type') if v.get('type') in ('message', 'reasoning', 'function_call', 'function_call_output') else 'other' for v in items],
                                'empty_text_message': any(v.get('type') == 'message' and (v.get('content') == ''
                                    or isinstance(v.get('content'), list) and all(isinstance(part, dict)
                                        and part.get('type') in ('input_text', 'output_text') and part.get('text') == ''
                                        for part in v['content'])) for v in items)}
                        error = ProofError('office_delegation_native_continuation')
                        error.office_continuation_diagnostic = dict(schema=1, model=model, turn=index + 1, **shapes,
                            first_difference=next((i for i, (a, e) in enumerate(zip(actual, expected)) if a != e), min(len(actual), len(expected))))
                        raise error
    parent = groups[MODELS[0]][-1]['wire_before_auth']
    pp = task_pairs(parent)
    created = json.loads(pp[0][1]['output']); require(len(created['tasks']) == 2 and any(t['status'] in ('pending', 'in_progress') for t in created['tasks']),
                                                   'office_delegation_active_tasks')
    expected_tasks = copy.deepcopy(created['tasks'])
    for index, (call, result) in enumerate(pp[3:]):
        status = 'cancelled' if quota else 'completed'
        require(json.loads(call['arguments']) == {'id': expected_tasks[index]['id'], 'status': status}, 'office_delegation_returned_task_id')
        expected_tasks[index]['status'] = status
        updated = json.loads(result['output'])
        require(isinstance(updated, dict) and updated.get('tasks') == expected_tasks, 'office_delegation_completed_tasks')
    require(browser['stored_chat']['tasks'] == expected_tasks
            and all(t['status'] == ('cancelled' if quota else 'completed') for t in expected_tasks),
            'office_delegation_completed_tasks')
    read_skill = json.loads(pp[1][1]['output'])
    require(read_skill['id'] == setup['skill']['id'] and read_skill['content'] == skill and read_skill.get('next_offset') is None,
            'office_delegation_skill_read')
    if quota:
        return {MODELS[0]: {c['provider']['id']: c['verified_cost_scope'] for c in groups[MODELS[0]]}}
    worker = groups[MODELS[1]][-1]['wire_before_auth']
    wp = task_pairs(worker)
    guide = json.loads(wp[0][1]['output'])
    require(isinstance(guide.get('content'), str) and guide['content'] and guide['content_sha256'] == sha256(guide['content'].encode()).hexdigest(),
            'office_delegation_guide')
    verify_guide(guide, browser, context)
    apply = json.loads(wp[2][0]['arguments']); result = json.loads(wp[2][1]['output'])
    inspect_source = json.loads(wp[1][0]['arguments']); inspected_source = json.loads(wp[1][1]['output'])
    require(inspect_source == {'file_id': setup['source_file']['id'], 'command_payload': {'command': 'query', 'selector': 'paragraph'}}
            and inspected_source['file_id'] == setup['source_file']['id'], 'office_delegation_source_inspection')
    nodes = inspected_source['officecli_result']['data']['results']
    discovered = {}
    for field in ('employee', 'case'):
        label = 'Employee' if field == 'employee' else 'Case'
        matches = [n for n in nodes if n.get('text') == label + ': {{' + field + '}}']
        require(len(matches) == 1 and isinstance(matches[0].get('path'), str), 'office_delegation_discovered_paths')
        discovered[matches[0]['path']] = label + ': ' + ('Ada Example' if field == 'employee' else 'G584-2026')
    require(apply['file_id'] == setup['source_file']['id'] and apply['output_name'] == 'goal584-delegated.docx'
            and len(apply['commands']) == 2 and len({c['path'] for c in apply['commands']}) == 2
            and {c['props']['text'] for c in apply['commands']} == {'Employee: Ada Example', 'Case: G584-2026'}
            and {c['path']: c['props']['text'] for c in apply['commands']} == discovered
            and all(c['command'] == 'set' for c in apply['commands'])
            and result['source_file_id'] == setup['source_file']['id'] and result['source_sha256'] == setup['source_sha256']
            and result['source_bytes_preserved'] is True and result['result_file_id'] == browser['file_id'], 'office_delegation_copy')
    inspected = json.loads(wp[3][1]['output'])
    require(json.loads(wp[3][0]['arguments']) == {'file_id': browser['file_id'], 'command_payload': {'command': 'query', 'selector': 'paragraph'}}
            and inspected['file_id'] == browser['file_id']
            and all(value in [n.get('text') for n in inspected['officecli_result']['data']['results']]
                    for value in ('Employee: Ada Example', 'Case: G584-2026', 'FIXED CLAUSE: preserve this sentence.', 'FIXED TABLE')),
            'office_delegation_result_inspection')
    require(json.loads(wp[4][0]['arguments']) == {'file_id': browser['file_id'], 'format': 'docx', 'grid': 2}, 'office_delegation_render')
    select_render_image(worker, wp[4][0], file_id=browser['file_id'])
    return {m: {c['provider']['id']: c['verified_cost_scope'] for c in groups[m]} for m in MODELS}


def verify_artifacts(browser, office, source):
    setup = selected(office); require(sha256(source).hexdigest() == setup['source_sha256'], 'office_delegation_source_bytes')
    for key in ('source_before', 'source_after'):
        require(browser[key] == {'sha256': setup['source_sha256'], 'bytes': len(source), 'status': 200}, 'office_delegation_source_preservation')
    paths = []
    for key, name in (('browser', 'office-delegation-browser.docx'), ('native', 'office-delegation-browser.native.docx')):
        require(Path(browser['paths'][key]).name == name, 'office_delegation_artifact_path')
        path = PRIVATE / name
        require(path.is_file() and not path.is_symlink() and path.resolve().parent == PRIVATE.resolve()
                and 0 < path.stat().st_size <= MAX_BYTES, 'office_delegation_artifact_path')
        raw = path.read_bytes(); require(browser['artifacts'][key] == {'sha256': sha256(raw).hexdigest(), 'bytes': len(raw)}, 'office_delegation_download')
        paths.append(raw)
    require(paths[0] == paths[1] and browser['foreign_file_statuses'] == [404, 404], 'office_delegation_file_acl_download')
    from io import BytesIO
    def tree(node):
        return (node.tag, sorted(node.attrib.items()), node.text if node.text and node.text.strip() else '', [tree(n) for n in node])
    with ZipFile(BytesIO(source)) as original, ZipFile(BytesIO(paths[0])) as filled:
        require(len(filled.namelist()) == len(set(filled.namelist())) <= 128
                and sum(part.file_size for part in filled.infolist()) <= MAX_BYTES
                and set(original.namelist()) <= set(filled.namelist()), 'office_delegation_docx_parts')
        for name in original.namelist():
            a, b = original.read(name), filled.read(name)
            if name.endswith('.xml') or name.endswith('.rels'):
                left, right = ET.fromstring(a), ET.fromstring(b)
                if name == 'word/document.xml':
                    for old, new in (('Employee: {{employee}}', 'Employee: Ada Example'), ('Case: {{case}}', 'Case: G584-2026')):
                        matches = [n for n in left.iter() if n.text == old]
                        require(len(matches) == 1, 'office_delegation_source_fields'); matches[0].text = new
                require(tree(left) == tree(right), 'office_delegation_docx_preservation')
            else: require(a == b, 'office_delegation_docx_preservation')
    return {'sha256': sha256(paths[0]).hexdigest(), 'bytes': len(paths[0])}


def verify_cost_status(final, cost, actor, chat, answer):
    """Compare the saved display to the existing owner's complete actual snapshot."""
    require(cost.user_id == actor and cost.root_chat_id == chat and cost.root_answer_id == answer
            and cost.complete is True and cost.pagination_complete is True and not cost.missing_call_ids
            and cost.answer.calls == cost.chat.calls == 12 and cost.answer.spend == cost.chat.spend == Decimal('1.32')
            and {m.model: m.calls for m in cost.answer.models} == dict.fromkeys(MODELS, 6), 'office_delegation_cost_snapshot')
    statuses = [s for s in final.get('statusHistory', []) if s.get('action') == 'employee_budget_cost']
    require(statuses and statuses[-1].get('done') is True, 'office_delegation_cost_status')
    description = statuses[-1]['description']; match = re.fullmatch(r'Ответ: \$(\d+(?:\.\d+)?) · Чат: \$(\d+(?:\.\d+)?) · на \d{2}:\d{2}:\d{2} UTC( · начислено на сейчас, учёт обновляется)?', description)
    require(match is not None and Decimal(match[1]) == cost.answer.spend and Decimal(match[2]) == cost.chat.spend,
            'office_delegation_cost_status_amount')
    return bool(match[3])


def verify(before, after, provider, captured, saved, browser, context, office, cost, d):
    setup = selected(office); actor = setup['actor']['id']; chat, answer = browser['chat_id'], browser['answer_id']
    require(browser.get('schema') == 1 and browser['actor_id'] == actor and browser['source_file_id'] == setup['source_file']['id']
            and browser['skill_id'] == setup['skill']['id'] and saved == browser['stored_chat']
            and saved['id'] == chat and saved['user_id'] == actor, 'office_delegation_browser_owner')
    sent = browser['submission']; user = sent['user_message']; messages = saved['chat']['history']['messages']; final = messages[answer]
    text = d['DELEGATED_USER_REQUEST'] + '\nNative Skill ID: ' + setup['skill']['id']
    require(browser['submission_status'] == 200 and sent['model'] == 'corporate-documents' and sent['chat_id'] == chat
            and sent['id'] == answer and user['id'] == browser['user_message_id'] and user['role'] == 'user'
            and user.get('parentId') is None and user['content'] == text
            and messages[user['id']]['content'] == text and final['parentId'] == user['id']
            and final['model'] == 'corporate-documents' and final['done'] is True and not final.get('error')
            and browser['native_running']['task_ids'] == [], 'office_delegation_saved_turn')
    file_id = browser['file_id']; file = browser['native_file']; path = '/api/v1/files/' + file_id + '/content'
    attachments = [f for f in final.get('files', []) if f.get('type') == 'file' and f.get('id') == file_id]
    require(file['id'] == file_id and file['user_id'] == actor and file['meta']['name'] == 'goal584-delegated.docx'
            and len(attachments) == 1 and attachments[0]['name'] == 'goal584-delegated.docx'
            and attachments[0]['url'] == file_id and path in final['content']
            and browser['acknowledgement'].get('chat_id', chat) == chat, 'office_delegation_native_file')
    groups = calls(before, provider, captured)
    scopes = verify_context(groups, office, browser, context, d, provider['requests'])
    main_reasoning = [v for c in groups[MODELS[0]] for v in c['provider']['response']['output'] if v.get('type') == 'reasoning']
    require([v for v in final['output'] if v.get('type') == 'reasoning'] == main_reasoning, 'office_delegation_saved_reasoning')
    require(set(before['finance']['raw_owners']) == set(after['raw_owners']), 'office_delegation_owner_inventory')
    finance = {}
    for model, price, rate_in, rate_out in zip(MODELS, ('.20', '.02'), ('.01', '.001'), ('.02', '.002')):
        key = before['finance']['personal'][model]['key']['token']
        finance[model] = proof.verify_finance(before['finance']['personal'][model], after['personal'][model],
            calls_by_provider=scopes[model], actor=actor, key_hash=key, chat_id=chat, answer_id=answer,
            model=model, wire_model=WIRES[model], deployment_id=DEPLOYMENTS[model], expected_calls=6,
            provider_transport='buffered' if model == MODELS[0] else 'native', expected_call_spend=Decimal(price), input_rate=Decimal(rate_in),
            output_rate=Decimal(rate_out), user_spend_delta=Decimal('1.32'), validate_scope=d['validate_persisted_scope'],
            validate_rates=d['validate_snapshot'], decode_response_id=d['ResponsesAPIRequestUtils']._decode_responses_api_response_id)
        descriptor = before['descriptors'][model]['model_info']['owui_pricing']
        for row in after['personal'][model]['rows']:
            metadata = json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
            snapshot = metadata['spend_logs_metadata']['owui_tariff_descriptor']
            if isinstance(snapshot, dict) and snapshot.get('availability') == 'unknown' and snapshot.get('descriptor') is None:
                from pricing_snapshot import DESCRIPTOR_UNKNOWN_REASONS
                reason = snapshot.get('reason')
                if type(reason) is str and reason in DESCRIPTOR_UNKNOWN_REASONS:
                    raise ProofError('office_delegation_tariff_source_' + reason)
            require(snapshot == {'schema': 1, 'availability': 'available', 'descriptor': descriptor},
                    'office_delegation_tariff_source')
    service = existing.verify_service_turn(groups['gpt-6-luna'][0], before['finance']['service'], after['service'], final,
        actor=actor, payer=office['service_fixture']['payer_id'], chat=chat,
        descriptor=before['descriptors']['service']['model_info']['owui_pricing'], d=d)
    provisional = verify_cost_status(final, cost, actor, chat, answer)
    artifact = verify_artifacts(browser, office, d['delegated_source_docx']())
    return {'personal': finance, 'service': service, 'provider_calls': 13, 'personal_calls': 12,
            'cost_status_provisional': provisional, 'artifact': artifact,
            'worker_reasoning_baseline': 'native_nonstream_no_replayed_encrypted_items', 'saved_main_reasoning_verified': True}


def quota_calls(before, provider, captured, office, browser, d):
    for name, current in (('provider', provider), ('capture', captured)):
        require(current['requests'][:len(before[name]['requests'])] == before[name]['requests'], 'office_quota_prior_context')
    require(provider.get('synthetic') is True and provider.get('control') == before['provider'].get('control'), 'office_quota_provider_control')
    physical = provider['requests'][len(before['provider']['requests']):]
    rows = captured['requests'][len(before['capture']['requests']):]
    require(len(physical) == 7 and len(rows) == 8, 'office_quota_call_count')
    rejected = [row for row in rows if row.get('auth_failure')]
    require(len(rejected) == 1, 'office_quota_denial_count')
    denied = rejected[0]; wire = denied['body']; witness = denied.get('native_budget_denial', {})
    setup = selected(office); actor = setup['actor']['id']
    key = before['finance']['personal'][MODELS[1]]['key']['token']
    scope = d['validate_persisted_scope'](witness.get('scope'))
    require(denied.get('auth_failure') == {'scope':'custom_auth','status_code':422,'code':'unclassified'}
            and witness.get('kind') == 'native_personal_key_budget_denial' and witness.get('entity_type') == 'key'
            and witness.get('key_hash') == key and scope['user_id'] == actor and scope['model'] == MODELS[1]
            and scope['root_chat_id'] == browser['chat_id'] and scope['root_answer_id'] == browser['answer_id']
            and wire == denied.get('body_after_auth') and wire.get('model') == MODELS[1]
            and denied.get('route') in ('/responses','/v1/responses','/openai/v1/responses')
            and denied.get('attestation_present_before') is True and denied.get('provenance_removed_after') is True
            and not any(k in denied for k in ('native_auth_user_id','native_auth_key_hash','verified_cost_scope')),
            'office_quota_native_denial')
    require(not any(row['body'].get('model') == WIRES[MODELS[1]] for row in physical), 'office_quota_worker_dispatched')
    groups = {model: [] for model in (*MODELS, 'gpt-6-luna')}; used = set(); nonces = {scope['call_id']}
    for row in rows:
        if row is denied: continue
        model = row['body'].get('model')
        require(model in (MODELS[0], 'gpt-6-luna'), 'office_quota_admitted_model')
        call = join_responses_call(row, physical, wire_model=WIRES.get(model,'goal584-fake-office-service'),
            provider_transport='buffered' if model == MODELS[0] else 'native')
        nonce = call['verified_cost_scope']['call_id']
        require(call['provider']['id'] not in used and nonce not in nonces, 'office_quota_duplicate_call')
        used.add(call['provider']['id']); nonces.add(nonce); groups[model].append(call)
    require(len(groups[MODELS[0]]) == 6 and len(groups['gpt-6-luna']) == 1 and len(used) == 7, 'office_quota_partition')
    parent = groups[MODELS[0]]
    require(rows.index(denied) == 3 and parent[2]['wire_before_auth'] == rows[2]['body'], 'office_quota_denial_order')
    pairs = task_pairs(parent[3]['wire_before_auth'])
    from mock_provider import DELEGATED_QUOTA_RESULT
    require(len(pairs) == 3 and json.loads(pairs[2][1]['output']) == DELEGATED_QUOTA_RESULT, 'office_quota_tool_error')
    # Validate the complete actual rejected input through the existing finite
    # worker grammar; this is context qualification, never a worker dispatch.
    require(type(wire.get('stream',False)) is bool, 'office_quota_worker_stream')
    body = proof.expected_provider_body(wire, WIRES[MODELS[1]],
        provider_transport='buffered' if wire.get('stream') is True else 'native')
    values=d['delegated_responses_input'](body)
    d['delegated_responses_step'](body, values, parent_requests=provider['requests'])
    prompt=json.loads(pairs[2][0]['arguments'])['prompt']
    require(isinstance(prompt,str) and sum(text.startswith(prompt) for item in values if item.get('role') == 'user'
            for text in text_strings(item.get('content',''))) == 1, 'office_quota_worker_parent_binding')
    workflow = office['office_setup']['workflow_skill']['content']
    proof.verify_instruction(wire, workflow)
    return groups, denied


def quota_answer(saved, actor, chat, user_id, answer_id, request):
    """Pure native saved-lifecycle contract shared with the host browser."""
    from mock_provider import DELEGATED_QUOTA_REFUSAL
    require(isinstance(saved,dict) and saved.get('id') == chat and saved.get('user_id') == actor,'office_quota_chat_owner')
    messages=saved.get('chat',{}).get('history',{}).get('messages',{})
    user,answer=messages.get(user_id),messages.get(answer_id)
    if user is None or answer is None:return None
    require(user.get('id') == user_id and user.get('role') == 'user' and user.get('parentId') is None and user.get('content') == request
            and answer.get('id') == answer_id and answer.get('role') == 'assistant' and answer.get('parentId') == user_id
            and answer.get('model') == 'corporate-documents' and saved['chat']['history'].get('currentId') == answer_id
            and not answer.get('error'),'office_quota_saved_ancestry')
    if answer.get('done') is not True:return None
    tasks=saved.get('tasks')
    if not isinstance(tasks,list) or not tasks:return None
    require(len(tasks) == 2 and all(isinstance(t,dict) and isinstance(t.get('id'),str) and t['id']
            and isinstance(t.get('content'),str) and t['content'].strip() for t in tasks)
            and len({t['id'] for t in tasks}) == 2,'office_quota_tasks_shape')
    if any(t.get('status') != 'cancelled' for t in tasks):return None
    require(answer.get('content') == DELEGATED_QUOTA_REFUSAL['text'] and not answer.get('files')
            and '/api/v1/files/' not in json.dumps(answer,ensure_ascii=False),'office_quota_refusal')
    statuses=[v for v in answer.get('statusHistory',[]) if isinstance(v,dict) and v.get('action') == 'employee_budget_cost']
    if not statuses or statuses[-1].get('done') is not True:return None
    require(isinstance(statuses[-1].get('description'),str) and bool(statuses[-1]['description'].strip()),'office_quota_cost_status')
    followups=answer.get('followUps')
    if not isinstance(followups,list) or not followups:return None
    require(all(isinstance(v,str) and v.strip() for v in followups),'office_quota_followups')
    return answer,statuses[-1]


def verify_quota(before, after, provider, captured, saved, browser, context, office, cost, d):
    setup = selected(office); actor = setup['actor']['id']; chat, answer = browser['chat_id'], browser['answer_id']
    sent = browser['submission']; user = sent['user_message']
    require(browser.get('actor_id') == actor and browser.get('submission_status') == 200
            and browser.get('source_file_id') == setup['source_file']['id'] and browser.get('skill_id') == setup['skill']['id']
            and sent.get('model') == 'corporate-documents' and sent.get('chat_id') == chat and sent.get('id') == answer
            and browser.get('user_message_id') == user.get('id')
            and browser['acknowledgement'].get('chat_id',chat) == chat and saved == browser['stored_chat']
            and browser['native_running'].get('task_ids') == [], 'office_quota_saved_turn')
    observed = quota_answer(saved, actor, chat, user['id'], answer,
        d['DELEGATED_USER_REQUEST']+'\nNative Skill ID: '+setup['skill']['id'])
    require(observed is not None, 'office_quota_lifecycle')
    final, status = observed
    require(browser['native_skill'] == setup['skill']
            and browser['source_before_sha256'] == browser['source_after_sha256'] == setup['source_sha256'], 'office_quota_source_changed')
    groups, denied = quota_calls(before, provider, captured, office, browser, d)
    proof.verify_schemas(denied['body']['tools'],context['packets'][0]['native_specs'])
    # Reuse complete parent Tool/Skill/history/reasoning checks, changing only
    # the already-approved terminal cancellation/refusal expectation.
    scopes = verify_context(groups, office, browser, context, d, provider['requests'], quota=True)
    require([v for v in final.get('output',[]) if v.get('type') == 'reasoning'] ==
            [v for c in groups[MODELS[0]] for v in c['provider']['response']['output'] if v.get('type') == 'reasoning'],
            'office_quota_saved_reasoning')
    model = MODELS[0]; key = before['finance']['personal'][model]['key']['token']
    finance = proof.verify_finance(before['finance']['personal'][model], after['personal'][model],
        calls_by_provider=scopes[model], actor=actor, key_hash=key, chat_id=chat, answer_id=answer,
        model=model, wire_model=WIRES[model], deployment_id=DEPLOYMENTS[model], expected_calls=6,
        provider_transport='buffered', expected_call_spend=Decimal('.20'), input_rate=Decimal('.01'), output_rate=Decimal('.02'),
        validate_scope=d['validate_persisted_scope'], validate_rates=d['validate_snapshot'],
        decode_response_id=d['ResponsesAPIRequestUtils']._decode_responses_api_response_id)
    old, current = before['finance']['personal'][MODELS[1]], after['personal'][MODELS[1]]
    require(protected_r(old['user'],old['key']) == protected_r(current['user'],current['key'])
            and amount(current['key']['spend']) == amount(old['key']['spend'])
            and old['old_payers'] == current['old_payers']
            and all(row in current['rows'] for row in old['rows']), 'office_quota_worker_finance')
    added = [row for row in current['rows'] if row not in old['rows']]
    require(all(amount(row.get('spend')) == 0 and row.get('status') in ('failure','failed','blocked')
                and row.get('user') == actor and row.get('api_key') == current['key']['token'] for row in added),
            'office_quota_denial_charge')
    require(set(before['finance']['raw_owners']) == set(after['raw_owners']), 'office_quota_owner_inventory')
    service = existing.verify_service_turn(groups['gpt-6-luna'][0], before['finance']['service'], after['service'], final,
        actor=actor, payer=office['service_fixture']['payer_id'], chat=chat,
        descriptor=before['descriptors']['service']['model_info']['owui_pricing'], d=d,
        expected_user_request=d['DELEGATED_USER_REQUEST'])
    # Strict cost-reader output/error is retained verbatim by its own owner.
    # It may remain pending/unavailable for the denied call; never turn it into 0.
    require(cost.get('snapshot') is not None or cost.get('error') in ('usage_unavailable','accounting_unavailable'), 'office_quota_cost_readback')
    if cost.get('snapshot') is not None:
        snapshot=cost['snapshot']
        require(snapshot.get('user_id') == actor and snapshot.get('root_chat_id') == chat
                and snapshot.get('root_answer_id') == answer, 'office_quota_cost_scope')
        from litellm.proxy.types_utils.utils import get_instance_fn
        from provision_cost_display import FILTER_SOURCE
        money_text=get_instance_fn('cost_filter.money_text',config_file_path=str(FILTER_SOURCE))
        for name in ('answer','chat'):
            total=snapshot[name]
            require(total['calls'] == 6 and Decimal(str(total['spend'])) == Decimal('1.20')
                    and {v['model']:v['calls'] for v in total['models']} == {MODELS[0]:6}, 'office_quota_cost_snapshot')
            if '$' in status['description']:
                require(money_text(Decimal(str(total['spend']))) in status['description'], 'office_quota_cost_display')
    else: require('$' not in status['description'], 'office_quota_cost_display')
    return dict(personal=finance, service=service, native_denial_status=422, worker_provider_calls=0,
        captured_attempts=8, provider_calls=7, worker_added_failure_rows=len(added),
        row_absence_is_not_zero_cost_proof=not added, worker_expense_final=False, cost_readback=cost, cost_status=status)


def quota_cap_only(before, after, key_hash, cap):
    """Compare native protected fields/rows/counters, allowing only this cap."""
    require(set(before['raw_owners']) == set(after['raw_owners']), 'office_quota_cap_owner_drift')
    for uid, old in before['raw_owners'].items():
        current=after['raw_owners'][uid]
        previous={k['token']:k for k in old['keys']}; actual={k['token']:k for k in current['keys']}
        require(set(previous) == set(actual) and current['rows'] == old['rows']
                and amount(current['user']['spend']) == amount(old['user']['spend']), 'office_quota_cap_owner_drift')
        for token,key in previous.items():
            expected=protected_r(old['user'],key)
            if token == key_hash: expected['key']['max_budget']=float(cap)
            require(protected_r(current['user'],actual[token]) == expected
                    and amount(actual[token]['spend']) == amount(key['spend']), 'office_quota_cap_owner_drift')


def quota_save(state, d):
    require(len(json.dumps(state,allow_nan=False).encode()) <= MAX_BYTES,'office_delegation_private_bound')
    d['write_private'](STATE,state)


def quota_restore(state, native, office, d):
    q = state['quota']; cap = Decimal(q['original_cap']); restricted = Decimal(q['restricted_cap'])
    if q.get('stage') == 'restored': return
    packet_path=PRIVATE/'office-delegation-quota.private.json'
    if packet_path.exists():
        from prove_pricing_snapshots import canonical_id
        packet=d['read_private'](packet_path); chat=canonical_id(packet.get('chat_id'))
        active=d['WebUI']().ok('GET','/api/tasks/chat/'+chat,token=selected(office)['actor']['token'])
        require(active.get('task_ids') == [], 'office_quota_restore_background_active')
    try: current = inventory(native, office, worker_cap=restricted)
    except ProofError: current = inventory(native, office, worker_cap=cap)
    baseline = q['finance']['personal'][MODELS[1]]; actual = current['personal'][MODELS[1]]
    expected=protected_r(baseline['user'],baseline['key']); expected['key']['max_budget']=actual['key']['max_budget']
    require(amount(actual['key']['max_budget']) in (restricted,cap)
            and protected_r(actual['user'],actual['key']) == expected
            and amount(actual['key']['spend']) == amount(baseline['key']['spend']), 'office_quota_restore_drift')
    q['journal'].append('restore_pre_write'); quota_save(state,d)
    async def restore():
        from employee_budget_admin_client import BudgetAdminClient
        async with d['ClientSession'](trust_env=False) as session:
            await BudgetAdminClient(session, 'http://proxy:4000', d['read_private'](d['OPERATOR_STATE'])['operator_token']).set_model_cap(actual['key']['token'],cap)
    asyncio.run(restore())
    def ready():
        observed = inventory(native, office)
        quota_cap_only(current,observed,actual['key']['token'],cap)
        return observed
    q['restored_inventory'] = native.poll('Only original Terra cap restored',ready)
    q['stage']='restored'; q['journal'].append('restore_readback'); quota_save(state,d)


def quota_quiesce(state, office, d):
    """Stop only this failed/finished negative chat; never replace product Task evidence."""
    from prove_pricing_snapshots import canonical_id
    q = state['quota']; packet_path = PRIVATE/'office-delegation-quota.private.json'
    if not packet_path.exists():
        q['cleanup'] = {'packet_present': False}; quota_save(state, d)
        return
    packet = d['read_private'](packet_path); setup = selected(office)
    chat = canonical_id(packet.get('chat_id')); actor = setup['actor']
    require(packet.get('actor_id') == actor['id'] and chat != state['browser']['chat_id'], 'office_quota_cleanup_identity')
    webui = d['WebUI'](); webui.session(actor, 'user')
    saved = webui.ok('GET', '/api/v1/chats/'+chat, token=actor['token'])
    require(saved.get('id') == chat and saved.get('user_id') == actor['id'], 'office_quota_cleanup_owner')
    active = webui.ok('GET', '/api/tasks/chat/'+chat, token=actor['token'])
    require(isinstance(active.get('task_ids'), list), 'office_quota_cleanup_tasks')
    q['cleanup'] = {'packet_present': True, 'chat_id': chat, 'before': active, 'saved_chat': saved}
    q['journal'].append('quiesce_before_stop'); quota_save(state, d)
    if active['task_ids']:
        q['cleanup']['stop'] = webui.ok('POST', '/api/tasks/chat/'+chat+'/stop', token=actor['token'])
        quota_save(state, d)
    observed = webui.ok('GET', '/api/tasks/chat/'+chat, token=actor['token'])
    q['cleanup']['after'] = observed; quota_save(state, d)
    require(observed.get('task_ids') == [], 'office_quota_cleanup_active')
    q['journal'].append('quiesce_readback'); quota_save(state, d)


def quota_run(phase, d):
    office=d['read_private'](OFFICE); setup=selected(office); state=d['read_private'](STATE)
    require(state.get('stage') == 'verified_readback' and state.get('prepared_sha256') == proof.digest(office), 'office_quota_positive_required')
    if phase == 'quota-status':
        q = state.get('quota')
        return dict(schema=1, phase=phase, passed=True, native_office_accepted=False,
                    quota_present=isinstance(q, dict), quota_stage=q.get('stage') if isinstance(q, dict) else None)
    if phase == 'quota-quiesce':
        require(isinstance(state.get('quota'), dict), 'office_quota_not_ready')
        quota_quiesce(state, office, d)
        return dict(schema=1, phase=phase, passed=True, native_office_accepted=False, quota_stage=state['quota']['stage'])
    native=d['native_client'](d['read_private'](COMMON)); native.started_at=datetime.fromisoformat(state['history_start_utc'])
    def observe():
        with d['capture'].capture_lock(): captured=d['capture']._read_locked()
        return d['provider'](),captured
    if phase == 'quota-baseline':
        require('quota' not in state, 'office_quota_baseline_exists')
        require(not (PRIVATE/'office-delegation-quota.private.json').exists(), 'office_quota_browser_exists')
        finance=inventory(native,office); provider,captured=observe()
        require(provider == state['provider_after'] and captured == state['capture_after'], 'office_quota_positive_changed')
        require(len(captured['requests']) + 8 <= d['capture'].MAX_RECORDS, 'office_quota_capture_capacity')
        worker=finance['personal'][MODELS[1]]['key']; cap=amount(worker['max_budget']); spend=amount(worker['spend'])
        quota_cap_only(state['after'],finance,worker['token'],cap)
        require(spend < cap, 'office_quota_worker_not_freshly_exhaustible')
        q=dict(stage='restricting',original_cap=str(cap),restricted_cap=str(spend),journal=['restrict_pre_write'],
            finance=finance,provider=provider,capture=captured,descriptors=state['descriptors'])
        state['quota']=q; quota_save(state,d)
        async def restrict():
            from employee_budget_admin_client import BudgetAdminClient
            async with d['ClientSession'](trust_env=False) as session:
                await BudgetAdminClient(session,'http://proxy:4000',d['read_private'](d['OPERATOR_STATE'])['operator_token']).set_model_cap(worker['token'],spend)
        try:
            asyncio.run(restrict()); q['journal'].append('restrict_returned'); quota_save(state,d)
            after=inventory(native,office,worker_cap=spend)
            quota_cap_only(finance,after,worker['token'],spend)
            q.update(finance=after,stage='baseline_ready'); q['journal'].append('restrict_readback'); quota_save(state,d)
        except BaseException:
            try: quota_restore(state,native,office,d)
            except BaseException:
                q['stage']='restore_failed'; quota_save(state,d)
                raise
            raise
    else:
        q=state['quota']; require(q.get('stage') == 'baseline_ready'
            or phase == 'quota-restore' and q.get('stage') in ('restricting','restore_failed','restored'), 'office_quota_not_ready')
        try:
            if phase == 'quota-verify':
                browser=d['read_private'](PRIVATE/'office-delegation-quota.private.json')
                context=d['read_private'](PRIVATE/'office-delegation-quota-context.private.json')
                require(descriptors(native.ok('GET','/model/info')['data']) == q['descriptors'], 'office_quota_descriptor_changed')
                def settled():
                    saved=d['WebUI']().ok('GET','/api/v1/chats/'+browser['chat_id'],token=setup['actor']['token'])
                    active=d['WebUI']().ok('GET','/api/tasks/chat/'+browser['chat_id'],token=setup['actor']['token'])
                    require(active.get('task_ids') == [], 'office_quota_background_active')
                    after=inventory(native,office,worker_cap=Decimal(q['restricted_cap'])); provider,captured=observe()
                    async def read_cost():
                        from dataclasses import asdict
                        from employee_budget_cost_readback import CostReadError
                        valves=d['WebUI']().ok('GET','/api/v1/functions/id/'+d['FILTER_ID']+'/valves',token=office['admin']['token'])
                        async with d['ClientSession'](trust_env=False) as session:
                            try:
                                cost=await d['read_cost_snapshot'](session,base_url=valves['ledger_base_url'],read_key=valves['ledger_read_key'],
                                    user_id=setup['actor']['id'],root_chat_id=browser['chat_id'],root_answer_id=browser['answer_id'],
                                    observed_call_ids=[(r.get('verified_cost_scope') or r.get('native_budget_denial',{}).get('scope',{})).get('call_id')
                                        for r in captured['requests'][len(q['capture']['requests']):] if r['body'].get('model') in MODELS],wait_seconds=0)
                                return {'snapshot':json.loads(json.dumps(asdict(cost),default=str))}
                            except CostReadError as error: return {'error':error.code}
                    cost=asyncio.run(read_cost()); q['last_observation']=dict(after=after,provider=provider,capture=captured,saved_chat=saved,cost=cost)
                    quota_save(state,d)
                    try: return verify_quota(q,after,provider,captured,saved,browser,context,office,cost,d)
                    except ProofError as error:
                        if str(error) in ('office_row_count','office_native_spend_delta','office_service_row_count','office_service_native_spend_delta'):return None
                        raise
                q['result']=native.poll('Quota denial and complete admitted native finance',settled)
        finally:
            try: quota_restore(state,native,office,d)
            except BaseException:
                q['stage']='restore_failed'; quota_save(state,d)
                raise
    result = dict(schema=1,phase=phase,passed=True,native_office_accepted=False,quota_stage=state['quota']['stage'])
    if phase == 'quota-baseline':
        result.update(provider_prefix_count=len(state['quota']['provider']['requests']),
                      provider_prefix_sha256=proof.digest(state['quota']['provider']))
    return result


def quota_public_readback(q, capture):
    """Project existing validated quota facts; never export the private journal/result."""
    journal = q['journal']; restricted = q['finance']['personal'][MODELS[1]]['key']
    worker = {'original_cap_usd': str(amount(q['original_cap'])),
              'restricted_cap_usd': str(amount(q['restricted_cap'])),
              'restriction_readback_complete': 'restrict_readback' in journal,
              'restricted_readback': None, 'restored_readback': None, 'restoration_complete': False}
    if worker['restriction_readback_complete']:
        worker['restricted_readback'] = {'cap_usd': str(amount(restricted['max_budget'])),
                                        'spend_usd': str(amount(restricted['spend']))}
        require(amount(restricted['max_budget']) == amount(q['restricted_cap'])
                and amount(restricted['spend']) == amount(q['restricted_cap']), 'office_quota_public_restriction')
    if 'restored_inventory' in q:
        restored = q['restored_inventory']['personal'][MODELS[1]]['key']
        worker['restored_readback'] = {'cap_usd': str(amount(restored['max_budget'])),
                                      'spend_usd': str(amount(restored['spend']))}
        worker['restoration_complete'] = (q['stage'] == 'restored' and 'restore_readback' in journal
            and amount(restored['max_budget']) == amount(q['original_cap'])
            and amount(restored['spend']) == amount(restricted['spend']))
    require(q['stage'] != 'restored' or worker['restoration_complete'], 'office_quota_public_restore')
    with capture.capture_lock():
        observed = capture._read_locked()
        with capture.CAPTURE.open('rb') as handle: raw = handle.read(capture.MAX_BYTES + 1)
        require(len(raw) == capture.CAPTURE.stat().st_size and len(raw) <= capture.MAX_BYTES
                and json.loads(raw) == observed, 'office_quota_public_capture')
    value = {'worker': worker, 'capture': {'total_records': len(observed['requests']),
        'serialized_bytes': len(raw), 'sha256': sha256(raw).hexdigest(),
        'max_records': capture.MAX_RECORDS, 'max_bytes': capture.MAX_BYTES}}
    if 'result' in q:
        result = q['result']
        summary = {key: result[key] for key in ('native_denial_status', 'worker_provider_calls',
            'captured_attempts', 'provider_calls', 'worker_added_failure_rows',
            'row_absence_is_not_zero_cost_proof', 'worker_expense_final')}
        for group in ('personal', 'service'):
            summary[group] = {key: result[group][key] for key in
                              ('physical_calls', 'new_raw_rows', 'native_spend_delta_usd')}
        value['verified'] = summary
    return value


def run(phase, d):
    if phase.startswith('quota-'):
        result = quota_run(phase,d)
        if phase in ('quota-baseline', 'quota-verify', 'quota-restore'):
            result['quota_readback'] = quota_public_readback(d['read_private'](STATE)['quota'], d['capture'])
        result['source_sha256'] = sha256(Path(__file__).read_bytes()).hexdigest()
        d['no_credentials'](result)
        return result
    common, office = d['read_private'](COMMON), d['read_private'](OFFICE); setup = selected(office)
    native = d['native_client'](common); operator = d['read_private'](d['OPERATOR_STATE'])
    native.started_at = min(datetime.fromisoformat(common['started_at_utc']), datetime.fromisoformat(operator['started_at'])) - timedelta(minutes=1)
    def observe():
        with d['capture'].capture_lock(): captured = d['capture']._read_locked()
        return d['provider'](), captured
    if phase == 'baseline':
        require(not STATE.exists(), 'office_delegation_baseline_exists')
        finance = inventory(native, office); provider, captured = observe()
        require(all(not v['rows'] for v in finance['personal'].values()), 'office_delegation_actor_not_fresh')
        state = dict(schema=1, stage='baseline', prepared_sha256=proof.digest(office), finance=finance,
            provider=provider, capture=captured, descriptors=descriptors(native.ok('GET', '/model/info')['data']),
            history_start_utc=native.started_at.isoformat())
        result = {'owners': len(finance['raw_owners']), 'personal_assignments': 2}
    else:
        state = d['read_private'](STATE)
        require(state['stage'] == 'baseline' and state['prepared_sha256'] == proof.digest(office)
                and state['history_start_utc'] == native.started_at.isoformat(), 'office_delegation_baseline_changed')
        require(descriptors(native.ok('GET', '/model/info')['data']) == state['descriptors'], 'office_delegation_descriptor_changed')
        if phase == 'diagnostic':
            provider, captured = observe()
            state['diagnostic'] = dict(provider=provider, capture=captured)
            # Retain actual observations even if native capacity inspection fails.
            d['write_private'](STATE, state)
            state['diagnostic']['capacity'] = capacity_observations(captured['requests'][len(state['capture']['requests']):], state['descriptors'])
            result = {'provider_added': len(provider['requests']) - len(state['provider']['requests']),
                      'auth_added': len(captured['requests']) - len(state['capture']['requests'])}
        else:
            browser, context = d['read_private'](BROWSER), d['read_private'](CONTEXT)
            def settled():
                saved = d['WebUI']().ok('GET', '/api/v1/chats/' + browser['chat_id'], token=setup['actor']['token'])
                after = inventory(native, office); provider, captured = observe()
                state['last_observation'] = dict(after=after, provider=provider, capture=captured, saved_chat=saved)
                require(len(json.dumps(state, allow_nan=False).encode()) <= MAX_BYTES, 'office_delegation_private_bound')
                d['write_private'](STATE, state)
                state['last_observation']['capacity'] = capacity_observations(captured['requests'][len(state['capture']['requests']):], state['descriptors'])
                valves = d['WebUI']().ok('GET', '/api/v1/functions/id/' + d['FILTER_ID'] + '/valves', token=office['admin']['token'])
                async def read_cost():
                    async with d['ClientSession'](trust_env=False) as session:
                        return await d['read_cost_snapshot'](session, base_url=valves['ledger_base_url'], read_key=valves['ledger_read_key'],
                            user_id=setup['actor']['id'], root_chat_id=browser['chat_id'], root_answer_id=browser['answer_id'],
                            observed_call_ids=[r['verified_cost_scope']['call_id'] for r in captured['requests'][len(state['capture']['requests']):]
                                               if r.get('verified_cost_scope', {}).get('category') == 'personal'], wait_seconds=0)
                cost = asyncio.run(read_cost())
                from dataclasses import asdict
                state['last_observation']['cost_snapshot'] = json.loads(json.dumps(asdict(cost), default=str))
                d['write_private'](STATE, state)
                try: result = verify(state, after, provider, captured, saved, browser, context, office, cost, d)
                except ProofError as error:
                    state['failure_code'] = str(error) if re.fullmatch(r'office_[a-z_]+', str(error)) else 'office_delegation_readback_failed'
                    d['write_private'](STATE, state)
                    if str(error) in ('office_row_count', 'office_native_spend_delta', 'office_service_row_count', 'office_service_native_spend_delta', 'office_delegation_cost_snapshot'):
                        return None
                    raise
                return result, after, provider, captured, saved
            result, after, provider, captured, saved = native.poll('Delegated Office complete native rows and counters', settled)
            state.update(stage='verified_readback', after=after, provider_after=provider, capture_after=captured, saved_chat=saved,
                         browser=browser, native_context=context, capacity=state['last_observation']['capacity'],
                         cost_snapshot=state['last_observation']['cost_snapshot'])
            state.pop('last_observation', None); state.pop('failure_code', None)
    require(len(json.dumps(state, allow_nan=False).encode()) <= MAX_BYTES, 'office_delegation_private_bound')
    d['write_private'](STATE, state)
    result = dict(schema=1, phase=phase, passed=True, native_office_accepted=False,
                  readback_sha256=proof.digest(state), source_sha256=sha256(Path(__file__).read_bytes()).hexdigest(), **result)
    d['no_credentials'](result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--phase', choices=('baseline', 'diagnostic', 'verify', *QUOTA_PHASES), required=True)
    args = parser.parse_args()
    d = None
    try:
        d = dependencies()
        result = run(args.phase, d)
    except Exception as error:
        code = str(error) if isinstance(error, ProofError) else ''
        result = dict(schema=1, phase=args.phase, passed=False, native_office_accepted=False,
                      source_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                      failure_code=code if re.fullmatch(r'office_[a-z_]+', code) else 'office_delegation_readback_failed')
        diagnostic = getattr(error, 'office_continuation_diagnostic', None)
        if code == 'office_delegation_native_continuation' and d is not None and isinstance(diagnostic, dict):
            try:
                require(type(diagnostic) is dict and all(type(k) is str for k in diagnostic)
                        and set(diagnostic) == {'schema', 'model', 'turn', 'actual', 'expected', 'first_difference'},
                        'office_continuation_diagnostic_shape')
                public = {'schema': diagnostic['schema'], 'model': diagnostic['model'], 'turn': diagnostic['turn'],
                          'actual': {}, 'expected': {}, 'first_difference': diagnostic['first_difference']}
                require(type(public['schema']) is int and public['schema'] == 1
                        and type(public['model']) is str and public['model'] in MODELS
                        and type(public['turn']) is int and 1 <= public['turn'] <= 6
                        and type(public['first_difference']) is int and 0 <= public['first_difference'] <= 128,
                        'office_continuation_diagnostic_shape')
                for label in ('actual', 'expected'):
                    shape = diagnostic[label]
                    require(type(shape) is dict and all(type(k) is str for k in shape)
                            and set(shape) == {'count', 'sha256', 'types', 'empty_text_message'}
                            and type(shape['types']) is list, 'office_continuation_diagnostic_shape')
                    shape = {'count': shape['count'], 'sha256': shape['sha256'], 'types': list(shape['types']),
                             'empty_text_message': shape['empty_text_message']}
                    require(type(shape['count']) is int and 0 <= shape['count'] <= 128
                            and len(shape['types']) == shape['count']
                            and all(type(v) is str and v in ('message', 'reasoning', 'function_call', 'function_call_output', 'other') for v in shape['types'])
                            and type(shape['sha256']) is str and re.fullmatch(r'[0-9a-f]{64}', shape['sha256'])
                            and type(shape['empty_text_message']) is bool, 'office_continuation_diagnostic_shape')
                    public[label] = shape
                require(len(json.dumps(public, allow_nan=False).encode()) <= 16 * 1024, 'office_continuation_diagnostic_bound')
                d['no_credentials'](public)
            except Exception:
                pass  # Preserve the original failure, never export an unsafe diagnostic.
            else:
                result['continuation_diagnostic'] = public
    print(json.dumps(result, allow_nan=False)); return 0 if result['passed'] else 1


if __name__ == '__main__': raise SystemExit(main())
