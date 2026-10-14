"""Opt-in capture of the native provider body for one authorized saved chat.

This observes the serialized request; it owns no messages, tools or execution.
No headers, cookies or credentials are accepted. Remove the overlay when native
OpenWebUI offers an equivalent final-provider-request diagnostic hook.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from open_webui.env import DATA_DIR

log = logging.getLogger(__name__)


def capture_provider_context(metadata, payload, request_url, *, root=None):
    """Write the exact outbound UTF-8 body without changing the request."""
    try:
        root = Path(root) if root is not None else Path(DATA_DIR) / 'forensics/provider-context'
        config_path = root / 'capture.json'
        if not config_path.is_file() or not isinstance(metadata, dict):
            return None
        config = json.loads(config_path.read_text(encoding='utf-8'))
        if (metadata.get('task') is not None
                or metadata.get('chat_id') != config.get('chat_id')
                or not time.time() < float(config['expires_at'])):
            return None
        run_id = str(uuid.UUID(config['run_id']))
        limit = int(config.get('max_requests', 12))
        max_bytes = int(config.get('max_bytes', 128 * 1024 * 1024))
        if not 1 <= limit <= 20 or not 1 <= max_bytes <= 256 * 1024 * 1024:
            return None
        if not isinstance(payload, str):
            return None
        data = payload.encode('utf-8')
        directory = root / run_id
        directory.mkdir(mode=0o700, exist_ok=True)
        lock_fd = os.open(directory / '.lock', os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(lock_fd, 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            existing = list(directory.glob('*.request.json'))
            if len(existing) >= limit or sum(p.stat().st_size for p in existing) + len(data) > max_bytes:
                return None
            index = len(existing) + 1
            path = directory / f'{index:03}.request.json'
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
            target = urlsplit(request_url)
            receipt = {
                'captured_at': time.time(), 'chat_id': metadata['chat_id'],
                'message_id': metadata.get('message_id'), 'round': index,
                'host': target.hostname, 'path': target.path,
                'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            }
            fd = os.open(directory / f'{index:03}.receipt.json', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(receipt, stream, ensure_ascii=True)
            return receipt
    except Exception as error:
        # Diagnostics must not change model execution or leak arbitrary content.
        log.warning('Provider context capture failed (%s)', type(error).__name__)
        return None
