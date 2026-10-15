"""Exercise the installed media functions without importing OpenWebUI/DB/ML.

Actual function bodies are extracted with AST; only their external native
configuration, persistence, extension-loading and task interfaces are fixtures.
No conversion, STT/provider call or authorization acceptance is claimed here.
"""
from __future__ import annotations

import argparse
import ast
import asyncio
import copy
import errno
import hashlib
import io
import json
import logging
import os
import sys
import tempfile
import types
import uuid
from pathlib import Path
from unittest.mock import patch


class Record(types.SimpleNamespace):
    def model_dump(self):
        return dict(vars(self))


class HttpError(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail
        super().__init__(detail)


class BoundedReader(io.BytesIO):
    def read(self, size=-1):
        assert 0 < size <= 1024 * 1024, 'Whole-file read attempted'
        return super().read(size)


def extracted(path, names):
    tree = ast.parse(path.read_bytes(), filename=str(path))
    nodes = [copy.deepcopy(node) for node in tree.body if getattr(node, 'name', None) in names]
    assert {node.name for node in nodes} == set(names)
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node.args.defaults = [ast.Constant(None) for _ in node.args.defaults]
            node.args.kw_defaults = [None if item is None else ast.Constant(None)
                                     for item in node.args.kw_defaults]
    future = ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)
    return compile(ast.fix_missing_locations(ast.Module(body=[future, *nodes], type_ignores=[])),
                   str(path), 'exec')


async def verify(root):
    manifest = json.loads((Path(__file__).with_name('manifest.json')).read_text(encoding='utf-8'))
    for relative, hashes in manifest['files'].items():
        if relative.startswith('backend/'):
            assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == hashes['candidate_sha256'], relative
    passed = []
    errors = Record(EMPTY_CONTENT='empty', DEFAULT=lambda detail: detail,
                    FILE_TOO_LARGE=lambda size: f'maximum {size}')
    namespace = dict(os=os, hashlib=hashlib, asyncio=asyncio, errno=errno, uuid=uuid,
                     log=logging.getLogger('media-contract'), ERROR_MESSAGES=errors,
                     StorageProvider=object, STORAGE_LOCAL_CACHE=False)
    exec(extracted(root / 'backend/open_webui/storage/provider.py', ['LocalStorageProvider']), namespace)
    local_type = namespace['LocalStorageProvider']
    storage = local_type()
    namespace['LocalStorageProvider'] = local_type
    namespace['Storage'] = storage
    exec(extracted(root / 'backend/open_webui/routers/files.py', ['_store_upload', 'upload_file_handler']), namespace)
    with tempfile.TemporaryDirectory(prefix='media-0122-backend-') as temporary:
        output = Path(temporary)
        namespace['UPLOAD_DIR'] = str(output)
        payload = bytes(range(256)) * (1024 * 9)
        size, digest, path = await namespace['_store_upload'](BoundedReader(payload), 'large.mp4', {})
        assert size == len(payload) and digest == hashlib.sha256(payload).hexdigest()
        assert Path(path).read_bytes() == payload
        passed.append('bounded native local upload preserves bytes, size and hash')

        for filename, reader, exception in [('empty.mp4', BoundedReader(b''), ValueError)]:
            try:
                await namespace['_store_upload'](reader, filename, {})
            except exception:
                assert not (output / filename).exists()
            else:
                raise AssertionError('Empty upload was accepted')

        class Interrupted(BoundedReader):
            def read(self, size=-1):
                if self.tell():
                    raise OSError('injected read interruption')
                return super().read(size)

        try:
            await namespace['_store_upload'](Interrupted(payload), 'broken.mp4', {})
        except OSError:
            assert not (output / 'broken.mp4').exists()
        else:
            raise AssertionError('Interrupted upload was accepted')
        try:
            await namespace['_store_upload'](BoundedReader(b'overwrite'), 'large.mp4', {})
        except FileExistsError:
            assert Path(path).read_bytes() == payload
        else:
            raise AssertionError('Existing file was overwritten')
        passed.append('empty/interrupted output removed; existing file preserved')

        class ExternalStorage:
            def upload_file(self, file, filename, tags):
                assert filename == 'external.bin' and tags == {'owner': 'u'}
                return file.read(), 'external://native-object'

        namespace['Storage'] = ExternalStorage()
        assert await namespace['_store_upload'](io.BytesIO(b'native'), 'external.bin', {'owner': 'u'}) == (
            6, hashlib.sha256(b'native').hexdigest(), 'external://native-object')
        namespace['Storage'] = storage
        passed.append('non-local storage retains native upload contract')

        rows, hooks, discoveries, scheduled, processed = {}, [], [], [], []
        settings = {}

        class Config:
            @staticmethod
            async def get(key):
                return settings.get(key)

        class Files:
            @staticmethod
            async def insert_new_file(user_id, form, db=None):
                row = Record(**form.model_dump(), user_id=user_id)
                rows[row.id] = row
                return row

        class Functions:
            @staticmethod
            async def get_functions_by_type(kind, active_only):
                assert (kind, active_only) == ('event', True)
                discoveries.append(kind)
                return [Record(id=str(index)) for index in range(len(hooks))]

        async def load_module(request, function_id, function):
            return Record(accept_upload=hooks[int(function_id)]), None, None

        async def native_process(*args, **kwargs):
            processed.append(args[3].id)

        class Background:
            def add_task(self, function, *args):
                scheduled.append((function, args))

        namespace.update(Config=Config, Files=Files, FileForm=Record, JSONCodec=json,
                         HTTPException=HttpError, process_uploaded_file=native_process,
                         status=Record(HTTP_400_BAD_REQUEST=400, HTTP_413_REQUEST_ENTITY_TOO_LARGE=413))
        modules = {
            'open_webui.models.functions': types.ModuleType('open_webui.models.functions'),
            'open_webui.utils.plugin': types.ModuleType('open_webui.utils.plugin'),
        }
        modules['open_webui.models.functions'].Functions = Functions
        modules['open_webui.utils.plugin'].get_function_module_from_cache = load_module
        user = Record(id='owner', email='fixture@localhost', name='Fixture')

        async def upload(data=b'fixture', **changes):
            arguments = dict(request=object(), file=Record(filename='fixture.m4a', content_type='audio/mp4',
                             file=BoundedReader(data)), metadata=None, process=True, process_in_background=True,
                             user=user, background_tasks=Background(), db=None)
            arguments.update(changes)
            return await namespace['upload_file_handler'](**arguments)

        async def claim(file_id, user_id):
            row = rows[file_id]
            assert row.user_id == user_id == 'owner' and Path(row.path).read_bytes() == b'fixture'
            assert row.data['status'] == 'pending'
            row.data.update(status='processing', stage2_video_intake={'state': 'pending'})
            return True

        async def decline(file_id, user_id):
            assert rows[file_id].user_id == user_id
            return False

        with patch.dict(sys.modules, modules):
            hooks[:] = [claim]
            response = await upload()
            assert response['id'] in rows and response['user_id'] == 'owner'
            assert response['data']['stage2_video_intake']['state'] == 'pending'
            assert not scheduled and not processed
            assert response['meta']['size'] == 7 and response['meta']['file_hash'] == hashlib.sha256(b'fixture').hexdigest()
            passed.append('claimed authenticated File keeps its ID and skips default processing')

            hooks[:] = [decline]
            response = await upload()
            assert len(scheduled) == 1 and scheduled[0][0] is native_process
            assert scheduled[0][1][3].id == response['id']
            await scheduled[0][0](*scheduled[0][1])
            assert processed == [response['id']]
            passed.append('unclaimed upload retains native background processing')

            hooks.clear()
            before = len(discoveries)
            response = await upload(process=False)
            assert response.data == {} and len(discoveries) == before and len(scheduled) == 1
            response = await upload(process_in_background=False)
            assert processed[-1] == response['id'] and len(scheduled) == 1
            passed.append('process=false and synchronous native fallback remain intact')

            settings['rag.file.max_size'] = 1
            before_paths, before_rows = set(output.iterdir()), set(rows)
            try:
                await upload(b'x' * (1024 * 1024 + 1))
            except HttpError as exc:
                assert exc.status_code == 413 and set(output.iterdir()) == before_paths and set(rows) == before_rows
            else:
                raise AssertionError('Oversized upload was accepted')
            settings.clear()
            passed.append('native maximum size rejects and removes stored bytes before File insertion')

            hooks[:] = [claim]
            settings['rag.file.allowed_extensions'] = ['pdf']
            before_discoveries, before_rows = len(discoveries), set(rows)
            try:
                await upload()
            except HttpError as exc:
                assert exc.status_code == 400 and len(discoveries) == before_discoveries and set(rows) == before_rows
            else:
                raise AssertionError('Disallowed extension was accepted')
            passed.append('native allowed-extension rejection precedes handoff and persistence')
    return passed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_root', type=Path)
    args = parser.parse_args()
    print(json.dumps({'passed': asyncio.run(verify(args.source_root.resolve(strict=True))),
                      'scope': 'actual backend function bodies; external native interfaces are fixtures'}))
