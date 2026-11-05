"""Offline native-source/host-driver rehearsal; no actual GUI or policy acceptance."""
import contextlib
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from uuid import NAMESPACE_URL, uuid5

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prove_unknown_usage_browser as B
import prove_webui_browser as login_owner
import prove_gateway_auth as private_owner

BASE = 'http://127.0.0.1:8080'
ACTOR, OTHER, OFFICE, ADMIN = [str(uuid5(NAMESPACE_URL, s)) for s in ('unknown-actor', 'other', 'office', 'admin')]


class Response:
    def __init__(self, url, value, status=200, submitted=None):
        self.url, self.value, self.status = url, value, status
        self.request = SimpleNamespace(method='POST', post_data_json=submitted)
    def body(self): return json.dumps(self.value).encode()
    def json(self): return self.value


def merge(target, patch):
    for key, value in patch.items():
        if isinstance(value, dict): merge(target.setdefault(key, {}), value)
        else: target[key] = copy.deepcopy(value)


class Locator:
    def __init__(self, page, key): self.page, self.key = page, key
    @property
    def first(self): return self
    def locator(self, selector): return self if selector == '..' else Locator(self.page, selector)
    def get_by_role(self, role, name=None, **kwargs):
        return Locator(self.page, 'stream' if self.key == 'stream' else name or role)
    def get_by_text(self, text, **kwargs):
        assert text == 'Stream Chat Response'; return Locator(self.page, 'stream')
    def fill(self, value): self.page.fields[self.key] = value
    def click(self):
        w = self.page.world
        if self.key == 'stream': w.pending_stream = True if w.pending_stream is None else False if w.pending_stream else None
        elif self.key == 'Save': w.save({'ui': {'system': None, 'params': {'stream_response': w.pending_stream}}})
        elif 'role="switch"' in self.key:
            label = re.search(r'aria-labelledby="([^"]+)"', self.key)[1]
            path = {'auto-generation-label': 'title.auto', 'follow-up-auto-generation-label': 'autoFollowUps', 'chat-tags-label': 'autoTags'}[label]
            ui = {'title': {'auto': False}} if path == 'title.auto' else {path: False}
            w.save({'ui': ui})
        elif self.key.startswith('button[data-value='): w.selected = self.key.split('"')[1]
        elif self.key == '#send-message-button': w.submit()
        elif self.key == 'form button[type="submit"]':
            account = self.page.context.account
            assert self.page.fields['#email'] == account['email'] and self.page.fields['#password'] == account['password']
            w.last = Response(BASE + '/api/v1/auths/signin', {'id': account['id'], 'role': 'user', 'token': account['token']})
        else:
            assert self.key in ('User menu', 'Settings', 'Show', 'Back') or 'model-selector-' in self.key or 'role="tab"' in self.key, self.key
    def inner_text(self):
        w = self.page.world
        if self.key == 'stream': return 'Default' if w.pending_stream is None else 'On' if w.pending_stream else 'Off'
        answer = next(reversed(w.chats.values()))['chat']['history']['messages'][w.sent['id']]
        text = B.BLOCKED if answer.get('error') else 'Proof ' + answer['statusHistory'][0]['description']
        return w.visible_mutation(self.key, text) if w.visible_mutation else text
    def get_attribute(self, name):
        w = self.page.world
        if name == 'aria-checked':
            label = re.search(r'aria-labelledby="([^"]+)"', self.key)[1]
            path = {'auto-generation-label': 'title.auto', 'follow-up-auto-generation-label': 'autoFollowUps', 'chat-tags-label': 'autoTags'}[label]
            return 'false' if B.setting(w.settings, path) is False else 'true'
        if name == 'aria-label': return 'Selected model: ' + w.selected
        raise AssertionError('Unexpected DOM attribute')


class Expect:
    def __init__(self, locator): self.locator = locator
    def to_be_visible(self, **kwargs): pass  # DOM visibility is a browser leaf.
    def to_have_text(self, text, **kwargs): assert self.locator.inner_text() == text
    def to_contain_text(self, text, **kwargs): assert text in self.locator.inner_text()
    def to_have_attribute(self, name, value, **kwargs): assert self.locator.get_attribute(name) == value


class Pending:
    def __init__(self, page, predicate): self.page, self.predicate = page, predicate
    def __enter__(self): return self
    def __exit__(self, *args):
        if args[0] is None:
            self.value = self.page.world.last
            assert self.predicate(self.value)


class Page:
    def __init__(self, context): self.context, self.world, self.fields = context, context.world, {}
    def set_default_timeout(self, timeout): assert timeout == 30_000
    def goto(self, url, **kwargs): assert url in (BASE + '/', BASE + '/auth')
    def locator(self, selector): return Locator(self, selector)
    def get_by_role(self, role, name, **kwargs): return Locator(self, name)
    def expect_response(self, predicate, **kwargs): return Pending(self, predicate)
    def wait_for_timeout(self, delay): assert delay == 250
    def screenshot(self, path, **kwargs): Path(path).write_bytes(b'synthetic-visible-only-PNG')


class Context:
    def __init__(self, world, account): self.world, self.account, self.request, self.closed = world, account, self, False
    def new_page(self): return Page(self)
    def close(self): self.closed = True
    def get(self, url, *, headers, timeout):
        w = self.world; path = url.removeprefix(BASE); token = headers['Authorization'].removeprefix('Bearer ')
        assert timeout == 10_000
        if path.startswith(B.SETTINGS):
            return Response(url, copy.deepcopy(w.office_settings if token == w.office['token'] else w.settings))
        if path.startswith('/api/tasks/chat/'):
            return Response(url, {'task_ids': ['active'] if w.active else []})
        if path.startswith('/api/v1/chats/'):
            if self.account['id'] == OTHER: return Response(url, {}, w.foreign_status)
            stored = copy.deepcopy(w.chats[path.rsplit('/', 1)[1]])
            if w.saved_mutation: w.saved_mutation(stored)
            return Response(url, stored)
        raise AssertionError('Unexpected browser read')
    def post(self, *args, **kwargs): raise AssertionError('Host settings/provisioning POST is forbidden')


class World:
    def __init__(self):
        def actor(uid): return {'id': uid, 'email': uid + '@example.invalid', 'password': 'synthetic-password', 'token': 'synthetic-session-' + uid}
        self.actor, self.other, self.office = map(actor, (ACTOR, OTHER, OFFICE))
        self.contexts, self.chats, self.updates = [], {}, []
        self.settings, self.office_settings, self.pending_stream = None, {'ui': {'params': {'stream_response': True}, 'autoFollowUps': True}}, None
        self.selected = None; self.ignored_update = self.active = False
        self.submit_mutation = self.saved_mutation = self.visible_mutation = self.ack_mutation = None
        self.ack_status = 200
        self.foreign_status = 404
    def new_context(self, **kwargs):
        c = Context(self, self.actor if not self.contexts else self.other); self.contexts.append(c); return c
    def save(self, value):
        self.updates.append(copy.deepcopy(value))
        desired = copy.deepcopy(self.settings or {}); merge(desired, value)
        if not self.ignored_update: self.settings = desired
        # A superficially successful ACK may lie about persistence: the driver
        # must also check the actual independent effective settings readback.
        self.last = Response(BASE + B.SETTINGS + '/update', desired, submitted=value)
    def submit(self):
        index = len(self.chats); model = self.selected
        _, expected, outcome = B.CASES[index]; assert model == expected
        ids = [str(uuid5(NAMESPACE_URL, f'unknown-ui-{index}-{name}')) for name in ('chat', 'answer', 'user')]
        chat, answer, user = ids
        sent = {'model': model, 'stream': B.setting(self.settings, 'params.stream_response'), 'id': answer,
            'parent_id': None, 'user_message': {'id': user, 'role': 'user', 'content': 'Hi', 'parentId': None},
            'message_ids': [{'model_id': model, 'message_id': answer, 'modelIdx': 0}],
            'background_tasks': {'title_generation': B.setting(self.settings, 'title.auto'), 'tags_generation': B.setting(self.settings, 'autoTags'),
                                 'follow_up_generation': B.setting(self.settings, 'autoFollowUps')}}
        if self.submit_mutation: self.submit_mutation(sent)
        self.sent = copy.deepcopy(sent)
        q = copy.deepcopy(sent['user_message']); q['childrenIds'] = [answer]
        a = {'id': answer, 'parentId': user, 'role': 'assistant', 'model': model, 'user_id': ACTOR, 'done': True, 'content': ''}
        if outcome == 'denied': a['error'] = {'content': {'message': B.BLOCKED + ' Update via `/key/unblock` if an admin.'}}
        else:
            a['output'] = [{'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'Proof', 'annotations': []}]}]
            a['statusHistory'] = [{'action': 'employee_budget_cost', 'done': True, 'description': B.UNKNOWN if outcome == 'unknown' else B.KNOWN + ' · на 13:00:00 UTC'}]
        self.chats[chat] = {'id': chat, 'user_id': ACTOR, 'chat': {'models': [model], 'history': {'currentId': answer, 'messages': {user: q, answer: a}}}}
        acknowledgement = {'chat_id': chat, 'status': True}
        if self.ack_mutation: self.ack_mutation(acknowledgement)
        self.last = Response(BASE + '/api/chat/completions', acknowledgement, self.ack_status, submitted=sent)


class UnknownBrowserTests(unittest.TestCase):
    def exercise(self, mutate=None, clock=None):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            root = Path(directory); private = root / 'private'; private.mkdir(mode=0o700)
            world = World()
            if mutate: mutate(world)
            states = {B.UNKNOWN_GUI_STATE: {'schema': 1, 'stage': 'setup_complete', 'users': [world.actor]},
                'webui-state.private.json': {'schema': 1, 'admin': {'id': ADMIN}, 'users': [world.other]},
                'office-state.private.json': {'schema': 1, 'users': [world.office]}}
            for name, value in states.items():
                p = private / name; p.write_text(json.dumps(value), encoding='utf8'); p.chmod(0o600)
            original = {n: (private / n).read_bytes() for n in states}
            fixture = SimpleNamespace(private=private, output=root / 'public', secrets=['synthetic-password'],
                running_readback=Mock(return_value={'source_commit': 'a' * 40}),
                _office_private=Mock(side_effect=lambda n: ((private / n).read_bytes(), json.loads((private / n).read_bytes()))))
            stack.enter_context(patch.object(B, 'expect', Expect)); stack.enter_context(patch.object(login_owner, 'expect', Expect))
            if os.name == 'nt':
                stack.enter_context(patch.object(B, 'private_parent')); stack.enter_context(patch.object(private_owner, 'private_parent'))
            if clock: stack.enter_context(patch.object(B.time, 'monotonic', side_effect=clock))
            safe = packet = failure = None
            try: safe, packet = B.run(world, fixture, BASE, {'source_commit': 'a' * 40}, 'a' * 40)
            except AssertionError as error: failure = error
            fixture.running_readback.assert_called_once_with(BASE, {'source_commit': 'a' * 40}, 'a' * 40)
            self.assertTrue(all(c.closed for c in world.contexts))
            self.assertEqual(original, {n: (private / n).read_bytes() for n in states})
            saved = json.loads((private / 'unknown-usage-browser.private.json').read_bytes())
            if safe: self.assertEqual(saved, packet)
            return safe, packet or saved, failure, world

    def test_six_native_sends_real_login_owner_ui_only_settings_and_private_packet(self):
        safe, packet, failure, world = self.exercise()
        self.assertIsNone(failure)
        self.assertEqual(len(safe['calls']), 6); self.assertEqual(len(world.updates), 4)
        self.assertEqual(len({c['chat_id'] for c in packet['calls']}), 6)
        for call, (_, model, outcome) in zip(packet['calls'], B.CASES):
            self.assertEqual(call['model'], model); self.assertNotIn('chat_id', call['submitted'])
            self.assertEqual(call['chat_id'], call['acknowledgement']['chat_id'])
            self.assertEqual(call['http_status'], 200); self.assertEqual(call['task_ids'], [])
            self.assertEqual(call['visible_status'], None if outcome == 'denied' else B.UNKNOWN if outcome == 'unknown' else B.KNOWN + ' · на 13:00:00 UTC')
            self.assertIsInstance(call['visible_error'], str if outcome == 'denied' else type(None))
            self.assertIn(B.BLOCKED if outcome == 'denied' else 'Proof', call['visible_text'])
        self.assertEqual(packet['office_settings_before'], packet['office_settings_after'])
        self.assertEqual(packet['foreign_chat_status'], 404)
        self.assertFalse(safe['provider_dispatch_accepted']); self.assertFalse(safe['native_accounting_accepted'])
        for secret in ('synthetic-password', world.actor['token'], world.office['token']): self.assertNotIn(secret, json.dumps(safe))

    def test_successful_settings_ack_cannot_replace_effective_readback(self):
        safe, packet, failure, world = self.exercise(lambda w: setattr(w, 'ignored_update', True))
        self.assertIsNone(safe); self.assertIsNotNone(failure); self.assertEqual(world.chats, {})
        self.assertIn('effective preference', packet['failure']['message'])

    def test_visible_unknown_amount_is_rejected_and_full_dom_text_retained(self):
        def mutation(key, text):
            return text + ' $0.00' if key.startswith('#message-') and B.UNKNOWN in text else text
        safe, packet, failure, _ = self.exercise(lambda w: setattr(w, 'visible_mutation', mutation))
        self.assertIsNone(safe); self.assertIsNotNone(failure)
        self.assertEqual(packet['calls'][-1]['visible_status'], B.UNKNOWN)
        self.assertEqual(packet['calls'][-1]['visible_text'], 'Proof ' + B.UNKNOWN + ' $0.00')
        self.assertIn('contradictory expense', packet['failure']['message'])

    def test_visible_unknown_or_known_provisional_cost_text_is_not_completed_feedback(self):
        for outcome, suffix in (('unknown', ' · начислено на сейчас, учёт обновляется'),
                                ('unknown', ' · Стоимость ещё не подтверждена журналом учёта.'),
                                ('known', ' · provisional cost')):
            with self.subTest(outcome=outcome, suffix=suffix):
                def mutation(key, text):
                    selected = B.UNKNOWN in text if outcome == 'unknown' else B.KNOWN in text
                    return text + suffix if key.startswith('#message-') and selected else text
                safe, packet, failure, _ = self.exercise(lambda w: setattr(w, 'visible_mutation', mutation))
                self.assertIsNone(safe); self.assertIsNotNone(failure)
                self.assertTrue(packet['calls'][-1]['visible_text'].endswith(suffix))
                self.assertIn('contradicts', packet['failure']['message'])

    def test_failed_stream_submission_retains_full_actual_attempt_and_ack(self):
        safe, packet, failure, world = self.exercise(lambda w: setattr(w, 'submit_mutation', lambda sent: sent.update(stream=True)))
        self.assertIsNone(safe); self.assertIsNotNone(failure)
        self.assertEqual(len(packet['calls']), 1)
        call = packet['calls'][0]
        self.assertEqual(call['submitted'], world.sent)
        self.assertIs(call['submitted']['stream'], True)
        self.assertEqual(call['http_status'], 200)
        self.assertEqual(call['acknowledgement'], world.last.value)

    def test_failed_ack_binding_and_http_error_retain_private_actual_payloads(self):
        def wrong_chat(w):
            w.submit_mutation = lambda sent: sent.update(chat_id=OTHER)
        for mutate in (wrong_chat, lambda w: setattr(w, 'ack_status', 503),
                       lambda w: setattr(w, 'ack_mutation', lambda ack: ack.update(chat_id='not-native-id'))):
            with self.subTest(mutate=mutate):
                safe, packet, failure, world = self.exercise(mutate)
                self.assertIsNone(safe); self.assertIsNotNone(failure)
                self.assertEqual(len(packet['calls']), 1)
                self.assertEqual(packet['calls'][0]['submitted'], world.sent)
                self.assertEqual(packet['calls'][0]['http_status'], world.last.status)
                if world.last.status == 200:
                    self.assertEqual(packet['calls'][0]['acknowledgement'], world.last.value)
                else:
                    self.assertEqual(json.loads(packet['calls'][0]['response_body']), world.last.value)

    def test_stream_context_background_and_selection_mutations_stop_before_native_polling(self):
        mutations = [lambda s: s.update(stream=True), lambda s: s.update(model='foreign'),
            lambda s: s['background_tasks'].update(tags_generation=True), lambda s: s['background_tasks'].pop('title_generation'),
            lambda s: s.update(messages=[{'role': 'system', 'content': 'invented'}]),
            lambda s: s['user_message'].update(parentId=OTHER), lambda s: s['user_message'].update(content='different'),
            lambda s: s.update(tool_ids=['foreign-tool']), lambda s: s['message_ids'][0].update(message_id=OTHER)]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                safe, _, failure, _ = self.exercise(lambda w: setattr(w, 'submit_mutation', mutation))
                self.assertIsNone(safe); self.assertIsNotNone(failure)

    def test_forged_saved_owner_ancestry_error_and_unknown_amount_reject(self):
        def answer(stored): return stored['chat']['history']['messages'][stored['chat']['history']['currentId']]
        mutations = [lambda s: s.update(user_id=OTHER), lambda s: answer(s).update(parentId=OTHER),
            lambda s: answer(s).update(user_id=OTHER), lambda s: answer(s).update(model='foreign'),
            lambda s: answer(s).update(error={'content': 'failed'}),
            lambda s: answer(s)['output'][0]['content'][0].update(text='fabricated'),
            lambda s: answer(s)['statusHistory'][0].update(description=B.KNOWN + ' · на 13:00:00 UTC · начислено на сейчас')]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                safe, _, failure, _ = self.exercise(lambda w: setattr(w, 'saved_mutation', mutation))
                self.assertIsNone(safe); self.assertIsNotNone(failure)
        def wrong_unknown(stored):
            if answer(stored)['model'].endswith('-absent'):
                answer(stored)['statusHistory'][0]['description'] = B.UNKNOWN + ' $0.00'
        self.assertIsNotNone(self.exercise(lambda w: setattr(w, 'saved_mutation', wrong_unknown))[2])

    def test_not_done_active_tasks_and_foreign_visibility_are_not_terminal_success(self):
        for mutation in (lambda w: setattr(w, 'active', True),
                         lambda w: setattr(w, 'saved_mutation', lambda s: s['chat']['history']['messages'][s['chat']['history']['currentId']].update(done=False))):
            safe, packet, failure, _ = self.exercise(mutation, iter([0, 1000]).__next__)
            self.assertIsNone(safe); self.assertIsNotNone(failure)
            self.assertIn('did not finish', packet['failure']['message'])
        self.assertIsNotNone(self.exercise(lambda w: setattr(w, 'foreign_status', 200))[2])

    def test_native_response_status_size_origin_and_json_bounds(self):
        for response in (Response(BASE + '/x', {}, 503), Response('https://foreign.invalid/x', {}),
                         Response(BASE + '/x', [])):
            with self.assertRaises(AssertionError): B.response_json(response, BASE, '/x')
        response = Response(BASE + '/x', {}); response.body = lambda: b'x' * (B.MAX_BYTES + 1)
        with self.assertRaises(AssertionError): B.response_json(response, BASE, '/x')
        response.body = lambda: b'not-json'
        with self.assertRaises(AssertionError): B.response_json(response, BASE, '/x')

    def test_personal_setting_delta_preserves_nonempty_context_and_other_preferences(self):
        for before in (None, {'ui': None}, {'ui': {}}):
            B.settings_preserved(before, {'ui': {'system': None, 'params': {'stream_response': False},
                'title': {'auto': False}, 'autoTags': False, 'autoFollowUps': False}})
        before = {'ui': {'system': 'Preserve this policy', 'params': {'temperature': 0.4}, 'other': True}}
        for mutate in (lambda s: s['ui'].update(system=None), lambda s: s['ui']['params'].update(temperature=0.9),
                       lambda s: s['ui'].update(other=False)):
            after = copy.deepcopy(before); mutate(after)
            with self.assertRaises(AssertionError): B.settings_preserved(before, after)

    def test_native_frontend_stream_settings_and_fresh_send_serialization(self):
        source = Path(os.environ.get('GOAL584_FRONTEND_SOURCE_ROOT', str(HERE.parents[1] / 'local/goal584/cost-display/open-webui/src')))
        if not source.exists(): self.skipTest('Exact native frontend cache unavailable')
        if not shutil.which('node'): self.skipTest('Node unavailable for actual native frontend expression replay')
        chat = (source / 'lib/components/chat/Chat.svelte').read_text(encoding='utf8')
        advanced = (source / 'lib/components/chat/Settings/Advanced/AdvancedParams.svelte').read_text(encoding='utf8')
        general = (source / 'lib/components/chat/Settings/General.svelte').read_text(encoding='utf8')
        interface = (source / 'lib/components/common/InterfaceSettings.svelte').read_text(encoding='utf8')
        modal = (source / 'lib/components/chat/SettingsModal.svelte').read_text(encoding='utf8')
        stream = re.search(r'const stream =\s*(.*?);', chat, re.S)[1]
        toggle = re.search(r'params.stream_response =\s*(.*?);', advanced, re.S)[1]
        background = chat.split('background_tasks: {', 1)[1].split('\n\t\t\t\t}', 1)[0]
        title = interface.split('const toggleTitleAutoGenerate = async () => {', 1)[1].split('\n\t};', 1)[0]
        script = '''const $settings={params:{stream_response:false},title:{auto:false},autoTags:false,autoFollowUps:false};
const model={info:{params:{}}}, params={stream_response:null};
const $temporaryChatEnabled=false,_chatId=null,embedded=false,userMessage={parentId:null};
const _history={},responseMessageId='native-answer',createMessagesList=()=>[];
const stream=STREAM;
const body=JSON.parse(JSON.stringify({stream,chat_id:_chatId||undefined,background_tasks:{BACKGROUND}}));
const cycle=[];for(let i=0;i<3;i++){params.stream_response=TOGGLE;cycle.push(params.stream_response);}
let submitted;const saveSettings=v=>submitted=v,currentSettings={title:{other:'preserved'}},titleAutoGenerate=false;
(async()=>{TITLE;console.log(JSON.stringify({body,cycle,submitted}));})();'''
        for key, value in [('STREAM', stream), ('BACKGROUND', background), ('TOGGLE', toggle), ('TITLE', title)]: script = script.replace(key, value)
        result = subprocess.run(['node', '-e', script], capture_output=True, timeout=10, check=True)
        replay = json.loads(result.stdout)
        self.assertEqual(replay['body'], {'stream': False, 'background_tasks': {'title_generation': False, 'tags_generation': False, 'follow_up_generation': False}})
        self.assertEqual(replay['cycle'], [True, False, None])
        self.assertEqual(replay['submitted'], {'title': {'other': 'preserved', 'auto': False}})
        self.assertIn('stream_response: params.stream_response !== null ? params.stream_response : undefined', general)
        self.assertIn("saveSettings({ autoFollowUps });", interface); self.assertIn('saveSettings({ autoTags });', interface)
        self.assertIn("ui: updated", modal)
        self.assertIn('ariaLabelledbyId="auto-generation-label"', interface)
        self.assertIn('ariaLabelledbyId="follow-up-auto-generation-label"', interface)
        self.assertIn('ariaLabelledbyId="chat-tags-label"', interface)
        general_save = modal.split('<General', 1)[1].split('/>', 1)[0]
        self.assertIn('Settings saved successfully!', general_save)
        self.assertNotIn('show = false', general_save)


if __name__ == '__main__': unittest.main()
