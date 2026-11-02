"""Representative native-shaped artifact rehearsal and negative mutations; no I/O calls."""
import copy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from uuid import uuid4

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
SPEC = importlib.util.spec_from_file_location('goal584_verify_admin_calls_under_test', HERE / 'verify_admin_calls.py')
V = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V)


def packet():
    admin, u1, u2 = [str(uuid4()) for _ in range(3)]
    staff, chat_id = [u1, u2], str(uuid4())
    skill, intent, results = V.source_contract()
    original = {'schema': 1, 'type': 'employee_budget_plan', 'changes': [
        {'user_id': u1, 'expected_revision': 'a' * 64, 'budget_usd': '40', 'shares': {'goal584-a': '100', 'goal584-b': '0'}},
        {'user_id': u2, 'expected_revision': 'b' * 64, 'budget_usd': '0.4', 'shares': {'goal584-a': '50', 'goal584-b': '50'}}]}
    recovery = {'schema': 1, 'type': 'employee_budget_plan', 'changes': [
        {'user_id': u2, 'expected_revision': 'c' * 64, 'budget_usd': '0.8', 'shares': {'goal584-a': '50', 'goal584-b': '50'}}]}
    serialize = lambda value: json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    texts = [intent, serialize(original), serialize(original), serialize(recovery)]
    browser = {'passed': True, 'admin_id': admin, 'staff_ids': staff, 'model_id': 'goal584-budget-admin',
               'original_proposal': original, 'recovery_proposal': recovery, 'calls': []}
    for label, value in zip(('opened', 'canceled', 'applied', 'recovered'), texts):
        browser[label] = {'admin_id': admin, 'parent_author_id': admin, 'model_id': browser['model_id'],
            'chat_id': chat_id, 'assistant_id': str(uuid4()), 'parent_user_id': str(uuid4()), 'stored_parent_text': value,
            'exact_submitted_and_stored_strings': True, 'terminal_persisted': True, 'sandbox_same_origin': False}
    provider, context, rows = {'synthetic': True, 'requests': []}, {'requests': []}, []
    schemas = [{'type': 'function', 'function': {'name': name, 'description': 'Native source description',
                'parameters': {'type': 'object', 'properties': properties}}} for name, properties in (
        ('open_budget_form', {'view_json': {'type': 'string', 'default': '{}'}}), ('apply_budget_form', {}))]
    def add(owner, model, chat, answer, messages, *, completed=True, tools=None):
        scope = {'schema': 1, 'user_id': owner, 'chat_id': chat, 'answer_id': answer, 'root_chat_id': chat,
                 'root_answer_id': answer, 'model': model, 'call_id': str(uuid4()), 'category': 'personal'}
        body = {'model': model, 'messages': copy.deepcopy(messages), 'stream': True, 'max_tokens': 5}
        if tools is not None:
            body['tools'] = copy.deepcopy(tools)
        captured = {'user_id': owner, 'task': '', 'body': body, 'body_after_auth': copy.deepcopy(body),
                    'attestation_present_before': True, 'provenance_removed_after': True, 'verified_cost_scope': scope}
        context['requests'].append(captured)
        if completed:
            captured['native_stream_usage_patch'] = {'stream_options': {'include_usage': True}, '_litellm_strip_stream_usage': True}
            identifier = 'chatcmpl-rehearsal-' + uuid4().hex
            physical = copy.deepcopy(body)
            physical.update(model=V.PHYSICAL[model], stream_options={'include_usage': True})
            provider['requests'].append({'id': identifier, 'body': physical,
                'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}})
            rows.append({'request_id': identifier, 'user_id': owner, 'model_group': model, 'session_id': chat,
                'owui_budget': scope, 'spend_usd': '.2', 'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15})
    history = [{'role': 'system', 'content': skill}]
    labels = ('opened', 'canceled', 'applied', 'recovered')
    def admin_turn(index):
        label = labels[index]
        turn = browser[label]
        history.append({'role': 'user', 'content': texts[index]})
        add(admin, 'goal584-a', chat_id, turn['assistant_id'], history, tools=schemas)
        call_id = 'call-rehearsal-' + uuid4().hex
        function = 'open_budget_form' if index == 0 else 'apply_budget_form'
        history.extend([{'role': 'assistant', 'content': '', 'tool_calls': [{'id': call_id, 'type': 'function',
            'function': {'name': function, 'arguments': serialize({'view_json': '{}'} if index == 0 else {})}}]},
            {'role': 'tool', 'tool_call_id': call_id, 'content': json.dumps(results[label], ensure_ascii=False)}])
        add(admin, 'goal584-a', chat_id, turn['assistant_id'], history, tools=schemas)
        history.append({'role': 'assistant', 'content': 'Proof'})
    for index in range(3):
        admin_turn(index)
    sequence = [(u1, 'goal584-b', False), (u1, 'goal584-a', True), (u2, 'goal584-a', False),
                (u2, 'goal584-b', True), (u2, 'goal584-b', False), (u2, 'goal584-b', True)]
    for index, (uid, model, completed) in enumerate(sequence):
        if index == 5:
            admin_turn(3)
        chat, answer = str(uuid4()), str(uuid4())
        browser['calls'].append({'user_id': uid, 'model': model, 'chat_id': chat, 'message_id': answer,
                                'outcome': 'success' if completed else 'budget_blocked', 'terminal_persisted': True})
        add(uid, model, chat, answer, [{'role': 'user', 'content': 'Hi'}], completed=completed)
    # Existing positive history is real input shape, not silently discarded.
    baseline = []
    for uid in staff:
        old = copy.deepcopy(next(row for row in rows if row['user_id'] == uid))
        old.update(request_id='prior-native-' + uuid4().hex)
        old['owui_budget'] = dict(old['owui_budget'], call_id=str(uuid4()), chat_id=str(uuid4()), answer_id=str(uuid4()))
        old['owui_budget'].update(root_chat_id=old['owui_budget']['chat_id'], root_answer_id=old['owui_budget']['answer_id'])
        old['session_id'] = old['owui_budget']['chat_id']
        rows.append(old)
        baseline.append(old['request_id'])
    browser['baseline_positive_request_ids'] = baseline
    users, keys = [], []
    for uid in [*staff, admin]:
        users.append({'user_id': uid, 'spend_usd': str(sum((Decimal(r['spend_usd']) for r in rows if r['user_id'] == uid), Decimal(0)))})
        for model in V.MODELS:
            keys.append({'user_id': uid, 'model': model, 'spend_usd': str(sum((Decimal(r['spend_usd']) for r in rows
                if r['user_id'] == uid and r['model_group'] == model), Decimal(0)))})
    native = {'passed': True, 'attributed_spend_logs': rows, 'users': users[:2], 'keys': keys[:4],
              'admin_accounting': {'users': users[2:], 'keys': keys[4:]}, 'unqualified_zero_row_count': 0}
    return [browser, provider, context, native]


class ArtifactVerifierTests(unittest.TestCase):
    def test_native_shaped_11_calls_14_attempts_and_baseline(self):
        receipt = V.verify(*packet())
        self.assertTrue(receipt['passed'])
        self.assertEqual((receipt['physical_calls'], receipt['signed_attempts'], receipt['admin_physical_calls']), (11, 14, 8))

    def reject(self, mutate):
        args = packet()
        mutate(args)
        with self.assertRaises((AssertionError, ValueError, KeyError)):
            V.verify(*args)

    def test_reject_missing_extra_duplicate_provider_and_native_rows(self):
        self.reject(lambda a: a[1]['requests'].pop())
        self.reject(lambda a: a[1]['requests'].append(copy.deepcopy(a[1]['requests'][0])))
        self.reject(lambda a: a[3]['attributed_spend_logs'].pop())
        def extra(a):
            row = copy.deepcopy(a[3]['attributed_spend_logs'][0])
            row['request_id'] = 'extra-positive'
            row['owui_budget']['call_id'] = str(uuid4())
            a[3]['attributed_spend_logs'].append(row)
        self.reject(extra)

    def test_reject_wrong_actor_root_nonce_usage_and_payer_total(self):
        for field in ('user_id', 'root_chat_id', 'root_answer_id'):
            self.reject(lambda a, field=field: a[2]['requests'][0]['verified_cost_scope'].__setitem__(field, str(uuid4())))
        self.reject(lambda a: a[2]['requests'][1]['verified_cost_scope'].__setitem__('call_id', a[2]['requests'][0]['verified_cost_scope']['call_id']))
        self.reject(lambda a: a[1]['requests'][0]['usage'].__setitem__('prompt_tokens', 9))
        self.reject(lambda a: a[3]['attributed_spend_logs'][0].__setitem__('spend_usd', '.21'))
        self.reject(lambda a: a[3]['admin_accounting']['users'][0].__setitem__('spend_usd', '0'))
        self.reject(lambda a: a[3]['admin_accounting']['keys'].pop())

    def test_reject_rewritten_current_json_and_history(self):
        def rewrite(a):
            for key in ('body', 'body_after_auth'):
                messages = a[2]['requests'][2][key]['messages']
                messages[-1]['content'] = messages[-1]['content'].replace('"40"', '"41"')
            a[1]['requests'][2]['body']['messages'][-1]['content'] = a[2]['requests'][2]['body']['messages'][-1]['content']
        self.reject(rewrite)
        self.reject(lambda a: a[2]['requests'][0]['body_after_auth']['messages'][0].__setitem__('content', 'changed'))

    def test_reject_tool_business_arguments_and_wrong_cancel_status(self):
        def arguments(a):
            for key in ('body', 'body_after_auth'):
                a[2]['requests'][3][key]['messages'][-2]['tool_calls'][0]['function']['arguments'] = '{"changes":[]}'
            a[1]['requests'][3]['body']['messages'][-2]['tool_calls'][0]['function']['arguments'] = '{"changes":[]}'
        self.reject(arguments)
        def cancel(a):
            for key in ('body', 'body_after_auth'):
                a[2]['requests'][3][key]['messages'][-1]['content'] = '{"status":"success","message":"wrong"}'
            a[1]['requests'][3]['body']['messages'][-1]['content'] = '{"status":"success","message":"wrong"}'
        self.reject(cancel)

    def test_reject_full_skill_truncation_or_demotion_even_if_all_copies_match(self):
        for demote in (False, True):
            def mutate(a, demote=demote):
                for key in ('body', 'body_after_auth'):
                    message = a[2]['requests'][0][key]['messages'][0]
                    if demote:
                        message['role'] = 'user'
                    else:
                        message['content'] = message['content'].replace('never claim that limits changed merely because a plan was drafted or submitted.', '')
                a[1]['requests'][0]['body']['messages'][0] = copy.deepcopy(a[2]['requests'][0]['body']['messages'][0])
            self.reject(mutate)

    def test_reject_html_or_credentials_even_when_auth_and_provider_agree(self):
        for content in ('<!doctype html><main data-budget-editor="v1">UI</main>', 'sk-' + 'x' * 32):
            def mutate(a, content=content):
                for key in ('body', 'body_after_auth'):
                    a[2]['requests'][0][key]['messages'][0]['content'] += content
                a[1]['requests'][0]['body']['messages'][0]['content'] += content
            self.reject(mutate)

    def test_reject_missing_schema_and_changed_native_normalization(self):
        self.reject(lambda a: a[1]['requests'][0]['body']['tools'].pop())
        self.reject(lambda a: a[1]['requests'][0]['body']['stream_options'].__setitem__('include_usage', False))
        self.reject(lambda a: a[2]['requests'][0]['native_stream_usage_patch'].__setitem__('messages', []))


if __name__ == '__main__':
    unittest.main()
