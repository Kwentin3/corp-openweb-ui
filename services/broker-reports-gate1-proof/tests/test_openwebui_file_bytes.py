from __future__ import annotations

import hashlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from broker_reports_gate1.openwebui_file_bytes import (
    OpenWebUIFileBytesError,
    OpenWebUIFileBytesResolverFactory,
)


PAYLOAD = b"owner-scoped native OpenWebUI PDF bytes"
FILE_ID = "11111111-2222-3333-4444-555555555555"
USER_ID = "ordinary-user"


class _Files:
    row = None

    @classmethod
    async def get_file_by_id(cls, file_id: str):
        return cls.row if file_id == FILE_ID else None


class OpenWebUIFileBytesTest(unittest.IsolatedAsyncioTestCase):
    def _modules(self, stored_path: Path):
        files_module = types.ModuleType("open_webui.models.files")
        files_module.Files = _Files
        storage_module = types.ModuleType("open_webui.storage.provider")
        storage_module.Storage = SimpleNamespace(
            get_file=lambda path: str(stored_path) if path == "stored/source.pdf" else ""
        )
        return {
            "open_webui": types.ModuleType("open_webui"),
            "open_webui.models": types.ModuleType("open_webui.models"),
            "open_webui.models.files": files_module,
            "open_webui.storage": types.ModuleType("open_webui.storage"),
            "open_webui.storage.provider": storage_module,
        }

    async def test_resolves_exact_bytes_for_authenticated_owner(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            stored_path = Path(temp_dir) / "source.pdf"
            stored_path.write_bytes(PAYLOAD)
            _Files.row = SimpleNamespace(
                id=FILE_ID,
                user_id=USER_ID,
                filename="source.pdf",
                path="stored/source.pdf",
                hash=hashlib.sha256(PAYLOAD).hexdigest(),
                meta={"content_type": "application/pdf", "size": len(PAYLOAD)},
            )
            with patch.dict(sys.modules, self._modules(stored_path)):
                resolved = await OpenWebUIFileBytesResolverFactory.create().resolve(
                    file_id=FILE_ID,
                    actor_user_id=USER_ID,
                )

        self.assertEqual(resolved.payload, PAYLOAD)
        self.assertEqual(resolved.filename, "source.pdf")
        self.assertEqual(resolved.content_type, "application/pdf")

    async def test_foreign_owner_is_denied_before_storage_read(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            stored_path = Path(temp_dir) / "source.pdf"
            stored_path.write_bytes(PAYLOAD)
            _Files.row = SimpleNamespace(
                id=FILE_ID,
                user_id="another-user",
                filename="source.pdf",
                path="stored/source.pdf",
                hash=hashlib.sha256(PAYLOAD).hexdigest(),
                meta={"content_type": "application/pdf", "size": len(PAYLOAD)},
            )
            with patch.dict(sys.modules, self._modules(stored_path)):
                with self.assertRaises(OpenWebUIFileBytesError) as denied:
                    await OpenWebUIFileBytesResolverFactory.create().resolve(
                        file_id=FILE_ID,
                        actor_user_id=USER_ID,
                    )

        self.assertEqual(denied.exception.code, "openwebui_file_not_owned")

    async def test_storage_hash_mismatch_is_terminal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            stored_path = Path(temp_dir) / "source.pdf"
            stored_path.write_bytes(PAYLOAD)
            _Files.row = SimpleNamespace(
                id=FILE_ID,
                user_id=USER_ID,
                filename="source.pdf",
                path="stored/source.pdf",
                hash="0" * 64,
                meta={"content_type": "application/pdf", "size": len(PAYLOAD)},
            )
            with patch.dict(sys.modules, self._modules(stored_path)):
                with self.assertRaises(OpenWebUIFileBytesError) as denied:
                    await OpenWebUIFileBytesResolverFactory.create().resolve(
                        file_id=FILE_ID,
                        actor_user_id=USER_ID,
                    )

        self.assertEqual(denied.exception.code, "openwebui_file_hash_mismatch")
