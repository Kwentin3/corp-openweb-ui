"""Artifact preparation/identity tests only; never run Docker or native services."""
import ast
import base64
import copy
from contextlib import redirect_stdout
import difflib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import build_native_floor_image as B

I = B.native_identity
REPO = Path(__file__).resolve().parents[2]
PATCH_DIR = REPO / 'deploy/litellm-patches/positive-floor-v1.105.1'
UPSTREAM = Path(os.environ.get('GOAL584_LITELLM_SOURCE_ROOT', str(REPO / 'local/goal584/litellm/upstream')))
FILES = ('scripts/goal584-budget-proof/build_native_floor_image.py',
         'deploy/litellm-patches/positive-floor-v1.105.1/manifest.json',
         'deploy/litellm-patches/positive-floor-v1.105.1/floor.patch',
         'deploy/litellm-patches/positive-floor-v1.105.1/LICENSE',
         'deploy/litellm-patches/positive-floor-v1.105.1/native_floor_identity.py',
         'scripts/goal584-budget-proof/test_native_floor_patch.py')


def sha(value):
    return hashlib.sha256(value).hexdigest()


class ArtifactFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Missing optional read-only Git cache can skip; missing candidate files
        # are an integration error, never a reason to report a green skip.
        for name in FILES:
            if not (REPO / name).is_file():
                raise AssertionError('Required candidate artifact missing: ' + name)
        if not (UPSTREAM / '.git').exists():
            raise unittest.SkipTest('Exact read-only d665 source cache unavailable; set GOAL584_LITELLM_SOURCE_ROOT')
        manifest = I.load_manifest()
        cls.original, cls.cache_bytes = {}, {}
        try:
            for name, expected in manifest['native_export_sha256'].items():
                raw = subprocess.check_output(['git', '-c', 'gc.auto=0', '-C', str(UPSTREAM), 'show',
                    I.BASE_REVISION + ':' + name], env={**os.environ, 'GIT_NO_LAZY_FETCH': '1'}, stderr=subprocess.DEVNULL)
                if sha(raw) != expected:
                    raise AssertionError('Pinned Git blob differs from fixed manifest: ' + name)
                cls.original[name] = raw
                if (UPSTREAM / name).is_file():
                    cls.cache_bytes[name] = (UPSTREAM / name).read_bytes()
            cls.license_source = subprocess.check_output(['git', '-c', 'gc.auto=0', '-C', str(UPSTREAM), 'show',
                I.BASE_REVISION + ':LICENSE'], env={**os.environ, 'GIT_NO_LAZY_FETCH': '1'}, stderr=subprocess.DEVNULL)
            if sha(cls.license_source) != manifest['license_sha256']:
                raise AssertionError('MIT notice differs from exact pinned upstream LICENSE')
        except subprocess.CalledProcessError:
            raise unittest.SkipTest('Exact known-path d665 Git objects unavailable; no lazy fetch')

    @classmethod
    def tearDownClass(cls):
        for name, raw in getattr(cls, 'cache_bytes', {}).items():
            if (UPSTREAM / name).read_bytes() != raw:
                raise AssertionError('Artifact test mutated original read-only source cache: ' + name)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / 'repo'
        self.patch_dir = self.root / 'deploy/litellm-patches/positive-floor-v1.105.1'
        for name in FILES:
            target = self.root / name; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((REPO / name).read_bytes())
        for owner, name, value in ((B, 'ROOT', self.root), (B, 'PATCH_DIR', self.patch_dir),
                (B, '__file__', str(self.root / 'scripts/goal584-budget-proof/build_native_floor_image.py')),
                (I, '__file__', str(self.patch_dir / 'native_floor_identity.py'))):
            item = patch.object(owner, name, value); item.start(); self.addCleanup(item.stop)
        environment = patch.dict(os.environ, {'PROOF_NATIVE_VARIANT': 'stock', 'PROOF_LITELLM_IMAGE': I.BASE_IMAGE})
        environment.start(); self.addCleanup(environment.stop)
        self.context = Path(self.directory.name) / 'context'; self.context.mkdir()
        self.exported = {name: base64.b64encode(raw).decode('ascii') for name, raw in self.original.items()}

    def candidate(self):
        return B.prepare(self.context, self.exported)

    def receipt(self):
        manifest = I.load_manifest()
        image = 'sha256:' + 'a' * 64
        os.environ.update(PROOF_NATIVE_VARIANT=I.VARIANT, PROOF_LITELLM_IMAGE=image)
        return {'schema': 1, 'variant': I.VARIANT, 'base_image': I.BASE_IMAGE, 'base_revision': I.BASE_REVISION,
            'image_ref': image, 'image_id': image, **{name: copy.deepcopy(manifest[name]) for name in
                ('original_sha256', 'patched_sha256', 'patch_sha256', 'native_export_sha256')},
            'files_sha256': {name: sha((self.root / name).read_bytes()) for name in FILES}}

    def rewrite_patch(self, original, changed):
        data = ''.join(difflib.unified_diff(original.decode().splitlines(True), changed.decode().splitlines(True),
            fromfile='a/' + B.TARGET, tofile='b/' + B.TARGET)).encode()
        (self.patch_dir / 'floor.patch').write_bytes(data)
        manifest = I.load_manifest(); manifest.update(patch_sha256=sha(data), patched_sha256=sha(changed))
        (self.patch_dir / 'manifest.json').write_text(json.dumps(manifest), encoding='utf8')


class PrepareTests(ArtifactFixture):
    def test_exact_five_git_exports_apply_real_git_patch_and_preserve_original_cache(self):
        manifest, original = self.candidate()
        self.assertEqual(original, self.original[B.TARGET])
        self.assertEqual(sha((self.context / B.TARGET).read_bytes()), manifest['patched_sha256'])
        B.validate_delta(original, (self.context / B.TARGET).read_bytes())
        for name, content in self.original.items():
            if name != B.TARGET:
                self.assertEqual((self.context / name).read_bytes(), content)
        self.assertEqual((self.context / 'LICENSE').read_bytes(), (self.patch_dir / 'LICENSE').read_bytes())
        self.assertEqual((self.context / 'LICENSE').read_bytes(), self.license_source)
        self.assertEqual((self.context / 'manifest.json').read_bytes(), (self.patch_dir / 'manifest.json').read_bytes())
        self.assertIn(b'Copyright (c) 2023 Berri AI', (self.context / 'LICENSE').read_bytes())

    def test_each_wrong_native_export_byte_rejects_before_a_candidate_is_accepted(self):
        for name, raw in self.original.items():
            with self.subTest(name=name):
                exported = {**self.exported, name: base64.b64encode(raw + b'\n# mutation').decode()}
                with self.assertRaises(AssertionError): B.prepare(self.context, exported)

    def test_missing_extra_and_invalid_base64_export_are_not_reinterpreted(self):
        values = [dict(list(self.exported.items())[1:]), {**self.exported, 'extra': 'eA=='},
                  {**self.exported, B.TARGET: 'not base64?'}]
        for value in values:
            with self.subTest(keys=list(value)), self.assertRaises((AssertionError, ValueError)):
                B.prepare(self.context, value)

    def test_patch_and_license_mutations_fail_fixed_manifest_guards(self):
        for name in ('floor.patch', 'LICENSE'):
            path = self.patch_dir / name; original = path.read_bytes()
            try:
                path.write_bytes(original + b'\nchanged artifact')
                with self.subTest(name=name), self.assertRaises(AssertionError): self.candidate()
            finally:
                path.write_bytes(original)

    def test_changed_allowed_function_body_still_rejects_fixed_reviewed_after_hash(self):
        manifest, original = self.candidate()
        candidate = (self.context / B.TARGET).read_bytes()
        changed = candidate.replace(b'cached positive floor', b'changed positive floor', 1)
        self.assertNotEqual(changed, candidate)
        B.validate_delta(original, changed)  # Scope alone cannot authorize new contents.
        self.rewrite_patch(original, changed)
        altered = I.load_manifest(); altered['patched_sha256'] = manifest['patched_sha256']
        (self.patch_dir / 'manifest.json').write_text(json.dumps(altered), encoding='utf8')
        clean = Path(self.directory.name) / 'changed-body'; clean.mkdir()
        with self.assertRaises(AssertionError): B.prepare(clean, self.exported)

    def test_recomputed_patch_and_after_hash_do_not_authorize_a_third_function(self):
        _, original = self.candidate()
        changed = (self.context / B.TARGET).read_bytes() + b'\n\ndef unapproved_native_function():\n    return 1\n'
        self.rewrite_patch(original, changed)
        clean = Path(self.directory.name) / 'extra-function'; clean.mkdir()
        with self.assertRaisesRegex(AssertionError, 'top-level structure'):
            B.prepare(clean, self.exported)

    def test_recomputed_hashes_do_not_authorize_changed_module_global(self):
        _, original = self.candidate(); content = (self.context / B.TARGET).read_bytes(); tree = ast.parse(content)
        assignment = next(n for n in tree.body if isinstance(n, ast.Assign))
        changed_assignment = copy.deepcopy(assignment); changed_assignment.value = ast.Constant(value='unapproved-global-change')
        lines = content.splitlines(keepends=True)
        changed = (b''.join(lines[:assignment.lineno - 1]) + ast.unparse(ast.fix_missing_locations(changed_assignment)).encode()
                   + b'\n' + b''.join(lines[assignment.end_lineno:]))
        self.rewrite_patch(original, changed)
        clean = Path(self.directory.name) / 'global-change'; clean.mkdir()
        with self.assertRaises(AssertionError): B.prepare(clean, self.exported)

    def test_public_signature_or_decorator_change_is_not_just_an_allowed_body_delta(self):
        _, original = self.candidate(); patched = (self.context / B.TARGET).read_bytes()
        for kind in ('signature', 'decorator'):
            tree = ast.parse(patched)
            function = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'get_current_spend')
            if kind == 'signature': function.args.kwonlyargs.append(ast.arg(arg='unapproved')); function.args.kw_defaults.append(ast.Constant(None))
            else: function.decorator_list.append(ast.Name(id='unapproved_decorator', ctx=ast.Load()))
            with self.subTest(kind=kind), self.assertRaises(AssertionError):
                B.validate_delta(original, (ast.unparse(ast.fix_missing_locations(tree)) + '\n').encode())


class IdentityTests(ArtifactFixture):
    def test_stock_and_derivative_maps_are_explicit_and_do_not_mutate_pristine(self):
        manifest = I.load_manifest()
        pristine = {name.removeprefix('litellm/'): digest for name, digest in manifest['native_export_sha256'].items()}
        stock = copy.deepcopy(pristine)
        self.assertEqual(I.variant(), 'stock'); self.assertEqual(I.image_ref(), I.BASE_IMAGE)
        self.assertEqual(I.selected_hashes(pristine), stock)
        receipt = self.receipt()
        expected = {**stock, I.PROXY: manifest['patched_sha256']}
        self.assertEqual(I.selected_hashes(pristine), expected)
        self.assertEqual(pristine, stock)
        self.assertEqual([name for name in stock if stock[name] != expected[name]], [I.PROXY])
        self.assertEqual(I.verify_build(receipt)['image_ref'], receipt['image_id'])
        with patch.dict(os.environ, {'PROOF_NATIVE_PROXY_SHA256': 'b' * 64}):
            self.assertEqual(I.selected_hashes(pristine)[I.PROXY], manifest['patched_sha256'])

    def test_unknown_variant_mutable_tag_or_derivative_on_foreign_baseline_rejects(self):
        for profile, image in (('unknown', I.BASE_IMAGE), ('stock', 'sha256:' + 'a' * 64),
                               (I.VARIANT, 'unreviewed:latest'), (I.VARIANT, I.BASE_IMAGE)):
            with self.subTest(profile=profile, image=image), patch.dict(os.environ,
                    {'PROOF_NATIVE_VARIANT': profile, 'PROOF_LITELLM_IMAGE': image}), self.assertRaises(AssertionError):
                I.image_ref()
        self.receipt()
        with self.assertRaises(AssertionError): I.selected_hashes({I.PROXY: 'b' * 64})

    def test_manifest_schema_bool_extra_key_and_wrong_basis_reject(self):
        path = self.patch_dir / 'manifest.json'; original = path.read_bytes(); source = json.loads(original)
        for mutation in ({**source, 'schema': True}, {**source, 'extra': 'unreviewed'},
                         {**source, 'base_revision': 'other'}, {**source, 'base_image': 'image:latest'}):
            with self.subTest(keys=mutation.keys()):
                path.write_text(json.dumps(mutation), encoding='utf8')
                with self.assertRaises(AssertionError): I.load_manifest()
        path.write_bytes(original)

    def test_build_receipt_forged_image_source_schema_or_extra_field_rejects(self):
        receipt = self.receipt()
        for name, value in (('image_id', 'sha256:' + 'b' * 64), ('image_ref', 'sha256:' + 'b' * 64),
                ('patched_sha256', 'b' * 64), ('original_sha256', 'b' * 64), ('patch_sha256', 'b' * 64),
                ('native_export_sha256', {}), ('schema', True), ('unexpected_metadata', 'private'),
                ('dockerfile_sha256', 'b' * 64)):
            with self.subTest(name=name), self.assertRaises(AssertionError):
                I.verify_build({**receipt, name: value})

    def test_actual_source_binding_mutation_and_missing_binding_reject(self):
        receipt = self.receipt()
        path = self.root / 'scripts/goal584-budget-proof/build_native_floor_image.py'
        path.write_bytes(path.read_bytes() + b'\n# actual changed artifact\n')
        with self.assertRaises(AssertionError): I.verify_build(receipt)
        receipt = self.receipt(); receipt['files_sha256'].pop('scripts/goal584-budget-proof/build_native_floor_image.py')
        with self.assertRaises(AssertionError): I.verify_build(receipt)

    def test_runtime_source_inspection_reads_all_five_installed_bytes_for_selected_variant(self):
        manifest, _ = self.candidate()
        origin = self.context / 'litellm/__init__.py'
        self.receipt()
        with patch.object(I.importlib.util, 'find_spec', return_value=SimpleNamespace(origin=str(origin))):
            actual = I.inspect_sources()
            self.assertEqual(len(actual['native_sha256']), 5)
            self.assertEqual(actual['native_sha256'][I.PROXY], manifest['patched_sha256'])
            self.assertEqual(actual['native_artifact']['variant'], I.VARIANT)
            with patch.dict(os.environ, {'PROOF_NATIVE_VARIANT': 'stock', 'PROOF_LITELLM_IMAGE': I.BASE_IMAGE}):
                with self.assertRaises(AssertionError): I.inspect_sources()
                target = self.context / B.TARGET; patched = target.read_bytes()
                target.write_bytes(self.original[B.TARGET])
                self.assertEqual(I.inspect_sources()['native_artifact']['variant'], 'stock')
                target.write_bytes(patched)
            companion = self.context / 'litellm/caching/in_memory_cache.py'
            companion.write_bytes(companion.read_bytes() + b'\n# unexpected second SDK edit\n')
            with self.assertRaises(AssertionError): I.inspect_sources()


class BuilderCommandTests(ArtifactFixture):
    def test_actual_builder_main_commands_dockerfile_install_and_receipt_with_external_docker_doubles(self):
        # Execute export/install/readback programs against disposable file copies.
        # Docker and nested test process scheduling are external boundary doubles.
        context = Path(self.directory.name) / 'main-context'
        receipt_path = Path(self.directory.name) / 'build.safe.json'
        installed = Path(self.directory.name) / 'image'
        for name, raw in self.original.items():
            path = installed / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
        image_id = 'sha256:' + 'a' * 64
        temporary = installed / 'tmp-proxy.py'
        docs = installed / 'docs'; docs.mkdir()
        original_run = B.run
        actual_subprocess_run = subprocess.run
        commands = []
        def program(script, argv=()):
            fake_pathlib = ModuleType('pathlib')
            fake_pathlib.Path = lambda value: temporary if str(value) == '/tmp/goal584-proxy_server.py' else (
                docs / Path(value).name if str(value).startswith('/usr/share/doc/goal584-native-floor/') else Path(value))
            output = io.StringIO()
            with patch.dict(sys.modules, {'pathlib': fake_pathlib}), patch.object(importlib.util, 'find_spec',
                    return_value=SimpleNamespace(origin=str(installed / 'litellm/__init__.py'))), patch.object(sys, 'argv', ['-c', *argv]), redirect_stdout(output):
                exec(compile(script, '<actual-builder-program>', 'exec'), {})
            return output.getvalue().encode()
        def run(argv, **kwargs):
            if argv[0] == 'git': return original_run(argv, **kwargs)
            commands.append(argv)
            if argv[:3] == ['docker', 'image', 'inspect']:
                return json.dumps([{'Id': image_id, 'Config': {'Labels': {'org.alpha-soft.goal584.native-variant': I.VARIANT}}}]).encode()
            self.assertEqual(argv[:8], ['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python', argv[7]])
            self.assertEqual(argv[8:10], ['-B', '-c'])
            self.assertIn(argv[7], (I.BASE_IMAGE, image_id))
            return program(argv[10], argv[11:])
        def scheduled(argv, **kwargs):
            if argv[0] == 'git':
                return actual_subprocess_run(argv, **kwargs)
            commands.append(argv)
            if argv[0] == sys.executable:
                self.assertEqual(argv[1:4], ['-m', 'unittest', 'discover'])
                self.assertIn('test_native_floor_patch.py', argv)
                originals = Path(kwargs['env']['GOAL584_NATIVE_FLOOR_SOURCE'])
                self.assertEqual(originals.read_bytes(), self.original[B.TARGET])
                for name, raw in self.original.items(): self.assertEqual((context / 'original' / name).read_bytes(), raw)
                return SimpleNamespace(returncode=0)
            self.assertEqual(argv[:3], ['docker', 'build', '--network=none'])
            text = (context / 'Dockerfile').read_text(encoding='utf8')
            self.assertEqual(text.splitlines()[0], 'FROM ' + I.BASE_IMAGE)
            self.assertIn('COPY LICENSE manifest.json /usr/share/doc/goal584-native-floor/', text)
            line = next(line for line in text.splitlines() if line.startswith('RUN '))
            arguments = shlex.split(line)
            self.assertEqual(len(arguments), 5)
            self.assertEqual(len(text.splitlines()), 5)
            self.assertEqual(arguments[:5], ['RUN', 'python', '-B', '-c', arguments[4]])
            self.assertNotIn('$', arguments[4]); self.assertNotIn('`', arguments[4])
            temporary.write_bytes((context / B.TARGET).read_bytes())
            for name in ('LICENSE', 'manifest.json'): shutil.copyfile(context / name, docs / name)
            program(arguments[4])
            self.assertEqual(sha((installed / B.TARGET).read_bytes()), I.load_manifest()['patched_sha256'])
            self.assertFalse(temporary.exists())
            Path(argv[argv.index('--iidfile') + 1]).write_text(image_id, encoding='ascii')
            return SimpleNamespace(returncode=0)
        stdout = io.StringIO()
        with (patch.object(B, 'run', side_effect=run), patch.object(B.subprocess, 'run', side_effect=scheduled),
                patch.object(sys, 'argv', ['builder', '--context', str(context), '--receipt', str(receipt_path)]), redirect_stdout(stdout)):
            B.main()
        value = json.loads(receipt_path.read_text(encoding='utf8'))
        self.assertEqual(value['image_id'], image_id)
        self.assertEqual(value['files_sha256'], {name: sha((self.root / name).read_bytes()) for name in FILES})
        self.assertNotIn('dockerfile_sha256', value)
        os.environ.update(PROOF_NATIVE_VARIANT=I.VARIANT, PROOF_LITELLM_IMAGE=image_id)
        self.assertEqual(I.verify_build(value)['proxy_sha256'], I.load_manifest()['patched_sha256'])
        self.assertEqual((docs / 'LICENSE').read_bytes(), (self.patch_dir / 'LICENSE').read_bytes())
        self.assertEqual(json.loads(stdout.getvalue())['image_ref'], image_id)
        self.assertFalse(any('pull' in command or 'push' in command for command in commands))


if __name__ == '__main__':
    unittest.main()
