"""Host/IO rehearsal; no real browser, Docker, inference, or Office acceptance.

The real strict-six/running/private owners and emitted inspection Python run.
Only Docker/Git/CLI, browser transport/DOM assertions, and Windows permission
observations are doubled. No replacement Tool/model loop exists in this test.
"""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prove_office_browser as B
import prove_gateway_auth as private_owner
import prove_webui_browser as login_owner
import office_fixture as fixture_owner
from test_office_fixture import BASE, SECRET, ReadbackWorld

ACTOR, OTHER, ADMIN, CHAT, USER, ANSWER, FILE = [f'{i:08x}-1111-4111-8111-111111111111' for i in range(1, 8)]


class Response:
    def __init__(self, value=None, status=200, body=b'', url='', request=None):
        self.value, self.status, self.raw, self.url, self.request = value, status, body, url, request
    def json(self): return copy.deepcopy(self.value)
    def body(self): return self.raw


class Pending:
    def __init__(self, page, kind, predicate=None): self.page, self.kind, self.predicate = page, kind, predicate
    def __enter__(self): self.page.pending = self; return self
    def __exit__(self, *error):
        if not error[0] and self.predicate: assert self.predicate(self.value)


class Locator:
    def __init__(self, page, selector): self.page, self.selector = page, selector
    @property
    def first(self): return self
    def locator(self, selector): return Locator(self.page, selector)
    def fill(self, value): self.page.fields[self.selector] = value
    def click(self):
        w = self.page.world
        if self.selector == 'form button[type="submit"]':
            assert self.page.fields['#email'] == self.page.account['email']
            assert self.page.fields['#password'] == self.page.account['password']
            request = SimpleNamespace(method='POST')
            self.page.pending.value = Response(self.page.account | {'role': w.login_role}, url=BASE + '/api/v1/auths/signin', request=request)
        elif self.selector == '#send-message-button':
            assert self.page.fields['#chat-input'] == B.USER_REQUEST
            w.sends += 1
            w.sent = {'model': B.MODEL, 'chat_id': CHAT, 'id': ANSWER,
                'user_message': {'id': USER, 'role': 'user', 'content': B.USER_REQUEST, 'parentId': w.source_id},
                'messages': [copy.deepcopy(w.form['chat']['messages'][0])], 'params': {},
                'background_tasks': {'follow_up_generation': True}}
            if w.submit_mutation: w.submit_mutation(w.sent)
            self.page.pending.value = Response({'chat_id': CHAT}, status=w.ack_status,
                url=BASE + '/api/chat/completions', request=SimpleNamespace(method='POST', post_data_json=w.sent))
        elif self.selector.startswith('a[href='):
            assert self.selector == 'a[href="/api/v1/files/' + FILE + '/content"]'
            w.download_clicks += 1
            self.page.pending.value = SimpleNamespace(url=w.download_url, suggested_filename=w.download_name,
                failure=lambda: w.download_failure, save_as=lambda p: Path(p).write_bytes(w.download_bytes))
        else: raise AssertionError('Unexpected browser click')


class Expect:
    def __init__(self, locator): self.locator = locator
    def to_be_visible(self, **kwargs): pass
    def to_have_attribute(self, name, value):
        assert name == 'aria-label' and value == 'Selected model: ' + B.MODEL
    def to_contain_text(self, value, **kwargs):
        assert value == B.COST and value in self.locator.page.world.answer()['statusHistory'][0]['description']


class Page:
    def __init__(self, context):
        self.context, self.world, self.account, self.fields = context, context.world, context.account, {}
    def set_default_timeout(self, timeout): assert timeout == 30_000
    def goto(self, url, **kwargs):
        assert url in (BASE + '/auth', BASE + '/c/' + CHAT)
    def locator(self, selector): return Locator(self, selector)
    def expect_response(self, predicate, **kwargs): return Pending(self, 'response', predicate)
    def expect_download(self, **kwargs): return Pending(self, 'download')
    def wait_for_timeout(self, timeout): assert timeout == 250
    def screenshot(self, path, **kwargs): Path(path).write_bytes(b'PNG-private-browser-evidence')


class Context:
    def __init__(self, world, account): self.world, self.account, self.request, self.closed = world, account, self, False
    def new_page(self): return Page(self)
    def close(self): self.closed = True
    def post(self, url, *, headers, data, timeout):
        w = self.world
        assert url == BASE + '/api/v1/chats/new' and headers == {'Authorization': 'Bearer actor-token'}
        assert timeout == 10_000
        w.form = copy.deepcopy(data); w.source_id = data['chat']['history']['currentId']
        assert set(data) == {'chat', 'folder_id'} and data['folder_id'] is None
        assert data['chat']['models'] == [B.MODEL] and data['chat']['params'] == {}
        assert len(data['chat']['messages']) == 2 and data['chat']['messages'][0]['role'] == 'user'
        assert data['chat']['messages'][1]['content'] == B.SOURCE
        result = {'id': CHAT, 'user_id': ACTOR, 'chat': copy.deepcopy(data['chat'])}
        if w.seed_mutation: w.seed_mutation(result)
        return Response(result)
    def get(self, url, *, headers, timeout):
        w = self.world; foreign = self.account['id'] == OTHER
        assert headers == {'Authorization': 'Bearer ' + self.account['token']}
        if foreign:
            assert url in (BASE + '/api/v1/files/' + FILE, BASE + '/api/v1/files/' + FILE + '/content')
            w.foreign_reads.append(url)
            return Response(status=w.foreign_status)
        if url == BASE + '/api/v1/chats/' + CHAT:
            w.reads += 1
            chat = copy.deepcopy(w.form['chat']); messages = chat['history']['messages']
            if w.reads > 1:
                messages[USER] = copy.deepcopy(w.sent['user_message']); messages[ANSWER] = w.answer()
                chat['history']['currentId'] = ANSWER
            result = {'id': CHAT, 'user_id': ACTOR, 'chat': chat}
            if w.saved_mutation: w.saved_mutation(result)
            return Response(result)
        if url == BASE + '/api/tasks/chat/' + CHAT:
            return Response({'task_ids': ['still-active'] if w.active_tasks else []})
        if url == BASE + '/api/v1/files/' + FILE:
            result = {'id': FILE, 'user_id': ACTOR, 'filename': B.OUTPUT_NAME,
                'meta': {'name': B.OUTPUT_NAME, 'content_type': B.DOCX, 'size': len(w.native_bytes)}}
            if w.file_mutation: w.file_mutation(result)
            return Response(result)
        if url == BASE + '/api/v1/files/' + FILE + '/content': return Response(body=w.native_bytes)
        raise AssertionError('Unexpected browser transport')


class Browser:
    def __init__(self, fixture):
        self.fixture, self.contexts = fixture, []
        self.actor = {'id': ACTOR, 'email': 'office@example.invalid', 'password': SECRET, 'token': 'actor-token'}
        self.other = {'id': OTHER, 'email': 'other@example.invalid', 'password': SECRET, 'token': 'other-token'}
        self.sends = self.reads = self.download_clicks = 0
        self.foreign_reads = []
        self.submit_mutation = self.saved_mutation = self.seed_mutation = self.file_mutation = None
        self.ack_status, self.foreign_status, self.active_tasks = 200, 404, False
        self.login_role = 'user'
        self.followups = ['Create an Excel version of the table.']
        self.download_failure, self.download_name = None, B.OUTPUT_NAME
        self.download_url = BASE + '/api/v1/files/' + FILE + '/content'
        buffer = io.BytesIO()
        with ZipFile(buffer, 'w') as docx: docx.writestr('word/document.xml', '<document>synthetic IO bytes only</document>')
        self.native_bytes = self.download_bytes = buffer.getvalue()
    def new_context(self, **kwargs):
        assert kwargs == {'locale': 'en-US', 'viewport': {'width': 1440, 'height': 1000}}
        context = Context(self, self.actor if not self.contexts else self.other)
        self.contexts.append(context); return context
    def answer(self):
        return {'id': ANSWER, 'parentId': USER, 'role': 'assistant', 'done': True,
            'content': '[Download](/api/v1/files/' + FILE + '/content)', 'followUps': self.followups,
            'statusHistory': [{'action': 'employee_budget_cost', 'done': True, 'description': B.COST + ' \u00b7 на 13:00:00 UTC'}],
            'files': [{'id': FILE, 'url': FILE, 'name': B.OUTPUT_NAME, 'type': 'file', 'content_type': B.DOCX}]}


class OfficeBrowserTests(unittest.TestCase):
    def exercise(self, mutate=None, clock=None):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            root = Path(directory); private = root / 'private'; private.mkdir(mode=0o700)
            fixture = B.OfficeFixture(root / 'env', root / 'output', root / 'config', private, [SECRET, 'actor-token', 'other-token'])
            world = ReadbackWorld(fixture, root / 'images'); browser = Browser(fixture)
            state = {'schema': 1, 'stage': 'setup_complete', 'users': [browser.actor], 'admin': {'id': ADMIN},
                'office_service_setup': {'stage': 'readback_ready'}}
            def write(name, value):
                path = private / name; path.write_text(json.dumps(value), encoding='utf-8'); path.chmod(0o600)
            write('office-state.private.json', state)
            write('webui-state.private.json', {'schema': 1, 'users': [browser.other]})
            for phase in ('office-setup', 'office-service-setup'):
                write(phase + '.safe.json', {'schema': 1, 'phase': phase, 'passed': True,
                    'inference_issued': False, 'native_office_accepted': False})
            if mutate: mutate(browser, world)
            before = (private / 'office-state.private.json').read_bytes()
            stack.enter_context(patch.object(B, 'expect', Expect))
            stack.enter_context(patch.object(login_owner, 'expect', Expect))
            stack.enter_context(patch.object(fixture_owner.subprocess, 'run', side_effect=world.run))
            if clock: stack.enter_context(patch.object(B.time, 'monotonic', side_effect=clock))
            if os.name == 'nt':
                stack.enter_context(patch.object(private_owner, 'private_parent'))
                stack.enter_context(patch.object(B, 'private_parent'))
            stdout = io.StringIO(); safe = packet = error = None
            with contextlib.redirect_stdout(stdout):
                try: safe, packet = B.run(browser, fixture, BASE, world.receipt, world.revision)
                except AssertionError as caught: error = caught
            self.assertEqual(stdout.getvalue(), '')
            self.assertTrue(all(c.closed for c in browser.contexts))
            self.assertEqual((private / 'office-state.private.json').read_bytes(), before)
            self.assertFalse(fixture.output.exists())
            if safe:
                self.assertEqual(json.loads((private / 'office-browser.private.json').read_bytes()),
                    {'schema': 1, 'chat_id': CHAT, 'answer_id': ANSWER, 'source_message_id': browser.source_id, 'file_id': FILE})
                for path in packet['paths'].values():
                    self.assertEqual(Path(path).resolve().parent, private.resolve())
                    if os.name != 'nt': self.assertEqual(Path(path).stat().st_mode & 0o777, 0o600)
            return safe, packet, error, browser, world

    def test_one_real_login_owner_seed_form_send_saved_lifecycle_native_download_and_acl(self):
        safe, private, error, browser, world = self.exercise()
        self.assertIsNone(error)
        self.assertEqual((browser.sends, browser.download_clicks, len(browser.foreign_reads)), (1, 1, 2))
        self.assertGreaterEqual(browser.reads, 2)
        self.assertEqual(safe['file_id'], FILE); self.assertFalse(safe['native_office_accepted'])
        self.assertEqual(safe['status'], 'browser_observed'); self.assertEqual(len(world.execs), 3)
        self.assertEqual(private['seed_form']['chat']['history']['messages'][browser.source_id]['content'], B.SOURCE)
        prepared = private['seed_form']['chat']
        question, source = prepared['messages']
        self.assertEqual(question['role'], 'user'); self.assertEqual(source['role'], 'assistant')
        self.assertEqual(source['parentId'], question['id']); self.assertEqual(question['childrenIds'], [browser.source_id])
        self.assertEqual(private['submission']['user_message']['parentId'], browser.source_id)
        for sensitive in (SECRET, 'actor-token', 'other-token', B.SOURCE, B.USER_REQUEST, 'class Pipe:'):
            self.assertNotIn(sensitive, json.dumps(safe))

    def test_wrong_running_image_stops_before_login_and_any_seed_or_send(self):
        safe, _, error, browser, _ = self.exercise(lambda b, w: w.rows[w.ids['webui']].update(image_id='sha256:' + 'f' * 64))
        self.assertIsNone(safe); self.assertIsNotNone(error); self.assertEqual(browser.contexts, [])

    def test_seed_owner_and_content_must_match_before_send(self):
        for mutation in (lambda s: s.update(user_id=OTHER),
                         lambda s: s['chat']['messages'][0].update(content='truncated previous answer')):
            with self.subTest(mutation=mutation):
                safe, _, error, browser, _ = self.exercise(lambda b, w: setattr(b, 'seed_mutation', mutation))
                self.assertIsNone(safe); self.assertIsNotNone(error); self.assertEqual(browser.sends, 0)

    def test_wrong_native_submission_ancestry_model_request_or_followup_is_rejected(self):
        for mutation in (lambda s: s.update(model='gpt-6-luna'), lambda s: s['user_message'].update(parentId=None),
            lambda s: s['user_message'].update(content='Export a summary'), lambda s: s['background_tasks'].update(follow_up_generation=False)):
            with self.subTest(mutation=mutation):
                safe, _, error, browser, _ = self.exercise(lambda b, w: setattr(b, 'submit_mutation', mutation))
                self.assertIsNone(safe); self.assertIsNotNone(error); self.assertEqual(browser.download_clicks, 0)

    def test_acknowledgement_alone_missing_followup_wrong_cost_and_live_tasks_cannot_pass(self):
        def bad_cost(saved):
            if ANSWER in saved['chat']['history']['messages']:
                saved['chat']['history']['messages'][ANSWER]['statusHistory'][0]['description'] = 'Wrong cost $0.20'
        for change in (lambda b, w: setattr(b, 'followups', []), lambda b, w: setattr(b, 'active_tasks', True),
                       lambda b, w: setattr(b, 'saved_mutation', bad_cost)):
            with self.subTest(change=change):
                safe, _, error, browser, _ = self.exercise(change, clock=iter([0, 1, 181, 182]).__next__)
                self.assertIsNone(safe); self.assertIsNotNone(error); self.assertEqual(browser.download_clicks, 0)

    def test_changed_persisted_source_or_answer_error_fails_not_a_success_ack(self):
        def lost_source(saved):
            source = next(v for v in saved['chat']['history']['messages'].values()
                if v.get('role') == 'assistant' and v.get('content') == B.SOURCE)
            source['content'] = 'lost table'
        for mutation in (lost_source,
                         lambda s: s['chat']['history']['messages'].get(ANSWER, {}).update(error={'message': 'tool failed'})):
            with self.subTest(mutation=mutation):
                safe, _, error, _, _ = self.exercise(lambda b, w: setattr(b, 'saved_mutation', mutation))
                self.assertIsNone(safe); self.assertIsNotNone(error)

    def test_file_owner_browser_bytes_filename_origin_and_foreign_acl_are_bound(self):
        for change in (lambda b, w: setattr(b, 'file_mutation', lambda f: f.update(user_id=OTHER)),
                       lambda b, w: setattr(b, 'download_bytes', b'other artifact'),
                       lambda b, w: setattr(b, 'download_name', 'other.docx'),
                       lambda b, w: setattr(b, 'download_url', 'https://example.invalid/other.docx'),
                       lambda b, w: setattr(b, 'foreign_status', 200)):
            with self.subTest(change=change):
                safe, _, error, _, _ = self.exercise(change)
                self.assertIsNone(safe); self.assertIsNotNone(error)

    def test_rejects_existing_output_without_overwrite(self):
        def existing(browser, world):
            (browser.fixture.private / 'office-browser.private.json').write_bytes(b'prior immutable evidence')
        safe, _, error, browser, _ = self.exercise(existing)
        self.assertIsNone(safe); self.assertIsNotNone(error); self.assertEqual(browser.contexts, [])

    def test_unprepared_private_stage_and_failed_worker_receipts_stop_before_login(self):
        def change(name, mutation):
            def apply(browser, world):
                path = browser.fixture.private / name
                value = json.loads(path.read_bytes()); mutation(value); path.write_text(json.dumps(value), encoding='utf-8')
            return apply
        for mutation in (change('office-state.private.json', lambda s: s['office_service_setup'].update(stage='in_progress')),
                         change('office-service-setup.safe.json', lambda s: s.update(passed=False)),
                         change('office-setup.safe.json', lambda s: s.update(inference_issued=True))):
            with self.subTest(mutation=mutation):
                safe, _, error, browser, _ = self.exercise(mutation)
                self.assertIsNone(safe); self.assertIsNotNone(error); self.assertEqual(browser.contexts, [])

    def test_rejected_send_and_failed_download_preserve_failure_and_close_contexts(self):
        for change in (lambda b, w: setattr(b, 'ack_status', 503),
                       lambda b, w: setattr(b, 'download_failure', 'cancelled')):
            with self.subTest(change=change):
                safe, _, error, browser, _ = self.exercise(change)
                self.assertIsNone(safe); self.assertIsNotNone(error); self.assertEqual(browser.sends, 1)

    def test_failed_native_login_closes_even_context_not_returned_by_login_owner(self):
        safe, _, error, browser, _ = self.exercise(lambda b, w: setattr(b, 'login_role', 'admin'))
        self.assertIsNone(safe); self.assertIsNotNone(error); self.assertEqual(browser.sends, 0)
        self.assertEqual(len(browser.contexts), 1)


if __name__ == '__main__': unittest.main()
