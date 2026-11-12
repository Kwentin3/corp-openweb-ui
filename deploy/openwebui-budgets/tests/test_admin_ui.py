"""Renderer contract plus opt-in real Chrome sandbox transport rehearsal."""
from html import escape
from html.parser import HTMLParser
import importlib.util
import copy
from decimal import Decimal
import json
import os
from pathlib import Path
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


SOURCE = Path(__file__).resolve().parents[1] / 'admin_ui.py'
SPEC = importlib.util.spec_from_file_location('goal584_admin_ui_under_test', SOURCE)
UI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UI)
IDS = ('11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222')


def rows():
    return [{'user_id': value, 'name': 'Employee ' + str(i + 1), 'email': f'user{i + 1}@example.invalid',
             'groups': [{'id': 'group-' + str(i + 1), 'name': 'Group ' + str(i + 1)}],
             'revision': 'revision-' + str(i + 1),
             'budget_usd': '10.00', 'spend_usd': '1.25', 'remaining_usd': '8.75', 'models': [
                 {'id': 'model-a', 'label': 'Model A', 'cap_usd': '5.00', 'spend_usd': '.25', 'share_percent': '50.00'},
                 {'id': 'model-b', 'label': 'Model B', 'cap_usd': '5.00', 'spend_usd': '1.00', 'share_percent': '50.00'}]}
            for i, value in enumerate(IDS)]


def template():
    return {'revision': 'template-revision', 'budget_usd': '0.80', 'budget_duration': '1mo', 'shares': [
        {'id': 'model-a', 'label': 'Model A', 'share_percent': '100'},
        {'id': 'model-b', 'label': 'Model B', 'share_percent': '0'}]}


def pending_rows():
    return [{'user_id': 'pending-' + str(i), 'name': 'New employee ' + str(i),
             'email': f'new{i}@example.invalid', 'revision': 'pending-revision-' + str(i),
             'state': state, 'code': state + '_assignment',
             'models': [{'id': 'model-a', 'label': 'Model A'}, {'id': 'model-b', 'label': 'Model B'}],
             'suggested_budget_usd': '0.80' if i == 0 else None,
             'suggested_shares': {'model-a': '100', 'model-b': '0'} if i == 0 else None}
            for i, state in enumerate(('absent', 'absent', 'incomplete', 'conflict'))]


def overview():
    return {'prices': [
        {'id': 'model-a', 'label': 'Model A', 'input_per_million': '0.1234567890123456789',
         'output_per_million': '1.20', 'cache_per_million': None, 'as_of': '2026-11-11T12:00:00Z',
         'source': 'remote', 'changed': True},
        {'id': 'model-b', 'label': 'Model B', 'input_per_million': None,
         'output_per_million': None, 'cache_per_million': '0', 'as_of': None,
         'source': 'local', 'changed': False}],
        'accounts': [
            {'id': 'opaque-account-' + str(i), 'label': 'Account ' + str(i), 'status': status,
             'event_at': None if status == 'unknown' else '2026-11-11T12:30:00Z',
             'balance': {'amount': '-1.000000000000000001', 'currency': 'USD',
                         'observed_at': '2026-11-10T10:00:00Z', 'actor': 'Server-owned actor',
                         'source': 'manual'} if i == 0 else None,
             'revision': 'account-revision-' + str(i)}
            for i, status in enumerate(('financial_refusal', 'success', 'unknown'))]}


class Parser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags, self.scripts, self.in_script = [], [], False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag == 'script':
            self.in_script = True
            self.scripts.append('')

    def handle_data(self, data):
        if self.in_script:
            self.scripts[-1] += data

    def handle_endtag(self, tag):
        if tag == 'script':
            self.in_script = False


class RendererTests(unittest.TestCase):
    def test_incomplete_provider_read_is_visible_without_claiming_zero_balance(self):
        supplied = overview()
        supplied['complete'] = False
        html = UI.render_editor(rows(), as_of='owned', overview=supplied)
        self.assertIn('Не удалось полностью проверить финансовые отказы провайдеров.', html)
        self.assertIn('Финансовый отказ', html)
        self.assertNotIn('Баланс равен нулю', html)

    def test_overview_projects_only_supplied_observations_and_server_owned_identity(self):
        supplied = overview()
        supplied['accounts'][0]['private_extra'] = 'PRIVATE_ACCOUNT'
        supplied['prices'][0]['private_extra'] = 'PRIVATE_PRICE'
        before = copy.deepcopy(supplied)
        html = UI.render_editor(rows(), as_of='owned', overview=supplied)
        parser = Parser(html)
        self.assertIn('data-money="0.1234567890123456789"', html)
        self.assertIn('data-money="1.20"', html)
        self.assertIn('title="нет данных USD"', html)
        self.assertEqual(html.count('class="price-changed"'), 1)
        self.assertIn('Кэш: <span data-money="0"', html)
        self.assertIn('Источник: Каталог LiteLLM', html)
        self.assertIn('Источник: Встроенный каталог LiteLLM', html)
        self.assertIn('Финансовый отказ', html)
        self.assertNotIn('Успешный запрос', html)
        self.assertIn('Наблюдение:', html)
        self.assertIn('Событие запроса, не текущий баланс.', html)
        self.assertLess(html.index('class="account-refusal"'), html.index('id="employee-table"'))
        self.assertEqual(html.count('USD / 1M токенов · вход / выход'), 1)
        self.assertNotIn('Последний известный баланс', html)
        self.assertNotIn('Server-owned actor', html)
        self.assertNotIn('PRIVATE_', html)
        self.assertEqual(len(parser.scripts), 2)
        self.assertNotIn('opaque-account-', html)
        self.assertNotIn('provider_balance_snapshot', html)
        fields = [attrs['data-balance-field'] for tag, attrs in parser.tags
                  if tag == 'input' and 'data-balance-field' in attrs]
        self.assertEqual(fields, [])
        self.assertEqual(supplied, before)
        empty = UI.render_editor([], as_of='owned', overview=supplied)
        self.assertIn('Model A', empty)

    def test_overview_and_employee_model_disclosure_escape_and_never_derive_values(self):
        attack = '</script><img src=x onerror="alert(1)"><&\u2028\u2029'
        data, supplied = rows(), overview()
        data[0]['models'][0].update(remaining_usd='4.750000000000000001', new=False, pending=True)
        data[0]['models'][1].update(expense_status='unknown', remaining_usd=None, new=False)
        for price in supplied['prices']:
            for key in ('input_per_million', 'output_per_million', 'cache_per_million', 'source', 'as_of'):
                price[key] = attack
        account = supplied['accounts'][0]
        for key in ('id', 'label', 'status', 'event_at', 'revision'):
            account[key] = attack
        account['balance'] = {key: attack for key in ('amount', 'currency', 'observed_at', 'actor', 'source')}
        html = UI.render_editor(data, as_of='owned', overview=supplied)
        parser = Parser(html)
        self.assertNotIn('<img', html)
        self.assertIn('&lt;img', html)
        self.assertNotIn('<', parser.scripts[0])
        self.assertNotIn('class="account-refusal"', html)
        self.assertIn('data-money="4.750000000000000001"', html)
        self.assertIn('Остаток по учёту: <span data-money=""', html)
        self.assertIn('class="new-model">новая', html)
        self.assertIn('<strong>Расход неизвестен.</strong>', html)
        projected = json.loads(parser.scripts[0])[0]['models']
        self.assertEqual(projected[0]['remaining_usd'], '4.750000000000000001')
        self.assertIs(projected[0]['pending'], True)
        self.assertIs(projected[1]['new'], False)

    def test_unknown_expense_is_primary_recorded_amount_and_known_part_are_separate(self):
        data = rows()
        data[0].update(expense_status='unknown', spend_usd='9.99', remaining_usd='0.01',
                       known_subtotal_usd='0.33')
        data[0]['models'][0].update(expense_status='unknown', spend_usd='.9',
                                   known_subtotal_usd='.2', blocked=True)
        before = copy.deepcopy(data)
        html = UI.render_editor(data, as_of='owned-global-time')
        section = html.split('<tr data-employee-id=', 1)[1].split('<tr data-employee-id=', 1)[0]
        spend = section.split('<td>', 2)[2].split('</td>', 1)[0]
        self.assertIn('data-money="9.99"', spend)
        self.assertIn('Неизвестен', spend)
        self.assertIn('<span role="status"><strong>Расход неизвестен.</strong></span>', section)
        self.assertIn('<small>В истории есть запросы без данных о расходе.</small>', section)
        self.assertIn('По данным учёта: 9.99 USD. Эта сумма не подтверждает итоговый расход.', section)
        self.assertIn('<small>Подтверждённая часть расхода: 0.33 USD. Итог не подтверждён.</small>', section)
        self.assertLess(section.index('Расход неизвестен.'), section.index('Подтверждённая часть'))
        self.assertIn('По данным учёта: .9 USD.', section)
        self.assertIn('Подтверждённая часть расхода: .2 USD.', section)
        self.assertNotIn('Остаток по учтённым расходам', section)
        self.assertIn('data-money="0.01"', section)
        self.assertIn('итог и доступность запроса не гарантированы', section)
        self.assertIn('<small data-model-status class="blocked">Заблокирована</small>', section)
        self.assertEqual(data, before)

    def test_unavailable_and_invalid_explicit_status_never_reassure_with_zero_or_remaining(self):
        for status in ('unknown', 'unavailable', '', 1, {'not': 'a status'}):
            data = rows()
            data[0].update(expense_status=status, spend_usd='0', remaining_usd='10.00',
                           known_subtotal_usd=None)
            data[0]['models'][0].update(expense_status=status, spend_usd='0', blocked=False)
            html = UI.render_editor(data, as_of='owned')
            section = html.split('<tr data-employee-id=', 1)[1].split('<tr data-employee-id=', 1)[0]
            with self.subTest(status=status):
                self.assertIn('data-money="0"', section.split('<td>', 2)[2].split('</td>', 1)[0])
                self.assertIn('Расход неизвестен.' if status == 'unknown' else 'Полнота данных о расходе не подтверждена.', section)
                self.assertEqual('В истории есть запросы без данных о расходе.' in section, status == 'unknown')
                self.assertIn('По данным учёта: 0 USD. Эта сумма не подтверждает итоговый расход.', section)
                self.assertNotIn('Учтённый расход: 0 USD', section)
                self.assertNotIn('Подтверждённая часть расхода', section)
                if status == 'unknown':
                    self.assertNotIn('Остаток по учтённым расходам', section)
                    self.assertIn('data-money="10.00"', section)
                    self.assertIn('итог и доступность запроса не гарантированы', section)
                else:
                    self.assertIn('data-money="10.00"', section)
                    self.assertIn('итог и доступность запроса не гарантированы', section)
                self.assertNotIn('data-model-status', section)

    def test_expense_context_uses_only_owned_strings_and_does_not_derive_dates_or_sums(self):
        data = rows()
        data[0].update(expense_status='unknown', known_subtotal_usd='7.1234567890123456789',
            expense_as_of='caller-completed-time', expense_window_start='caller-start',
            expense_window_end_exclusive='caller-end')
        data[0]['models'][0].update(expense_status='unknown', known_subtotal_usd='.3')
        data[0]['models'][1].update(expense_status='unavailable', known_subtotal_usd='.7')
        section = UI.render_editor(data, as_of='global-header-time').split('<tr data-employee-id=', 1)[1].split('<tr data-employee-id=', 1)[0]
        self.assertIn('Подтверждённая часть расхода: 7.1234567890123456789 USD.', section)
        self.assertIn('Наблюдение на: caller-completed-time.', section)
        self.assertIn('Диапазон наблюдения: с caller-start (включительно) до caller-end (не включается).', section)
        self.assertNotIn('Период:', section)
        self.assertNotIn('global-header-time', section)
        data[0] = rows()[0] | {'expense_status': 'unknown'}
        section = UI.render_editor(data, as_of='global-header-time').split('<tr data-employee-id=', 1)[1].split('<tr data-employee-id=', 1)[0]
        self.assertNotIn('Наблюдение на:', section)
        self.assertNotIn('Период:', section)
        self.assertNotIn('Диапазон наблюдения:', section)

    def test_expense_status_is_readonly_and_does_not_change_budget_actions_or_public_transport(self):
        data = rows()
        data[0].update(expense_status='unknown', known_subtotal_usd='.33', expense_as_of='owned-time',
            expense_window_start='owned-start', expense_window_end_exclusive='owned-end', secret_extra='PRIVATE')
        data[0]['models'][0].update(expense_status='unavailable', known_subtotal_usd=None,
                                   blocked=True, secret_extra='PRIVATE')
        html = UI.render_editor(data, as_of='owned')
        parser = Parser(html)
        baseline = Parser(UI.render_editor(rows(), as_of='owned'))
        controls = lambda parsed: [(tag, attrs) for tag, attrs in parsed.tags if tag in ('input', 'button', 'form')]
        self.assertEqual(controls(parser), controls(baseline))
        self.assertEqual(parser.scripts[-1], baseline.scripts[-1])
        projected = json.loads(parser.scripts[0])
        for key in UI._EXPENSE_FIELDS:
            self.assertEqual(projected[0][key], data[0][key])
        self.assertEqual(projected[0]['models'][0]['expense_status'], 'unavailable')
        self.assertNotIn('blocked', projected[0]['models'][0])
        self.assertNotIn('PRIVATE', html)
        cell = html.split('<td><strong class="unknown"', 1)[1].split('</td>', 1)[0]
        self.assertNotIn('<input', cell)
        self.assertNotIn('<button', cell)
        self.assertEqual(len([attrs for tag, attrs in parser.tags if tag == 'span' and attrs.get('role') == 'status']), 2)

    def test_expense_strings_and_status_cannot_inject_markup_or_client_authority(self):
        data = rows()
        attack = '</script><img src=x onerror="alert(1)"><&\u2028\u2029'
        data[0].update({key: attack for key in UI._EXPENSE_FIELDS})
        data[0]['models'][0].update({key: attack for key in UI._EXPENSE_FIELDS})
        html = UI.render_editor(data, as_of='owned')
        parser = Parser(html)
        self.assertNotIn('img', [tag for tag, attrs in parser.tags])
        self.assertEqual(len(parser.scripts), 2)
        self.assertIn('Полнота данных о расходе не подтверждена.', html)
        self.assertIn('Подтверждённая часть расхода: &lt;/script&gt;', html)
        self.assertEqual(json.loads(parser.scripts[0])[0]['expense_as_of'], attack)
        self.assertNotIn('<', parser.scripts[0])
        self.assertNotIn('\u2028', parser.scripts[0])

    def test_absent_and_none_status_keep_legacy_known_markup(self):
        baseline = UI.render_editor(rows(), as_of='owned')
        self.assertIn('data-money="1.25"', baseline)
        self.assertIn('data-money="8.75"', baseline)
        data = rows()
        data[0].update(expense_status=None, known_subtotal_usd='must-not-replace-legacy')
        data[0]['models'][0].update(expense_status=None, known_subtotal_usd='must-not-replace-legacy')
        html = UI.render_editor(data, as_of='owned')
        self.assertEqual(html.split('<form id="editor">')[1].split('</form>')[0],
                         baseline.split('<form id="editor">')[1].split('</form>')[0])
        self.assertNotIn('<span role="status">', html)

    def test_native_block_tristate_is_readonly_and_does_not_enter_client_data(self):
        data = rows()
        data[0]['models'][0]['blocked'] = True
        data[0]['models'][1]['blocked'] = False
        data[1]['models'][0]['blocked'] = None
        before = copy.deepcopy(data)
        html = UI.render_editor(data, as_of='now')
        self.assertEqual(html.count('data-model-status '), 1)
        self.assertEqual(html.count('<small data-model-status class="blocked">Заблокирована</small>'), 1)
        self.assertNotIn('Не заблокирована', html)
        self.assertIn('data-sort="spend"', html)
        self.assertIn('data-money="1.25"', html)
        self.assertIn('data-money="8.75"', html)
        parser = Parser(html)
        baseline = Parser(UI.render_editor(rows(), as_of='now'))
        self.assertEqual(parser.scripts, baseline.scripts)
        self.assertEqual(json.loads(parser.scripts[0]), rows())
        inputs = [attrs for tag, attrs in parser.tags if tag == 'input' and 'data-model-id' in attrs]
        self.assertEqual(len(inputs), 4)
        self.assertTrue(all('disabled' not in attrs for attrs in inputs))
        self.assertEqual(data, before)

    def test_unexpected_block_value_cannot_inject_markup_or_become_true(self):
        data = rows()
        attack = '</script><img src=x onerror="alert(1)"><&\u2028\u2029'
        data[0]['models'][0].update(blocked=attack, label=attack)
        data[0]['models'][1]['blocked'] = 1
        html = UI.render_editor(data, as_of='now')
        parser = Parser(html)
        self.assertNotIn('img', [tag for tag, _ in parser.tags])
        self.assertNotIn('data-model-status', html)
        self.assertEqual(json.loads(parser.scripts[0])[0]['models'][0]['label'], attack)
        self.assertTrue(all('blocked' not in model for row in json.loads(parser.scripts[0]) for model in row['models']))

    def test_service_summary_is_readonly_escaped_and_excludes_private_fields(self):
        value = {'label': '<script>bad()</script>', 'budget_usd': '20', 'spend_usd': '0.2',
                 'remaining_usd': '19.8', 'budget_reset_at': '2026-12-01T00:00:00Z',
                 'payer_id': 'private-payer-id', 'operator_key': 'private-management-key'}
        rendered = UI.render_editor([], as_of='now', service=value)
        panel = rendered.split('<aside data-service-budget="v1">')[1].split('</aside>')[0]
        self.assertIn('&lt;script&gt;bad()&lt;/script&gt;', panel)
        self.assertIn('data-service-spend><span data-money="0.2"', panel)
        self.assertIn('Расход: <span data-service-spend>', panel)
        self.assertIn('Остаток: <span data-service-remaining>', panel)
        self.assertNotIn('<input', panel)
        self.assertNotIn('<button', panel)
        self.assertNotIn('private-payer-id', rendered)
        self.assertNotIn('private-management-key', rendered)
        unknown = UI.render_editor([], as_of='now', service={'label': 'Titles'})
        self.assertIn('data-service-spend><span data-money="" title="нет данных USD">нет данных</span>', unknown)

    def test_optional_arguments_preserve_existing_output(self):
        self.assertEqual(UI.render_editor(rows(), as_of='now'),
                         UI.render_editor(rows(), as_of='now', template=None, pending=None))

    def test_contract_and_exact_strings(self):
        data = rows()
        data[0]['budget_usd'] = '10.000000000000000001'
        parser = Parser(UI.render_editor(data, as_of='2026-11-02 17:00 UTC'))
        self.assertEqual(json.loads(parser.scripts[0]), data)
        self.assertEqual(len(parser.scripts), 2)
        self.assertIn(('main', {'data-budget-editor': 'v1'}), parser.tags)
        self.assertEqual([a['data-employee-id'] for t, a in parser.tags if t == 'tr' and 'data-employee-id' in a], list(IDS))
        self.assertEqual(len([a for t, a in parser.tags if t == 'input' and 'data-model-id' in a]), 4)
        equal = [attrs for tag, attrs in parser.tags if tag == 'button' and 'data-equal-shares' in attrs]
        self.assertEqual([button['aria-label'] for button in equal], ['Поровну для Employee 1', 'Поровну для Employee 2'])
        self.assertTrue(all(button['type'] == 'button' for button in equal))
        self.assertEqual(len([a for t, a in parser.tags if t == 'option' and a.get('value', '').startswith('group-')]), 2)

    def test_all_untrusted_text_and_script_terminators_are_escaped(self):
        data = rows()
        attack = '</script><img src=x onerror="alert(1)"><&\u2028\u2029'
        for key in ('user_id', 'name', 'email', 'revision', 'budget_usd', 'spend_usd', 'remaining_usd'):
            data[0][key] = attack
        data[0]['groups'] = [{'id': attack, 'name': attack}]
        for key in data[0]['models'][0]:
            data[0]['models'][0][key] = attack
        html = UI.render_editor(data, as_of=attack, status=attack)
        parser = Parser(html)
        self.assertNotIn('img', [tag for tag, _ in parser.tags])
        self.assertEqual(len(parser.scripts), 2)
        self.assertEqual(json.loads(parser.scripts[0]), data)
        self.assertNotIn('<', parser.scripts[0])
        self.assertNotIn('\u2028', parser.scripts[0])
        self.assertIn('&lt;/script&gt;', html)

    def test_unknown_values_are_not_silently_zero_and_extra_fields_never_enter_html(self):
        data = rows()
        for key in ('budget_usd', 'spend_usd', 'remaining_usd'):
            data[0][key] = None
        data[0]['models'][0]['cap_usd'] = None
        data[0]['models'][0]['spend_usd'] = None
        data[0]['secret_extra'] = 'must-never-be-rendered'
        data[0]['models'][0]['secret_extra'] = 'must-never-be-rendered'
        html = UI.render_editor(data, as_of='now')
        self.assertIn('нет данных', html)
        self.assertIn('не установлен', html)
        self.assertNotIn('must-never-be-rendered', html)
        parser = Parser(html)
        self.assertIsNone(json.loads(parser.scripts[0])[0]['spend_usd'])
        self.assertEqual(next(a for t, a in parser.tags if t == 'input' and a.get('id') == 'budget-0')['value'], '')

    def test_empty_state_and_network_boundary(self):
        html = UI.render_editor([], as_of='now', status='Fresh')
        parser = Parser(html)
        self.assertIn('Сотрудники для этого представления не найдены', html)
        self.assertIn(('button', {'type': 'button', 'id': 'apply', 'class': 'primary', 'disabled': None}), parser.tags)
        self.assertIn("default-src 'none'", html)
        self.assertIn("form-action 'none'", html)
        for forbidden in ('fetch(', 'XMLHttpRequest', 'document.cookie', 'parent.document', 'localStorage',
                          'sessionStorage', 'allow-same-origin', 'https://', 'ledger_read_key'):
            self.assertNotIn(forbidden, html)

    def test_bootstrap_panels_project_only_public_data_and_keep_drafts_separate(self):
        defaults, pending = template(), pending_rows()
        defaults['secret_extra'] = 'must-never-be-rendered'
        defaults['shares'][0]['secret_extra'] = 'must-never-be-rendered'
        pending[0]['secret_extra'] = 'must-never-be-rendered'
        pending[0]['models'][0]['secret_extra'] = 'must-never-be-rendered'
        pending[0]['suggested_shares']['secret_extra'] = 'must-never-be-rendered'
        html = UI.render_editor(rows(), as_of='now', template=defaults, pending=pending)
        parser = Parser(html)
        self.assertNotIn('must-never-be-rendered', html)
        self.assertEqual(json.loads(parser.scripts[0]), rows())
        public = json.loads(parser.scripts[1])
        self.assertEqual(public['template'], template())
        self.assertEqual(public['pending'], pending_rows())
        self.assertEqual([a['data-employee-id'] for t, a in parser.tags if t == 'tr' and 'data-employee-id' in a], list(IDS))
        self.assertEqual(len([a for t, a in parser.tags if t == 'input' and 'data-initialize' in a]), 2)
        self.assertFalse(any('checked' in a for t, a in parser.tags if a.get('type') == 'checkbox'))
        self.assertEqual(next(a['value'] for t, a in parser.tags if a.get('id') == 'pending-budget-1'), '')
        self.assertIn('Расход: нет данных', html)
        for forbidden in ('fetch(', 'XMLHttpRequest', 'document.cookie', 'parent.document', 'localStorage',
                          'sessionStorage', 'allow-same-origin', 'https://', 'ledger_admin_key'):
            self.assertNotIn(forbidden, html)

    def test_bootstrap_escaping_and_readonly_states(self):
        defaults, pending = template(), pending_rows()
        attack = '</script><img src=x onerror="alert(1)"><&\u2028\u2029'
        defaults['revision'] = defaults['budget_usd'] = defaults['shares'][0]['label'] = attack
        pending[2]['name'] = pending[2]['code'] = pending[2]['models'][0]['id'] = attack
        parser = Parser(UI.render_editor([], as_of='now', template=defaults, pending=pending[2:]))
        self.assertNotIn('img', [tag for tag, _ in parser.tags])
        self.assertEqual(len(parser.scripts), 3)
        data = json.loads(parser.scripts[1])
        self.assertEqual(data['template']['revision'], attack)
        self.assertEqual(data['pending'][0]['name'], attack)
        self.assertNotIn('<', parser.scripts[1])
        self.assertFalse(any('data-initialize' in a for t, a in parser.tags))
        self.assertIn(('button', {'type': 'button', 'id': 'initialize-budgets', 'disabled': None}), parser.tags)
        empty = UI.render_editor([], as_of='now', pending=[])
        self.assertIn('Неподготовленных бюджетов нет', empty)


@unittest.skipUnless(os.environ.get('RUN_GOAL584_ADMIN_BROWSER') == '1', 'Opt-in local Chrome sandbox rehearsal')
class ChromeSandboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        data = rows()
        data[0]['models'][0]['blocked'] = True
        data[0]['models'][1]['blocked'] = False
        data[1]['models'][0]['blocked'] = None
        cls.editor = UI.render_editor(data, as_of='2026-11-02 17:00 UTC')
        cls.bootstrap_editor = UI.render_editor(rows(), as_of='2026-11-02 17:00 UTC',
                                                template=template(), pending=pending_rows())
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_GET(self):
                data = ('<!doctype html><script>window.received=[];addEventListener("message",e=>{'
                        'if(e.source===document.querySelector("iframe").contentWindow)'
                        'received.push({origin:e.origin,data:e.data});});</script>'
                        '<iframe style="width:100%;height:1000px" sandbox="allow-scripts allow-downloads" srcdoc="'
                        + escape(cls.bootstrap_editor if self.path == '/bootstrap' else cls.editor,
                                 quote=True) + '"></iframe>').encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.playwright = sync_playwright().start()
        try:
            launch = {'headless': True, 'args': ['--disable-background-networking']}
            if os.environ.get('GOAL584_CHROME'):
                launch['executable_path'] = os.environ['GOAL584_CHROME']
            else:
                launch['channel'] = 'chrome'
            cls.browser = cls.playwright.chromium.launch(**launch)
        except Exception:
            cls.playwright.stop()
            cls.server.shutdown()
            cls.server.server_close()
            cls.thread.join(timeout=5)
            raise

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        assert not cls.thread.is_alive(), 'Owned server did not stop'

    def setUp(self):
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.errors, self.external = [], []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        base = f'http://127.0.0.1:{self.server.server_port}'
        self.page.route('**/*', lambda route: route.continue_() if route.request.url.startswith(base + '/')
                        else (self.external.append(route.request.url), route.abort()))
        self.page.goto(base + '/')
        self.frame = self.page.frame_locator('iframe')
        self.frame.locator('main[data-budget-editor="v1"]').wait_for()

    def tearDown(self):
        try:
            self.assertEqual(self.errors, [])
            self.assertEqual(self.external, [])
        finally:
            self.context.close()

    def prompts(self):
        return self.page.evaluate("received.filter(x=>x.data.type==='input:prompt:submit')")

    def test_group_filter_matches_each_membership_and_ungrouped(self):
        data = rows()
        data[0]['groups'].extend(data[1]['groups'])
        data[1]['groups'] = []
        self.page.locator('iframe').evaluate('(el, html) => el.srcdoc=html', UI.render_editor(data, as_of='now'))
        self.frame.locator('#group').wait_for()
        for group in ('group-1', 'group-2'):
            self.frame.locator('#group').select_option(group)
            self.assertEqual(self.frame.locator('tr[data-employee-id]:visible').get_attribute('data-employee-id'), IDS[0])
        self.frame.locator('#group').select_option('__ungrouped__')
        self.assertEqual(self.frame.locator('tr[data-employee-id]:visible').get_attribute('data-employee-id'), IDS[1])
        self.frame.locator('#group').select_option('')
        self.assertEqual(self.frame.locator('tr[data-employee-id]:visible').count(), 2)
        self.assertEqual(self.prompts(), [])

    def open_bootstrap(self):
        self.page.goto(f'http://127.0.0.1:{self.server.server_port}/bootstrap')
        self.frame.locator('.optional').first.evaluate('el=>el.open=true')
        self.frame.locator('#template-editor').wait_for()

    def employee_editor(self, index=0):
        row = self.employee_row(index)
        if row.locator('.expand-editor').get_attribute('aria-expanded') != 'true':
            row.locator('.expand-editor').click()
        return self.frame.locator(f'[data-editor-index="{row.get_attribute("data-index")}"]')

    def employee_row(self, index=0):
        return self.frame.locator('tr[data-employee-id]').nth(index)

    def review_plan(self):
        review = self.frame.locator('#plan-review')
        if review.get_attribute('open') is None:
            review.locator('summary').click()
        return self.frame.locator('#preview')

    def load_overview(self, data=None, supplied=None, **kwargs):
        html = UI.render_editor(data if data is not None else rows(), as_of='2026-11-11T13:00:00Z',
                                overview=supplied if supplied is not None else overview(), **kwargs)
        self.page.locator('iframe').evaluate('(el,html)=>el.srcdoc=html', html)
        self.frame.locator('.account-refusal').wait_for()
        return html

    def test_overview_disclosures_keep_drafts_and_only_show_financial_refusal(self):
        data = rows()
        data[0]['models'][0].update(remaining_usd='4.750000000000000001', new=True)
        self.load_overview(data)
        budget = self.frame.locator('[data-field="budget_usd"]').first
        budget.fill('20.000000000000000001')
        self.frame.locator('.legend-price>summary').first.click()
        employee = self.employee_editor()
        employee.locator('.model-stats>summary').first.click()
        self.assertIn('4,75', employee.inner_text())
        self.assertEqual(employee.locator('[data-money="4.750000000000000001"]').get_attribute('title'),
                         '4.750000000000000001 USD')
        self.assertEqual(self.frame.locator('.account-refusal').count(), 1)
        self.assertIn('Наблюдение:', self.frame.locator('.account-refusal').inner_text())
        self.assertEqual(self.frame.locator('[data-balance-field],#budget-account-data').count(), 0)
        self.assertEqual(self.frame.locator('.legend-price [data-money]').first.get_attribute('title'),
                         '0.1234567890123456789 USD')
        self.assertEqual(budget.input_value(), '20.000000000000000001')
        self.assertEqual(self.prompts(), [])

    def test_overview_820px_compact_rows_sticky_header_and_unknown_state(self):
        data = []
        for i in range(12):
            row = copy.deepcopy(rows()[i % 2])
            row.update(user_id='preview-' + str(i), name='Сотрудник ' + str(i + 1))
            row['models'].append({'id': 'model-c', 'label': 'Model C', 'cap_usd': '0',
                                  'spend_usd': '0', 'remaining_usd': '0', 'share_percent': '0', 'new': True})
            data.append(row)
        supplied = overview()
        supplied['prices'].append({'id': 'model-c', 'label': 'Model C', 'input_per_million': '0',
            'output_per_million': '0', 'cache_per_million': None, 'as_of': None,
            'source': 'cached-provider-price', 'changed': False})
        html = self.load_overview(data, supplied)
        self.page.set_viewport_size({'width': 820, 'height': 900})
        self.assertIn('нет данных', self.frame.locator('.legend-price').nth(1).inner_text())
        self.assertEqual(self.frame.locator('.account-refusal').count(), 1)
        heights = self.frame.locator('tr[data-employee-id]').evaluate_all(
            '(rows)=>rows.map(row=>row.getBoundingClientRect().height)')
        self.assertTrue(all(40 <= height <= 65 for height in heights), heights)
        legend = self.frame.locator('.legend').evaluate(
            'el=>({width:el.clientWidth,scrollWidth:el.scrollWidth,height:el.clientHeight,scrollHeight:el.scrollHeight})')
        self.assertEqual(legend['height'], legend['scrollHeight'])
        self.assertEqual(legend['width'], legend['scrollWidth'])
        metrics = self.frame.locator('.table-scroll').evaluate(
            'el=>({width:el.clientWidth,scrollWidth:el.scrollWidth,top:el.getBoundingClientRect().top})')
        self.assertEqual(metrics['width'], metrics['scrollWidth'])
        self.assertLess(self.frame.locator('thead').evaluate('el=>el.getBoundingClientRect().height'), 220)
        out = Path(os.environ['GOAL584_ADMIN_UI_EVIDENCE']) if os.environ.get('GOAL584_ADMIN_UI_EVIDENCE') else None
        if out:
            out.mkdir(parents=True, exist_ok=True)
            (out / 'overview-12-820.html').write_text(html, encoding='utf-8')
            self.page.screenshot(path=str(out / 'overview-12-820.png'), full_page=True)
        self.frame.locator('.table-scroll').evaluate('el=>el.scrollTop=240')
        self.assertAlmostEqual(self.frame.locator('thead').evaluate('el=>el.getBoundingClientRect().top'),
                               metrics['top'] + 1, delta=1)
        if out:
            self.page.screenshot(path=str(out / 'overview-12-820-scrolled.png'), full_page=True)
        self.frame.locator('.table-scroll').evaluate('el=>el.scrollTop=0')
        self.assertEqual(self.prompts(), [])

    def test_template_exact_validation_preview_and_separate_native_payload(self):
        self.open_bootstrap()
        self.assertEqual(self.prompts(), [])
        self.frame.locator('#save-template').click()
        self.assertIn('Нет изменений', self.frame.locator('#template-feedback').inner_text())
        self.frame.locator('#template-budget').fill('0.800000000000000001')
        self.frame.locator('[data-template-model="model-a"]').fill('33.3333333333333333')
        self.frame.locator('[data-template-model="model-b"]').fill('66.6666666666666666')
        self.frame.locator('#save-template').click()
        self.assertIn('суммой 100%', self.frame.locator('#template-feedback').inner_text())
        self.assertEqual(self.prompts(), [])
        self.frame.locator('[data-template-model="model-b"]').fill('66.6666666666666667')
        self.frame.locator('#save-template').click()
        self.page.wait_for_function("received.some(x=>x.data.type==='input:prompt:submit')")
        received = self.prompts()
        self.assertEqual(received[0]['origin'], 'null')
        self.assertEqual(json.loads(received[0]['data']['text']), {
            'schema': 1, 'type': 'employee_budget_template', 'expected_revision': 'template-revision',
            'budget_usd': '0.800000000000000001', 'budget_duration': '1mo',
            'shares': {'model-a': '33.3333333333333333', 'model-b': '66.6666666666666667'}})
        self.assertIn('0.80 → 0.800000000000000001 USD', self.frame.locator('#template-preview').inner_text())
        self.assertIn('100 → 33.3333333333333333%', self.frame.locator('#template-preview').inner_text())
        self.assertTrue(self.frame.locator('#save-template').is_disabled())
        self.assertIn('ещё не сохранён', self.frame.locator('#template-feedback').inner_text())

    def test_pending_only_explicit_selected_rows_and_no_automatic_normalization(self):
        self.open_bootstrap()
        self.frame.locator('#initialize-budgets').click()
        self.assertIn('Выберите сотрудников', self.frame.locator('#pending-feedback').inner_text())
        first = self.frame.locator('article[data-pending-index="0"]')
        second = self.frame.locator('article[data-pending-index="1"]')
        second.locator('[data-pending-budget]').fill('1e3')  # Invalid unselected row must not be submitted.
        first.locator('input[type="checkbox"]').check()
        first.locator('[data-pending-budget]').fill('20.000000000000000001')
        first.locator('[data-pending-model="model-a"]').fill('99.999999999999999999')
        self.assertEqual(self.prompts(), [])
        self.frame.locator('#initialize-budgets').click()
        self.assertIn('суммой 100%', self.frame.locator('#pending-feedback').inner_text())
        self.assertEqual(self.prompts(), [])
        first.locator('[data-pending-model="model-a"]').fill('33.3333333333333333')
        first.locator('[data-pending-model="model-b"]').fill('66.6666666666666667')
        self.frame.locator('#initialize-budgets').click()
        self.page.wait_for_function("received.some(x=>x.data.type==='input:prompt:submit')")
        self.assertEqual(json.loads(self.prompts()[0]['data']['text']), {
            'schema': 1, 'type': 'employee_budget_initialize', 'changes': [{
                'user_id': 'pending-0', 'expected_revision': 'pending-revision-0',
                'budget_usd': '20.000000000000000001',
                'shares': {'model-a': '33.3333333333333333', 'model-b': '66.6666666666666667'}}]})
        self.assertTrue(self.frame.locator('#initialize-budgets').is_disabled())
        self.assertIn('бюджет не создан → 20.000000000000000001 USD',
                      self.frame.locator('#pending-preview').inner_text())
        self.assertIn('ещё не созданы', self.frame.locator('#pending-feedback').inner_text())

    def test_bootstrap_and_existing_employee_forms_do_not_mix_drafts(self):
        self.open_bootstrap()
        self.frame.locator('#template-budget').fill('999')
        first = self.frame.locator('article[data-pending-index="0"]')
        first.locator('input[type="checkbox"]').check()
        self.assertTrue(self.frame.locator('#apply').is_disabled())
        self.assertEqual(self.prompts(), [])
        self.frame.locator('#editor [data-field="budget_usd"]').first.fill('20')
        self.frame.locator('#apply').click()
        self.page.wait_for_function("received.some(x=>x.data.type==='input:prompt:submit')")
        self.assertEqual(json.loads(self.prompts()[0]['data']['text']), {
            'schema': 1, 'type': 'employee_budget_plan', 'changes': [{
                'user_id': IDS[0], 'expected_revision': 'revision-1', 'budget_usd': '20',
                'shares': {'model-a': '50.00', 'model-b': '50.00'}}]})
        self.frame.locator('#initialize-budgets').click()
        self.page.wait_for_function("received.filter(x=>x.data.type==='input:prompt:submit').length===2")
        self.assertEqual(json.loads(self.prompts()[1]['data']['text'])['type'], 'employee_budget_initialize')
        self.assertFalse(self.frame.locator('#save-template').is_disabled())

    def test_missing_suggestions_stay_empty_and_conflicts_have_no_action(self):
        self.open_bootstrap()
        missing = self.frame.locator('article[data-pending-index="1"]')
        self.assertEqual(missing.locator('[data-pending-budget]').input_value(), '')
        self.assertEqual(missing.locator('[data-pending-model="model-a"]').input_value(), '')
        self.assertIn('Расход: нет данных', missing.inner_text())
        missing.locator('input[type="checkbox"]').check()
        self.frame.locator('#initialize-budgets').click()
        self.assertIn('десятичной строкой', self.frame.locator('#pending-feedback').inner_text())
        self.assertEqual(self.prompts(), [])
        for index in (2, 3):
            readonly = self.frame.locator(f'article[data-pending-index="{index}"]')
            self.assertEqual(readonly.locator('input,button').count(), 0)
            self.assertIn('требуется проверка', readonly.inner_text())

    def test_block_states_are_readonly_in_the_personal_model_table(self):
        self.assertEqual(self.frame.locator('thead [data-sort="spend"]').count(), 1)
        self.employee_editor(0)
        self.employee_editor(1)
        statuses = self.frame.locator('[data-model-status]')
        self.assertEqual(statuses.count(), 1)
        statuses.first.locator('..').locator('summary').click()
        self.assertEqual(statuses.first.inner_text(), 'Заблокирована')
        self.assertEqual(statuses.first.locator('input,button').count(), 0)
        self.assertEqual(self.prompts(), [])

    def test_changed_rows_precision_and_two_employee_submission(self):
        first = self.employee_editor(0)
        self.employee_row(0).locator('[data-field="budget_usd"]').fill('20.000000000000000001')
        first.locator('[data-model-id="model-a"]').fill('33.3333333333333333')
        first.locator('[data-model-id="model-b"]').fill('66.6666666666666667')
        self.frame.get_by_role('button', name='Применить изменения', exact=True).click()
        self.page.wait_for_function("received.some(x=>x.data.type==='input:prompt:submit')")
        messages = self.prompts()
        self.assertEqual(messages[0]['origin'], 'null')
        plan = json.loads(messages[0]['data']['text'])
        expected = {'user_id': IDS[0], 'expected_revision': 'revision-1', 'budget_usd': '20.000000000000000001',
                    'shares': {'model-a': '33.3333333333333333', 'model-b': '66.6666666666666667'}}
        self.assertEqual(plan, {'schema': 1, 'type': 'employee_budget_plan', 'changes': [expected]})
        self.assertIn('10.00 → 20.000000000000000001 USD', self.review_plan().inner_text())
        self.assertTrue(self.frame.locator('#apply').is_disabled())
        second = self.employee_editor(1)
        self.employee_row(1).locator('[data-field="budget_usd"]').fill('40.000')
        self.frame.get_by_role('button', name='Применить изменения', exact=True).click()
        self.page.wait_for_function("received.filter(x=>x.data.type==='input:prompt:submit').length===2")
        second_plan = json.loads(self.prompts()[1]['data']['text'])
        self.assertEqual(second_plan['changes'], [expected, {'user_id': IDS[1], 'expected_revision': 'revision-2',
                         'budget_usd': '40.000', 'shares': {'model-a': '50.00', 'model-b': '50.00'}}])
        self.assertTrue(self.page.evaluate("received.some(x=>x.data.type==='iframe:height'&&x.data.height>0)"))

    def test_invalid_and_unchanged_values_do_not_submit(self):
        self.assertTrue(self.frame.locator('#apply').is_disabled())
        first = self.employee_editor(0)
        self.employee_row(0).locator('[data-field="budget_usd"]').fill('20')
        first.locator('[data-model-id="model-a"]').fill('49.')
        self.frame.get_by_role('button', name='Применить изменения', exact=True).click()
        self.assertIn('суммой 100%', self.frame.locator('#feedback').inner_text())
        first.locator('[data-model-id="model-a"]').fill('50.00')
        self.employee_row(0).locator('[data-field="budget_usd"]').fill('1e3')
        self.frame.get_by_role('button', name='Применить изменения', exact=True).click()
        self.assertIn('десятичной строкой', self.frame.locator('#feedback').inner_text())
        self.assertEqual(self.prompts(), [])

    def test_local_filters_sort_slider_and_reset_preserve_exact_drafts_without_prompts(self):
        first = self.employee_editor(0)
        row = self.employee_row(0)
        row.locator('[data-field="budget_usd"]').fill('20.000000000000000001')
        self.assertEqual(row.locator('.allocation-bar input').count(), 0)
        self.assertEqual(first.locator('[data-share-slider]').count(), 2)
        first.locator('[data-share-slider]').first.press('Home')
        first.locator('[data-share-slider]').first.press('ArrowRight')
        self.assertEqual(first.locator('[data-model-id="model-a"]').input_value(), '1')
        self.assertEqual(first.locator('[data-model-id="model-b"]').input_value(), '99')
        first.locator('[data-share-slider]').first.evaluate("el=>{el.value='35';el.dispatchEvent(new Event('input',{bubbles:true}))}")
        self.assertEqual(first.locator('[data-model-id="model-a"]').input_value(), '35')
        self.assertEqual(first.locator('[data-model-id="model-b"]').input_value(), '65')
        self.assertEqual(Decimal(first.locator('[data-allocation="0"]').get_attribute('title').removesuffix(' USD')), Decimal('7.00000000000000000035'))
        self.assertIn('50.00 → 35%', self.review_plan().inner_text())
        self.frame.locator('#search').fill('user2@')
        self.assertFalse(first.is_visible())
        self.frame.locator('[data-sort="remaining"]').click()
        self.frame.locator('#search').fill('')
        self.frame.locator('#group').select_option('group-2')
        self.assertFalse(first.is_visible())
        self.frame.locator('#group').select_option('')
        self.frame.locator('#only-changed').check()
        self.assertEqual(self.frame.locator('tr[data-employee-id]:visible').count(), 1)
        self.assertEqual(row.locator('[data-field="budget_usd"]').input_value(), '20.000000000000000001')
        self.assertEqual(row.locator('xpath=following-sibling::*[1]').get_attribute('data-editor-index'), row.get_attribute('data-index'))
        self.assertIn('Изменено: 1', self.frame.locator('#changed-count').inner_text())
        self.assertEqual(self.prompts(), [])
        self.frame.locator('#reset-drafts').click()
        self.assertTrue(self.frame.locator('#apply').is_disabled())
        self.assertTrue(self.frame.locator('#empty-result').is_visible())
        self.frame.locator('#only-changed').uncheck()
        self.assertEqual(row.locator('[data-field="budget_usd"]').input_value(), '10.00')
        self.assertEqual(first.locator('[data-model-id="model-a"]').input_value(), '50.00')
        self.assertTrue(self.frame.locator('#plan-review').is_hidden())
        self.assertEqual(self.prompts(), [])

    def test_proportional_shares_preserve_zeros_and_nine_model_explicit_equal_action(self):
        data = rows()
        data[0]['remaining_usd'] = '-0.000000000001'
        data[1]['remaining_usd'] = '0.000000000001'
        data[0].update(expense_status='unavailable', spend_usd='0.1')
        data[1].update(expense_status='unknown', spend_usd='2')
        data[0]['models'][0]['share_percent'] = '50'
        data[0]['models'][1]['share_percent'] = '30'
        data[0]['models'].extend({'id': f'model-{i}', 'label': f'Model {i}', 'cap_usd': None,
                                 'spend_usd': None, 'share_percent': '20' if i == 2 else '0'}
                                for i in range(2, 9))
        html = UI.render_editor(data, as_of='owned')
        self.page.locator('iframe').evaluate('(el,html)=>el.srcdoc=html', html)
        self.frame.locator('#employee-table').wait_for()
        out = Path(os.environ['GOAL584_ADMIN_UI_EVIDENCE']) if os.environ.get('GOAL584_ADMIN_UI_EVIDENCE') else None
        if out:
            out.mkdir(parents=True, exist_ok=True)
            (out / 'nine-models.html').write_text(html, encoding='utf-8')
            self.page.screenshot(path=str(out / 'nine-models-normal.png'), full_page=True)
        row = self.employee_row(0)
        row.locator('.allocation-bar').press('Enter')
        self.assertEqual(row.locator('.expand-editor').get_attribute('aria-expanded'), 'true')
        first = self.employee_editor(0)
        second = self.frame.locator(f'tr[data-employee-id="{IDS[1]}"]')
        self.assertAlmostEqual(first.bounding_box()['width'], row.bounding_box()['width'], delta=1)
        self.assertEqual(first.locator('[data-share-slider]').count(), 9)
        if out:
            self.page.screenshot(path=str(out / 'nine-models-expanded.png'), full_page=True)
        shares = lambda: first.locator('input[data-model-id]').evaluate_all('els=>els.map(el=>el.value)')
        handles = first.locator('[data-share-slider]')
        first.locator('[data-model-id="model-a"]').fill('40')
        self.assertEqual(shares(), ['40', '36', '24'] + ['0'] * 6)
        if out:
            self.page.screenshot(path=str(out / 'nine-models-redistributed.png'), full_page=True)
        # One drag keeps its original proportions, including a return to its starting point.
        handles.first.dispatch_event('pointerdown')
        for candidate in ('25', '40'):
            handles.first.evaluate('(el,value)=>{el.value=value;el.dispatchEvent(new Event("input",{bubbles:true}))}', candidate)
        self.assertEqual(shares(), ['40', '36', '24'] + ['0'] * 6)
        handles.first.dispatch_event('pointerup')
        handles.first.press('End')
        self.assertEqual(shares(), ['100', '0', '0'] + ['0'] * 6)
        handles.first.press('ArrowLeft')
        self.assertEqual(shares(), ['100', '0', '0'] + ['0'] * 6)
        self.assertIn('Сначала задайте долю другой модели', first.locator('[data-share-feedback]').inner_text())
        first.locator('[data-model-id="model-b"]').fill('20')
        self.assertEqual(shares(), ['80', '20', '0'] + ['0'] * 6)
        first.locator('[data-equal-shares]').click()
        equal = shares()
        self.assertEqual(len(equal), 9)
        self.assertTrue(all(Decimal(value) > 0 for value in equal))
        self.assertEqual(sum(map(Decimal, equal)), Decimal(100))
        first.locator('[data-model-id="model-a"]').fill('12.')
        self.frame.locator('#apply').click()
        self.assertIn('суммой 100%', self.frame.locator('#feedback').inner_text())
        self.assertEqual(self.prompts(), [])
        first.locator('[data-model-id="model-a"]').fill('12')
        self.assertEqual(sum(map(Decimal, shares())), Decimal(100))
        self.frame.locator('#remaining-filter').select_option('exhausted')
        self.assertTrue(first.is_visible())
        self.assertFalse(second.is_visible())
        self.frame.locator('#remaining-filter').select_option('low')
        self.assertFalse(first.is_visible())
        self.assertTrue(second.is_visible())
        self.assertIn('< 0,00000001', second.locator('[data-money="0.000000000001"]').inner_text())
        self.assertEqual(second.locator('[data-money="0.000000000001"]').get_attribute('title'), '0.000000000001 USD')
        self.frame.locator('#remaining-filter').select_option('all')
        self.frame.locator('[data-sort="spend"]').click()
        self.assertEqual(self.frame.locator('#employee-rows>tr').first.get_attribute('data-employee-id'), IDS[1])
        self.frame.locator('[data-sort="remaining"]').click()
        self.assertEqual(self.frame.locator('#employee-rows>tr').first.get_attribute('data-employee-id'), IDS[0])
        self.assertEqual(self.frame.locator('#employee-rows>tr').nth(1).get_attribute('data-editor-index'), '0')
        self.assertEqual(self.prompts(), [])

    def test_refresh_prompt_and_reload_discards_drafts(self):
        self.frame.locator('[data-field="budget_usd"]').first.fill('999')
        self.frame.get_by_role('button', name='Обновить данные', exact=True).click()
        self.assertEqual(self.prompts(), [])
        self.assertIn('несохранённые правки', self.frame.locator('#feedback').inner_text())
        self.frame.locator('#reset-drafts').click()
        self.frame.locator('#refresh').click()
        self.page.wait_for_function("received.some(x=>x.data.type==='input:prompt:submit')")
        self.assertEqual(self.prompts()[0]['data']['text'], 'Обнови управление бюджетами')
        self.page.reload()
        self.assertEqual(self.frame.locator('[data-field="budget_usd"]').first.input_value(), '10.00')
        frame = self.page.frames[1]
        self.assertTrue(frame.evaluate("(()=>{try{return parent.document.body===null}catch(e){return e.name==='SecurityError'}})()"))
        self.assertTrue(frame.evaluate("(()=>{try{document.cookie;return false}catch(e){return e.name==='SecurityError'}})()"))


if __name__ == '__main__':
    unittest.main()
