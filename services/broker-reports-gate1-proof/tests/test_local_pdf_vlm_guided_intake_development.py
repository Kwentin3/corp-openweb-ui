from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "local_pdf_vlm_guided_intake_development.py"
SCORER_PATH = ROOT / "scripts" / "local_pdf_vlm_guided_intake_development_score.py"


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = _load_script("development_runner", RUNNER_PATH)
SCORER = _load_script("development_scorer", SCORER_PATH)
MANIFEST_SHA = "a" * 64


class LocalPdfVlmGuidedIntakeDevelopmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_run_command_exposes_no_reference_argument(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(RUNNER_PATH), "run", "--help"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        self.assertNotIn("--reference", completed.stdout)

    def test_gate_uses_sealed_terminal_then_distinct_scorer_process(self) -> None:
        fake_runner = self.root / "fake_runner.py"
        fake_scorer = self.root / "fake_scorer.py"
        fake_runner.write_text(_fake_runner_source(), encoding="utf-8")
        fake_scorer.write_text(_fake_scorer_source(), encoding="utf-8")
        reference = self.root / "reference.json"
        reference.write_text("{}", encoding="utf-8")
        output = self.root / "gate"

        returncode = RUNNER.run_gate_processes(
            manifest=self.root / "manifest.json",
            corpus_root=self.root / "corpus",
            output_root=output,
            env_file=self.root / ".env",
            repo_root=self.root,
            bundle=self.root / "bundle.py",
            reference=reference,
            runner_script=fake_runner,
            scorer_script=fake_scorer,
        )

        self.assertEqual(0, returncode)
        process = json.loads(
            (output / "gate_processes.safe.json").read_text(encoding="utf-8")
        )
        self.assertTrue(process["separate_processes"])
        self.assertNotEqual(process["run_pid"], process["scorer_pid"])
        self.assertNotEqual(os.getpid(), process["run_pid"])
        self.assertNotEqual(os.getpid(), process["scorer_pid"])
        self.assertTrue(process["terminal_sealed_before_scorer_started"])
        self.assertFalse(process["reference_argument_passed_to_run"])
        self.assertTrue(process["reference_argument_passed_to_scorer"])
        self.assertNotIn("--reference", process["run_command_argument_names"])
        self.assertIn("--reference", process["scorer_command_argument_names"])
        score = json.loads((output / "score.json").read_text(encoding="utf-8"))
        self.assertEqual("WORKS_ON_DEVELOPMENT_CORPUS", score["binary_result"])
        self.assertTrue(score["terminal_verified_before_reference"])

    def test_gate_preserves_runner_failure_without_starting_scorer(self) -> None:
        fake_runner = self.root / "fake_failed_runner.py"
        fake_scorer = self.root / "fake_probe_scorer.py"
        fake_runner.write_text(
            _fake_incomplete_runner_source(exit_code=7), encoding="utf-8"
        )
        fake_scorer.write_text(_fake_probe_scorer_source(), encoding="utf-8")
        reference = self.root / "reference.json"
        reference.write_text('{"human": "reference"}', encoding="utf-8")
        output = self.root / "failed-gate"

        returncode = RUNNER.run_gate_processes(
            manifest=self.root / "manifest.json",
            corpus_root=self.root / "corpus",
            output_root=output,
            env_file=self.root / ".env",
            repo_root=self.root,
            bundle=self.root / "bundle.py",
            reference=reference,
            runner_script=fake_runner,
            scorer_script=fake_scorer,
        )

        process = json.loads(
            (output / "gate_processes.safe.json").read_text(encoding="utf-8")
        )
        self.assertEqual(7, returncode)
        self.assertEqual(7, process["run_returncode"])
        self.assertIsNone(process["scorer_pid"])
        self.assertIsNone(process["scorer_returncode"])
        self.assertFalse(process["scorer_started"])
        self.assertFalse(process["separate_processes"])
        self.assertFalse(process["reference_argument_passed_to_scorer"])
        self.assertEqual(
            ["development_runner_failed", "development_terminal_not_sealed"],
            process["gate_blocker_codes"],
        )
        self.assertFalse((output / "reference-read.marker").exists())

    def test_gate_requires_terminal_and_seal_before_starting_scorer(self) -> None:
        fake_runner = self.root / "fake_unsealed_runner.py"
        fake_scorer = self.root / "fake_probe_scorer.py"
        fake_runner.write_text(
            _fake_incomplete_runner_source(exit_code=0, write_terminal=True),
            encoding="utf-8",
        )
        fake_scorer.write_text(_fake_probe_scorer_source(), encoding="utf-8")
        reference = self.root / "reference.json"
        reference.write_text('{"human": "reference"}', encoding="utf-8")
        output = self.root / "unsealed-gate"

        returncode = RUNNER.run_gate_processes(
            manifest=self.root / "manifest.json",
            corpus_root=self.root / "corpus",
            output_root=output,
            env_file=self.root / ".env",
            repo_root=self.root,
            bundle=self.root / "bundle.py",
            reference=reference,
            runner_script=fake_runner,
            scorer_script=fake_scorer,
        )

        process = json.loads(
            (output / "gate_processes.safe.json").read_text(encoding="utf-8")
        )
        self.assertEqual(1, returncode)
        self.assertEqual(0, process["run_returncode"])
        self.assertIsNone(process["scorer_pid"])
        self.assertIsNone(process["scorer_returncode"])
        self.assertFalse(process["terminal_sealed_before_scorer_started"])
        self.assertFalse(process["scorer_started"])
        self.assertFalse(process["separate_processes"])
        self.assertEqual(
            ["development_terminal_not_sealed"],
            process["gate_blocker_codes"],
        )
        self.assertFalse((output / "reference-read.marker").exists())

    def test_scorer_rejects_terminal_tamper_before_reference_access(self) -> None:
        terminal, reference = _passing_fixture()
        terminal_path, seal_path, reference_path, output_path = self._write_fixture(
            terminal, reference
        )
        terminal_path.write_bytes(terminal_path.read_bytes() + b"\n")
        reference_path.unlink()

        completed = _score(terminal_path, seal_path, reference_path, output_path)

        self.assertEqual(1, completed.returncode)
        self.assertEqual(
            "DOES_NOT_WORK_ON_DEVELOPMENT_CORPUS",
            completed.stdout.splitlines()[0],
        )
        self.assertIn(
            "reason=development_terminal_seal_checksum_mismatch",
            completed.stdout,
        )
        result = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertFalse(result["reference_accessed_after_terminal_verification"])

    def test_negative_provider_call_budget_is_exact_binary_failure(self) -> None:
        terminal, reference = _passing_fixture()
        negative = next(
            item for item in terminal["cases"] if item["case_id"] == "negative_toc"
        )
        negative["target_terminal"]["count_tokens_calls"] = 1
        terminal_path, seal_path, reference_path, output_path = self._write_fixture(
            terminal, reference
        )

        completed = _score(terminal_path, seal_path, reference_path, output_path)

        self.assertEqual(1, completed.returncode)
        self.assertEqual(
            "DOES_NOT_WORK_ON_DEVELOPMENT_CORPUS",
            completed.stdout.splitlines()[0],
        )
        self.assertIn("condition_3 target=negative_toc", completed.stdout)
        self.assertIn(
            "reason=development_negative_provider_budget_or_acceptance_invalid",
            completed.stdout,
        )

    def test_negative_upstream_block_cannot_pass_as_normal_skip(self) -> None:
        terminal, reference = _passing_fixture()
        negative = next(
            item for item in terminal["cases"] if item["case_id"] == "negative_toc"
        )
        negative["target_terminal"]["terminal_status"] = "guided_upstream_blocked"
        terminal_path, seal_path, reference_path, output_path = self._write_fixture(
            terminal, reference
        )

        completed = _score(terminal_path, seal_path, reference_path, output_path)

        self.assertEqual(1, completed.returncode)
        self.assertIn("condition_3 target=negative_toc", completed.stdout)
        self.assertIn(
            "reason=development_negative_provider_budget_or_acceptance_invalid",
            completed.stdout,
        )

    def test_positive_unprocessable_target_cannot_pass_route_condition(self) -> None:
        terminal, reference = _passing_fixture()
        positive = next(
            item for item in terminal["cases"] if item["case_id"] == "betterment_p4"
        )
        positive["target_terminal"]["intake_decisions"]["processability"][
            "decision"
        ] = "unsupported"
        terminal_path, seal_path, reference_path, output_path = self._write_fixture(
            terminal, reference
        )

        completed = _score(terminal_path, seal_path, reference_path, output_path)

        self.assertEqual(1, completed.returncode)
        self.assertIn("condition_1 target=betterment_p4", completed.stdout)
        self.assertIn("reason=development_positive_route_mismatch", completed.stdout)

    def test_positive_count_without_generated_proposal_fails_route_condition(
        self,
    ) -> None:
        terminal, reference = _passing_fixture()
        positive = next(
            item for item in terminal["cases"] if item["case_id"] == "betterment_p4"
        )
        positive["target_terminal"]["generate_calls"] = 0
        positive["target_terminal"]["proposal"] = None
        accounting = positive["target_terminal"]["provider_accounting"]
        accounting["generate_calls"] = 0
        accounting["journal_generate_calls"] = 0
        accounting.pop("accounting_checksum")
        accounting["accounting_checksum"] = hashlib.sha256(
            _json_bytes(accounting)
        ).hexdigest()
        terminal_path, seal_path, reference_path, output_path = self._write_fixture(
            terminal, reference
        )

        completed = _score(terminal_path, seal_path, reference_path, output_path)

        self.assertEqual(1, completed.returncode)
        self.assertIn("condition_1 target=betterment_p4", completed.stdout)
        self.assertIn("reason=development_positive_route_mismatch", completed.stdout)

    def test_generated_call_without_actual_tokens_fails_exact_accounting_contract(
        self,
    ) -> None:
        terminal, reference = _passing_fixture()
        positive = next(
            item for item in terminal["cases"] if item["case_id"] == "betterment_p4"
        )
        target = positive["target_terminal"]
        target["provider_accounting"]["actual_input_tokens"] = None
        _reseal_provider_projection(target)
        terminal_path, seal_path, reference_path, output_path = self._write_fixture(
            terminal, reference
        )

        completed = _score(terminal_path, seal_path, reference_path, output_path)

        self.assertEqual(1, completed.returncode)
        self.assertIn("condition_9 target=betterment_p4", completed.stdout)
        self.assertIn(
            "reason=development_provider_actual_input_tokens_missing",
            completed.stdout,
        )

    def test_resolved_model_drift_fails_exact_manifest_contract(self) -> None:
        terminal, reference = _passing_fixture()
        positive = next(
            item for item in terminal["cases"] if item["case_id"] == "betterment_p4"
        )
        target = positive["target_terminal"]
        target["provider_accounting"]["model_resolved"] = "models/other"
        _reseal_provider_projection(target)
        terminal_path, seal_path, reference_path, output_path = self._write_fixture(
            terminal, reference
        )

        completed = _score(terminal_path, seal_path, reference_path, output_path)

        self.assertEqual(1, completed.returncode)
        self.assertIn(
            "reason=development_provider_manifest_model_mismatch",
            completed.stdout,
        )

    def test_specific_pre_provider_geometry_block_allows_exact_zero_calls(
        self,
    ) -> None:
        terminal, reference = _passing_fixture()
        positive = next(
            item for item in terminal["cases"] if item["case_id"] == "betterment_p4"
        )
        target = positive["target_terminal"]
        target.update(
            {
                "terminal_status": "guided_upstream_blocked",
                "reason_codes": ["pdf_visual_topology_atom_bbox_invalid"],
                "count_tokens_calls": 0,
                "generate_calls": 0,
                "hidden_retry": False,
                "provider_failover": False,
                "provider_accounting": _provider_accounting(calls=0, image=False),
            }
        )
        target["provider_accounting_verification"] = _provider_verification(
            target["provider_accounting"],
            journal=False,
            pre_provider_zero_call_allowed=True,
        )
        terminal_path, seal_path, reference_path, output_path = self._write_fixture(
            terminal, reference
        )

        completed = _score(terminal_path, seal_path, reference_path, output_path)

        self.assertEqual(1, completed.returncode)
        self.assertIn("condition_1 target=betterment_p4", completed.stdout)
        self.assertNotIn("condition_9 target=betterment_p4", completed.stdout)

    def test_pre_provider_geometry_reason_allowlist_matches_runtime_classes(
        self,
    ) -> None:
        expected = {
            "pdf_visual_topology_atom_bbox_invalid",
            "pdf_visual_topology_atom_contract_invalid",
            "pdf_visual_topology_atom_normalization_defect",
            "pdf_visual_topology_atom_outside_selected_source_region",
            "pdf_visual_topology_coordinate_transform_defect",
            "pdf_visual_topology_provider_package_construction_invalid",
        }

        self.assertEqual(expected, RUNNER.PRE_PROVIDER_ZERO_CALL_REASONS)
        self.assertEqual(expected, SCORER.PRE_PROVIDER_ZERO_CALL_REASONS)

    def test_count_only_route_accepts_exact_transport_accounting(self) -> None:
        terminal, reference = _passing_fixture()
        positive = next(
            item for item in terminal["cases"] if item["case_id"] == "betterment_p4"
        )
        target = positive["target_terminal"]
        target["generate_calls"] = 0
        target["proposal"] = None
        accounting = target["provider_accounting"]
        accounting.update(
            {
                "generate_calls": 0,
                "journal_generate_calls": 0,
                "actual_input_tokens": None,
                "output_tokens": None,
                "attempt_id": None,
                "provider_profile": None,
                "provider_profile_revision": None,
                "model_resolved": None,
            }
        )
        _reseal_provider_projection(target)
        terminal_path, seal_path, reference_path, output_path = self._write_fixture(
            terminal, reference
        )

        completed = _score(terminal_path, seal_path, reference_path, output_path)

        self.assertEqual(1, completed.returncode)
        self.assertIn("condition_1 target=betterment_p4", completed.stdout)
        self.assertNotIn("condition_9 target=betterment_p4", completed.stdout)

    def test_post_provider_binding_failure_cannot_claim_zero_calls(self) -> None:
        terminal, reference = _passing_fixture()
        positive = next(
            item for item in terminal["cases"] if item["case_id"] == "betterment_p4"
        )
        target = positive["target_terminal"]
        target.update(
            {
                "terminal_status": "guided_upstream_blocked",
                "reason_codes": ["pdf_vlm_region_binding_parent_atom_crossing"],
                "count_tokens_calls": 0,
                "generate_calls": 0,
                "hidden_retry": False,
                "provider_failover": False,
                "provider_accounting": _provider_accounting(calls=0, image=False),
            }
        )
        target["provider_accounting_verification"] = _provider_verification(
            target["provider_accounting"], journal=False
        )
        terminal_path, seal_path, reference_path, output_path = self._write_fixture(
            terminal, reference
        )

        completed = _score(terminal_path, seal_path, reference_path, output_path)

        self.assertEqual(1, completed.returncode)
        self.assertIn("condition_9 target=betterment_p4", completed.stdout)
        self.assertIn(
            "reason=development_provider_pre_provider_reason_invalid",
            completed.stdout,
        )

    def test_duplicate_target_state_emits_specific_cardinality_failure(self) -> None:
        terminal, reference = _passing_fixture()
        positive = next(
            item for item in terminal["cases"] if item["case_id"] == "betterment_p4"
        )
        target = positive["target_terminal"]
        target["target_state_payloads_total"] = 2
        target["terminal_cardinality_verified"] = False
        target["cardinality_failure_codes"] = [
            "development_target_state_cardinality_invalid"
        ]
        terminal_path, seal_path, reference_path, output_path = self._write_fixture(
            terminal, reference
        )

        completed = _score(terminal_path, seal_path, reference_path, output_path)

        self.assertEqual(1, completed.returncode)
        self.assertIn("condition_10 target=betterment_p4", completed.stdout)
        self.assertIn(
            "reason=development_target_state_cardinality_invalid",
            completed.stdout,
        )

    def test_all_twelve_conditions_emit_exact_success_and_zero_exit(self) -> None:
        terminal, reference = _passing_fixture()
        terminal_path, seal_path, reference_path, output_path = self._write_fixture(
            terminal, reference
        )

        completed = _score(terminal_path, seal_path, reference_path, output_path)

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual("WORKS_ON_DEVELOPMENT_CORPUS\n", completed.stdout)
        result = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual([], result["failed_contracts"])
        self.assertEqual(12, len(result["conditions"]))
        self.assertTrue(all(item["passed"] for item in result["conditions"]))
        self.assertTrue(result["terminal_unchanged_during_scoring"])
        self.assertTrue(result["reference_accessed_after_terminal_verification"])

    def test_page_region_with_zero_parser_candidates_keeps_source_proof(self) -> None:
        terminal, reference = _passing_fixture()
        moomoo = next(
            item for item in terminal["cases"] if item["case_id"] == "moomoo_compound"
        )
        region = moomoo["target_terminal"]["binding_result"]["region_results"][0]
        accounting = region["candidate_accounting"]
        accounting["scope_candidates_total"] = 0
        accounting["included_candidate_ids"] = []
        accounting["excluded_candidate_ids"] = []
        accounting["crossing_candidate_ids"] = []
        self.assertNotEqual(
            region["materialization"]["selected_candidate_ids"],
            accounting["included_candidate_ids"],
        )
        terminal_path, seal_path, reference_path, output_path = self._write_fixture(
            terminal, reference
        )

        completed = _score(terminal_path, seal_path, reference_path, output_path)

        self.assertEqual(0, completed.returncode, completed.stdout)
        self.assertEqual("WORKS_ON_DEVELOPMENT_CORPUS\n", completed.stdout)

    def test_exact_accepted_region_counts_when_peer_region_is_blocked(self) -> None:
        terminal, reference = _passing_fixture()
        moomoo = next(
            item for item in terminal["cases"] if item["case_id"] == "moomoo_compound"
        )
        target = moomoo["target_terminal"]
        target["binding_result"]["region_results"][1]["runtime_terminal_status"] = (
            "validation_blocked"
        )
        target["binding_result"]["source_accounting"]["regions_accepted"] = 1
        terminal_path, seal_path, reference_path, output_path = self._write_fixture(
            terminal, reference
        )

        completed = _score(terminal_path, seal_path, reference_path, output_path)

        self.assertEqual(0, completed.returncode, completed.stdout)
        result = json.loads(output_path.read_text(encoding="utf-8"))
        for condition in (6, 7, 8):
            observed = next(
                item for item in result["conditions"] if item["condition"] == condition
            )
            self.assertTrue(observed["passed"], observed)

    def test_accepted_region_is_compared_with_same_position_reference(self) -> None:
        terminal, reference = _passing_fixture()
        moomoo = next(
            item for item in terminal["cases"] if item["case_id"] == "moomoo_compound"
        )
        target = moomoo["target_terminal"]
        first, second = target["binding_result"]["region_results"]
        first["runtime_terminal_status"] = "validation_blocked"
        second["materialization"]["cells"][0]["resolved_source_values"] = [
            "moomoo_compound value 1"
        ]
        target["binding_result"]["source_accounting"]["regions_accepted"] = 1
        terminal_path, seal_path, reference_path, output_path = self._write_fixture(
            terminal, reference
        )

        completed = _score(terminal_path, seal_path, reference_path, output_path)

        self.assertEqual(1, completed.returncode)
        self.assertIn("condition_8 target=moomoo_compound", completed.stdout)
        self.assertIn(
            "reason=development_incorrect_structure_accepted", completed.stdout
        )

    def test_retained_prefix_assertion_rejects_resealed_evidence_drift(self) -> None:
        terminal, reference = _passing_fixture()
        ibkr = next(
            item for item in terminal["cases"] if item["case_id"] == "ibkr_prefix"
        )
        ibkr["source"]["retained_prefix_evidence"]["completed_pages_total"] = 11
        terminal_path, seal_path, reference_path, output_path = self._write_fixture(
            terminal, reference
        )

        completed = _score(terminal_path, seal_path, reference_path, output_path)

        self.assertEqual(1, completed.returncode)
        self.assertIn("condition_10 target=ibkr_prefix", completed.stdout)
        self.assertIn(
            "reason=development_retained_prefix_evidence_invalid",
            completed.stdout,
        )

    def test_manifest_rejects_embedded_human_labels(self) -> None:
        manifest = _manifest_fixture()
        manifest["cases"][0]["expected_kind"] = "table"
        with self.assertRaises(RUNNER.DevelopmentGateError) as raised:
            RUNNER._validate_manifest(manifest)
        self.assertEqual(
            "development_manifest_contains_reference_labels",
            raised.exception.code,
        )

    def test_manifest_selector_cannot_choose_product_route(self) -> None:
        manifest = _manifest_fixture()
        manifest["cases"][0]["selector"]["scope"] = "candidate_crop"
        with self.assertRaises(RUNNER.DevelopmentGateError) as raised:
            RUNNER._validate_manifest(manifest)
        self.assertEqual("development_manifest_case_invalid", raised.exception.code)

    def test_dedicated_skip_terminal_is_the_single_observed_terminal(self) -> None:
        routing = _routing("skip_obvious_non_table", "implausible")
        decisions = _decisions("implausible", "unsupported", "not_selected")
        accounting = _provider_accounting(calls=0, image=False)
        proposal_outcome = _sealed_outcome(
            {
                "status": "not_attempted",
                "proposal_scope": "page_level",
                "proposal_checksum": None,
                "raw_proposal_checksum": None,
                "reason_codes": [],
            }
        )
        binding_outcome = _sealed_outcome(
            {
                "status": "not_applicable",
                "binding_checksum": None,
                "reason_codes": [],
            }
        )
        result = {
            "summary": {
                "target_outcomes": [
                    {
                        "target_id": "target_skip",
                        "terminal_status": "guided_skip_terminal",
                        "reason_code": "objective_table_signal_absent",
                        "count_token_calls": 0,
                        "generate_calls": 0,
                    }
                ]
            },
            "private_diagnostic_refs": [],
            "runtime_result_refs": [],
            "guided_upstream_terminal_refs": [],
            "guided_skip_terminal_refs": ["artifact_skip"],
            "private_target_state_refs": ["artifact_state"],
        }
        artifacts = [
            {
                "payload": {
                    "schema_version": (
                        "broker_reports_pdf_structural_repair_target_state_v1"
                    ),
                    "target_id": "target_skip",
                    "product_routing": routing,
                    "intake_decisions": decisions,
                    "proposal_outcome": proposal_outcome,
                    "binding_outcome": binding_outcome,
                    "provider_accounting": accounting,
                }
            },
            {
                "payload": {
                    "schema_version": (
                        "broker_reports_pdf_vlm_guided_skip_terminal_v1"
                    ),
                    "target_id": "target_skip",
                    "runtime_terminal_status": "skipped_obvious_non_table",
                    "reason_code": "objective_table_signal_absent",
                    "product_routing": routing,
                    "finalized_intake_decisions": decisions,
                    "proposal_outcome": proposal_outcome,
                    "binding_outcome": binding_outcome,
                    "provider_accounting": accounting,
                }
            },
        ]

        terminal = RUNNER._target_terminal(result=result, artifacts=artifacts)

        self.assertTrue(terminal["terminal_cardinality_verified"])
        self.assertEqual(1, terminal["terminal_payloads_total"])
        self.assertEqual("skipped_obvious_non_table", terminal["terminal_status"])
        self.assertEqual("skip_obvious_non_table", terminal["route_selected"])
        self.assertTrue(terminal["routing_evidence_verified"])
        self.assertEqual(0, terminal["count_tokens_calls"])
        self.assertEqual(0, terminal["generate_calls"])
        self.assertEqual(["artifact_skip"], terminal["routing_terminal_refs"])

    def test_runner_rejects_duplicate_target_state_without_selecting_one(self) -> None:
        result, artifacts = _runner_skip_fixture()
        duplicate = json.loads(json.dumps(artifacts[0]))
        duplicate["payload"]["intake_decisions"]["holdout"]["decision"] = "conflicting"
        artifacts.append(duplicate)

        terminal = RUNNER._target_terminal(result=result, artifacts=artifacts)

        self.assertFalse(terminal["terminal_cardinality_verified"])
        self.assertEqual(2, terminal["target_state_payloads_total"])
        self.assertIn(
            "development_target_state_cardinality_invalid",
            terminal["cardinality_failure_codes"],
        )
        self.assertIn(
            "development_proposal_outcome_view_cardinality_invalid",
            terminal["cardinality_failure_codes"],
        )
        self.assertEqual(
            ["terminal"],
            terminal["provider_accounting_verification"]["views_observed"],
        )

    def test_runner_rejects_each_cross_view_intake_decision_conflict(self) -> None:
        conflicting_decisions = {
            "detection": "plausible",
            "processability": "processable",
            "holdout": "selected",
        }
        for name, conflicting in conflicting_decisions.items():
            with self.subTest(decision=name):
                result, artifacts = _runner_skip_fixture()
                artifacts[0]["payload"]["intake_decisions"][name][
                    "decision"
                ] = conflicting

                terminal = RUNNER._target_terminal(
                    result=result,
                    artifacts=artifacts,
                )

                self.assertFalse(terminal["terminal_cardinality_verified"])
                self.assertEqual(2, terminal[f"{name}_decisions_total"])
                self.assertNotIn(name, terminal["intake_decisions"])
                self.assertIn(
                    f"development_{name}_decision_cardinality_invalid",
                    terminal["cardinality_failure_codes"],
                )
                self.assertIn(
                    "development_intake_decision_cross_view_conflict",
                    terminal["cardinality_failure_codes"],
                )

    def test_runner_rejects_conflicting_provider_views_without_first_value_fallback(
        self,
    ) -> None:
        result, artifacts = _runner_skip_fixture()
        state_accounting = artifacts[0]["payload"]["provider_accounting"]
        state_accounting["count_token_calls"] = 1
        state_accounting["journal_count_token_calls"] = 1
        state_accounting.pop("accounting_checksum")
        state_accounting["accounting_checksum"] = hashlib.sha256(
            _json_bytes(state_accounting)
        ).hexdigest()

        terminal = RUNNER._target_terminal(result=result, artifacts=artifacts)

        self.assertIsNone(terminal["count_tokens_calls"])
        self.assertIsNone(terminal["provider_accounting"])
        self.assertFalse(terminal["provider_accounting_verification"]["verified"])
        self.assertIn(
            "development_provider_accounting_view_conflict",
            terminal["provider_accounting_verification"]["failure_codes"],
        )
        self.assertIn(
            "development_provider_accounting_count_token_view_conflict",
            terminal["provider_accounting_verification"]["failure_codes"],
        )

    def test_runner_derives_byte_equal_provider_view_from_transport_journal(
        self,
    ) -> None:
        result, artifacts, provider_contract = _runner_provider_fixture()

        terminal = RUNNER._target_terminal(
            result=result,
            artifacts=artifacts,
            provider_contract=provider_contract,
        )

        self.assertTrue(terminal["terminal_cardinality_verified"])
        self.assertTrue(terminal["provider_accounting_verification"]["verified"])
        self.assertEqual(
            ["journal", "state", "terminal"],
            terminal["provider_accounting_verification"]["views_observed"],
        )
        self.assertEqual(
            ["state", "terminal"],
            terminal["provider_accounting_verification"][
                "journal_views_observed"
            ],
        )
        self.assertEqual(
            1,
            terminal["provider_accounting_verification"][
                "journal_unique_views_total"
            ],
        )
        self.assertEqual(120, terminal["provider_accounting"]["counted_input_tokens"])
        self.assertEqual(120, terminal["provider_accounting"]["actual_input_tokens"])
        self.assertEqual("c" * 64, terminal["provider_accounting"]["request_hash"])

    def test_runner_rejects_conflicting_state_and_terminal_provider_journals(
        self,
    ) -> None:
        result, artifacts, provider_contract = _runner_provider_fixture()
        state_journal = artifacts[0]["payload"]["proposal_result"]["journal"]
        state_journal[0]["provider_attempt"]["usage"]["output_tokens"] = 31

        terminal = RUNNER._target_terminal(
            result=result,
            artifacts=artifacts,
            provider_contract=provider_contract,
        )

        verification = terminal["provider_accounting_verification"]
        self.assertIsNone(terminal["provider_accounting"])
        self.assertFalse(verification["verified"])
        self.assertEqual(["state", "terminal"], verification["journal_views_observed"])
        self.assertEqual(2, verification["journal_unique_views_total"])
        self.assertIn(
            "development_provider_accounting_journal_view_conflict",
            verification["failure_codes"],
        )

    def test_runner_requires_provider_journal_in_state_and_terminal(self) -> None:
        for artifact_index, label in ((0, "state"), (1, "terminal")):
            with self.subTest(missing_view=label):
                result, artifacts, provider_contract = _runner_provider_fixture()
                artifacts[artifact_index]["payload"]["proposal_result"][
                    "journal"
                ] = []

                terminal = RUNNER._target_terminal(
                    result=result,
                    artifacts=artifacts,
                    provider_contract=provider_contract,
                )

                verification = terminal["provider_accounting_verification"]
                self.assertIsNone(terminal["provider_accounting"])
                self.assertFalse(verification["verified"])
                self.assertIn(
                    f"development_provider_accounting_{label}_journal_view_missing",
                    verification["failure_codes"],
                )

    def _write_fixture(self, terminal, reference):
        terminal_path = self.root / "terminal.private.json"
        seal_path = self.root / "terminal.private.sha256.json"
        reference_path = self.root / "reference.private.json"
        output_path = self.root / "score.json"
        terminal_bytes = _json_bytes(terminal)
        terminal_path.write_bytes(terminal_bytes)
        seal_path.write_bytes(
            _json_bytes(
                {
                    "schema_version": (
                        "broker_reports_pdf_vlm_guided_intake_terminal_seal_v1"
                    ),
                    "terminal_sha256": hashlib.sha256(terminal_bytes).hexdigest(),
                    "terminal_size_bytes": len(terminal_bytes),
                }
            )
        )
        reference_path.write_bytes(_json_bytes(reference))
        return terminal_path, seal_path, reference_path, output_path


def _runner_skip_fixture():
    routing = _routing("skip_obvious_non_table", "implausible")
    decisions = _decisions("implausible", "unsupported", "not_selected")
    accounting = _provider_accounting(calls=0, image=False)
    proposal_outcome = _sealed_outcome(
        {
            "status": "not_attempted",
            "proposal_scope": "page_level",
            "proposal_checksum": None,
            "raw_proposal_checksum": None,
            "reason_codes": [],
        }
    )
    binding_outcome = _sealed_outcome(
        {
            "status": "not_applicable",
            "binding_checksum": None,
            "reason_codes": [],
        }
    )
    result = {
        "summary": {
            "target_outcomes": [
                {
                    "target_id": "target_skip",
                    "terminal_status": "guided_skip_terminal",
                    "reason_code": "objective_table_signal_absent",
                    "count_token_calls": 0,
                    "generate_calls": 0,
                }
            ]
        },
        "private_diagnostic_refs": [],
        "runtime_result_refs": [],
        "guided_upstream_terminal_refs": [],
        "guided_skip_terminal_refs": ["artifact_skip"],
        "private_target_state_refs": ["artifact_state"],
    }
    artifacts = [
        {
            "payload": {
                "schema_version": "broker_reports_pdf_structural_repair_target_state_v1",
                "target_id": "target_skip",
                "product_routing": routing,
                "intake_decisions": json.loads(json.dumps(decisions)),
                "proposal_outcome": proposal_outcome,
                "binding_outcome": binding_outcome,
                "provider_accounting": json.loads(json.dumps(accounting)),
            }
        },
        {
            "payload": {
                "schema_version": "broker_reports_pdf_vlm_guided_skip_terminal_v1",
                "target_id": "target_skip",
                "runtime_terminal_status": "skipped_obvious_non_table",
                "reason_code": "objective_table_signal_absent",
                "product_routing": routing,
                "finalized_intake_decisions": json.loads(json.dumps(decisions)),
                "proposal_outcome": proposal_outcome,
                "binding_outcome": binding_outcome,
                "provider_accounting": json.loads(json.dumps(accounting)),
            }
        },
    ]
    return result, artifacts


def _runner_provider_fixture():
    provider_contract = _manifest_fixture()["provider_contract"]
    routing = _routing("candidate_crop", "plausible")
    decisions = _decisions("plausible", "processable", "selected")
    proposal = {
        "schema_version": "broker_reports_pdf_visual_topology_response_v1",
        "contract_revision": "pdf_visual_topology_region_proposal_v1",
        "package_id": "pdfvisualpkg_test",
        "proposal_scope": "candidate_crop",
        "table_presence": "present",
        "regions": [],
        "uncertainty_codes": [],
        "alternatives_complete": True,
    }
    journal = [
        {
            "provider_count_token_call_performed": True,
            "provider_generate_call_performed": True,
            "count_tokens": {
                "total_tokens": 120,
                "request_hash": "c" * 64,
                "model_requested": "models/gemini-3.5-flash",
            },
            "provider_attempt": {
                "attempt_id": "pdfvlmtask_test_a1",
                "task_id": "pdfvlmtask_test",
                "request_hash": "9" * 64,
                "provider_profile": "google_gemini",
                "provider_profile_revision": "d" * 64,
                "model_requested": "models/gemini-3.5-flash",
                "model_resolved": "models/gemini-3.5-flash",
                "crop_sha256": "e" * 64,
                "hidden_retry": False,
                "provider_failover": False,
                "usage": {
                    "input_tokens": 120,
                    "output_tokens": 30,
                },
            },
            "task_id": "pdfvlmtask_test",
            "topology_response": proposal,
        }
    ]
    proposal_result = {
        "package_id": "pdfvisualpkg_test",
        "package_hash": "b" * 64,
        "new_provider_count_token_calls": 1,
        "new_provider_generate_calls": 1,
        "journal": journal,
    }
    visual = {
        "package_id": "pdfvisualpkg_test",
        "package_hash": "b" * 64,
        "proposal_scope": "candidate_crop",
        "crop_identity": {
            "crop_sha256": "e" * 64,
            "png_bytes": 2048,
        },
    }
    accounting = {
        "count_token_calls": 1,
        "generate_calls": 1,
        "journal_count_token_calls": 1,
        "journal_generate_calls": 1,
        "counted_input_tokens": 120,
        "actual_input_tokens": 120,
        "output_tokens": 30,
        "package_id": "pdfvisualpkg_test",
        "package_hash": "b" * 64,
        "request_hash": "c" * 64,
        "task_id": "pdfvlmtask_test",
        "attempt_id": "pdfvlmtask_test_a1",
        "provider_profile": "google_gemini",
        "provider_profile_revision": "d" * 64,
        "model_requested": "models/gemini-3.5-flash",
        "model_resolved": "models/gemini-3.5-flash",
        "image_sha256": "e" * 64,
        "image_bytes": 2048,
        "hidden_retry": False,
        "provider_failover": False,
        "journal_checksum": hashlib.sha256(_json_bytes(journal)).hexdigest(),
    }
    accounting["accounting_checksum"] = hashlib.sha256(
        _json_bytes(accounting)
    ).hexdigest()
    proposal_outcome = _sealed_outcome(
        {
            "status": "persisted",
            "proposal_scope": "candidate_crop",
            "proposal_checksum": hashlib.sha256(_json_bytes(proposal)).hexdigest(),
            "raw_proposal_checksum": hashlib.sha256(_json_bytes(proposal)).hexdigest(),
            "reason_codes": [],
        }
    )
    binding_outcome = _sealed_outcome(
        {
            "status": "completed",
            "binding_checksum": "2" * 64,
            "reason_codes": [],
        }
    )
    result = {
        "summary": {
            "target_outcomes": [
                {
                    "target_id": "target_provider",
                    "terminal_status": "accepted_physical_structure",
                    "count_token_calls": 1,
                    "generate_calls": 1,
                }
            ]
        },
        "private_diagnostic_refs": [],
        "runtime_result_refs": ["artifact_result"],
        "guided_upstream_terminal_refs": [],
        "guided_skip_terminal_refs": [],
        "private_target_state_refs": ["artifact_state"],
    }
    artifacts = [
        {
            "payload": {
                "schema_version": "broker_reports_pdf_structural_repair_target_state_v1",
                "target_id": "target_provider",
                "product_routing": routing,
                "intake_decisions": json.loads(json.dumps(decisions)),
                "visual_package": visual,
                "proposal_result": json.loads(json.dumps(proposal_result)),
                "proposal_outcome": proposal_outcome,
                "binding_outcome": binding_outcome,
                "provider_accounting": accounting,
            }
        },
        {
            "payload": {
                "schema_version": "broker_reports_pdf_vlm_guided_candidate_intake_result_v1",
                "target_id": "target_provider",
                "proposal_scope": "candidate_crop",
                "product_routing": routing,
                "finalized_intake_decisions": json.loads(json.dumps(decisions)),
                "visual_package": visual,
                "proposal_result": proposal_result,
                "proposal": proposal,
                "binding_result": {
                    "result_checksum": "2" * 64,
                    "reason_codes": [],
                },
                "runtime_terminal_status": "accepted_physical_structure",
                "reason_codes": [],
                "new_provider_count_token_calls": 1,
                "new_provider_generate_calls": 1,
                "safe_summary": {
                    "count_token_calls": 1,
                    "generate_calls": 1,
                },
            }
        },
    ]
    return result, artifacts, provider_contract


def _score(terminal: Path, seal: Path, reference: Path, output: Path):
    return subprocess.run(
        [
            sys.executable,
            str(SCORER_PATH),
            "--terminal",
            str(terminal),
            "--seal",
            str(seal),
            "--reference",
            str(reference),
            "--output",
            str(output),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )


def _passing_fixture():
    references = [
        {
            "case_id": "betterment_p4",
            "expected_kind": "table",
            "expected_route": "candidate_crop",
            "expected_regions": 1,
            "broker": "betterment",
            "region_contract": "bounded",
            "regions": [_reference_region("betterment_p4", 1)],
        },
        {
            "case_id": "drivewealth_p7",
            "expected_kind": "table",
            "expected_route": "candidate_crop",
            "expected_regions": 1,
            "broker": "drivewealth",
            "region_contract": "bounded",
            "regions": [_reference_region("drivewealth_p7", 1)],
        },
        {
            "case_id": "moomoo_compound",
            "expected_kind": "table",
            "expected_route": "page_level",
            "expected_regions": 2,
            "broker": "moomoo",
            "region_contract": "compound",
            "regions": [
                _reference_region("moomoo_compound", 1),
                _reference_region("moomoo_compound", 2),
            ],
        },
        {
            "case_id": "ibkr_prefix",
            "expected_kind": "table",
            "expected_route": "page_level",
            "expected_regions": 1,
            "broker": "ibkr",
            "region_contract": "outside_bbox",
            "regions": [_reference_region("ibkr_prefix", 1)],
            "technical_assertions": ["retained_prefix_accounted"],
        },
        {
            "case_id": "negative_toc",
            "expected_kind": "negative",
            "expected_route": "skip_obvious_non_table",
            "expected_regions": 0,
            "broker": "drivewealth",
            "region_contract": "obvious_non_table",
            "regions": [],
        },
    ]
    cases = []
    for item in references:
        if item["expected_kind"] == "negative":
            target = _negative_target(item["case_id"])
        else:
            target = _accepted_target(
                item["case_id"],
                route=item["expected_route"],
                regions=item["expected_regions"],
            )
        case = {"case_id": item["case_id"], "target_terminal": target}
        if item["case_id"] == "ibkr_prefix":
            case["source"] = {"retained_prefix_evidence": _retained_prefix_evidence()}
        cases.append(case)
    terminal = {
        "schema_version": (
            "broker_reports_pdf_vlm_guided_intake_development_terminal_v1"
        ),
        "runner": {
            "pid": os.getpid() + 10_000,
            "reference_argument_supported": False,
        },
        "reference_accessed": False,
        "manifest_sha256": MANIFEST_SHA,
        "target_manifest": {
            "provider_contract": _manifest_fixture()["provider_contract"],
        },
        "manifest_case_ids": [item["case_id"] for item in references],
        "cases": cases,
        "failures": [],
    }
    reference = {
        "schema_version": (
            "broker_reports_pdf_vlm_guided_intake_development_reference_v1"
        ),
        "manifest_sha256": MANIFEST_SHA,
        "cases": references,
        "minimum_correct_acceptances": 4,
        "required_brokers": ["betterment", "drivewealth", "moomoo"],
    }
    reference["reference_checksum"] = hashlib.sha256(_json_bytes(reference)).hexdigest()
    return terminal, reference


def _accepted_target(case_id: str, *, route: str, regions: int):
    parent_bbox = [0.0, 0.0, 100.0, 100.0]
    region_values = []
    parent_words = [f"{case_id}_w{number}" for number in range(1, regions + 2)]
    for index in range(regions):
        included = [parent_words[index]]
        excluded = [item for item in parent_words if item not in included]
        candidate_id = f"{case_id}_c{index + 1}"
        materialization = {
            "model_invented_values_total": 0,
            "omitted_candidate_ids": [],
            "extra_candidate_ids": [],
            "duplicate_candidate_ids": [],
            "structural_provenance_conflicts": [],
            "selected_candidate_ids": [candidate_id],
            "word_refs": included,
            "row_count": 1,
            "column_count": 1,
            "header_rows": [],
            "spans": [],
            "header_hierarchy": [],
            "cells": [
                {
                    "row_ordinal": 1,
                    "column_ordinal": 1,
                    "resolved_source_values": [f"{case_id} value {index + 1}"],
                }
            ],
        }
        region_values.append(
            {
                "region_key": f"region_{index + 1}",
                "source_bbox": [
                    float(index * 10),
                    0.0,
                    float(50 + index * 10),
                    100.0,
                ],
                "included_word_refs": included,
                "excluded_word_refs": excluded,
                "crossing_word_refs": [],
                "candidate_accounting": {
                    "scope_candidates_total": 1,
                    "included_candidate_ids": [candidate_id],
                    "excluded_candidate_ids": [],
                    "crossing_candidate_ids": [],
                    "every_scope_candidate_accounted": True,
                },
                "assembly": {
                    "source_accounting": {
                        "all_bound_alternatives_exactly_once": True,
                    },
                    "value_mutation_performed": False,
                    "nearest_cell_fallback_used": False,
                    "legacy_grid_consumed": False,
                },
                "materialization": materialization,
                "runtime_terminal_status": "accepted_physical_structure",
            }
        )
    routing = _routing(route, "plausible")
    provider_accounting = _provider_accounting(calls=1, image=True)
    proposal_outcome = _sealed_outcome(
        {
            "status": "persisted",
            "proposal_scope": route,
            "proposal_checksum": "1" * 64,
            "raw_proposal_checksum": "1" * 64,
            "reason_codes": [],
        }
    )
    binding_outcome = _sealed_outcome(
        {
            "status": "completed",
            "binding_checksum": "2" * 64,
            "reason_codes": [],
        }
    )
    return {
        "target_id": f"target_{case_id}",
        "target_outcomes_total": 1,
        "result_payloads_total": 1,
        "routing_terminal_payloads_total": 0,
        "terminal_payloads_total": 1,
        "target_state_payloads_total": 1,
        "proposal_outcomes_total": 1,
        "proposal_outcome_views_total": 2,
        "proposal_outcome": proposal_outcome,
        "binding_outcomes_total": 1,
        "binding_outcome_views_total": 2,
        "binding_outcome": binding_outcome,
        "detection_decisions_total": 1,
        "processability_decisions_total": 1,
        "holdout_decisions_total": 1,
        "cardinality_failure_codes": [],
        "terminal_cardinality_verified": True,
        "terminal_status": "accepted_physical_structure",
        "reason_codes": [],
        "route_selected": route,
        "routing_evidence": routing,
        "routing_evidence_verified": True,
        "count_tokens_calls": 1,
        "generate_calls": 1,
        "hidden_retry": False,
        "provider_failover": False,
        "provider_accounting": provider_accounting,
        "provider_accounting_verification": _provider_verification(
            provider_accounting, journal=True
        ),
        "proposal": {"table_presence": "present"},
        "binding_result": {
            "parent_source_bbox": parent_bbox,
            "region_results": region_values,
            "source_accounting": {
                "parent_word_refs_total": len(parent_words),
                "regions_proposed": regions,
                "regions_accepted": regions,
            },
            "value_mutation_performed": False,
            "model_invented_values_total": 0,
        },
        "intake_decisions": _decisions("plausible", "processable", "selected"),
    }


def _negative_target(case_id: str):
    routing = _routing("skip_obvious_non_table", "implausible")
    provider_accounting = _provider_accounting(calls=0, image=False)
    proposal_outcome = _sealed_outcome(
        {
            "status": "not_attempted",
            "proposal_scope": "page_level",
            "proposal_checksum": None,
            "raw_proposal_checksum": None,
            "reason_codes": [],
        }
    )
    binding_outcome = _sealed_outcome(
        {
            "status": "not_applicable",
            "binding_checksum": None,
            "reason_codes": [],
        }
    )
    return {
        "target_id": f"target_{case_id}",
        "target_outcomes_total": 1,
        "result_payloads_total": 1,
        "routing_terminal_payloads_total": 0,
        "terminal_payloads_total": 1,
        "target_state_payloads_total": 1,
        "proposal_outcomes_total": 1,
        "proposal_outcome_views_total": 2,
        "proposal_outcome": proposal_outcome,
        "binding_outcomes_total": 1,
        "binding_outcome_views_total": 2,
        "binding_outcome": binding_outcome,
        "detection_decisions_total": 1,
        "processability_decisions_total": 1,
        "holdout_decisions_total": 1,
        "cardinality_failure_codes": [],
        "terminal_cardinality_verified": True,
        "terminal_status": "skipped_obvious_non_table",
        "reason_codes": ["pdf_guided_intake_obvious_non_table"],
        "route_selected": "skip_obvious_non_table",
        "routing_evidence": routing,
        "routing_evidence_verified": True,
        "count_tokens_calls": 0,
        "generate_calls": 0,
        "hidden_retry": False,
        "provider_failover": False,
        "provider_accounting": provider_accounting,
        "provider_accounting_verification": _provider_verification(
            provider_accounting, journal=False
        ),
        "binding_result": {
            "parent_source_bbox": [0.0, 0.0, 100.0, 100.0],
            "region_results": [],
            "source_accounting": {
                "parent_word_refs_total": 0,
                "regions_proposed": 0,
                "regions_accepted": 0,
            },
            "value_mutation_performed": False,
            "model_invented_values_total": 0,
        },
        "intake_decisions": _decisions("implausible", "processable", "not_selected"),
    }


def _routing(route: str, detection: str):
    value = {
        "schema_version": "broker_reports_pdf_guided_product_routing_v1",
        "route": route,
        "detection_decision": detection,
        "reason_codes": [],
        "observations": {"bounded_scope": True},
    }
    value["routing_checksum"] = hashlib.sha256(_json_bytes(value)).hexdigest()
    return value


def _reference_region(case_id: str, ordinal: int):
    return {
        "rows": 1,
        "columns": 1,
        "header_rows": [],
        "spans": [],
        "header_hierarchy": [],
        "cells": [[f"{case_id} value {ordinal}"]],
    }


def _retained_prefix_evidence():
    value = {
        "document_projection_status": "partial",
        "document_reason_codes": ["pdf_layout_document_inventory_budget_exceeded"],
        "source_pages_total": 20,
        "completed_pages_total": 12,
        "missing_tail_pages_total": 8,
        "first_missing_page_number": 13,
        "inventory_objects_limit": 25_000,
        "inventory_objects_retained_total": 24_500,
        "inventory_objects_would_be_total": 25_400,
        "selected_page_number": 11,
        "selected_page_projection_status": "complete",
        "selected_page_reason_codes": [],
        "retained_prefix_accounted": True,
    }
    value["evidence_checksum"] = hashlib.sha256(_json_bytes(value)).hexdigest()
    return value


def _decisions(detection: str, processability: str, holdout: str):
    return {
        "detection": {"decision": detection},
        "processability": {"decision": processability},
        "holdout": {"decision": holdout},
    }


def _provider_accounting(*, calls: int, image: bool):
    value = {
        "count_token_calls": calls,
        "generate_calls": calls,
        "journal_count_token_calls": calls,
        "journal_generate_calls": calls,
        "counted_input_tokens": 120 if calls else None,
        "actual_input_tokens": 120 if calls else None,
        "output_tokens": 30 if calls else None,
        "package_id": "pdfvisualpkg_test" if calls else None,
        "package_hash": "b" * 64 if calls else None,
        "request_hash": "c" * 64 if calls else None,
        "task_id": "pdfvlmtask_test" if calls else None,
        "attempt_id": "pdfvlmtask_test_a1" if calls else None,
        "provider_profile": "google_gemini" if calls else None,
        "provider_profile_revision": "d" * 64 if calls else None,
        "model_requested": "models/gemini-3.5-flash" if calls else None,
        "model_resolved": "models/gemini-3.5-flash" if calls else None,
        "image_sha256": "e" * 64 if image else None,
        "image_bytes": 2048 if image else None,
        "hidden_retry": False,
        "provider_failover": False,
        "journal_checksum": "f" * 64,
    }
    value["accounting_checksum"] = hashlib.sha256(_json_bytes(value)).hexdigest()
    return value


def _provider_verification(
    accounting: dict,
    *,
    journal: bool,
    pre_provider_zero_call_allowed: bool = False,
):
    checksum = accounting["accounting_checksum"]
    views = ["state", "terminal"]
    if journal:
        views.insert(0, "journal")
    value = {
        "schema_version": (
            "broker_reports_pdf_vlm_guided_provider_accounting_verification_v1"
        ),
        "views_observed": views,
        "view_checksums": {name: checksum for name in views},
        "unique_views_total": 1,
        "pre_provider_zero_call_allowed": pre_provider_zero_call_allowed,
        "failure_codes": [],
        "verified": True,
    }
    value["verification_checksum"] = hashlib.sha256(_json_bytes(value)).hexdigest()
    return value


def _reseal_provider_projection(target: dict):
    accounting = target["provider_accounting"]
    accounting.pop("accounting_checksum", None)
    accounting["accounting_checksum"] = hashlib.sha256(
        _json_bytes(accounting)
    ).hexdigest()
    verification = target["provider_accounting_verification"]
    checksum = accounting["accounting_checksum"]
    verification["view_checksums"] = {
        name: checksum for name in verification["views_observed"]
    }
    verification["unique_views_total"] = 1
    verification["failure_codes"] = []
    verification["verified"] = True
    verification.pop("verification_checksum", None)
    verification["verification_checksum"] = hashlib.sha256(
        _json_bytes(verification)
    ).hexdigest()


def _sealed_outcome(value: dict):
    value = dict(value)
    value["outcome_checksum"] = hashlib.sha256(_json_bytes(value)).hexdigest()
    return value


def _manifest_fixture():
    return {
        "schema_version": (
            "broker_reports_pdf_vlm_guided_intake_development_manifest_v1"
        ),
        "source_revision": {
            "repository_commit_sha": "b" * 40,
            "gate1_bundle_sha256": "c" * 64,
            "require_clean_worktree": True,
        },
        "provider_contract": {
            "provider_profile": "google_gemini",
            "model_id": "models/gemini-3.5-flash",
            "maximum_counted_input_tokens": 20_000,
            "maximum_output_tokens": 8_192,
            "hidden_retry": False,
            "provider_failover": False,
        },
        "cases": [
            {
                "case_id": "betterment_p4",
                "relative_pdf": "betterment.pdf",
                "pdf_sha256": "d" * 64,
                "selector": {
                    "page_number": 4,
                    "parser_ordinal": 2,
                },
            }
        ],
    }


def _fake_runner_source():
    return textwrap.dedent(
        """
        import argparse
        import hashlib
        import json
        import os
        from pathlib import Path

        parser = argparse.ArgumentParser()
        parser.add_argument("command")
        parser.add_argument("--manifest")
        parser.add_argument("--corpus-root")
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--env-file")
        parser.add_argument("--repo-root")
        parser.add_argument("--bundle")
        args = parser.parse_args()
        output = Path(args.output_dir)
        output.mkdir(parents=True)
        terminal = {
            "schema_version": "broker_reports_pdf_vlm_guided_intake_development_terminal_v1",
            "runner": {"pid": os.getpid(), "reference_argument_supported": False},
            "reference_accessed": False,
            "manifest_sha256": "a" * 64,
            "manifest_case_ids": [],
            "cases": [],
            "failures": [],
        }
        terminal_bytes = json.dumps(terminal, sort_keys=True, separators=(",", ":")).encode()
        (output / "terminal.private.json").write_bytes(terminal_bytes)
        seal = {
            "schema_version": "broker_reports_pdf_vlm_guided_intake_terminal_seal_v1",
            "terminal_sha256": hashlib.sha256(terminal_bytes).hexdigest(),
            "terminal_size_bytes": len(terminal_bytes),
        }
        (output / "terminal.private.sha256.json").write_text(json.dumps(seal), encoding="utf-8")
        print("sealed: Проекты")
        """
    )


def _fake_scorer_source():
    return textwrap.dedent(
        """
        import argparse
        import hashlib
        import json
        import os
        from pathlib import Path

        parser = argparse.ArgumentParser()
        parser.add_argument("--terminal", required=True)
        parser.add_argument("--seal", required=True)
        parser.add_argument("--reference", required=True)
        parser.add_argument("--output", required=True)
        args = parser.parse_args()
        terminal_bytes = Path(args.terminal).read_bytes()
        seal = json.loads(Path(args.seal).read_text(encoding="utf-8"))
        assert seal["terminal_sha256"] == hashlib.sha256(terminal_bytes).hexdigest()
        terminal = json.loads(terminal_bytes)
        assert terminal["runner"]["pid"] != os.getpid()
        Path(args.reference).read_bytes()
        result = {
            "binary_result": "WORKS_ON_DEVELOPMENT_CORPUS",
            "scorer_pid": os.getpid(),
            "terminal_verified_before_reference": True,
        }
        Path(args.output).write_text(json.dumps(result), encoding="utf-8")
        print("WORKS_ON_DEVELOPMENT_CORPUS")
        """
    )


def _fake_incomplete_runner_source(*, exit_code: int, write_terminal: bool = False):
    terminal_write = (
        "(output / 'terminal.private.json').write_text('{}', encoding='utf-8')"
        if write_terminal
        else "pass"
    )
    return textwrap.dedent(
        f"""
        import argparse
        from pathlib import Path

        parser = argparse.ArgumentParser()
        parser.add_argument("command")
        parser.add_argument("--manifest")
        parser.add_argument("--corpus-root")
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--env-file")
        parser.add_argument("--repo-root")
        parser.add_argument("--bundle")
        args = parser.parse_args()
        output = Path(args.output_dir)
        output.mkdir(parents=True)
        {terminal_write}
        raise SystemExit({exit_code})
        """
    )


def _fake_probe_scorer_source():
    return textwrap.dedent(
        """
        import argparse
        from pathlib import Path

        parser = argparse.ArgumentParser()
        parser.add_argument("--terminal", required=True)
        parser.add_argument("--seal", required=True)
        parser.add_argument("--reference", required=True)
        parser.add_argument("--output", required=True)
        args = parser.parse_args()
        Path(args.reference).read_bytes()
        (Path(args.output).parent / "reference-read.marker").write_text(
            "read",
            encoding="utf-8",
        )
        """
    )


def _json_bytes(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
