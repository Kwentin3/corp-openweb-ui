from __future__ import annotations

import copy
from dataclasses import dataclass
from statistics import median
from typing import Any

from .contracts import stable_digest
from .pdf_dual_oracle_contracts import (
    PdfDualOracleContractConfig,
    PdfDualOracleContractError,
    PdfDualOracleContractFactory,
)
from .pdf_hybrid_contracts import PDF_HYBRID_BINDING_OUTPUT_SCHEMA, sha256_json
from .pdf_hybrid_structure import PDF_HYBRID_CONTINUATION_SCHEMA


PDF_DUAL_ORACLE_CONSENSUS_RESULT_SCHEMA = (
    "broker_reports_pdf_dual_oracle_consensus_result_v1"
)
PDF_DUAL_ORACLE_CONTINUATION_RESULT_SCHEMA_V1 = (
    "broker_reports_pdf_dual_oracle_continuation_consensus_v1"
)
PDF_DUAL_ORACLE_CONTINUATION_RESULT_SCHEMA = (
    "broker_reports_pdf_dual_oracle_continuation_consensus_v2"
)
PDF_DUAL_ORACLE_CONSENSUS_POLICY_VERSION = "pdf_dual_oracle_consensus_policy_v1"
PDF_DUAL_ORACLE_REPEATABILITY_RECORD_SCHEMA = (
    "broker_reports_pdf_dual_oracle_repeatability_record_v2"
)
TERMINAL_STATUSES = {
    "accepted_unique_consensus",
    "ambiguous_multiple_consensus",
    "parser_vlm_conflict",
    "no_valid_consensus",
    "human_review_required",
    "unsupported",
}
_FACTORY_TOKEN = object()

_CONTINUATION_CONTRACT_KEYS = {
    "schema_version",
    "continuation_group_id",
    "shared_column_count",
    "fragments",
    "subtotal_policy",
    "duplicate_row_policy",
    "fragment_coverage_required",
    "joined_coverage_required",
    "authoritative",
}
_CONTINUATION_FRAGMENT_KEYS = {
    "fragment_order",
    "page_number",
    "table_ref",
    "repeated_header_policy",
}
_CONTINUATION_RESULT_V1_KEYS = {
    "schema_version",
    "policy_version",
    "continuation_group_id",
    "terminal_status",
    "reason_codes",
    "ordered_table_refs",
    "fragment_terminals",
    "fragment_coverage_complete",
    "fragment_evidence_complete",
    "source_row_count",
    "joined_row_count",
    "source_candidate_count",
    "joined_candidate_count",
    "deduplicated_boundary_rows",
    "joined_coverage_complete",
    "repeated_header_policy_passed",
    "subtotal_policy_passed",
    "duplicate_row_policy_passed",
    "canonical_joined_grid_checksum",
    "all_required_fragments_independently_accepted",
    "authority_state",
    "production_gate2_selection_changed",
    "result_checksum",
}
_CONTINUATION_RESULT_V2_KEYS = _CONTINUATION_RESULT_V1_KEYS | {
    "shared_column_count",
    "subtotal_policy",
    "duplicate_row_policy",
    "ordered_fragments",
    "joined_rows",
    "join_plan_checksum",
}
_CONTINUATION_RESULT_ORDERED_FRAGMENT_KEYS = {
    "fragment_order",
    "page_number",
    "table_ref",
    "repeated_header_policy",
    "fragment_result_checksum",
    "fragment_evidence_checksum",
    "canonical_grid_checksum",
    "binding_checksum",
}
_CONTINUATION_RESULT_JOINED_ROW_KEYS = {
    "row_ordinal",
    "row_kind",
    "cells",
    "row_content_checksum",
    "fragment_order",
    "page_number",
    "table_ref",
    "source_row_ordinal",
}
_CONTINUATION_RESULT_DEDUPLICATED_ROW_KEYS = {
    "table_ref",
    "fragment_order",
    "page_number",
    "source_row_ordinal",
    "row_content_checksum",
    "removed_candidate_ids",
    "kept_table_ref",
    "kept_fragment_order",
    "kept_page_number",
    "kept_source_row_ordinal",
    "kept_joined_row_ordinal",
}
_CONSENSUS_RESULT_KEYS = {
    "schema_version",
    "policy_version",
    "solver_version",
    "result_id",
    "table_ref",
    "parser_observation_id",
    "parser_observation_checksum",
    "vlm_hypothesis_set_id",
    "vlm_hypothesis_set_checksum",
    "terminal_status",
    "reason_codes",
    "review_codes",
    "canonical_grid_checksum",
    "row_count",
    "column_count",
    "valid_canonical_grid_checksums",
    "consensus_witness_hypothesis_ids",
    "alternatives_considered",
    "alternatives_considered_count",
    "valid_distinct_grid_count",
    "structurally_unique_within_supplied_evidence",
    "uniqueness_proven",
    "solver_search_complete",
    "required_evidence_to_resolve",
    "historical_repeatability",
    "historical_conflict_preserved",
    "numeric_score_used",
    "majority_vote_used",
    "oracle_preference_used",
    "reference_answer_used",
    "repair_performed",
    "authority_state",
    "production_gate2_selection_changed",
    "result_checksum",
}

FACTORY_REQUIRED = (
    "PdfDualOracleConsensusFactory.create is the only deterministic dual-oracle "
    "constraint-enumeration entrypoint"
)
FORBIDDEN = (
    "The solver must not score, rank, repair, majority-vote, prefer an oracle, "
    "or use reference answers"
)


class PdfDualOracleConsensusError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PdfDualOracleConsensusConfig:
    policy_version: str = PDF_DUAL_ORACLE_CONSENSUS_POLICY_VERSION
    coordinate_tolerance_points: float = 0.75
    maximum_candidates: int = 2048
    maximum_hypotheses: int = 16
    maximum_grid_positions: int = 4096


class PdfDualOracleConsensusFactory:
    def __init__(self, config: PdfDualOracleConsensusConfig | None = None) -> None:
        self.config = config or PdfDualOracleConsensusConfig()

    def create(self) -> "PdfDualOracleConsensusRuntime":
        if self.config.policy_version != PDF_DUAL_ORACLE_CONSENSUS_POLICY_VERSION:
            raise PdfDualOracleConsensusError("pdf_dual_oracle_solver_policy_invalid")
        if (
            self.config.coordinate_tolerance_points < 0
            or self.config.maximum_candidates < 1
            or self.config.maximum_hypotheses < 1
            or self.config.maximum_grid_positions < 1
        ):
            raise PdfDualOracleConsensusError("pdf_dual_oracle_solver_config_invalid")
        return PdfDualOracleConsensusRuntime(
            self.config, _factory_token=_FACTORY_TOKEN
        )


class PdfDualOracleConsensusRuntime:
    def __init__(
        self,
        config: PdfDualOracleConsensusConfig,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise PdfDualOracleConsensusError(
                "pdf_dual_oracle_consensus_factory_required"
            )
        self.config = config
        self.contracts = PdfDualOracleContractFactory(
            PdfDualOracleContractConfig(
                maximum_candidates=config.maximum_candidates,
                maximum_hypotheses=config.maximum_hypotheses,
                maximum_grid_positions=config.maximum_grid_positions,
            )
        ).create()

    def build_repeatability_record(
        self,
        *,
        parser_observation: dict[str, Any],
        vlm_hypothesis_set: dict[str, Any],
    ) -> dict[str, Any]:
        parser_errors = self.contracts.validate_parser_observation(
            parser_observation
        )
        hypothesis_errors = self.contracts.validate_vlm_hypothesis_set(
            parser_observation=parser_observation,
            hypothesis_set=vlm_hypothesis_set,
        )
        if parser_errors or hypothesis_errors:
            raise PdfDualOracleConsensusError(
                "pdf_dual_oracle_repeatability_evidence_invalid"
            )
        candidates = _candidate_map(parser_observation)
        evaluated_alternatives = [
            (
                self._unsupported_alternative(hypothesis)
                if hypothesis.get("decision") == "unsupported"
                else self._evaluate_hypothesis(
                    parser_observation=parser_observation,
                    candidates=candidates,
                    hypothesis=hypothesis,
                )
            )
            for hypothesis in _dicts(vlm_hypothesis_set.get("hypotheses"))
        ]
        return _build_repeatability_record(
            parser_observation=parser_observation,
            hypothesis_set=vlm_hypothesis_set,
            evaluated_alternatives=evaluated_alternatives,
            solver_version=self.config.policy_version,
        )

    def sync_repeat_history(
        self,
        *,
        parser_observation: dict[str, Any],
        vlm_hypothesis_set: dict[str, Any],
        history: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = self.build_repeatability_record(
            parser_observation=parser_observation,
            vlm_hypothesis_set=vlm_hypothesis_set,
        )
        context = _object(vlm_hypothesis_set.get("model_context"))
        scope = {
            "parser_observation_checksum": str(
                parser_observation.get("observation_checksum") or ""
            ),
            "provider": str(context.get("provider") or ""),
            "model": str(context.get("model") or ""),
            "configuration_hash": str(context.get("configuration_hash") or ""),
            "crop_manifest_hash": str(context.get("crop_manifest_hash") or ""),
            "solver_version": self.config.policy_version,
        }
        current = (
            self.contracts.create_repeat_history(scope=scope)
            if history is None
            else copy.deepcopy(history)
        )
        history_errors = self.contracts.validate_repeat_history(current)
        if history_errors:
            raise PdfDualOracleConsensusError(history_errors[0])
        if current.get("scope") != {
            key: scope[key] for key in sorted(scope)
        }:
            raise PdfDualOracleConsensusError(
                "pdf_dual_oracle_repeat_history_scope_mismatch"
            )
        hypotheses = _dicts(vlm_hypothesis_set.get("hypotheses"))
        revisions_by_attempt: dict[str, set[str]] = {}
        for hypothesis in hypotheses:
            evidence = _object(hypothesis.get("evidence"))
            revisions_by_attempt.setdefault(
                str(evidence.get("attempt_id") or ""), set()
            ).add(str(evidence.get("evidence_revision") or ""))
        for attempt in record.get("attempt_history") or []:
            attempt_id = str(attempt.get("attempt_id") or "")
            revisions = revisions_by_attempt.get(attempt_id, set())
            if len(revisions) != 1 or "" in revisions:
                raise PdfDualOracleConsensusError(
                    "pdf_dual_oracle_repeat_history_evidence_revision_invalid"
                )
            valid_checksums = [
                str(item)
                for item in attempt.get("valid_canonical_grid_checksums") or []
            ]
            terminal_status = (
                "accepted_unique_consensus"
                if len(valid_checksums) == 1
                else "ambiguous_multiple_consensus"
                if len(valid_checksums) > 1
                else "no_valid_consensus"
            )
            try:
                current = self.contracts.append_repeat_history_event(
                    history=current,
                    attempt_id=attempt_id,
                    attempt_number=int(attempt.get("attempt_number") or 0),
                    evidence_revision=next(iter(revisions)),
                    canonical_grid_checksum=(
                        valid_checksums[0] if len(valid_checksums) == 1 else None
                    ),
                    topology_checksum=str(
                        attempt.get("alternative_set_checksum") or ""
                    )
                    or None,
                    terminal_status=terminal_status,
                    expected_prior_history_checksum=str(
                        current.get("history_checksum") or ""
                    ),
                )
            except PdfDualOracleContractError as exc:
                raise PdfDualOracleConsensusError(exc.code) from exc
        return current

    def solve(
        self,
        *,
        parser_observation: dict[str, Any],
        vlm_hypothesis_set: dict[str, Any],
        historical_repeatability: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        parser_errors = self.contracts.validate_parser_observation(parser_observation)
        hypothesis_errors = self.contracts.validate_vlm_hypothesis_set(
            parser_observation=parser_observation,
            hypothesis_set=vlm_hypothesis_set,
        )
        if parser_errors or hypothesis_errors:
            return self._result(
                parser_observation=parser_observation,
                hypothesis_set=vlm_hypothesis_set,
                terminal_status="no_valid_consensus",
                alternatives=[],
                valid_checksums=[],
                review_codes=[],
                global_reason_codes=sorted(set(parser_errors + hypothesis_errors)),
                required_evidence=["valid_parser_and_vlm_contracts"],
                historical_repeatability=historical_repeatability,
            )

        candidates = _candidate_map(parser_observation)
        hypotheses = _dicts(vlm_hypothesis_set.get("hypotheses"))
        if len(candidates) > self.config.maximum_candidates:
            return self._result(
                parser_observation=parser_observation,
                hypothesis_set=vlm_hypothesis_set,
                terminal_status="unsupported",
                alternatives=[],
                valid_checksums=[],
                review_codes=[],
                global_reason_codes=["pdf_dual_oracle_candidate_budget_exceeded"],
                required_evidence=["smaller_bounded_table_or_row_window_contract"],
                historical_repeatability=historical_repeatability,
            )
        if not hypotheses:
            rejected = _dicts(vlm_hypothesis_set.get("rejected_evidence"))
            rejected_codes = sorted(
                set(
                    str(code)
                    for item in rejected
                    for code in item.get("reason_codes") or []
                )
            )
            return self._result(
                parser_observation=parser_observation,
                hypothesis_set=vlm_hypothesis_set,
                terminal_status=("no_valid_consensus" if rejected else "unsupported"),
                alternatives=[
                    self._rejected_evidence_alternative(item)
                    for item in rejected
                ],
                valid_checksums=[],
                review_codes=[],
                global_reason_codes=(
                    [
                        "pdf_dual_oracle_all_vlm_evidence_invalid",
                        *rejected_codes,
                    ]
                    if rejected
                    else ["pdf_dual_oracle_vlm_hypothesis_unavailable"]
                ),
                required_evidence=["bounded_candidate_id_topology_hypothesis"],
                historical_repeatability=historical_repeatability,
            )

        supported = [item for item in hypotheses if item.get("decision") != "unsupported"]
        if not supported:
            return self._result(
                parser_observation=parser_observation,
                hypothesis_set=vlm_hypothesis_set,
                terminal_status="unsupported",
                alternatives=[self._unsupported_alternative(item) for item in hypotheses],
                valid_checksums=[],
                review_codes=[],
                global_reason_codes=["pdf_dual_oracle_all_vlm_hypotheses_unsupported"],
                required_evidence=["supported_bounded_table_topology"],
                historical_repeatability=historical_repeatability,
            )

        evaluated_alternatives = [
            (
                self._unsupported_alternative(hypothesis)
                if hypothesis.get("decision") == "unsupported"
                else self._evaluate_hypothesis(
                    parser_observation=parser_observation,
                    candidates=candidates,
                    hypothesis=hypothesis,
                )
            )
            for hypothesis in hypotheses
        ]
        rejected_evidence = _dicts(vlm_hypothesis_set.get("rejected_evidence"))
        alternatives = [
            *evaluated_alternatives,
            *[
                self._rejected_evidence_alternative(item)
                for item in rejected_evidence
            ],
        ]
        valid = [
            item
            for item in evaluated_alternatives
            if item["accepted_by_constraints"]
        ]
        checksum_groups: dict[str, list[dict[str, Any]]] = {}
        for item in valid:
            checksum_groups.setdefault(str(item["canonical_grid_checksum"]), []).append(item)
        valid_checksums = sorted(checksum_groups)

        context = _object(vlm_hypothesis_set.get("model_context"))
        review_codes = []
        construction = _object(parser_observation.get("candidate_construction"))
        if (
            construction.get("kind") != "raw_word_atoms"
            or construction.get("semantic_grid_dependency") is not False
        ):
            review_codes.append(
                "pdf_dual_oracle_parser_candidate_grouping_independence_not_proven"
            )
        if context.get("topology_dimensions_independently_observed") is not True:
            review_codes.append("pdf_dual_oracle_vlm_shape_independence_not_proven")
        if context.get("alternative_topology_hypotheses_complete") is not True:
            review_codes.append("pdf_dual_oracle_vlm_alternative_set_not_complete")
        if context.get("context_guard_attested") is not True:
            review_codes.append("pdf_dual_oracle_context_guard_not_proven")
        if rejected_evidence:
            review_codes.append("pdf_dual_oracle_vlm_evidence_rejected")
        if len(supported) != len(hypotheses):
            review_codes.append(
                "pdf_dual_oracle_vlm_mixed_unsupported_alternative"
            )
        repeatability = historical_repeatability or {}
        derived_repeatability = _build_repeatability_record(
            parser_observation=parser_observation,
            hypothesis_set=vlm_hypothesis_set,
            evaluated_alternatives=evaluated_alternatives,
            solver_version=self.config.policy_version,
        )
        repeatability_passed = _repeatability_passed(
            parser_observation=parser_observation,
            hypothesis_set=vlm_hypothesis_set,
            evaluated_alternatives=evaluated_alternatives,
            record=repeatability,
            solver_version=self.config.policy_version,
        )
        if (
            repeatability.get("ever_conflicted") is True
            and derived_repeatability.get("ever_conflicted") is not True
        ):
            derived_repeatability = copy.deepcopy(derived_repeatability)
            derived_repeatability["external_prior_conflict_claimed"] = True
            derived_repeatability["ever_conflicted"] = True
            derived_repeatability["passed"] = False
            derived_repeatability.pop("record_checksum", None)
            derived_repeatability["record_checksum"] = sha256_json(
                derived_repeatability
            )
        if derived_repeatability.get("ever_conflicted") is True:
            review_codes.append("pdf_dual_oracle_historical_same_evidence_conflict")
        if not repeatability_passed:
            review_codes.append("pdf_dual_oracle_repeatability_incomplete")
        for item in valid:
            review_codes.extend(str(code) for code in item.get("ambiguity_codes") or [])
            if item.get("decision") == "ambiguous":
                review_codes.append("pdf_dual_oracle_vlm_declared_ambiguous")
            if item.get("uncertainty_codes"):
                review_codes.append("pdf_dual_oracle_vlm_uncertainty_unresolved")
            if not _object(item.get("evidence")).get("package_ids"):
                review_codes.append("pdf_dual_oracle_vlm_package_lineage_missing")

        if len(valid_checksums) > 1:
            terminal = "ambiguous_multiple_consensus"
            reasons = ["pdf_dual_oracle_multiple_physically_valid_grids"]
            required = ["human_signed_topology_or_new_disambiguating_geometry"]
        elif len(valid_checksums) == 1:
            if review_codes:
                terminal = "human_review_required"
                reasons = sorted(set(review_codes))
                required = _required_evidence(review_codes)
            else:
                terminal = "accepted_unique_consensus"
                reasons = []
                required = []
        else:
            rejected_codes = sorted(
                set(
                    code
                    for item in alternatives
                    for code in item.get("reason_codes") or []
                )
            )
            physical_conflict = any(
                code.startswith("pdf_dual_oracle_geometry_")
                or code.startswith("pdf_dual_oracle_candidate_")
                or code.startswith("pdf_dual_oracle_empty_")
                or code.startswith("pdf_dual_oracle_merged_")
                or code.startswith("pdf_dual_oracle_order_")
                for code in rejected_codes
            )
            terminal = "parser_vlm_conflict" if physical_conflict else "no_valid_consensus"
            reasons = rejected_codes or ["pdf_dual_oracle_no_structurally_valid_grid"]
            required = _required_evidence(reasons)

        return self._result(
            parser_observation=parser_observation,
            hypothesis_set=vlm_hypothesis_set,
            terminal_status=terminal,
            alternatives=alternatives,
            valid_checksums=valid_checksums,
            review_codes=sorted(set(review_codes)),
            global_reason_codes=reasons,
            required_evidence=required,
            historical_repeatability=derived_repeatability,
        )

    def binding_from_accepted_consensus(
        self,
        *,
        parser_observation: dict[str, Any],
        consensus_result: dict[str, Any],
        vlm_hypothesis_set: dict[str, Any],
        evidence_package: dict[str, Any],
    ) -> dict[str, Any]:
        expected_result = self.solve(
            parser_observation=parser_observation,
            vlm_hypothesis_set=vlm_hypothesis_set,
            historical_repeatability=_object(
                consensus_result.get("historical_repeatability")
            ),
        )
        if (
            consensus_result.get("result_checksum")
            != expected_result.get("result_checksum")
            or consensus_result != expected_result
        ):
            raise PdfDualOracleConsensusError(
                "pdf_dual_oracle_consensus_result_integrity_invalid"
            )
        if (
            consensus_result.get("terminal_status")
            != "accepted_unique_consensus"
            or consensus_result.get("uniqueness_proven") is not True
            or consensus_result.get("solver_search_complete") is not True
            or consensus_result.get("valid_distinct_grid_count") != 1
            or consensus_result.get("reason_codes")
            or consensus_result.get("review_codes")
        ):
            raise PdfDualOracleConsensusError(
                "pdf_dual_oracle_nonaccepted_materialization_forbidden"
            )
        checksum = str(consensus_result.get("canonical_grid_checksum") or "")
        expected_witness_ids = sorted(
            str(item) for item in consensus_result.get(
                "consensus_witness_hypothesis_ids"
            ) or []
        )
        if (
            not checksum
            or consensus_result.get("valid_canonical_grid_checksums") != [checksum]
            or consensus_result.get("consensus_witness_hypothesis_ids")
            != expected_witness_ids
        ):
            raise PdfDualOracleConsensusError(
                "pdf_dual_oracle_consensus_witness_identity_invalid"
            )
        witnesses = sorted(
            (
                item
                for item in _dicts(vlm_hypothesis_set.get("hypotheses"))
                if item.get("canonical_grid_checksum") == checksum
                and str(item.get("hypothesis_id") or "")
                in set(expected_witness_ids)
            ),
            key=lambda item: str(item.get("hypothesis_id") or ""),
        )
        if (
            not witnesses
            or [str(item.get("hypothesis_id") or "") for item in witnesses]
            != expected_witness_ids
        ):
            raise PdfDualOracleConsensusError(
                "pdf_dual_oracle_consensus_witness_missing"
            )
        witness = witnesses[0]
        package_id = str(evidence_package.get("package_id") or "")
        crop_sha256 = str(
            _object(evidence_package.get("crop_identity")).get("crop_sha256")
            or ""
        )
        dictionary_hash = str(
            evidence_package.get("candidate_dictionary_hash") or ""
        )
        private_dictionary = evidence_package.get("private_candidate_dictionary")
        if (
            not isinstance(private_dictionary, dict)
            or not dictionary_hash
            or sha256_json(private_dictionary) != dictionary_hash
            or not _dictionary_matches_parser_observation(
                private_dictionary, parser_observation
            )
        ):
            raise PdfDualOracleConsensusError(
                "pdf_dual_oracle_evidence_dictionary_integrity_invalid"
            )
        construction = _object(parser_observation.get("candidate_construction"))
        if (
            construction.get("kind")
            == "legacy_compact_ledger_candidate_groups"
            and construction.get("source_candidate_dictionary_hash")
            != dictionary_hash
        ):
            raise PdfDualOracleConsensusError(
                "pdf_dual_oracle_evidence_dictionary_lineage_mismatch"
            )
        if "package_hash" in evidence_package:
            package_copy = dict(evidence_package)
            stored_package_hash = package_copy.pop("package_hash", None)
            if stored_package_hash != sha256_json(package_copy):
                raise PdfDualOracleConsensusError(
                    "pdf_dual_oracle_evidence_package_checksum_invalid"
                )
        package_record = next(
            (
                item
                for item in _dicts(_object(witness.get("evidence")).get("packages"))
                if item.get("package_id") == package_id
            ),
            None,
        )
        if (
            package_record is None
            or package_record.get("crop_sha256") != crop_sha256
            or package_record.get("candidate_dictionary_hash") != dictionary_hash
            or set(
                str(item)
                for row in _dicts(witness.get("rows"))
                for cell in row.get("cells") or []
                if isinstance(cell, list)
                for item in cell
            )
            != set(str(item) for item in parser_observation.get("candidate_order") or [])
            or set(private_dictionary)
            != set(
                str(item)
                for item in parser_observation.get("candidate_order") or []
            )
        ):
            raise PdfDualOracleConsensusError(
                "pdf_dual_oracle_evidence_package_identity_mismatch"
            )
        return {
            "schema_version": PDF_HYBRID_BINDING_OUTPUT_SCHEMA,
            "package_id": package_id,
            "crop_sha256": crop_sha256,
            "candidate_dictionary_hash": dictionary_hash,
            "decision": "bound",
            "row_count": witness.get("row_count"),
            "column_count": witness.get("column_count"),
            "header_rows": copy.deepcopy(witness.get("header_rows") or []),
            "header_hierarchy": copy.deepcopy(
                witness.get("header_hierarchy") or []
            ),
            "rows": copy.deepcopy(witness.get("rows") or []),
            "spans": copy.deepcopy(witness.get("spans") or []),
            "uncertainty_codes": [],
        }

    def solve_continuation(
        self,
        *,
        continuation_contract: dict[str, Any],
        fragment_results: list[dict[str, Any]],
        fragment_evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        reasons: list[str] = []
        if not isinstance(continuation_contract, dict):
            continuation_contract = {}
        raw_fragments = continuation_contract.get("fragments")
        if not isinstance(raw_fragments, list):
            raw_fragments = []
            reasons.append("pdf_dual_oracle_continuation_contract_invalid")
        raw_results = fragment_results if isinstance(fragment_results, list) else []
        typed_results = _dicts(raw_results)
        if len(typed_results) != len(raw_results):
            reasons.append("pdf_dual_oracle_continuation_fragment_result_invalid")
        if (
            set(continuation_contract) != _CONTINUATION_CONTRACT_KEYS
            or continuation_contract.get("schema_version")
            != PDF_HYBRID_CONTINUATION_SCHEMA
            or not continuation_contract.get("continuation_group_id")
            or not isinstance(
                continuation_contract.get("shared_column_count"), int
            )
            or isinstance(
                continuation_contract.get("shared_column_count"), bool
            )
            or int(continuation_contract.get("shared_column_count") or 0) < 1
            or continuation_contract.get("fragment_coverage_required") is not True
            or continuation_contract.get("joined_coverage_required") is not True
            or continuation_contract.get("authoritative") is not False
        ):
            reasons.append("pdf_dual_oracle_continuation_contract_invalid")
        fragments = _dicts(raw_fragments)
        if (
            len(fragments) != len(raw_fragments)
            or any(set(item) != _CONTINUATION_FRAGMENT_KEYS for item in fragments)
        ):
            reasons.append("pdf_dual_oracle_continuation_contract_invalid")
        expected_refs = [str(item.get("table_ref") or "") for item in fragments]
        supplied_refs = [str(item.get("table_ref") or "") for item in typed_results]
        if (
            not all(expected_refs)
            or len(expected_refs) != len(set(expected_refs))
            or not all(supplied_refs)
            or len(supplied_refs) != len(set(supplied_refs))
        ):
            reasons.append("pdf_dual_oracle_continuation_fragment_identity_duplicate")
        if set(supplied_refs) != set(expected_refs) or len(supplied_refs) != len(
            expected_refs
        ):
            reasons.append("pdf_dual_oracle_continuation_fragment_set_mismatch")
        result_by_ref = {
            str(item.get("table_ref") or ""): item for item in typed_results
        }
        ordered_results = [
            result_by_ref.get(str(item.get("table_ref") or "")) for item in fragments
        ]
        if len(fragments) != 2:
            reasons.append("pdf_dual_oracle_continuation_contract_invalid")
        if len(fragments) != 2 or any(item is None for item in ordered_results):
            reasons.append("pdf_dual_oracle_continuation_fragment_coverage_incomplete")
        if continuation_contract.get("subtotal_policy") not in {
            "preserve_fragment_subtotals",
            "deduplicate_exact_boundary_subtotal",
        }:
            reasons.append("pdf_dual_oracle_continuation_subtotal_policy_invalid")
        if continuation_contract.get("duplicate_row_policy") not in {
            "forbid",
            "allow_explicit_repeated_header_only",
        }:
            reasons.append("pdf_dual_oracle_continuation_duplicate_policy_invalid")
        if [int(item.get("fragment_order") or 0) for item in fragments] != list(
            range(1, len(fragments) + 1)
        ):
            reasons.append("pdf_dual_oracle_continuation_fragment_order_invalid")
        page_numbers = [int(item.get("page_number") or 0) for item in fragments]
        if page_numbers != sorted(page_numbers) or len(page_numbers) != len(
            set(page_numbers)
        ):
            reasons.append("pdf_dual_oracle_continuation_page_order_invalid")
        for item in fragments:
            if item.get("repeated_header_policy") not in {
                "source_header",
                "no_repeated_header",
            }:
                reasons.append(
                    "pdf_dual_oracle_continuation_header_policy_invalid"
                )
        terminals = [
            str(item.get("terminal_status") or "")
            for item in ordered_results
            if isinstance(item, dict)
        ]
        if any(value != "accepted_unique_consensus" for value in terminals):
            reasons.append("pdf_dual_oracle_continuation_fragment_not_uniquely_accepted")
        for item in ordered_results:
            if not isinstance(item, dict):
                continue
            result_copy = dict(item)
            stored_checksum = result_copy.pop("result_checksum", None)
            if (
                set(item) != _CONSENSUS_RESULT_KEYS
                or item.get("schema_version")
                != PDF_DUAL_ORACLE_CONSENSUS_RESULT_SCHEMA
                or stored_checksum != sha256_json(result_copy)
                or item.get("uniqueness_proven")
                is not (item.get("terminal_status") == "accepted_unique_consensus")
                or item.get("authority_state") != "non_authoritative"
                or item.get("production_gate2_selection_changed") is not False
                or (
                    item.get("terminal_status") == "accepted_unique_consensus"
                    and (
                        item.get("solver_search_complete") is not True
                        or item.get("valid_distinct_grid_count") != 1
                        or not item.get("canonical_grid_checksum")
                        or item.get("reason_codes")
                        or item.get("review_codes")
                    )
                )
            ):
                reasons.append(
                    "pdf_dual_oracle_continuation_fragment_result_invalid"
                )
        columns = [
            int(item.get("column_count") or 0)
            for item in ordered_results
            if isinstance(item, dict)
        ]
        shared_columns = int(continuation_contract.get("shared_column_count") or 0)
        if columns and any(value != shared_columns for value in columns):
            reasons.append("pdf_dual_oracle_continuation_column_model_mismatch")

        raw_evidence = fragment_evidence if isinstance(fragment_evidence, list) else []
        typed_evidence = _dicts(raw_evidence)
        if fragment_evidence is None:
            reasons.append("pdf_dual_oracle_continuation_fragment_evidence_missing")
        elif len(typed_evidence) != len(raw_evidence):
            reasons.append("pdf_dual_oracle_continuation_fragment_evidence_invalid")
        evidence_refs = [str(item.get("table_ref") or "") for item in typed_evidence]
        if len(evidence_refs) != len(set(evidence_refs)):
            reasons.append(
                "pdf_dual_oracle_continuation_fragment_evidence_identity_duplicate"
            )
        evidence_by_ref = {
            str(item.get("table_ref") or ""): item for item in typed_evidence
        }
        ordered_evidence = [
            evidence_by_ref.get(str(item.get("table_ref") or ""))
            for item in fragments
        ]
        if (
            set(evidence_refs) != set(expected_refs)
            or len(evidence_refs) != len(expected_refs)
            or any(item is None for item in ordered_evidence)
        ):
            reasons.append(
                "pdf_dual_oracle_continuation_fragment_evidence_set_mismatch"
            )

        source_rows: list[dict[str, Any]] = []
        joined_rows: list[dict[str, Any]] = []
        deduplicated_boundary_rows: list[dict[str, Any]] = []
        source_candidate_ids: list[str] = []
        joined_candidate_ids: list[str] = []
        repeated_header_policy_passed = True
        subtotal_policy_passed = True
        duplicate_row_policy_passed = True
        seen_fragment_candidates: set[str] = set()
        for contract_fragment, result_item, evidence_item in zip(
            fragments, ordered_results, ordered_evidence
        ):
            if not isinstance(result_item, dict) or not isinstance(evidence_item, dict):
                continue
            evidence_errors = self.contracts.validate_continuation_fragment_evidence(
                evidence_item
            )
            if evidence_errors:
                reasons.extend(evidence_errors)
                reasons.append(
                    "pdf_dual_oracle_continuation_fragment_evidence_invalid"
                )
                continue
            if (
                evidence_item.get("fragment_order")
                != contract_fragment.get("fragment_order")
                or evidence_item.get("page_number")
                != contract_fragment.get("page_number")
                or evidence_item.get("repeated_header_policy")
                != contract_fragment.get("repeated_header_policy")
                or evidence_item.get("consensus_result_checksum")
                != result_item.get("result_checksum")
                or evidence_item.get("canonical_grid_checksum")
                != result_item.get("canonical_grid_checksum")
                or evidence_item.get("row_count") != result_item.get("row_count")
                or evidence_item.get("column_count")
                != result_item.get("column_count")
                or evidence_item.get("column_count") != shared_columns
            ):
                reasons.append(
                    "pdf_dual_oracle_continuation_fragment_evidence_crosslink_invalid"
                )
            header_rows = [int(item) for item in evidence_item.get("header_rows") or []]
            repeated_header_policy = str(
                contract_fragment.get("repeated_header_policy") or ""
            )
            if (
                repeated_header_policy == "source_header"
                and not header_rows
            ) or (
                repeated_header_policy == "no_repeated_header"
                and header_rows
            ):
                repeated_header_policy_passed = False
                reasons.append(
                    "pdf_dual_oracle_continuation_repeated_header_policy_mismatch"
                )
            fragment_candidate_ids = [
                str(item) for item in evidence_item.get("candidate_ids") or []
            ]
            if seen_fragment_candidates & set(fragment_candidate_ids):
                reasons.append(
                    "pdf_dual_oracle_continuation_candidate_identity_reused"
                )
            seen_fragment_candidates.update(fragment_candidate_ids)
            source_candidate_ids.extend(fragment_candidate_ids)
            fragment_rows = [
                {
                    **copy.deepcopy(row),
                    "fragment_order": contract_fragment.get("fragment_order"),
                    "page_number": contract_fragment.get("page_number"),
                    "table_ref": contract_fragment.get("table_ref"),
                }
                for row in _dicts(evidence_item.get("rows"))
            ]
            source_rows.extend(fragment_rows)
            first_row = fragment_rows[0] if fragment_rows else None
            if (
                continuation_contract.get("subtotal_policy")
                == "deduplicate_exact_boundary_subtotal"
                and joined_rows
                and first_row is not None
                and joined_rows[-1].get("row_content_checksum")
                == first_row.get("row_content_checksum")
                and joined_rows[-1].get("row_kind") in {"subtotal", "total"}
                and first_row.get("row_kind") in {"subtotal", "total"}
            ):
                removed_ids = [
                    str(candidate_id)
                    for cell in first_row.get("cells") or []
                    if isinstance(cell, list)
                    for candidate_id in cell
                ]
                deduplicated_boundary_rows.append(
                    {
                        "table_ref": first_row.get("table_ref"),
                        "fragment_order": first_row.get("fragment_order"),
                        "page_number": first_row.get("page_number"),
                        "source_row_ordinal": first_row.get("row_ordinal"),
                        "row_content_checksum": first_row.get(
                            "row_content_checksum"
                        ),
                        "removed_candidate_ids": removed_ids,
                        "kept_table_ref": joined_rows[-1].get("table_ref"),
                        "kept_fragment_order": joined_rows[-1].get(
                            "fragment_order"
                        ),
                        "kept_page_number": joined_rows[-1].get("page_number"),
                        "kept_source_row_ordinal": joined_rows[-1].get(
                            "source_row_ordinal"
                        ),
                        "kept_joined_row_ordinal": joined_rows[-1].get(
                            "row_ordinal"
                        ),
                    }
                )
                fragment_rows = fragment_rows[1:]
            for row in fragment_rows:
                joined = copy.deepcopy(row)
                joined["source_row_ordinal"] = joined.pop("row_ordinal", None)
                joined["row_ordinal"] = len(joined_rows) + 1
                joined_rows.append(joined)
                joined_candidate_ids.extend(
                    str(candidate_id)
                    for cell in joined.get("cells") or []
                    if isinstance(cell, list)
                    for candidate_id in cell
                )

        if continuation_contract.get("subtotal_policy") == "preserve_fragment_subtotals":
            if deduplicated_boundary_rows or len(joined_rows) != len(source_rows):
                subtotal_policy_passed = False
                reasons.append(
                    "pdf_dual_oracle_continuation_subtotal_preservation_invalid"
                )
        elif (
            continuation_contract.get("subtotal_policy")
            == "deduplicate_exact_boundary_subtotal"
            and len(joined_rows) + len(deduplicated_boundary_rows)
            != len(source_rows)
        ):
            subtotal_policy_passed = False
            reasons.append(
                "pdf_dual_oracle_continuation_subtotal_deduplication_invalid"
            )

        rows_by_content: dict[str, list[dict[str, Any]]] = {}
        for row in source_rows:
            rows_by_content.setdefault(
                str(row.get("row_content_checksum") or ""), []
            ).append(row)
        duplicate_groups = [
            group for checksum, group in rows_by_content.items() if checksum and len(group) > 1
        ]
        for group in duplicate_groups:
            allowed_boundary_subtotal = bool(
                continuation_contract.get("subtotal_policy")
                == "deduplicate_exact_boundary_subtotal"
                and any(
                    item.get("row_content_checksum")
                    == group[0].get("row_content_checksum")
                    for item in deduplicated_boundary_rows
                )
                and all(item.get("row_kind") in {"subtotal", "total"} for item in group)
            )
            allowed_header = bool(
                continuation_contract.get("duplicate_row_policy")
                == "allow_explicit_repeated_header_only"
                and all(
                    item.get("row_kind") in {"header", "column_numbers"}
                    for item in group
                )
                and all(
                    next(
                        (
                            fragment.get("repeated_header_policy")
                            for fragment in fragments
                            if fragment.get("table_ref") == item.get("table_ref")
                        ),
                        None,
                    )
                    == "source_header"
                    for item in group
                )
            )
            if continuation_contract.get("duplicate_row_policy") == "forbid":
                allowed_header = False
            if not allowed_boundary_subtotal and not allowed_header:
                duplicate_row_policy_passed = False
                reasons.append(
                    "pdf_dual_oracle_continuation_duplicate_row_policy_violation"
                )

        removed_candidate_ids = {
            str(candidate_id)
            for item in deduplicated_boundary_rows
            for candidate_id in item.get("removed_candidate_ids") or []
        }
        joined_coverage_complete = bool(
            ordered_evidence
            and all(isinstance(item, dict) for item in ordered_evidence)
            and len(source_candidate_ids) == len(set(source_candidate_ids))
            and set(joined_candidate_ids) | removed_candidate_ids
            == set(source_candidate_ids)
            and len(joined_candidate_ids) == len(set(joined_candidate_ids))
            and len(joined_rows) + len(deduplicated_boundary_rows)
            == len(source_rows)
        )
        if not joined_coverage_complete:
            reasons.append("pdf_dual_oracle_continuation_joined_coverage_incomplete")

        ordered_fragment_records = []
        for index, fragment in enumerate(fragments):
            result_item = (
                ordered_results[index]
                if index < len(ordered_results)
                and isinstance(ordered_results[index], dict)
                else {}
            )
            evidence_item = (
                ordered_evidence[index]
                if index < len(ordered_evidence)
                and isinstance(ordered_evidence[index], dict)
                else {}
            )
            ordered_fragment_records.append(
                {
                    "fragment_order": fragment.get("fragment_order"),
                    "page_number": fragment.get("page_number"),
                    "table_ref": fragment.get("table_ref"),
                    "repeated_header_policy": fragment.get(
                        "repeated_header_policy"
                    ),
                    "fragment_result_checksum": result_item.get(
                        "result_checksum"
                    ),
                    "fragment_evidence_checksum": evidence_item.get(
                        "fragment_evidence_checksum"
                    ),
                    "canonical_grid_checksum": evidence_item.get(
                        "canonical_grid_checksum"
                    ),
                    "binding_checksum": evidence_item.get("binding_checksum"),
                }
            )

        if reasons:
            if any(value == "ambiguous_multiple_consensus" for value in terminals):
                terminal = "ambiguous_multiple_consensus"
            elif any(value == "parser_vlm_conflict" for value in terminals):
                terminal = "parser_vlm_conflict"
            elif any(value == "unsupported" for value in terminals):
                terminal = "unsupported"
            elif any(value == "no_valid_consensus" for value in terminals):
                terminal = "no_valid_consensus"
            elif any("contract_invalid" in value for value in reasons):
                terminal = "no_valid_consensus"
            else:
                terminal = "human_review_required"
            canonical_checksum = None
            join_plan_checksum = None
            sealed_joined_rows: list[dict[str, Any]] = []
            sealed_deduplicated_rows: list[dict[str, Any]] = []
        else:
            terminal = "accepted_unique_consensus"
            sealed_joined_rows = copy.deepcopy(joined_rows)
            sealed_deduplicated_rows = copy.deepcopy(deduplicated_boundary_rows)
            canonical_checksum = sha256_json(
                _continuation_canonical_projection(
                    shared_column_count=shared_columns,
                    joined_rows=sealed_joined_rows,
                )
            )
            join_plan_checksum = sha256_json(
                _continuation_join_plan_projection(
                    continuation_group_id=str(
                        continuation_contract.get("continuation_group_id") or ""
                    ),
                    shared_column_count=shared_columns,
                    subtotal_policy=str(
                        continuation_contract.get("subtotal_policy") or ""
                    ),
                    duplicate_row_policy=str(
                        continuation_contract.get("duplicate_row_policy") or ""
                    ),
                    ordered_fragments=ordered_fragment_records,
                    joined_rows=sealed_joined_rows,
                    deduplicated_boundary_rows=sealed_deduplicated_rows,
                )
            )
        result = {
            "schema_version": PDF_DUAL_ORACLE_CONTINUATION_RESULT_SCHEMA,
            "policy_version": self.config.policy_version,
            "continuation_group_id": continuation_contract.get(
                "continuation_group_id"
            ),
            "terminal_status": terminal,
            "reason_codes": sorted(set(reasons)),
            "ordered_table_refs": [item.get("table_ref") for item in fragments],
            "fragment_terminals": terminals,
            "fragment_coverage_complete": not any(
                code
                in {
                    "pdf_dual_oracle_continuation_fragment_identity_duplicate",
                    "pdf_dual_oracle_continuation_fragment_set_mismatch",
                    "pdf_dual_oracle_continuation_fragment_coverage_incomplete",
                }
                for code in reasons
            ),
            "fragment_evidence_complete": not any(
                code
                in {
                    "pdf_dual_oracle_continuation_fragment_evidence_missing",
                    "pdf_dual_oracle_continuation_fragment_evidence_invalid",
                    "pdf_dual_oracle_continuation_fragment_evidence_identity_duplicate",
                    "pdf_dual_oracle_continuation_fragment_evidence_set_mismatch",
                    "pdf_dual_oracle_continuation_fragment_evidence_crosslink_invalid",
                }
                for code in reasons
            ),
            "source_row_count": len(source_rows),
            "joined_row_count": len(sealed_joined_rows),
            "source_candidate_count": len(source_candidate_ids),
            "joined_candidate_count": (
                len(joined_candidate_ids)
                if terminal == "accepted_unique_consensus"
                else 0
            ),
            "deduplicated_boundary_rows": sealed_deduplicated_rows,
            "joined_coverage_complete": (
                joined_coverage_complete
                and terminal == "accepted_unique_consensus"
            ),
            "repeated_header_policy_passed": repeated_header_policy_passed,
            "subtotal_policy_passed": subtotal_policy_passed,
            "duplicate_row_policy_passed": duplicate_row_policy_passed,
            "canonical_joined_grid_checksum": canonical_checksum,
            "all_required_fragments_independently_accepted": (
                terminal == "accepted_unique_consensus"
            ),
            "authority_state": "non_authoritative",
            "production_gate2_selection_changed": False,
            "shared_column_count": shared_columns,
            "subtotal_policy": continuation_contract.get("subtotal_policy"),
            "duplicate_row_policy": continuation_contract.get(
                "duplicate_row_policy"
            ),
            "ordered_fragments": ordered_fragment_records,
            "joined_rows": sealed_joined_rows,
            "join_plan_checksum": join_plan_checksum,
        }
        result["result_checksum"] = sha256_json(result)
        validation_errors = self.validate_continuation_result(result)
        if validation_errors:
            raise PdfDualOracleConsensusError(validation_errors[0])
        return result

    def validate_continuation_result(self, value: Any) -> list[str]:
        """Validate sealed v2 results while retaining closed v1 read support."""

        return _continuation_result_errors(
            value,
            policy_version=self.config.policy_version,
        )

    def _evaluate_hypothesis(
        self,
        *,
        parser_observation: dict[str, Any],
        candidates: dict[str, dict[str, Any]],
        hypothesis: dict[str, Any],
    ) -> dict[str, Any]:
        rows = int(hypothesis.get("row_count") or 0)
        columns = int(hypothesis.get("column_count") or 0)
        grid = _grid(hypothesis)
        candidate_positions: dict[str, tuple[int, int]] = {}
        used: list[str] = []
        for position, ids in grid.items():
            for candidate_id in ids:
                used.append(candidate_id)
                candidate_positions[candidate_id] = position

        constraints: dict[str, dict[str, Any]] = {}
        accounting_errors = []
        if set(used) != set(candidates):
            accounting_errors.append("pdf_dual_oracle_candidate_coverage_incomplete")
        if len(used) != len(set(used)):
            accounting_errors.append("pdf_dual_oracle_candidate_ownership_duplicate")
        constraints["complete_source_and_candidate_accounting"] = _gate(
            accounting_errors,
            {
                "expected_candidates": len(candidates),
                "used_candidates": len(used),
                "unique_used_candidates": len(set(used)),
            },
        )

        expected_positions = {
            (row, column)
            for row in range(1, rows + 1)
            for column in range(1, columns + 1)
        }
        rectangular_errors = []
        if set(grid) != expected_positions or len(grid) != rows * columns:
            rectangular_errors.append("pdf_dual_oracle_empty_rectangular_grid_incomplete")
        constraints["complete_rectangular_grid_and_explicit_empties"] = _gate(
            rectangular_errors,
            {
                "grid_positions": len(grid),
                "expected_grid_positions": rows * columns,
                "explicit_empty_positions": sum(not ids for ids in grid.values()),
            },
        )

        table_bbox = _bbox(
            _object(parser_observation.get("coordinate_space")).get("table_bbox")
        )
        spans = _dicts(hypothesis.get("spans"))
        row_axis = _axis_model(
            axis="row",
            segments=rows,
            table_bbox=table_bbox,
            proposed_geometry=_object(hypothesis.get("proposed_geometry")),
            candidate_positions=candidate_positions,
            candidates=candidates,
            spans=spans,
            tolerance=self.config.coordinate_tolerance_points,
        )
        column_axis = _axis_model(
            axis="column",
            segments=columns,
            table_bbox=table_bbox,
            proposed_geometry=_object(hypothesis.get("proposed_geometry")),
            candidate_positions=candidate_positions,
            candidates=candidates,
            spans=spans,
            tolerance=self.config.coordinate_tolerance_points,
        )
        boundary_errors = [*row_axis["reason_codes"], *column_axis["reason_codes"]]
        constraints["row_bands_and_column_boundaries"] = _gate(
            boundary_errors,
            {
                "row_geometry_source": row_axis["source"],
                "column_geometry_source": column_axis["source"],
                "row_bands": len(row_axis["bands"]),
                "column_bands": len(column_axis["bands"]),
            },
        )

        empty_errors: list[str] = []
        empty_explanations: list[dict[str, Any]] = []
        for (row, column), ids in sorted(grid.items()):
            if ids:
                continue
            covering = _covering_span(spans, row, column)
            if covering is not None and (
                row != int(covering.get("start_row") or 0)
                or column != int(covering.get("start_column") or 0)
            ):
                anchor = (
                    int(covering.get("start_row") or 0),
                    int(covering.get("start_column") or 0),
                )
                anchor_ids = [str(item) for item in grid.get(anchor, [])]
                source_candidate_ids_only = bool(anchor_ids) and set(anchor_ids) <= set(
                    candidates
                )
                if not source_candidate_ids_only:
                    empty_errors.append(
                        "pdf_dual_oracle_empty_merged_span_anchor_invalid"
                    )
                empty_explanations.append(
                    {
                        "row_ordinal": row,
                        "column_ordinal": column,
                        "physical_region_available": True,
                        "parser_candidate_collision": False,
                        "covered_by_declared_span": True,
                        "span_relation": covering.get("relation"),
                        "span_anchor_row": anchor[0],
                        "span_anchor_column": anchor[1],
                        "span_anchor_candidate_ids": anchor_ids,
                        "source_candidate_ids_only": source_candidate_ids_only,
                        "invented_value_count": 0,
                    }
                )
                continue
            row_scope = _scope(row_axis["bands"], row, None, "row")
            column_scope = _scope(column_axis["bands"], column, None, "column")
            collision = False
            if row_scope is None or column_scope is None:
                empty_errors.append(
                    "pdf_dual_oracle_empty_physical_region_unavailable"
                )
            else:
                for candidate_id, candidate_position in candidate_positions.items():
                    bbox = _bbox(candidates.get(candidate_id, {}).get("bbox"))
                    if bbox is None:
                        continue
                    candidate_span = _covering_span(
                        spans, candidate_position[0], candidate_position[1]
                    )
                    if candidate_span is not None and (
                        int(candidate_span.get("start_row") or 0) <= row
                        <= int(candidate_span.get("end_row") or 0)
                        and int(candidate_span.get("start_column") or 0) <= column
                        <= int(candidate_span.get("end_column") or 0)
                    ):
                        continue
                    center_x = (bbox[0] + bbox[2]) / 2
                    center_y = (bbox[1] + bbox[3]) / 2
                    if _inside(center_y, row_scope, 0.0) and _inside(
                        center_x, column_scope, 0.0
                    ):
                        collision = True
                        empty_errors.append(
                            "pdf_dual_oracle_empty_parser_candidate_collision"
                        )
                        break
            empty_explanations.append(
                {
                    "row_ordinal": row,
                    "column_ordinal": column,
                    "physical_region_available": (
                        row_scope is not None and column_scope is not None
                    ),
                    "parser_candidate_collision": collision,
                    "covered_by_declared_span": False,
                    "span_relation": None,
                    "span_anchor_row": None,
                    "span_anchor_column": None,
                    "span_anchor_candidate_ids": [],
                    "source_candidate_ids_only": True,
                    "invented_value_count": 0,
                }
            )
        constraints["explicit_empty_cell_evidence"] = _gate(
            empty_errors,
            {
                "explicit_empty_positions": len(empty_explanations),
                "empty_positions_with_parser_collision": sum(
                    bool(item["parser_candidate_collision"])
                    for item in empty_explanations
                ),
                "empty_positions_covered_by_declared_span": sum(
                    bool(item["covered_by_declared_span"])
                    for item in empty_explanations
                ),
                "invented_value_count": sum(
                    int(item["invented_value_count"])
                    for item in empty_explanations
                ),
                "all_span_covered_empties_use_source_candidate_ids": all(
                    item["source_candidate_ids_only"]
                    for item in empty_explanations
                    if item["covered_by_declared_span"]
                ),
            },
        )

        row_errors: list[str] = []
        column_errors: list[str] = []
        source_order_errors: list[str] = []
        explanations = []
        for candidate_id in sorted(candidates, key=lambda item: int(candidates[item].get("source_order") or 0)):
            candidate = candidates[candidate_id]
            position = candidate_positions.get(candidate_id)
            bbox = _bbox(candidate.get("bbox"))
            if position is None or bbox is None:
                row_passed = False
                column_passed = False
                row_errors.append("pdf_dual_oracle_candidate_position_or_bbox_missing")
                column_errors.append("pdf_dual_oracle_candidate_position_or_bbox_missing")
                row, column = (0, 0)
            else:
                row, column = position
                span = _covering_span(spans, row, column)
                row_scope = _scope(row_axis["bands"], row, span, "row")
                column_scope = _scope(column_axis["bands"], column, span, "column")
                center_x = (bbox[0] + bbox[2]) / 2
                center_y = (bbox[1] + bbox[3]) / 2
                row_passed = _inside(
                    center_y, row_scope, self.config.coordinate_tolerance_points
                )
                column_passed = _inside(
                    center_x, column_scope, self.config.coordinate_tolerance_points
                )
                if not row_passed:
                    row_errors.append("pdf_dual_oracle_candidate_row_incompatible")
                if not column_passed:
                    column_errors.append(
                        "pdf_dual_oracle_candidate_column_incompatible"
                    )
            explanations.append(
                {
                    "candidate_id": candidate_id,
                    "row_ordinal": row,
                    "column_ordinal": column,
                    "candidate_bbox_checksum": sha256_json(candidate.get("bbox")),
                    "row_compatibility_passed": row_passed,
                    "column_compatibility_passed": column_passed,
                    "source_identity_and_provenance_passed": bool(
                        candidate.get("source_value_refs")
                        and candidate.get("word_refs")
                        and candidate.get("candidate_observation_checksum")
                    ),
                    "duplicate_value_group": _duplicate_group_id(
                        parser_observation, candidate_id
                    ),
                }
            )
        for position, ids in grid.items():
            source_orders = [
                int(candidates.get(item, {}).get("source_order") or 0) for item in ids
            ]
            if source_orders != sorted(source_orders):
                source_order_errors.append("pdf_dual_oracle_order_within_cell_invalid")
        constraints["candidate_to_row_compatibility"] = _gate(
            row_errors, {"candidates_checked": len(explanations)}
        )
        constraints["candidate_to_column_compatibility"] = _gate(
            column_errors, {"candidates_checked": len(explanations)}
        )
        order_errors = [
            *source_order_errors,
            *(
                ["pdf_dual_oracle_order_row_bands_interleaved"]
                if row_axis["interleaved"]
                else []
            ),
            *(
                ["pdf_dual_oracle_order_column_bands_interleaved"]
                if column_axis["interleaved"]
                else []
            ),
        ]
        constraints["left_to_right_and_top_to_bottom_order"] = _gate(
            order_errors,
            {
                "row_order_passed": not row_axis["interleaved"],
                "column_order_passed": not column_axis["interleaved"],
            },
        )
        constraints["stable_column_alignment_across_rows"] = _gate(
            (
                ["pdf_dual_oracle_geometry_column_alignment_unstable"]
                if column_axis["interleaved"]
                else []
            ),
            {"columns_checked": columns},
        )

        merged_errors = _merged_errors(
            hypothesis=hypothesis,
            candidates=candidates,
            candidate_positions=candidate_positions,
            column_bands=column_axis["bands"],
            tolerance=self.config.coordinate_tolerance_points,
        )
        constraints["merged_and_hierarchical_headers"] = _gate(
            merged_errors,
            {
                "spans": len(spans),
                "header_relations": len(
                    _dicts(hypothesis.get("header_hierarchy"))
                ),
            },
        )

        provenance_errors = []
        for candidate in candidates.values():
            if not (
                candidate.get("exact_visible_value_checksum")
                and candidate.get("source_value_refs")
                and candidate.get("word_refs")
                and candidate.get("candidate_observation_checksum")
            ):
                provenance_errors.append(
                    "pdf_dual_oracle_candidate_source_provenance_incomplete"
                )
                break
        constraints["exact_source_provenance"] = _gate(
            provenance_errors,
            {
                "candidates_with_provenance": sum(
                    bool(item.get("source_value_refs") and item.get("word_refs"))
                    for item in candidates.values()
                )
            },
        )

        ambiguity_codes = []
        independent_geometry_sources = {
            "vlm_normalized_boundaries",
            "consensus_normalized_boundaries",
        }
        if (
            row_axis["source"] not in independent_geometry_sources
            or column_axis["source"] not in independent_geometry_sources
        ):
            ambiguity_codes.append(
                "pdf_dual_oracle_vlm_geometry_independence_not_proven"
            )
        for group in _dicts(parser_observation.get("duplicate_value_ambiguities")):
            if group.get("coordinates_distinguish_identities") is not True:
                ambiguity_codes.append(
                    "pdf_dual_oracle_duplicate_identity_not_physically_distinguishable"
                )
        constraints["duplicate_value_identity"] = _gate(
            [],
            {
                "duplicate_value_groups": len(
                    _dicts(parser_observation.get("duplicate_value_ambiguities"))
                ),
                "unresolved_identity_groups": len(ambiguity_codes),
            },
        )

        reason_codes = sorted(
            set(
                code
                for value in constraints.values()
                for code in value.get("reason_codes") or []
            )
        )
        return {
            "hypothesis_id": hypothesis.get("hypothesis_id"),
            "decision": hypothesis.get("decision"),
            "row_count": rows,
            "column_count": columns,
            "canonical_grid_checksum": hypothesis.get("canonical_grid_checksum"),
            "hypothesis_checksum": hypothesis.get("hypothesis_checksum"),
            "topology_checksum": hypothesis.get("topology_checksum"),
            "evidence": copy.deepcopy(hypothesis.get("evidence") or {}),
            "accepted_by_constraints": not reason_codes,
            "constraints": constraints,
            "candidate_explanations": explanations,
            "empty_explanations": empty_explanations,
            "reason_codes": reason_codes,
            "ambiguity_codes": sorted(set(ambiguity_codes)),
            "uncertainty_codes": copy.deepcopy(
                hypothesis.get("uncertainty_codes") or []
            ),
            "repair_performed": False,
        }

    def _unsupported_alternative(self, hypothesis: dict[str, Any]) -> dict[str, Any]:
        return {
            "hypothesis_id": hypothesis.get("hypothesis_id"),
            "decision": "unsupported",
            "row_count": int(hypothesis.get("row_count") or 0),
            "column_count": int(hypothesis.get("column_count") or 0),
            "canonical_grid_checksum": hypothesis.get("canonical_grid_checksum"),
            "accepted_by_constraints": False,
            "constraints": {},
            "candidate_explanations": [],
            "empty_explanations": [],
            "reason_codes": ["pdf_dual_oracle_vlm_hypothesis_unsupported"],
            "ambiguity_codes": [],
            "uncertainty_codes": copy.deepcopy(
                hypothesis.get("uncertainty_codes") or []
            ),
            "repair_performed": False,
        }

    def _rejected_evidence_alternative(
        self, rejected_evidence: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "hypothesis_id": rejected_evidence.get("evidence_id"),
            "decision": "rejected_evidence",
            "row_count": 0,
            "column_count": 0,
            "canonical_grid_checksum": None,
            "accepted_by_constraints": False,
            "constraints": {},
            "candidate_explanations": [],
            "empty_explanations": [],
            "reason_codes": copy.deepcopy(
                rejected_evidence.get("reason_codes") or []
            ),
            "ambiguity_codes": [],
            "uncertainty_codes": [],
            "repair_performed": False,
        }

    def _result(
        self,
        *,
        parser_observation: dict[str, Any],
        hypothesis_set: dict[str, Any],
        terminal_status: str,
        alternatives: list[dict[str, Any]],
        valid_checksums: list[str],
        review_codes: list[str],
        global_reason_codes: list[str],
        required_evidence: list[str],
        historical_repeatability: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if terminal_status not in TERMINAL_STATUSES:
            raise PdfDualOracleConsensusError(
                "pdf_dual_oracle_terminal_status_invalid"
            )
        canonical_checksum = valid_checksums[0] if len(valid_checksums) == 1 else None
        witness_ids = sorted(
            str(item.get("hypothesis_id") or "")
            for item in alternatives
            if item.get("accepted_by_constraints")
            and item.get("canonical_grid_checksum") == canonical_checksum
        )
        canonical_alternative = next(
            (
                item
                for item in alternatives
                if item.get("accepted_by_constraints")
                and item.get("canonical_grid_checksum") == canonical_checksum
            ),
            {},
        )
        context = _object(hypothesis_set.get("model_context"))
        construction = _object(parser_observation.get("candidate_construction"))
        solver_search_complete = bool(
            terminal_status
            in {
                "accepted_unique_consensus",
                "ambiguous_multiple_consensus",
                "parser_vlm_conflict",
                "human_review_required",
            }
            and
            context.get("topology_dimensions_independently_observed") is True
            and context.get("alternative_topology_hypotheses_complete") is True
            and context.get("context_guard_attested") is True
            and not _dicts(hypothesis_set.get("rejected_evidence"))
            and all(
                item.get("decision") != "unsupported"
                for item in _dicts(hypothesis_set.get("hypotheses"))
            )
            and construction.get("kind") == "raw_word_atoms"
            and construction.get("semantic_grid_dependency") is False
        )
        result = {
            "schema_version": PDF_DUAL_ORACLE_CONSENSUS_RESULT_SCHEMA,
            "policy_version": self.config.policy_version,
            "solver_version": self.config.policy_version,
            "result_id": "pdfdualconsensus_"
            + stable_digest(
                [
                    parser_observation.get("observation_checksum"),
                    hypothesis_set.get("hypothesis_set_checksum"),
                    terminal_status,
                    valid_checksums,
                    historical_repeatability or {},
                    self.config.policy_version,
                ],
                length=24,
            ),
            "table_ref": parser_observation.get("table_ref"),
            "parser_observation_id": parser_observation.get("observation_id"),
            "parser_observation_checksum": parser_observation.get(
                "observation_checksum"
            ),
            "vlm_hypothesis_set_id": hypothesis_set.get("hypothesis_set_id"),
            "vlm_hypothesis_set_checksum": hypothesis_set.get(
                "hypothesis_set_checksum"
            ),
            "terminal_status": terminal_status,
            "reason_codes": sorted(set(global_reason_codes)),
            "review_codes": sorted(set(review_codes)),
            "canonical_grid_checksum": canonical_checksum,
            "row_count": int(canonical_alternative.get("row_count") or 0),
            "column_count": int(canonical_alternative.get("column_count") or 0),
            "valid_canonical_grid_checksums": valid_checksums,
            "consensus_witness_hypothesis_ids": witness_ids,
            "alternatives_considered": alternatives,
            "alternatives_considered_count": len(alternatives),
            "valid_distinct_grid_count": len(valid_checksums),
            "structurally_unique_within_supplied_evidence": (
                len(valid_checksums) == 1
            ),
            "uniqueness_proven": (
                terminal_status == "accepted_unique_consensus"
                and solver_search_complete
            ),
            "solver_search_complete": solver_search_complete,
            "required_evidence_to_resolve": sorted(set(required_evidence)),
            "historical_repeatability": copy.deepcopy(
                historical_repeatability or {}
            ),
            "historical_conflict_preserved": bool(
                _object(historical_repeatability).get("ever_conflicted")
            ),
            "numeric_score_used": False,
            "majority_vote_used": False,
            "oracle_preference_used": False,
            "reference_answer_used": False,
            "repair_performed": False,
            "authority_state": "non_authoritative",
            "production_gate2_selection_changed": False,
        }
        result["result_checksum"] = sha256_json(result)
        return result


def _continuation_result_errors(
    value: Any,
    *,
    policy_version: str,
) -> list[str]:
    if not isinstance(value, dict):
        return ["pdf_dual_oracle_continuation_result_not_object"]
    result = value
    schema = result.get("schema_version")
    expected_keys = (
        _CONTINUATION_RESULT_V1_KEYS
        if schema == PDF_DUAL_ORACLE_CONTINUATION_RESULT_SCHEMA_V1
        else _CONTINUATION_RESULT_V2_KEYS
        if schema == PDF_DUAL_ORACLE_CONTINUATION_RESULT_SCHEMA
        else set()
    )
    errors: list[str] = []
    if not expected_keys or set(result) != expected_keys:
        errors.append("pdf_dual_oracle_continuation_result_contract_invalid")
    result_copy = dict(result)
    stored_checksum = result_copy.pop("result_checksum", None)
    if not isinstance(stored_checksum, str) or stored_checksum != sha256_json(
        result_copy
    ):
        errors.append("pdf_dual_oracle_continuation_result_checksum_invalid")
    if (
        result.get("policy_version") != policy_version
        or result.get("terminal_status") not in TERMINAL_STATUSES
        or not isinstance(result.get("reason_codes"), list)
        or not all(isinstance(item, str) for item in result.get("reason_codes") or [])
        or result.get("authority_state") != "non_authoritative"
        or result.get("production_gate2_selection_changed") is not False
    ):
        errors.append("pdf_dual_oracle_continuation_result_state_invalid")
    if schema == PDF_DUAL_ORACLE_CONTINUATION_RESULT_SCHEMA_V1:
        return sorted(set(errors))

    ordered_fragments = _dicts(result.get("ordered_fragments"))
    joined_rows = _dicts(result.get("joined_rows"))
    deduplicated_rows = _dicts(result.get("deduplicated_boundary_rows"))
    if (
        not isinstance(result.get("ordered_fragments"), list)
        or len(ordered_fragments) != len(result.get("ordered_fragments") or [])
        or any(
            set(fragment) != _CONTINUATION_RESULT_ORDERED_FRAGMENT_KEYS
            for fragment in ordered_fragments
        )
        or not isinstance(result.get("joined_rows"), list)
        or len(joined_rows) != len(result.get("joined_rows") or [])
        or any(
            set(row) != _CONTINUATION_RESULT_JOINED_ROW_KEYS for row in joined_rows
        )
        or not isinstance(result.get("deduplicated_boundary_rows"), list)
        or len(deduplicated_rows)
        != len(result.get("deduplicated_boundary_rows") or [])
        or any(
            set(row) != _CONTINUATION_RESULT_DEDUPLICATED_ROW_KEYS
            for row in deduplicated_rows
        )
    ):
        errors.append("pdf_dual_oracle_continuation_result_join_contract_invalid")

    accepted = result.get("terminal_status") == "accepted_unique_consensus"
    if not accepted:
        if (
            joined_rows
            or deduplicated_rows
            or result.get("canonical_joined_grid_checksum") is not None
            or result.get("join_plan_checksum") is not None
            or result.get("joined_row_count") != 0
            or result.get("joined_candidate_count") != 0
            or result.get("all_required_fragments_independently_accepted") is not False
        ):
            errors.append("pdf_dual_oracle_continuation_failed_result_not_sealed")
        return sorted(set(errors))

    if (
        len(ordered_fragments) != 2
        or [item.get("fragment_order") for item in ordered_fragments] != [1, 2]
        or not all(
            isinstance(item.get("page_number"), int)
            and not isinstance(item.get("page_number"), bool)
            and item.get("page_number") >= 1
            and isinstance(item.get("table_ref"), str)
            and bool(item.get("table_ref"))
            and item.get("repeated_header_policy")
            in {"source_header", "no_repeated_header"}
            and all(
                isinstance(item.get(key), str) and bool(item.get(key))
                for key in (
                    "fragment_result_checksum",
                    "fragment_evidence_checksum",
                    "canonical_grid_checksum",
                    "binding_checksum",
                )
            )
            for item in ordered_fragments
        )
        or ordered_fragments[0].get("page_number")
        >= ordered_fragments[1].get("page_number")
        or [item.get("table_ref") for item in ordered_fragments]
        != result.get("ordered_table_refs")
        or len(set(result.get("ordered_table_refs") or [])) != 2
        or result.get("fragment_terminals")
        != ["accepted_unique_consensus", "accepted_unique_consensus"]
    ):
        errors.append("pdf_dual_oracle_continuation_result_fragment_plan_invalid")
    columns = result.get("shared_column_count")
    if (
        not isinstance(columns, int)
        or isinstance(columns, bool)
        or columns < 1
        or result.get("subtotal_policy")
        not in {
            "preserve_fragment_subtotals",
            "deduplicate_exact_boundary_subtotal",
        }
        or result.get("duplicate_row_policy")
        not in {"forbid", "allow_explicit_repeated_header_only"}
    ):
        errors.append("pdf_dual_oracle_continuation_result_policy_invalid")
        columns = 0

    joined_candidate_ids: list[str] = []
    for ordinal, row in enumerate(joined_rows, start=1):
        cells = row.get("cells")
        if (
            row.get("row_ordinal") != ordinal
            or row.get("row_kind")
            not in {
                "header",
                "column_numbers",
                "data",
                "section",
                "subtotal",
                "total",
                "unknown",
            }
            or not isinstance(cells, list)
            or len(cells) != columns
            or not all(
                isinstance(cell, list)
                and all(isinstance(candidate_id, str) and candidate_id for candidate_id in cell)
                for cell in cells
            )
            or not isinstance(row.get("row_content_checksum"), str)
            or not row.get("row_content_checksum")
            or row.get("fragment_order") not in {1, 2}
            or not isinstance(row.get("page_number"), int)
            or row.get("page_number") < 1
            or not isinstance(row.get("table_ref"), str)
            or not row.get("table_ref")
            or not isinstance(row.get("source_row_ordinal"), int)
            or row.get("source_row_ordinal") < 1
        ):
            errors.append("pdf_dual_oracle_continuation_result_joined_row_invalid")
            continue
        joined_candidate_ids.extend(
            str(candidate_id) for cell in cells for candidate_id in cell
        )
    removed_candidate_ids: list[str] = []
    for row in deduplicated_rows:
        removed = row.get("removed_candidate_ids")
        if (
            not isinstance(removed, list)
            or not removed
            or not all(isinstance(item, str) and item for item in removed)
            or row.get("fragment_order") not in {1, 2}
            or row.get("kept_fragment_order") not in {1, 2}
            or row.get("fragment_order") <= row.get("kept_fragment_order")
            or row.get("kept_joined_row_ordinal") not in range(
                1, len(joined_rows) + 1
            )
            or joined_rows[row.get("kept_joined_row_ordinal") - 1].get(
                "row_content_checksum"
            )
            != row.get("row_content_checksum")
        ):
            errors.append(
                "pdf_dual_oracle_continuation_result_boundary_dedupe_invalid"
            )
            continue
        removed_candidate_ids.extend(str(item) for item in removed)
    all_candidates = joined_candidate_ids + removed_candidate_ids
    if (
        len(all_candidates) != len(set(all_candidates))
        or result.get("joined_row_count") != len(joined_rows)
        or result.get("joined_candidate_count") != len(joined_candidate_ids)
        or result.get("source_candidate_count") != len(all_candidates)
        or result.get("source_row_count")
        != len(joined_rows) + len(deduplicated_rows)
        or result.get("joined_coverage_complete") is not True
        or result.get("fragment_coverage_complete") is not True
        or result.get("fragment_evidence_complete") is not True
        or result.get("repeated_header_policy_passed") is not True
        or result.get("subtotal_policy_passed") is not True
        or result.get("duplicate_row_policy_passed") is not True
        or result.get("all_required_fragments_independently_accepted") is not True
        or result.get("reason_codes")
    ):
        errors.append("pdf_dual_oracle_continuation_result_coverage_invalid")
    canonical_projection = _continuation_canonical_projection(
        shared_column_count=int(columns or 0),
        joined_rows=joined_rows,
    )
    if result.get("canonical_joined_grid_checksum") != sha256_json(
        canonical_projection
    ):
        errors.append("pdf_dual_oracle_continuation_result_grid_checksum_invalid")
    join_projection = _continuation_join_plan_projection(
        continuation_group_id=str(result.get("continuation_group_id") or ""),
        shared_column_count=int(columns or 0),
        subtotal_policy=str(result.get("subtotal_policy") or ""),
        duplicate_row_policy=str(result.get("duplicate_row_policy") or ""),
        ordered_fragments=ordered_fragments,
        joined_rows=joined_rows,
        deduplicated_boundary_rows=deduplicated_rows,
    )
    if result.get("join_plan_checksum") != sha256_json(join_projection):
        errors.append("pdf_dual_oracle_continuation_join_plan_checksum_invalid")
    return sorted(set(errors))


def _continuation_canonical_projection(
    *,
    shared_column_count: int,
    joined_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "shared_column_count": shared_column_count,
        "joined_rows": copy.deepcopy(joined_rows),
    }


def _continuation_join_plan_projection(
    *,
    continuation_group_id: str,
    shared_column_count: int,
    subtotal_policy: str,
    duplicate_row_policy: str,
    ordered_fragments: list[dict[str, Any]],
    joined_rows: list[dict[str, Any]],
    deduplicated_boundary_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "continuation_group_id": continuation_group_id,
        "shared_column_count": shared_column_count,
        "subtotal_policy": subtotal_policy,
        "duplicate_row_policy": duplicate_row_policy,
        "ordered_fragments": copy.deepcopy(ordered_fragments),
        "joined_rows": copy.deepcopy(joined_rows),
        "deduplicated_boundary_rows": copy.deepcopy(
            deduplicated_boundary_rows
        ),
    }


def _candidate_map(parser_observation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("candidate_id") or ""): item
        for item in _dicts(parser_observation.get("candidates"))
    }


def _dictionary_matches_parser_observation(
    dictionary: dict[str, Any], parser_observation: dict[str, Any]
) -> bool:
    candidate_order = [
        str(item) for item in parser_observation.get("candidate_order") or []
    ]
    candidates = _candidate_map(parser_observation)
    if set(dictionary) != set(candidate_order) or set(candidates) != set(candidate_order):
        return False
    required_source_keys = {
        "candidate_id",
        "exact_source_span",
        "source_value_refs",
        "word_refs",
        "source_bbox",
        "source_bbox_refs",
        "source_text_checksum_refs",
        "source_order",
    }
    optional_source_keys = {
        "private_exact_value_paths",
        "source_cell_ref",
        "source_cell_bbox",
        "expected_row_ordinal",
        "expected_column_ordinal",
        "candidate_checksum",
    }
    for candidate_id in candidate_order:
        source = dictionary.get(candidate_id)
        candidate = candidates.get(candidate_id)
        if not isinstance(source, dict) or not isinstance(candidate, dict):
            return False
        if (
            not required_source_keys <= set(source)
            or set(source) - required_source_keys - optional_source_keys
        ):
            return False
        if (
            source.get("candidate_id") != candidate_id
            or source.get("exact_source_span")
            != candidate.get("exact_visible_value")
            or source.get("source_value_refs")
            != candidate.get("source_value_refs")
            or source.get("word_refs") != candidate.get("word_refs")
            or source.get("source_bbox") != candidate.get("bbox")
            or source.get("source_bbox_refs")
            != candidate.get("source_bbox_refs")
            or source.get("source_text_checksum_refs")
            != candidate.get("source_text_checksum_refs")
            or source.get("source_order") != candidate.get("source_order")
        ):
            return False
        private_paths = source.get("private_exact_value_paths")
        if private_paths is not None and (
            not isinstance(private_paths, list)
            or any(
                not isinstance(item, dict)
                or set(item) != {"kind", "word_ref"}
                or item.get("kind") != "pdf_layout_word_text"
                or item.get("word_ref") not in source.get("word_refs", [])
                for item in private_paths
            )
        ):
            return False
        if (
            ("source_cell_ref" in source and not source.get("source_cell_ref"))
            or (
                "source_cell_bbox" in source
                and _bbox(source.get("source_cell_bbox")) is None
            )
            or any(
                key in source
                and (
                    not isinstance(source.get(key), int)
                    or isinstance(source.get(key), bool)
                    or int(source.get(key) or 0) < 1
                )
                for key in ("expected_row_ordinal", "expected_column_ordinal")
            )
        ):
            return False
        if "candidate_checksum" in source:
            source_copy = dict(source)
            stored_checksum = source_copy.pop("candidate_checksum", None)
            if stored_checksum != sha256_json(source_copy):
                return False
    return True


def _build_repeatability_record(
    *,
    parser_observation: dict[str, Any],
    hypothesis_set: dict[str, Any],
    evaluated_alternatives: list[dict[str, Any]],
    solver_version: str,
) -> dict[str, Any]:
    context = _object(hypothesis_set.get("model_context"))
    evaluated_by_id = {
        str(item.get("hypothesis_id") or ""): item
        for item in evaluated_alternatives
    }
    grouped: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for hypothesis in _dicts(hypothesis_set.get("hypotheses")):
        evidence = _object(hypothesis.get("evidence"))
        attempt_number = evidence.get("attempt_number")
        attempt_id = str(evidence.get("attempt_id") or "")
        group_key = (
            int(attempt_number)
            if isinstance(attempt_number, int) and not isinstance(attempt_number, bool)
            else 0,
            attempt_id,
        )
        evidence_identity = {
            "evidence_revision": evidence.get("evidence_revision"),
            "provider": evidence.get("provider"),
            "model": evidence.get("model"),
            "provider_config_hash": evidence.get("provider_config_hash"),
            "package_ids": copy.deepcopy(evidence.get("package_ids")),
            "packages": copy.deepcopy(evidence.get("packages")),
        }
        evaluated = evaluated_by_id.get(str(hypothesis.get("hypothesis_id") or ""), {})
        alternative_identity = {
            "decision": hypothesis.get("decision"),
            "topology_checksum": hypothesis.get("topology_checksum"),
            "uncertainty_codes": copy.deepcopy(
                hypothesis.get("uncertainty_codes")
            ),
            "binding_output_hash": evidence.get("binding_output_hash"),
            "accepted_by_constraints": evaluated.get("accepted_by_constraints")
            is True,
            "canonical_grid_checksum": (
                evaluated.get("canonical_grid_checksum")
                if evaluated.get("accepted_by_constraints") is True
                else None
            ),
            "reason_codes": copy.deepcopy(evaluated.get("reason_codes") or []),
            "ambiguity_codes": copy.deepcopy(
                evaluated.get("ambiguity_codes") or []
            ),
        }
        grouped.setdefault(group_key, []).append(
            {
                "evidence_identity_checksum": sha256_json(evidence_identity),
                "alternative_identity": alternative_identity,
            }
        )

    history = []
    for (attempt_number, attempt_id), members in grouped.items():
        evidence_identity_checksums = sorted(
            {
                str(item.get("evidence_identity_checksum") or "")
                for item in members
            }
        )
        alternatives = sorted(
            [
                copy.deepcopy(_object(item.get("alternative_identity")))
                for item in members
            ],
            key=sha256_json,
        )
        alternative_identity_checksums = [sha256_json(item) for item in alternatives]
        valid_checksums = sorted(
            {
                str(item.get("canonical_grid_checksum") or "")
                for item in alternatives
                if item.get("accepted_by_constraints") is True
                and item.get("canonical_grid_checksum")
            }
        )
        history.append(
            {
                "attempt_id": attempt_id,
                "attempt_number": attempt_number,
                "evidence_identity_checksum": (
                    evidence_identity_checksums[0]
                    if len(evidence_identity_checksums) == 1
                    else None
                ),
                "evidence_identity_consistent": len(evidence_identity_checksums)
                == 1,
                "alternative_count": len(alternatives),
                "alternative_identities_unique": len(alternative_identity_checksums)
                == len(set(alternative_identity_checksums)),
                "alternative_set_checksum": sha256_json(alternatives),
                "valid_canonical_grid_checksums": valid_checksums,
                "consensus_canonical_grid_checksum": (
                    valid_checksums[0] if len(valid_checksums) == 1 else None
                ),
            }
        )
    history.sort(
        key=lambda item: (
            int(item.get("attempt_number") or 0),
            str(item.get("attempt_id") or ""),
        )
    )
    attempt_ids = [str(item.get("attempt_id") or "") for item in history]
    attempt_numbers = [item.get("attempt_number") for item in history]
    evidence_identities = {
        str(item.get("evidence_identity_checksum") or "") for item in history
    }
    alternative_set_identities = {
        str(item.get("alternative_set_checksum") or "") for item in history
    }
    consensus_checksums = {
        str(item.get("consensus_canonical_grid_checksum") or "")
        for item in history
        if item.get("consensus_canonical_grid_checksum")
    }
    provider_call_count = (
        int(context.get("stitched_oracle_observations") or 0)
        if context.get("execution_mode") == "vertical_atom_windows"
        else int(context.get("provider_calls_replayed") or 0)
        + int(context.get("new_provider_calls") or 0)
    )
    supplied_history_structurally_complete = bool(
        len(history) >= 2
        and all(attempt_ids)
        and len(attempt_ids) == len(set(attempt_ids))
        and all(
            isinstance(item, int) and not isinstance(item, bool) and item > 0
            for item in attempt_numbers
        )
        and attempt_numbers == list(range(1, len(history) + 1))
        and len(evidence_identities) == 1
        and "" not in evidence_identities
        and all(item.get("evidence_identity_consistent") is True for item in history)
        and all(item.get("alternative_identities_unique") is True for item in history)
        and provider_call_count >= len(history)
        and not _dicts(hypothesis_set.get("rejected_evidence"))
    )
    every_attempt_has_unique_consensus = bool(
        history
        and all(
            len(item.get("valid_canonical_grid_checksums") or []) == 1
            for item in history
        )
    )
    ever_conflicted = bool(
        len(alternative_set_identities) > 1 or len(consensus_checksums) > 1
    )
    record = {
        "schema_version": PDF_DUAL_ORACLE_REPEATABILITY_RECORD_SCHEMA,
        "parser_observation_checksum": parser_observation.get(
            "observation_checksum"
        ),
        "vlm_hypothesis_set_checksum": hypothesis_set.get(
            "hypothesis_set_checksum"
        ),
        "provider": context.get("provider"),
        "model": context.get("model"),
        "configuration_hash": context.get("configuration_hash"),
        "crop_manifest_hash": context.get("crop_manifest_hash"),
        "solver_version": solver_version,
        "attempt_history": history,
        "attempt_history_checksum": sha256_json(history),
        "supplied_history_structurally_complete": (
            supplied_history_structurally_complete
        ),
        "attempt_alternative_sets_identical": len(alternative_set_identities) == 1,
        "every_attempt_has_unique_consensus": every_attempt_has_unique_consensus,
        "external_prior_conflict_claimed": False,
        "ever_conflicted": ever_conflicted,
        "passed": bool(
            supplied_history_structurally_complete
            and every_attempt_has_unique_consensus
            and len(consensus_checksums) == 1
            and not ever_conflicted
        ),
    }
    record["record_checksum"] = sha256_json(record)
    return record


def _repeatability_passed(
    *,
    parser_observation: dict[str, Any],
    hypothesis_set: dict[str, Any],
    evaluated_alternatives: list[dict[str, Any]],
    record: dict[str, Any],
    solver_version: str,
) -> bool:
    expected = _build_repeatability_record(
        parser_observation=parser_observation,
        hypothesis_set=hypothesis_set,
        evaluated_alternatives=evaluated_alternatives,
        solver_version=solver_version,
    )
    if record != expected or expected.get("passed") is not True:
        return False
    valid_checksums = {
        str(item.get("canonical_grid_checksum") or "")
        for item in evaluated_alternatives
        if item.get("accepted_by_constraints") is True
    }
    repeated_checksums = {
        str(item.get("consensus_canonical_grid_checksum") or "")
        for item in expected.get("attempt_history") or []
    }
    return valid_checksums == repeated_checksums and "" not in repeated_checksums


def _grid(hypothesis: dict[str, Any]) -> dict[tuple[int, int], list[str]]:
    return {
        (int(row.get("row_ordinal") or 0), column): [
            str(item) for item in cell
        ]
        for row in _dicts(hypothesis.get("rows"))
        for column, cell in enumerate(row.get("cells") or [], start=1)
        if isinstance(cell, list)
    }


def _axis_model(
    *,
    axis: str,
    segments: int,
    table_bbox: list[float] | None,
    proposed_geometry: dict[str, Any],
    candidate_positions: dict[str, tuple[int, int]],
    candidates: dict[str, dict[str, Any]],
    spans: list[dict[str, Any]],
    tolerance: float,
) -> dict[str, Any]:
    if table_bbox is None or segments < 1:
        return {
            "source": "unavailable",
            "bands": [],
            "interleaved": True,
            "reason_codes": ["pdf_dual_oracle_geometry_table_scope_invalid"],
        }
    geometry_key = "rows" if axis == "row" else "columns"
    geometry = _object(proposed_geometry.get(geometry_key))
    geometry_kind = geometry.get("kind")
    if geometry_kind in {
        "normalized_boundaries",
        "consensus_normalized_boundaries",
    }:
        geometry_source = (
            "consensus_normalized_boundaries"
            if geometry_kind == "consensus_normalized_boundaries"
            else "vlm_normalized_boundaries"
        )
        boundaries = [float(item) for item in geometry.get("boundaries") or []]
        if len(boundaries) != segments + 1:
            return {
                "source": geometry_source,
                "bands": [],
                "interleaved": True,
                "reason_codes": [
                    f"pdf_dual_oracle_geometry_{axis}_boundary_count_invalid"
                ],
            }
        start = table_bbox[1] if axis == "row" else table_bbox[0]
        length = (
            table_bbox[3] - table_bbox[1]
            if axis == "row"
            else table_bbox[2] - table_bbox[0]
        )
        bands = [
            [start + length * boundaries[index], start + length * boundaries[index + 1]]
            for index in range(segments)
        ]
        return {
            "source": geometry_source,
            "bands": bands,
            "interleaved": False,
            "reason_codes": [],
        }

    centers_by_segment: dict[int, list[float]] = {
        value: [] for value in range(1, segments + 1)
    }
    fallback_by_segment: dict[int, list[float]] = {
        value: [] for value in range(1, segments + 1)
    }
    for candidate_id, position in candidate_positions.items():
        candidate = candidates.get(candidate_id, {})
        bbox = _bbox(candidate.get("bbox"))
        if bbox is None:
            continue
        row, column = position
        segment = row if axis == "row" else column
        center = (bbox[1] + bbox[3]) / 2 if axis == "row" else (bbox[0] + bbox[2]) / 2
        fallback_by_segment.setdefault(segment, []).append(center)
        span = _covering_span(spans, row, column)
        spans_axis = bool(
            span
            and (
                int(span.get("end_row") or 0) > int(span.get("start_row") or 0)
                if axis == "row"
                else int(span.get("end_column") or 0)
                > int(span.get("start_column") or 0)
            )
        )
        if not spans_axis:
            centers_by_segment.setdefault(segment, []).append(center)
    for segment in range(1, segments + 1):
        if not centers_by_segment[segment]:
            centers_by_segment[segment] = fallback_by_segment[segment]
    missing = [segment for segment, values in centers_by_segment.items() if not values]
    if missing:
        return {
            "source": "joint_candidate_geometry",
            "bands": [],
            "interleaved": True,
            "reason_codes": [
                f"pdf_dual_oracle_geometry_{axis}_segment_unobserved"
            ],
        }
    anchors = [median(centers_by_segment[index]) for index in range(1, segments + 1)]
    interleaved = False
    for index in range(1, segments):
        left = centers_by_segment[index]
        right = centers_by_segment[index + 1]
        if max(left) > min(right) + tolerance or anchors[index - 1] >= anchors[index]:
            interleaved = True
            break
    start = table_bbox[1] if axis == "row" else table_bbox[0]
    end = table_bbox[3] if axis == "row" else table_bbox[2]
    boundaries = [start]
    boundaries.extend(
        (anchors[index] + anchors[index + 1]) / 2
        for index in range(len(anchors) - 1)
    )
    boundaries.append(end)
    bands = [
        [boundaries[index], boundaries[index + 1]] for index in range(segments)
    ]
    return {
        "source": "joint_candidate_geometry",
        "bands": bands,
        "interleaved": interleaved,
        "reason_codes": (
            [f"pdf_dual_oracle_geometry_{axis}_segments_interleaved"]
            if interleaved
            else []
        ),
    }


def _merged_errors(
    *,
    hypothesis: dict[str, Any],
    candidates: dict[str, dict[str, Any]],
    candidate_positions: dict[str, tuple[int, int]],
    column_bands: list[list[float]],
    tolerance: float,
) -> list[str]:
    if not column_bands:
        return ["pdf_dual_oracle_merged_column_geometry_unavailable"]
    errors: list[str] = []
    spans = _dicts(hypothesis.get("spans"))
    headers = set(int(item) for item in hypothesis.get("header_rows") or [])
    for candidate_id, position in candidate_positions.items():
        row, _ = position
        if row not in headers:
            continue
        bbox = _bbox(candidates.get(candidate_id, {}).get("bbox"))
        if bbox is None:
            continue
        overlapped = [
            index
            for index, band in enumerate(column_bands, start=1)
            if min(bbox[2], band[1]) - max(bbox[0], band[0]) > tolerance
        ]
        if len(overlapped) > 1 and not any(
            int(span.get("start_row") or 0) <= row <= int(span.get("end_row") or 0)
            and int(span.get("start_column") or 0) <= min(overlapped)
            and int(span.get("end_column") or 0) >= max(overlapped)
            for span in spans
        ):
            errors.append("pdf_dual_oracle_merged_header_relation_missing")
    return errors


def _covering_span(
    spans: list[dict[str, Any]], row: int, column: int
) -> dict[str, Any] | None:
    return next(
        (
            span
            for span in spans
            if int(span.get("start_row") or 0) <= row <= int(span.get("end_row") or 0)
            and int(span.get("start_column") or 0)
            <= column
            <= int(span.get("end_column") or 0)
        ),
        None,
    )


def _scope(
    bands: list[list[float]],
    ordinal: int,
    span: dict[str, Any] | None,
    axis: str,
) -> list[float] | None:
    if not bands or ordinal < 1 or ordinal > len(bands):
        return None
    if span is None:
        return bands[ordinal - 1]
    start = int(span.get("start_row" if axis == "row" else "start_column") or ordinal)
    end = int(span.get("end_row" if axis == "row" else "end_column") or ordinal)
    if start < 1 or end > len(bands):
        return None
    return [bands[start - 1][0], bands[end - 1][1]]


def _inside(value: float, scope: list[float] | None, tolerance: float) -> bool:
    return bool(
        scope is not None and scope[0] - tolerance <= value <= scope[1] + tolerance
    )


def _duplicate_group_id(
    parser_observation: dict[str, Any], candidate_id: str
) -> str | None:
    for group in _dicts(parser_observation.get("duplicate_value_ambiguities")):
        if candidate_id in [str(item) for item in group.get("candidate_ids") or []]:
            return str(group.get("exact_visible_value_checksum") or "")
    return None


def _gate(errors: list[str], metrics: dict[str, Any]) -> dict[str, Any]:
    reason_codes = sorted(set(errors))
    return {
        "passed": not reason_codes,
        "reason_codes": reason_codes,
        "metrics": metrics,
    }


def _required_evidence(codes: list[str]) -> list[str]:
    required = []
    joined = " ".join(codes)
    if "parser_candidate_grouping" in joined:
        required.append("raw_word_atom_parser_observation_without_cell_grid_lineage")
    if "independence" in joined or "alternative_set" in joined:
        required.append("bounded_independent_vlm_topology_with_explicit_alternatives")
    if "context_guard" in joined:
        required.append("sealed_bounded_context_and_exact_provider_accounting_manifest")
    if "evidence_rejected" in joined or "package_lineage" in joined:
        required.append("complete_valid_vlm_evidence_package_lineage")
    if "repeat" in joined or "historical" in joined:
        required.append("same_evidence_repeat_without_erasing_conflict_history")
    if "continuation" in joined:
        required.append("all_required_continuation_fragments_with_shared_column_model")
    if "merged" in joined or "header" in joined:
        required.append("explicit_merged_header_and_hierarchy_hypothesis")
    if "geometry" in joined or "candidate" in joined or "empty" in joined or "order" in joined:
        required.append("disambiguating_candidate_placement_or_normalized_geometry")
    if not required:
        required.append("new_bounded_evidence_or_human_signed_topology")
    return required


def _bbox(value: Any) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    result = [float(item) for item in value]
    if result[2] <= result[0] or result[3] <= result[1]:
        return None
    return result


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return (
        [item for item in value if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )
