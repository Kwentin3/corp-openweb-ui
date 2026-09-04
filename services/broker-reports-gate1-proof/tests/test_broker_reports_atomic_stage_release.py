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
    GATE1_RETIRED_VALVE_KEYS,
    RELEASE_QUIESCENT_WORKLOAD_STATES,
    RETIRED_FUNCTION_IDS,
    SCHEMA_VERSION,
    build_manifest,
    merged_valves,
    nonterminal_workload_count,
    provider_policy_manifest,
    release_blocking_workload_count,
    validate_manifest,
    valves_match,
)
from broker_reports_release_source import (  # noqa: E402
    LOADER_REPOSITORY_PATH,
    git_blob_bytes,
)
from broker_reports_gate1 import GATE2_PROVIDER_PROFILES  # noqa: E402
from live_verify_broker_reports_atomic_stage_release import (  # noqa: E402
    _read_remote_runtime_state,
    evaluate_action_release,
    evaluate_function_release,
    evaluate_remote_runtime,
    evaluate_route_activation,
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
    def test_remote_verifier_payload_is_valid_python(self):
        def validate_remote_payload(*args, **kwargs):
            compile(kwargs["input"], "remote_runtime_verifier.py", "exec")
            return subprocess.CompletedProcess(args[0], 0, stdout="{}", stderr="")

        with mock.patch(
            "live_verify_broker_reports_atomic_stage_release.subprocess.run",
            side_effect=validate_remote_payload,
        ):
            self.assertEqual(
                {},
                _read_remote_runtime_state(
                    ssh_target="validated-target",
                    release_id="broker-reports-" + "a" * 12,
                ),
            )

    def test_delivery_verifier_exposes_only_current_pipeline_function(self):
        self.assertEqual(1, len(DELIVERY_FUNCTION_CONTRACTS))
        self.assertEqual(
            "broker_reports_gate1_pipe",
            DELIVERY_FUNCTION_CONTRACTS[0].function_id,
        )
        self.assertEqual(
            {
                "broker_reports_gate2_source_fact_pipe",
                "broker_reports_gate2_domain_source_fact_pipe",
            },
            set(RETIRED_FUNCTION_IDS),
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
        remote._validate_manifest(manifest)

        self.assertEqual(1, len(manifest["functions"]))
        self.assertEqual(list(RETIRED_FUNCTION_IDS), manifest["retired_function_ids"])
        self.assertEqual(12, len(manifest["managed_prompts"]))
        self.assertEqual(
            "broker_reports_atomic_stage_release_v10",
            manifest["schema_version"],
        )
        self.assertTrue(
            all(
                item["activation_policy"] == "preserve_existing"
                for item in manifest["functions"]
            )
        )
        self.assertEqual(SCHEMA_VERSION, remote.MANIFEST_SCHEMA_VERSION)
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
        self.assertEqual(
            REVISION,
            manifest["functions"][0]["valves"][
                "pdf_document_ai_qualification_repository_head"
            ],
        )
        self.assertTrue(manifest["runtime"]["pdf_document_ai_static_ready"])
        self.assertFalse(manifest["runtime"]["pdf_document_ai_live_qualified"])
        self.assertFalse(manifest["runtime"]["legacy_table_route_available"])
        self.assertNotIn(
            "semantic_visual_table_contract", manifest["provider_policy"]
        )
        document_ai = manifest["provider_policy"]["pdf_document_ai_contract"]
        self.assertFalse(document_ai["configured"])
        self.assertEqual("static_ready", document_ai["adapter_status"])
        self.assertEqual("mistral_ocr", document_ai["selected_engine"])
        self.assertEqual(
            "mistral_serverless_ocr_adapter_v1", document_ai["selected_adapter"]
        )
        self.assertTrue(document_ai["static_ready"])
        self.assertFalse(document_ai["live_qualified"])
        self.assertEqual("PdfDocumentExtractorFactory", document_ai["composition_owner"])
        self.assertEqual(
            {
                "unconfigured": "PDF_DOCUMENT_AI_NOT_CONFIGURED",
                "selected_unqualified": "PDF_DOCUMENT_AI_LIVE_QUALIFICATION_REQUIRED",
            },
            document_ai["terminal_blockers"],
        )
        self.assertFalse(document_ai["automatic_fallback"])
        self.assertEqual(
            {
                "architecture_policy_version": "broker_reports_architecture_policy_v26",
                "knowledge_rag_vectorization_allowed": False,
                "local_ocr_production_allowed": False,
                "local_ocr_worker_pool_allowed": False,
            },
            document_ai["runtime_boundary"],
        )
        self.assertNotIn(
            "financial_evidence_registry", manifest["provider_policy"]
        )
        self.assertFalse(manifest["functions"][0]["valves"]["ndfl_gate3_enabled"])
        self.assertTrue(
            manifest["functions"][0]["valves"][
                "ordinary_trade_candidate_enabled"
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
        manifest["runtime"]["pdf_document_ai_live_qualified"] = True

        with self.assertRaisesRegex(ValueError, "manifest_digest_mismatch"):
            validate_manifest(manifest)

    def test_resealed_manifest_cannot_open_pdf_document_ai_live_admission(self):
        manifest = _manifest()
        manifest["runtime"]["pdf_document_ai_live_qualified"] = True
        manifest["manifest_sha256"] = remote._sha256_text(
            remote._canonical_json(
                {key: value for key, value in manifest.items() if key != "manifest_sha256"}
            )
        )

        with self.assertRaisesRegex(ValueError, "current_route_invalid"):
            validate_manifest(manifest)
        with self.assertRaisesRegex(
            remote.StageReleaseError,
            "stage_release_pdf_document_ai_admission_invalid",
        ):
            remote._validate_manifest(manifest)

    def test_release_valves_remove_retired_pdf_routes(self):
        function_id = FUNCTION_CONTRACTS[0].function_id
        valves = merged_valves(
            function_id,
            {
                "unrelated_operator_setting": "preserved",
                GATE1_RETIRED_VALVE_KEYS[0]: False,
                "canonical_gate2_compare_enabled": True,
                "pdf_dual_vlm_enabled": False,
            },
        )

        self.assertEqual("preserved", valves["unrelated_operator_setting"])
        self.assertNotIn(GATE1_RETIRED_VALVE_KEYS[0], valves)
        self.assertNotIn("canonical_gate2_compare_enabled", valves)
        self.assertNotIn("pdf_dual_vlm_enabled", valves)
        self.assertNotIn("pdf_semantic_visual_table_downstream_enabled", valves)
        self.assertNotIn("pdf_hybrid_shadow_enabled", valves)
        self.assertNotIn("pdf_structural_repair_shadow_enabled", valves)
        self.assertTrue(valves["canonical_gate2_write_enabled"])
        self.assertTrue(valves["canonical_gate2_read_enabled"])
        self.assertFalse(valves["ndfl_gate3_enabled"])
        self.assertTrue(valves["ordinary_trade_candidate_enabled"])
        self.assertTrue(valves_match(function_id, valves))
        self.assertTrue(all(key not in valves for key in GATE1_RETIRED_VALVE_KEYS))

    def test_quiescence_counts_every_nonterminal_state(self):
        state_counts = {
            "queued": 1,
            "normalizing": 2,
            "awaiting_review": 1,
            "completed": 9,
            "failed": 2,
            "cancelled": 3,
        }

        self.assertEqual(4, nonterminal_workload_count(state_counts))
        self.assertEqual(3, release_blocking_workload_count(state_counts))
        self.assertEqual(
            RELEASE_QUIESCENT_WORKLOAD_STATES,
            remote.RELEASE_QUIESCENT_WORKLOAD_STATES,
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
            expected_active=True,
        )
        live["meta"]["broker_reports_release"]["source_revision"] = "b" * 40
        failed = evaluate_function_release(
            expected=expected,
            live_function=live,
            live_valves=expected["valves"],
            source_revision=REVISION,
            manifest_sha256=manifest["manifest_sha256"],
            expected_active=True,
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
            "workload": {
                "nonterminal_jobs": 5,
                "release_blocking_jobs": 0,
                "unsafe_review_jobs": 0,
                "owned_temp_entries": 0,
            },
            "release_staging_entries": 0,
            "rollback_identity_sha256": "c" * 64,
            "rollback_loader_hash_exact": True,
            "previous_function_activation": {
                item["function_id"]: index == 0
                for index, item in enumerate(manifest["functions"])
            },
        }
        checks = evaluate_remote_runtime(
            expected_manifest=manifest,
            runtime=runtime,
            rollback_identity_sha256="c" * 64,
        )
        runtime["workload"]["release_blocking_jobs"] = 1
        failed = evaluate_remote_runtime(
            expected_manifest=manifest,
            runtime=runtime,
            rollback_identity_sha256="c" * 64,
        )

        self.assertTrue(action["passed"], action)
        self.assertTrue(all(checks.values()), checks)
        self.assertFalse(failed["workload_quiescent"])

    def test_function_release_preserves_an_inactive_pipe(self):
        manifest = _manifest()
        expected = manifest["functions"][0]
        content = FUNCTION_CONTRACTS[0].bundle_path.read_text(encoding="utf-8")
        result = evaluate_function_release(
            expected=expected,
            live_function={
                "content": content,
                "type": "pipe",
                "is_active": 0,
                "is_global": 0,
                "meta": {
                    "broker_reports_release": {
                        "source_revision": REVISION,
                        "manifest_sha256": manifest["manifest_sha256"],
                        "bundle_sha256": expected["content_sha256"],
                    }
                },
            },
            live_valves=expected["valves"],
            source_revision=REVISION,
            manifest_sha256=manifest["manifest_sha256"],
            expected_active=False,
        )

        self.assertTrue(result["passed"], result)
        self.assertFalse(result["expected_active"])

    def test_parked_review_is_quiescent_only_without_runtime_ownership(self):
        remote._assert_quiescent(
            {
                "workload": {
                    "nonterminal_jobs": 5,
                    "release_blocking_jobs": 0,
                    "unsafe_review_jobs": 0,
                    "owned_temp_entries": 0,
                }
            }
        )

        with self.assertRaisesRegex(
            remote.StageReleaseError,
            "stage_release_workload_not_quiescent",
        ):
            remote._assert_quiescent(
                {
                    "workload": {
                        "nonterminal_jobs": 5,
                        "release_blocking_jobs": 1,
                        "unsafe_review_jobs": 1,
                        "owned_temp_entries": 0,
                    }
                }
            )

    def test_verifier_requires_fail_closed_pdf_document_ai_route(self):
        manifest = _manifest()
        checks = evaluate_route_activation(
            expected_manifest=manifest,
            gate1_valves=manifest["functions"][0]["valves"],
        )
        self.assertTrue(all(checks.values()), checks)

        drifted = dict(manifest["functions"][0]["valves"])
        drifted["pdf_dual_vlm_enabled"] = True
        failed = evaluate_route_activation(
            expected_manifest=manifest,
            gate1_valves=drifted,
        )
        self.assertFalse(failed["pdf_document_ai_fail_closed"])

        manifest["provider_policy"]["pdf_document_ai_contract"][
            "terminal_blockers"
        ].pop("selected_unqualified")
        contract_failed = evaluate_route_activation(
            expected_manifest=manifest,
            gate1_valves=manifest["functions"][0]["valves"],
        )
        self.assertFalse(contract_failed["pdf_document_ai_contract_identity_exact"])

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
            for index, function_id in enumerate(RETIRED_FUNCTION_IDS, 100):
                conn.execute(
                    "INSERT INTO function VALUES (?, ?, ?, ?, 'pipe', 1, 0, ?)",
                    (
                        function_id,
                        f"retired-{index}",
                        json.dumps({"retired": index}),
                        json.dumps({"retired": index}),
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
        ids = [
            *[contract.function_id for contract in FUNCTION_CONTRACTS],
            *RETIRED_FUNCTION_IDS,
        ]
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

    def test_post_replace_failure_restores_loader_rows_and_health(self):
        prior_loader = b"prior-loader"
        candidate_loader = b"candidate-loader"
        manifest = build_manifest(
            source_revision=REVISION,
            prompt_contracts=expected_prompt_contracts(),
            provider_policy=provider_policy_manifest(
                GATE2_PROVIDER_PROFILES
            ),
            loader_bytes=candidate_loader,
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staging = root / manifest["release_id"]
            staging.mkdir()
            (staging / "manifest.json").write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
            (staging / manifest["loader"]["file_name"]).write_bytes(
                candidate_loader
            )
            db = root / "webui.db"
            self._database(db)
            loader_path = root / "loader.js"
            loader_path.write_bytes(prior_loader)
            before_rows = self._function_rows(db)
            before_prompts = self._prompt_rows(db)
            rollback_rows = remote._snapshot_function_rows(before_rows)
            rollback_prompts = remote._snapshot_prompt_rows(before_prompts)
            before_state = {
                "functions": [
                    {
                        "function_id": contract.function_id,
                        "active": True,
                        "global": False,
                        "type": "pipe",
                    }
                    for contract in FUNCTION_CONTRACTS
                ],
                "loader": {
                    "content_sha256": remote._sha256_bytes(prior_loader),
                },
                "image": {},
                "action": {},
                "managed_prompts": [],
                "workload": {},
                "counters": {},
            }
            rollback = {
                "previous_function_rows": rollback_rows,
                "previous_prompt_rows": rollback_prompts,
                "previous_loader": {
                    "content_sha256": remote._sha256_bytes(prior_loader),
                },
            }
            original_atomic_write = remote._write_bytes_atomically
            atomic_write_calls = 0

            def fail_after_first_replace(*, path, content, mode):
                nonlocal atomic_write_calls
                atomic_write_calls += 1
                original_atomic_write(path=path, content=content, mode=mode)
                if atomic_write_calls == 1:
                    raise RuntimeError("fault_after_loader_replace")

            with (
                mock.patch.object(remote, "LOADER_PATH", loader_path),
                mock.patch.object(remote, "_validate_manifest"),
                mock.patch.object(remote, "_validate_payload"),
                mock.patch.object(remote, "_volume_mount", return_value=root),
                mock.patch.object(remote, "_webui_db", return_value=db),
                mock.patch.object(
                    remote,
                    "_live_state",
                    return_value=before_state,
                ),
                mock.patch.object(remote, "_assert_static_contracts"),
                mock.patch.object(remote, "_assert_prompt_set_present"),
                mock.patch.object(remote, "_assert_quiescent"),
                mock.patch.object(
                    remote,
                    "_desired_rows",
                    return_value=before_rows,
                ),
                mock.patch.object(
                    remote,
                    "_rollback_artifact",
                    return_value=(
                        rollback,
                        "f" * 64,
                        True,
                        prior_loader,
                    ),
                ),
                mock.patch.object(
                    remote,
                    "_write_bytes_atomically",
                    side_effect=fail_after_first_replace,
                ),
                mock.patch.object(remote, "_stop_container") as stop_mock,
                mock.patch.object(remote, "_start_container") as start_mock,
                mock.patch.object(remote, "_wait_healthy") as health_mock,
                mock.patch.object(
                    remote,
                    "_container_running",
                    return_value=False,
                ),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "fault_after_loader_replace",
                ):
                    remote.execute(
                        staging_dir=staging,
                        apply=True,
                        prove_rollback=False,
                    )

            self.assertEqual(prior_loader, loader_path.read_bytes())
            self.assertEqual(
                rollback_rows,
                remote._snapshot_function_rows(self._function_rows(db)),
            )
            self.assertEqual(
                rollback_prompts,
                remote._snapshot_prompt_rows(self._prompt_rows(db)),
            )
            self.assertEqual(2, stop_mock.call_count)
            start_mock.assert_called_once_with()
            health_mock.assert_called_once_with()

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

    def test_desired_function_rows_preserve_existing_activation(self):
        manifest = _manifest()
        current = {
            contract.function_id: {
                "content": "old",
                "meta": "{}",
                "valves": "{}",
                "type": "pipe",
                "is_active": 1 if index == 0 else 0,
                "is_global": 0,
                "updated_at": index,
            }
            for index, contract in enumerate(FUNCTION_CONTRACTS)
        }

        desired = remote._desired_rows(
            staging_dir=ROOT
            / "services"
            / "broker-reports-gate1-proof"
            / "openwebui_actions",
            manifest=manifest,
            current_rows=current,
        )

        self.assertEqual(
            {function_id: row["is_active"] for function_id, row in current.items()},
            {function_id: row["is_active"] for function_id, row in desired.items()},
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
