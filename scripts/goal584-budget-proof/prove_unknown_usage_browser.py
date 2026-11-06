"""Six ordinary Sends through the native whole-provider-response profile.

Host/browser observation only. Native models/settings/chat persistence and the
separate collector own authorization, accounting, provider dispatch and policy.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import time
from urllib.parse import urlsplit

from playwright.sync_api import expect

from office_fixture import OfficeFixture
from prove_gateway_auth import private_parent, write_private
from prove_office_browser import native_id
from prove_office_compatibility import digest
from prove_pricing_browser import MAX_BYTES, no_credentials
from prove_webui_browser import login, require, text_content


UNKNOWN_GUI_STATE = 'unknown-usage-gui-state.private.json'
SETTINGS = '/api/v1/users/user/settings'
UNKNOWN = 'Расход неизвестен. Обратитесь к администратору.'
KNOWN = 'Ответ: $0.166 · Чат: $0.166'
BLOCKED = 'Authentication Error, Доступ заблокирован. Обратитесь к администратору.'
CHAT_NOT_FOUND = "We could not find what you're looking for :/"
PROVISIONAL_COST_TEXT = ('учёт обновляется', 'учет обновляется', 'начислено на сейчас',
                         'стоимость ещё не подтверждена', 'стоимость еще не подтверждена',
                         'pending cost', 'cost pending', 'partial cost', 'provisional cost')
CASES = (('known-before', 'goal584-usage', 'known'),
         ('absent', 'goal584-usage-absent', 'unknown'),
         ('absent-denied', 'goal584-usage-absent', 'denied'),
         ('null', 'goal584-usage-null', 'unknown'),
         ('null-denied', 'goal584-usage-null', 'denied'),
         ('known-after', 'goal584-usage', 'known'))


def same_origin(url, base_url, path):
    target, base = urlsplit(url), urlsplit(base_url)
    return (target.scheme, target.netloc, target.path) == (base.scheme, base.netloc, path)


def response_json(response, base_url, path, *, nullable=False):
    require(response.status == 200 and same_origin(response.url, base_url, path),
            'Unknown GUI native response origin/status differs')
    try:
        raw = response.body()
        require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_BYTES, 'Unknown GUI response body exceeded bound')
        value = json.loads(raw)
    except (ValueError, UnicodeError):
        raise AssertionError('Unknown GUI native response JSON unavailable') from None
    require(isinstance(value, dict) or nullable and value is None, 'Unknown GUI native response is not an object')
    return value


def read(context, base_url, token, path):
    return response_json(context.request.get(base_url + path,
        headers={'Authorization': 'Bearer ' + token}, timeout=10_000), base_url, urlsplit(path).path,
        nullable=urlsplit(path).path == SETTINGS)


def setting(settings, path):
    value = (settings or {}).get('ui', {})
    for part in path.split('.'):
        value = value.get(part) if isinstance(value, dict) else None
    return value


def settings_preserved(before, after):
    def normalized(value):
        value = copy.deepcopy(value or {})
        ui = value.get('ui') or {}
        for field in ('autoTags', 'autoFollowUps'): ui.pop(field, None)
        for parent, field in (('title', 'auto'), ('params', 'stream_response')):
            if isinstance(ui.get(parent), dict): ui[parent].pop(field, None)
        # General's native Save serializes unset system as null and may create
        # empty containers. Do not mistake those native representations for a
        # changed nonempty system prompt/parameter or another personal setting.
        def prune(v):
            if isinstance(v, dict): return {k: clean for k, item in v.items()
                if (clean := prune(item)) is not None and clean != {}}
            return v
        return prune(value)
    require(normalized(before) == normalized(after), 'Unknown GUI changed unrelated actor settings')


def configure_settings(page, base_url, token, packet):
    before = read(page.context, base_url, token, SETTINGS)
    packet['settings_before'] = before
    packet['settings_raw_before'] = read(page.context, base_url, token, SETTINGS + '?raw=true')
    packet['settings_updates'] = []
    def open_settings(tab):
        page.get_by_role('button', name='User menu', exact=True).first.click()
        page.get_by_role('button', name='Settings', exact=True).click()
        page.locator('#settings-tabs-container [role="tab"][aria-controls="tab-' + tab + '"]').click()
        panel = page.locator('#tab-' + tab)
        expect(panel).to_be_visible()
        return panel
    def update(action, path, expected=False):
        with page.expect_response(lambda r: same_origin(r.url, base_url, SETTINGS + '/update')
                and r.request.method == 'POST', timeout=30_000) as pending:
            action()
        response = pending.value
        acknowledged = response_json(response, base_url, SETTINGS + '/update')
        submitted = response.request.post_data_json
        require(isinstance(submitted, dict) and setting(submitted, path) is expected,
                'Unknown GUI visible settings control submitted a different preference')
        effective = read(page.context, base_url, token, SETTINGS)
        require(setting(acknowledged, path) is expected and setting(effective, path) is expected,
                'Unknown GUI settings acknowledgement did not change its effective preference')
        packet['settings_updates'].append({'submitted': submitted, 'acknowledged': acknowledged, 'effective': effective})
    panel = open_settings('general')
    panel.get_by_role('button', name='Show', exact=True).click()
    stream = panel.get_by_text('Stream Chat Response', exact=True).locator('..').get_by_role('button')
    for _ in range(2):
        if stream.inner_text().strip() == 'On': break
        require(stream.inner_text().strip() in ('Default', 'Off'), 'Unknown GUI streaming preference control differs')
        stream.click()
    expect(stream).to_have_text('On')
    update(lambda: panel.get_by_role('button', name='Save', exact=True).click(), 'params.stream_response', True)
    # Native General Save shows a toast and keeps Settings open.
    page.locator('#settings-tabs-container [role="tab"][aria-controls="tab-interface"]').click()
    panel = page.locator('#tab-interface')
    expect(panel).to_be_visible()
    for label, path in (('auto-generation-label', 'title.auto'),
                        ('follow-up-auto-generation-label', 'autoFollowUps'), ('chat-tags-label', 'autoTags')):
        control = panel.locator('[role="switch"][aria-labelledby="' + label + '"]')
        expect(control).to_be_visible()
        checked = control.get_attribute('aria-checked')
        require(checked in ('true', 'false'), 'Unknown GUI task preference control differs')
        if checked == 'true': update(control.click, path)
        expect(control).to_have_attribute('aria-checked', 'false')
    page.locator('#settings-tabs-container').get_by_role('button', name='Back', exact=True).click()
    after = read(page.context, base_url, token, SETTINGS)
    require(setting(after, 'params.stream_response') is True and all(setting(after, key) is False for key in
                ('title.auto', 'autoTags', 'autoFollowUps')),
            'Unknown GUI effective personal preferences differ')
    settings_preserved(before, after)
    packet['settings_after'] = after
    packet['settings_raw_after'] = read(page.context, base_url, token, SETTINGS + '?raw=true')


def submission(sent, model):
    require(isinstance(sent, dict) and sent.get('model') == model and sent.get('stream') is True,
            'Unknown GUI submitted model/stream differs')
    user = sent.get('user_message')
    require(isinstance(user, dict) and user.get('role') == 'user' and user.get('parentId') is None
            and text_content(user.get('content')) == 'Hi' and sent.get('parent_id') is None,
            'Unknown GUI submitted a different fresh native turn')
    require(sent.get('background_tasks') == {'title_generation': False, 'tags_generation': False,
                                            'follow_up_generation': False},
            'Unknown GUI submitted an enabled or ambiguous background task')
    require(not sent.get('messages') and not sent.get('assistant_message_id') and not sent.get('regeneration_prompt')
            and all(not sent.get(k) for k in ('tool_ids', 'skill_ids', 'tool_servers', 'files')),
            'Unknown GUI submitted unexpected history/tools/files')
    answer_id, user_id = native_id(sent.get('id')), native_id(user.get('id'))
    require(sent.get('message_ids') == [{'model_id': model, 'message_id': answer_id, 'modelIdx': 0}],
            'Unknown GUI native model/answer selection differs')
    return answer_id, user_id


def saved_answer(stored, actor_id, chat_id, answer_id, user_id, model, outcome):
    require(stored.get('id') == chat_id and stored.get('user_id') == actor_id,
            'Unknown GUI native chat identity/owner differs')
    chat = stored.get('chat', {}); history = chat.get('history', {}); messages = history.get('messages', {})
    require(isinstance(messages, dict) and set(messages) <= {user_id, answer_id},
            'Unknown GUI saved fresh chat has unexpected ancestry')
    if user_id not in messages or answer_id not in messages: return None
    user, answer = messages[user_id], messages[answer_id]
    require(chat.get('models') == [model] and history.get('currentId') == answer_id
            and user.get('id') == user_id and user.get('role') == 'user' and user.get('parentId') is None
            and user.get('childrenIds') == [answer_id] and text_content(user.get('content')) == 'Hi'
            and answer.get('id') == answer_id and answer.get('parentId') == user_id
            and answer.get('role') == 'assistant' and answer.get('model') == model
            and (answer.get('user_id') or stored['user_id']) == actor_id,
            'Unknown GUI saved native turn/model/owner differs')
    if answer.get('done') is not True: return None
    statuses = [s for s in answer.get('statusHistory', []) if isinstance(s, dict)
                and s.get('action') == 'employee_budget_cost']
    if outcome == 'denied':
        require(bool(answer.get('error')) and BLOCKED in json.dumps(answer['error'], ensure_ascii=False)
                and answer.get('content', '') != 'Proof' and not answer.get('output') and not statuses,
                'Unknown GUI repeat is not an explicit saved native key denial')
        return answer
    require(answer.get('error') is None, 'Unknown GUI successful answer has a saved error')
    output = answer.get('output')
    require(answer.get('content') in (None, '', 'Proof') and isinstance(output, list) and len(output) == 1
            and output[0].get('type') == 'message' and output[0].get('role', 'assistant') == 'assistant'
            and isinstance(output[0].get('content'), list) and len(output[0]['content']) == 1
            and output[0]['content'][0].get('type') == 'output_text' and output[0]['content'][0].get('text') == 'Proof'
            and not output[0]['content'][0].get('annotations'),
            'Unknown GUI saved native answer output differs')
    if not statuses: return None
    require(len(statuses) == 1 and statuses[0].get('done') is True, 'Unknown GUI cost status is ambiguous or incomplete')
    description = statuses[0].get('description')
    require(description == UNKNOWN if outcome == 'unknown' else
            isinstance(description, str) and re.fullmatch(re.escape(KNOWN) + r' · на \d{2}:\d{2}:\d{2} UTC', description),
            'Unknown GUI saved cost status differs or claims a partial amount')
    return answer


def run(browser, fixture: OfficeFixture, base_url, build_receipt, expected_revision):
    running = fixture.running_readback(base_url, build_receipt, expected_revision)
    raw, state = fixture._office_private(UNKNOWN_GUI_STATE)
    _, common = fixture._office_private('webui-state.private.json')
    _, office = fixture._office_private('office-state.private.json')
    require(state.get('stage') == 'setup_complete' and len(state.get('users', [])) == 1,
            'Unknown GUI handoff is not ready')
    actor = state['users'][0]; actor_id = native_id(actor['id'])
    require(actor_id not in {u['id'] for u in [common['admin'], *common['users'], *office['users']]},
            'Unknown GUI requires a separate fresh actor')
    packet = {'schema': 1, 'actor_id': actor_id, 'calls': [], 'running': running}
    target = fixture.private / 'unknown-usage-browser.private.json'
    screenshots = fixture.output / 'unknown-usage-browser'
    require(not target.exists() and not target.is_symlink() and not screenshots.exists(),
            'Unknown GUI browser evidence already exists')
    private_parent(target); screenshots.mkdir(parents=True)
    existing_contexts = set(browser.contexts)
    try:
        context, page, token = login(browser, base_url, actor)
        office_actor = office['users'][0]
        packet['office_settings_before'] = read(context, base_url, office_actor['token'], SETTINGS + '?raw=true')
        configure_settings(page, base_url, token, packet)
        seen = set(); safe_calls = []
        for label, model, outcome in CASES:
            page.goto(base_url + '/', wait_until='domcontentloaded')
            expect(page.locator('#chat-input')).to_be_visible()
            selector = page.locator('button[id^="model-selector-"][aria-haspopup="listbox"]').first
            selector.click(); page.locator('button[data-value="' + model + '"]').click()
            expect(selector).to_have_attribute('aria-label', 'Selected model: ' + model)
            page.locator('#chat-input').fill('Hi')
            with page.expect_response(lambda r: same_origin(r.url, base_url, '/api/chat/completions')
                    and r.request.method == 'POST', timeout=45_000) as pending:
                page.locator('#send-message-button').click()
            response = pending.value
            # Capture the actual attempt before any predicate can reject its
            # body or ACK. Failed evidence must not erase an already-sent call.
            call = {'model': model, 'submitted': None, 'http_status': response.status,
                    'visible_status': None, 'visible_error': None, 'visible_text': None}
            packet['calls'].append(call)
            raw_submit = getattr(response.request, 'post_data', None)
            if isinstance(raw_submit, str) and len(raw_submit.encode()) <= MAX_BYTES:
                call['submitted_raw'] = raw_submit
            sent = response.request.post_data_json
            call['submitted'] = sent
            try:
                acknowledgement = response_json(response, base_url, '/api/chat/completions')
            except Exception:
                # Diagnostics only; these bytes never make a failed ACK valid.
                try:
                    raw_response = response.body()
                    if isinstance(raw_response, bytes) and len(raw_response) <= MAX_BYTES:
                        call['response_body'] = raw_response.decode('utf8', 'replace')
                except Exception:
                    call['response_body_unavailable'] = True
                raise
            call['acknowledgement'] = acknowledgement
            answer_id, user_id = submission(sent, model)
            chat_id = native_id(acknowledgement.get('chat_id'))
            require(sent.get('chat_id', chat_id) == chat_id and chat_id not in seen,
                    'Unknown GUI native acknowledgement changed/reused chat')
            seen.add(chat_id)
            call['chat_id'] = chat_id
            deadline = time.monotonic() + 60
            while True:
                stored = read(context, base_url, token, '/api/v1/chats/' + chat_id)
                call['stored'] = stored
                answer = saved_answer(stored, actor_id, chat_id, answer_id, user_id, model, outcome)
                tasks = read(context, base_url, token, '/api/tasks/chat/' + chat_id).get('task_ids')
                require(isinstance(tasks, list), 'Unknown GUI native task list malformed')
                call.update(stored=stored, task_ids=tasks)
                if answer is not None and tasks == []: break
                require(time.monotonic() < deadline, 'Unknown GUI native saved/outlet/task lifecycle did not finish')
                page.wait_for_timeout(250)
            card = page.locator('#message-' + answer_id)
            if outcome == 'denied':
                expect(card).to_contain_text(BLOCKED)
            else:
                expect(card.locator('#response-content-container')).to_contain_text('Proof')
                description = next(s['description'] for s in answer['statusHistory'] if s.get('action') == 'employee_budget_cost')
                expect(card).to_contain_text(description)
                call['visible_status'] = description
            visible = card.inner_text()
            call['visible_text'] = visible
            if outcome == 'denied':
                call['visible_error'] = visible
            else:
                require(description in visible and not any(text in visible.casefold() for text in PROVISIONAL_COST_TEXT),
                        'Unknown GUI visible card contradicts its completed cost status')
                require('$' not in visible if outcome == 'unknown' else UNKNOWN not in visible,
                        'Unknown GUI visible card claims a contradictory expense')
            require('sk-' not in visible and 'owui-budget-v1-' not in visible, 'Unknown GUI feedback leaked an internal key')
            no_credentials(visible, list(fixture.secrets) + [token, actor['password'], office_actor['token']])
            image = screenshots / (label + '.png'); page.screenshot(path=str(image), full_page=False)
            safe_calls.append({'model': model, 'chat_id': chat_id, 'answer_id': answer_id, 'outcome': outcome,
                'terminal_persisted': True, 'tasks_empty': True, 'submit_sha256': digest(sent),
                'screenshot_sha256': hashlib.sha256(image.read_bytes()).hexdigest()})
        packet['office_settings_after'] = read(context, base_url, office_actor['token'], SETTINGS + '?raw=true')
        require(packet['office_settings_before'] == packet['office_settings_after'], 'Unknown GUI changed Office actor settings')
        other = common['users'][0]
        foreign, _, foreign_token = login(browser, base_url, other)
        headers = {'Authorization': 'Bearer ' + foreign_token}
        authenticated = foreign.request.get(base_url + '/api/v1/auths/', headers=headers, timeout=10_000)
        packet['foreign_auth'] = {'http_status': authenticated.status}
        packet['foreign_auth_confirmed'] = False
        session = response_json(authenticated, base_url, '/api/v1/auths/')
        packet['foreign_auth']['session'] = session
        require(session.get('id') == other['id'] and session.get('id') != actor_id and session.get('role') == 'user',
                'Unknown GUI foreign session identity/role differs')
        packet['foreign_auth_confirmed'] = True
        denied = foreign.request.get(base_url + '/api/v1/chats/' + packet['calls'][0]['chat_id'],
            headers=headers, timeout=10_000)
        packet['foreign_chat_status'] = denied.status
        require(same_origin(denied.url, base_url, '/api/v1/chats/' + packet['calls'][0]['chat_id']),
                'Unknown GUI foreign chat response origin differs')
        raw_denial = denied.body()
        require(isinstance(raw_denial, bytes) and 0 < len(raw_denial) <= MAX_BYTES,
                'Unknown GUI foreign chat response exceeded bound')
        denial = json.loads(raw_denial)
        packet['foreign_chat_detail'] = denial.get('detail') if isinstance(denial, dict) else None
        packet['foreign_chat_not_found'] = denied.status == 401 and packet['foreign_chat_detail'] == CHAT_NOT_FOUND
        # Native chat access uses 401/NOT_FOUND; Office file routes use 404.
        # The same fresh session/headers must first prove an authenticated user.
        require(packet['foreign_chat_not_found'], 'Unknown GUI saved chat native denial differs')
        safe = {'schema': 1, 'status': 'browser_observed', 'actor_id': actor_id, 'calls': safe_calls,
            'handoff_sha256': hashlib.sha256(raw).hexdigest(), 'running_sha256': digest(running),
            'foreign_chat_status': 401, 'foreign_chat_not_found': True, 'foreign_auth_confirmed': True,
            'office_settings_unchanged': True,
            'native_accounting_accepted': False, 'provider_dispatch_accepted': False, 'unknown_policy_accepted': False}
        no_credentials(safe, list(fixture.secrets) + [token, actor['password'], office_actor['token']])
        write_private(target, packet)
        return safe, packet
    except Exception as error:
        packet['failure'] = {'stage': 'browser_observation', 'type': type(error).__name__, 'message': str(error)[:2000]}
        write_private(target, packet)
        raise AssertionError('Unknown GUI browser observation failed; inspect private packet') from None
    finally:
        for context in reversed(browser.contexts):
            if context not in existing_contexts: context.close()
