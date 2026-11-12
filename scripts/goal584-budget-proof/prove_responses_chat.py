#!/usr/bin/env python3
"""Bounded source candidate: ordinary native Send, one Responses Tool round.

Host owns the existing disposable fixture/browser; worker uses existing native
API/private-I/O owners. No inference retries, provider reset, finance deletion,
ID rewrite/decryption, alternative auth, ledger, or native core modification.
Mount/CI activation belongs to the parent. This module imports no browser/native
runtime until its explicit host/worker entrypoint is invoked.
"""
from __future__ import annotations

import argparse
import copy
from decimal import Decimal
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from prove_native_budgets import ProofError, close_amount, expected_budget_message, protected_r, require

ROOT = Path(__file__).resolve().parent.parent.parent  # Saturates safely at /proof.
PRIVATE = Path('/proof-private')
STATE = PRIVATE / 'webui-state.private.json'
R_STATE = PRIVATE / 'responses-state.private.json'
HANDOFF = PRIVATE / 'responses-browser-accounts.private.json'
CONFIG = Path('/proof/config.yaml')
MODEL, WIRE, DEPLOYMENT = 'goal584-r', 'goal584-fake-r', 'goal584-deployment-r'
PROOF = 'goal584-native-responses-chat'
PROBE_ID = 'goal584_responses_id_probe'
PROBE_ACTION = 'goal584_responses_id'
MAX_BYTES = 4 * 1024 * 1024
SYSTEM = 'Synthetic Responses policy\nUse the exposed budget_echo Tool once, then answer Proof.'
REASONING = {'effort': 'low', 'summary': 'auto'}
LIMITS = ['one fresh R-only actor, one ordinary Send, two no-retry Responses dispatches',
          'stateless text/function profile only; no managed objects or paid provider',
          'known native plain saved-history reasoning loss is not repaired or accepted as continuity',
          'no concurrency, cancellation, recovery, production or full GOAL qualification']
CREDENTIAL = re.compile(r'(?:sk-|gw-)[A-Za-z0-9_-]{16,}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+')
PROBE_SOURCE = '''"""
title: GOAL584 bounded Responses ID observation
description: Disposable R-only hidden native status; no model/body transformation.
required_open_webui_version: 0.12.2
version: 0.1.0
"""
import json
import re
from uuid import UUID
from pydantic import BaseModel

def check(condition, code):
    if not condition:
        raise ValueError("Responses diagnostic boundary failed (" + code + ").")

class Filter:
    class Valves(BaseModel):
        priority: int = 1001
        actor_id: str = ""

    def __init__(self):
        self.valves = self.Valves()
        self.toggle = False

    async def stream(self, event, __user__=None, __metadata__=None, __request__=None,
                     __model__=None, __event_emitter__=None):
        if not isinstance(event, dict) or not str(event.get("type", "")).startswith("response."):
            return event
        response = event.get("response")
        if not isinstance(response, dict) or "id" not in response:
            return event
        actor = self.valves.actor_id
        check(str(UUID(actor)) == actor and isinstance(__user__, dict) and __user__.get("id") == actor, "actor")
        check(isinstance(__metadata__, dict) and __metadata__.get("user_id") == actor
              and isinstance(__model__, dict) and __model__.get("id") == "goal584-r", "server_context")
        chat, answer = __metadata__.get("chat_id"), __metadata__.get("message_id")
        check(str(UUID(chat)) == chat and str(UUID(answer)) == answer and callable(__event_emitter__), "native_ids")
        identifier = response["id"]
        check(isinstance(identifier, str) and identifier.startswith("resp_") and 5 < len(identifier) <= 1024
              and not any(c.isspace() for c in identifier)
              and re.search(r"(?:sk-|gw-)[A-Za-z0-9_-]{16,}|eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+", identifier) is None,
              "response_id")
        seen = __metadata__.setdefault("_goal584_responses_probe_ids", [])
        check(isinstance(seen, list) and len(seen) <= 8 and all(isinstance(v, str) for v in seen), "observation_bound")
        if identifier in seen:
            return event
        check(len(seen) < 8, "observation_bound")
        from open_webui.models.users import Users
        from open_webui.models.chats import Chats
        from employee_budget_webui_model_binding import native_connection
        user = await Users.get_user_by_id(actor)
        check(user is not None and user.role == "user", "native_user")
        owned = await Chats.get_accessible_chat_by_id(chat, user, permission="write")
        message = await Chats.get_message_by_id_and_message_id(chat, answer)
        check(owned is not None and owned.user_id == actor and isinstance(message, dict)
              and message.get("role") == "assistant" and message.get("model") == "goal584-r", "native_answer")
        secret, wire = await native_connection({"model": "goal584-r"}, __model__, __request__,
                                               "http://proxy:4000", require=check)
        check(wire == "goal584-r" and secret not in identifier, "known_secret")
        payload = {"schema": 1, "actor_id": actor, "chat_id": chat, "answer_id": answer, "response_id": identifier}
        await __event_emitter__({"type": "status", "data": {"action": "goal584_responses_id",
            "description": json.dumps(payload, separators=(",", ":")), "done": True, "hidden": True}})
        seen.append(identifier)
        return event
'''
R_BLOCK = '''  - model_name: goal584-r
    litellm_params:
      model: openai/goal584-fake-r
      api_base: http://provider:8000/v1
      api_key: synthetic-provider-only-not-a-credential
    model_info:
      id: goal584-deployment-r
      mode: responses
      supports_reasoning: true
      supports_function_calling: true
      max_tokens: 26
      max_input_tokens: 10
      max_output_tokens: 16
      input_cost_per_token: 0.01
      output_cost_per_token: 0.02

'''


def encoded(value):
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    require(len(raw) <= MAX_BYTES, 'Responses evidence exceeded byte bound')
    return raw


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def safe(value, secrets=()):
    raw = encoded(value).decode()
    require(CREDENTIAL.search(raw) is None and not any(s and s in raw for s in secrets),
            'Credential-bearing Responses evidence suppressed')
    return value


DENIAL_CAPTURE_ERRORS = frozenset({'provider_capture_read_failed', 'native_rows_read_failed',
    'native_user_read_failed', 'native_key_read_failed', 'provider_projection_failed',
    'rows_projection_failed', 'budget_projection_failed', 'raw_snapshot_exceeded_bound',
    'raw_snapshot_encoding_failed', 'private_snapshot_write_failed'})


def diagnostic_hash(value):
    """Hash the full private value even when it cannot fit the raw snapshot bound."""
    result = hashlib.sha256()
    for part in json.JSONEncoder(ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).iterencode(value):
        result.update(part.encode())
    return result.hexdigest()


def diagnostic_amount(value):
    require(type(value) in (int, float, str, Decimal), 'Responses diagnostic amount shape differs')
    number = Decimal(str(value))
    require(number.is_finite() and len(str(number)) <= 128, 'Responses diagnostic amount is not bounded finite money')
    return str(number)


def bound_private_snapshot(value):
    # Match existing write_private's JSON defaults and final text newline;
    # compact public evidence encoding would underestimate private file bytes.
    size = len(os.linesep.encode())
    for part in json.JSONEncoder(allow_nan=False).iterencode(value):
        size += len(part.encode())
        require(size <= MAX_BYTES, 'Responses private diagnostic snapshot exceeded byte bound')


def validate_denial_diagnostic(value):
    """Closed public worker schema: no raw native fields/errors/credentials."""
    names = {'schema', 'provider_snapshot_equal', 'provider_count', 'baseline_provider_count',
             'raw_row_count', 'raw_rows_sha256', 'rows', 'budgets', 'raw_snapshot_retained', 'capture_errors'}
    require(isinstance(value, dict) and set(value) == names and type(value['schema']) is int and value['schema'] == 1,
            'Responses denial diagnostic schema differs')
    require(value['provider_snapshot_equal'] is None or type(value['provider_snapshot_equal']) is bool,
            'Responses denial provider comparison shape differs')
    for name in ('provider_count', 'baseline_provider_count', 'raw_row_count'):
        require(value[name] is None or type(value[name]) is int and value[name] >= 0, 'Responses denial count shape differs')
    def hash_or_none(item):
        return item is None or isinstance(item, str) and re.fullmatch('[0-9a-f]{64}', item) is not None
    require(hash_or_none(value['raw_rows_sha256']) and type(value['raw_snapshot_retained']) is bool,
            'Responses denial hash/private marker differs')
    errors = value['capture_errors']
    require(isinstance(errors, list) and len(errors) == len(set(errors)) and all(e in DENIAL_CAPTURE_ERRORS for e in errors),
            'Responses denial capture error enum differs')
    rows = value['rows']
    require(rows is None or isinstance(rows, list) and len(rows) == value['raw_row_count'],
            'Responses denial row projection count differs')
    if rows is not None:
        for row in rows:
            require(isinstance(row, dict) and set(row) == {'request_id_sha256', 'status', 'spend_usd', 'usage',
                    'full_row_sha256', 'is_original_success_id', 'original_full_row_unchanged'}
                    and hash_or_none(row['request_id_sha256']) and row['request_id_sha256'] is not None
                    and hash_or_none(row['full_row_sha256']) and row['full_row_sha256'] is not None
                    and row['status'] in ('success', 'failure', 'other')
                    and isinstance(row['spend_usd'], str) and diagnostic_amount(row['spend_usd']) == row['spend_usd']
                    and type(row['is_original_success_id']) is bool and type(row['original_full_row_unchanged']) is bool,
                    'Responses denial row projection shape differs')
            usage = row['usage']
            require(isinstance(usage, dict) and set(usage) == {'prompt_tokens', 'completion_tokens', 'total_tokens'}
                    and all(type(n) is int and n >= 0 for n in usage.values()), 'Responses denial usage shape differs')
    budgets = value['budgets']
    if budgets is not None:
        require(isinstance(budgets, dict) and set(budgets) == {'user_spend_usd', 'key_spend_usd', 'user_cap_usd',
                'key_cap_usd', 'user_period', 'key_period', 'protected_fields_sha256', 'protected_fields_equal_except_key_cap'}
                and all(isinstance(budgets[k], str) and diagnostic_amount(budgets[k]) == budgets[k]
                        for k in ('user_spend_usd', 'key_spend_usd', 'user_cap_usd', 'key_cap_usd'))
                and hash_or_none(budgets['protected_fields_sha256']) and budgets['protected_fields_sha256'] is not None
                and type(budgets['protected_fields_equal_except_key_cap']) is bool,
                'Responses denial budget projection differs')
        from datetime import datetime
        for name in ('user_period', 'key_period'):
            period = budgets[name]
            require(isinstance(period, dict) and set(period) == {'duration', 'reset_at'}
                    and period['duration'] in ('1mo', 'other') and isinstance(period['reset_at'], str)
                    and len(period['reset_at']) <= 40, 'Responses denial budget period differs')
            stamp = datetime.fromisoformat(period['reset_at'])
            require(stamp.tzinfo is not None and stamp.isoformat() == period['reset_at'], 'Responses denial reset timestamp differs')
    safe(value)
    return value


def canonical(value):
    try:
        valid = isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        valid = False
    require(valid, 'Responses identity is not a canonical UUID')
    return value


def append_r(original):
    require(isinstance(original, bytes) and 0 < len(original) <= 128 * 1024, 'Responses YAML input exceeded bound')
    text = original.decode('utf-8')
    require(re.findall(r'(?m)^  - model_name: (\S+)\r?$', text) == ['goal584-a', 'goal584-b', 'goal584-e']
            and len(re.findall(r'(?m)^general_settings:\r?$', text)) == 1,
            'Responses requires the exact existing A/B/E configuration profile')
    at = re.search(r'(?m)^general_settings:\r?$', text).start()
    block = R_BLOCK.replace('\n', '\r\n') if '\r\n' in text else R_BLOCK
    return (text[:at] + block + text[at:]).encode('utf-8')


def validate_config(original, current):
    import yaml
    require(current == append_r(original), 'Responses YAML changed outside the one fixed R block')
    old, new = yaml.safe_load(original), yaml.safe_load(current)
    require(set(old) == set(new) and len(new['model_list']) == 4
            and new['model_list'][:3] == old['model_list']
            and all(new[k] == v for k, v in old.items() if k != 'model_list'),
            'Responses changed pre-existing native configuration semantics')
    require(old['general_settings'].get('custom_auth') == 'capture_webui_auth.gateway_auth'
            and old['general_settings'].get('custom_auth_run_common_checks') is True
            and old['general_settings'].get('fail_closed_budget_enforcement') is True
            and old['general_settings'].get('store_prompts_in_spend_logs') is False,
            'Responses requires unchanged native auth/enforcement/private logging')
    return {'original_sha256': hashlib.sha256(original).hexdigest(), 'active_sha256': hashlib.sha256(current).hexdigest()}


def connection_config(original, gateway):
    require(set(original) == {'ENABLE_OPENAI_API', 'OPENAI_API_BASE_URLS', 'OPENAI_API_KEYS', 'OPENAI_API_CONFIGS'}
            and original['ENABLE_OPENAI_API'] is True
            and original['OPENAI_API_BASE_URLS'] == ['http://proxy:4000/v1']
            and original['OPENAI_API_KEYS'] == [gateway]
            and set(original['OPENAI_API_CONFIGS']) == {'0'}, 'Responses requires the existing single native CC connection')
    prior = original['OPENAI_API_CONFIGS']['0']
    require(prior.get('enable') is True and prior.get('auth_type') == 'bearer'
            and prior.get('model_ids') == ['goal584-a', 'goal584-b']
            and prior.get('headers') == {'X-OpenWebUI-User-Id': '{{USER_ID}}', 'X-OpenWebUI-Task': '{{TASK}}'},
            'Responses native CC connection header/model contract differs')
    result = copy.deepcopy(original)
    result['OPENAI_API_BASE_URLS'].append('http://proxy:4000')
    result['OPENAI_API_KEYS'].append(gateway)
    result['OPENAI_API_CONFIGS']['1'] = {'enable': True, 'auth_type': 'bearer', 'api_type': 'responses',
        'model_ids': [MODEL], 'headers': copy.deepcopy(prior['headers'])}
    return result


def workspace_model(original, actor, filter_id, tool_id):
    result = copy.deepcopy(original)
    result.update(id=MODEL, name=MODEL, base_model_id=None, is_active=True,
        access_grants=[{'principal_type': 'user', 'principal_id': canonical(actor), 'permission': 'read'}])
    result['meta'].update(filterIds=[filter_id, PROBE_ID], toolIds=[tool_id])
    result['meta'].setdefault('capabilities', {})['builtin_tools'] = False
    result['params'] = dict(max_tokens=16, system=SYSTEM, function_calling='native', custom_params={
        'reasoning': REASONING, 'include': ['reasoning.encrypted_content'], 'store': False,
        'parallel_tool_calls': False, 'metadata': {'goal584_fixture': 'responses'}})
    return result


def controls_patch(original, current):
    """Existing control owner accepts null only for absent optional controls."""
    return {k: original.get(k) for k in set(original) | set(current) if original.get(k) != current.get(k)
            or (k in original) != (k in current)}


def unsigned_raw_body():
    return {'model': MODEL, 'input': 'Hi', 'max_output_tokens': 16, 'store': False, 'stream': False}


def missing_provenance_denied(status, body, capture):
    require(status == 403 and isinstance(body, dict), 'Unsigned Responses did not return the native missing-signature403')
    detail = body
    for _ in range(4):
        if not isinstance(detail, dict):
            break
        envelopes = [k for k in ('detail', 'error', 'message') if k in detail]
        require(len(envelopes) == 1, 'Unsigned Responses guard error envelope is ambiguous')
        detail = detail[envelopes[0]]
    require(detail == 'Signed budget provenance required', 'Unsigned Responses did not reach the exact missing-capsule guard')
    require(capture.get('route') in ('/responses', '/v1/responses', '/openai/v1/responses')
            and capture.get('body') == capture.get('body_after_auth') == unsigned_raw_body()
            and capture.get('attestation_present_before') is False and capture.get('provenance_removed_after') is True
            and capture.get('auth_failure') == {'scope': 'custom_auth', 'status_code': 403, 'code': 'unclassified'}
            and 'verified_cost_scope' not in capture and 'native_auth_user_id' not in capture,
            'Unsigned Responses capture is not the same missing-capsule native auth attempt')
    return {'http_status': 403, 'detail': detail, 'native_guard': 'signed_budget_provenance_required',
            'source_branch': 'shared_gateway_required_missing_capsule_empty_task',
            'capture_failure_code': 'unclassified', 'capture_route': capture['route'], 'request_body_sha256': digest(capture['body'])}


def worker_packet(result, phase, source, secrets=()):
    require(isinstance(result.stdout, bytes) and len(result.stdout) <= MAX_BYTES and len(result.stderr) <= MAX_BYTES,
            'Responses worker output bounds failed')
    try:
        value = json.loads(result.stdout)
    except (ValueError, UnicodeError):
        raise ProofError('Responses worker whole-stdout JSON protocol failed') from None
    safe(value, secrets)
    allowed = {'schema', 'proof', 'phase', 'passed', 'source_sha256', 'not_qualified', 'result', 'stage',
               'error_class', 'failed_stage', 'error_message', 'denial_diagnostic'}
    require(isinstance(value, dict) and not (set(value) - allowed)
            and type(value.get('schema')) is int and value['schema'] == 1
            and value.get('proof') == PROOF and value.get('phase') == phase and type(value.get('passed')) is bool
            and value.get('source_sha256') == source and value.get('not_qualified') == LIMITS,
            'Responses worker source/phase/protocol mismatch')
    require(isinstance(value.get('result'), dict) and isinstance(value.get('stage'), str) if value['passed']
            else isinstance(value.get('error_class'), str) or isinstance(value.get('result'), dict),
            'Responses worker terminal result/failure is missing')
    if 'denial_diagnostic' in value:
        require(phase in ('limit', 'denied'), 'Responses denial diagnostic belongs only to the negative phases')
        try:
            validate_denial_diagnostic(value['denial_diagnostic'])
        except Exception:
            raise ProofError('Responses denial diagnostic protocol failed') from None
    return value


class WorkerFailure(ProofError):
    def __init__(self, packet):
        self.packet = packet
        super().__init__('Responses worker phase failed')


def record_failure(receipt, error):
    receipt['passed'] = False
    if 'failure' in receipt:
        return
    receipt['failure'] = {'stage': receipt.get('stage', 'host_initialization'), 'error_class': type(error).__name__}
    if isinstance(error, WorkerFailure):
        receipt['failure']['worker'] = error.packet
    elif isinstance(error, ProofError):
        receipt['failure']['error_message'] = str(error)


def advertised_ids(answer, actor, chat_id, answer_id):
    history = answer.get('statusHistory')
    require(isinstance(history, list) and len(history) <= 128, 'Responses native status history is absent/unbounded')
    identifiers = []
    for entry in history:
        if entry.get('action') != PROBE_ACTION:
            continue
        require(entry.get('hidden') is True and entry.get('done') is True and isinstance(entry.get('description'), str)
                and len(entry['description']) <= 2048, 'Responses diagnostic status shape differs')
        value = json.loads(entry['description'])
        require(set(value) == {'schema', 'actor_id', 'chat_id', 'answer_id', 'response_id'}
                and type(value['schema']) is int and value['schema'] == 1 and value['actor_id'] == actor
                and value['chat_id'] == chat_id and value['answer_id'] == answer_id,
                'Responses diagnostic native actor/chat/answer binding differs')
        identifier = value['response_id']
        require(isinstance(identifier, str) and identifier.startswith('resp_') and 5 < len(identifier) <= 1024
                and not any(c.isspace() for c in identifier), 'Responses advertised native ID is malformed')
        safe(value)
        identifiers.append(identifier)
    require(len(identifiers) == len(set(identifiers)) == 2, 'Responses did not persist two distinct actual advertised IDs')
    require(history[-1].get('hidden') is not True and history[-1].get('action') == 'employee_budget_cost',
            'Responses diagnostic hid the final native visible cost widget')
    return identifiers


def verify_two_calls(provider_before, provider_after, context_before, context_after, *, actor, key_hash, chat_id, answer_id):
    require(provider_after['synthetic'] is True and provider_before['synthetic'] is True
            and provider_after['requests'][:len(provider_before['requests'])] == provider_before['requests']
            and len(provider_after['requests']) == len(provider_before['requests']) + 2
            and context_after['requests'][:len(context_before['requests'])] == context_before['requests']
            and len(context_after['requests']) == len(context_before['requests']) + 2,
            'Responses ordinary Send was not exactly two new physical/auth calls')
    physical, captures = provider_after['requests'][-2:], context_after['requests'][-2:]
    require(provider_before['control'] == provider_after['control'], 'Responses call changed provider controls')
    initial = [{'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'Hi'}]}]
    issued, observations = [], []
    for index, (p, c) in enumerate(zip(physical, captures)):
        body, after = c['body'], c['body_after_auth']
        require(body == after and c.get('route') in ('/responses', '/v1/responses', '/openai/v1/responses')
                and c.get('native_auth_user_id') == actor and c.get('native_auth_key_hash') == key_hash
                and c.get('attestation_present_before') is True and c.get('provenance_removed_after') is True
                and not c.get('auth_failure') and not c.get('responses_projection_rejected_after_auth'),
                'Responses full context/auth identity or JWT consumption changed')
        require(body.get('model') == MODEL and body.get('instructions') == SYSTEM and body.get('max_output_tokens') == 16
                and body.get('reasoning') == REASONING and body.get('include') == ['reasoning.encrypted_content']
                and body.get('store') is False and body.get('stream') is True
                and body.get('parallel_tool_calls') is False and not body.get('previous_response_id')
                and body.get('background', False) is False,
                'Responses instructions/reasoning/stateless/output profile differs from the approved model')
        tools = body.get('tools')
        require(isinstance(tools, list) and len(tools) == 1 and tools[0].get('type') == 'function'
                and tools[0].get('name', '').endswith('budget_echo') and tools[0].get('parameters', {}).get('properties') == {}
                and not tools[0]['parameters'].get('required'), 'Responses did not expose exactly the native zero-argument Tool')
        require(body['input'] == initial if index == 0 else body['input'][:1] == initial,
                'Responses native source message changed')
        require(p.get('route') == '/v1/responses' and p.get('id_kind') == 'provider_response'
                and p.get('body') == {**copy.deepcopy(after), 'model': WIRE}
                and p.get('response', {}).get('id') == p.get('id') and p['response'].get('model') == WIRE
                and p['response'].get('status') == 'completed' and p['response'].get('usage') == p.get('usage')
                and p.get('usage') == {'input_tokens': 10, 'output_tokens': 5, 'total_tokens': 15,
                    'input_tokens_details': {'cached_tokens': 0}, 'output_tokens_details': {'reasoning_tokens': 0}}
                and p.get('lifecycle', {}).get('terminal') is True and p['lifecycle'].get('outcome') == 'completed',
                'Responses complete provider wire input/usage/lifecycle differs from actual auth input')
        scope = c.get('verified_cost_scope')
        require(isinstance(scope, dict) and scope.get('category') == 'personal' and scope.get('user_id') == actor
                and scope.get('model') == MODEL and scope.get('chat_id') == scope.get('root_chat_id') == chat_id
                and scope.get('answer_id') == scope.get('root_answer_id') == answer_id,
                'Responses native signed lineage does not belong to the ordinary answer')
        issued.append(canonical(scope.get('call_id')))
        observations.append({'provider_response_id': p['id'], 'scope': scope, 'body': body, 'provider_body': p['body'],
                             'provider_output': p['response']['output'], 'usage': p['usage']})
    require(len(set(issued)) == 2 and len({p['id'] for p in physical}) == 2, 'Responses repeated physical/logical call identity')
    calls = [v for v in physical[0]['response']['output'] if v.get('type') == 'function_call']
    require(len(calls) == 1 and calls[0]['name'] == captures[0]['body']['tools'][0]['name']
            and calls[0]['arguments'] == '{}', 'Responses first physical output is not the approved Tool call')
    followup = captures[1]['body']['input'][1:]
    business = [v for v in followup if v.get('type') in ('function_call', 'function_call_output')]
    reasoning = [v for v in followup if v.get('type') == 'reasoning']
    require(len(business) + len(reasoning) == len(followup) and len(business) == 2 and business[0].get('type') == 'function_call'
            and all(business[0].get(k) == calls[0][k] for k in ('call_id', 'name', 'arguments'))
            and business[1] == {'type': 'function_call_output', 'call_id': calls[0]['call_id'], 'output': 'proof-tool-result'},
            'Responses follow-up lost or invented the actual native Tool result/pair')
    original_reasoning = [v for v in physical[0]['response']['output'] if v.get('type') == 'reasoning']
    require(original_reasoning, 'Responses synthetic first response omitted its declared reasoning profile')
    missing_reasoning = ['reasoning_items'] if not reasoning else []
    for field in ('summary', 'encrypted_content'):
        if any(v.get(field) for v in original_reasoning) and not any(v.get(field) for v in reasoning):
            missing_reasoning.append(field)
    final = [v for v in physical[1]['response']['output'] if v.get('type') == 'message']
    require(len(final) == 1 and final[0]['content'][0]['text'] == 'Proof', 'Responses final physical output differs')
    return {'calls': observations, 'issued_call_ids': issued,
            'reasoning_baseline': {'first_provider_summary_encrypted_present': True,
                                  'native_followup_reasoning_item_absent': not reasoning,
                                  'first_provider_reasoning_items_sha256': digest(original_reasoning),
                                  'actual_followup_reasoning_items_sha256': digest(reasoning),
                                  'normative_history_missing': missing_reasoning,
                                  'full_continuity_qualified': False},
            'context_scope': 'instructions_tools_parameters_and_native_to_provider_parity_only; reasoning continuity unqualified'}


def row_evidence(row, *, actor, key_hash, chat_id, answer_id, scope_by_provider, validate_scope, validate_rates, decode):
    metadata = json.loads(row['metadata']) if isinstance(row.get('metadata'), str) else row.get('metadata')
    require(isinstance(metadata, dict), 'Responses native row lacks metadata')
    spend = metadata.get('spend_logs_metadata') or {}
    scope = validate_scope(spend.get('owui_budget'))
    require(scope['user_id'] == actor and scope['model'] == MODEL
            and scope['chat_id'] == scope['root_chat_id'] == row.get('session_id') == chat_id
            and scope['answer_id'] == scope['root_answer_id'] == answer_id
            and row.get('api_key') == key_hash and row.get('user') == actor
            and row.get('status') == 'success' and row.get('model_group') == MODEL
            and row.get('model') in (MODEL, WIRE, 'openai/' + WIRE) and row.get('model_id') == DEPLOYMENT
            and close_amount(row.get('spend'), Decimal('.20'))
            and all(type(row.get(k)) is int for k in ('prompt_tokens', 'completion_tokens', 'total_tokens'))
            and [row[k] for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')] == [10, 5, 15],
            'Responses native row lost actual key/lineage/model/usage/cost')
    rates = validate_rates(spend.get('owui_billed_token_rates'))
    require(Decimal(str(rates['rates']['input_cost_per_token'])) == Decimal('.01')
            and Decimal(str(rates['rates']['output_cost_per_token'])) == Decimal('.02'), 'Responses native billed rates differ')
    decoded = decode(row['request_id'])
    require(isinstance(decoded, dict) and set(decoded) == {'custom_llm_provider', 'model_id', 'response_id'}
            and all(isinstance(v, str) and v for v in decoded.values()), 'Responses native SDK decoded-ID schema differs')
    require(decoded['custom_llm_provider'] == 'openai' and decoded['model_id'] == DEPLOYMENT
            and decoded['response_id'] in scope_by_provider,
            'Responses actual native SDK row ID does not decode to an observed provider response')
    require(scope == scope_by_provider[decoded['response_id']],
            'Responses native row signed call nonce does not match its actual decoded provider dispatch')
    return {'native_request_id': row['request_id'], 'provider_response_id': decoded['response_id'],
        'native_litellm_call_id': metadata.get('litellm_call_id'), 'scope': scope,
        'usage': {k: row[k] for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')},
        'spend_usd': str(row['spend']), 'billed_rates': rates, 'full_row_sha256': digest(row)}


def native_zero_audit(rows, original, *, actor, key_hash):
    """One controlled direct-vkey422 bracket, never a general zero-row exemption."""
    require(isinstance(rows, list) and 2 <= len(rows) <= 3 and len(original) == 2,
            'Responses native zero bracket has unexpected raw row count')
    def by_id(values):
        require(all(isinstance(row, dict) and isinstance(row.get('request_id'), str)
                    and 0 < len(row['request_id']) <= 4096 for row in values), 'Responses audit row identity is missing')
        result = {row['request_id']: row for row in values}
        require(len(result) == len(values), 'Responses native zero bracket duplicated a row ID')
        return result
    old, current = by_id(original), by_id(rows)
    require(old.keys() <= current.keys() and all(diagnostic_hash(current[key]) == diagnostic_hash(value)
            for key, value in old.items()), 'Responses native zero bracket changed an original positive row')
    added = [row for key, row in current.items() if key not in old]
    if not added:
        return None
    require(len(added) == 1, 'Responses native zero bracket has ambiguous new raw rows')
    row = added[0]
    require(row.get('user') == actor and row.get('api_key') == key_hash,
            'Responses native audit does not belong to the isolated R user/key')
    require(row.get('model_group') == MODEL and row.get('model_id') == DEPLOYMENT
            and row.get('model') == 'openai/' + WIRE and row.get('custom_llm_provider') == 'openai'
            and row.get('call_type') == 'aresponses', 'Responses native audit R attribution differs')
    require(row.get('status') == 'failure' and Decimal(diagnostic_amount(row.get('spend'))) == 0
            and all(type(row.get(k)) is int and row[k] == 0 for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')),
            'Responses native audit is not an exact zero-cost zero-usage failure')
    try:
        metadata = json.loads(row['metadata']) if isinstance(row.get('metadata'), str) else row.get('metadata')
    except ValueError:
        raise ProofError('Responses native audit metadata is malformed') from None
    require(isinstance(metadata, dict) and isinstance(metadata.get('error_information'), dict),
            'Responses native audit has no native error information')
    error = metadata['error_information']
    require(error.get('error_class') == 'BudgetExceededError' and error.get('error_code') == '422',
            'Responses native audit is not the exact native budget422 class')
    spend_metadata = metadata.get('spend_logs_metadata')
    require(spend_metadata is None or isinstance(spend_metadata, dict)
            and all(name not in spend_metadata for name in ('owui_budget', 'owui_budget_provenance', 'owui_budget_root')),
            'Direct native audit unexpectedly acquired a claimed signed scope')
    expected = {'error_budget_entity_type': 'key', 'error_budget_entity_id': key_hash,
                'error_budget_limit': Decimal(0), 'error_budget_spend': Decimal('.40')}
    verified = []
    for name, value in expected.items():
        if error.get(name) is not None:
            matches = (close_amount(error[name], value) if name == 'error_budget_spend' else
                       Decimal(diagnostic_amount(error[name])) == value if isinstance(value, Decimal) else error[name] == value)
            require(matches, 'Responses native audit budget-owner information conflicts')
            verified.append(name)
    return {'classification': 'one_controlled_direct_native_key_budget422',
        'request_id_sha256': hashlib.sha256(row['request_id'].encode()).hexdigest(), 'full_row_sha256': diagnostic_hash(row),
        'own_r_user_and_key': True, 'native_r_model_binding': True, 'native_budget_error_class': 'BudgetExceededError',
        'native_error_code': '422', 'status': 'failure', 'spend_usd': diagnostic_amount(row['spend']),
        'usage': {k: row[k] for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')},
        'native_call_type': 'aresponses', 'verified_native_budget_fields': verified,
        'original_positive_rows_unchanged': True, 'native_audit_row_count': 1,
        'lineage': 'causal_before_after_single_native_http_attempt_not_provider_response_id'}


def worker_dependencies():
    from provision_webui import WebUI, native_client, read_private, write_private, account_from_response, TASK_FLAGS, WEBUI_URL
    from employee_budget_assignment import assignment_alias, assignment_metadata, assignment_matches
    from provision_cost_display import FILTER_ID, TOOL_ID, TOOL_SOURCE, model_body, grant_set, source_hash
    from prove_service_tasks import provider, response
    from prove_pricing_snapshots import private_credentials, validate_snapshot
    from provenance import validate_persisted_scope
    from litellm.responses.utils import ResponsesAPIRequestUtils
    import capture_webui_auth as capture
    return locals()


class Worker:
    def __init__(self):
        self.d = worker_dependencies()
        self.main = self.d['read_private'](STATE)
        self.webui, self.native = self.d['WebUI'](), self.d['native_client'](self.main)
        self.r = self.d['read_private'](R_STATE) if R_STATE.exists() else {'schema': 1}
        self.admin = self.main['admin']['token']
        self.secrets = self.d['private_credentials'](self.main) + [self.native.master_key, os.environ.get('OWUI_BUDGET_GATEWAY_SECRET', '')]
        self.secrets += self.d['private_credentials'](self.r)

    def stage(self, name):
        self.r['stage'] = name
        self.d['write_private'](R_STATE, self.r)

    def captures(self):
        with self.d['capture'].capture_lock():
            c = self.d['capture']._read_locked()
        return self.d['provider'](), c

    def protected_main(self):
        people = [*[u['id'] for u in self.main['users']], self.main['admin']['id'],
                  self.main['bootstrap_fixture']['employee']['id'], self.main['service_fixture']['payer_id']]
        require(len(set(people)) == 5, 'Responses requires the existing five distinct A/B/E payers')
        result = []
        for uid in sorted(people):
            user, rows = self.native.user_info(uid), self.native.logs(uid)
            require(close_amount(user['spend'], sum((Decimal(str(v['spend'])) for v in rows), Decimal(0))),
                    'Responses prior payer accounting is unsettled')
            result.append({'user_id': uid, 'user': user, 'rows': sorted(rows, key=lambda v: v['request_id'])})
        return result

    def key(self):
        return self.native.ok('GET', '/key/info', query={'key': self.r['key_hash']})['info']

    def setup(self):
        require(self.r == {'schema': 1} and self.main.get('stage') == 'setup_complete', 'Responses requires fresh separate private state')
        self.native.schema()
        require(self.webui.ok('GET', '/api/version').get('version') == '0.12.2', 'Responses requires exact native WebUI 0.12.2')
        rag = self.d['read_private'](PRIVATE / 'rag-state.private.json')
        require(rag.get('stage') == 'qualified_native_rag_http_text_query'
                and rag.get('config', {}).get('active_sha256') == hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
                'Responses requires the exact completed prior RAG A/B/E configuration')
        self.r.update(original_finance=self.protected_main(),
            original_openai=self.webui.ok('GET', '/openai/config', token=self.admin),
            original_tasks=self.webui.ok('GET', '/api/v1/tasks/config', token=self.admin),
            original_tool=self.webui.ok('GET', '/api/v1/tools/id/' + self.d['TOOL_ID'], token=self.admin),
            original_model_a=self.webui.model(self.admin, 'goal584-a'))
        self.r['original_models'] = {m: self.d['model_body'](self.webui.model(self.admin, m)) for m in ('goal584-a', 'goal584-b')}
        require(all(self.r['original_tasks'].get(k) is False for k in self.d['TASK_FLAGS']), 'Responses auxiliary tasks must remain disabled')
        require(self.r['original_tool']['content'] == self.d['TOOL_SOURCE'], 'Responses native Tool source differs')
        specs = self.r['original_tool'].get('specs')
        require(isinstance(specs, list) and len(specs) == 1 and specs[0].get('name') == 'budget_echo'
                and specs[0].get('parameters', {}).get('properties') == {} and not specs[0]['parameters'].get('required'),
                'Responses existing native public Tool schema is not the zero-argument method')
        source = self.webui.ok('GET', '/api/v1/functions/id/' + self.d['FILTER_ID'], token=self.admin)
        mounted = Path('/proof/budgets/cost_filter.py').read_text(encoding='utf-8')
        require(self.d['source_hash'](source['content']) == self.d['source_hash'](mounted), 'Responses installed signing Filter differs from mounted product source')
        self.r['filter_source_sha256'] = self.d['source_hash'](mounted)
        p, c = self.captures()
        require(p.get('synthetic') is True and all(v.get('lifecycle', {}).get('terminal') is True for v in p['requests'])
                and p['control'].get('delay_ms') == 0 and p['control'].get('response_status', 200) == 200
                and p['control'].get('after_first_chunk_delay_ms', 0) == 0
                and len(c['requests']) + 5 <= self.d['capture'].MAX_RECORDS, 'Responses requires bounded quiescent provider/context history')
        self.r.update(provider_original=p, context_original=c, original_controls=copy.deepcopy(p['control']))
        self.stage('creating_r_actor')
        import secrets
        email, password = 'responses-' + uuid4().hex[:12] + '@example.com', 'Aa1!' + secrets.token_urlsafe(32)
        created = self.webui.ok('POST', '/api/v1/auths/add', token=self.admin,
            body={'name': 'GOAL584 isolated Responses user', 'email': email, 'password': password, 'role': 'user'})
        self.r['actor'] = self.d['account_from_response'](created, email, password, 'user')
        self.secrets.extend([password, self.r['actor']['token']]); self.stage('r_actor_created')
        uid = canonical(self.r['actor']['id'])
        self.webui.session(self.r['actor'], 'user')
        self.d['write_private'](HANDOFF, {'schema': 1, 'users': [{k: self.r['actor'][k] for k in ('id', 'email', 'password')}]})
        require(os.name == 'posix' and HANDOFF.stat().st_uid == 0 and stat.S_IMODE(HANDOFF.stat().st_mode) == 0o600,
                'Responses private browser handoff must remain container-root-owned0600')
        self.stage('prepared')
        return {'actor_id': uid, 'old_payers': [{'user_id': v['user_id'],
                'user_sha256': digest(v['user']), 'rows': [{'request_id': row['request_id'], 'full_row_sha256': digest(row)} for row in v['rows']]}
                for v in self.r['original_finance']], 'filter_source_sha256': self.r['filter_source_sha256'],
                'native_tool_source_sha256': self.d['source_hash'](self.r['original_tool']['content']), 'native_tool_specs_sha256': digest(specs)}

    def provision_native(self):
        uid = self.r['actor']['id']
        self.stage('creating_r_native_user')
        self.native.ok('POST', '/user/new', body={'user_id': uid, 'user_role': 'internal_user', 'models': [MODEL],
            'max_budget': 20, 'budget_duration': '1mo', 'auto_create_key': False, 'send_invite_email': False})
        self.stage('creating_r_native_key')
        generated = self.native.ok('POST', '/key/generate', body={'user_id': uid, 'models': [MODEL],
            'key_alias': self.d['assignment_alias'](uid, MODEL), 'metadata': self.d['assignment_metadata'](MODEL),
            'max_budget': 20, 'budget_duration': '1mo', 'blocked': False, 'allowed_routes': ['llm_api_routes'],
            'team_id': None, 'budget_id': None, 'send_invite_email': False})
        key = generated.get('key')
        require(isinstance(key, str) and key.startswith('sk-'), 'Responses native key generation failed')
        self.r.update(key=key, key_hash=hashlib.sha256(key.encode()).hexdigest()); self.secrets.append(key)
        self.stage('r_native_readback')
        user, info = self.native.user_info(uid), self.key()
        from types import SimpleNamespace
        require(user['models'] == [MODEL] and user['user_role'] == 'internal_user'
                and user['budget_duration'] == info['budget_duration'] == '1mo'
                and Decimal(str(user['max_budget'])) == Decimal(str(info['max_budget'])) == 20
                and Decimal(str(user['spend'])) == Decimal(str(info['spend'])) == 0
                and len(user['keys']) == 1 and self.d['assignment_matches'](SimpleNamespace(**info), uid, MODEL),
                'Responses isolated native user/key/100-percent monthly assignment differs')
        self.r['protected_r'] = protected_r(user, info)

    def configure(self):
        require(self.r['stage'] == 'prepared', 'Responses configure requires prepared state')
        require(self.protected_main() == self.r['original_finance'], 'Responses preparation changed old payers')
        original = Path('/proof-private/responses-config-original.private.yaml').read_bytes()
        config = validate_config(original, CONFIG.read_bytes())
        self.provision_native()  # Router now owns the appended R model.
        gateway = os.environ.get('OWUI_BUDGET_GATEWAY_SECRET')
        require(isinstance(gateway, str) and gateway, 'Responses existing gateway owner is unavailable')
        target = connection_config(self.r['original_openai'], gateway)
        self.stage('configuring_native_r_connection')
        self.webui.ok('POST', '/openai/config/update', token=self.admin, body=target)
        require(self.webui.ok('GET', '/openai/config', token=self.admin) == target, 'Responses connection readback differs')
        self.stage('granting_existing_tool_read')
        grants = copy.deepcopy(self.r['original_tool']['access_grants'])
        grants.append({'principal_type': 'user', 'principal_id': self.r['actor']['id'], 'permission': 'read'})
        self.webui.ok('POST', '/api/v1/tools/id/' + self.d['TOOL_ID'] + '/access/update', token=self.admin,
            body={'access_grants': grants})
        observed_tool = self.webui.ok('GET', '/api/v1/tools/id/' + self.d['TOOL_ID'], token=self.admin)
        require(self.d['grant_set'](observed_tool) == self.d['grant_set']({'access_grants': grants})
                and observed_tool['content'] == self.r['original_tool']['content'], 'Responses changed Tool source or old grants')
        visible = self.webui.ok('GET', '/api/v1/tools/id/' + self.d['TOOL_ID'], token=self.r['actor']['token'])
        require(visible.get('id') == self.d['TOOL_ID'] and visible.get('write_access') is False and visible.get('content') is None,
                'Responses ordinary actor Tool access is not native read-only')
        self.stage('creating_native_r_workspace_model')
        created_probe = self.webui.ok('POST', '/api/v1/functions/create', token=self.admin,
            body={'id': PROBE_ID, 'name': 'Responses bounded ID probe', 'content': PROBE_SOURCE, 'meta': {}})
        require(created_probe.get('id') == PROBE_ID and created_probe.get('type') == 'filter'
                and created_probe.get('is_active') is False, 'Responses diagnostic Function creation differs')
        self.r['probe_created'] = True; self.stage('configuring_r_only_id_probe')
        self.webui.ok('POST', '/api/v1/functions/id/' + PROBE_ID + '/valves/update', token=self.admin,
            body={'priority': 1001, 'actor_id': self.r['actor']['id']})
        self.webui.ok('POST', '/api/v1/functions/id/' + PROBE_ID + '/toggle', token=self.admin)
        probe = self.webui.ok('GET', '/api/v1/functions/id/' + PROBE_ID, token=self.admin)
        require(probe.get('is_active') is True and probe.get('is_global') is False
                and self.d['source_hash'](probe['content']) == self.d['source_hash'](PROBE_SOURCE), 'Responses probe source/global binding differs')
        model = workspace_model(self.d['model_body'](self.r['original_model_a']), self.r['actor']['id'],
            self.d['FILTER_ID'], self.d['TOOL_ID'])
        self.webui.ok('POST', '/api/v1/models/create', token=self.admin, body=model)
        actual = self.webui.model(self.admin, MODEL)
        require(all(actual.get(k) == v for k, v in model.items() if k != 'access_grants')
                and self.d['grant_set'](actual) == {('user', self.r['actor']['id'], 'read')}, 'Responses Workspace Model readback differs')
        account = self.r['actor']
        catalog = self.webui.ok('GET', '/api/models?refresh=true', token=account['token']).get('data')
        require(isinstance(catalog, list) and len(catalog) == 1 and catalog[0]['id'] == MODEL
                and str(catalog[0].get('urlIdx')) == '1', 'Responses ordinary catalog is not isolated to native R connection')
        self.webui.ok('POST', '/api/v1/functions/id/' + self.d['FILTER_ID'] + '/valves/user/update', token=account['token'], body={})
        p, c = self.captures()
        if p['control'].get('tool_round') is not True:
            self.d['provider']('POST', '/__proof/control', {'tool_round': True})
        p, c = self.captures()
        require(p['control'] == {**self.r['original_controls'], 'tool_round': True}
                and p['requests'] == self.r['provider_original']['requests'] and c == self.r['context_original'],
                'Responses setup changed controls/history outside tool_round')
        self.r.update(provider_before=p, context_before=c, config=config, target_openai_sha256=digest(target))
        self.stage('ready_for_one_ordinary_send')
        return {'actor_id': account['id'], 'key_hash': self.r['key_hash'], 'config': config,
                'openai_config_sha256': digest(target), 'native_r_model_sha256': digest(model), 'connection_index': 1}

    def observe(self, chat_id, answer_id):
        canonical(chat_id); canonical(answer_id)
        self.stage('observing_two_native_r_calls')
        uid = self.r['actor']['id']
        p, c = self.captures()
        evidence = verify_two_calls(self.r['provider_before'], p, self.r['context_before'], c,
            actor=uid, key_hash=self.r['key_hash'], chat_id=chat_id, answer_id=answer_id)
        require(self.protected_main() == self.r['original_finance'], 'Responses changed old A/B/E payer/key/history state')
        require({m: self.d['model_body'](self.webui.model(self.admin, m)) for m in self.r['original_models']} == self.r['original_models'],
                'Responses changed old native Workspace models')
        issued = set(evidence['issued_call_ids'])
        def settled():
            rows = self.native.logs(uid)
            require(len(rows) <= 2, 'Responses produced extra native financial rows')
            if len(rows) != 2:
                return None
            projected = []
            for row in rows:
                projected.append(row_evidence(row, actor=uid, key_hash=self.r['key_hash'], chat_id=chat_id,
                    answer_id=answer_id, scope_by_provider={v['provider_response_id']: v['scope'] for v in evidence['calls']},
                    validate_scope=self.d['validate_persisted_scope'], validate_rates=self.d['validate_snapshot'],
                    decode=self.d['ResponsesAPIRequestUtils']._decode_responses_api_response_id))
            require({v['scope']['call_id'] for v in projected} == issued and len({v['native_request_id'] for v in projected}) == 2
                    and len({v['provider_response_id'] for v in projected}) == 2, 'Responses native logical/physical coverage differs')
            user, key = self.native.user_info(uid), self.key()
            require(protected_r(user, key) == self.r['protected_r'], 'Responses native protected identity/caps/reset fields changed')
            if not (close_amount(user['spend'], Decimal('.40')) and close_amount(key['spend'], Decimal('.40'))):
                return None
            return projected, rows, user, key
        projected, rows, actual_user, actual_key = self.native.poll('two actual Responses ledger rows and counters', settled)
        saved = self.webui.ok('GET', '/api/v1/chats/' + chat_id, token=self.r['actor']['token'])
        require(saved.get('user_id') == uid, 'Responses persisted chat belongs to another actor')
        answer = saved['chat']['history']['messages'][answer_id]
        require(answer.get('done') is True and answer.get('content') == 'Proof' and not answer.get('error'), 'Responses native terminal answer differs')
        actual_advertised = advertised_ids(answer, uid, chat_id, answer_id)
        require(set(actual_advertised).isdisjoint(v['native_request_id'] for v in projected)
                and set(actual_advertised).isdisjoint(v['provider_response_id'] for v in projected),
                'Responses expected selected encrypted advertised IDs to remain distinct from raw/SDK row IDs')
        require(self.webui.ok('GET', '/api/v1/tasks/config', token=self.admin) == self.r['original_tasks'], 'Responses changed native auxiliary tasks')
        self.r.update(chat_id=chat_id, answer_id=answer_id, success_rows=rows, success_provider=p,
                      success_context=c, native_evidence=projected)
        self.stage('two_native_calls_observed')
        return {**evidence, 'native_rows': projected, 'actor_id': uid, 'key_hash': self.r['key_hash'],
            'native_user_spend_usd': str(actual_user['spend']), 'native_key_spend_usd': str(actual_key['spend']),
            'native_protected_fields': protected_r(actual_user, actual_key), 'old_five_payers_unchanged': True,
            'actual_advertised_response_ids': actual_advertised, 'probe_source_sha256': self.d['source_hash'](PROBE_SOURCE)}

    def limit(self):
        require(self.r['stage'] == 'two_native_calls_observed', 'Responses zero cap requires completed positive readback')
        self.stage('unsigned_raw_negative')
        p, c = self.captures()
        self.webui.session(self.r['actor'], 'user')
        status, body = self.d['response'](self.webui, 'POST', '/openai/responses', self.r['actor']['token'],
            unsigned_raw_body())
        actual_provider, actual_context = self.captures()
        require(actual_provider == p and actual_context['requests'][:-1] == c['requests']
                and len(actual_context['requests']) == len(c['requests']) + 1
                and self.native.logs(self.r['actor']['id']) == self.r['success_rows'],
                'Unsigned Responses reached provider or changed ledger')
        unsigned = missing_provenance_denied(status, body, actual_context['requests'][-1])
        self.r['unsigned_http'] = {'status': status, 'body': body}
        self.stage('zeroing_r_key_cap')
        self.r['restore_cap'] = True; self.stage('zeroing_r_key_cap')
        self.native.ok('POST', '/key/update', body={'key': self.r['key_hash'], 'max_budget': 0})
        info = self.key()
        expected = copy.deepcopy(self.r['protected_r']); expected['key']['max_budget'] = info['max_budget']
        require(Decimal(str(info['max_budget'])) == 0 and protected_r(self.native.user_info(self.r['actor']['id']), info) == expected,
                'Responses hard-zero changed fields outside the R key cap')
        self.stage('native_r_zero_witness')
        status, error, _ = self.native.request('POST', '/v1/responses', token=self.r['key'],
            body={'model': MODEL, 'input': 'Hi', 'max_output_tokens': 16, 'store': False, 'stream': False})
        require(status == 422 and error.get('error', {}).get('type') == 'budget_exceeded', 'Responses native hard-zero did not produce exact422')
        expected_budget_message(error, scope='key')
        require(self.captures()[0] == p, 'Responses zero native witness reached provider')
        self.r['denial_provider_baseline'] = p
        self.stage('settling_one_direct_native_zero_audit')
        require(type(self.native.timeout) in (int, float) and 0 < self.native.timeout <= 60,
                'Responses native audit read budget must be at most60 seconds')
        deadline = time.monotonic() + self.native.timeout
        def settled_audit():
            require(time.monotonic() <= deadline, 'Responses native audit observation exceeded its read deadline')
            raw = self.denial_snapshot()
            if raw['provider'] is not None:
                require(raw['provider'] == p, 'Responses direct native zero audit reached or changed provider')
            evidence = (native_zero_audit(raw['rows'], self.r['success_rows'], actor=self.r['actor']['id'], key_hash=self.r['key_hash'])
                        if raw['rows'] is not None else None)
            require(not self.denial_diagnostic['capture_errors'] and all(raw[k] is not None for k in raw),
                    'Responses native audit observation is unavailable or could not be retained safely')
            user, key = raw['user'], raw['key']
            require(protected_r(user, key) == expected and Decimal(str(key['max_budget'])) == 0
                    and close_amount(user['spend'], Decimal('.40')) and close_amount(key['spend'], Decimal('.40')),
                    'Responses native audit changed R budget identity/cap/period/spend')
            require(time.monotonic() <= deadline, 'Responses native audit observation exceeded its read deadline')
            return (raw['rows'], evidence) if evidence is not None else None
        rows, audit = self.native.poll('one isolated direct native budget422 audit row', settled_audit)
        self.r.update(post_native_zero_rows=rows, native_audit_evidence=audit,
            native_audit_row=next(row for row in rows if hashlib.sha256(row['request_id'].encode()).hexdigest() == audit['request_id_sha256']))
        bound_private_snapshot({**self.r, 'stage': 'ready_for_ordinary_zero_denial'})
        self.stage('ready_for_ordinary_zero_denial')
        return {'unsigned_raw': unsigned, 'native_zero_status': status, 'native_zero_type': 'budget_exceeded', 'native_audit': audit}

    def denial_snapshot(self):
        """Observe once before assertions; technical failures never replace a known financial violation."""
        uid = self.r['actor']['id']
        raw = {'provider': None, 'capture': None, 'rows': None, 'user': None, 'key': None}
        diagnostic = {'schema': 1, 'provider_snapshot_equal': None, 'provider_count': None,
            'baseline_provider_count': None, 'raw_row_count': None, 'raw_rows_sha256': None,
            'rows': None, 'budgets': None, 'raw_snapshot_retained': False, 'capture_errors': []}
        self.denial_diagnostic = diagnostic
        def failed(code):
            if code not in diagnostic['capture_errors']:
                diagnostic['capture_errors'].append(code)
        try:
            raw['provider'], raw['capture'] = self.captures()
        except Exception:
            failed('provider_capture_read_failed')
        for name, call in (('rows', lambda: self.native.logs(uid)), ('user', lambda: self.native.user_info(uid)), ('key', self.key)):
            try:
                raw[name] = call()
            except Exception:
                failed('native_' + name + '_read_failed')
        try:
            baseline = self.r['denial_provider_baseline']
            diagnostic['baseline_provider_count'] = len(baseline['requests'])
            if raw['provider'] is not None:
                require(isinstance(raw['provider']['requests'], list), 'Responses provider history shape differs')
                diagnostic['provider_count'] = len(raw['provider']['requests'])
                diagnostic['provider_snapshot_equal'] = raw['provider'] == baseline
        except Exception:
            failed('provider_projection_failed')
        try:
            rows = raw['rows']
            if rows is not None:
                require(isinstance(rows, list), 'Responses raw journal shape differs')
                diagnostic['raw_row_count'] = len(rows)
                diagnostic['raw_rows_sha256'] = diagnostic_hash(rows)
                original = {row['request_id']: row for row in self.r['success_rows']}
                diagnostic['rows'] = [{'request_id_sha256': hashlib.sha256(row['request_id'].encode()).hexdigest(),
                    'status': row.get('status') if row.get('status') in ('success', 'failure') else 'other',
                    'spend_usd': diagnostic_amount(row['spend']),
                    'usage': {k: row[k] for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')},
                    'full_row_sha256': diagnostic_hash(row), 'is_original_success_id': row['request_id'] in original,
                    'original_full_row_unchanged': row['request_id'] in original and diagnostic_hash(row) == diagnostic_hash(original[row['request_id']])}
                    for row in rows]
                validate_denial_diagnostic(diagnostic)
        except Exception:
            diagnostic['rows'] = None
            failed('rows_projection_failed')
        try:
            if raw['user'] is not None and raw['key'] is not None:
                from datetime import datetime
                user, key = raw['user'], raw['key']
                require(user['user_id'] == key['user_id'] == uid, 'Responses diagnostic native budget owner differs')
                protected = protected_r(user, key)
                expected = copy.deepcopy(self.r['protected_r']); expected['key']['max_budget'] = key['max_budget']
                periods = {}
                for name, value in (('user_period', user), ('key_period', key)):
                    stamp = datetime.fromisoformat(value['budget_reset_at'].replace('Z', '+00:00'))
                    require(stamp.tzinfo is not None, 'Responses diagnostic native period has no timezone')
                    periods[name] = {'duration': '1mo' if value['budget_duration'] == '1mo' else 'other', 'reset_at': stamp.isoformat()}
                diagnostic['budgets'] = {**periods, 'user_spend_usd': diagnostic_amount(user['spend']),
                    'key_spend_usd': diagnostic_amount(key['spend']), 'user_cap_usd': diagnostic_amount(user['max_budget']),
                    'key_cap_usd': diagnostic_amount(key['max_budget']), 'protected_fields_sha256': diagnostic_hash(protected),
                    'protected_fields_equal_except_key_cap': protected == expected}
                validate_denial_diagnostic(diagnostic)
        except Exception:
            diagnostic['budgets'] = None
            failed('budget_projection_failed')
        if diagnostic['budgets'] is None and not any(e in diagnostic['capture_errors'] for e in
                ('native_user_read_failed', 'native_key_read_failed', 'budget_projection_failed')):
            failed('budget_projection_failed')
        # Bound the complete existing state, not only this raw addition. Oversize
        # retains hashes/counts but never exports or writes the oversized raw data.
        candidate = {**self.r, 'denial_observation': raw, 'denial_diagnostic': diagnostic}
        try:
            bound_private_snapshot(candidate)
        except Exception as error:
            failed('raw_snapshot_exceeded_bound' if isinstance(error, ProofError) else 'raw_snapshot_encoding_failed')
            candidate = {**self.r, 'denial_diagnostic': diagnostic}
        else:
            diagnostic['raw_snapshot_retained'] = True
        try:
            bound_private_snapshot(candidate)
            self.d['write_private'](R_STATE, candidate)
            self.r = candidate
        except Exception:
            diagnostic['raw_snapshot_retained'] = False
            failed('private_snapshot_write_failed')
        return raw

    def denied(self, chat_id, answer_id):
        account = self.r['actor']
        raw = self.denial_snapshot()
        p, c, rows = raw['provider'], raw['capture'], raw['rows']
        if p is not None:
            require(p == self.r['denial_provider_baseline'], 'Responses negatives changed the full provider snapshot')
        if rows is not None:
            require(diagnostic_hash(rows) == diagnostic_hash(self.r['post_native_zero_rows']),
                    'Responses ordinary zero changed the bracketed native raw journal')
        require(p is not None and c is not None and rows is not None and not self.denial_diagnostic['capture_errors'],
                'Responses denial observation is unavailable or could not be retained safely')
        audit = native_zero_audit(rows, self.r['success_rows'], actor=account['id'], key_hash=self.r['key_hash'])
        require(audit == self.r['native_audit_evidence'], 'Responses ordinary zero changed its classified direct native audit')
        saved = self.webui.ok('GET', '/api/v1/chats/' + canonical(chat_id), token=account['token'])
        answer = saved['chat']['history']['messages'][canonical(answer_id)]
        require(saved['user_id'] == account['id'] and answer.get('done') is True and answer.get('content') != 'Proof',
                'Responses ordinary zero outcome is not a terminal owned denial')
        expected_budget_message(answer.get('error'), scope='key')
        require(len(c['requests']) == len(self.r['context_before']['requests']) + 5,
                'Responses signed/raw/native denial auth cardinality differs')
        negatives = c['requests'][-3:]
        missing_provenance_denied(self.r['unsigned_http']['status'], self.r['unsigned_http']['body'], negatives[0])
        require([v.get('auth_failure', {}).get('status_code') for v in negatives] == [403, 422, 422]
                and negatives[-1].get('attestation_present_before') is True
                and negatives[-1].get('provenance_removed_after') is True
                and negatives[-1]['body'] == negatives[-1]['body_after_auth'] == self.r['success_context']['requests'][-2]['body'],
                'Responses ordinary denial did not reach the exact signed R input/native guard')
        self.native.ok('POST', '/key/update', body={'key': self.r['key_hash'], 'max_budget': 20})
        user, key = self.native.user_info(account['id']), self.key()
        require(protected_r(user, key) == self.r['protected_r']
                and close_amount(user['spend'], Decimal('.40')) and close_amount(key['spend'], Decimal('.40')),
                'Responses cap restoration changed R identity/period/caps')
        self.r['restore_cap'] = False
        require(self.protected_main() == self.r['original_finance'], 'Responses denial changed old payer state')
        current = self.d['provider']()['control']
        patch = controls_patch(self.r['original_controls'], current)
        if patch:
            self.d['provider']('POST', '/__proof/control', patch)
        require(self.d['provider']()['control'] == self.r['original_controls'], 'Responses controls restoration differs')
        self.stage('qualified_native_responses_financial_profile')
        return {'original_positive_rows_unchanged': True, 'native_audit_row_count': 1, 'native_audit_row_unchanged': True,
                'provider_dispatches_unchanged': True, 'cap_restored': True,
                'controls_restored': True, 'success_state_lifetime': 'until existing disposable stand teardown',
                'advertised_id_observation': 'native_hidden_status_during_actual_stream', 'full_GOAL_acceptance': False}

    def restore(self):
        outcomes = {}
        operations = []
        if self.r.get('key_hash'):
            def cap():
                self.native.ok('POST', '/key/update', body={'key': self.r['key_hash'], 'max_budget': 20})
                key = self.key()
                require(Decimal(str(key['max_budget'])) == 20, 'Responses R cap rollback readback differs')
                if self.r.get('protected_r'):
                    require(protected_r(self.native.user_info(self.r['actor']['id']), key) == self.r['protected_r'],
                            'Responses R protected identity changed during rollback')
            operations.append(('r_cap', cap))
        if self.r.get('original_openai'):
            def openai():
                self.webui.ok('POST', '/openai/config/update', token=self.admin, body=self.r['original_openai'])
                require(self.webui.ok('GET', '/openai/config', token=self.admin) == self.r['original_openai'], 'Responses OpenAI rollback differs')
            operations.append(('openai_config', openai))
        if self.r.get('original_tool'):
            def grants():
                self.webui.ok('POST', '/api/v1/tools/id/' + self.d['TOOL_ID'] + '/access/update', token=self.admin,
                    body={'access_grants': self.r['original_tool']['access_grants']})
                actual = self.webui.ok('GET', '/api/v1/tools/id/' + self.d['TOOL_ID'], token=self.admin)
                require(self.d['grant_set'](actual) == self.d['grant_set'](self.r['original_tool']), 'Responses Tool grant rollback differs')
            operations.append(('tool_grants', grants))
        if self.r.get('original_controls'):
            def controls():
                patch = controls_patch(self.r['original_controls'], self.d['provider']()['control'])
                if patch:
                    self.d['provider']('POST', '/__proof/control', patch)
                require(self.d['provider']()['control'] == self.r['original_controls'], 'Responses provider control rollback differs')
            operations.append(('provider_controls', controls))
        if self.r.get('probe_created'):
            def probe():
                # Native Function DELETE returns a JSON bool; reuse the existing
                # WebUI opener, whose ok() intentionally requires object JSON.
                from urllib.request import Request
                request = Request(self.d['WEBUI_URL'] + '/api/v1/functions/id/' + PROBE_ID + '/delete',
                    method='DELETE', headers={'Authorization': 'Bearer ' + self.admin})
                with self.webui.opener.open(request, timeout=20) as result:
                    require(result.code == 200 and result.read(32).strip() == b'true', 'Responses probe removal was not confirmed')
                self.r['probe_created'] = False
            operations.append(('diagnostic_function_removed', probe))
        for name, operation in operations:
            try:
                operation(); outcomes[name] = {'completed': True}
            except BaseException as error:
                outcomes[name] = {'completed': False, 'error_class': type(error).__name__}
        self.stage('failure_restoration_attempted_financial_state_retained')
        return {'restoration': outcomes, 'financial_rows_users_keys_deleted': False}


def worker_main(args):
    receipt = {'schema': 1, 'proof': PROOF, 'phase': args.worker_action, 'passed': False,
               'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'not_qualified': LIMITS}
    worker = None
    try:
        worker = Worker()
        if args.worker_action == 'prepare':
            result = worker.setup()
        elif args.worker_action == 'configure':
            result = worker.configure()
        elif args.worker_action == 'observe':
            result = worker.observe(args.chat_id, args.answer_id)
        elif args.worker_action == 'limit':
            result = worker.limit()
        elif args.worker_action == 'denied':
            result = worker.denied(args.chat_id, args.answer_id)
        else:
            result = worker.restore()
        receipt.update(result=result, passed=True, stage=worker.r.get('stage'))
        if args.worker_action == 'restore':
            receipt['passed'] = all(v['completed'] for v in result['restoration'].values())
    except BaseException as error:
        receipt.update(error_class=type(error).__name__, failed_stage=worker.r.get('stage') if worker else 'worker_initialization')
        if isinstance(error, ProofError):
            receipt['error_message'] = str(error)
    if args.worker_action in ('limit', 'denied') and worker is not None and hasattr(worker, 'denial_diagnostic'):
        receipt['denial_diagnostic'] = worker.denial_diagnostic
    try:
        print(json.dumps(safe(receipt, worker.secrets if worker else ()), allow_nan=False))
    except BaseException:
        print(json.dumps({'schema': 1, 'proof': PROOF, 'phase': args.worker_action, 'passed': False,
            'source_sha256': receipt['source_sha256'], 'error_class': 'SafeEmissionFailure', 'not_qualified': LIMITS}))
        return 1
    return 0 if receipt['passed'] else 1


def host_main(args):
    from prove_pricing_browser import PricingFixture, private_fixture, overwrite_config
    from prove_webui_browser import login, chat, write_json
    from playwright.sync_api import sync_playwright
    target = urlsplit(args.base_url)
    require(target.scheme == 'http' and target.port == 8080 and target.path in ('', '/') and not target.username
            and not target.password and not target.query and not target.fragment
            and isinstance(ipaddress.ip_address(target.hostname), ipaddress.IPv4Address)
            and ipaddress.ip_address(target.hostname).is_private, 'Responses host requires disposable private IPv4:8080')
    private, config, accounts, secrets = private_fixture(args.env_file, args.accounts, args.output)
    require(not (private / R_STATE.name).exists() and not (args.output / 'responses-chat.json').exists(), 'Responses requires fresh state/output')
    args.output.mkdir(exist_ok=True)
    fixture = PricingFixture(args.env_file, args.output, config, private, secrets)
    source = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    receipt = {'schema': 1, 'proof': PROOF, 'phase': 'host', 'passed': False, 'source_sha256': source, 'not_qualified': LIMITS}
    original, playwright, browser, context = None, None, None, None
    bound = False
    def phase(name, call=None, label=None):
        if name != 'restore':
            receipt['stage'] = 'worker_' + (label or name)
        command = fixture.command + ['exec', '-T', 'proxy', 'python', '-B', '/proof/prove_responses_chat.py', '--worker-action', name]
        if call:
            command += ['--chat-id', canonical(call['chat_id']), '--answer-id', canonical(call['message_id'])]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=180)
        packet = worker_packet(result, name, source, secrets)
        write_json(args.output / ('responses-' + (label or name) + '.json'), packet)
        if 'denial_diagnostic' in packet:
            receipt['denial_diagnostic'] = packet['denial_diagnostic']
        if result.returncode != 0 or not packet['passed']:
            raise WorkerFailure(packet)
        return packet['result']
    try:
        receipt['stage'] = 'bind_existing_fixture'
        fixture.bind(args.base_url)
        bound = True
        from prove_rag_service import serial_proxy
        receipt['serial_proxy_before'] = serial_proxy(fixture)
        composition = subprocess.run(fixture.command + ['config', '--format', 'json'], cwd=ROOT, capture_output=True, timeout=30)
        require(composition.returncode == 0 and len(composition.stdout) <= MAX_BYTES, 'Responses private Compose observation failed')
        composed = json.loads(composition.stdout)  # Contains secrets: never export.
        mounts = [m for m in composed['services']['proxy']['volumes'] if m.get('target') == '/proof/prove_responses_chat.py']
        require(len(mounts) == 1 and mounts[0].get('read_only') is True
                and Path(mounts[0]['source']).resolve() == Path(__file__).resolve(), 'Responses coordinator mount differs')
        receipt['prepare'] = phase('prepare')
        original = config.read_bytes()
        backup = private / 'responses-config-original.private.yaml'
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(original); handle.flush(); os.fsync(handle.fileno())
        changed = append_r(original)
        receipt['config'] = validate_config(original, changed)
        receipt['stage'] = 'append_r_restart_existing_proxy'
        overwrite_config(config, changed); fixture.restart()
        receipt['serial_proxy_after_reload'] = serial_proxy(fixture)
        receipt['configure'] = phase('configure')
        host_handoff = private / 'responses-browser-host.private.json'
        require(not host_handoff.exists() and not host_handoff.is_symlink(), 'Responses host private handoff already exists')
        proxy_id = serial_proxy(fixture)['running_proxy_container_ids'][0]
        copied = subprocess.run(['docker', 'cp', proxy_id + ':' + str(HANDOFF), str(host_handoff)],
            cwd=ROOT, capture_output=True, timeout=30)
        require(copied.returncode == 0 and host_handoff.is_file() and not host_handoff.is_symlink(), 'Responses container-owner handoff copy failed')
        os.chmod(host_handoff, 0o600)
        require(os.name != 'posix' or host_handoff.stat().st_uid == os.getuid(), 'Responses host private handoff owner differs')
        handoff = json.loads(host_handoff.read_text(encoding='utf-8'))
        require(handoff.get('schema') == 1 and len(handoff.get('users', [])) == 1, 'Responses browser private handoff differs')
        actor = handoff['users'][0]
        require(set(actor) == {'id', 'email', 'password'} and actor['id'] == receipt['prepare']['actor_id']
                and actor['email'].endswith('@example.com') and actor['password'], 'Responses browser handoff actor/profile differs')
        secrets.append(actor['password'])
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        context, page, token = login(browser, args.base_url, actor)
        secrets.append(token)
        receipt['stage'] = 'one_ordinary_send'
        call = chat(page, args.base_url, token, actor['id'], MODEL, 'success', 'responses-success', args.output,
                    expected_costs=('0.40', '0.40'))
        receipt['ordinary_send'] = call
        receipt['observe'] = phase('observe', call)
        from prove_cost_browser import cost_status, chat_state
        saved = chat_state(page, args.base_url, token, call['chat_id'])[call['message_id']]
        receipt['status_before_reload'] = cost_status(page, args.base_url, token, call, fixture,
            'responses-status', answer_spend='.40', chat_spend='.40')
        page.reload(wait_until='domcontentloaded')
        receipt['status_after_reload'] = cost_status(page, args.base_url, token, call, fixture,
            'responses-status-reloaded', answer_spend='.40', chat_spend='.40')
        require(chat_state(page, args.base_url, token, call['chat_id'])[call['message_id']] == saved,
                'Responses reload changed the persisted native answer/status')
        receipt['after_reload'] = phase('observe', call, label='after-reload')
        receipt['persisted_ui_costs'] = {'answer_usd': '.40', 'chat_usd': '.40', 'reload_visible': True}
        receipt['limit'] = phase('limit')
        denied = chat(page, args.base_url, token, actor['id'], MODEL, 'budget_blocked', 'responses-zero', args.output, expected_costs=None)
        receipt['denied'] = phase('denied', denied)
        receipt.update(stage='qualified_native_responses_financial_profile',
            success_state_lifetime='R model/connection/probe/user/key remain until existing disposable stand teardown')
        receipt['serial_proxy_after'] = serial_proxy(fixture)
        safe(receipt, secrets)
        receipt['passed'] = True
    except BaseException as error:
        record_failure(receipt, error)
    finally:
        for name, resource in [('context', context), ('browser', browser), ('playwright', playwright)]:
            if resource is not None:
                try:
                    resource.stop() if name == 'playwright' else resource.close()
                except BaseException as error:
                    receipt.setdefault('cleanup_failures', []).append({'resource': name, 'error_class': type(error).__name__})
        if receipt.get('cleanup_failures'):
            receipt['passed'] = False
        if not receipt['passed']:
            receipt['restoration'] = {}
            if bound and (private / R_STATE.name).exists():
                try:
                    receipt['restoration']['worker'] = phase('restore')
                except BaseException as error:
                    receipt['restoration']['worker_failure'] = type(error).__name__
                    if isinstance(error, WorkerFailure):
                        receipt['restoration']['worker_packet'] = error.packet
            if original is not None:
                try:
                    overwrite_config(config, original); fixture.restart()
                    receipt['restoration']['yaml_bytes_equal'] = config.read_bytes() == original
                except BaseException as error:
                    receipt['restoration']['yaml_failure'] = type(error).__name__
        safe(receipt, secrets)
        write_json(args.output / 'responses-chat.json', receipt)
    return 0 if receipt['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker-action', choices=('prepare', 'configure', 'observe', 'limit', 'denied', 'restore'))
    parser.add_argument('--chat-id'); parser.add_argument('--answer-id'); parser.add_argument('--base-url')
    for key in ('accounts', 'env-file', 'output'):
        parser.add_argument('--' + key, type=Path)
    args = parser.parse_args()
    if args.worker_action:
        return worker_main(args)
    require(all(getattr(args, k) is not None for k in ('base_url', 'accounts', 'env_file', 'output')), 'Incomplete Responses host arguments')
    return host_main(args)


if __name__ == '__main__':
    raise SystemExit(main())
