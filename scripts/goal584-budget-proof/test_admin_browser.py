"""Verifier rehearsal only: no browser, API, fixture process or provider calls."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
SPEC = importlib.util.spec_from_file_location('goal584_admin_browser_under_test', HERE / 'prove_admin_browser.py')
DRIVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DRIVER)
IDS = ('11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222')
ADMIN = '33333333-3333-4333-8333-333333333333'
CHAT = '44444444-4444-4444-8444-444444444444'
PARENT = '55555555-5555-4555-8555-555555555555'
ANSWER = '66666666-6666-4666-8666-666666666666'


def snapshot():
    return {'users': [{'user_id': uid, 'max_budget_usd': '20', 'spend_usd': '2.6' if i == 0 else '.2',
                      'budget_duration': '30d', 'budget_reset_at': '2026-12-01T00:00:00Z'} for i, uid in enumerate(IDS)],
            'keys': [{'user_id': uid, 'model': model, 'key_alias': f'synthetic-{i}-{j}', 'max_budget_usd': '10',
                      'spend_usd': ('1.4' if j == 0 else '1.2') if i == 0 else ('.2' if j == 0 else '0'),
                      'budget_duration': '30d', 'budget_reset_at': '2026-12-01T00:00:00Z'}
                     for i, uid in enumerate(IDS) for j, model in enumerate(DRIVER.MODELS)]}


def public_rows(state):
    rows = []
    for user in state['users']:
        uid = user['user_id']
        models = []
        for key in state['keys']:
            if key['user_id'] == uid:
                share = str(DRIVER.Decimal(key['max_budget_usd']) * 100 / DRIVER.Decimal(user['max_budget_usd']))
                models.append({'id': key['model'], 'label': key['model'], 'cap_usd': key['max_budget_usd'],
                               'spend_usd': key['spend_usd'], 'share_percent': str(DRIVER.Decimal(share).normalize())})
        rows.append({'user_id': uid, 'name': 'Synthetic', 'email': 'synthetic@example.invalid', 'department': '',
                     'revision': 'a' * 64, 'budget_usd': user['max_budget_usd'], 'spend_usd': user['spend_usd'],
                     'remaining_usd': str(DRIVER.Decimal(user['max_budget_usd']) - DRIVER.Decimal(user['spend_usd'])),
                     'models': models})
    return rows


def changed_state(before, second='.4'):
    result = copy.deepcopy(before)
    for user in result['users']:
        user['max_budget_usd'] = '40' if user['user_id'] == IDS[0] else second
    for key in result['keys']:
        key['max_budget_usd'] = ('40' if key['model'] == DRIVER.MODELS[0] else '0') if key['user_id'] == IDS[0] else str(DRIVER.Decimal(second) / 2)
    return result


class AdminVerifierTests(unittest.TestCase):
    def test_exact_plan_and_changed_rows_only_recovery(self):
        plan = DRIVER.planned_changes(public_rows(snapshot()), IDS)
        self.assertEqual(plan['changes'][0]['budget_usd'], '40')
        self.assertEqual(plan['changes'][1]['budget_usd'], '0.4')
        self.assertEqual(plan['changes'][0]['shares'], {'goal584-a': '100', 'goal584-b': '0'})
        applied = changed_state(snapshot())
        rows = public_rows(applied)
        # Native public policy emits plain money strings, not Decimal exponent notation.
        for row in rows:
            for model in row['models']:
                model['share_percent'] = format(DRIVER.Decimal(model['share_percent']), 'f')
        recovery = DRIVER.planned_changes(rows, IDS, second_budget='0.8')
        self.assertEqual(len(recovery['changes']), 1)
        self.assertEqual(recovery['changes'][0]['user_id'], IDS[1])
        with self.assertRaises(AssertionError):
            DRIVER.planned_changes(rows, (IDS[0], ADMIN))

    def test_exact_authenticated_parent_not_latest_user_or_rewritten_text(self):
        model = 'goal584-budget-admin'
        text = json.dumps(DRIVER.planned_changes(public_rows(snapshot()), IDS), separators=(',', ':'))
        sent = {'id': ANSWER, 'model': model, 'user_message': {'id': PARENT, 'role': 'user', 'content': text}}
        stored = {'id': CHAT, 'user_id': ADMIN, 'chat': {'history': {'messages': {
            ANSWER: {'id': ANSWER, 'role': 'assistant', 'model': model, 'parentId': PARENT},
            PARENT: {'id': PARENT, 'role': 'user', 'user_id': ADMIN, 'content': text},
            'other-latest': {'id': 'other-latest', 'role': 'user', 'user_id': IDS[0], 'content': 'ignore'}}}}}
        _, proof = DRIVER.verify_parent(stored, sent, ADMIN, model, expected_text=text)
        self.assertEqual(proof['parent_user_id'], PARENT)
        for label in ('foreign_actor', 'wrong_parent', 'rewritten_json', 'wrong_model'):
            broken = copy.deepcopy(stored)
            messages = broken['chat']['history']['messages']
            if label == 'foreign_actor':
                messages[PARENT]['user_id'] = IDS[0]
            elif label == 'wrong_parent':
                messages[ANSWER]['parentId'] = 'other-latest'
            elif label == 'rewritten_json':
                messages[PARENT]['content'] = text.replace('"40"', '"41"')
            else:
                messages[ANSWER]['model'] = 'other'
            with self.subTest(label=label), self.assertRaises(AssertionError):
                DRIVER.verify_parent(broken, sent, ADMIN, model, expected_text=text)

    def test_saved_caps_match_native_and_preserve_spend_reset_identity(self):
        before = snapshot()
        after = changed_state(before)
        DRIVER.verify_saved(before, after, public_rows(after), IDS)
        for field, value in [('spend_usd', '999'), ('budget_reset_at', '2030-01-01'), ('key_alias', 'other'), ('max_budget_usd', '0.1')]:
            broken = copy.deepcopy(after)
            broken['keys'][0][field] = value
            with self.subTest(field=field), self.assertRaises(AssertionError):
                DRIVER.verify_saved(before, broken, public_rows(after), IDS)
        wrong_ui = public_rows(after)
        wrong_ui[0]['models'][0]['spend_usd'] = '999'
        with self.assertRaises(AssertionError):
            DRIVER.verify_saved(before, after, wrong_ui, IDS)

    def test_inference_delta_rejects_extra_call_or_cap_change(self):
        before = changed_state(snapshot())
        after = copy.deepcopy(before)
        after['users'][0]['spend_usd'] = '2.8'
        after['keys'][0]['spend_usd'] = '1.6'
        DRIVER.verify_inference_delta(before, after, IDS, [(IDS[0], DRIVER.MODELS[0])])
        for section, field, value in [('keys', 'spend_usd', '1.8'), ('users', 'max_budget_usd', '100')]:
            broken = copy.deepcopy(after)
            broken[section][0][field] = value
            with self.assertRaises(AssertionError):
                DRIVER.verify_inference_delta(before, broken, IDS, [(IDS[0], DRIVER.MODELS[0])])

    def test_prepared_editor_data_parser_and_credential_guard(self):
        rows = public_rows(snapshot())
        html = '<main data-budget-editor="v1"></main><script id="budget-data" type="application/json">' + json.dumps(rows) + '</script>'
        self.assertEqual(DRIVER.editor_rows(html), rows)
        with self.assertRaises(AssertionError):
            DRIVER.editor_rows(html + '<p>sk-' + 'x' * 32 + '</p>')
        with self.assertRaises(AssertionError):
            DRIVER.editor_rows(html + '<script id="budget-data">[]</script>')

    def test_server_diff_expected_from_original_native_fields(self):
        rows = public_rows(snapshot())
        lines = DRIVER.diff_lines(rows, DRIVER.planned_changes(rows, IDS))
        self.assertEqual(lines, ['Бюджет USD: 20 → 40', 'goal584-a: 10 → 40 USD', 'goal584-b: 10 → 0 USD',
                                 'Бюджет USD: 20 → 0.4', 'goal584-a: 10 → 0.2 USD', 'goal584-b: 10 → 0.2 USD'])

    def test_editor_belongs_to_completed_correlated_native_tool_result(self):
        html = '<main data-budget-editor="v1">Actual native editor</main>'
        message = {'done': True, 'output': [
            {'type': 'function_call', 'name': 'open_budget_form', 'call_id': 'call-native-1', 'status': 'completed'},
            {'type': 'function_call_output', 'call_id': 'call-native-1', 'status': 'completed', 'embeds': [html]}]}
        self.assertEqual(DRIVER.editor_embeds(message, 'open_budget_form'), [html])
        for field, value in [('call_id', 'foreign-call'), ('status', 'failed'), ('type', 'message')]:
            broken = copy.deepcopy(message)
            broken['output'][1][field] = value
            self.assertEqual(DRIVER.editor_embeds(broken, 'open_budget_form'), [])
        self.assertEqual(DRIVER.editor_embeds(message, 'apply_budget_form'), [])
        self.assertEqual(DRIVER.editor_embeds({'embeds': [html]}, 'open_budget_form'), [])


if __name__ == '__main__':
    unittest.main()
