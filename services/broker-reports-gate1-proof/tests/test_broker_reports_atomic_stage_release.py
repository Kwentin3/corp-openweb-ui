from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]
SERVICE_ROOT = ROOT / "services" / "broker-reports-gate1-proof"
SCRIPTS = SERVICE_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import broker_reports_atomic_stage_remote as remote  # noqa: E402
import live_release_broker_reports_atomic_stage as driver  # noqa: E402
from broker_reports_atomic_stage_release_contracts import (  # noqa: E402
    FUNCTION_CONTRACTS,
    build_manifest,
    merged_valves,
    nonterminal_workload_count,
    provider_policy_manifest,
    validate_manifest,
    valves_match,
)
from broker_reports_release_source import (  # noqa: E402
    LOADER_REPOSITORY_PATH,
    git_blob_bytes,
)
from broker_reports_gate1 import GATE2_PROVIDER_PROFILES  # noqa: E402
from live_verify_broker_reports_atomic_stage_release import (  # noqa: E402
    evaluate_action_release,
    evaluate_function_release,
    evaluate_remote_runtime,
)
from live_verify_broker_reports_stage2_delivery import (  # noqa: E402
    FUNCTION_CONTRACTS as DELIVERY_FUNCTION_CONTRACTS,
    expected_prompt_contracts,
)


REVISION = "a" * 40


def _manifest():
    return build_manifest(
        source_revision=REVISION,
        prompt_contracts=expected_prompt_contracts(),
        provider_policy=provider_policy_manifest(GATE2_PROVIDER_PROFILES),
        loader_bytes=(
            ROOT / "deploy" / "openwebui-static" / "loader.js"
        ).read_bytes(),
    )


class AtomicStageReleaseContractTests(unittest.TestCase):
    def test_delivery_verifier_scopes_financial_markers_to_domain_function(self):
        source_contract = DELIVERY_FUNCTION_CONTRACTS[1]
        domain_contract = DELIVERY_FUNCTION_CONTRACTS[2]

        self.assertNotIn(
            "Gate2FinancialEvidenceProductionRuntimeFactory",
            source_contract.required_markers,
        )
        self.assertIn(
            "Gate2FinancialEvidenceProductionRuntimeFactory",
            domain_contract.required_markers,
        )
        self.assertIn(
            "financial_evidence_enabled",
            domain_contract.required_markers,
        )

    def test_driver_materializes_loader_from_exact_approved_git_blob(self):
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.strip()
        expected = git_blob_bytes(
            root=ROOT,
            source_revision=revision,
            repository_path=LOADER_REPOSITORY_PATH,
        )
        captured = {}

        def capture_payload(**kwargs):
            captured["loader"] = kwargs["loader_payload_path"].read_bytes()
            captured["manifest"] = json.loads(
                kwargs["manifest_path"].read_text(encoding="utf-8")
            )

        with (
            mock.patch.object(
                driver,
                "_assert_release_tree",
                return_value={"worktree_clean": True},
            ),
            mock.patch.object(
                driver,
                "_prepare_remote_staging",
                return_value="/validated/staging",
            ),
            mock.patch.object(driver, "_copy_payload", side_effect=capture_payload),
            mock.patch.object(
                driver,
                "_run_remote_release",
                return_value={"status": "validated"},
            ),
        ):
            receipt = driver.execute(
                source_revision=revision,
                ssh_target="validated-target",
                apply=False,
                prove_rollback=False,
            )

        self.assertEqual(expected, captured["loader"])
        self.assertEqual(
            remote._sha256_bytes(expected),
            captured["manifest"]["loader"]["content_sha256"],
        )
        self.assertEqual(
            remote._sha256_bytes(expected),
            receipt["manifest"]["loader_sha256"],
        )

    def test_git_blob_loader_identity_ignores_checkout_line_endings(self):
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.strip()
        git_bytes = git_blob_bytes(
            root=ROOT,
            source_revision=revision,
            repository_path=LOADER_REPOSITORY_PATH,
        )
        converted = (
            git_bytes.replace(b"\r\n", b"\n")
            if b"\r\n" in git_bytes
            else git_bytes.replace(b"\n", b"\r\n")
        )
        self.assertNotEqual(git_bytes, converted)

        manifest = build_manifest(
            source_revision=revision,
            prompt_contracts=expected_prompt_contracts(),
            provider_policy=provider_policy_manifest(GATE2_PROVIDER_PROFILES),
            loader_bytes=git_bytes,
        )

        self.assertEqual(
            remote._sha256_bytes(git_bytes),
            manifest["loader"]["content_sha256"],
        )
        self.assertNotEqual(
            remote._sha256_bytes(converted),
            manifest["loader"]["content_sha256"],
        )

    def test_git_blob_loader_source_fails_closed_for_invalid_revision(self):
        with self.assertRaisesRegex(
            ValueError,
            "source_revision_invalid",
        ):
            git_blob_bytes(
                root=ROOT,
                source_revision="HEAD",
                repository_path=LOADER_REPOSITORY_PATH,
            )

    def test_manifest_covers_exact_release_object_contract(self):
        manifest = _manifest()

        validate_manifest(manifest)

        self.assertEqual(3, len(manifest["functions"]))
        self.assertEqual(12, len(manifest["managed_prompts"]))
        self.assertEqual(
            "broker_reports_atomic_stage_release_v3",
            manifest["schema_version"],
        )
        self.assertEqual("loader.js", manifest["loader"]["file_name"])
        self.assertEqual(
            remote._sha256_bytes(
                (
                    ROOT
                    / "deploy"
                    / "openwebui-static"
                    / "loader.js"
                ).read_bytes()
            ),
            manifest["loader"]["content_sha256"],
        )
        self.assertTrue(
            all(
                item["content"]
                and remote._sha256_text(item["content"])
                == item["content_sha256"]
                for item in manifest["managed_prompts"]
            )
        )
        self.assertEqual(
            [contract.function_id for contract in FUNCTION_CONTRACTS],
            [item["function_id"] for item in manifest["functions"]],
        )
        self.assertTrue(manifest["runtime"]["vlm_default_enabled"])
        self.assertTrue(
            manifest["runtime"]["semantic_visual_profile_default_enabled"]
        )
        self.assertFalse(
            manifest["runtime"]["visual_auto_publication_enabled"]
        )
        semantic = manifest["provider_policy"]["semantic_visual_table_contract"]
        self.assertEqual(
            "broker_reports_semantic_table_transcription_prompt_v1",
            semantic["prompt_version"],
        )
        self.assertEqual(
            "broker_reports_semantic_visual_numeric_profile_v1",
            semantic["accepted_profile_id"],
        )
        self.assertEqual(64, len(semantic["prompt_sha256"]))
        self.assertEqual(64, len(semantic["canonical_schema_sha256"]))
        self.assertEqual(
            {
                "architecture_policy_version": "broker_reports_architecture_policy_v2",
                "knowledge_rag_vectorization_allowed": False,
                "local_ocr_production_allowed": False,
                "local_ocr_worker_pool_allowed": False,
                "native_openwebui_document_processing_allowed": False,
                "whole_document_provider_upload_allowed": False,
            },
            semantic["runtime_boundary"],
        )
        financial = manifest["provider_policy"][
            "financial_evidence_registry"
        ]
        self.assertEqual(
            "broker_reports_gate2_financial_evidence_registry_v1",
            financial["registry_version"],
        )
        self.assertEqual(64, len(financial["registry_hash"]))
        self.assertEqual("dual_read", financial["legacy_read_policy"])
        self.assertEqual(
            "new_schema_only", financial["write_policy"]
        )
        domain_release = manifest["functions"][-1]
        self.assertTrue(
            domain_release["valves"]["financial_evidence_enabled"]
        )
        self.assertEqual(
            financial["registry_version"],
            domain_release["valves"][
                "financial_evidence_registry_version"
            ],
        )
        self.assertFalse(
            manifest["functions"][1]["valves"][
                "semantic_selection_enabled"
            ]
        )
        self.assertEqual(1, manifest["runtime"]["gate1_heavy_concurrency"])
        self.assertEqual(2, manifest["runtime"]["gate2_local_maximum_concurrency"])
        self.assertEqual(
            "server-authoritative-v2",
            manifest["image"]["private_intake_contract"],
        )

    def test_manifest_digest_tampering_fails_closed(self):
        manifest = _manifest()
        manifest["runtime"]["vlm_default_enabled"] = False

        with self.assertRaisesRegex(ValueError, "manifest_digest_mismatch"):
            validate_manifest(manifest)

    def test_release_valves_enable_only_qualified_semantic_route(self):
        function_id = FUNCTION_CONTRACTS[0].function_id
        valves = merged_valves(
            function_id,
            {
                "unrelated_operator_setting": "preserved",
                "pdf_table_intake_enabled": False,
                "pdf_dual_vlm_enabled": False,
            },
        )

        self.assertEqual("preserved", valves["unrelated_operator_setting"])
        self.assertTrue(valves["pdf_table_intake_enabled"])
        self.assertTrue(valves["pdf_dual_vlm_enabled"])
        self.assertTrue(valves["pdf_semantic_visual_table_downstream_enabled"])
        self.assertEqual(
            "broker_reports_semantic_visual_table_migration_policy_v1",
            valves["pdf_semantic_visual_table_migration_policy_version"],
        )
        self.assertFalse(valves["pdf_hybrid_shadow_enabled"])
        self.assertFalse(valves["pdf_structural_repair_shadow_enabled"])
        self.assertTrue(valves_match(function_id, valves))
        self.assertEqual(64, valves["pdf_table_intake_maximum_pages"])
        self.assertEqual(8, valves["pdf_dual_vlm_maximum_candidates"])

        domain_valves = merged_valves(
            FUNCTION_CONTRACTS[-1].function_id,
            {"allow_standalone_semantic_visual_projections": False},
        )
        self.assertTrue(
            domain_valves["allow_standalone_semantic_visual_projections"]
        )
        self.assertTrue(domain_valves["answer_context_selection_enabled"])

        source_valves = merged_valves(
            FUNCTION_CONTRACTS[1].function_id,
            {"semantic_selection_enabled": True},
        )
        self.assertFalse(source_valves["semantic_selection_enabled"])
        self.assertTrue(
            valves_match(FUNCTION_CONTRACTS[1].function_id, source_valves)
        )

    def test_quiescence_counts_every_nonterminal_state(self):
        self.assertEqual(
            4,
            nonterminal_workload_count(
                {
                    "queued": 1,
                    "normalizing": 2,
                    "awaiting_review": 1,
                    "completed": 9,
                    "failed": 2,
                    "cancelled": 3,
                }
            ),
        )

    def test_verifier_requires_exact_function_revision_hash_and_valves(self):
        manifest = _manifest()
        expected = manifest["functions"][0]
        content = FUNCTION_CONTRACTS[0].bundle_path.read_text(encoding="utf-8")
        live = {
            "content": content,
            "type": "pipe",
            "is_active": 1,
            "is_global": 0,
            "meta": {
                "broker_reports_release": {
                    "source_revision": REVISION,
                    "manifest_sha256": manifest["manifest_sha256"],
                    "bundle_sha256": expected["content_sha256"],
                }
            },
        }

        passed = evaluate_function_release(
            expected=expected,
            live_function=live,
            live_valves=expected["valves"],
            source_revision=REVISION,
            manifest_sha256=manifest["manifest_sha256"],
        )
        live["meta"]["broker_reports_release"]["source_revision"] = "b" * 40
        failed = evaluate_function_release(
            expected=expected,
            live_function=live,
            live_valves=expected["valves"],
            source_revision=REVISION,
            manifest_sha256=manifest["manifest_sha256"],
        )

        self.assertTrue(passed["passed"], passed)
        self.assertFalse(failed["passed"])
        self.assertFalse(failed["checks"]["release_revision_match"])

    def test_action_and_runtime_checks_are_terminal_not_shape_only(self):
        manifest = _manifest()
        action_content = (
            SERVICE_ROOT
            / "openwebui_actions"
            / "broker_reports_private_intake_action.py"
        ).read_text(encoding="utf-8")
        action = evaluate_action_release(
            expected=manifest["action"],
            live={
                "content": action_content,
                "type": "action",
                "is_active": 1,
                "is_global": 0,
            },
        )
        runtime = {
            "image": {
                **manifest["image"],
                "running": True,
                "restart_count": 0,
            },
            "loader_sha256": manifest["loader"]["content_sha256"],
            "fitz_version": manifest["runtime"]["fitz_version"],
            "workload": {"nonterminal_jobs": 0, "owned_temp_entries": 0},
            "release_staging_entries": 0,
            "rollback_identity_sha256": "c" * 64,
            "rollback_loader_hash_exact": True,
        }
        checks = evaluate_remote_runtime(
            expected_manifest=manifest,
            runtime=runtime,
            rollback_identity_sha256="c" * 64,
        )
        runtime["workload"]["nonterminal_jobs"] = 1
        failed = evaluate_remote_runtime(
            expected_manifest=manifest,
            runtime=runtime,
            rollback_identity_sha256="c" * 64,
        )

        self.assertTrue(action["passed"], action)
        self.assertTrue(all(checks.values()), checks)
        self.assertFalse(failed["workload_quiescent"])

    def test_local_driver_surfaces_only_typed_safe_remote_error(self):
        completed = subprocess.CompletedProcess(
            args=["ssh"],
            returncode=1,
            stdout=json.dumps(
                {
                    "status": "error",
                    "code": "stage_release_prompt_contract_mismatch",
                }
            ),
            stderr="private remote traceback is not propagated",
        )

        with self.assertRaisesRegex(
            driver.StageReleaseDriverError,
            "stage_release_remote_failed:stage_release_prompt_contract_mismatch",
        ):
            driver._validated_remote_receipt(completed, apply=True)

        completed.stdout = json.dumps(
            {"status": "error", "code": "unsafe value with spaces"}
        )
        with self.assertRaisesRegex(
            driver.StageReleaseDriverError,
            "stage_release_remote_error_unclassified",
        ):
            driver._validated_remote_receipt(completed, apply=False)


class AtomicStageRemoteTransactionTests(unittest.TestCase):
    def _database(self, path: Path) -> None:
        conn = sqlite3.connect(path)
        try:
            conn.execute(
                """
                CREATE TABLE function(
                    id TEXT PRIMARY KEY,
                    content TEXT,
                    meta TEXT,
                    valves TEXT,
                    type TEXT,
                    is_active INTEGER,
                    is_global INTEGER,
                    updated_at INTEGER
                )
                """
            )
            for index, contract in enumerate(FUNCTION_CONTRACTS):
                conn.execute(
                    "INSERT INTO function VALUES (?, ?, ?, ?, 'pipe', 1, 0, ?)",
                    (
                        contract.function_id,
                        f"old-{index}",
                        json.dumps({"old": index}),
                        json.dumps({"old": index}),
                        index,
                    ),
                )
            conn.execute(
                """
                CREATE TABLE prompt(
                    id TEXT PRIMARY KEY,
                    command TEXT,
                    version_id TEXT,
                    is_active INTEGER,
                    content TEXT,
                    meta TEXT,
                    updated_at INTEGER
                )
                """
            )
            for index, contract in enumerate(_manifest()["managed_prompts"]):
                conn.execute(
                    "INSERT INTO prompt VALUES (?, ?, ?, 1, ?, ?, ?)",
                    (
                        contract["prompt_id"],
                        "old-command-" + str(index),
                        "old-version-" + str(index),
                        "old-content-" + str(index),
                        json.dumps({"old": index}),
                        index,
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def _function_rows(self, path: Path):
        ids = [contract.function_id for contract in FUNCTION_CONTRACTS]
        return remote._function_rows(path, ids)

    def _prompt_rows(self, path: Path):
        ids = [item["prompt_id"] for item in _manifest()["managed_prompts"]]
        return remote._prompt_rows(path, ids)

    def test_payload_requires_exact_staged_loader_bytes(self):
        manifest = _manifest()
        with tempfile.TemporaryDirectory() as temp:
            staging = Path(temp) / manifest["release_id"]
            staging.mkdir()
            for contract in FUNCTION_CONTRACTS:
                shutil.copyfile(
                    contract.bundle_path,
                    staging / contract.bundle_path.name,
                )
            loader_path = staging / manifest["loader"]["file_name"]
            shutil.copyfile(
                ROOT / "deploy" / "openwebui-static" / "loader.js",
                loader_path,
            )

            remote._validate_payload(staging, manifest)
            loader_path.write_bytes(b"tampered-loader")
            with self.assertRaisesRegex(
                remote.StageReleaseError,
                "loader_payload_digest_mismatch",
            ):
                remote._validate_payload(staging, manifest)

    def test_hash_guard_rolls_back_entire_sqlite_transaction(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "webui.db"
            self._database(db)
            before = self._function_rows(db)
            before_prompts = self._prompt_rows(db)
            replacement = {
                function_id: {
                    **row,
                    "content": "new-" + function_id,
                    "updated_at": 100,
                }
                for function_id, row in before.items()
            }
            replacement_prompts = {
                prompt_id: {**row, "content": "new-" + prompt_id}
                for prompt_id, row in before_prompts.items()
            }
            expected = remote._content_hashes(before)
            expected[FUNCTION_CONTRACTS[-1].function_id] = "0" * 64

            with self.assertRaisesRegex(
                remote.StageReleaseError,
                "function_changed_during_release",
            ):
                remote._replace_release_rows(
                    db_path=db,
                    replacement_function_rows=replacement,
                    replacement_prompt_rows=replacement_prompts,
                    expected_function_hashes=expected,
                    expected_prompt_hashes=remote._prompt_hashes(
                        before_prompts
                    ),
                )

            self.assertEqual(
                remote._content_hashes(before),
                remote._content_hashes(self._function_rows(db)),
            )
            self.assertEqual(
                remote._prompt_hashes(before_prompts),
                remote._prompt_hashes(self._prompt_rows(db)),
            )

    def test_loader_candidate_diff_is_validated_before_apply_and_replaced_exactly(
        self,
    ):
        manifest = _manifest()
        prior = b"prior-loader"
        candidate = b"candidate-loader"
        with tempfile.TemporaryDirectory() as temp:
            loader_path = Path(temp) / "loader.js"
            loader_path.write_bytes(prior)
            state = {
                "image": {
                    **manifest["image"],
                    "running": True,
                    "restart_count": 0,
                },
                "action": {
                    **manifest["action"],
                    "type": "action",
                },
                "loader": {
                    "content_sha256": remote._sha256_bytes(prior),
                },
                "fitz_version": manifest["runtime"]["fitz_version"],
            }

            remote._assert_static_contracts(
                state,
                manifest,
                require_candidate_loader=False,
            )
            with self.assertRaisesRegex(
                remote.StageReleaseError,
                "loader_contract_mismatch",
            ):
                remote._assert_static_contracts(
                    state,
                    manifest,
                    require_candidate_loader=True,
                )

            with mock.patch.object(remote, "LOADER_PATH", loader_path):
                remote._replace_loader(
                    content=candidate,
                    expected_sha256=remote._sha256_bytes(prior),
                )
                self.assertEqual(candidate, loader_path.read_bytes())
                with self.assertRaisesRegex(
                    remote.StageReleaseError,
                    "loader_changed_during_release",
                ):
                    remote._replace_loader(
                        content=prior,
                        expected_sha256=remote._sha256_bytes(prior),
                    )

    def test_rollback_artifact_retains_exact_loader_and_detects_tampering(self):
        manifest = _manifest()
        loader_bytes = b"previous-loader-bytes"
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "webui.db"
            self._database(db)
            before_state = {
                "functions": [],
                "action": {},
                "image": {},
                "loader": {
                    "content_sha256": remote._sha256_bytes(loader_bytes),
                },
                "managed_prompts": [],
            }
            rollback_root = Path(temp) / "rollbacks"
            with mock.patch.object(remote, "ROLLBACK_ROOT", rollback_root):
                value, identity, created, restored_loader = (
                    remote._rollback_artifact(
                        manifest=manifest,
                        function_rows=self._function_rows(db),
                        prompt_rows=self._prompt_rows(db),
                        before_state=before_state,
                        loader_bytes=loader_bytes,
                    )
                )
                rollback_dir = rollback_root / manifest["release_id"]
                metadata_path = rollback_dir / "function_rows.rollback.json"
                loader_path = rollback_dir / "loader.rollback.js"

                self.assertTrue(created)
                self.assertEqual(loader_bytes, restored_loader)
                self.assertEqual(loader_bytes, loader_path.read_bytes())
                self.assertEqual(
                    remote._sha256_bytes(metadata_path.read_bytes()),
                    identity,
                )
                self.assertEqual(
                    remote._sha256_bytes(loader_bytes),
                    value["previous_loader"]["content_sha256"],
                )

                loader_path.write_bytes(b"tampered-rollback-loader")
                with self.assertRaisesRegex(
                    remote.StageReleaseError,
                    "rollback_loader_invalid",
                ):
                    remote._rollback_artifact(
                        manifest=manifest,
                        function_rows=self._function_rows(db),
                        prompt_rows=self._prompt_rows(db),
                        before_state=before_state,
                        loader_bytes=loader_bytes,
                    )

    def test_prompt_drift_blocks_function_and_prompt_updates_in_one_transaction(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "webui.db"
            self._database(db)
            before = self._function_rows(db)
            before_prompts = self._prompt_rows(db)
            replacement = {
                function_id: {**row, "content": "new-" + function_id}
                for function_id, row in before.items()
            }
            replacement_prompts = remote._desired_prompt_rows(
                manifest=_manifest(),
                current_rows=before_prompts,
            )
            expected_prompt_hashes = remote._prompt_hashes(before_prompts)
            last_prompt_id = sorted(expected_prompt_hashes)[-1]
            expected_prompt_hashes[last_prompt_id] = "0" * 64

            with self.assertRaisesRegex(
                remote.StageReleaseError,
                "prompt_changed_during_release",
            ):
                remote._replace_release_rows(
                    db_path=db,
                    replacement_function_rows=replacement,
                    replacement_prompt_rows=replacement_prompts,
                    expected_function_hashes=remote._content_hashes(before),
                    expected_prompt_hashes=expected_prompt_hashes,
                )

            self.assertEqual(
                remote._content_hashes(before),
                remote._content_hashes(self._function_rows(db)),
            )
            self.assertEqual(
                remote._prompt_hashes(before_prompts),
                remote._prompt_hashes(self._prompt_rows(db)),
            )

    def test_desired_prompt_rows_preserve_exact_unchanged_rows(self):
        manifest = _manifest()
        current = {
            item["prompt_id"]: {
                "command": item["command"],
                "version_id": item["version"],
                "is_active": 1,
                "content": item["content"],
                "meta": json.dumps(
                    {**item["meta"], "preserved_operator_key": True},
                    ensure_ascii=False,
                ),
                "updated_at": index,
            }
            for index, item in enumerate(manifest["managed_prompts"])
        }

        desired = remote._desired_prompt_rows(
            manifest=manifest,
            current_rows=current,
        )

        self.assertEqual(
            remote._prompt_hashes(current),
            remote._prompt_hashes(desired),
        )
        self.assertTrue(
            all(
                json.loads(row["meta"])["preserved_operator_key"] is True
                for row in desired.values()
            )
        )

    def test_candidate_apply_and_exact_rollback_reach_terminal_states(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "webui.db"
            self._database(db)
            before = self._function_rows(db)
            before_prompts = self._prompt_rows(db)
            rollback_rows = remote._snapshot_function_rows(before)
            rollback_prompt_rows = remote._snapshot_prompt_rows(
                before_prompts
            )
            desired = {
                function_id: {
                    **row,
                    "content": "candidate-" + function_id,
                    "meta": json.dumps({"candidate": function_id}),
                    "valves": json.dumps({"candidate": True}),
                    "updated_at": 200,
                }
                for function_id, row in before.items()
            }
            manifest = _manifest()
            desired_prompts = remote._desired_prompt_rows(
                manifest=manifest,
                current_rows=before_prompts,
            )
            before_hashes = remote._content_hashes(before)
            desired_hashes = remote._content_hashes(desired)
            before_prompt_hashes = remote._prompt_hashes(before_prompts)
            desired_prompt_hashes = remote._prompt_hashes(desired_prompts)

            remote._replace_release_rows(
                db_path=db,
                replacement_function_rows=desired,
                replacement_prompt_rows=desired_prompts,
                expected_function_hashes=before_hashes,
                expected_prompt_hashes=before_prompt_hashes,
            )
            self.assertEqual(
                desired_hashes,
                remote._content_hashes(self._function_rows(db)),
            )
            self.assertEqual(
                desired_prompt_hashes,
                remote._prompt_hashes(self._prompt_rows(db)),
            )

            remote._replace_release_rows(
                db_path=db,
                replacement_function_rows=rollback_rows,
                replacement_prompt_rows=rollback_prompt_rows,
                expected_function_hashes=desired_hashes,
                expected_prompt_hashes=desired_prompt_hashes,
            )
            restored = self._function_rows(db)
            restored_prompts = self._prompt_rows(db)
            self.assertEqual(before_hashes, remote._content_hashes(restored))
            self.assertEqual(
                before_prompt_hashes,
                remote._prompt_hashes(restored_prompts),
            )
            self.assertEqual(
                rollback_rows,
                remote._snapshot_function_rows(restored),
            )
            self.assertEqual(
                rollback_prompt_rows,
                remote._snapshot_prompt_rows(restored_prompts),
            )

    def test_remote_cleanup_and_ssh_are_fail_closed(self):
        remote_source = (SCRIPTS / "broker_reports_atomic_stage_remote.py").read_text(
            encoding="utf-8"
        )
        driver_source = (
            SCRIPTS / "live_release_broker_reports_atomic_stage.py"
        ).read_text(encoding="utf-8")

        self.assertIn("resolved.parent != root", remote_source)
        self.assertIn("shutil.rmtree(resolved)", remote_source)
        self.assertIn("_restore_after_failure", remote_source)
        self.assertIn("_replace_loader", remote_source)
        self.assertIn("_raise_release_signal", remote_source)
        self.assertIn("elif not _container_running()", remote_source)
        self.assertIn('"BEGIN IMMEDIATE"', remote_source)
        self.assertIn("LOADER_PATH,", driver_source)
        self.assertIn('"StrictHostKeyChecking=yes"', driver_source)
        self.assertNotIn('"StrictHostKeyChecking=no"', driver_source)


if __name__ == "__main__":
    unittest.main()
