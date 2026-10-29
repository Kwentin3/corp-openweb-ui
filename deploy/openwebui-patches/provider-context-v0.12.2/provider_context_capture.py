"""Bounded, opt-in observation of the final native provider request body.

No request state is changed and no credentials or headers are accepted. This
Linux-only diagnostic is deliberately inactive without a protected capture.json.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import math
import os
import re
import stat
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

log = logging.getLogger(__name__)
DEFAULT_MAX_BYTES = 128 * 1024 * 1024
MAX_BYTES = 256 * 1024 * 1024
MAX_REQUESTS = 20
MAX_TTL_SECONDS = 3600
RECEIPT_FIELDS = (
    'captured_at', 'scope_chat_id', 'chat_id', 'message_id', 'task',
    'sub_agent_iteration', 'agent_kind', 'selected_model', 'provider_model',
    'round', 'host', 'path', 'bytes', 'sha256', 'parent_chat_id',
    'delegation_id', 'lineage_depth', 'previous_response_id_present',
    'provider_state',
)
_REQUEST_NAME = re.compile(r'^(\d{3})\.request\.json$')


def capture_root(root=None):
    if root is not None:
        return Path(root).absolute()
    from open_webui.env import DATA_DIR
    return Path(DATA_DIR).absolute() / 'forensics' / 'provider-context'


def _check(info, *, directory=False):
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if (not expected(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077
            or (not directory and info.st_nlink != 1)):
        raise PermissionError('Unprotected diagnostic storage')


@contextmanager
def protected_root(root=None, *, create=False):
    path = capture_root(root)
    # Open each component relative to its already opened parent. No ancestor
    # symlink can redirect a later read/write between validation and use.
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(path.anchor, flags)
    try:
        for part in path.parts[1:]:
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child_fd
        _check(os.fstat(fd), directory=True)
        yield fd
    finally:
        os.close(fd)


def _open_file(directory_fd, name, flags=os.O_RDONLY):
    fd = os.open(name, flags | os.O_NOFOLLOW, 0o600, dir_fd=directory_fd)
    try:
        _check(os.fstat(fd))
    except BaseException:
        os.close(fd)
        raise
    return fd


def _read_json(directory_fd, name):
    fd = _open_file(directory_fd, name)
    with os.fdopen(fd, 'r', encoding='utf-8') as stream:
        # Configuration and receipts are small. Bound accidental oversized input.
        data = stream.read(65537)
        if len(data) > 65536:
            raise ValueError('Diagnostic JSON too large')
        return json.loads(data)


def _write_file(directory_fd, name, data):
    fd = _open_file(directory_fd, name, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _atomic_json(directory_fd, name, value):
    temporary = f'.{name}.{uuid.uuid4().hex}.tmp'
    try:
        _write_file(directory_fd, temporary, json.dumps(value, ensure_ascii=True).encode('utf-8'))
        os.replace(temporary, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        os.fsync(directory_fd)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except FileNotFoundError:
            pass


@contextmanager
def storage_lock(directory_fd, name, *, create=True):
    fd = _open_file(directory_fd, name, os.O_RDWR | (os.O_CREAT if create else 0))
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _uuid(value):
    if not isinstance(value, str) or str(uuid.UUID(value)) != value:
        raise ValueError('Expected canonical UUID')
    return value


def validate_config(config, *, active=True):
    if not isinstance(config, dict):
        raise ValueError('Invalid capture configuration')
    _uuid(config['chat_id'])
    _uuid(config['run_id'])
    expires_at = config['expires_at']
    if (isinstance(expires_at, bool) or not isinstance(expires_at, (int, float))
            or not math.isfinite(expires_at)
            or expires_at > time.time() + MAX_TTL_SECONDS):
        raise ValueError('Invalid expiry')
    if active and expires_at <= time.time():
        raise ValueError('Expired capture')
    for key, default, maximum in (
        ('max_requests', MAX_REQUESTS, MAX_REQUESTS),
        ('max_bytes', DEFAULT_MAX_BYTES, MAX_BYTES),
    ):
        value = config.get(key, default)
        if type(value) is not int or not 1 <= value <= maximum:
            raise ValueError('Invalid capture budget')
    tasks = config.get('include_tasks', [])
    if (not isinstance(tasks, list) or len(tasks) > 32
            or any(not isinstance(task, str) or not task or len(task) > 128 for task in tasks)
            or len(set(tasks)) != len(tasks)):
        raise ValueError('Invalid task selection')
    if type(config.get('include_native_subagents', False)) is not bool:
        raise ValueError('Invalid native subagent selection')
    return config


def read_config(root_fd, *, active=True):
    return validate_config(_read_json(root_fd, 'capture.json'), active=active)


@contextmanager
def run_directory(root_fd, run_id, *, create=False):
    _uuid(run_id)
    if create:
        try:
            os.mkdir(run_id, mode=0o700, dir_fd=root_fd)
        except FileExistsError:
            pass
    fd = os.open(run_id, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
    try:
        _check(os.fstat(fd), directory=True)
        yield fd
    finally:
        os.close(fd)


def request_inventory(run_fd):
    requests = []
    for name in os.listdir(run_fd):
        match = _REQUEST_NAME.fullmatch(name)
        if match:
            fd = _open_file(run_fd, name)
            try:
                requests.append((int(match[1]), os.fstat(fd).st_size))
            finally:
                os.close(fd)
    return requests


async def _get_chat(chat_id):
    from open_webui.models.chats import Chats
    return await Chats.get_chat_by_id(chat_id)


async def _resolve_scope(metadata, config, user_id):
    chat_id = metadata.get('chat_id')
    if not isinstance(chat_id, str) or not isinstance(user_id, str) or not user_id:
        return None
    task = metadata.get('task')
    if task is not None and task not in config.get('include_tasks', []):
        return None
    root_id = config['chat_id']
    if chat_id != root_id and not config.get('include_native_subagents', False):
        return None
    current = await _get_chat(chat_id)
    if current is None or current.id != chat_id or current.user_id != user_id:
        return None
    if chat_id == root_id:
        return {'agent_kind': ('main' if task is None else
                               'community_subagent' if task == 'sub_agent' else 'explicit_task')}
    original_meta = current.meta
    if not isinstance(original_meta, dict):
        return None
    visited = {chat_id}
    for depth in range(1, 9):
        meta = current.meta
        if (not isinstance(meta, dict) or meta.get('internal') is not True
                or meta.get('type') != 'subagent'):
            return None
        parent_id = meta.get('parent_chat_id')
        if not isinstance(parent_id, str) or not parent_id or parent_id in visited:
            return None
        visited.add(parent_id)
        current = await _get_chat(parent_id)
        if current is None or current.id != parent_id or current.user_id != user_id:
            return None
        if parent_id == root_id:
            result = {
                'agent_kind': 'native_subagent', 'parent_chat_id': original_meta['parent_chat_id'],
                'lineage_depth': depth,
            }
            if isinstance(original_meta.get('delegation_id'), str):
                result['delegation_id'] = original_meta['delegation_id']
            return result
    return None


def _text(value):
    return value if isinstance(value, str) and len(value) <= 4096 else None


async def capture_provider_context(
    metadata, payload, request_url, *, selected_model=None, user_id=None, root=None,
):
    """Observe exact serialized UTF-8 bytes; never disrupt model execution."""
    try:
        if not isinstance(metadata, dict) or not isinstance(payload, str):
            return None
        try:
            with protected_root(root) as root_fd:
                config = read_config(root_fd)
        except (FileNotFoundError, ValueError, KeyError, PermissionError):
            return None
        scope = await _resolve_scope(metadata, config, user_id)
        if scope is None:
            return None
        data = payload.encode('utf-8')
        if len(data) > config.get('max_bytes', DEFAULT_MAX_BYTES):
            return None
        body = json.loads(payload)
        if not isinstance(body, dict):
            return None
        target = urlsplit(request_url)
        with protected_root(root) as root_fd:
            # Do not retain a stale opt-in while native ownership was awaited.
            with storage_lock(root_fd, '.control.lock'):
                if read_config(root_fd) != config:
                    return None
                with run_directory(root_fd, config['run_id'], create=True) as run_fd:
                    with storage_lock(run_fd, '.lock'):
                        requests = request_inventory(run_fd)
                        if (len(requests) >= config.get('max_requests', MAX_REQUESTS)
                                or sum(size for _, size in requests) + len(data)
                                > config.get('max_bytes', DEFAULT_MAX_BYTES)):
                            return None
                        index = max((index for index, _ in requests), default=0) + 1
                        if index > MAX_REQUESTS:
                            return None
                        receipt = {
                            'captured_at': time.time(), 'scope_chat_id': config['chat_id'],
                            'chat_id': metadata['chat_id'], 'message_id': _text(metadata.get('message_id')),
                            'task': metadata.get('task'),
                            'sub_agent_iteration': (metadata.get('sub_agent_iteration')
                                                    if type(metadata.get('sub_agent_iteration')) is int else None),
                            'selected_model': _text(selected_model), 'provider_model': _text(body.get('model')),
                            'round': index, 'host': target.hostname, 'path': target.path,
                            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                            'previous_response_id_present': 'previous_response_id' in body,
                            'provider_state': ('outbound_delta' if 'previous_response_id' in body
                                               else 'outbound_request'),
                            **scope,
                        }
                        _write_file(run_fd, f'{index:03}.request.json', data)
                        _write_file(run_fd, f'{index:03}.receipt.json',
                                    json.dumps(receipt, ensure_ascii=True).encode('utf-8'))
                        return receipt
    except Exception as error:
        try:
            log.warning('Provider context capture failed (%s)', type(error).__name__)
        except Exception:
            # A failing logging handler must not turn diagnostics into a request failure.
            pass
        return None
