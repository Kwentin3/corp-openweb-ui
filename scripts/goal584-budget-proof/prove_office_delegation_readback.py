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


def inventory(native, office):
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
        require(key['models'] == [model] and key['user_id'] == actor and amount(key['max_budget']) == Decimal(1000),
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
        require(model in groups and wire == row['body_after_auth'] and not row.get('auth_failure')
                and row['attestation_present_before'] is True and row['provenance_removed_after'] is True
                and row['route'] in ('/responses', '/v1/responses', '/openai/v1/responses'), 'office_delegation_auth_context')
        target = WIRES.get(model, 'goal584-fake-office-service')
        expected = proof.expected_provider_body(wire, target, provider_transport='buffered' if model == MODELS[0] else 'native')
        matches = [p for p in physical if p['body'] == expected]
        require(len(matches) == 1 and matches[0]['id'] not in used, 'office_delegation_provider_join')
        p = copy.deepcopy(matches[0]); used.add(p['id'])
        p['lifecycle'] = {k: p['lifecycle'][k] for k in ('terminal', 'outcome')}
        scope = row['verified_cost_scope']
        require(scope['call_id'] not in nonces, 'office_delegation_nonce')
        nonces.add(scope['call_id'])
        groups[model].append(dict(wire_before_auth=wire, wire_after_auth=row['body_after_auth'],
            auth_user_id=row['native_auth_user_id'], auth_key_hash=row['native_auth_key_hash'],
            attestation_present_before=True, provenance_removed_after=True, route=row['route'], verified_cost_scope=scope, provider=p))
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


def verify_context(groups, office, browser, context, d, provider_requests):
    setup = selected(office); actor = setup['actor']['id']; chat, answer = browser['chat_id'], browser['answer_id']
    require(context.get('schema') == 1 and isinstance(context.get('packets'), list) and context['packets'],
            'office_delegation_native_context')
    personal = [c for m in MODELS for c in groups[m]]
    require(set(context['provider_ids']) == {c['provider']['id'] for c in personal}
            and len(context['provider_ids']) == 12, 'office_delegation_native_context')
    cases, specs = {}, None
    for packet in context['packets']:
        convert = existing.native_converter(packet, office)
        if specs is not None: require(specs == packet['native_specs'], 'office_delegation_native_context')
        specs = packet['native_specs']
        for case in packet['reasoning_cases']:
            key = proof.digest(case['input_reasoning']); converted = convert({'messages': [{'role': 'assistant', 'output': case['input_reasoning']}]})['input']
            require(key not in cases or cases[key] == converted, 'office_delegation_native_context')
            cases[key] = converted
    expected_cases = {proof.digest([v for v in c['provider']['response']['output'] if v.get('type') == 'reasoning']) for c in groups[MODELS[0]]}
    require(set(cases) == expected_cases, 'office_delegation_native_context')
    skill = setup['skill']['content']; workflow = office['office_setup']['workflow_skill']['content']
    require(sha256(workflow.encode()).hexdigest() == d['WORKFLOW_SKILL_SHA256'], 'office_delegation_workflow_source')
    for group_index, model in enumerate(MODELS):
        history = groups[model]; initial = None
        for index, call in enumerate(history):
            wire, p = call['wire_before_auth'], call['provider']; scope = d['validate_persisted_scope'](call['verified_cost_scope'])
            choice = d['delegated_responses_step'](p['body'], d['delegated_responses_input'](p['body']), parent_requests=provider_requests)
            key_hash = next(m['key_hash'] for m in setup['budget']['models'] if m['model'] == model)
            require(call['auth_user_id'] == actor and call['auth_key_hash'] == key_hash
                    and scope['model'] == model and scope['user_id'] == actor and scope['category'] == 'personal'
                    and scope['chat_id'] == scope['root_chat_id'] == chat
                    and scope['answer_id'] == scope['root_answer_id'] == answer, 'office_delegation_scope')
            require(wire.get('store') is False and not wire.get('previous_response_id') and not wire.get('background', False)
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
                    reasoning = cases[proof.digest([v for v in raw if v.get('type') == 'reasoning'])]
                    require(wire['input'][len(previous):] == reasoning + [current_call, result], 'office_delegation_native_continuation')
    parent, worker = (groups[m][-1]['wire_before_auth'] for m in MODELS)
    pp, wp = task_pairs(parent), task_pairs(worker)
    created = json.loads(pp[0][1]['output']); require(len(created['tasks']) == 2 and any(t['status'] in ('pending', 'in_progress') for t in created['tasks']),
                                                   'office_delegation_active_tasks')
    expected_tasks = copy.deepcopy(created['tasks'])
    for index, (call, result) in enumerate(pp[3:]):
        require(json.loads(call['arguments']) == {'id': expected_tasks[index]['id'], 'status': 'completed'}, 'office_delegation_returned_task_id')
        expected_tasks[index]['status'] = 'completed'
        require(json.loads(result['output'])['tasks'] == expected_tasks, 'office_delegation_completed_tasks')
    require(browser['stored_chat']['tasks'] == expected_tasks and all(t['status'] == 'completed' for t in expected_tasks),
            'office_delegation_completed_tasks')
    read_skill = json.loads(pp[1][1]['output'])
    require(read_skill['id'] == setup['skill']['id'] and read_skill['content'] == skill and read_skill.get('next_offset') is None,
            'office_delegation_skill_read')
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
    pngs = [n['image_url'] for n in proof._nodes(wp[4][1]['output']) if n.get('type') == 'input_image']
    require(len(pngs) == 1 and pngs[0].startswith('data:image/png;base64,'), 'office_delegation_png')
    png = base64.b64decode(pngs[0].partition(',')[2], validate=True)
    require(len(png) >= 24 and png.startswith(b'\x89PNG\r\n\x1a\n') and png[12:16] == b'IHDR', 'office_delegation_png')
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
            provider_transport='buffered', expected_call_spend=Decimal(price), input_rate=Decimal(rate_in),
            output_rate=Decimal(rate_out), user_spend_delta=Decimal('1.32'), validate_scope=d['validate_persisted_scope'],
            validate_rates=d['validate_snapshot'], decode_response_id=d['ResponsesAPIRequestUtils']._decode_responses_api_response_id)
        descriptor = before['descriptors'][model]['model_info']['owui_pricing']
        for row in after['personal'][model]['rows']:
            metadata = json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
            require(metadata['spend_logs_metadata']['owui_tariff_descriptor'] == {
                'schema': 1, 'availability': 'available', 'descriptor': descriptor}, 'office_delegation_tariff_source')
    service = existing.verify_service_turn(groups['gpt-6-luna'][0], before['finance']['service'], after['service'], final,
        actor=actor, payer=office['service_fixture']['payer_id'], chat=chat,
        descriptor=before['descriptors']['service']['model_info']['owui_pricing'], d=d)
    provisional = verify_cost_status(final, cost, actor, chat, answer)
    artifact = verify_artifacts(browser, office, d['delegated_source_docx']())
    return {'personal': finance, 'service': service, 'provider_calls': 13, 'personal_calls': 12,
            'cost_status_provisional': provisional, 'artifact': artifact,
            'worker_reasoning_baseline': 'native_nonstream_no_replayed_encrypted_items', 'saved_main_reasoning_verified': True}


def run(phase, d):
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
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--phase', choices=('baseline', 'diagnostic', 'verify'), required=True)
    args = parser.parse_args()
    try: result = run(args.phase, dependencies())
    except Exception as error:
        code = str(error) if isinstance(error, ProofError) else ''
        result = dict(schema=1, phase=args.phase, passed=False, native_office_accepted=False,
                      failure_code=code if re.fullmatch(r'office_[a-z_]+', code) else 'office_delegation_readback_failed')
    print(json.dumps(result, allow_nan=False)); return 0 if result['passed'] else 1


if __name__ == '__main__': raise SystemExit(main())
