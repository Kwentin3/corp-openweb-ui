"""Browser/native HTTP IO-leaf checks, never actual browser/runtime acceptance."""
import contextlib
import copy
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prove_office_delegation_browser as B
import prove_gateway_auth as private_owner
import prove_webui_browser as login_owner
from test_office_browser import Pending, Response

BASE = 'http://stand.invalid:8080'
ACTOR, OTHER, ADMIN, CHAT, USER, ANSWER, SOURCE, FILE = [
    f'{i:08x}-1111-4111-8111-111111111111' for i in range(1, 9)]
SECRET = 'private-delegated-password'


class Locator:
    def __init__(self, page, selector): self.page, self.selector = page, selector
    @property
    def first(self): return self
    def locator(self, selector): return Locator(self.page, selector)
    def fill(self, value): self.page.fields[self.selector] = value
    def click(self):
        world = self.page.world
        if self.selector == 'form button[type="submit"]':
            assert self.page.fields['#email'] == self.page.account['email']
            assert self.page.fields['#password'] == self.page.account['password']
            self.page.pending.value = Response(self.page.account | {'role': world.role},
                url=BASE + '/api/v1/auths/signin', request=SimpleNamespace(method='POST'))
        elif self.selector == '#send-message-button':
            assert self.page.fields['#chat-input'] == B.user_request(world.skill['id'])
            world.sends += 1
            world.sent = {'model': B.MODEL, 'chat_id': CHAT, 'id': ANSWER,
                'user_message': {'id': USER, 'role': 'user', 'parentId': None,
                    'content': self.page.fields['#chat-input']},
                'messages': [{'role': 'user', 'content': self.page.fields['#chat-input']}],
                'background_tasks': {'follow_up_generation': True}, 'params': {}}
            if world.submit_mutation: world.submit_mutation(world.sent)
            self.page.pending.value = Response({'chat_id': CHAT}, status=world.ack_status,
                url=BASE + '/api/chat/completions', request=SimpleNamespace(method='POST', post_data_json=world.sent))
        elif self.selector == 'a[href="/api/v1/files/' + FILE + '/content"]':
            world.downloads += 1
            self.page.pending.value = SimpleNamespace(url=world.download_url, suggested_filename=world.filename,
                failure=lambda: world.download_failure, save_as=lambda path: Path(path).write_bytes(world.download_bytes))
        else: raise AssertionError('Unexpected delegated browser click')


class Expect:
    def __init__(self, locator): self.locator = locator
    def to_be_visible(self, **kwargs): pass
    def to_have_attribute(self, name, value):
        assert name == 'aria-label' and value == 'Selected model: Корпоративные документы'
    def to_contain_text(self, value, **kwargs):
        world = self.locator.page.world
        assert value == world.cost and world.cost_visible


class Page:
    def __init__(self, context): self.context, self.world, self.account, self.fields = context, context.world, context.account, {}
    def set_default_timeout(self, timeout): assert timeout == 30_000
    def goto(self, url, **kwargs): assert url in (BASE + '/auth', BASE + '/c/' + CHAT)
    def locator(self, selector): return Locator(self, selector)
    def expect_response(self, predicate, **kwargs): return Pending(self, 'response', predicate)
    def expect_download(self, **kwargs): return Pending(self, 'download')
    def wait_for_timeout(self, timeout): assert timeout == 250
    def screenshot(self, path, **kwargs): Path(path).write_bytes(b'private-IO-screenshot')


class Context:
    def __init__(self, world, account): self.world, self.account, self.request, self.closed = world, account, self, False
    def new_page(self): return Page(self)
    def close(self): self.closed = True
    def post(self, url, *, headers, data, timeout):
        world = self.world
        assert url == BASE + '/api/v1/chats/new' and timeout == 10_000
        assert headers == {'Authorization': 'Bearer actor-token'}
        assert data['chat']['history'] == {'currentId': None, 'messages': {}}
        assert data['chat']['messages'] == [] and data['chat']['models'] == [B.MODEL]
        world.form = copy.deepcopy(data)
        value = {'id': CHAT, 'user_id': ACTOR, 'chat': copy.deepcopy(data['chat'])}
        if world.seed_mutation: world.seed_mutation(value)
        return Response(value)
    def get(self, url, *, headers, timeout):
        world = self.world
        assert headers == {'Authorization': 'Bearer ' + self.account['token']} and timeout == 10_000
        if self.account['id'] == OTHER:
            assert url in (BASE + '/api/v1/files/' + FILE, BASE + '/api/v1/files/' + FILE + '/content')
            world.foreign_reads.append(url)
            return Response(status=world.foreign_status)
        if url == BASE + '/api/v1/skills/id/' + world.skill['id']:
            value = copy.deepcopy(world.skill)
            if world.skill_mutation: world.skill_mutation(value)
            return Response(value)
        if url == BASE + '/api/v1/files/' + SOURCE + '/content':
            world.source_reads += 1
            return Response(body=world.source_bytes if world.source_reads == 1 else world.source_after)
        if url == BASE + '/api/v1/chats/' + CHAT:
            world.chat_reads += 1
            chat = copy.deepcopy(world.form['chat'])
            chat['history']['messages'] = {USER: copy.deepcopy(world.sent['user_message']), ANSWER: world.answer()}
            chat['history']['currentId'] = ANSWER
            value = {'id': CHAT, 'user_id': ACTOR, 'chat': chat, 'tasks': copy.deepcopy(world.tasks)}
            if world.saved_mutation: world.saved_mutation(value)
            return Response(value)
        if url == BASE + '/api/tasks/chat/' + CHAT: return Response({'task_ids': world.running_tasks})
        if url == BASE + '/api/v1/files/' + FILE:
            value = {'id': FILE, 'user_id': ACTOR, 'meta': {'name': world.filename}}
            if world.file_mutation: world.file_mutation(value)
            return Response(value)
        if url == BASE + '/api/v1/files/' + FILE + '/content': return Response(body=world.native_bytes)
        raise AssertionError('Unexpected delegated native HTTP leaf')


class Browser:
    def __init__(self):
        self.actor = {'id': ACTOR, 'email': 'delegated@example.invalid', 'password': SECRET, 'token': 'actor-token'}
        self.other = {'id': OTHER, 'email': 'other@example.invalid', 'password': SECRET, 'token': 'other-token'}
        self.contexts = []; self.sends = self.downloads = self.chat_reads = self.source_reads = 0
        self.created_contexts = 0
        self.foreign_reads = []; self.role = 'user'; self.ack_status = 200; self.foreign_status = 404
        self.skill = {'id': 'goal584-delegated-synthetic', 'content': 'Complete synthetic private template Skill',
            'version_id': USER, 'is_active': True}
        self.source_bytes = self.source_after = b'synthetic original IO bytes'
        self.native_bytes = self.download_bytes = b'synthetic returned DOCX IO bytes'
        self.filename = 'goal584-filled.docx'; self.download_failure = None
        self.download_url = BASE + '/api/v1/files/' + FILE + '/content'
        self.tasks = [{'id': 'returned-native-task', 'content': 'Fill and inspect the copy', 'status': 'completed'}]
        self.running_tasks = []; self.followups = ['Review another copy.']
        self.cost = 'Ответ: $1.234 · Чат: $5.678 · на 13:00:00 UTC'; self.cost_visible = True
        self.submit_mutation = self.seed_mutation = self.saved_mutation = self.file_mutation = self.skill_mutation = None
    def new_context(self, **kwargs):
        assert kwargs == {'locale': 'en-US', 'viewport': {'width': 1440, 'height': 1000}}
        context = Context(self, self.actor if self.created_contexts == 0 else self.other)
        self.created_contexts += 1
        self.contexts.append(context); return context
    def answer(self):
        return {'id': ANSWER, 'parentId': USER, 'role': 'assistant', 'done': True,
            'content': '[Download](/api/v1/files/' + FILE + '/content)', 'followUps': self.followups,
            'statusHistory': [{'action': 'employee_budget_cost', 'done': True, 'description': self.cost}],
            'files': [{'type': 'file', 'id': FILE, 'url': FILE, 'name': self.filename, 'content_type': B.DOCX}]}


class DelegatedBrowserTests(unittest.TestCase):
    def test_empty_form_uses_actual_native_chat_form_without_prior_messages(self):
        from pydantic import BaseModel
        native = Path(os.environ.get('GOAL584_NATIVE_SOURCE_ROOT', str(HERE.parents[1] /
            'local/goal584/cost-display/open-webui/backend/open_webui')))
        raw = (native/'models/chats.py').read_bytes()
        nodes = [node for node in ast.parse(raw).body if isinstance(node, ast.ClassDef) and node.name == 'ChatForm']
        self.assertEqual(len(nodes), 1)
        namespace = {'BaseModel': BaseModel}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(native/'models/chats.py'), 'exec'), namespace)
        native_form = namespace['ChatForm'].model_validate(B.empty_form()).model_dump()
        self.assertEqual(native_form['chat']['history'], {'currentId': None, 'messages': {}})
        self.assertEqual(native_form['chat']['messages'], [])
        self.assertEqual(native_form['chat']['models'], [B.MODEL])

    def exercise(self, mutation=None, clock=None):
        with TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            root = Path(directory); private = root/'private'; private.mkdir(mode=0o700)
            fixture = B.OfficeFixture(root/'env', root/'output', root/'config', private, [SECRET, 'actor-token', 'other-token'])
            browser = Browser()
            state = {'schema': 1, 'stage': 'setup_complete', 'admin': {'id': ADMIN}, 'users': [{'id': OTHER}],
                'office_delegation_setup': {'stage': 'readback_ready', 'actor': browser.actor, 'skill': browser.skill,
                    'source_file': {'id': SOURCE}, 'source_sha256': hashlib.sha256(browser.source_bytes).hexdigest(),
                    'models': {B.MODEL: {'base_model_id': 'gpt-6.1-sol', 'name': 'Корпоративные документы',
                        'meta': {'builtinTools': {'tasks': True}}}}}}
            receipt = {'schema': 1, 'phase': 'office-delegation-setup', 'passed': True,
                'inference_issued': False, 'native_office_accepted': False}
            if mutation: mutation(browser, state, receipt)
            inherited_contexts = set(browser.contexts)
            for name, value in (('office-state.private.json', state), ('webui-state.private.json',
                    {'schema': 1, 'users': [browser.other]}), ('office-delegation-setup.safe.json', receipt)):
                target = private/name; target.write_text(json.dumps(value), encoding='utf8'); target.chmod(0o600)
            original = (private/'office-state.private.json').read_bytes()
            stack.enter_context(patch.object(B, 'expect', Expect))
            stack.enter_context(patch.object(login_owner, 'expect', Expect))
            running = stack.enter_context(patch.object(B.OfficeFixture, 'running_readback',
                return_value={'webui': {'image_id': 'actual-IO-boundary-observation'}, 'office': {'image_id': 'office-IO'}}))
            if clock: stack.enter_context(patch.object(B.time, 'monotonic', side_effect=clock))
            if os.name == 'nt':
                stack.enter_context(patch.object(B, 'private_parent'))
                stack.enter_context(patch.object(private_owner, 'private_parent'))
            safe = packet = error = None; stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                try: safe, packet = B.run(browser, fixture, BASE, {'bound': 'builder'}, 'accepted-revision')
                except AssertionError as caught: error = caught
            self.assertEqual(stdout.getvalue(), '')
            self.assertTrue(all(context.closed for context in browser.contexts if context not in inherited_contexts))
            self.assertTrue(all(not context.closed for context in inherited_contexts))
            self.assertEqual((private/'office-state.private.json').read_bytes(), original)
            running.assert_called_once_with(BASE, {'bound': 'builder'}, 'accepted-revision')
            self.assertFalse(fixture.output.exists())
            if safe:
                self.assertEqual(json.loads((private/B.PACKET).read_text(encoding='utf8')), packet)
                for path in packet['paths'].values():
                    self.assertEqual(Path(path).resolve().parent, private.resolve())
                    if os.name != 'nt': self.assertEqual(Path(path).stat().st_mode & 0o777, 0o600)
                for value in (SECRET, 'actor-token', 'other-token', browser.skill['content'], B.DELEGATED_USER_REQUEST, browser.cost):
                    self.assertNotIn(value, json.dumps(safe, ensure_ascii=False))
            else: self.assertFalse((private/B.PACKET).exists())
            return safe, packet, error, browser

    def test_one_ordinary_send_native_tasks_file_download_acl_and_full_private_handoff(self):
        safe, packet, error, browser = self.exercise()
        self.assertIsNone(error); self.assertFalse(safe['native_office_accepted'])
        self.assertEqual((browser.sends, browser.downloads, len(browser.foreign_reads)), (1, 1, 2))
        self.assertEqual(packet['chat_form']['chat']['history'], {'currentId': None, 'messages': {}})
        self.assertEqual(packet['chat_form']['chat']['messages'], [])
        self.assertEqual(packet['submission']['user_message']['content'], B.user_request(packet['skill_id']))
        self.assertEqual(packet['native_tasks'], packet['stored_chat']['tasks'])
        self.assertEqual(packet['source_before'], packet['source_after'])
        self.assertEqual(packet['artifacts']['browser'], packet['artifacts']['native'])
        self.assertTrue(set(('schema', 'actor_id', 'chat_id', 'user_message_id', 'answer_id', 'source_file_id',
            'skill_id', 'file_id', 'submission', 'stored_chat', 'native_file', 'running', 'paths')) <= set(packet))

    def test_preconditions_reject_stale_setup_actor_and_profile_before_login(self):
        for change in (lambda b,s,r:r.update(passed=False), lambda b,s,r:s['office_delegation_setup'].update(stage='preparing'),
                lambda b,s,r:s['users'].append({'id': ACTOR}),
                lambda b,s,r:s['office_delegation_setup']['models'][B.MODEL].update(base_model_id='gpt-6-luna')):
            with self.subTest(change=change):
                safe, _, error, browser = self.exercise(change)
                self.assertIsNone(safe); self.assertIsNotNone(error); self.assertEqual(browser.contexts, [])

    def test_native_login_and_inherited_context_lifetime_are_preserved(self):
        safe, _, error, browser = self.exercise(lambda b,s,r:setattr(b, 'role', 'admin'))
        self.assertIsNone(safe); self.assertIsNotNone(error); self.assertTrue(all(c.closed for c in browser.contexts))
        safe, _, error, browser = self.exercise(lambda b,s,r:b.contexts.append(Context(b, b.other)))
        self.assertIsNone(error); self.assertTrue(safe['terminal_persisted'])
        self.assertFalse(browser.contexts[0].closed)
        self.assertTrue(all(context.closed for context in browser.contexts[1:]))

    def test_malformed_checklist_and_native_answer_error_are_rejected(self):
        for change in (lambda b,s,r:b.tasks.append(copy.deepcopy(b.tasks[0])),
                lambda b,s,r:b.tasks[0].update(id=''),
                lambda b,s,r:setattr(b,'saved_mutation',lambda value:value['chat']['history']['messages'][ANSWER].update(error={'message':'PRIVATE_ERROR'})),
                lambda b,s,r:setattr(b,'saved_mutation',lambda value:value.update(user_id=OTHER))):
            with self.subTest(change=change):
                safe, _, error, _ = self.exercise(change)
                self.assertIsNone(safe); self.assertIsNotNone(error)

    def test_source_and_native_skill_binding_fail_before_send(self):
        for change in (lambda b,s,r:s['office_delegation_setup'].update(source_sha256='f'*64),
                lambda b,s,r:setattr(b, 'skill_mutation', lambda value:value.update(version_id=OTHER)),
                lambda b,s,r:setattr(b, 'seed_mutation', lambda value:value.update(user_id=OTHER))):
            with self.subTest(change=change):
                safe, _, error, browser = self.exercise(change)
                self.assertIsNone(safe); self.assertIsNotNone(error); self.assertEqual(browser.sends, 0)

    def test_actual_submission_model_prompt_parent_and_background_flag_are_bound(self):
        for change in (lambda value:value.update(model='corporate-office-worker'),
                lambda value:value['user_message'].update(parentId=SOURCE),
                lambda value:value['user_message'].update(content=B.DELEGATED_USER_REQUEST),
                lambda value:value['background_tasks'].update(follow_up_generation=False)):
            with self.subTest(change=change):
                safe, _, error, browser = self.exercise(lambda b,s,r:setattr(b, 'submit_mutation', change))
                self.assertIsNone(safe); self.assertIsNotNone(error); self.assertEqual(browser.sends, 1)

    def test_ack_pending_tasks_followups_and_background_are_not_terminal(self):
        for change in (lambda b,s,r:setattr(b,'running_tasks',['native-running']),
                lambda b,s,r:setattr(b,'tasks',[]), lambda b,s,r:b.tasks[0].update(status='pending'),
                lambda b,s,r:setattr(b,'followups',[]),
                lambda b,s,r:setattr(b,'saved_mutation',lambda value:value['chat']['history']['messages'][ANSWER].update(done=False))):
            with self.subTest(change=change):
                safe, _, error, browser = self.exercise(change, [0, 181])
                self.assertIsNone(safe); self.assertIsNotNone(error); self.assertEqual(browser.sends, 1)

    def test_unknown_pending_or_invisible_cost_does_not_pass(self):
        for description in ('Расход неизвестен. Обратитесь к администратору.',
                'Стоимость ещё не подтверждена журналом учёта. Учёт и лимиты действуют.',
                'Ответ: $1 · Чат: $1 · на 13:00:00 UTC · неизвестный статус'):
            safe, _, error, _ = self.exercise(lambda b,s,r:setattr(b, 'cost', description))
            self.assertIsNone(safe); self.assertIsNotNone(error)
        safe, _, error, _ = self.exercise(lambda b,s,r:setattr(b, 'cost_visible', False))
        self.assertIsNone(safe); self.assertIsNotNone(error)

    def test_observed_cost_amount_is_not_hardcoded(self):
        safe, packet, error, _ = self.exercise(lambda b,s,r:setattr(b, 'cost', 'Ответ: $0.0123 · Чат: $0.0456 · на 14:59:00 UTC'))
        self.assertIsNone(error); self.assertTrue(safe['visible_cost_status'])
        self.assertEqual(packet['cost_status']['description'], 'Ответ: $0.0123 · Чат: $0.0456 · на 14:59:00 UTC')

    def test_native_delegation_accrued_label_is_preserved_without_claiming_settlement(self):
        description = 'Ответ: $1.32 · Чат: $1.32 · на 13:00:00 UTC · начислено на сейчас, учёт обновляется'
        safe, packet, error, _ = self.exercise(lambda b,s,r:setattr(b, 'cost', description))
        self.assertIsNone(error); self.assertTrue(safe['visible_cost_status'])
        self.assertEqual(packet['cost_status']['description'], description)

    def test_result_native_owner_download_source_and_foreign_acl_mutations_fail(self):
        changes = (lambda b,s,r:setattr(b,'file_mutation',lambda value:value.update(user_id=OTHER)),
            lambda b,s,r:setattr(b,'download_url','https://foreign.invalid/api/v1/files/'+FILE+'/content'),
            lambda b,s,r:setattr(b,'download_bytes',b'changed-copy'),
            lambda b,s,r:setattr(b,'source_after',b'changed-original'),
            lambda b,s,r:setattr(b,'foreign_status',200), lambda b,s,r:setattr(b,'ack_status',503))
        for change in changes:
            with self.subTest(change=change):
                safe, _, error, _ = self.exercise(change)
                self.assertIsNone(safe); self.assertIsNotNone(error)


if __name__ == '__main__':
    unittest.main()
