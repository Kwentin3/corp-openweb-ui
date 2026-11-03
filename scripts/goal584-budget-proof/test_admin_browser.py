"""Verifier rehearsal only: no browser, API, fixture process or provider calls."""
import copy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

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
        third = [*rows, dict(rows[0], user_id=ADMIN)]
        expanded = '<main data-budget-editor="v1"></main><script id="budget-data">' + json.dumps(third) + '</script>'
        self.assertEqual(DRIVER.editor_rows(expanded, expected_count=3), third)
        with self.assertRaises(AssertionError):
            DRIVER.editor_rows(expanded)

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


class InferenceSettlementTests(unittest.TestCase):
    def packet(self, pairs=None):
        before=snapshot()
        rows=[]
        for uid,model,count in ((IDS[0],DRIVER.MODELS[0],7),(IDS[0],DRIVER.MODELS[1],6),(IDS[1],DRIVER.MODELS[0],1)):
            for _ in range(count):
                rows.append({'request_id':'old-'+str(len(rows)), 'user_id':uid,'model_group':model,'spend_usd':'.20',
                             'owui_budget':{'retained':'synthetic historical row'}})
        rows.append({'request_id':'old-admin','user_id':ADMIN,'model_group':DRIVER.MODELS[0],'spend_usd':'2.00'})
        before['attributed_spend_logs']=rows
        pairs=[(IDS[0],DRIVER.MODELS[0]),(IDS[1],DRIVER.MODELS[1])] if pairs is None else pairs
        final=copy.deepcopy(before)
        for index,(uid,model) in enumerate(pairs):
            user=next(row for row in final['users'] if row['user_id']==uid)
            key=next(row for row in final['keys'] if row['user_id']==uid and row['model']==model)
            user['spend_usd']=str(Decimal(user['spend_usd'])+Decimal('.20'))
            key['spend_usd']=str(Decimal(key['spend_usd'])+Decimal('.20'))
            final['attributed_spend_logs'].append({'request_id':'new-'+str(index),'user_id':uid,
                'model_group':model,'spend_usd':'.20'})
        return before,final,pairs

    def settle(self, fixture, before, pairs, *, targets=IDS, timeout=1):
        clock=[0.0]
        def sleep(seconds):clock[0]+=seconds
        with patch.object(DRIVER,'time',SimpleNamespace(monotonic=lambda:clock[0],sleep=sleep)):
            return DRIVER.wait_inference_delta(fixture,before,targets,pairs,timeout=timeout)

    def test_partial_user_key_and_event_lag_require_all_observed_values_without_input_mutation(self):
        before,final,pairs=self.packet()
        pending=copy.deepcopy(final)
        pending['users']=copy.deepcopy(before['users']);pending['keys']=copy.deepcopy(before['keys'])
        partial=copy.deepcopy(pending);partial['users']=copy.deepcopy(final['users'])
        missing_row=copy.deepcopy(final);missing_row['attributed_spend_logs'].pop()
        sequence=[pending,partial,missing_row,final]
        unchanged=copy.deepcopy(sequence)
        fixture=SimpleNamespace(snapshot=Mock(side_effect=sequence))
        actual,evidence=self.settle(fixture,before,pairs)
        self.assertIs(actual,final)
        self.assertEqual(fixture.snapshot.call_count,4)
        self.assertEqual((evidence['observations'],evidence['expected_successful_calls'],evidence['matched_new_native_rows']),(4,2,2))
        self.assertEqual(sequence,unchanged)
        DRIVER.verify_inference_delta(before,actual,IDS,pairs)

    def test_unrelated_admin_ledger_rows_are_not_counted_as_staff_inference(self):
        before,final,pairs=self.packet()
        final['attributed_spend_logs'][-3]['spend_usd']='999'
        final['attributed_spend_logs'].append({'request_id':'new-admin','user_id':ADMIN,'model_group':DRIVER.MODELS[1],'spend_usd':'.20'})
        actual,evidence=self.settle(SimpleNamespace(snapshot=Mock(return_value=final)),before,pairs)
        self.assertIs(actual,final)
        self.assertEqual(evidence['matched_new_native_rows'],2)

    def test_pending_snapshots_timeout_and_never_repeat_a_model_or_financial_write(self):
        before,final,pairs=self.packet()
        pending=copy.deepcopy(final);pending['users']=copy.deepcopy(before['users']);pending['keys']=copy.deepcopy(before['keys'])
        fixture=SimpleNamespace(snapshot=Mock(return_value=pending))
        with self.assertRaisesRegex(AssertionError,'counters/ledger did not settle'):
            self.settle(fixture,before,pairs,timeout=.5)
        self.assertEqual(fixture.snapshot.call_count,3)

    def test_conflicts_regression_excess_and_ledger_mutations_fail_even_while_another_counter_is_pending(self):
        before,final,pairs=self.packet()
        mutations=[lambda s:s['keys'][0].update(max_budget_usd='9'),
                   lambda s:s['keys'][0].update(key_alias='changed'),
                   lambda s:s['users'][0].update(budget_reset_at='2030-01-01'),
                   lambda s:s['users'][1].update(spend_usd='.19'),
                   lambda s:s['users'][1].update(spend_usd='.41'),
                   lambda s:s['keys'][-1].update(spend_usd='.40'),
                   lambda s:s['keys'][1].update(spend_usd='1.200000000001'),
                   lambda s:s['users'][1].update(spend_usd='NaN'),
                   lambda s:s['attributed_spend_logs'].pop(0),
                   lambda s:s['attributed_spend_logs'][0]['owui_budget'].update(retained='changed'),
                   lambda s:s['attributed_spend_logs'].append(copy.deepcopy(s['attributed_spend_logs'][-1])),
                   lambda s:s['attributed_spend_logs'].append({'request_id':'extra','user_id':IDS[1],'model_group':DRIVER.MODELS[1],'spend_usd':'.20'}),
                   lambda s:s['attributed_spend_logs'][-1].update(spend_usd='.2000000001'),
                   lambda s:s['attributed_spend_logs'][-1].update(model_group=DRIVER.MODELS[0])]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                bad=copy.deepcopy(final);bad['users'][0]['spend_usd']=before['users'][0]['spend_usd'];mutate(bad)
                fixture=SimpleNamespace(snapshot=Mock(side_effect=[bad,final]))
                with self.assertRaises(AssertionError):self.settle(fixture,before,pairs)
                self.assertEqual(fixture.snapshot.call_count,1)

    def test_single_user_adapter_uses_same_counter_owner_and_preserves_hard_zero_model_b(self):
        before,final,pairs=self.packet([(IDS[1],DRIVER.MODELS[0])])
        self.settle(SimpleNamespace(snapshot=Mock(return_value=final)),before,pairs,targets=(IDS[1],))
        bad=copy.deepcopy(final);bad['keys'][-1]['spend_usd']='.000000000001'
        with self.assertRaisesRegex(AssertionError,'unchanged'):
            self.settle(SimpleNamespace(snapshot=Mock(return_value=bad)),before,pairs,targets=(IDS[1],))

    def test_binary_float_rounding_uses_existing_browser_bound_without_changing_ledger_values(self):
        before,final,pairs=self.packet([(IDS[0],DRIVER.MODELS[0])])
        before['users'][0]['spend_usd']='2.6000000000000001'
        final['users'][0]['spend_usd']='2.8000000000000003'
        final['keys'][0]['spend_usd']='1.5999999999999999'
        actual,_=self.settle(SimpleNamespace(snapshot=Mock(return_value=final)),before,pairs)
        self.assertEqual(actual['attributed_spend_logs'][-1]['spend_usd'],'.20')
        DRIVER.verify_inference_delta(before,actual,IDS,pairs)

    def test_unchanged_actual_run32_event_with_stale_counters_times_out(self):
        root=HERE.parents[1]/'local/goal584/runtime-proof-41618051782/receipts/admin'
        if not (root/'admin-native-06.json').is_file():self.skipTest('Optional actual run32 evidence unavailable')
        before=json.loads((root/'admin-native-05.json').read_text(encoding='utf-8'))
        observed=json.loads((root/'admin-native-06.json').read_text(encoding='utf-8'))
        old_ids={row['request_id'] for row in before['attributed_spend_logs']}
        added=[row for row in observed['attributed_spend_logs'] if row['request_id'] not in old_ids]
        self.assertEqual(len(added),1)
        self.assertEqual((added[0]['model_group'],Decimal(added[0]['spend_usd'])),(DRIVER.MODELS[1],Decimal('.20')))
        targets=[row['user_id'] for row in before['users']]
        preserved=copy.deepcopy(observed)
        fixture=SimpleNamespace(snapshot=Mock(return_value=observed))
        with self.assertRaisesRegex(AssertionError,'did not settle'):
            self.settle(fixture,before,[(added[0]['user_id'],DRIVER.MODELS[1])],targets=targets,timeout=.5)
        self.assertEqual(fixture.snapshot.call_count,3)
        self.assertEqual(observed,preserved)


if __name__ == '__main__':
    unittest.main()
