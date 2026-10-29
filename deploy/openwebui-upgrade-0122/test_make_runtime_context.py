"""Exercise the real runtime packager with synthetic reviewed frontend bytes.

These tests qualify the packaged inputs, not a Docker build or a deployed UI.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PROVIDER_BUNDLE = REPO / 'deploy/openwebui-patches/provider-context-v0.12.2'
OBSERVER_FILES = {
    'provider_context_capture.py', 'capture_control.py', 'apply_capture.py', 'verify_capture.py',
}


class RuntimeContextPackaging(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='runtime-context-fixture-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.frontend = self.root / 'reviewed-frontend'
        self.build = self.frontend / 'build'
        self.build.mkdir(parents=True)
        self.output = self.root / 'packaged-runtime'
        self.identity = 'a' * 64
        self.files = {
            'index.html': b'<html><body>Synthetic reviewed frontend</body></html>\n',
            '_app/version.json': json.dumps({'version': self.identity}).encode('utf-8'),
            '_app/immutable/app.js': 'export const title = "\u0421\u0447\u0451\u0442";\n'.encode('utf-8'),
        }
        for name, data in self.files.items():
            path = self.build / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.manifest = {
            name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            for name, data in self.files.items()
        }
        self.manifest_path = self.frontend / 'frontend-files.json'
        self.manifest_path.write_text(json.dumps(self.manifest), encoding='utf-8')
        self.receipt = {
            'upstream_version': '0.12.2',
            'upstream_commit': '6a18585ff4c2e5f6805f682222cfbc46dc669ef8',
            'build_identity': self.identity,
            'native_build_command': 'npm run build',
            'source_archive_sha256': 'b' * 64,
            'input_receipt_sha256': 'c' * 64,
            'frontend_sources_sha256': 'd' * 64,
            'artifact_sha256': 'e' * 64,
            'build_files': len(self.files),
            'build_uncompressed_bytes': sum(map(len, self.files.values())),
            'build_files_manifest_sha256': hashlib.sha256(self.manifest_path.read_bytes()).hexdigest(),
            'native_build_success': True,
            'sourcemap': False,
            'build_directory': str(self.build),
            'private_operator_note': 'PRIVATE-FIXTURE-EXCLUDED',
        }
        self.save_receipt()
        (self.frontend / 'private.env').write_text('PRIVATE-FIXTURE-EXCLUDED', encoding='utf-8')

    def save_receipt(self):
        (self.frontend / 'frontend-artifact-receipt.json').write_text(
            json.dumps(self.receipt), encoding='utf-8')

    def package(self):
        return subprocess.run(
            [sys.executable, str(HERE / 'make_runtime_context.py'),
             '--frontend', str(self.frontend), '--output', str(self.output)],
            capture_output=True, text=True, timeout=30, check=False,
        )

    def test_complete_observer_and_existing_runtime_inputs_are_packaged_exactly(self):
        result = self.package()
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary['build_identity'], self.identity)
        self.assertEqual(summary['frontend_files'], len(self.files))
        for name, expected in self.files.items():
            self.assertEqual((self.output / 'build' / name).read_bytes(), expected)
        for name in OBSERVER_FILES:
            with self.subTest(observer_file=name):
                self.assertEqual((self.output / 'provider-context' / name).read_bytes(),
                                 (PROVIDER_BUNDLE / name).read_bytes())
        self.assertTrue(all(path.suffix in {'.py', '.json'}
                            for path in (self.output / 'provider-context').iterdir()))
        for destination, source in (
            ('tool-context/apply_context.py', 'tool-context-v0.12.2/apply_context.py'),
            ('media-upload/apply_media.py', 'media-upload-v0.12.2/apply_media.py'),
        ):
            self.assertEqual((self.output / destination).read_bytes(),
                             (REPO / 'deploy/openwebui-patches' / source).read_bytes())
        self.assertEqual((self.output / 'runtime.Dockerfile').read_bytes(),
                         (HERE / 'runtime.Dockerfile').read_bytes())
        self.assertEqual((self.output / 'frontend-files.json').read_bytes(), self.manifest_path.read_bytes())
        receipt = json.loads((self.output / 'frontend-receipt.json').read_text(encoding='utf-8'))
        self.assertEqual(receipt['build_files_manifest_sha256'],
                         hashlib.sha256((self.output / 'frontend-files.json').read_bytes()).hexdigest())
        self.assertNotIn('build_directory', receipt)
        self.assertNotIn('private_operator_note', receipt)
        self.assertFalse((self.output / 'private.env').exists())
        self.assertFalse((self.output / 'provider-context/capture.json').exists())

    def test_failed_frontend_binding_leaves_no_runtime_context(self):
        for failure in ('changed_body', 'changed_manifest', 'extra_file', 'missing_file',
                        'wrong_upstream', 'failed_native_build'):
            with self.subTest(failure=failure):
                original_manifest = self.manifest_path.read_bytes()
                original_receipt = dict(self.receipt)
                if failure == 'changed_body':
                    (self.build / 'index.html').write_bytes(b'Unreviewed frontend bytes')
                elif failure == 'changed_manifest':
                    self.manifest_path.write_text('{}', encoding='utf-8')
                elif failure == 'extra_file':
                    (self.build / 'unreviewed.js').write_bytes(b'Unreviewed extra file')
                elif failure == 'missing_file':
                    (self.build / 'index.html').unlink()
                elif failure == 'wrong_upstream':
                    self.receipt['upstream_commit'] = 'f' * 40
                    self.save_receipt()
                else:
                    self.receipt['native_build_success'] = False
                    self.save_receipt()
                result = self.package()
                self.assertNotEqual(result.returncode, 0, failure)
                self.assertFalse(self.output.exists(), failure)
                for name, data in self.files.items():
                    (self.build / name).write_bytes(data)
                (self.build / 'unreviewed.js').unlink(missing_ok=True)
                self.manifest_path.write_bytes(original_manifest)
                self.receipt = original_receipt
                self.save_receipt()


if __name__ == '__main__':
    unittest.main()
