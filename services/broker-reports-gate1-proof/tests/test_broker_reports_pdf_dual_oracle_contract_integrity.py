from __future__ import annotations

import copy
import unittest

from broker_reports_gate1.contracts import stable_digest
from broker_reports_gate1.pdf_dual_oracle_consensus import (
    PdfDualOracleConsensusFactory,
)
from broker_reports_gate1.pdf_dual_oracle_contracts import (
    PdfDualOracleContractError,
    PdfDualOracleContractFactory,
)
from broker_reports_gate1.pdf_hybrid_contracts import (
    PDF_HYBRID_BINDING_OUTPUT_SCHEMA,
    sha256_json,
)


class PdfDualOracleContractIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contracts = PdfDualOracleContractFactory().create()
        self.observation, self.binding = _observation_and_binding(self.contracts)

    def test_nested_row_geometry_continuation_and_uncertainty_are_closed(self) -> None:
        cases = [
            (
                "row extra field",
                lambda hypothesis: hypothesis["rows"][0].__setitem__(
                    "invented_financial_payload", "INVENTED"
                ),
                "pdf_vlm_hypothesis_row_contract_invalid",
            ),
            (
                "row ordinal bool",
                lambda hypothesis: hypothesis["rows"][0].__setitem__(
                    "row_ordinal", True
                ),
                "pdf_vlm_hypothesis_row_identity_invalid",
            ),
            (
                "geometry outer extra field",
                lambda hypothesis: hypothesis["proposed_geometry"].__setitem__(
                    "invented_axis", {}
                ),
                "pdf_vlm_hypothesis_geometry_contract_invalid",
            ),
            (
                "geometry axis extra field",
                lambda hypothesis: hypothesis["proposed_geometry"]["rows"].__setitem__(
                    "confidence", 1.0
                ),
                "pdf_vlm_hypothesis_geometry_contract_invalid",
            ),
            (
                "continuation extra field",
                lambda hypothesis: hypothesis["continuation"].__setitem__(
                    "hidden_fragment", "table-elsewhere"
                ),
                "pdf_vlm_hypothesis_continuation_contract_invalid",
            ),
            (
                "continuation bool is exact",
                lambda hypothesis: hypothesis["continuation"].__setitem__(
                    "required", 1
                ),
                "pdf_vlm_hypothesis_continuation_contract_invalid",
            ),
            (
                "uncertainty codes are strings",
                lambda hypothesis: hypothesis.__setitem__(
                    "uncertainty_codes", [1]
                ),
                "pdf_vlm_hypothesis_uncertainty_contract_invalid",
            ),
        ]

        for label, mutate, expected_error in cases:
            with self.subTest(label=label):
                hypothesis_set = self._hypothesis_set()
                mutate(hypothesis_set["hypotheses"][0])
                _resign(hypothesis_set)

                self.assertIn(
                    expected_error,
                    self.contracts.validate_vlm_hypothesis_set(
                        parser_observation=self.observation,
                        hypothesis_set=hypothesis_set,
                    ),
                )

    def test_hypothesis_identity_and_authority_flags_are_exact(self) -> None:
        cases = [
            (
                lambda hypothesis: hypothesis.__setitem__("hypothesis_id", ""),
                "pdf_vlm_hypothesis_identity_invalid",
            ),
            (
                lambda hypothesis: hypothesis.__setitem__(
                    "candidate_id_only", False
                ),
                "pdf_vlm_hypothesis_authority_boundary_invalid",
            ),
            (
                lambda hypothesis: hypothesis.__setitem__(
                    "authoritative_values_present", True
                ),
                "pdf_vlm_hypothesis_authority_boundary_invalid",
            ),
        ]

        for mutate, expected_error in cases:
            with self.subTest(expected_error=expected_error):
                hypothesis_set = self._hypothesis_set()
                mutate(hypothesis_set["hypotheses"][0])
                _resign(hypothesis_set)
                self.assertIn(
                    expected_error,
                    self.contracts.validate_vlm_hypothesis_set(
                        parser_observation=self.observation,
                        hypothesis_set=hypothesis_set,
                    ),
                )

        set_level = self._hypothesis_set()
        set_level["authoritative_values_present"] = 0
        _resign(set_level)
        self.assertIn(
            "pdf_vlm_hypothesis_authority_boundary_invalid",
            self.contracts.validate_vlm_hypothesis_set(
                parser_observation=self.observation,
                hypothesis_set=set_level,
            ),
        )

    def test_evidence_requires_typed_nonempty_lineage_and_package_scope(self) -> None:
        cases = [
            ("attempt_id", ""),
            ("attempt_number", True),
            ("evidence_revision", ""),
            ("package_ids", []),
        ]
        for key, value in cases:
            with self.subTest(key=key):
                hypothesis_set = self._hypothesis_set()
                hypothesis_set["hypotheses"][0]["evidence"][key] = value
                _resign(hypothesis_set)
                self.assertIn(
                    "pdf_vlm_hypothesis_evidence_identity_invalid",
                    self.contracts.validate_vlm_hypothesis_set(
                        parser_observation=self.observation,
                        hypothesis_set=hypothesis_set,
                    ),
                )

        package_extra = self._hypothesis_set()
        package_extra["hypotheses"][0]["evidence"]["packages"][0][
            "free_value"
        ] = "INVENTED"
        _resign(package_extra)
        self.assertIn(
            "pdf_vlm_hypothesis_evidence_package_invalid",
            self.contracts.validate_vlm_hypothesis_set(
                parser_observation=self.observation,
                hypothesis_set=package_extra,
            ),
        )

    def test_model_lineage_is_sealed_at_set_scope_and_cross_linked(self) -> None:
        hypothesis_set = self._hypothesis_set(
            evidence_overrides={
                "provider": "foreign-provider",
                "model": "foreign-model",
                "provider_config_hash": "foreign-config",
            }
        )
        evidence = hypothesis_set["hypotheses"][0]["evidence"]
        context = hypothesis_set["model_context"]

        self.assertEqual(context["provider"], evidence["provider"])
        self.assertEqual(context["model"], evidence["model"])
        self.assertEqual(
            context["configuration_hash"], evidence["provider_config_hash"]
        )

        evidence["provider_config_hash"] = "tampered-config"
        _resign(hypothesis_set)
        self.assertIn(
            "pdf_vlm_hypothesis_evidence_model_context_mismatch",
            self.contracts.validate_vlm_hypothesis_set(
                parser_observation=self.observation,
                hypothesis_set=hypothesis_set,
            ),
        )

    def test_missing_evidence_is_rejected_instead_of_becoming_consensus(self) -> None:
        hypothesis_set = self.contracts.build_vlm_hypothesis_set(
            parser_observation=self.observation,
            binding_hypotheses=[
                {
                    "hypothesis_id": "missing-evidence",
                    "binding_output": self.binding,
                    "proposed_geometry": _geometry(),
                }
            ],
            model_context=_model_context(with_budgets=True),
        )

        self.assertEqual([], hypothesis_set["hypotheses"])
        self.assertEqual("missing-evidence", hypothesis_set["rejected_evidence"][0]["evidence_id"])
        self.assertIn(
            "pdf_vlm_hypothesis_evidence_identity_invalid",
            hypothesis_set["rejected_evidence"][0]["reason_codes"],
        )

    def test_budget_attestation_is_derived_and_required_for_autoaccept(self) -> None:
        complete = self._hypothesis_set()
        self.assertTrue(
            complete["model_context"]["image_and_output_budgets_attested"]
        )
        self.assertTrue(complete["model_context"]["context_guard_attested"])

        incomplete = self._hypothesis_set(with_budgets=False)
        self.assertIsNone(incomplete["model_context"]["observed_image_bytes"])
        self.assertFalse(
            incomplete["model_context"]["image_and_output_budgets_attested"]
        )
        self.assertFalse(incomplete["model_context"]["context_guard_attested"])
        result = PdfDualOracleConsensusFactory().create().solve(
            parser_observation=self.observation,
            vlm_hypothesis_set=incomplete,
            historical_repeatability={
                "required": True,
                "passed": True,
                "ever_conflicted": False,
            },
        )
        self.assertEqual("incomplete_evidence", result["terminal_status"])
        self.assertIn(
            "pdf_dual_oracle_context_guard_not_proven", result["review_codes"]
        )

        forged = copy.deepcopy(incomplete)
        forged["model_context"]["image_and_output_budgets_attested"] = True
        forged["model_context"]["context_guard_attested"] = True
        _resign(forged)
        self.assertIn(
            "pdf_vlm_hypothesis_model_context_derived_fields_invalid",
            self.contracts.validate_vlm_hypothesis_set(
                parser_observation=self.observation,
                hypothesis_set=forged,
            ),
        )

        zero_call_context = _model_context(with_budgets=True)
        zero_call_context["new_provider_calls"] = 0
        zero_calls = self._hypothesis_set(model_context=zero_call_context)
        self.assertFalse(zero_calls["model_context"]["context_guard_attested"])

    def test_window_execution_accounting_is_closed_and_raw_calls_are_not_hidden(
        self,
    ) -> None:
        context = _model_context(with_budgets=True)
        context.update(
            {
                "new_provider_calls": 4,
                "execution_mode": "vertical_atom_windows",
                "window_count": 2,
                "raw_provider_calls": 4,
                "stitched_oracle_observations": 2,
                "window_lineage_checksum": "window-lineage-sha",
            }
        )
        hypothesis_set = self._hypothesis_set(model_context=context)
        sealed = hypothesis_set["model_context"]
        self.assertEqual(4, sealed["new_provider_calls"])
        self.assertEqual(4, sealed["raw_provider_calls"])
        self.assertEqual(2, sealed["stitched_oracle_observations"])
        self.assertTrue(sealed["context_guard_attested"])

        forged = copy.deepcopy(hypothesis_set)
        forged["model_context"]["raw_provider_calls"] = 3
        _resign(forged)
        errors = self.contracts.validate_vlm_hypothesis_set(
            parser_observation=self.observation,
            hypothesis_set=forged,
        )
        self.assertIn(
            "pdf_vlm_hypothesis_model_context_execution_invalid",
            errors,
        )

    def test_legacy_lineage_remains_typed_but_cannot_claim_independence(self) -> None:
        context = _model_context(with_budgets=False)
        context.update(
            {
                "topology_input_basis": "legacy_candidate_placement_only",
                "topology_dimensions_source": "parser_seeded",
                "alternative_generation_contract": "single_response_only",
                "topology_prompt_contract_hash": "",
                "alternative_topology_hypotheses_complete": False,
            }
        )
        hypothesis_set = self._hypothesis_set(model_context=context)

        self.assertEqual(
            [],
            self.contracts.validate_vlm_hypothesis_set(
                parser_observation=self.observation,
                hypothesis_set=hypothesis_set,
            ),
        )
        self.assertFalse(
            hypothesis_set["model_context"][
                "topology_dimensions_independently_observed"
            ]
        )
        self.assertFalse(
            hypothesis_set["model_context"][
                "alternative_topology_hypotheses_complete"
            ]
        )

    def test_rejected_reason_codes_are_strict_strings(self) -> None:
        for reason_codes in ([1], ["contains whitespace"], [""]):
            with self.subTest(reason_codes=reason_codes):
                with self.assertRaisesRegex(
                    PdfDualOracleContractError,
                    "pdf_vlm_hypothesis_rejected_evidence_invalid",
                ):
                    self._hypothesis_set(
                        rejected_evidence=[
                            {
                                "evidence_id": "bad-evidence",
                                "reason_codes": reason_codes,
                            }
                        ]
                    )

        hypothesis_set = self._hypothesis_set(
            rejected_evidence=[
                {
                    "evidence_id": "valid-rejection",
                    "reason_codes": ["z_reason", "a_reason"],
                }
            ]
        )
        self.assertEqual(
            ["a_reason", "z_reason"],
            hypothesis_set["rejected_evidence"][0]["reason_codes"],
        )
        hypothesis_set["rejected_evidence"][0]["reason_codes"] = [
            "a_reason",
            "a_reason",
        ]
        _resign(hypothesis_set)
        self.assertIn(
            "pdf_vlm_hypothesis_rejected_evidence_invalid",
            self.contracts.validate_vlm_hypothesis_set(
                parser_observation=self.observation,
                hypothesis_set=hypothesis_set,
            ),
        )

    def test_repeat_history_is_append_only_and_conflict_is_monotonic(self) -> None:
        history = self.contracts.create_repeat_history(
            scope={
                "parser_observation_checksum": self.observation[
                    "observation_checksum"
                ],
                "provider": "test-provider",
                "model": "test-model",
                "configuration_hash": "config-v1",
                "crop_manifest_hash": "crop-v1",
                "solver_version": "solver-v1",
            }
        )
        windowed_history = self.contracts.create_repeat_history(
            scope={
                **history["scope"],
                "runtime_policy_version": "runtime-v1",
                "execution_mode": "vertical_atom_windows",
                "window_policy_version": "window-v1",
                "window_plan_hash": "plan-v1",
            }
        )
        self.assertNotEqual(
            history["scope_checksum"], windowed_history["scope_checksum"]
        )
        self.assertEqual(
            [], self.contracts.validate_repeat_history(windowed_history)
        )
        first = self.contracts.append_repeat_history_event(
            history=history,
            attempt_id="attempt-1",
            attempt_number=1,
            evidence_revision="revision-1",
            canonical_grid_checksum="grid-a",
            topology_checksum="topology-a",
            terminal_status="accepted_supplied_consensus",
            expected_prior_history_checksum=history["history_checksum"],
        )
        immutable_first = copy.deepcopy(first)
        conflicted = self.contracts.append_repeat_history_event(
            history=first,
            attempt_id="attempt-2",
            attempt_number=2,
            evidence_revision="revision-1",
            canonical_grid_checksum="grid-b",
            topology_checksum="topology-b",
            terminal_status="accepted_supplied_consensus",
            expected_prior_history_checksum=first["history_checksum"],
        )
        later_agreement = self.contracts.append_repeat_history_event(
            history=conflicted,
            attempt_id="attempt-3",
            attempt_number=3,
            evidence_revision="revision-1",
            canonical_grid_checksum="grid-b",
            topology_checksum="topology-b",
            terminal_status="accepted_supplied_consensus",
            expected_prior_history_checksum=conflicted["history_checksum"],
        )

        self.assertEqual(immutable_first, first)
        self.assertTrue(conflicted["ever_conflicted"])
        self.assertTrue(later_agreement["ever_conflicted"])
        self.assertTrue(later_agreement["events"][-1]["conflict_observed"])
        self.assertEqual(
            conflicted["history_checksum"],
            later_agreement["events"][-1]["prior_history_checksum"],
        )
        idempotent = self.contracts.append_repeat_history_event(
            history=later_agreement,
            attempt_id="attempt-3",
            attempt_number=3,
            evidence_revision="revision-1",
            canonical_grid_checksum="grid-b",
            topology_checksum="topology-b",
            terminal_status="accepted_supplied_consensus",
        )
        self.assertEqual(later_agreement, idempotent)

        with self.assertRaisesRegex(
            PdfDualOracleContractError,
            "pdf_dual_oracle_repeat_history_attempt_rewrite_forbidden",
        ):
            self.contracts.append_repeat_history_event(
                history=later_agreement,
                attempt_id="attempt-3",
                attempt_number=3,
                evidence_revision="revision-1",
                canonical_grid_checksum="grid-c",
                topology_checksum="topology-c",
                terminal_status="accepted_supplied_consensus",
            )
        tampered = copy.deepcopy(later_agreement)
        tampered["ever_conflicted"] = False
        tampered_copy = dict(tampered)
        tampered_copy.pop("history_checksum")
        tampered["history_checksum"] = sha256_json(tampered_copy)
        self.assertIn(
            "pdf_dual_oracle_repeat_history_integrity_invalid",
            self.contracts.validate_repeat_history(tampered),
        )

    def _hypothesis_set(
        self,
        *,
        with_budgets: bool = True,
        model_context: dict | None = None,
        evidence_overrides: dict | None = None,
        rejected_evidence: list[dict] | None = None,
    ) -> dict:
        evidence = _evidence(self.binding)
        evidence.update(evidence_overrides or {})
        return self.contracts.build_vlm_hypothesis_set(
            parser_observation=self.observation,
            binding_hypotheses=[
                {
                    "hypothesis_id": "hypothesis-1",
                    "binding_output": self.binding,
                    "proposed_geometry": _geometry(),
                    "evidence": evidence,
                }
            ],
            rejected_evidence=rejected_evidence,
            model_context=(
                model_context
                if model_context is not None
                else _model_context(with_budgets=with_budgets)
            ),
        )


def _observation_and_binding(contracts) -> tuple[dict, dict]:
    table_bbox = [0.0, 0.0, 200.0, 100.0]
    bbox_inventory = []
    word_inventory = []
    for ordinal, (text, bbox) in enumerate(
        (("left", [10.0, 10.0, 90.0, 90.0]), ("right", [110.0, 10.0, 190.0, 90.0])),
        start=1,
    ):
        bbox_ref = f"bbox-{ordinal}"
        bbox_inventory.append({"bbox_ref": bbox_ref, "bbox": bbox})
        word_inventory.append(
            {
                "word_ref": f"word-{ordinal}",
                "page_ref": "page-1",
                "bbox_ref": bbox_ref,
                "text": text,
                "geometry_reading_order": ordinal,
                "text_checksum_ref": f"text-checksum-{ordinal}",
                "source_value_ref": f"source-{ordinal}",
            }
        )
    observation = contracts.build_parser_observation_from_word_atoms(
        document_ref="document-1",
        pdf_sha256="pdf-sha",
        page_ref="page-1",
        page_number=1,
        table_ref="table-1",
        table_bbox=table_bbox,
        pdf_text_layer_projection={
            "bbox_inventory": bbox_inventory,
            "word_inventory": word_inventory,
            "line_inventory": [],
        },
    )
    binding = {
        "schema_version": PDF_HYBRID_BINDING_OUTPUT_SCHEMA,
        "package_id": "package-1",
        "crop_sha256": "crop-sha",
        "candidate_dictionary_hash": "dictionary-sha",
        "decision": "bound",
        "row_count": 1,
        "column_count": 2,
        "header_rows": [],
        "header_hierarchy": [],
        "rows": [
            {
                "row_ordinal": 1,
                "row_kind": "data",
                "cells": [[observation["candidate_order"][0]], [observation["candidate_order"][1]]],
            }
        ],
        "spans": [],
        "uncertainty_codes": [],
    }
    return observation, binding


def _geometry() -> dict:
    return {
        "rows": {"kind": "normalized_boundaries", "boundaries": [0.0, 1.0]},
        "columns": {
            "kind": "normalized_boundaries",
            "boundaries": [0.0, 0.5, 1.0],
        },
    }


def _evidence(binding: dict) -> dict:
    return {
        "attempt_id": "attempt-1",
        "attempt_number": 1,
        "evidence_revision": "revision-1",
        "provider": "test-provider",
        "model": "test-model",
        "provider_config_hash": "config-v1",
        "package_ids": [binding["package_id"]],
        "packages": [
            {
                "package_id": binding["package_id"],
                "crop_sha256": binding["crop_sha256"],
                "candidate_dictionary_hash": binding["candidate_dictionary_hash"],
            }
        ],
    }


def _model_context(*, with_budgets: bool) -> dict:
    context = {
        "provider": "test-provider",
        "model": "test-model",
        "configuration_hash": "config-v1",
        "bounded_row_windows": True,
        "provider_calls_replayed": 0,
        "new_provider_calls": 1,
        "topology_input_basis": "visual_crop_without_parser_grid",
        "topology_dimensions_source": "vlm_visual_observation",
        "alternative_generation_contract": "explicit_exhaustive_bounded_alternatives",
        "topology_prompt_contract_hash": "prompt-contract-sha",
        "crop_manifest_hash": "crop-manifest-sha",
        "provider_token_accounting_exact": True,
        "candidate_ownership_exact": True,
        "no_silent_truncation": True,
        "column_splitting_used": False,
        "hidden_provider_failover": False,
        "alternative_topology_hypotheses_complete": True,
    }
    if with_budgets:
        context.update(
            {
                "observed_image_bytes": 100,
                "maximum_image_bytes": 1000,
                "observed_output_tokens": 10,
                "maximum_output_tokens": 100,
            }
        )
    return context


def _resign(hypothesis_set: dict) -> None:
    for hypothesis in hypothesis_set.get("hypotheses") or []:
        grid_projection = {
            key: copy.deepcopy(hypothesis.get(key))
            for key in (
                "row_count",
                "column_count",
                "header_rows",
                "header_hierarchy",
                "rows",
                "spans",
            )
        }
        hypothesis["canonical_grid_checksum"] = sha256_json(grid_projection)
        topology_projection = {
            **grid_projection,
            "proposed_geometry": copy.deepcopy(hypothesis.get("proposed_geometry")),
            "continuation": copy.deepcopy(hypothesis.get("continuation")),
        }
        hypothesis["topology_checksum"] = sha256_json(topology_projection)
        hypothesis_copy = dict(hypothesis)
        hypothesis_copy.pop("hypothesis_checksum", None)
        hypothesis["hypothesis_checksum"] = sha256_json(hypothesis_copy)
    hypothesis_set["alternative_topologies_explicit"] = len(
        {
            item.get("canonical_grid_checksum")
            for item in hypothesis_set.get("hypotheses") or []
        }
    ) > 1
    hypothesis_set["hypothesis_set_id"] = "pdfvlmhypset_" + stable_digest(
        [
            hypothesis_set.get("parser_observation_id"),
            [
                item.get("hypothesis_checksum")
                for item in hypothesis_set.get("hypotheses") or []
            ],
            hypothesis_set.get("rejected_evidence"),
            hypothesis_set.get("model_context"),
            hypothesis_set.get("policy_version"),
        ],
        length=24,
    )
    set_copy = dict(hypothesis_set)
    set_copy.pop("hypothesis_set_checksum", None)
    hypothesis_set["hypothesis_set_checksum"] = sha256_json(set_copy)


if __name__ == "__main__":
    unittest.main()
