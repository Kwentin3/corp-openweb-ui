from __future__ import annotations

import copy
import unittest
from pathlib import Path

from broker_reports_gate1.contracts import stable_digest
from broker_reports_gate1.pdf_dual_oracle_consensus import (
    FACTORY_REQUIRED as CONSENSUS_FACTORY_REQUIRED,
    FORBIDDEN as CONSENSUS_FORBIDDEN,
    PDF_DUAL_ORACLE_CONTINUATION_RESULT_SCHEMA,
    PDF_DUAL_ORACLE_CONTINUATION_RESULT_SCHEMA_V1,
    PdfDualOracleConsensusConfig,
    PdfDualOracleConsensusError,
    PdfDualOracleConsensusFactory,
    PdfDualOracleConsensusRuntime,
)
from broker_reports_gate1.pdf_dual_oracle_contracts import (
    FACTORY_REQUIRED as CONTRACT_FACTORY_REQUIRED,
    FORBIDDEN as CONTRACT_FORBIDDEN,
    PdfDualOracleContractConfig,
    PdfDualOracleContractError,
    PdfDualOracleContractFactory,
    PdfDualOracleContractRuntime,
)
from broker_reports_gate1.pdf_hybrid_contracts import (
    PDF_HYBRID_BINDING_OUTPUT_SCHEMA,
    sha256_json,
)
from broker_reports_gate1.pdf_hybrid_materialization import (
    PDF_CONTINUATION_MATERIALIZATION_SCHEMA,
    PdfHybridMaterializationError,
    PdfHybridMaterializationFactory,
)
from broker_reports_gate1.pdf_hybrid_structure import (
    PDF_HYBRID_CONTINUATION_SCHEMA,
    PdfHybridStructureFactory,
)
from broker_reports_gate1.pdf_table_validation import PdfTableValidationFactory


class PdfDualOracleContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contracts = PdfDualOracleContractFactory().create()

    def test_parser_observation_is_exact_but_contains_no_parser_grid_semantics(self) -> None:
        ledger, projection, _, _ = _fixture()
        observation = self.contracts.build_parser_observation(
            compact_ledger=ledger,
            pdf_text_layer_projection=projection,
        )

        self.assertEqual([], self.contracts.validate_parser_observation(observation))
        self.assertEqual(4, observation["source_accounting"]["candidates"])
        self.assertFalse(observation["source_accounting"]["semantic_grid_claimed"])
        serialized = repr(observation)
        self.assertNotIn("expected_row_ordinal", serialized)
        self.assertNotIn("expected_column_ordinal", serialized)
        self.assertEqual("a", observation["candidates"][0]["exact_visible_value"])
        self.assertTrue(observation["candidates"][0]["source_value_refs"])
        self.assertTrue(observation["candidates"][0]["word_refs"])

    def test_vlm_contract_rejects_free_values_and_incomplete_candidate_ownership(self) -> None:
        ledger, projection, binding, _ = _fixture()
        observation = self.contracts.build_parser_observation(
            compact_ledger=ledger,
            pdf_text_layer_projection=projection,
        )
        invalid = copy.deepcopy(binding)
        invalid["rows"][0]["cells"][0] = []
        invalid["value"] = "invented"

        hypothesis_set = self.contracts.build_vlm_hypothesis_set(
            parser_observation=observation,
            binding_hypotheses=[
                {"hypothesis_id": "bad", "binding_output": invalid}
            ],
        )

        self.assertEqual([], hypothesis_set["hypotheses"])
        self.assertEqual(1, len(hypothesis_set["rejected_evidence"]))
        self.assertIn(
            "hybrid_binding_output_keys_invalid",
            hypothesis_set["rejected_evidence"][0]["reason_codes"],
        )

    def test_parser_derived_candidate_geometry_cannot_be_tampered(self) -> None:
        ledger, projection, _, _ = _fixture()
        observation = self.contracts.build_parser_observation_from_word_atoms(
            document_ref=ledger["document_ref"],
            pdf_sha256=ledger["pdf_sha256"],
            page_ref=ledger["page_ref"],
            page_number=ledger["page_number"],
            table_ref=ledger["table_ref"],
            table_bbox=ledger["table_bbox"],
            pdf_text_layer_projection=projection,
        )
        tampered = copy.deepcopy(observation)
        tampered["candidates"][0]["bbox"][0] += 2.0
        candidate = tampered["candidates"][0]
        candidate_copy = dict(candidate)
        candidate_copy.pop("candidate_observation_checksum")
        candidate["candidate_observation_checksum"] = sha256_json(candidate_copy)
        tampered.pop("observation_checksum")
        tampered["observation_checksum"] = sha256_json(tampered)

        self.assertIn(
            "pdf_parser_observation_candidate_derivation_invalid",
            self.contracts.validate_parser_observation(tampered),
        )

    def test_ambiguous_binding_without_grid_becomes_typed_rejected_evidence(self) -> None:
        ledger, projection, binding, _ = _fixture()
        observation = self.contracts.build_parser_observation_from_word_atoms(
            document_ref=ledger["document_ref"],
            pdf_sha256=ledger["pdf_sha256"],
            page_ref=ledger["page_ref"],
            page_number=ledger["page_number"],
            table_ref=ledger["table_ref"],
            table_bbox=ledger["table_bbox"],
            pdf_text_layer_projection=projection,
        )
        ambiguous = copy.deepcopy(binding)
        ambiguous.update(
            {
                "decision": "ambiguous",
                "row_count": 0,
                "column_count": 0,
                "header_rows": [],
                "header_hierarchy": [],
                "rows": [],
                "spans": [],
            }
        )
        hypothesis_set = self.contracts.build_vlm_hypothesis_set(
            parser_observation=observation,
            binding_hypotheses=[
                {"hypothesis_id": "ambiguous-no-grid", "binding_output": ambiguous}
            ],
            model_context=_model_context(independent=True),
        )

        self.assertEqual([], hypothesis_set["hypotheses"])
        self.assertIn(
            "pdf_vlm_hypothesis_rectangular_grid_incomplete",
            hypothesis_set["rejected_evidence"][0]["reason_codes"],
        )

    def test_runtime_constructors_require_factories(self) -> None:
        with self.assertRaisesRegex(
            PdfDualOracleContractError,
            "pdf_dual_oracle_contract_factory_required",
        ):
            PdfDualOracleContractRuntime(PdfDualOracleContractConfig())
        with self.assertRaisesRegex(
            PdfDualOracleConsensusError,
            "pdf_dual_oracle_consensus_factory_required",
        ):
            PdfDualOracleConsensusRuntime(PdfDualOracleConsensusConfig())
        self.assertIn("PdfDualOracleContractFactory.create", CONTRACT_FACTORY_REQUIRED)
        self.assertIn("must not contain values", CONTRACT_FORBIDDEN)
        self.assertIn("PdfDualOracleConsensusFactory.create", CONSENSUS_FACTORY_REQUIRED)
        self.assertIn("must not score", CONSENSUS_FORBIDDEN)

    def test_continuation_contract_factory_requires_exact_ordered_pair(self) -> None:
        fragments = [
            {
                "fragment_order": 1,
                "page_number": 4,
                "table_ref": "table-4",
                "repeated_header_policy": "source_header",
            },
            {
                "fragment_order": 2,
                "page_number": 5,
                "table_ref": "table-5",
                "repeated_header_policy": "no_repeated_header",
            },
        ]

        contract = self.contracts.build_continuation_contract(
            continuation_group_id="group-4-5",
            fragments=fragments,
            shared_column_count=12,
        )

        self.assertEqual([1, 2], [item["fragment_order"] for item in contract["fragments"]])
        self.assertEqual(12, contract["shared_column_count"])
        with self.assertRaisesRegex(
            PdfDualOracleContractError,
            "pdf_dual_oracle_continuation_contract_invalid",
        ):
            self.contracts.build_continuation_contract(
                continuation_group_id="group-too-wide",
                fragments=[*fragments, copy.deepcopy(fragments[1])],
                shared_column_count=12,
            )
        reversed_pair = copy.deepcopy(fragments)
        reversed_pair.reverse()
        with self.assertRaisesRegex(
            PdfDualOracleContractError,
            "pdf_dual_oracle_continuation_fragment_order_invalid",
        ):
            self.contracts.build_continuation_contract(
                continuation_group_id="group-reversed",
                fragments=reversed_pair,
                shared_column_count=12,
            )

    def test_runtime_modules_are_routed_but_replay_stays_out_of_production_bundle(self) -> None:
        service_root = Path(__file__).resolve().parents[1]
        bundle_builder = (
            service_root / "scripts" / "build_openwebui_pipe_bundle.py"
        ).read_text(encoding="utf-8")

        self.assertIn("pdf_dual_oracle_contracts", bundle_builder)
        self.assertIn("pdf_dual_oracle_consensus", bundle_builder)
        self.assertNotIn("pdf_dual_oracle_replay", bundle_builder)


class PdfDualOracleConsensusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contracts = PdfDualOracleContractFactory().create()
        self.solver = PdfDualOracleConsensusFactory().create()

    def test_unique_consensus_is_deterministic_and_passes_existing_downstream_contracts(self) -> None:
        ledger, projection, binding, evidence = _fixture()
        observation, hypothesis_set = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[binding, copy.deepcopy(binding)],
            independent=True,
        )
        repeatability = _sealed_repeatability(
            self.solver, observation, hypothesis_set
        )

        first = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability=repeatability,
        )
        second = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability=repeatability,
        )

        self.assertEqual("accepted_supplied_consensus", first["terminal_status"])
        self.assertTrue(first["supplied_hypotheses_exhausted"])
        self.assertFalse(first["structural_domain_complete"])
        self.assertFalse(first["uniqueness_proven"])
        self.assertFalse(first["ambiguity_proven"])
        self.assertTrue(first["domain_incomplete"])
        self.assertFalse(first["search_not_certifiable"])
        self.assertEqual(
            "supplied_vlm_hypotheses_only", first["search_scope"]
        )
        self.assertIn(
            "structural domain was not enumerated", first["safe_explanation"]
        )
        self.assertEqual(1, first["valid_distinct_grid_count"])
        self.assertEqual(first["result_checksum"], second["result_checksum"])
        self.assertEqual(
            first["canonical_grid_checksum"], second["canonical_grid_checksum"]
        )
        self.assertFalse(first["numeric_score_used"])
        self.assertFalse(first["oracle_preference_used"])
        self.assertTrue(
            all(
                item["row_compatibility_passed"]
                and item["column_compatibility_passed"]
                for item in first["alternatives_considered"][0][
                    "candidate_explanations"
                ]
            )
        )

        consensus_binding = self.solver.binding_from_accepted_consensus(
            parser_observation=observation,
            consensus_result=first,
            vlm_hypothesis_set=hypothesis_set,
            evidence_package=evidence,
        )
        materialization = PdfHybridMaterializationFactory().create().materialize(
            evidence_package=evidence,
            binding_output=consensus_binding,
        )
        structure = PdfHybridStructureFactory().create().validate_placement(
            compact_ledger=ledger,
            materialization=materialization,
        )
        validation = PdfTableValidationFactory().create().validate(
            evidence_package=evidence,
            binding_output=consensus_binding,
            materialization=materialization,
            classification={"measured_signals": {}},
            independent_structural_validation=structure,
        )
        self.assertTrue(structure["passed"])
        self.assertEqual("accepted_shadow", validation["aggregate_result"])
        self.assertTrue(validation["source_authenticity_validated"])
        self.assertTrue(validation["structural_placement_validated"])

    def test_seeded_parser_shape_forces_human_review_even_when_grid_is_unique(self) -> None:
        ledger, projection, binding, _ = _fixture()
        observation, hypothesis_set = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[binding],
            independent=False,
        )

        result = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability=_passed_repeatability(),
        )

        self.assertEqual("incomplete_evidence", result["terminal_status"])
        self.assertIn(
            "pdf_dual_oracle_vlm_shape_independence_not_proven",
            result["reason_codes"],
        )
        with self.assertRaises(PdfDualOracleConsensusError):
            self.solver.binding_from_accepted_consensus(
                parser_observation=observation,
                consensus_result=result,
                vlm_hypothesis_set=hypothesis_set,
                evidence_package={},
            )

    def test_repeatability_record_is_bound_and_repeat_is_solver_derived(self) -> None:
        ledger, projection, binding, _ = _fixture()
        observation, hypothesis_set = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[binding, copy.deepcopy(binding)],
            independent=True,
        )
        unsealed = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability=_passed_repeatability(),
        )
        self.assertEqual("incomplete_evidence", unsealed["terminal_status"])
        self.assertIn(
            "pdf_dual_oracle_repeatability_incomplete", unsealed["review_codes"]
        )

        sealed_record = _sealed_repeatability(
            self.solver, observation, hypothesis_set
        )
        accepted = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability=sealed_record,
        )
        self.assertEqual("accepted_supplied_consensus", accepted["terminal_status"])

        wrong_identity = copy.deepcopy(sealed_record)
        wrong_identity["model"] = "foreign-model"
        wrong_identity_copy = dict(wrong_identity)
        wrong_identity_copy.pop("record_checksum")
        wrong_identity["record_checksum"] = sha256_json(wrong_identity_copy)
        blocked = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability=wrong_identity,
        )
        self.assertEqual("incomplete_evidence", blocked["terminal_status"])
        self.assertIn(
            "pdf_dual_oracle_repeatability_incomplete", blocked["review_codes"]
        )

        single_observation, single_set = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[binding],
            independent=True,
        )
        single = self.solver.solve(
            parser_observation=single_observation,
            vlm_hypothesis_set=single_set,
            historical_repeatability=_sealed_repeatability(
                self.solver, single_observation, single_set
            ),
        )
        self.assertEqual("incomplete_evidence", single["terminal_status"])
        self.assertIn(
            "pdf_dual_oracle_repeatability_incomplete", single["review_codes"]
        )

        legacy_prior_conflict = _passed_repeatability()
        legacy_prior_conflict["ever_conflicted"] = True
        conservatively_blocked = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability=legacy_prior_conflict,
        )
        self.assertEqual(
            "incomplete_evidence", conservatively_blocked["terminal_status"]
        )
        self.assertTrue(
            conservatively_blocked["historical_conflict_preserved"]
        )
        self.assertTrue(
            conservatively_blocked["historical_repeatability"][
                "external_prior_conflict_claimed"
            ]
        )

    def test_windowed_repeatability_uses_two_composite_observations_not_raw_calls(
        self,
    ) -> None:
        ledger, projection, binding, _ = _fixture()
        observation, _ = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[binding],
            independent=True,
        )
        context = _model_context(independent=True)
        context.update(
            {
                "provider_calls_replayed": 0,
                "new_provider_calls": 4,
                "execution_mode": "vertical_atom_windows",
                "window_count": 2,
                "raw_provider_calls": 4,
                "stitched_oracle_observations": 2,
                "window_lineage_checksum": "window-lineage-sha",
            }
        )
        hypothesis_set = self.contracts.build_vlm_hypothesis_set(
            parser_observation=observation,
            binding_hypotheses=[
                {
                    "hypothesis_id": f"composite-attempt-{attempt}",
                    "binding_output": copy.deepcopy(binding),
                    "proposed_geometry": _uniform_geometry(binding),
                    "evidence": _binding_evidence(binding, attempt),
                }
                for attempt in (1, 2)
            ],
            model_context=context,
        )
        repeatability = _sealed_repeatability(
            self.solver, observation, hypothesis_set
        )
        result = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability=repeatability,
        )

        self.assertEqual(4, hypothesis_set["model_context"]["raw_provider_calls"])
        self.assertEqual(
            2,
            hypothesis_set["model_context"]["stitched_oracle_observations"],
        )
        self.assertEqual(2, len(repeatability["attempt_history"]))
        self.assertTrue(repeatability["supplied_history_structurally_complete"])
        self.assertTrue(repeatability["passed"])
        self.assertEqual("accepted_supplied_consensus", result["terminal_status"])

    def test_alternatives_from_one_provider_attempt_do_not_prove_repeatability(
        self,
    ) -> None:
        ledger, projection, binding, _ = _fixture()
        observation, _ = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[binding],
            independent=True,
        )
        hypothesis_set = self.contracts.build_vlm_hypothesis_set(
            parser_observation=observation,
            binding_hypotheses=[
                {
                    "hypothesis_id": "attempt-1-alternative-1",
                    "binding_output": copy.deepcopy(binding),
                    "proposed_geometry": _uniform_geometry(binding),
                    "evidence": _binding_evidence(binding, 1),
                },
                {
                    "hypothesis_id": "attempt-1-alternative-2",
                    "binding_output": copy.deepcopy(binding),
                    "proposed_geometry": _uniform_geometry(binding),
                    "evidence": _binding_evidence(binding, 1),
                },
            ],
            model_context=_model_context(independent=True),
        )

        record = _sealed_repeatability(self.solver, observation, hypothesis_set)
        result = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability=record,
        )
        self.assertEqual(1, len(record["attempt_history"]))
        self.assertEqual(2, record["attempt_history"][0]["alternative_count"])
        self.assertFalse(
            record["attempt_history"][0]["alternative_identities_unique"]
        )
        self.assertFalse(record["supplied_history_structurally_complete"])
        self.assertFalse(record["passed"])
        self.assertEqual("incomplete_evidence", result["terminal_status"])
        self.assertIn(
            "pdf_dual_oracle_repeatability_incomplete", result["review_codes"]
        )

    def test_distinct_alternatives_from_one_attempt_are_not_historical_conflict(
        self,
    ) -> None:
        ledger, projection, binding, _ = _fixture()
        observation, _ = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[binding],
            independent=True,
        )
        bad_geometry = _uniform_geometry(binding)
        bad_geometry["columns"]["boundaries"] = [0.0, 0.9, 1.0]
        hypothesis_set = self.contracts.build_vlm_hypothesis_set(
            parser_observation=observation,
            binding_hypotheses=[
                {
                    "hypothesis_id": "attempt-1-valid",
                    "binding_output": copy.deepcopy(binding),
                    "proposed_geometry": _uniform_geometry(binding),
                    "evidence": _binding_evidence(binding, 1),
                },
                {
                    "hypothesis_id": "attempt-1-invalid",
                    "binding_output": copy.deepcopy(binding),
                    "proposed_geometry": bad_geometry,
                    "evidence": _binding_evidence(binding, 1),
                },
            ],
            model_context=_model_context(independent=True),
        )

        record = _sealed_repeatability(self.solver, observation, hypothesis_set)
        result = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability=record,
        )

        self.assertEqual(1, len(record["attempt_history"]))
        self.assertTrue(
            record["attempt_history"][0]["alternative_identities_unique"]
        )
        self.assertFalse(record["ever_conflicted"])
        self.assertFalse(record["passed"])
        self.assertEqual("incomplete_evidence", result["terminal_status"])
        self.assertNotIn(
            "pdf_dual_oracle_historical_same_evidence_conflict",
            result["review_codes"],
        )
        self.assertIn(
            "pdf_dual_oracle_repeatability_incomplete", result["review_codes"]
        )

    def test_later_agreement_does_not_erase_prior_attempt_conflict(self) -> None:
        ledger, projection, binding, _ = _fixture()
        observation, _ = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[binding],
            independent=True,
        )
        changed_geometry = _uniform_geometry(binding)
        changed_geometry["columns"]["boundaries"] = [0.0, 0.55, 1.0]
        context = _model_context(independent=True)
        context["provider_calls_replayed"] = 3
        hypothesis_set = self.contracts.build_vlm_hypothesis_set(
            parser_observation=observation,
            binding_hypotheses=[
                {
                    "hypothesis_id": "attempt-1-original",
                    "binding_output": copy.deepcopy(binding),
                    "proposed_geometry": _uniform_geometry(binding),
                    "evidence": _binding_evidence(binding, 1),
                },
                {
                    "hypothesis_id": "attempt-2-changed",
                    "binding_output": copy.deepcopy(binding),
                    "proposed_geometry": copy.deepcopy(changed_geometry),
                    "evidence": _binding_evidence(binding, 2),
                },
                {
                    "hypothesis_id": "attempt-3-changed",
                    "binding_output": copy.deepcopy(binding),
                    "proposed_geometry": copy.deepcopy(changed_geometry),
                    "evidence": _binding_evidence(binding, 3),
                },
            ],
            model_context=context,
        )

        record = _sealed_repeatability(self.solver, observation, hypothesis_set)
        result = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability=record,
        )
        caller_omitted_record = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability={},
        )
        repeat_history = self.solver.sync_repeat_history(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
        )
        replayed_history = self.solver.sync_repeat_history(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
            history=repeat_history,
        )

        self.assertEqual(3, len(record["attempt_history"]))
        self.assertTrue(record["supplied_history_structurally_complete"])
        self.assertTrue(record["ever_conflicted"])
        self.assertFalse(record["passed"])
        self.assertEqual(3, len(repeat_history["events"]))
        self.assertTrue(repeat_history["ever_conflicted"])
        self.assertEqual(
            repeat_history["history_checksum"],
            replayed_history["history_checksum"],
        )
        self.assertEqual(repeat_history["events"], replayed_history["events"])
        self.assertEqual("incomplete_evidence", result["terminal_status"])
        self.assertIn(
            "pdf_dual_oracle_historical_same_evidence_conflict",
            result["review_codes"],
        )
        self.assertTrue(caller_omitted_record["historical_conflict_preserved"])
        self.assertIn(
            "pdf_dual_oracle_historical_same_evidence_conflict",
            caller_omitted_record["review_codes"],
        )

    def test_wrong_column_is_parser_vlm_conflict_with_candidate_explanation(self) -> None:
        ledger, projection, binding, _ = _fixture()
        wrong = copy.deepcopy(binding)
        wrong["rows"][0]["cells"][0], wrong["rows"][0]["cells"][1] = (
            wrong["rows"][0]["cells"][1],
            wrong["rows"][0]["cells"][0],
        )
        observation, hypothesis_set = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[wrong],
            independent=True,
        )

        result = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability=_passed_repeatability(),
        )

        self.assertEqual("parser_vlm_conflict", result["terminal_status"])
        self.assertIn(
            "pdf_dual_oracle_candidate_column_incompatible", result["reason_codes"]
        )
        explanations = result["alternatives_considered"][0]["candidate_explanations"]
        self.assertTrue(any(not item["column_compatibility_passed"] for item in explanations))

    def test_two_physically_valid_distinct_grids_are_ambiguous(self) -> None:
        ledger, projection, binding, _ = _fixture(rows=1, columns=2, values=("same", "same"))
        for candidate in ledger["private_candidate_dictionary"].values():
            candidate["source_bbox"] = [99.5, 10.0, 100.5, 40.0]
            candidate["source_cell_bbox"] = [0.0, 0.0, 200.0, 100.0]
        for word in projection["word_inventory"]:
            projection["bbox_inventory"][int(word["parser_ordinal"])]["bbox"] = [
                99.5,
                10.0,
                100.5,
                40.0,
            ]
        first = copy.deepcopy(binding)
        second = copy.deepcopy(binding)
        second["rows"][0]["cells"].reverse()
        observation, hypothesis_set = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[first, second],
            independent=True,
        )

        result = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
        )

        self.assertEqual("ambiguous_multiple_consensus", result["terminal_status"])
        self.assertEqual(2, result["valid_distinct_grid_count"])
        self.assertTrue(result["supplied_hypotheses_exhausted"])
        self.assertFalse(result["uniqueness_proven"])
        self.assertTrue(result["ambiguity_proven"])
        self.assertFalse(result["structural_domain_complete"])
        self.assertTrue(result["domain_incomplete"])
        self.assertFalse(result["search_not_certifiable"])
        self.assertIn("ambiguity is proven", result["safe_explanation"])

    def test_indistinguishable_duplicate_value_identity_requires_review(self) -> None:
        ledger, projection, binding, _ = _fixture(rows=1, columns=2, values=("same", "same"))
        for candidate in ledger["private_candidate_dictionary"].values():
            candidate["source_bbox"] = [99.5, 10.0, 100.5, 40.0]
            candidate["source_cell_bbox"] = [0.0, 0.0, 200.0, 100.0]
        for word in projection["word_inventory"]:
            projection["bbox_inventory"][int(word["parser_ordinal"])]["bbox"] = [
                99.5,
                10.0,
                100.5,
                40.0,
            ]
        observation, hypothesis_set = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[binding],
            independent=True,
        )

        result = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
        )

        self.assertEqual("incomplete_evidence", result["terminal_status"])
        self.assertIn(
            "pdf_dual_oracle_duplicate_identity_not_physically_distinguishable",
            result["review_codes"],
        )

    def test_missing_merged_header_relation_is_conflict(self) -> None:
        ledger, projection, binding, _ = _fixture()
        candidate = ledger["private_candidate_dictionary"][
            ledger["candidate_order"][0]
        ]
        candidate["source_bbox"] = [10.0, 10.0, 190.0, 40.0]
        projection["bbox_inventory"][1]["bbox"] = [10.0, 10.0, 190.0, 40.0]
        observation, hypothesis_set = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[binding],
            independent=True,
        )

        result = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
        )

        self.assertEqual("parser_vlm_conflict", result["terminal_status"])
        self.assertIn(
            "pdf_dual_oracle_merged_header_relation_missing", result["reason_codes"]
        )

    def test_merged_span_covered_empty_is_explicit_and_invents_no_value(self) -> None:
        ledger, projection, binding, _ = _fixture()
        first, second = ledger["candidate_order"][:2]
        binding["rows"][0]["cells"] = [[first, second], []]
        binding["spans"] = [
            {
                "start_row": 1,
                "end_row": 1,
                "start_column": 1,
                "end_column": 2,
                "relation": "spanning_header",
            }
        ]
        observation, hypothesis_set = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[binding, copy.deepcopy(binding)],
            independent=True,
        )
        repeatability = _sealed_repeatability(
            self.solver, observation, hypothesis_set
        )

        result = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability=repeatability,
        )

        self.assertEqual("accepted_supplied_consensus", result["terminal_status"])
        alternative = next(
            item
            for item in result["alternatives_considered"]
            if item["accepted_by_constraints"]
        )
        covered = next(
            item
            for item in alternative["empty_explanations"]
            if item["covered_by_declared_span"]
        )
        self.assertEqual((1, 2), (covered["row_ordinal"], covered["column_ordinal"]))
        self.assertEqual([first, second], covered["span_anchor_candidate_ids"])
        self.assertTrue(covered["source_candidate_ids_only"])
        self.assertEqual(0, covered["invented_value_count"])
        metrics = alternative["constraints"]["explicit_empty_cell_evidence"][
            "metrics"
        ]
        self.assertEqual(1, metrics["empty_positions_covered_by_declared_span"])
        self.assertEqual(0, metrics["invented_value_count"])

    def test_invalid_contract_and_unsupported_have_distinct_terminals(self) -> None:
        ledger, projection, binding, _ = _fixture()
        observation, valid_set = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[binding],
            independent=True,
        )
        tampered = copy.deepcopy(valid_set)
        tampered["candidate_ids"] = []
        invalid = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=tampered,
        )
        self.assertEqual("incomplete_evidence", invalid["terminal_status"])
        self.assertFalse(invalid["supplied_hypotheses_exhausted"])
        self.assertFalse(invalid["structural_domain_complete"])
        self.assertFalse(invalid["uniqueness_proven"])
        self.assertFalse(invalid["ambiguity_proven"])
        self.assertTrue(invalid["domain_incomplete"])
        self.assertTrue(invalid["search_not_certifiable"])

        unsupported_binding = copy.deepcopy(binding)
        unsupported_binding.update(
            {
                "decision": "unsupported",
                "row_count": 0,
                "column_count": 0,
                "header_rows": [],
                "header_hierarchy": [],
                "rows": [],
                "spans": [],
                "uncertainty_codes": ["image_not_supported"],
            }
        )
        unsupported_set = self.contracts.build_vlm_hypothesis_set(
            parser_observation=observation,
            binding_hypotheses=[
                {
                    "hypothesis_id": "unsupported",
                    "binding_output": unsupported_binding,
                    "evidence": _binding_evidence(unsupported_binding, 1),
                }
            ],
            model_context=_model_context(independent=True),
        )
        unsupported = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=unsupported_set,
        )
        self.assertEqual("unsupported", unsupported["terminal_status"])
        self.assertTrue(unsupported["supplied_hypotheses_exhausted"])
        self.assertFalse(unsupported["structural_domain_complete"])
        self.assertFalse(unsupported["uniqueness_proven"])
        self.assertFalse(unsupported["ambiguity_proven"])
        self.assertTrue(unsupported["domain_incomplete"])
        self.assertFalse(unsupported["search_not_certifiable"])
        self.assertEqual(
            "supplied_vlm_hypotheses_only", unsupported["search_scope"]
        )

    def test_mixed_supported_and_unsupported_alternatives_are_explained_and_blocked(
        self,
    ) -> None:
        ledger, projection, binding, _ = _fixture()
        observation, _ = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[binding],
            independent=True,
        )
        unsupported_binding = copy.deepcopy(binding)
        unsupported_binding.update(
            {
                "decision": "unsupported",
                "row_count": 0,
                "column_count": 0,
                "header_rows": [],
                "header_hierarchy": [],
                "rows": [],
                "spans": [],
                "uncertainty_codes": ["image_not_supported"],
            }
        )
        inputs = []
        for attempt in (1, 2):
            inputs.extend(
                [
                    {
                        "hypothesis_id": f"attempt-{attempt}-valid",
                        "binding_output": copy.deepcopy(binding),
                        "proposed_geometry": _uniform_geometry(binding),
                        "evidence": _binding_evidence(binding, attempt),
                    },
                    {
                        "hypothesis_id": f"attempt-{attempt}-unsupported",
                        "binding_output": copy.deepcopy(unsupported_binding),
                        "evidence": _binding_evidence(
                            unsupported_binding, attempt
                        ),
                    },
                ]
            )
        hypothesis_set = self.contracts.build_vlm_hypothesis_set(
            parser_observation=observation,
            binding_hypotheses=inputs,
            model_context=_model_context(independent=True),
        )
        record = _sealed_repeatability(self.solver, observation, hypothesis_set)

        result = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability=record,
        )

        self.assertTrue(record["passed"])
        self.assertEqual("incomplete_evidence", result["terminal_status"])
        self.assertIn(
            "pdf_dual_oracle_vlm_mixed_unsupported_alternative",
            result["review_codes"],
        )
        self.assertTrue(result["supplied_hypotheses_exhausted"])
        self.assertFalse(result["search_not_certifiable"])
        self.assertEqual(4, result["alternatives_considered_count"])
        self.assertEqual(
            2,
            sum(
                item["decision"] == "unsupported"
                for item in result["alternatives_considered"]
            ),
        )

    def test_failed_required_continuation_fragment_blocks_logical_group(self) -> None:
        accepted = {
            "table_ref": "table1",
            "terminal_status": "accepted_supplied_consensus",
            "canonical_grid_checksum": "a",
            "column_count": 2,
        }
        blocked = {
            "table_ref": "table2",
            "terminal_status": "parser_vlm_conflict",
            "canonical_grid_checksum": None,
            "column_count": 2,
        }
        contract = {
            "schema_version": PDF_HYBRID_CONTINUATION_SCHEMA,
            "continuation_group_id": "group1",
            "shared_column_count": 2,
            "fragments": [
                {
                    "fragment_order": 1,
                    "page_number": 1,
                    "table_ref": "table1",
                    "repeated_header_policy": "source_header",
                },
                {
                    "fragment_order": 2,
                    "page_number": 2,
                    "table_ref": "table2",
                    "repeated_header_policy": "no_repeated_header",
                },
            ],
            "subtotal_policy": "preserve_fragment_subtotals",
            "duplicate_row_policy": "allow_explicit_repeated_header_only",
        }

        result = self.solver.solve_continuation(
            continuation_contract=contract,
            fragment_results=[accepted, blocked],
        )

        self.assertEqual("parser_vlm_conflict", result["terminal_status"])
        self.assertFalse(result["all_required_fragments_independently_accepted"])
        self.assertIn(
            "pdf_dual_oracle_continuation_fragment_not_accepted_supplied_scope",
            result["reason_codes"],
        )

    def test_valid_plus_rejected_alternative_cannot_claim_unique_acceptance(self) -> None:
        ledger, projection, binding, _ = _fixture()
        observation, hypothesis_set = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[binding],
            independent=True,
        )
        hypothesis_set = self.contracts.build_vlm_hypothesis_set(
            parser_observation=observation,
            binding_hypotheses=[
                {
                    "hypothesis_id": "valid",
                    "binding_output": binding,
                    "proposed_geometry": _uniform_geometry(binding),
                    "evidence": _binding_evidence(binding, 1),
                }
            ],
            rejected_evidence=[
                {"evidence_id": "malformed", "reason_codes": ["malformed_output"]}
            ],
            model_context=_model_context(independent=True),
        )

        result = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
        )

        self.assertEqual("incomplete_evidence", result["terminal_status"])
        self.assertFalse(result["uniqueness_proven"])
        self.assertFalse(result["supplied_hypotheses_exhausted"])
        self.assertTrue(result["search_not_certifiable"])
        self.assertIn("pdf_dual_oracle_vlm_evidence_rejected", result["review_codes"])
        self.assertEqual(2, result["alternatives_considered_count"])

    def test_caller_booleans_do_not_self_attest_independent_topology(self) -> None:
        ledger, projection, binding, _ = _fixture()
        observation = self.contracts.build_parser_observation_from_word_atoms(
            document_ref=ledger["document_ref"],
            pdf_sha256=ledger["pdf_sha256"],
            page_ref=ledger["page_ref"],
            page_number=ledger["page_number"],
            table_ref=ledger["table_ref"],
            table_bbox=ledger["table_bbox"],
            pdf_text_layer_projection=projection,
        )
        context = _model_context(independent=False)
        context["topology_dimensions_independently_observed"] = True
        context["alternative_topology_hypotheses_complete"] = True
        hypothesis_set = self.contracts.build_vlm_hypothesis_set(
            parser_observation=observation,
            binding_hypotheses=[
                {
                    "binding_output": binding,
                    "proposed_geometry": _uniform_geometry(binding),
                    "evidence": _binding_evidence(binding, 1),
                }
            ],
            model_context=context,
        )

        result = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
        )

        self.assertEqual("incomplete_evidence", result["terminal_status"])
        self.assertIn(
            "pdf_dual_oracle_vlm_shape_independence_not_proven",
            result["review_codes"],
        )

    def test_forged_result_and_foreign_package_cannot_materialize(self) -> None:
        ledger, projection, binding, evidence = _fixture()
        observation, hypothesis_set = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[binding, copy.deepcopy(binding)],
            independent=True,
        )
        repeatability = _sealed_repeatability(
            self.solver, observation, hypothesis_set
        )
        result = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability=repeatability,
        )
        forged = copy.deepcopy(result)
        forged["result_id"] = "forged"
        forged_copy = dict(forged)
        forged_copy.pop("result_checksum")
        forged["result_checksum"] = sha256_json(forged_copy)
        with self.assertRaisesRegex(
            PdfDualOracleConsensusError,
            "pdf_dual_oracle_consensus_result_integrity_invalid",
        ):
            self.solver.binding_from_accepted_consensus(
                parser_observation=observation,
                consensus_result=forged,
                vlm_hypothesis_set=hypothesis_set,
                evidence_package=evidence,
            )

        foreign = copy.deepcopy(evidence)
        foreign["package_id"] = "foreign-package"
        with self.assertRaisesRegex(
            PdfDualOracleConsensusError,
            "pdf_dual_oracle_evidence_package_identity_mismatch",
        ):
            self.solver.binding_from_accepted_consensus(
                parser_observation=observation,
                consensus_result=result,
                vlm_hypothesis_set=hypothesis_set,
                evidence_package=foreign,
            )

    def test_tampered_private_dictionary_cannot_cross_accepted_adapter(self) -> None:
        ledger, projection, binding, evidence = _fixture()
        observation, hypothesis_set = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[binding, copy.deepcopy(binding)],
            independent=True,
        )
        result = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability=_sealed_repeatability(
                self.solver, observation, hypothesis_set
            ),
        )
        self.assertEqual("accepted_supplied_consensus", result["terminal_status"])

        mutations = {
            "exact_source_span": "INVENTED",
            "source_value_refs": ["foreign-source-ref"],
            "word_refs": ["foreign-word-ref"],
            "source_bbox": [1.0, 1.0, 2.0, 2.0],
            "source_bbox_refs": ["foreign-bbox-ref"],
            "source_text_checksum_refs": ["foreign-text-checksum"],
            "source_order": 99,
            "invented_financial_payload": "INVENTED",
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                tampered = copy.deepcopy(evidence)
                first = next(iter(tampered["private_candidate_dictionary"].values()))
                first[field] = value
                tampered["candidate_dictionary_hash"] = sha256_json(
                    tampered["private_candidate_dictionary"]
                )
                with self.assertRaisesRegex(
                    PdfDualOracleConsensusError,
                    "pdf_dual_oracle_evidence_dictionary_integrity_invalid",
                ):
                    self.solver.binding_from_accepted_consensus(
                        parser_observation=observation,
                        consensus_result=result,
                        vlm_hypothesis_set=hypothesis_set,
                        evidence_package=tampered,
                    )

        stale_hash = copy.deepcopy(evidence)
        first = next(iter(stale_hash["private_candidate_dictionary"].values()))
        first["exact_source_span"] = "INVENTED"
        with self.assertRaisesRegex(
            PdfDualOracleConsensusError,
            "pdf_dual_oracle_evidence_dictionary_integrity_invalid",
        ):
            self.solver.binding_from_accepted_consensus(
                parser_observation=observation,
                consensus_result=result,
                vlm_hypothesis_set=hypothesis_set,
                evidence_package=stale_hash,
            )

    def test_repeated_alternative_sets_are_grouped_by_attempt_and_invalid_witness_is_excluded(
        self,
    ) -> None:
        ledger, projection, binding, evidence = _fixture()
        observation, _ = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[binding],
            independent=True,
        )
        bad_geometry = _uniform_geometry(binding)
        bad_geometry["columns"]["boundaries"] = [0.0, 0.9, 1.0]
        hypothesis_set = self.contracts.build_vlm_hypothesis_set(
            parser_observation=observation,
            binding_hypotheses=[
                {
                    "hypothesis_id": "attempt-1-valid",
                    "binding_output": binding,
                    "proposed_geometry": _uniform_geometry(binding),
                    "evidence": _binding_evidence(binding, 1),
                },
                {
                    "hypothesis_id": "attempt-1-invalid",
                    "binding_output": copy.deepcopy(binding),
                    "proposed_geometry": copy.deepcopy(bad_geometry),
                    "evidence": _binding_evidence(binding, 1),
                },
                {
                    "hypothesis_id": "attempt-2-invalid",
                    "binding_output": copy.deepcopy(binding),
                    "proposed_geometry": copy.deepcopy(bad_geometry),
                    "evidence": _binding_evidence(binding, 2),
                },
                {
                    "hypothesis_id": "attempt-2-valid",
                    "binding_output": copy.deepcopy(binding),
                    "proposed_geometry": _uniform_geometry(binding),
                    "evidence": _binding_evidence(binding, 2),
                },
            ],
            model_context=_model_context(independent=True),
        )
        repeatability = _sealed_repeatability(
            self.solver, observation, hypothesis_set
        )
        result = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
            historical_repeatability=repeatability,
        )

        self.assertTrue(repeatability["passed"])
        self.assertFalse(repeatability["ever_conflicted"])
        self.assertEqual(2, len(repeatability["attempt_history"]))
        self.assertTrue(
            all(
                item["alternative_count"] == 2
                for item in repeatability["attempt_history"]
            )
        )
        self.assertEqual("accepted_supplied_consensus", result["terminal_status"])
        self.assertEqual(
            ["attempt-1-valid", "attempt-2-valid"],
            result["consensus_witness_hypothesis_ids"],
        )
        materialized = self.solver.binding_from_accepted_consensus(
            parser_observation=observation,
            consensus_result=result,
            vlm_hypothesis_set=hypothesis_set,
            evidence_package=evidence,
        )
        self.assertEqual(binding["rows"], materialized["rows"])

    def test_wrong_row_and_lost_empty_region_are_typed_conflicts(self) -> None:
        ledger, projection, binding, _ = _fixture()
        wrong_row = copy.deepcopy(binding)
        wrong_row["rows"][0]["cells"], wrong_row["rows"][1]["cells"] = (
            wrong_row["rows"][1]["cells"],
            wrong_row["rows"][0]["cells"],
        )
        observation, wrong_row_set = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[wrong_row],
            independent=True,
        )
        wrong_row_result = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=wrong_row_set,
            historical_repeatability=_passed_repeatability(),
        )
        self.assertEqual("parser_vlm_conflict", wrong_row_result["terminal_status"])
        self.assertIn(
            "pdf_dual_oracle_candidate_row_incompatible",
            wrong_row_result["reason_codes"],
        )

        candidate_ids = list(ledger["candidate_order"])
        lost_empty = copy.deepcopy(binding)
        lost_empty["column_count"] = 3
        lost_empty["rows"][0]["cells"] = [
            [candidate_ids[0]],
            [candidate_ids[1]],
            [],
        ]
        lost_empty["rows"][1]["cells"] = [
            [candidate_ids[2]],
            [candidate_ids[3]],
            [],
        ]
        _, lost_empty_set = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[lost_empty],
            independent=True,
        )
        lost_empty_result = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=lost_empty_set,
            historical_repeatability=_passed_repeatability(),
        )
        self.assertEqual(
            "parser_vlm_conflict", lost_empty_result["terminal_status"]
        )
        self.assertIn(
            "pdf_dual_oracle_empty_parser_candidate_collision",
            lost_empty_result["reason_codes"],
        )

    def test_span_requires_anchor_candidate_and_empty_covered_positions(self) -> None:
        ledger, projection, binding, _ = _fixture()
        invalid_span = copy.deepcopy(binding)
        invalid_span["spans"] = [
            {
                "start_row": 1,
                "end_row": 1,
                "start_column": 1,
                "end_column": 2,
                "relation": "spanning_header",
            }
        ]
        observation, hypothesis_set = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[invalid_span],
            independent=True,
        )

        result = self.solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
        )

        self.assertEqual("incomplete_evidence", result["terminal_status"])
        self.assertIn(
            "pdf_vlm_hypothesis_span_anchor_or_empty_coverage_invalid",
            result["reason_codes"],
        )

    def test_custom_solver_hypothesis_cap_is_enforced(self) -> None:
        ledger, projection, binding, _ = _fixture()
        observation, hypothesis_set = self._inputs(
            ledger=ledger,
            projection=projection,
            bindings=[binding, copy.deepcopy(binding)],
            independent=True,
        )
        bounded_solver = PdfDualOracleConsensusFactory(
            PdfDualOracleConsensusConfig(maximum_hypotheses=1)
        ).create()

        result = bounded_solver.solve(
            parser_observation=observation,
            vlm_hypothesis_set=hypothesis_set,
        )

        self.assertEqual("incomplete_evidence", result["terminal_status"])
        self.assertIn("pdf_vlm_hypothesis_count_budget_exceeded", result["reason_codes"])

    def test_accepted_continuation_uses_real_checked_fragment_results(self) -> None:
        first_ledger, projection, binding, _ = _fixture()
        second_ledger, second_projection, second_binding, _ = _fixture(
            values=("e", "f", "g", "h")
        )
        second_ledger["table_ref"] = "table-2"
        second_ledger["page_ref"] = "page-2"
        second_ledger["page_number"] = 2
        old_ids = [
            str(cell[0])
            for row in second_binding["rows"]
            for cell in row["cells"]
        ]
        for word in second_projection["word_inventory"]:
            word["page_ref"] = "page-2"
        new_ids = [
            "wa_"
            + stable_digest(
                ["pdf-sha", "page-2", f"word-{index}"], length=16
            )
            for index in range(len(old_ids))
        ]
        remap = dict(zip(old_ids, new_ids))
        for row in second_binding["rows"]:
            row["cells"] = [
                [remap[str(candidate_id)] for candidate_id in cell]
                for cell in row["cells"]
            ]
        second_binding["header_rows"] = []
        second_binding["header_hierarchy"] = []
        for row in second_binding["rows"]:
            row["row_kind"] = "data"
        first_observation, first_set = self._inputs(
            ledger=first_ledger,
            projection=projection,
            bindings=[binding, copy.deepcopy(binding)],
            independent=True,
        )
        second_observation, second_set = self._inputs(
            ledger=second_ledger,
            projection=second_projection,
            bindings=[second_binding, copy.deepcopy(second_binding)],
            independent=True,
        )
        first = self.solver.solve(
            parser_observation=first_observation,
            vlm_hypothesis_set=first_set,
            historical_repeatability=_sealed_repeatability(
                self.solver, first_observation, first_set
            ),
        )
        second = self.solver.solve(
            parser_observation=second_observation,
            vlm_hypothesis_set=second_set,
            historical_repeatability=_sealed_repeatability(
                self.solver, second_observation, second_set
            ),
        )
        contract = _continuation_contract(
            [first_observation["table_ref"], second_observation["table_ref"]],
            columns=int(binding["column_count"]),
        )

        result = self.solver.solve_continuation(
            continuation_contract=contract,
            fragment_results=[first, second],
        )

        self.assertEqual("human_review_required", result["terminal_status"])
        self.assertIn(
            "pdf_dual_oracle_continuation_fragment_evidence_missing",
            result["reason_codes"],
        )
        fragment_evidence = [
            self.contracts.build_continuation_fragment_evidence(
                parser_observation=first_observation,
                consensus_result=first,
                binding_output=binding,
                fragment_order=1,
                page_number=1,
                repeated_header_policy="source_header",
            ),
            self.contracts.build_continuation_fragment_evidence(
                parser_observation=second_observation,
                consensus_result=second,
                binding_output=second_binding,
                fragment_order=2,
                page_number=2,
                repeated_header_policy="no_repeated_header",
            ),
        ]
        result = self.solver.solve_continuation(
            continuation_contract=contract,
            fragment_results=[first, second],
            fragment_evidence=fragment_evidence,
        )

        self.assertEqual("accepted_supplied_consensus", result["terminal_status"])
        self.assertEqual(
            PDF_DUAL_ORACLE_CONTINUATION_RESULT_SCHEMA,
            result["schema_version"],
        )
        self.assertTrue(result["all_required_fragments_independently_accepted"])
        self.assertTrue(result["fragment_evidence_complete"])
        self.assertTrue(result["joined_coverage_complete"])
        self.assertEqual([], self.solver.validate_continuation_result(result))
        self.assertEqual(4, len(result["joined_rows"]))
        self.assertTrue(result["join_plan_checksum"])
        legacy = copy.deepcopy(result)
        for key in (
            "shared_column_count",
            "subtotal_policy",
            "duplicate_row_policy",
            "ordered_fragments",
            "joined_rows",
            "join_plan_checksum",
        ):
            legacy.pop(key)
        legacy["schema_version"] = PDF_DUAL_ORACLE_CONTINUATION_RESULT_SCHEMA_V1
        legacy.pop("result_checksum")
        legacy["result_checksum"] = sha256_json(legacy)
        self.assertEqual([], self.solver.validate_continuation_result(legacy))

        tampered_evidence = copy.deepcopy(fragment_evidence)
        tampered_evidence[1]["rows"][0]["row_content_checksum"] = "tampered"
        tampered = self.solver.solve_continuation(
            continuation_contract=contract,
            fragment_results=[first, second],
            fragment_evidence=tampered_evidence,
        )
        self.assertNotEqual("accepted_supplied_consensus", tampered["terminal_status"])
        self.assertIn(
            "pdf_dual_oracle_continuation_fragment_evidence_checksum_invalid",
            tampered["reason_codes"],
        )

        duplicate = self.solver.solve_continuation(
            continuation_contract=contract,
            fragment_results=[first, first],
            fragment_evidence=fragment_evidence,
        )
        self.assertNotEqual("accepted_supplied_consensus", duplicate["terminal_status"])
        self.assertIn(
            "pdf_dual_oracle_continuation_fragment_identity_duplicate",
            duplicate["reason_codes"],
        )

        missing = self.solver.solve_continuation(
            continuation_contract=contract,
            fragment_results=[first],
            fragment_evidence=fragment_evidence[:1],
        )
        self.assertFalse(missing["fragment_coverage_complete"])
        self.assertIn(
            "pdf_dual_oracle_continuation_fragment_set_mismatch",
            missing["reason_codes"],
        )

        extra_result = copy.deepcopy(second)
        extra_result["table_ref"] = "table-extra"
        extra_copy = dict(extra_result)
        extra_copy.pop("result_checksum")
        extra_result["result_checksum"] = sha256_json(extra_copy)
        extra = self.solver.solve_continuation(
            continuation_contract=contract,
            fragment_results=[first, second, extra_result],
            fragment_evidence=fragment_evidence,
        )
        self.assertFalse(extra["fragment_coverage_complete"])
        self.assertIn(
            "pdf_dual_oracle_continuation_fragment_set_mismatch",
            extra["reason_codes"],
        )

        wrong_columns = copy.deepcopy(contract)
        wrong_columns["shared_column_count"] += 1
        mismatched = self.solver.solve_continuation(
            continuation_contract=wrong_columns,
            fragment_results=[first, second],
            fragment_evidence=fragment_evidence,
        )
        self.assertIn(
            "pdf_dual_oracle_continuation_column_model_mismatch",
            mismatched["reason_codes"],
        )

        open_schema = copy.deepcopy(contract)
        open_schema["unexpected"] = True
        invalid_contract = self.solver.solve_continuation(
            continuation_contract=open_schema,
            fragment_results=[first, second],
            fragment_evidence=fragment_evidence,
        )
        self.assertIn(
            "pdf_dual_oracle_continuation_contract_invalid",
            invalid_contract["reason_codes"],
        )

    def test_continuation_materialization_offsets_and_seals_provenance(self) -> None:
        contract, fragment_results, fragment_evidence, fragment_materializations = (
            self._continuation_case()
        )
        continuation = self.solver.solve_continuation(
            continuation_contract=contract,
            fragment_results=fragment_results,
            fragment_evidence=fragment_evidence,
        )
        materializer = PdfHybridMaterializationFactory().create()

        result = materializer.materialize_continuation(
            continuation_result=continuation,
            fragment_evidence=fragment_evidence,
            fragment_materializations=fragment_materializations,
        )

        self.assertEqual(PDF_CONTINUATION_MATERIALIZATION_SCHEMA, result["schema_version"])
        self.assertEqual([], materializer.validate_continuation_materialization(result))
        self.assertEqual([1, 3], [item["joined_row_start"] for item in result["fragment_offsets"]])
        self.assertEqual([0, 2], [item["row_offset"] for item in result["fragment_offsets"]])
        self.assertEqual([], result["omitted_candidate_ids"])
        self.assertEqual([], result["extra_candidate_ids"])
        self.assertEqual([], result["duplicate_candidate_ids"])
        self.assertTrue(result["candidate_ownership_exact"])
        self.assertEqual(0, result["model_invented_values_total"])
        self.assertEqual(8, len(result["selected_candidate_ids"]))
        self.assertEqual([], result["deduplicated_candidate_ids"])

        tampered = copy.deepcopy(fragment_materializations)
        tampered[1]["cells"][0]["candidate_ids"] = []
        with self.assertRaises(PdfHybridMaterializationError):
            materializer.materialize_continuation(
                continuation_result=continuation,
                fragment_evidence=fragment_evidence,
                fragment_materializations=tampered,
            )

    def test_continuation_materialization_offsets_headers_spans_and_boundary_dedupe(
        self,
    ) -> None:
        header_case = self._continuation_case(
            second_header=True,
            spanning_headers=True,
        )
        header_continuation = self.solver.solve_continuation(
            continuation_contract=header_case[0],
            fragment_results=header_case[1],
            fragment_evidence=header_case[2],
        )
        materializer = PdfHybridMaterializationFactory().create()
        header_result = materializer.materialize_continuation(
            continuation_result=header_continuation,
            fragment_evidence=header_case[2],
            fragment_materializations=header_case[3],
        )

        self.assertEqual([1, 3], header_result["header_rows"])
        self.assertEqual([1, 3], [item["parent_row"] for item in header_result["header_hierarchy"]])
        self.assertEqual([1, 3], [item["start_row"] for item in header_result["spans"]])
        self.assertEqual([1, 1], [item["source_start_row"] for item in header_result["spans"]])

        subtotal_case = self._continuation_case(
            second_values=("c", "d", "g", "h"),
            first_last_kind="subtotal",
            second_first_kind="subtotal",
        )
        subtotal_case[0]["subtotal_policy"] = "deduplicate_exact_boundary_subtotal"
        subtotal_case[0]["duplicate_row_policy"] = "forbid"
        subtotal_continuation = self.solver.solve_continuation(
            continuation_contract=subtotal_case[0],
            fragment_results=subtotal_case[1],
            fragment_evidence=subtotal_case[2],
        )
        subtotal_result = materializer.materialize_continuation(
            continuation_result=subtotal_continuation,
            fragment_evidence=subtotal_case[2],
            fragment_materializations=subtotal_case[3],
        )

        self.assertEqual(3, subtotal_result["row_count"])
        self.assertEqual(2, len(subtotal_result["deduplicated_candidate_ids"]))
        self.assertEqual(1, len(subtotal_result["deduplicated_boundary_rows"]))
        self.assertEqual(
            set(subtotal_result["source_candidate_ids"]),
            set(subtotal_result["selected_candidate_ids"])
            | set(subtotal_result["deduplicated_candidate_ids"]),
        )
        self.assertEqual([], materializer.validate_continuation_materialization(subtotal_result))

    def test_continuation_join_enforces_headers_subtotals_and_duplicate_rows(
        self,
    ) -> None:
        repeated = self._continuation_case(second_header=True)
        repeated_contract = copy.deepcopy(repeated[0])
        repeated_contract["fragments"][1]["repeated_header_policy"] = (
            "no_repeated_header"
        )
        repeated_result = self.solver.solve_continuation(
            continuation_contract=repeated_contract,
            fragment_results=repeated[1],
            fragment_evidence=repeated[2],
        )
        self.assertEqual("human_review_required", repeated_result["terminal_status"])
        self.assertFalse(repeated_result["repeated_header_policy_passed"])
        self.assertIn(
            "pdf_dual_oracle_continuation_repeated_header_policy_mismatch",
            repeated_result["reason_codes"],
        )

        subtotal = self._continuation_case(
            second_values=("c", "d", "g", "h"),
            first_last_kind="subtotal",
            second_first_kind="subtotal",
        )
        subtotal_contract = copy.deepcopy(subtotal[0])
        subtotal_contract["subtotal_policy"] = (
            "deduplicate_exact_boundary_subtotal"
        )
        subtotal_contract["duplicate_row_policy"] = "forbid"
        subtotal_result = self.solver.solve_continuation(
            continuation_contract=subtotal_contract,
            fragment_results=subtotal[1],
            fragment_evidence=subtotal[2],
        )
        self.assertEqual(
            "accepted_supplied_consensus", subtotal_result["terminal_status"]
        )
        self.assertEqual(1, len(subtotal_result["deduplicated_boundary_rows"]))
        self.assertEqual(3, subtotal_result["joined_row_count"])
        self.assertTrue(subtotal_result["joined_coverage_complete"])

        preserved_contract = copy.deepcopy(subtotal[0])
        preserved_contract["duplicate_row_policy"] = "forbid"
        preserved = self.solver.solve_continuation(
            continuation_contract=preserved_contract,
            fragment_results=subtotal[1],
            fragment_evidence=subtotal[2],
        )
        self.assertNotEqual("accepted_supplied_consensus", preserved["terminal_status"])
        self.assertIn(
            "pdf_dual_oracle_continuation_duplicate_row_policy_violation",
            preserved["reason_codes"],
        )

    def _continuation_case(
        self,
        *,
        second_values: tuple[str, ...] = ("e", "f", "g", "h"),
        second_header: bool = False,
        first_last_kind: str | None = None,
        second_first_kind: str | None = None,
        spanning_headers: bool = False,
    ) -> tuple[dict, list[dict], list[dict], list[dict]]:
        first_ledger, first_projection, first_binding, _ = _fixture()
        second_ledger, second_projection, second_binding, _ = _fixture(
            values=second_values
        )
        second_ledger["table_ref"] = "table-2"
        second_ledger["page_ref"] = "page-2"
        second_ledger["page_number"] = 2
        old_ids = [
            str(candidate_id)
            for row in second_binding["rows"]
            for cell in row["cells"]
            for candidate_id in cell
        ]
        for word in second_projection["word_inventory"]:
            word["page_ref"] = "page-2"
        new_ids = [
            "wa_"
            + stable_digest(
                ["pdf-sha", "page-2", f"word-{index}"], length=16
            )
            for index in range(len(old_ids))
        ]
        remap = dict(zip(old_ids, new_ids))
        for row in second_binding["rows"]:
            row["cells"] = [
                [remap[str(candidate_id)] for candidate_id in cell]
                for cell in row["cells"]
            ]
        if not second_header:
            second_binding["header_rows"] = []
            second_binding["header_hierarchy"] = []
            for row in second_binding["rows"]:
                row["row_kind"] = "data"
        if first_last_kind is not None:
            first_binding["rows"][-1]["row_kind"] = first_last_kind
        if second_first_kind is not None:
            second_binding["rows"][0]["row_kind"] = second_first_kind
        if spanning_headers:
            for current_binding in (first_binding, second_binding):
                if not current_binding["header_rows"]:
                    continue
                current_binding["rows"][0]["cells"] = [
                    [
                        *current_binding["rows"][0]["cells"][0],
                        *current_binding["rows"][0]["cells"][1],
                    ],
                    [],
                ]
                current_binding["spans"] = [
                    {
                        "start_row": 1,
                        "end_row": 1,
                        "start_column": 1,
                        "end_column": 2,
                        "relation": "spanning_header",
                    }
                ]
                current_binding["header_hierarchy"] = [
                    {
                        "parent_row": 1,
                        "parent_column": 1,
                        "child_start_column": 1,
                        "child_end_column": 2,
                    }
                ]
        first_observation, first_set = self._inputs(
            ledger=first_ledger,
            projection=first_projection,
            bindings=[first_binding, copy.deepcopy(first_binding)],
            independent=True,
        )
        second_observation, second_set = self._inputs(
            ledger=second_ledger,
            projection=second_projection,
            bindings=[second_binding, copy.deepcopy(second_binding)],
            independent=True,
        )
        first = self.solver.solve(
            parser_observation=first_observation,
            vlm_hypothesis_set=first_set,
            historical_repeatability=_sealed_repeatability(
                self.solver, first_observation, first_set
            ),
        )
        second = self.solver.solve(
            parser_observation=second_observation,
            vlm_hypothesis_set=second_set,
            historical_repeatability=_sealed_repeatability(
                self.solver, second_observation, second_set
            ),
        )
        policies = ["source_header", "source_header" if second_header else "no_repeated_header"]
        evidence = [
            self.contracts.build_continuation_fragment_evidence(
                parser_observation=observation,
                consensus_result=result,
                binding_output=current_binding,
                fragment_order=index,
                page_number=index,
                repeated_header_policy=policies[index - 1],
            )
            for index, (observation, result, current_binding) in enumerate(
                (
                    (first_observation, first, first_binding),
                    (second_observation, second, second_binding),
                ),
                start=1,
            )
        ]
        contract = _continuation_contract(
            [first_observation["table_ref"], second_observation["table_ref"]],
            columns=int(first_binding["column_count"]),
        )
        contract["fragments"][1]["repeated_header_policy"] = policies[1]
        materializations = [
            PdfHybridMaterializationFactory().create().materialize(
                evidence_package=_materialization_evidence_package(
                    observation=observation,
                    binding_output=current_binding,
                ),
                binding_output=current_binding,
            )
            for observation, current_binding in (
                (first_observation, first_binding),
                (second_observation, second_binding),
            )
        ]
        return contract, [first, second], evidence, materializations

    def _inputs(
        self,
        *,
        ledger: dict,
        projection: dict,
        bindings: list[dict],
        independent: bool,
    ) -> tuple[dict, dict]:
        observation = (
            self.contracts.build_parser_observation_from_word_atoms(
                document_ref=str(ledger["document_ref"]),
                pdf_sha256=str(ledger["pdf_sha256"]),
                page_ref=str(ledger["page_ref"]),
                page_number=int(ledger["page_number"]),
                table_ref=str(ledger["table_ref"]),
                table_bbox=ledger["table_bbox"],
                pdf_text_layer_projection=projection,
                scope_word_refs=[
                    str(item["word_ref"])
                    for item in projection["word_inventory"]
                ],
            )
            if independent
            else self.contracts.build_parser_observation(
                compact_ledger=ledger,
                pdf_text_layer_projection=projection,
            )
        )
        hypothesis_set = self.contracts.build_vlm_hypothesis_set(
            parser_observation=observation,
            binding_hypotheses=[
                {
                    "hypothesis_id": f"hypothesis-{index}",
                    "binding_output": binding,
                    "proposed_geometry": {
                        "rows": {
                            "kind": "normalized_boundaries",
                            "boundaries": [
                                value / int(binding["row_count"])
                                for value in range(int(binding["row_count"]) + 1)
                            ],
                        },
                        "columns": {
                            "kind": "normalized_boundaries",
                            "boundaries": [
                                value / int(binding["column_count"])
                                for value in range(int(binding["column_count"]) + 1)
                            ],
                        },
                    },
                    "evidence": {
                        "attempt_id": f"attempt-{index}",
                        "attempt_number": index,
                        "evidence_revision": "test-revision",
                        "provider": "test-vlm",
                        "model": "test-model",
                        "provider_config_hash": "provider-config-hash",
                        "package_ids": [str(binding["package_id"])],
                        "packages": [
                            {
                                "package_id": str(binding["package_id"]),
                                "crop_sha256": str(binding["crop_sha256"]),
                                "candidate_dictionary_hash": str(
                                    binding["candidate_dictionary_hash"]
                                ),
                            }
                        ],
                    },
                }
                for index, binding in enumerate(bindings, start=1)
            ],
            model_context=_model_context(independent=independent),
        )
        return observation, hypothesis_set


def _model_context(*, independent: bool) -> dict:
    return {
        "provider": "test-vlm",
        "model": "test-model",
        "configuration_hash": "provider-config-hash",
        "bounded_row_windows": True,
        "provider_calls_replayed": 2,
        "new_provider_calls": 0,
        "topology_input_basis": (
            "visual_crop_without_parser_grid" if independent else "parser_seeded_grid"
        ),
        "topology_dimensions_source": (
            "vlm_visual_observation" if independent else "parser_seeded"
        ),
        "alternative_generation_contract": (
            "explicit_exhaustive_bounded_alternatives"
            if independent
            else "single_response_only"
        ),
        "topology_prompt_contract_hash": "prompt-contract" if independent else "",
        "crop_manifest_hash": "crop-manifest" if independent else "",
        "provider_token_accounting_exact": True,
        "candidate_ownership_exact": True,
        "observed_image_bytes": 100,
        "maximum_image_bytes": 1000,
        "observed_output_tokens": 10,
        "maximum_output_tokens": 100,
        "no_silent_truncation": True,
        "column_splitting_used": False,
        "hidden_provider_failover": False,
        "alternative_topology_hypotheses_complete": independent,
    }


def _passed_repeatability() -> dict:
    return {"required": True, "passed": True, "ever_conflicted": False}


def _sealed_repeatability(
    solver: object, observation: dict, hypothesis_set: dict
) -> dict:
    return solver.build_repeatability_record(
        parser_observation=observation,
        vlm_hypothesis_set=hypothesis_set,
    )


def _uniform_geometry(binding: dict) -> dict:
    return {
        "rows": {
            "kind": "normalized_boundaries",
            "boundaries": [
                value / int(binding["row_count"])
                for value in range(int(binding["row_count"]) + 1)
            ],
        },
        "columns": {
            "kind": "normalized_boundaries",
            "boundaries": [
                value / int(binding["column_count"])
                for value in range(int(binding["column_count"]) + 1)
            ],
        },
    }


def _binding_evidence(binding: dict, attempt: int) -> dict:
    return {
        "attempt_id": f"attempt-{attempt}",
        "attempt_number": attempt,
        "evidence_revision": "test-revision",
        "provider": "test-vlm",
        "model": "test-model",
        "provider_config_hash": "provider-config-hash",
        "package_ids": [str(binding["package_id"])],
        "packages": [
            {
                "package_id": str(binding["package_id"]),
                "crop_sha256": str(binding["crop_sha256"]),
                "candidate_dictionary_hash": str(
                    binding["candidate_dictionary_hash"]
                ),
            }
        ],
    }


def _continuation_contract(table_refs: list[str], *, columns: int) -> dict:
    return {
        "schema_version": PDF_HYBRID_CONTINUATION_SCHEMA,
        "continuation_group_id": "checked-group",
        "shared_column_count": columns,
        "fragments": [
            {
                "fragment_order": index,
                "page_number": index,
                "table_ref": table_ref,
                "repeated_header_policy": (
                    "source_header" if index == 1 else "no_repeated_header"
                ),
            }
            for index, table_ref in enumerate(table_refs, start=1)
        ],
        "subtotal_policy": "preserve_fragment_subtotals",
        "duplicate_row_policy": "allow_explicit_repeated_header_only",
        "fragment_coverage_required": True,
        "joined_coverage_required": True,
        "authoritative": False,
    }


def _materialization_evidence_package(
    *,
    observation: dict,
    binding_output: dict,
) -> dict:
    dictionary = {
        str(candidate["candidate_id"]): {
            "exact_source_span": candidate["exact_visible_value"],
            "source_value_refs": copy.deepcopy(candidate["source_value_refs"]),
            "word_refs": copy.deepcopy(candidate["word_refs"]),
        }
        for candidate in observation["candidates"]
    }
    return {
        "package_id": binding_output["package_id"],
        "crop_identity": {"crop_sha256": binding_output["crop_sha256"]},
        "candidate_dictionary_hash": binding_output["candidate_dictionary_hash"],
        "private_candidate_dictionary": dictionary,
    }


def _fixture(
    *,
    rows: int = 2,
    columns: int = 2,
    values: tuple[str, ...] = ("a", "b", "c", "d"),
) -> tuple[dict, dict, dict, dict]:
    self_values = list(values)
    if len(self_values) != rows * columns:
        raise ValueError("fixture values must fill the grid")
    table_bbox = [0.0, 0.0, 200.0, 100.0]
    bbox_inventory = [{"bbox_ref": "table-bbox", "bbox": table_bbox}]
    word_inventory = []
    dictionary = {}
    candidate_order = []
    row_height = 100.0 / rows
    column_width = 200.0 / columns
    row_model = []
    column_model = []
    for row in range(1, rows + 1):
        row_model.append(
            {
                "ordinal": row,
                "start": (row - 1) * row_height,
                "end": row * row_height,
            }
        )
    for column in range(1, columns + 1):
        column_model.append(
            {
                "ordinal": column,
                "start": (column - 1) * column_width,
                "end": column * column_width,
            }
        )
    grid = [[[] for _ in range(columns)] for _ in range(rows)]
    for ordinal, value in enumerate(self_values):
        row = ordinal // columns + 1
        column = ordinal % columns + 1
        word_ref = f"word-{ordinal}"
        candidate_id = "wa_" + stable_digest(
            ["pdf-sha", "page-1", word_ref], length=16
        )
        source_ref = f"source-{ordinal}"
        bbox = [
            (column - 1) * column_width + 10.0,
            (row - 1) * row_height + 10.0,
            column * column_width - 10.0,
            row * row_height - 10.0,
        ]
        bbox_ref = f"word-bbox-{ordinal}"
        bbox_inventory.append({"bbox_ref": bbox_ref, "bbox": bbox})
        word_inventory.append(
            {
                "parser_ordinal": ordinal + 1,
                "word_ref": word_ref,
                "page_ref": "page-1",
                "bbox_ref": bbox_ref,
                "text": value,
                "geometry_reading_order": ordinal + 1,
                "text_checksum_ref": f"text-checksum-{ordinal}",
                "source_value_ref": source_ref,
            }
        )
        dictionary[candidate_id] = {
            "candidate_id": candidate_id,
            "exact_source_span": value,
            "source_value_refs": [source_ref],
            "word_refs": [word_ref],
            "source_bbox": bbox,
            "source_bbox_refs": [bbox_ref],
            "source_text_checksum_refs": [f"text-checksum-{ordinal}"],
            "source_cell_ref": f"cell-{row}-{column}",
            "source_cell_bbox": [
                (column - 1) * column_width,
                (row - 1) * row_height,
                column * column_width,
                row * row_height,
            ],
            "expected_row_ordinal": row,
            "expected_column_ordinal": column,
            "source_order": ordinal,
        }
        candidate_order.append(candidate_id)
        grid[row - 1][column - 1] = [candidate_id]
    ledger = {
        "schema_version": "broker_reports_pdf_hybrid_compact_ledger_v2",
        "ledger_id": "ledger-1",
        "ledger_checksum": "ledger-checksum",
        "document_ref": "document-1",
        "pdf_sha256": "pdf-sha",
        "page_ref": "page-1",
        "page_number": 1,
        "table_ref": "table-1",
        "table_bbox": table_bbox,
        "row_count": rows,
        "column_count": columns,
        "header_depth": 1 if rows > 1 else 0,
        "candidate_order": candidate_order,
        "private_candidate_dictionary": dictionary,
        "candidate_dictionary_hash": sha256_json(dictionary),
        "row_model": row_model,
        "column_model": column_model,
    }
    projection = {
        "bbox_inventory": bbox_inventory,
        "word_inventory": word_inventory,
        "line_inventory": [],
    }
    binding = {
        "schema_version": PDF_HYBRID_BINDING_OUTPUT_SCHEMA,
        "package_id": "package-1",
        "crop_sha256": "crop-sha",
        "candidate_dictionary_hash": ledger["candidate_dictionary_hash"],
        "decision": "bound",
        "row_count": rows,
        "column_count": columns,
        "header_rows": [1] if rows > 1 else [],
        "header_hierarchy": [],
        "rows": [
            {
                "row_ordinal": row,
                "row_kind": "header" if row == 1 and rows > 1 else "data",
                "cells": grid[row - 1],
            }
            for row in range(1, rows + 1)
        ],
        "spans": [],
        "uncertainty_codes": [],
    }
    evidence = {
        "package_id": "package-1",
        "crop_identity": {"crop_sha256": "crop-sha"},
        "candidate_dictionary_hash": ledger["candidate_dictionary_hash"],
        "private_candidate_dictionary": dictionary,
    }
    return ledger, projection, binding, evidence


if __name__ == "__main__":
    unittest.main()
