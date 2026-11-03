"""Renderer contract plus opt-in real Chrome sandbox transport rehearsal."""
from html import escape
from html.parser import HTMLParser
import importlib.util
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
             'department': 'Department ' + str(i + 1), 'revision': 'revision-' + str(i + 1),
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
        self.assertEqual([a['data-employee-id'] for t, a in parser.tags if t == 'section'], list(IDS))
        self.assertEqual(len([a for t, a in parser.tags if t == 'input' and 'data-model-id' in a]), 4)
        self.assertEqual(len([a for t, a in parser.tags if t == 'h2' and 'data-department' in a]), 2)

    def test_all_untrusted_text_and_script_terminators_are_escaped(self):
        data = rows()
        attack = '</script><img src=x onerror="alert(1)"><&\u2028\u2029'
        for key in ('user_id', 'name', 'email', 'department', 'revision', 'budget_usd', 'spend_usd', 'remaining_usd'):
            data[0][key] = attack
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
        self.assertIn(('button', {'type': 'button', 'id': 'apply', 'disabled': None}), parser.tags)
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
        self.assertEqual([a['data-employee-id'] for t, a in parser.tags if t == 'section'], list(IDS))
        self.assertEqual(len([a for t, a in parser.tags if t == 'input' and a.get('type') == 'checkbox']), 2)
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
        self.assertFalse(any(a.get('type') == 'checkbox' for t, a in parser.tags))
        self.assertIn(('button', {'type': 'button', 'id': 'initialize-budgets', 'disabled': None}), parser.tags)
        empty = UI.render_editor([], as_of='now', pending=[])
        self.assertIn('Неподготовленных бюджетов нет', empty)


@unittest.skipUnless(os.environ.get('RUN_GOAL584_ADMIN_BROWSER') == '1', 'Opt-in local Chrome sandbox rehearsal')
class ChromeSandboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.editor = UI.render_editor(rows(), as_of='2026-11-02 17:00 UTC')
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

    def open_bootstrap(self):
        self.page.goto(f'http://127.0.0.1:{self.server.server_port}/bootstrap')
        self.frame.locator('#template-editor').wait_for()

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
        self.frame.locator('#apply').click()
        self.assertIn('Нет изменений', self.frame.locator('#feedback').inner_text())
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

    def test_changed_rows_precision_and_two_employee_submission(self):
        first = self.frame.locator('section').nth(0)
        first.locator('[data-field="budget_usd"]').fill('20.000000000000000001')
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
        self.assertIn('10.00 → 20.000000000000000001 USD', self.frame.locator('#preview').inner_text())
        self.assertTrue(self.frame.locator('#apply').is_disabled())
        second = self.frame.locator('section').nth(1)
        second.locator('[data-field="budget_usd"]').fill('40.000')
        self.frame.get_by_role('button', name='Применить изменения', exact=True).click()
        self.page.wait_for_function("received.filter(x=>x.data.type==='input:prompt:submit').length===2")
        second_plan = json.loads(self.prompts()[1]['data']['text'])
        self.assertEqual(second_plan['changes'], [expected, {'user_id': IDS[1], 'expected_revision': 'revision-2',
                         'budget_usd': '40.000', 'shares': {'model-a': '50.00', 'model-b': '50.00'}}])
        self.assertTrue(self.page.evaluate("received.some(x=>x.data.type==='iframe:height'&&x.data.height>0)"))

    def test_invalid_and_unchanged_values_do_not_submit(self):
        self.frame.get_by_role('button', name='Применить изменения', exact=True).click()
        self.assertIn('Нет изменений', self.frame.locator('#feedback').inner_text())
        first = self.frame.locator('section').nth(0)
        first.locator('[data-field="budget_usd"]').fill('20')
        first.locator('[data-model-id="model-a"]').fill('49.999999999999999999')
        self.frame.get_by_role('button', name='Применить изменения', exact=True).click()
        self.assertIn('суммой 100%', self.frame.locator('#feedback').inner_text())
        first.locator('[data-model-id="model-a"]').fill('50.00')
        first.locator('[data-field="budget_usd"]').fill('1e3')
        self.frame.get_by_role('button', name='Применить изменения', exact=True).click()
        self.assertIn('десятичной строкой', self.frame.locator('#feedback').inner_text())
        self.assertEqual(self.prompts(), [])

    def test_refresh_prompt_and_reload_discards_drafts(self):
        self.frame.locator('[data-field="budget_usd"]').first.fill('999')
        self.frame.get_by_role('button', name='Обновить данные', exact=True).click()
        self.page.wait_for_function("received.some(x=>x.data.type==='input:prompt:submit')")
        self.assertEqual(self.prompts()[0]['data']['text'], 'Обнови управление бюджетами')
        self.page.reload()
        self.assertEqual(self.frame.locator('[data-field="budget_usd"]').first.input_value(), '10.00')
        frame = self.page.frames[1]
        self.assertTrue(frame.evaluate("(()=>{try{return parent.document.body===null}catch(e){return e.name==='SecurityError'}})()"))
        self.assertTrue(frame.evaluate("(()=>{try{document.cookie;return false}catch(e){return e.name==='SecurityError'}})()"))


if __name__ == '__main__':
    unittest.main()
