"""Operator CLI for the installed final-provider-request diagnostic helper."""
from __future__ import annotations

import argparse
import json
import os
import time
import uuid

from open_webui.utils import provider_context_capture as capture


def enable(args):
    config = {
        'chat_id': args.chat_id, 'run_id': str(uuid.uuid4()),
        'expires_at': time.time() + args.ttl_seconds,
        'max_requests': args.max_requests, 'max_bytes': args.max_bytes,
        'include_tasks': args.include_task,
        'include_native_subagents': args.include_native_subagents,
    }
    capture.validate_config(config)
    with capture.protected_root(args.root, create=True) as root_fd:
        with capture.storage_lock(root_fd, '.control.lock'):
            try:
                previous = capture.read_config(root_fd, active=False)
            except FileNotFoundError:
                previous = None
            if previous is not None and previous['expires_at'] > time.time():
                raise ValueError('An active capture already exists; disable it first')
            capture._atomic_json(root_fd, 'capture.json', config)
    return {'enabled': True, 'config': config}


def disable(args):
    try:
        with capture.protected_root(args.root) as root_fd:
            with capture.storage_lock(root_fd, '.control.lock'):
                try:
                    # Validate protection before unlinking the control file.
                    fd = capture._open_file(root_fd, 'capture.json')
                except FileNotFoundError:
                    return {'enabled': False}
                os.close(fd)
                os.unlink('capture.json', dir_fd=root_fd)
                os.fsync(root_fd)
    except FileNotFoundError:
        pass
    return {'enabled': False}


def status(args):
    try:
        with capture.protected_root(args.root) as root_fd:
            try:
                config = capture.read_config(root_fd, active=False)
            except FileNotFoundError:
                return {'enabled': False}
            result = {
                'enabled': config['expires_at'] > time.time(),
                'config': {key: config.get(key) for key in (
                    'chat_id', 'run_id', 'expires_at', 'max_requests', 'max_bytes',
                    'include_tasks', 'include_native_subagents',
                )},
                'count': 0, 'bytes': 0, 'receipts': [],
            }
            try:
                with capture.run_directory(root_fd, config['run_id']) as run_fd:
                    # Lock an existing run for a coherent body/receipt inventory.
                    with capture.storage_lock(run_fd, '.lock'):
                        requests = capture.request_inventory(run_fd)
                        result['count'] = len(requests)
                        result['bytes'] = sum(size for _, size in requests)
                        for index, _ in sorted(requests):
                            try:
                                receipt = capture._read_json(run_fd, f'{index:03}.receipt.json')
                            except FileNotFoundError:
                                result['receipts'].append({'round': index, 'receipt_missing': True})
                                continue
                            if not isinstance(receipt, dict):
                                raise ValueError('Invalid receipt')
                            result['receipts'].append({
                                key: value for key, value in receipt.items()
                                if key in capture.RECEIPT_FIELDS
                                and (value is None or type(value) in (str, int, float, bool))
                            })
            except FileNotFoundError:
                pass
            return result
    except FileNotFoundError:
        return {'enabled': False}


def bounded_integer(maximum):
    def parse(value):
        result = int(value)
        if not 1 <= result <= maximum:
            raise argparse.ArgumentTypeError(f'Must be between 1 and {maximum}')
        return result
    return parse


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', help='Diagnostic root (default: DATA_DIR/forensics/provider-context)')
    commands = parser.add_subparsers(dest='command', required=True)
    arm = commands.add_parser('enable')
    arm.add_argument('--chat-id', required=True, help='One saved chat UUID')
    arm.add_argument('--include-task', action='append', default=[])
    arm.add_argument('--include-native-subagents', action='store_true')
    arm.add_argument('--ttl-seconds', type=bounded_integer(capture.MAX_TTL_SECONDS), default=900)
    arm.add_argument('--max-requests', type=bounded_integer(capture.MAX_REQUESTS), default=capture.MAX_REQUESTS)
    arm.add_argument('--max-bytes', type=bounded_integer(capture.MAX_BYTES), default=capture.DEFAULT_MAX_BYTES)
    commands.add_parser('status')
    commands.add_parser('disable')
    args = parser.parse_args(argv)
    try:
        result = {'enable': enable, 'status': status, 'disable': disable}[args.command](args)
    except Exception as error:
        # Do not render a DB, filesystem or malformed-content exception message.
        parser.exit(1, f'Capture control failed ({type(error).__name__})\n')
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
