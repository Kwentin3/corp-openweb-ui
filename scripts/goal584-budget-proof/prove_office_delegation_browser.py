"""One ordinary delegated Office Send on the already prepared disposable stand.

Returns (safe, private); the independent collector owns artifact/context/finance
acceptance. This caller never executes a Tool/model loop or computes a charge.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

from playwright.sync_api import expect

from mock_provider import DELEGATED_USER_REQUEST
from office_fixture import OfficeFixture
from prove_gateway_auth import private_parent, write_private
from prove_office_browser import DOCX, native_id
from prove_office_compatibility import digest
from prove_pricing_browser import MAX_BYTES, no_credentials
from prove_webui_browser import login, require, text_content


MODEL = 'corporate-documents'
PACKET = 'office-delegation-browser.private.json'
PHASES = ('login', 'source', 'create_chat', 'send', 'acknowledgement', 'lifecycle',
          'artifact', 'download', 'source_after', 'foreign_acl', 'success')
TASK_STATUSES = ('pending', 'in_progress', 'completed', 'cancelled', 'other')


def _mapping(value):
    return value if isinstance(value, dict) else {}


def failure_projection(packet):
    """Public technical observations only; never an Office/financial acceptance."""
    packet = _mapping(packet)
    stored = _mapping(packet.get('stored_chat'))
    messages = _mapping(_mapping(_mapping(stored.get('chat')).get('history')).get('messages'))
    user = messages.get(packet['user_message_id']) if isinstance(packet.get('user_message_id'), str) else None
    answer = messages.get(packet['answer_id']) if isinstance(packet.get('answer_id'), str) else None
    answer_present = isinstance(answer, dict)
    answer = _mapping(answer)
    tasks = stored.get('tasks')
    statuses = answer.get('statusHistory')
    costs = [value for value in statuses if isinstance(value, dict)
             and value.get('action') == 'employee_budget_cost'] if isinstance(statuses, list) else []
    files = answer.get('files')
    active = _mapping(packet.get('native_running')).get('task_ids')
    def boolean(value): return value if type(value) is bool else None
    observation = {
        'user_present': isinstance(user, dict),
        'answer_present': answer_present,
        'answer_done': boolean(answer.get('done')),
        'checklist_present': isinstance(tasks, list),
        'checklist_count': len(tasks) if isinstance(tasks, list) else None,
        'checklist_status_counts': {status: sum(1 for task in tasks
            if (task.get('status') if isinstance(task, dict) and task.get('status') in TASK_STATUSES[:-1]
                else 'other') == status) for status in TASK_STATUSES} if isinstance(tasks, list) else None,
        'budget_status_present': bool(costs),
        'budget_status_done': boolean(costs[-1].get('done')) if costs else None,
        'followups_count': len(answer['followUps']) if isinstance(answer.get('followUps'), list) else None,
        'native_task_ids_count': len(active) if isinstance(active, list) else None,
        'attachment_count': len(files) if isinstance(files, list) else None,
        'docx_count': sum(isinstance(value, dict) and value.get('type') == 'file'
                          and value.get('content_type') == DOCX for value in files) if isinstance(files, list) else None}
    # A size-bound checkpoint explicitly retains only these technical values.
    if packet.get('raw_omitted') is True:
        saved = _mapping(packet.get('lifecycle_observation'))
        for key, value in observation.items():
            candidate = saved.get(key)
            if key == 'checklist_status_counts':
                observation[key] = ({status: candidate[status] for status in TASK_STATUSES}
                    if isinstance(candidate, dict) and set(candidate) == set(TASK_STATUSES)
                    and all(type(number) is int and number >= 0 for number in candidate.values()) else None)
            elif key.endswith('_present') or key.endswith('_done'):
                observation[key] = boolean(candidate)
            else:
                observation[key] = candidate if type(candidate) is int and candidate >= 0 else None
    failure = packet.get('failure')
    phase = packet.get('phase') if packet.get('phase') in PHASES else None
    failure = failure if isinstance(failure, str) and re.fullmatch(r'delegated_browser_[a-z0-9_]{1,80}', failure) else None
    return {'schema': 1, 'collected': type(packet.get('schema')) is int and packet['schema'] == 1
            and packet.get('status') == 'failed' and phase is not None and failure is not None,
        'phase': phase, 'failure': failure,
        'raw_omitted': packet.get('raw_omitted') is True,
        'native_office_accepted': False, 'native_finance_qualified': False, **observation}


def _checkpoint(path, packet):
    """Use the existing atomic private writer, with its actual serialized bound."""
    size = len((json.dumps(packet, allow_nan=False) + '\n').encode('utf-8'))
    if size > MAX_BYTES or packet.get('raw_acknowledgement_omitted') is True:
        projection = failure_projection(packet)
        retained = {key: packet[key] for key in ('schema', 'status', 'phase', 'failure') if key in packet}
        for key in ('actor_id', 'chat_id', 'user_message_id', 'answer_id', 'source_file_id'):
            value = packet.get(key)
            if isinstance(value, str) and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value):
                retained[key] = value
        for key in ('browser_source_sha256', 'prepared_handoff_sha256', 'raw_acknowledgement_sha256'):
            value = packet.get(key)
            if isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value):
                retained[key] = value
        if type(packet.get('raw_acknowledgement_bytes')) is int:
            retained['raw_acknowledgement_bytes'] = packet['raw_acknowledgement_bytes']
        if packet.get('raw_acknowledgement_omitted') is True:
            retained['raw_acknowledgement_omitted'] = True
        if isinstance(packet.get('skill_id'), str) and re.fullmatch(r'[a-z0-9_-]+', packet['skill_id']):
            retained['skill_id'] = packet['skill_id']
        if isinstance(packet.get('error_class'), str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}', packet['error_class']):
            retained['error_class'] = packet['error_class']
        if isinstance(packet.get('native_skill'), dict):
            retained['native_skill_sha256'] = digest(packet['native_skill'])
        source = _mapping(packet.get('source_before'))
        if isinstance(source.get('sha256'), str) and re.fullmatch(r'[0-9a-f]{64}', source['sha256']) \
                and type(source.get('bytes')) is int and source['bytes'] >= 0 and source.get('status') == 200:
            retained['source_before'] = source
        retained.update(raw_omitted=True, raw_bytes=size,
                        lifecycle_observation={key: value for key, value in projection.items()
                            if key not in ('schema', 'collected', 'phase', 'failure', 'raw_omitted',
                                           'native_office_accepted', 'native_finance_qualified')})
        packet = retained
    require(len((json.dumps(packet, allow_nan=False) + '\n').encode('utf-8')) <= MAX_BYTES,
            'delegated_browser_packet_bound')
    write_private(path, packet)


def empty_form():
    """Native ChatForm wrapper with Chat.svelte's initial empty history."""
    return {'chat': {'title': 'GOAL584 delegated Office', 'models': [MODEL], 'params': {},
        'history': {'currentId': None, 'messages': {}}, 'messages': [], 'tags': [],
        'timestamp': int(time.time() * 1000)}, 'folder_id': None}


def user_request(skill_id):
    require(isinstance(skill_id, str) and re.fullmatch(r'[a-z0-9_-]+', skill_id),
            'delegated_browser_skill_id')
    return DELEGATED_USER_REQUEST + '\nNative Skill ID: ' + skill_id


def check_submission(sent, chat_id, request):
    require(isinstance(sent, dict) and sent.get('model') == MODEL and sent.get('chat_id') == chat_id,
            'delegated_browser_submission_model_chat')
    user = sent.get('user_message')
    require(isinstance(user, dict) and user.get('role') == 'user' and user.get('parentId') is None
            and text_content(user.get('content')) == request
            and isinstance(sent.get('background_tasks'), dict)
            and sent['background_tasks'].get('follow_up_generation') is True,
            'delegated_browser_submission_turn')
    return native_id(user.get('id')), native_id(sent.get('id'))


def observed_answer(stored, actor_id, chat_id, user_id, answer_id, request):
    require(isinstance(stored, dict) and stored.get('id') == chat_id and stored.get('user_id') == actor_id,
            'delegated_browser_chat_owner')
    messages = stored.get('chat', {}).get('history', {}).get('messages', {})
    user, answer = messages.get(user_id), messages.get(answer_id)
    if user is None or answer is None: return None
    require(user.get('role') == 'user' and user.get('parentId') is None
            and text_content(user.get('content')) == request
            and answer.get('role') == 'assistant' and answer.get('parentId') == user_id,
            'delegated_browser_saved_ancestry')
    require(not answer.get('error'), 'delegated_browser_answer_error')
    if answer.get('done') is not True: return None
    checklist = stored.get('tasks')
    if not isinstance(checklist, list) or not checklist: return None
    require(all(isinstance(task, dict) and isinstance(task.get('id'), str) and task['id']
                and isinstance(task.get('content'), str) and task['content'].strip()
                for task in checklist) and len({task['id'] for task in checklist}) == len(checklist),
            'delegated_browser_native_tasks_shape')
    if not all(task.get('status') == 'completed' for task in checklist): return None
    statuses = [value for value in answer.get('statusHistory', [])
                if isinstance(value, dict) and value.get('action') == 'employee_budget_cost']
    if not statuses or statuses[-1].get('done') is not True: return None
    description = statuses[-1].get('description')
    # Observe native accrued known cost; finance must prove all related rows.
    # Delegation keeps the existing explicit provisional label even after the
    # UI turn completes. A terminal widget is not financial settlement proof.
    require(isinstance(description, str) and re.fullmatch(
        r'Ответ: \$[0-9]+(?:\.[0-9]+)? · Чат: \$[0-9]+(?:\.[0-9]+)? · на [0-9]{2}:[0-9]{2}:[0-9]{2} UTC'
        r'(?: · начислено на сейчас, учёт обновляется)?', description),
        'delegated_browser_cost_not_known')
    followups = answer.get('followUps')
    if not isinstance(followups, list) or not followups: return None
    require(all(isinstance(value, str) and value.strip() for value in followups),
            'delegated_browser_followups_shape')
    return answer, statuses[-1]


def run(browser, fixture: OfficeFixture, base_url, build_receipt, expected_revision):
    running = fixture.running_readback(base_url, build_receipt, expected_revision)
    office_raw, state = fixture._office_private('office-state.private.json')
    _, common = fixture._office_private('webui-state.private.json')
    _, prepared = fixture._office_private('office-delegation-setup.safe.json')
    selected = state.get('office_delegation_setup', {})
    require(state.get('stage') == 'setup_complete' and selected.get('stage') == 'readback_ready'
            and prepared.get('phase') == 'office-delegation-setup' and prepared.get('passed') is True
            and prepared.get('inference_issued') is False and prepared.get('native_office_accepted') is False,
            'delegated_browser_not_prepared')
    actor, skill = selected['actor'], selected['skill']
    actor_id, source_id = native_id(actor['id']), native_id(selected['source_file']['id'])
    require(actor_id not in {entry['id'] for entry in [state['admin'], *state['users']]},
            'delegated_browser_actor_not_fresh')
    other = next((account for account in common['users'] if account['id'] != actor_id), None)
    require(other is not None and other['id'] != state['admin']['id'], 'delegated_browser_foreign_user')
    request = user_request(skill['id'])
    profile = selected.get('models', {}).get(MODEL, {})
    require(profile.get('base_model_id') == 'gpt-6.1-sol'
            and profile.get('meta', {}).get('builtinTools', {}).get('tasks') is True
            and isinstance(profile.get('name'), str) and bool(profile['name']),
            'delegated_browser_parent_profile')
    paths = {name: fixture.private / ('office-delegation-browser.' + suffix) for name, suffix in
             (('browser', 'docx'), ('native', 'native.docx'), ('screenshot', 'png'))}
    packet_path = fixture.private / PACKET
    require(all(not path.exists() and not path.is_symlink() and path.resolve().parent == fixture.private.resolve()
                for path in [*paths.values(), packet_path]), 'delegated_browser_output_conflict')
    private_parent(packet_path)
    existing_contexts = set(browser.contexts)
    checkpoint = {'schema': 1, 'status': 'observing', 'phase': 'login',
        'browser_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'actor_id': actor_id, 'source_file_id': source_id, 'skill_id': skill['id'],
        'prepared_handoff_sha256': hashlib.sha256(office_raw).hexdigest(), 'running': running}
    try:
        context, page, token = login(browser, base_url, actor)
        headers = {'Authorization': 'Bearer ' + token}
        def get(path):
            response = context.request.get(base_url + path, headers=headers, timeout=10_000)
            require(response.status == 200, 'delegated_browser_native_read')
            return response
        source_path = '/api/v1/files/' + source_id + '/content'
        checkpoint['phase'] = 'source'
        before = get(source_path).body()
        checkpoint['source_before'] = {'sha256': hashlib.sha256(before).hexdigest(),
            'bytes': len(before), 'status': 200} if isinstance(before, bytes) else None
        require(isinstance(before, bytes) and 0 < len(before) <= MAX_BYTES
                and hashlib.sha256(before).hexdigest() == selected.get('source_sha256'),
                'delegated_browser_source_before')
        native_skill = get('/api/v1/skills/id/' + skill['id']).json()
        checkpoint['native_skill'] = native_skill
        require(all(native_skill.get(key) == skill.get(key) for key in ('id', 'content', 'version_id', 'is_active'))
                and native_skill.get('is_active') is True and bool(native_skill.get('version_id')),
                'delegated_browser_skill_binding')
        form = empty_form()
        checkpoint.update(phase='create_chat', chat_form=form)
        created = context.request.post(base_url + '/api/v1/chats/new', headers=headers, data=form, timeout=10_000)
        require(created.status == 200, 'delegated_browser_chat_create')
        seeded = created.json()
        checkpoint['created_chat'] = seeded
        if isinstance(seeded, dict) and isinstance(seeded.get('id'), str) and re.fullmatch(
                r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', seeded['id']):
            checkpoint['chat_id'] = seeded['id']
        _checkpoint(packet_path, checkpoint)
        chat_id = native_id(seeded.get('id'))
        require(seeded.get('user_id') == actor_id and seeded.get('chat') == form['chat'],
                'delegated_browser_empty_chat_readback')
        page.goto(base_url + '/c/' + chat_id, wait_until='domcontentloaded')
        expect(page.locator('#chat-input')).to_be_visible()
        selector = page.locator('button[id^="model-selector-"][aria-haspopup="listbox"]').first
        expect(selector).to_have_attribute('aria-label', 'Selected model: ' + profile['name'])
        page.locator('#chat-input').fill(request)
        checkpoint['phase'] = 'send'
        with page.expect_response(lambda response: urlsplit(response.url).path == '/api/chat/completions'
                and response.request.method == 'POST', timeout=45_000) as pending:
            page.locator('#send-message-button').click()
        response = pending.value; sent = response.request.post_data_json
        checkpoint.update(submission=sent, submission_status=response.status)
        raw_user = _mapping(_mapping(sent).get('user_message'))
        for key, value in (('user_message_id', raw_user.get('id')), ('answer_id', _mapping(sent).get('id'))):
            if isinstance(value, str) and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value):
                checkpoint[key] = value
        # Preserve the wire acknowledgement before status/JSON/turn validation.
        raw_ack = response.body()
        checkpoint['raw_acknowledgement_bytes'] = len(raw_ack) if isinstance(raw_ack, bytes) else None
        if isinstance(raw_ack, bytes):
            checkpoint['raw_acknowledgement_sha256'] = hashlib.sha256(raw_ack).hexdigest()
            if len(raw_ack) <= MAX_BYTES:
                checkpoint['raw_acknowledgement_base64'] = base64.b64encode(raw_ack).decode('ascii')
            else:
                checkpoint['raw_acknowledgement_omitted'] = True
        _checkpoint(packet_path, checkpoint)
        user_id, answer_id = check_submission(sent, chat_id, request)
        checkpoint.update(user_message_id=user_id, answer_id=answer_id, phase='acknowledgement')
        require(response.status == 200, 'delegated_browser_send_rejected')
        acknowledgement = response.json()
        checkpoint['acknowledgement'] = acknowledgement
        require(acknowledgement.get('chat_id', chat_id) == chat_id, 'delegated_browser_ack_chat')
        deadline = time.monotonic() + 180
        checkpoint['phase'] = 'lifecycle'
        while True:
            stored = get('/api/v1/chats/' + chat_id).json()
            checkpoint['stored_chat'] = stored
            checkpoint['native_tasks'] = stored.get('tasks') if isinstance(stored, dict) else None
            observed = observed_answer(stored, actor_id, chat_id, user_id, answer_id, request)
            active = get('/api/tasks/chat/' + chat_id).json()
            checkpoint.update(background_tasks=active, native_running=active)
            require(isinstance(active.get('task_ids'), list), 'delegated_browser_background_tasks_shape')
            if observed is not None and not active['task_ids']: break
            require(time.monotonic() < deadline, 'delegated_browser_lifecycle_timeout')
            page.wait_for_timeout(250)
        answer, cost_status = observed
        checkpoint['phase'] = 'artifact'
        files = [value for value in answer.get('files', []) if isinstance(value, dict) and value.get('type') == 'file'
                 and value.get('content_type') == DOCX]
        require(len(files) == 1, 'delegated_browser_result_attachment')
        attachment = files[0]; file_id = native_id(attachment.get('id'))
        path = '/api/v1/files/' + file_id; content_path = path + '/content'
        require(file_id != source_id and attachment.get('url') == file_id
                and isinstance(attachment.get('name'), str) and attachment['name'].endswith('.docx')
                and content_path in text_content(answer.get('content')), 'delegated_browser_result_link')
        file = get(path).json()
        require(file.get('id') == file_id and file.get('user_id') == actor_id
                and file.get('meta', {}).get('name') == attachment['name'], 'delegated_browser_result_owner')
        raw = get(content_path).body()
        require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_BYTES, 'delegated_browser_result_size')
        with paths['native'].open('xb') as output: output.write(raw)
        paths['native'].chmod(0o600)
        card = page.locator('#message-' + answer_id)
        checkpoint['phase'] = 'download'
        expect(card).to_contain_text(cost_status['description'], timeout=25_000)
        with page.expect_download(timeout=30_000) as pending_download:
            card.locator('a[href="' + content_path + '"]').click()
        download = pending_download.value
        target, origin = urlsplit(download.url), urlsplit(base_url)
        require((target.scheme, target.netloc, target.path) == (origin.scheme, origin.netloc, content_path)
                and not target.query and not target.fragment and download.failure() is None
                and download.suggested_filename == attachment['name'], 'delegated_browser_download_origin')
        download.save_as(paths['browser']); paths['browser'].chmod(0o600)
        require(paths['browser'].stat().st_size == len(raw) and paths['browser'].read_bytes() == raw,
                'delegated_browser_download_bytes')
        checkpoint['phase'] = 'source_after'
        after = get(source_path).body()
        checkpoint['source_after'] = {'sha256': hashlib.sha256(after).hexdigest(),
            'bytes': len(after), 'status': 200} if isinstance(after, bytes) else None
        require(after == before, 'delegated_browser_source_changed')
        checkpoint['phase'] = 'foreign_acl'
        foreign, _, foreign_token = login(browser, base_url, other)
        denied = [foreign.request.get(base_url + target, headers={'Authorization': 'Bearer ' + foreign_token},
                  timeout=10_000).status for target in (path, content_path)]
        require(denied == [404, 404], 'delegated_browser_foreign_acl')
        page.screenshot(path=str(paths['screenshot']), full_page=False); paths['screenshot'].chmod(0o600)
        checkpoint['phase'] = 'success'
        private = {'schema': 1, 'actor_id': actor_id, 'chat_id': chat_id, 'user_message_id': user_id,
            'answer_id': answer_id, 'source_file_id': source_id, 'skill_id': skill['id'], 'file_id': file_id,
            'submission': sent, 'submission_status': response.status, 'acknowledgement': acknowledgement,
            'chat_form': form, 'created_chat': seeded, 'stored_chat': stored, 'native_file': file, 'running': running,
            'native_tasks': stored['tasks'], 'background_tasks': active, 'cost_status': cost_status,
            'native_running': active,
            'source_before_sha256': hashlib.sha256(before).hexdigest(), 'source_after_sha256': hashlib.sha256(after).hexdigest(),
            'source_before': {'sha256': hashlib.sha256(before).hexdigest(), 'bytes': len(before), 'status': 200},
            'source_after': {'sha256': hashlib.sha256(after).hexdigest(), 'bytes': len(after), 'status': 200},
            'artifacts': {'browser': {'sha256': hashlib.sha256(paths['browser'].read_bytes()).hexdigest(), 'bytes': paths['browser'].stat().st_size},
                'native': {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}},
            'native_skill': native_skill, 'foreign_file_statuses': denied,
            'paths': {key: str(value) for key, value in paths.items()}}
        require(len((json.dumps(private, allow_nan=False) + '\n').encode('utf-8')) <= MAX_BYTES,
                'delegated_browser_packet_bound')
        write_private(packet_path, private)
        safe = {'schema': 1, 'status': 'browser_observed', 'native_office_accepted': False, 'ordinary_sends': 1,
            'actor_id': actor_id, 'chat_id': chat_id, 'user_message_id': user_id, 'answer_id': answer_id,
            'source_file_id': source_id, 'skill_id': skill['id'], 'file_id': file_id, 'model': MODEL,
            'terminal_persisted': True, 'native_tasks_completed': len(stored['tasks']), 'background_tasks_empty': True,
            'follow_up_count': len(answer['followUps']), 'visible_cost_status': True, 'cost_status_sha256': digest(cost_status),
            'foreign_file_statuses': denied, 'source_unchanged': True, 'source_sha256': hashlib.sha256(before).hexdigest(),
            'docx_sha256': hashlib.sha256(raw).hexdigest(), 'submission_sha256': digest(sent),
            'prepared_handoff_sha256': hashlib.sha256(office_raw).hexdigest(), 'running_sha256': digest(running),
            'screenshot_sha256': hashlib.sha256(paths['screenshot'].read_bytes()).hexdigest()}
        no_credentials(safe, fixture.secrets)
        return safe, private
    except Exception as error:
        code = str(error)
        checkpoint.update(status='failed', failure=code if re.fullmatch(
            r'delegated_browser_[a-z0-9_]{1,80}', code) else 'delegated_browser_unclassified')
        checkpoint['error_class'] = type(error).__name__
        try:
            _checkpoint(packet_path, checkpoint)
        except Exception:
            # Diagnostics cannot replace the original fatal browser/native error.
            pass
        raise
    finally:
        for context in reversed(browser.contexts):
            if context not in existing_contexts: context.close()
