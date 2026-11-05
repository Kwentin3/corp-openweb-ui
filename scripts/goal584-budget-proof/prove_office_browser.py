"""Finite host caller on an already prepared disposable OfficeFixture.

Returns (safe receipt, private native inputs). The caller retains the second
value privately for the independent Office/context/finance collector. No model
or Tool loop, provisioning, accounting calculation, or Office acceptance here.
"""
from __future__ import annotations

import hashlib
import re
import time
from urllib.parse import urlsplit
from uuid import uuid4

from playwright.sync_api import expect

from office_fixture import OfficeFixture
from prove_gateway_auth import private_parent, write_private
from prove_office_compatibility import MODEL, OUTPUT_NAME, SOURCE, SOURCE_SHA256, USER_REQUEST, digest
from prove_pricing_browser import MAX_BYTES, no_credentials
from prove_webui_browser import login, require, text_content


COST = '\u041e\u0442\u0432\u0435\u0442: $0.60 \u00b7 \u0427\u0430\u0442: $0.60'
DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


def native_id(value):
    require(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value),
            'Office native identifier unavailable')
    return value


def seed_form(source_id):
    """Pinned ChatForm wrapper and Chat.svelte history representation, no inference."""
    native_id(source_id)
    question_id = str(uuid4())
    question = {'id': question_id, 'parentId': None, 'childrenIds': [source_id], 'role': 'user',
        'content': 'Prepare the complete original proposal.', 'timestamp': int(time.time())}
    message = {'id': source_id, 'parentId': question_id, 'childrenIds': [], 'role': 'assistant',
        'content': SOURCE, 'model': MODEL, 'modelName': MODEL, 'modelIdx': 0, 'done': True,
        'timestamp': int(time.time())}
    return {'chat': {'title': 'GOAL584 Office compatibility', 'models': [MODEL], 'params': {},
        'history': {'currentId': source_id, 'messages': {question_id: question, source_id: message}},
        'messages': [question, message], 'tags': [], 'timestamp': int(time.time() * 1000)}, 'folder_id': None}


def check_submission(sent, chat_id, source_id):
    user = sent.get('user_message')
    require(sent.get('chat_id') == chat_id and sent.get('model') == MODEL
            and isinstance(user, dict) and user.get('role') == 'user' and user.get('parentId') == source_id
            and text_content(user.get('content')) == USER_REQUEST
            and sent.get('background_tasks', {}).get('follow_up_generation') is True,
            'Office UI submitted a different native turn/model/task')
    native_id(user.get('id'))
    return native_id(sent.get('id'))


def observed_answer(stored, actor_id, source_id, user_id, answer_id):
    require(stored.get('user_id') == actor_id, 'Office saved chat owner differs')
    messages = stored.get('chat', {}).get('history', {}).get('messages', {})
    source, user, answer = (messages.get(key, {}) for key in (source_id, user_id, answer_id))
    require(source.get('role') == 'assistant' and source.get('content') == SOURCE, 'Office saved source differs')
    if not user or not answer: return None
    require(user.get('role') == 'user' and user.get('parentId') == source_id
            and text_content(user.get('content')) == USER_REQUEST
            and answer.get('role') == 'assistant' and answer.get('parentId') == user_id,
            'Office saved source/turn ancestry differs')
    require(not answer.get('error'), 'Office native answer failed')
    statuses = [v for v in answer.get('statusHistory', []) if v.get('action') == 'employee_budget_cost']
    followups = answer.get('followUps')
    ready = (answer.get('done') is True and statuses and statuses[-1].get('done') is True
        and statuses[-1].get('description', '').startswith(COST + ' \u00b7 ') and isinstance(followups, list) and bool(followups)
        and all(isinstance(v, str) and v.strip() for v in followups))
    return answer if ready else None


def run(browser, fixture: OfficeFixture, base_url, build_receipt, expected_revision):
    """One ordinary Send; fixture.prepare must already have completed in this job."""
    running = fixture.running_readback(base_url, build_receipt, expected_revision)
    office_raw, state = fixture._office_private('office-state.private.json')
    _, common = fixture._office_private('webui-state.private.json')
    require(state.get('stage') == 'setup_complete'
            and state.get('office_service_setup', {}).get('stage') == 'readback_ready', 'Office is not prepared')
    for phase in ('office-setup', 'office-service-setup'):
        _, receipt = fixture._office_private(phase + '.safe.json')
        require(receipt.get('phase') == phase and receipt.get('passed') is True
                and receipt.get('inference_issued') is False and receipt.get('native_office_accepted') is False,
                'Office preparation receipt differs')
    actor = state['users'][0]
    other = next((u for u in common['users'] if u['id'] != actor['id']), None)
    require(other is not None and other['id'] != state['admin']['id'], 'Office foreign ordinary user unavailable')
    actor_id = native_id(actor['id'])
    paths = {name: fixture.private / ('office-browser.' + suffix) for name, suffix in
        (('browser', 'docx'), ('native', 'native.docx'), ('screenshot', 'png'), ('packet', 'private.json'))}
    require(all(not p.exists() and not p.is_symlink() and p.resolve().parent == fixture.private.resolve()
                for p in paths.values()), 'Office browser private output already exists or escaped')
    private_parent(paths['packet'])
    existing_contexts = set(browser.contexts)
    try:
        context, page, token = login(browser, base_url, actor)
        headers = {'Authorization': 'Bearer ' + token}
        source_id = str(uuid4()); form = seed_form(source_id)
        created = context.request.post(base_url + '/api/v1/chats/new', headers=headers, data=form, timeout=10_000)
        require(created.status == 200, 'Office native seed creation failed')
        seeded = created.json(); chat_id = native_id(seeded.get('id'))
        require(seeded.get('user_id') == actor_id and seeded.get('chat') == form['chat'], 'Office native seed readback differs')
        page.goto(base_url + '/c/' + chat_id, wait_until='domcontentloaded')
        expect(page.locator('#chat-input')).to_be_visible()
        selector = page.locator('button[id^="model-selector-"][aria-haspopup="listbox"]').first
        expect(selector).to_have_attribute('aria-label', 'Selected model: ' + MODEL)
        page.locator('#chat-input').fill(USER_REQUEST)
        with page.expect_response(lambda r: urlsplit(r.url).path == '/api/chat/completions'
                and r.request.method == 'POST', timeout=45_000) as pending:
            page.locator('#send-message-button').click()
        response = pending.value; sent = response.request.post_data_json
        answer_id = check_submission(sent, chat_id, source_id); user_id = sent['user_message']['id']
        require(response.status == 200, 'Office native Send was rejected')
        acknowledgement = response.json()
        require(acknowledgement.get('chat_id', chat_id) == chat_id, 'Office native acknowledgement changed chat')
        deadline = time.monotonic() + 180
        while True:
            observed = context.request.get(base_url + '/api/v1/chats/' + chat_id, headers=headers, timeout=10_000)
            require(observed.status == 200, 'Office native saved chat unavailable')
            stored = observed.json()
            answer = observed_answer(stored, actor_id, source_id, user_id, answer_id)
            tasks = context.request.get(base_url + '/api/tasks/chat/' + chat_id, headers=headers, timeout=10_000)
            require(tasks.status == 200 and isinstance(tasks.json().get('task_ids'), list), 'Office task readback failed')
            if answer is not None and tasks.json()['task_ids'] == []: break
            require(time.monotonic() < deadline, 'Office answer/cost/follow-up lifecycle did not complete')
            page.wait_for_timeout(250)
        files = [v for v in answer.get('files', []) if v.get('type') == 'file' and v.get('name') == OUTPUT_NAME]
        require(len(files) == 1, 'Office native DOCX attachment missing or ambiguous')
        attachment = files[0]; file_id = native_id(attachment.get('id'))
        path = '/api/v1/files/' + file_id; content_path = path + '/content'
        require(attachment.get('url') == file_id and attachment.get('content_type') == DOCX
                and isinstance(answer.get('content'), str) and content_path in answer['content'], 'Office attachment identity differs')
        metadata = context.request.get(base_url + path, headers=headers, timeout=10_000)
        require(metadata.status == 200, 'Office native file metadata unavailable')
        file = metadata.json()
        require(file.get('id') == file_id and file.get('user_id') == actor_id
                and file.get('meta', {}).get('name') == OUTPUT_NAME, 'Office native file owner/name differs')
        native = context.request.get(base_url + content_path, headers=headers, timeout=15_000)
        require(native.status == 200, 'Office owner native download failed')
        raw = native.body(); require(0 < len(raw) <= MAX_BYTES, 'Office native DOCX size outside bound')
        with paths['native'].open('xb') as output: output.write(raw)
        paths['native'].chmod(0o600)
        card = page.locator('#message-' + answer_id)
        expect(card).to_contain_text(COST, timeout=25_000)
        with page.expect_download(timeout=30_000) as pending_download:
            card.locator('a[href="' + content_path + '"]').click()
        download = pending_download.value
        target = urlsplit(download.url)
        require(target.scheme == urlsplit(base_url).scheme and target.netloc == urlsplit(base_url).netloc
                and target.path == content_path and not target.query and not target.fragment
                and download.suggested_filename == OUTPUT_NAME and download.failure() is None,
                'Office browser download origin/name/outcome differs')
        download.save_as(paths['browser']); paths['browser'].chmod(0o600)
        require(paths['browser'].stat().st_size == len(raw) and paths['browser'].read_bytes() == raw,
                'Office browser and independent native bytes differ')
        foreign, _, foreign_token = login(browser, base_url, other)
        denied = [foreign.request.get(base_url + p, headers={'Authorization': 'Bearer ' + foreign_token},
                  timeout=10_000).status for p in (path, content_path)]
        require(denied == [404, 404], 'Office file leaked to another ordinary user')
        page.screenshot(path=str(paths['screenshot']), full_page=False); paths['screenshot'].chmod(0o600)
        packet = {'schema': 1, 'chat_id': chat_id, 'answer_id': answer_id,
            'source_message_id': source_id, 'file_id': file_id}
        write_private(paths['packet'], packet)
        safe = {'schema': 1, 'status': 'browser_observed', 'native_office_accepted': False,
            'actor_id': actor_id, 'source_message_id': source_id, 'chat_id': chat_id, 'user_message_id': user_id,
            'message_id': answer_id, 'model': MODEL, 'file_id': file_id, 'outcome': 'success',
            'terminal_persisted': True, 'native_cost_status': True, 'follow_up_count': len(answer['followUps']),
            'foreign_file_statuses': denied, 'source_sha256': SOURCE_SHA256, 'submit_sha256': digest(sent),
            'docx_sha256': hashlib.sha256(raw).hexdigest(), 'screenshot_sha256': hashlib.sha256(paths['screenshot'].read_bytes()).hexdigest(),
            'prepared_handoff_sha256': hashlib.sha256(office_raw).hexdigest(), 'running_sha256': digest(running)}
        no_credentials(safe, fixture.secrets)
        private = {'schema': 1, 'seed_form': form, 'seeded': seeded, 'submission': sent,
            'acknowledgement': acknowledgement, 'stored_chat': stored, 'native_file': file,
            'running': running, 'paths': {k: str(v) for k, v in paths.items()}}
        return safe, private
    finally:
        for context in reversed(browser.contexts):
            if context not in existing_contexts: context.close()
