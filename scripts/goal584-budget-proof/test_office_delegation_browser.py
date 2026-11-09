"""Browser/native HTTP IO-leaf checks, never actual browser/runtime acceptance."""
import contextlib
import copy
import ast
import base64
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
            self.page.pending.value = Response({'chat_id': CHAT}, status=world.ack_status, body=world.raw_ack,
                url=BASE + '/api/chat/completions', request=SimpleNamespace(method='POST', post_data_json=world.sent))
            if world.ack_error:
                def decode(): raise world.ack_error
                self.page.pending.value.json = decode
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
        assert value in (world.cost, world.answer()['content']) and world.cost_visible


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
        if url == BASE + '/api/v1/files/' + SOURCE:
            return Response({'id':SOURCE,'user_id':ACTOR,'meta':{'name':'source.docx'}})
        if url == BASE + '/api/v1/chats/' + CHAT:
            world.chat_reads += 1
            chat = copy.deepcopy(world.form['chat'])
            chat['history']['messages'] = {USER: copy.deepcopy(world.sent['user_message']), ANSWER: world.answer()}
            chat['history']['currentId'] = ANSWER
            value = {'id': CHAT, 'user_id': ACTOR, 'chat': chat, 'tasks': copy.deepcopy(world.tasks)}
            if world.saved_mutation: world.saved_mutation(value)
            return Response(value)
        if url == BASE + '/api/tasks/chat/' + CHAT: return Response({'task_ids': world.running_tasks}, status=world.active_status)
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
        self.contexts = []; self.sends = self.downloads = self.chat_reads = self.source_reads = 0; self.quota=False
        self.created_contexts = 0
        self.foreign_reads = []; self.role = 'user'; self.ack_status = 200; self.foreign_status = 404
        self.raw_ack = json.dumps({'chat_id': CHAT}).encode(); self.ack_error = None
        self.active_status = 200
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
        if self.quota:
            from mock_provider import DELEGATED_QUOTA_REFUSAL
            return {'id':ANSWER,'parentId':USER,'role':'assistant','model':B.MODEL,'done':True,
                'content':DELEGATED_QUOTA_REFUSAL['text'],'followUps':self.followups,'files':[],
                'statusHistory':[{'action':'employee_budget_cost','done':True,'description':self.cost}]}
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

    def exercise(self, mutation=None, clock=None, packet_limit=None, writer=None, *, quota=False, positive_stage='verified_readback'):
        with TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            root = Path(directory); private = root/'private'; private.mkdir(mode=0o700)
            fixture = B.OfficeFixture(root/'env', root/'output', root/'config', private, [SECRET, 'actor-token', 'other-token'])
            browser = Browser()
            if quota:
                browser.quota=True
                browser.tasks=[{'id':str(i),'content':'Unfinished document work','status':'cancelled'} for i in (1,2)]
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
            if quota:
                (private/'office-delegation-readback.private.json').write_text(json.dumps({
                    'schema':1,'stage':positive_stage,'prepared_sha256':B.digest(state),'quota':{'stage':'baseline_ready'}}),encoding='utf8')
            stack.enter_context(patch.object(B, 'expect', Expect))
            stack.enter_context(patch.object(login_owner, 'expect', Expect))
            running = stack.enter_context(patch.object(B.OfficeFixture, 'running_readback',
                return_value={'webui': {'image_id': 'actual-IO-boundary-observation'}, 'office': {'image_id': 'office-IO'}}))
            if clock: stack.enter_context(patch.object(B.time, 'monotonic', side_effect=clock))
            if packet_limit: stack.enter_context(patch.object(B, 'MAX_BYTES', packet_limit))
            if writer: stack.enter_context(patch.object(B, 'write_private', side_effect=writer))
            if os.name == 'nt':
                stack.enter_context(patch.object(B, 'private_parent'))
                stack.enter_context(patch.object(private_owner, 'private_parent'))
            safe = packet = error = None; stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                try: safe, packet = B.run(browser, fixture, BASE, {'bound': 'builder'}, 'accepted-revision',quota=quota)
                except Exception as caught: error = caught
            self.assertEqual(stdout.getvalue(), '')
            self.assertTrue(all(context.closed for context in browser.contexts if context not in inherited_contexts))
            self.assertTrue(all(not context.closed for context in inherited_contexts))
            self.assertEqual((private/'office-state.private.json').read_bytes(), original)
            running.assert_called_once_with(BASE, {'bound': 'builder'}, 'accepted-revision')
            self.assertFalse(fixture.output.exists())
            if safe:
                self.assertEqual(json.loads((private/('office-delegation-quota.private.json' if quota else B.PACKET)).read_text(encoding='utf8')), packet)
                for path in packet['paths'].values():
                    self.assertEqual(Path(path).resolve().parent, private.resolve())
                    if os.name != 'nt': self.assertEqual(Path(path).stat().st_mode & 0o777, 0o600)
                for value in (SECRET, 'actor-token', 'other-token', browser.skill['content'], B.DELEGATED_USER_REQUEST, browser.cost):
                    self.assertNotIn(value, json.dumps(safe, ensure_ascii=False))
            elif (private/('office-delegation-quota.private.json' if quota else B.PACKET)).exists():
                packet = json.loads((private/('office-delegation-quota.private.json' if quota else B.PACKET)).read_text(encoding='utf8'))
                self.assertIn(packet['status'], ('observing', 'failed'))
                self.assertLessEqual((private/('office-delegation-quota.private.json' if quota else B.PACKET)).stat().st_size,
                                     packet_limit or B.MAX_BYTES)
                public = B.failure_projection(packet)
                B.no_credentials(public, fixture.secrets)
                for value in (SECRET, 'actor-token', 'other-token', browser.skill['content'],
                              B.DELEGATED_USER_REQUEST, browser.cost, ACTOR, CHAT, USER, ANSWER, SOURCE):
                    self.assertNotIn(value, json.dumps(public, ensure_ascii=False))
            return safe, packet, error, browser

    def test_quota_one_send_two_cancelled_tasks_source_preserved_and_no_download(self):
        safe,packet,error,browser=self.exercise(quota=True)
        self.assertIsNone(error);self.assertTrue(safe['quota_refusal'])
        self.assertEqual((browser.sends,browser.downloads,len(browser.foreign_reads)),(1,0,0))
        self.assertEqual([t['status'] for t in packet['stored_chat']['tasks']],['cancelled','cancelled'])
        self.assertNotIn('file_id',packet);self.assertEqual(packet['native_running']['task_ids'],[])

    def test_quota_rejects_unaccepted_positive_before_send(self):
        safe,packet,error,browser=self.exercise(quota=True,positive_stage='baseline')
        self.assertIsNone(safe);self.assertIsNotNone(error);self.assertEqual(browser.sends,0)

    def test_quota_failure_retains_owned_chat_and_pre_stop_pending_tasks_for_recovery(self):
        def pending(world,state,receipt):
            world.tasks[0]['status']='pending';world.running_tasks=['native-still-running']
        safe,packet,error,browser=self.exercise(pending,quota=True,clock=[0,181])
        self.assertIsNone(safe);self.assertEqual(str(error),'delegated_browser_lifecycle_timeout')
        self.assertEqual((packet['actor_id'],packet['chat_id']),(ACTOR,CHAT))
        self.assertEqual(packet['native_tasks'][0]['status'],'pending')
        self.assertEqual(packet['native_running']['task_ids'],['native-still-running'])
        self.assertFalse(packet.get('terminal_persisted',False));self.assertEqual(browser.downloads,0)

    def test_quota_pending_tasks_or_background_cannot_finish_and_file_or_other_refusal_fail(self):
        for kind in ('pending','completed','active','file','text','source'):
            def mutate(world,state,receipt):
                if kind in ('pending','completed'):world.tasks[0]['status']=kind
                elif kind=='active':world.running_tasks=['actual-running-task']
                elif kind=='source':world.source_after=b'changed actual source bytes'
                else:
                    world.saved_mutation=lambda value:value['chat']['history']['messages'][ANSWER].update(
                        {'files':[{'type':'file','id':FILE}]} if kind=='file' else {'content':'Completed successfully'})
            with self.subTest(kind=kind):
                safe,packet,error,world=self.exercise(mutate,quota=True,clock=[0,181])
                self.assertIsNone(safe);self.assertIsNotNone(error);self.assertEqual(world.downloads,0)

    def test_failure_projection_reports_each_actual_lifecycle_none_gate(self):
        def answer_change(change):
            return lambda b,s,r:setattr(b, 'saved_mutation', lambda value:change(value['chat']['history']['messages'][ANSWER]))
        cases = [
            ('user_missing', lambda b,s,r:setattr(b, 'saved_mutation', lambda v:v['chat']['history']['messages'].pop(USER)), 'user_present', False),
            ('answer_missing', lambda b,s,r:setattr(b, 'saved_mutation', lambda v:v['chat']['history']['messages'].pop(ANSWER)), 'answer_present', False),
            ('done_missing', answer_change(lambda a:a.pop('done')), 'answer_done', None),
            ('done_false', answer_change(lambda a:a.update(done=False)), 'answer_done', False),
            ('done_not_bool', answer_change(lambda a:a.update(done=1)), 'answer_done', None),
            ('checklist_missing', lambda b,s,r:setattr(b, 'saved_mutation', lambda v:v.pop('tasks')), 'checklist_present', False),
            ('checklist_empty', lambda b,s,r:setattr(b, 'tasks', []), 'checklist_count', 0),
            ('cost_missing', answer_change(lambda a:a.pop('statusHistory')), 'budget_status_present', False),
            ('cost_pending', answer_change(lambda a:a['statusHistory'][0].update(done=False)), 'budget_status_done', False),
            ('cost_done_missing', answer_change(lambda a:a['statusHistory'][0].pop('done')), 'budget_status_done', None),
            ('followups_missing', answer_change(lambda a:a.pop('followUps')), 'followups_count', None),
            ('followups_empty', lambda b,s,r:setattr(b, 'followups', []), 'followups_count', 0),
            ('active_task', lambda b,s,r:setattr(b, 'running_tasks', ['native-active']), 'native_task_ids_count', 1)]
        for name, change, key, expected in cases:
            with self.subTest(name=name):
                safe, packet, error, browser = self.exercise(change, [0, 181])
                self.assertIsNone(safe)
                self.assertEqual(str(error), 'delegated_browser_lifecycle_timeout')
                self.assertEqual(packet['phase'], 'lifecycle')
                self.assertEqual(packet['actor_id'], ACTOR)
                self.assertEqual((packet['chat_id'], packet['user_message_id'], packet['answer_id']), (CHAT, USER, ANSWER))
                self.assertEqual(packet['native_tasks'], packet['stored_chat'].get('tasks'))
                self.assertEqual(packet['native_running'], {'task_ids': browser.running_tasks})
                projection = B.failure_projection(packet)
                self.assertTrue(projection['collected'])
                self.assertEqual(projection[key], expected)
                self.assertFalse(projection['native_finance_qualified'])

    def test_failure_projection_attachment_and_task_statuses_are_counts_only(self):
        def change(b,s,r):
            b.tasks = [{'id': str(index), 'content': 'PRIVATE_TASK_CONTENT', 'status': status}
                       for index, status in enumerate(('pending', 'in_progress', 'completed', 'cancelled', 'PRIVATE_STATUS'))]
            b.saved_mutation = lambda value:value['chat']['history']['messages'][ANSWER].update(files=[
                {'type': 'file', 'content_type': B.DOCX, 'url': 'https://PRIVATE_URL'}, {'private': SECRET}, None])
        _, packet, error, _ = self.exercise(change, [0, 181])
        self.assertEqual(str(error), 'delegated_browser_lifecycle_timeout')
        projection = B.failure_projection(packet)
        self.assertEqual(projection['checklist_status_counts'], dict.fromkeys(B.TASK_STATUSES, 1))
        self.assertEqual((projection['attachment_count'], projection['docx_count']), (3, 1))
        for secret in ('PRIVATE_TASK_CONTENT', 'PRIVATE_STATUS', 'https://PRIVATE_URL'):
            self.assertNotIn(secret, json.dumps(projection))

    def test_created_chat_and_raw_ack_checkpoints_precede_validation_without_poll_writes(self):
        writes = []
        def writer(path, packet):
            writes.append(copy.deepcopy(packet))
            private_owner.write_private(path, packet)
        _, packet, error, _ = self.exercise(lambda b,s,r:setattr(b, 'ack_status', 503), writer=writer)
        self.assertEqual(str(error), 'delegated_browser_send_rejected')
        self.assertEqual(len(writes), 3)
        self.assertEqual(writes[0]['created_chat']['id'], CHAT)
        self.assertNotIn('submission', writes[0])
        self.assertEqual(writes[1]['submission_status'], 503)
        self.assertEqual(base64.b64decode(writes[1]['raw_acknowledgement_base64']), json.dumps({'chat_id': CHAT}).encode())
        self.assertNotIn('acknowledgement', writes[1])
        self.assertEqual(packet['submission'], writes[1]['submission'])
        writes.clear()
        _, _, error, _ = self.exercise(lambda b,s,r:setattr(b, 'running_tasks', ['active']), [0, 1, 2, 181], writer=writer)
        self.assertEqual(str(error), 'delegated_browser_lifecycle_timeout')
        self.assertEqual(len(writes), 3)  # created, wire ACK, final failure; never per poll

    def test_non_json_raw_ack_survives_decode_exception_without_text_dump(self):
        original = ValueError('PRIVATE_RESPONSE_ERROR')
        def change(b,s,r): b.raw_ack = b'\xff\x00not JSON PRIVATE_ACK'; b.ack_error = original
        safe, packet, error, _ = self.exercise(change)
        self.assertIsNone(safe); self.assertIs(error, original)
        self.assertEqual(base64.b64decode(packet['raw_acknowledgement_base64']), b'\xff\x00not JSON PRIVATE_ACK')
        self.assertEqual(packet['failure'], 'delegated_browser_unclassified')
        self.assertNotIn('PRIVATE_RESPONSE_ERROR', json.dumps(packet))
        self.assertNotIn('PRIVATE_ACK', json.dumps(B.failure_projection(packet)))

    def test_failed_native_read_keeps_last_actual_chat_without_extra_diagnostic_reads(self):
        _, packet, error, browser = self.exercise(lambda b,s,r:setattr(b, 'active_status', 503))
        self.assertEqual(str(error), 'delegated_browser_native_read')
        self.assertEqual(browser.chat_reads, 1)
        self.assertEqual(packet['stored_chat']['chat']['history']['messages'][ANSWER], browser.answer())
        projection = B.failure_projection(packet)
        self.assertTrue(projection['answer_done'])
        self.assertIsNone(projection['native_task_ids_count'])

    def test_failure_retains_actual_source_binding_without_repairing_it(self):
        _, packet, error, browser = self.exercise(lambda b,s,r:setattr(b, 'skill_mutation', lambda v:v.update(version_id=OTHER)))
        self.assertEqual(str(error), 'delegated_browser_skill_binding')
        self.assertEqual(packet['native_skill']['version_id'], OTHER)
        self.assertEqual(packet['source_before']['sha256'], hashlib.sha256(browser.source_bytes).hexdigest())
        self.assertEqual(browser.sends, 0)
        self.assertNotIn('created_chat', packet)
        _, packet, error, browser = self.exercise(lambda b,s,r:setattr(b, 'seed_mutation', lambda v:v.update(user_id=OTHER)))
        self.assertEqual(str(error), 'delegated_browser_empty_chat_readback')
        self.assertEqual(packet['created_chat']['user_id'], OTHER)
        self.assertEqual(browser.sends, 0)

    def test_browser_code_binding_is_actual_module_bytes_in_regular_and_omitted_packets(self):
        expected = hashlib.sha256(Path(B.__file__).read_bytes()).hexdigest()
        for oversized in (False, True):
            with self.subTest(oversized=oversized):
                def change(b,s,r):
                    b.running_tasks = ['active']
                    s['browser_source_sha256'] = 'f' * 64  # caller claim is never the code source
                    if oversized:
                        b.saved_mutation = lambda value:value['chat']['history']['messages'][ANSWER].update(content='x' * 20000)
                _, packet, error, _ = self.exercise(change, [0, 181], packet_limit=12000 if oversized else None)
                self.assertEqual(str(error), 'delegated_browser_lifecycle_timeout')
                self.assertEqual(packet['browser_source_sha256'], expected)
                self.assertNotEqual(packet['browser_source_sha256'], packet['source_before']['sha256'])
                self.assertEqual(packet.get('raw_omitted', False), oversized)
        with TemporaryDirectory() as directory:
            module = Path(directory) / 'actual-browser-module.py'
            for actual in (b'actual first module bytes', b'changed module bytes'):
                module.write_bytes(actual)
                with patch.object(B, '__file__', str(module)):
                    _, packet, error, _ = self.exercise(lambda b,s,r:setattr(b, 'running_tasks', ['active']), [0, 181])
                self.assertEqual(str(error), 'delegated_browser_lifecycle_timeout')
                self.assertEqual(packet['browser_source_sha256'], hashlib.sha256(actual).hexdigest())
    def test_oversized_actual_chat_retains_only_explicit_bounded_observation(self):
        def change(b,s,r):
            b.running_tasks = ['active']
            b.saved_mutation = lambda value:value['chat']['history']['messages'][ANSWER].update(content='PRIVATE_LARGE_' * 5000)
        _, packet, error, _ = self.exercise(change, [0, 181], packet_limit=12000)
        self.assertEqual(str(error), 'delegated_browser_lifecycle_timeout')
        self.assertTrue(packet['raw_omitted']); self.assertGreater(packet['raw_bytes'], 12000)
        self.assertNotIn('stored_chat', packet); self.assertNotIn('submission', packet)
        self.assertEqual(packet['source_before']['sha256'], hashlib.sha256(b'synthetic original IO bytes').hexdigest())
        projection = B.failure_projection(packet)
        self.assertTrue(projection['collected']); self.assertTrue(projection['answer_done'])
        self.assertEqual(projection['native_task_ids_count'], 1)
        self.assertNotIn('PRIVATE_LARGE_', json.dumps(packet))

    def test_oversized_ack_is_explicitly_omitted_and_keeps_only_technical_metadata(self):
        def change(b,s,r): b.raw_ack = b'PRIVATE_ACK' * 2000; b.ack_status = 503
        _, packet, error, _ = self.exercise(change, packet_limit=12000)
        self.assertEqual(str(error), 'delegated_browser_send_rejected')
        self.assertTrue(packet['raw_omitted']); self.assertTrue(packet['raw_acknowledgement_omitted'])
        self.assertEqual(packet['raw_acknowledgement_bytes'], 22000)
        self.assertEqual(packet['raw_acknowledgement_sha256'], hashlib.sha256(b'PRIVATE_ACK' * 2000).hexdigest())
        self.assertNotIn('submission', packet); self.assertNotIn('raw_acknowledgement_base64', packet)

    def test_success_cannot_export_an_oversized_private_packet_as_accepted(self):
        def change(b,s,r):
            b.saved_mutation = lambda v:v['chat']['history']['messages'][ANSWER].update(private_extra='x' * 20000)
        safe, packet, error, _ = self.exercise(change, packet_limit=12000)
        self.assertIsNone(safe); self.assertEqual(str(error), 'delegated_browser_packet_bound')
        self.assertTrue(packet['raw_omitted']); self.assertEqual(packet['status'], 'failed')
        self.assertFalse(B.failure_projection(packet)['native_office_accepted'])

    def test_failure_save_error_keeps_original_failure_and_observing_packet_uncollected(self):
        def writer(path, packet):
            if packet.get('status') == 'failed': raise OSError('PRIVATE_WRITE_ERROR')
            private_owner.write_private(path, packet)
        _, packet, error, _ = self.exercise(lambda b,s,r:setattr(b, 'running_tasks', ['active']), [0, 181], writer=writer)
        self.assertEqual(str(error), 'delegated_browser_lifecycle_timeout')
        self.assertEqual(packet['status'], 'observing')
        self.assertFalse(B.failure_projection(packet)['collected'])

    def test_projection_rejects_untrusted_text_types_and_oversize_summary_values(self):
        projection = B.failure_projection({'schema': 1, 'status': 'failed', 'phase': 'PRIVATE_PHASE',
            'failure': 'delegated_browser_timeout PRIVATE_SECRET', 'user_message_id': [], 'answer_id': {},
            'raw_omitted': True, 'lifecycle_observation': {'answer_done': 1, 'attachment_count': True,
                'checklist_status_counts': {'PRIVATE_STATUS': 5}}})
        self.assertIsNone(projection['phase']); self.assertIsNone(projection['failure'])
        self.assertFalse(projection['collected'])
        self.assertIsNone(projection['answer_done']); self.assertIsNone(projection['attachment_count'])
        self.assertIsNone(projection['checklist_status_counts'])
        self.assertNotIn('PRIVATE_', json.dumps(projection))

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
        self.assertEqual(set(packet), {'schema', 'actor_id', 'chat_id', 'user_message_id', 'answer_id',
            'source_file_id', 'skill_id', 'file_id', 'submission', 'submission_status', 'acknowledgement',
            'chat_form', 'created_chat', 'stored_chat', 'native_file', 'running', 'native_tasks',
            'background_tasks', 'cost_status', 'native_running', 'source_before_sha256', 'source_after_sha256',
            'source_before', 'source_after', 'artifacts', 'native_skill', 'foreign_file_statuses', 'paths'})
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


def run_native_artifact_host_tail(directory, *, mutation=None, workflow=None):
    """Real final context/finance owners and exact workflow tail; native IO leaves."""
    import pytest
    import yaml
    import test_office_delegation_readback as T
    import prove_office_delegation_readback as R
    root=HERE.parents[1]
    with pytest.MonkeyPatch.context() as monkeypatch:
        data=T.complete_case(directory,monkeypatch)
        private=directory.resolve();out=private/'output';out.mkdir()
        paths={key:(private/name).resolve() for key,name in data['browser']['paths'].items()}
        worker=next(row for row in reversed(data['provider']['requests']) if row['body']['model']==R.WIRES[R.MODELS[1]])
        render_call=R.task_pairs(worker['body'])[-1][0]
        png,_=R.select_render_image(worker['body'],render_call,file_id=data['browser']['file_id'])
        paths['screenshot']=private/'screenshot.png';paths['screenshot'].write_bytes(png)
        observed={'file_id':data['browser']['file_id'],'docx_sha256':hashlib.sha256(paths['browser'].read_bytes()).hexdigest(),
            'screenshot_sha256':hashlib.sha256(png).hexdigest()}
        publications={};events=[]
        def public(name,packet):
            B.no_credentials(packet,[]);publications[name]=copy.deepcopy(packet)
        def readback(phase):
            events.append(phase)
            packet={'passed':True,'phase':phase,'native_office_accepted':False}
            if phase=='verify':packet.update(R.verify(**data))
            else:
                assert phase=='diagnostic'
                packet.update(provider_added=len(data['provider']['requests']),auth_added=len(data['captured']['requests']))
            public('office-delegation-'+phase,packet)
            return packet
        source_root=root/'scripts/goal584-budget-proof'
        mounted_paths={name:source_root/name for name in ('prove_office_delegation_readback.py','mock_provider.py')}
        mounted_paths.update({'corporate_templates.py':root/'deploy/openwebui-tools/corporate_templates.py',
            'corporate_template_models.json':root/'deploy/openwebui-tools/corporate_template_models.json',
            'artifact-workflow.md':root/'deploy/openwebui-skills/artifact-workflow.md'})
        host_paths={'prove_office_delegation_browser.py':source_root/'prove_office_delegation_browser.py'}
        source_hashes=lambda paths:{name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in paths.items()}
        namespace=dict(Path=Path,base64=base64,hashlib=hashlib,json=json,_nodes=R.proof._nodes,digest=R.proof.digest,
            select_render_image=R.select_render_image,private=private,out=out,observed=observed,
            raw={'paths':{key:str(path) for key,path in paths.items()}},provider=data['provider'],
            readback=readback,public=public,source_hashes=source_hashes,mounted_paths=mounted_paths,host_paths=host_paths,
            mounted_sources=source_hashes(mounted_paths),host_sources=source_hashes(host_paths),
            stage='diagnostic',baseline_ready=True,diagnostic_collected=False,artifacts_collected=False,
            ProofError=T.N.ProofError,no_credentials=B.no_credentials,fixture=SimpleNamespace(secrets=[]),
            signal=SimpleNamespace(alarm=lambda value:None))
        if mutation=='screenshot_bytes':paths['screenshot'].write_bytes(b'swapped-private-screenshot')
        elif mutation=='private_path':namespace['raw']['paths']['screenshot']=str(private.parent/'unowned.png')
        elif mutation=='native_bytes':paths['native'].write_bytes(b'swapped-private-document')
        elif mutation=='wrong_role':worker['body']['input'][-1]['role']='assistant'
        text=workflow or (root/'.github/workflows/goal584-office-proof.yml').read_text(encoding='utf8')
        run=next(step['run'] for job in yaml.safe_load(text)['jobs'].values() for step in job['steps']
            if step.get('name')=='Verify one ordinary delegated Office Send and native personal accounting')
        source=run.partition("<<'PY'\n")[2].rsplit('\nPY',1)[0]
        tree=ast.parse(source)
        collector=next(n for n in tree.body if getattr(n,'name',None)=='collect_artifacts')
        guarded=next(n for n in tree.body if isinstance(n,ast.Try))
        start=next(i for i,n in enumerate(guarded.body) if isinstance(n,ast.Assign)
            and any(getattr(t,'id',None)=='stage' for t in n.targets) and isinstance(n.value,ast.Constant)
            and n.value.value=='diagnostic')
        tail=ast.Try(body=guarded.body[start:],handlers=guarded.handlers,orelse=guarded.orelse,finalbody=guarded.finalbody)
        error=None
        try:exec(compile(ast.fix_missing_locations(ast.Module(body=[collector,tail],type_ignores=[])),
            'actual-native-delegated-artifact-host-tail','exec'),namespace)
        except SystemExit as caught:error=caught.code
        return publications,{path.name:path.read_bytes() for path in out.iterdir()},error,events


class NativeArtifactHostTailTests(unittest.TestCase):
    def test_actual_native_context_finance_then_same_selector_exports_all_public_artifacts(self):
        with TemporaryDirectory() as directory:
            packets,files,error,events=run_native_artifact_host_tail(Path(directory))
        self.assertIsNone(error);self.assertEqual(events,['diagnostic','verify'])
        self.assertTrue(packets['office-delegation']['passed'])
        self.assertEqual(set(files),{'office-delegation.docx','office-delegation-render.png','office-delegation-browser.png'})
        financial=packets['office-delegation-verify']
        self.assertEqual(financial['personal']['gpt-6.1-sol']['native_spend_delta_usd'],'1.20')
        self.assertEqual(financial['personal']['gpt-6.1-terra']['native_spend_delta_usd'],'.12')
        self.assertEqual(financial['service']['native_spend_delta_usd'],'.20')
        self.assertFalse(packets['office-delegation']['native_office_accepted'])

    def test_artifact_failures_still_exit_fatal_and_preserve_prior_genuine_financial_result(self):
        for mutation in ('screenshot_bytes','private_path','native_bytes','wrong_role'):
            with self.subTest(mutation=mutation),TemporaryDirectory() as directory:
                packets,files,error,events=run_native_artifact_host_tail(Path(directory),mutation=mutation)
                self.assertEqual(error,1);self.assertFalse(packets['office-delegation']['passed'])
                self.assertFalse(files)
                self.assertTrue(packets['office-delegation']['failure'])
                if mutation in ('screenshot_bytes','private_path'):
                    self.assertTrue(packets['office-delegation-verify']['passed'])
                else:self.assertNotIn('office-delegation-verify',packets)


if __name__ == '__main__':
    unittest.main()
