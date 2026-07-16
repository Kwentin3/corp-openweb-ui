from __future__ import annotations

import copy
import math
from dataclasses import asdict, dataclass
from typing import Any

from .contracts import stable_digest
from .pdf_dual_oracle_contracts import PdfDualOracleContractFactory
from .pdf_hybrid_contracts import (
    PDF_HYBRID_BINDING_OUTPUT_SCHEMA,
    sha256_json,
    validate_binding_output_shape,
)
from .pdf_parser_geometry import (
    PdfParserGeometryFactory,
    PdfParserGeometryRuntime,
)
from .pdf_visual_topology import (
    PdfVisualTopologyFactory,
    PdfVisualTopologyRuntime,
)


PDF_TOPOLOGY_ASSEMBLY_RESULT_SCHEMA = (
    "broker_reports_pdf_topology_assembly_result_v6"
)
PDF_TOPOLOGY_ASSEMBLY_POLICY_VERSION = "pdf_topology_assembly_policy_v6"
PDF_TOPOLOGY_SAFE_BOUNDARY_RECONCILIATION_OPERATIONS = frozenset(
    {
        "replace_visual_boundary_with_parser_geometry",
        "replace_visual_boundary_with_unique_source_atom_gap",
    }
)

FACTORY_REQUIRED = (
    "PdfTopologyAssemblyFactory.create is the only visual-topology to raw-atom "
    "binding entrypoint"
)
FORBIDDEN = (
    "The assembler must not read legacy cells or dimensions, invent or change "
    "values, use nearest-cell fallback, or hide structural adjustments"
)

_FACTORY_TOKEN = object()
_RESULT_KEYS = {
    "schema_version",
    "policy_version",
    "policy_configuration_hash",
    "result_id",
    "package_id",
    "package_hash",
    "parser_observation_checksum",
    "parser_geometry_observation_checksum",
    "topology_response_checksum",
    "reconstruction_status",
    "certification_status",
    "alternatives_complete",
    "binding_hypotheses",
    "rejected_evidence",
    "geometry_evidence",
    "regional_issues",
    "structural_adjustments",
    "source_accounting",
    "value_mutation_performed",
    "nearest_cell_fallback_used",
    "legacy_grid_consumed",
    "result_checksum",
}
_GEOMETRY_EVIDENCE_STATUSES = {
    "confirmed",
    "contradicted",
    "insufficient_evidence",
    "not_applicable",
}
_GEOMETRY_EVIDENCE_KEYS = {
    "hypothesis_id",
    "row_boundaries",
    "column_boundaries",
    "candidate_separators",
    "span_separators",
}
_GEOMETRY_EVIDENCE_ITEM_KEYS = {
    "status",
    "observed_count",
    "required_count",
    "reason_codes",
}
_STRUCTURAL_ADJUSTMENT_BASE_KEYS = {
    "hypothesis_id",
    "operation",
    "axis",
    "boundary_index",
    "before",
    "after",
    "delta",
    "row_or_column_count_changed",
    "candidate_assignment_change_allowed",
    "source_value_change_allowed",
}
_PARSER_GEOMETRY_ADJUSTMENT_KEYS = _STRUCTURAL_ADJUSTMENT_BASE_KEYS | {
    "parser_geometry_coverage"
}
_SOURCE_GAP_ADJUSTMENT_KEYS = _STRUCTURAL_ADJUSTMENT_BASE_KEYS | {
    "evidence_basis",
    "source_atom_gap",
    "crossing_candidate_ids",
    "candidate_assignment_preserved",
}
_SPAN_ADJUSTMENT_KEYS = _STRUCTURAL_ADJUSTMENT_BASE_KEYS | {
    "parser_separator_boundaries"
}
_SPAN_ADJUSTMENT_OPERATIONS = {
    "drop_degenerate_single_cell_span",
    "drop_span_reduced_to_single_cell_by_parser_separator",
    "trim_span_to_parser_separator",
    "project_geometry_certified_empty_span_to_explicit_empty_cells",
}
_HEADER_ADJUSTMENT_OPERATIONS = {
    "drop_redundant_identity_header_relation",
    "drop_header_relation_with_contradicted_span",
}


class PdfTopologyAssemblyError(ValueError):
    def __init__(self, code: str, subject: str = "") -> None:
        self.code = code
        self.subject = subject
        super().__init__(code if not subject else f"{code}:{subject}")


@dataclass(frozen=True)
class PdfTopologyAssemblyConfig:
    policy_version: str = PDF_TOPOLOGY_ASSEMBLY_POLICY_VERSION
    boundary_epsilon: float = 1e-9
    geometry_cluster_tolerance_normalized: float = 0.003
    minimum_geometry_boundary_coverage_normalized: float = 0.35
    minimum_span_separator_coverage_ratio: float = 0.80
    maximum_span_gap_coverage_ratio: float = 0.10
    atom_band_tolerance_normalized: float = 0.002
    maximum_grid_positions: int = 4096


class PdfTopologyAssemblyFactory:
    def __init__(
        self,
        config: PdfTopologyAssemblyConfig | None = None,
        *,
        visual_topology: PdfVisualTopologyRuntime | None = None,
        parser_geometry: PdfParserGeometryRuntime | None = None,
    ) -> None:
        self.config = config or PdfTopologyAssemblyConfig()
        self.visual_topology = visual_topology
        self.parser_geometry = parser_geometry

    def create(self) -> "PdfTopologyAssemblyRuntime":
        if self.config.policy_version != PDF_TOPOLOGY_ASSEMBLY_POLICY_VERSION:
            raise PdfTopologyAssemblyError("pdf_topology_assembly_policy_invalid")
        if (
            self.config.boundary_epsilon < 0
            or self.config.geometry_cluster_tolerance_normalized <= 0
            or not 0
            < self.config.minimum_geometry_boundary_coverage_normalized
            <= 1
            or not 0 < self.config.minimum_span_separator_coverage_ratio <= 1
            or not 0
            <= self.config.maximum_span_gap_coverage_ratio
            < self.config.minimum_span_separator_coverage_ratio
            or self.config.atom_band_tolerance_normalized < 0
            or self.config.maximum_grid_positions < 1
        ):
            raise PdfTopologyAssemblyError("pdf_topology_assembly_config_invalid")
        return PdfTopologyAssemblyRuntime(
            self.config,
            visual_topology=self.visual_topology
            or PdfVisualTopologyFactory().create(),
            parser_geometry=self.parser_geometry
            or PdfParserGeometryFactory().create(),
            _factory_token=_FACTORY_TOKEN,
        )


class PdfTopologyAssemblyRuntime:
    def __init__(
        self,
        config: PdfTopologyAssemblyConfig,
        *,
        visual_topology: PdfVisualTopologyRuntime,
        parser_geometry: PdfParserGeometryRuntime,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise PdfTopologyAssemblyError("pdf_topology_assembly_factory_required")
        self.config = config
        self.visual_topology = visual_topology
        self.parser_geometry = parser_geometry
        self.contracts = PdfDualOracleContractFactory().create()

    def assemble(
        self,
        *,
        parser_observation: dict[str, Any],
        parser_geometry_observation: dict[str, Any],
        visual_package: dict[str, Any],
        topology_response: dict[str, Any],
        attempt_evidence: dict[str, Any],
        hypothesis_id_prefix: str,
    ) -> dict[str, Any]:
        parser_errors = self.contracts.validate_parser_observation(
            parser_observation
        )
        package_errors = self.visual_topology.validate_package(
            parser_observation=parser_observation,
            package=visual_package,
        )
        geometry_errors = self.parser_geometry.validate_observation(
            parser_geometry_observation
        )
        if parser_errors:
            raise PdfTopologyAssemblyError(parser_errors[0])
        if package_errors:
            raise PdfTopologyAssemblyError(package_errors[0])
        if geometry_errors:
            raise PdfTopologyAssemblyError(geometry_errors[0])
        if not self._same_parser_scope(
            parser_observation=parser_observation,
            parser_geometry_observation=parser_geometry_observation,
        ):
            raise PdfTopologyAssemblyError(
                "pdf_topology_assembly_parser_geometry_scope_mismatch"
            )
        self._validate_attempt_evidence(attempt_evidence)
        if not hypothesis_id_prefix:
            raise PdfTopologyAssemblyError(
                "pdf_topology_assembly_hypothesis_prefix_invalid"
            )
        raw_response_checksum = sha256_json(topology_response)
        normalized_response, normalization_events = self._normalize_response(
            topology_response,
            parser_geometry_observation=parser_geometry_observation,
        )
        response = self.visual_topology.parse_response(
            normalized_response,
            expected_package_id=str(visual_package.get("package_id") or ""),
        )

        bindings: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        all_issues: list[dict[str, Any]] = []
        all_adjustments: list[dict[str, Any]] = []
        geometry_evidence: list[dict[str, Any]] = []
        alternative_accounting: list[dict[str, Any]] = []
        package_evidence = {
            "package_id": visual_package.get("package_id"),
            "crop_sha256": _object(visual_package.get("crop_identity")).get(
                "crop_sha256"
            ),
            "candidate_dictionary_hash": visual_package.get(
                "candidate_dictionary_hash"
            ),
        }

        for index, hypothesis in enumerate(response.get("hypotheses") or []):
            hypothesis_key = str(hypothesis.get("hypothesis_key") or "")
            hypothesis_id = (
                f"{hypothesis_id_prefix}_{index + 1}_{hypothesis_key}"
            )
            bound = self._bind_hypothesis(
                parser_observation=parser_observation,
                parser_geometry_observation=parser_geometry_observation,
                visual_package=visual_package,
                hypothesis=hypothesis,
                hypothesis_id=hypothesis_id,
            )
            pre_adjustments = [
                {
                    "hypothesis_id": hypothesis_id,
                    "operation": event["operation"],
                    "axis": "span",
                    "boundary_index": None,
                    "before": copy.deepcopy(event["before"]),
                    "after": copy.deepcopy(event["after"]),
                    "delta": None,
                    "row_or_column_count_changed": False,
                    "candidate_assignment_change_allowed": event[
                        "candidate_assignment_change_allowed"
                    ],
                    "source_value_change_allowed": False,
                    "parser_separator_boundaries": copy.deepcopy(
                        event["parser_separator_boundaries"]
                    ),
                }
                for event in normalization_events.get(index, [])
            ]
            bound["structural_adjustments"] = [
                *pre_adjustments,
                *bound["structural_adjustments"],
            ]
            bound["accounting"]["structural_adjustments"] += len(
                pre_adjustments
            )
            pre_separator_conflicts = sum(
                len(item.get("parser_separator_boundaries") or [])
                for item in pre_adjustments
            )
            if pre_separator_conflicts:
                bound["geometry_evidence"]["span_separators"] = (
                    _geometry_evidence_item(
                        status="contradicted",
                        observed_count=pre_separator_conflicts,
                        required_count=0,
                        reason_codes=[
                            "pdf_topology_assembly_span_crosses_parser_separator"
                        ],
                    )
                )
            all_issues.extend(bound["regional_issues"])
            all_adjustments.extend(bound["structural_adjustments"])
            geometry_evidence.append(bound["geometry_evidence"])
            alternative_accounting.append(bound["accounting"])
            if bound["binding_output"] is None:
                reason_codes = sorted(
                    {
                        str(item.get("reason_code") or "")
                        for item in bound["regional_issues"]
                        if item.get("reason_code")
                    }
                ) or ["pdf_topology_assembly_binding_failed"]
                rejected.append(
                    {
                        "evidence_id": hypothesis_id,
                        "reason_codes": reason_codes,
                    }
                )
                continue
            bindings.append(
                {
                    "hypothesis_id": hypothesis_id,
                    "binding_output": bound["binding_output"],
                    "proposed_geometry": bound["proposed_geometry"],
                    "evidence": {
                        "attempt_id": attempt_evidence["attempt_id"],
                        "attempt_number": attempt_evidence["attempt_number"],
                        "evidence_revision": attempt_evidence[
                            "evidence_revision"
                        ],
                        "provider": attempt_evidence["provider"],
                        "model": attempt_evidence["model"],
                        "provider_config_hash": attempt_evidence[
                            "provider_config_hash"
                        ],
                        "packages": [package_evidence],
                    },
                    "continuation": {
                        "required": False,
                        "continuation_group_id": None,
                        "fragment_order": 0,
                        "fragment_count": 0,
                        "shared_column_count": 0,
                        "repeated_header_policy": None,
                    },
                }
            )

        top_uncertainty = [
            str(item) for item in response.get("uncertainty_codes") or []
        ]
        hypothesis_uncertainty = [
            str(item)
            for item in response.get("hypotheses") or []
            for item in item.get("uncertainty_codes") or []
        ]
        if response.get("decision") == "unsupported":
            status = "unsupported"
            all_issues.extend(
                {
                    "hypothesis_id": None,
                    "axis": "table",
                    "boundary_index": None,
                    "reason_code": code,
                    "retry_scope": "full_table_crop",
                }
                for code in top_uncertainty
            )
        elif rejected or top_uncertainty or hypothesis_uncertainty:
            status = "regional_retry_required"
        elif bindings:
            status = "assembled"
        else:
            status = "regional_retry_required"

        candidate_count = len(
            parser_observation.get("candidate_order") or []
        )
        source_accounting = {
            "expected_candidates": candidate_count,
            "alternatives_received": len(response.get("hypotheses") or []),
            "alternatives_bound": len(bindings),
            "alternatives_rejected": len(rejected),
            "all_bound_alternatives_exactly_once": bool(
                bindings
                and all(
                    item.get("expected_candidates") == candidate_count
                    and item.get("used_candidates") == candidate_count
                    and item.get("unique_used_candidates") == candidate_count
                    and not item.get("omitted_candidate_ids")
                    and not item.get("extra_candidate_ids")
                    and not item.get("duplicate_candidate_ids")
                    for item in alternative_accounting
                    if item.get("binding_created") is True
                )
            ),
            "alternative_accounting": alternative_accounting,
        }
        result = {
            "schema_version": PDF_TOPOLOGY_ASSEMBLY_RESULT_SCHEMA,
            "policy_version": self.config.policy_version,
            "policy_configuration_hash": sha256_json(asdict(self.config)),
            "result_id": "pdftopoassembly_"
            + stable_digest(
                [
                    visual_package.get("package_hash"),
                    parser_geometry_observation.get("observation_checksum"),
                    raw_response_checksum,
                    attempt_evidence.get("attempt_id"),
                    self.config.policy_version,
                ],
                length=24,
            ),
            "package_id": visual_package.get("package_id"),
            "package_hash": visual_package.get("package_hash"),
            "parser_observation_checksum": parser_observation.get(
                "observation_checksum"
            ),
            "parser_geometry_observation_checksum": parser_geometry_observation.get(
                "observation_checksum"
            ),
            "topology_response_checksum": raw_response_checksum,
            "reconstruction_status": status,
            "certification_status": "not_evaluated",
            "alternatives_complete": response.get("alternatives_complete") is True,
            "binding_hypotheses": bindings,
            "rejected_evidence": rejected,
            "geometry_evidence": geometry_evidence,
            "regional_issues": sorted(
                all_issues,
                key=lambda item: (
                    str(item.get("hypothesis_id") or ""),
                    str(item.get("axis") or ""),
                    int(item.get("boundary_index") or 0),
                    str(item.get("reason_code") or ""),
                ),
            ),
            "structural_adjustments": sorted(
                all_adjustments,
                key=lambda item: (
                    str(item.get("hypothesis_id") or ""),
                    str(item.get("axis") or ""),
                    int(item.get("boundary_index") or 0),
                ),
            ),
            "source_accounting": source_accounting,
            "value_mutation_performed": False,
            "nearest_cell_fallback_used": False,
            "legacy_grid_consumed": False,
        }
        result["result_checksum"] = sha256_json(result)
        validation_errors = self.validate_result(result)
        if validation_errors:
            raise PdfTopologyAssemblyError(validation_errors[0])
        return result

    def validate_result(self, value: Any) -> list[str]:
        data = _object(value)
        errors: list[str] = []
        if set(data) != _RESULT_KEYS:
            errors.append("pdf_topology_assembly_result_keys_invalid")
        if data.get("schema_version") != PDF_TOPOLOGY_ASSEMBLY_RESULT_SCHEMA:
            errors.append("pdf_topology_assembly_result_schema_invalid")
        if data.get("policy_version") != self.config.policy_version:
            errors.append("pdf_topology_assembly_result_policy_invalid")
        if data.get("policy_configuration_hash") != sha256_json(
            asdict(self.config)
        ):
            errors.append("pdf_topology_assembly_result_config_invalid")
        if data.get("reconstruction_status") not in {
            "assembled",
            "regional_retry_required",
            "unsupported",
        }:
            errors.append("pdf_topology_assembly_status_invalid")
        if data.get("certification_status") != "not_evaluated":
            errors.append("pdf_topology_assembly_certification_boundary_invalid")
        if (
            data.get("value_mutation_performed") is not False
            or data.get("nearest_cell_fallback_used") is not False
            or data.get("legacy_grid_consumed") is not False
        ):
            errors.append("pdf_topology_assembly_authority_boundary_invalid")
        for item in _dicts(data.get("binding_hypotheses")):
            binding_errors = validate_binding_output_shape(
                _object(item.get("binding_output"))
            )
            if binding_errors:
                errors.append(binding_errors[0])
        evidence_value = data.get("geometry_evidence")
        evidence = _dicts(evidence_value)
        if (
            not isinstance(evidence_value, list)
            or len(evidence) != len(evidence_value)
            or any(set(item) != _GEOMETRY_EVIDENCE_KEYS for item in evidence)
        ):
            errors.append("pdf_topology_assembly_geometry_evidence_invalid")
        expected_evidence_ids = {
            str(item.get("hypothesis_id") or "")
            for item in _dicts(data.get("binding_hypotheses"))
        } | {
            str(item.get("evidence_id") or "")
            for item in _dicts(data.get("rejected_evidence"))
        }
        observed_evidence_ids = [
            str(item.get("hypothesis_id") or "") for item in evidence
        ]
        if (
            set(observed_evidence_ids) != expected_evidence_ids
            or len(set(observed_evidence_ids)) != len(observed_evidence_ids)
        ):
            errors.append("pdf_topology_assembly_geometry_evidence_invalid")
        for item in evidence:
            if not isinstance(item.get("hypothesis_id"), str) or not item.get(
                "hypothesis_id"
            ):
                errors.append("pdf_topology_assembly_geometry_evidence_invalid")
            for subject in (
                "row_boundaries",
                "column_boundaries",
                "candidate_separators",
                "span_separators",
            ):
                observation = _object(item.get(subject))
                status = observation.get("status")
                reason_codes = observation.get("reason_codes")
                if (
                    set(observation) != _GEOMETRY_EVIDENCE_ITEM_KEYS
                    or status not in _GEOMETRY_EVIDENCE_STATUSES
                    or not _nonnegative_integer(observation.get("observed_count"))
                    or not _nonnegative_integer(observation.get("required_count"))
                    or not _reason_codes(reason_codes)
                    or status in {"confirmed", "not_applicable"}
                    and bool(reason_codes)
                    or status in {"contradicted", "insufficient_evidence"}
                    and not reason_codes
                ):
                    errors.append(
                        "pdf_topology_assembly_geometry_evidence_invalid"
                    )
        structural_adjustments_valid = _structural_adjustments_valid(
            data.get("structural_adjustments"),
            expected_hypothesis_ids=expected_evidence_ids,
        )
        if not structural_adjustments_valid or not (
            _structural_adjustments_consistent(
                adjustments=data.get("structural_adjustments"),
                source_accounting=data.get("source_accounting"),
                binding_hypotheses=data.get("binding_hypotheses"),
                expected_hypothesis_ids=expected_evidence_ids,
            )
        ):
            errors.append(
                "pdf_topology_assembly_structural_adjustment_invalid"
            )
        unsigned = dict(data)
        stored = unsigned.pop("result_checksum", None)
        if stored != sha256_json(unsigned):
            errors.append("pdf_topology_assembly_result_checksum_invalid")
        return sorted(set(errors))

    def _normalize_response(
        self,
        value: dict[str, Any],
        *,
        parser_geometry_observation: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[int, list[dict[str, Any]]]]:
        normalized = copy.deepcopy(value)
        events: dict[int, list[dict[str, Any]]] = {}
        if not isinstance(normalized, dict):
            return normalized, events
        hypotheses = normalized.get("hypotheses")
        if not isinstance(hypotheses, list):
            return normalized, events
        for index, hypothesis in enumerate(hypotheses):
            if not isinstance(hypothesis, dict):
                continue
            rows = hypothesis.get("row_boundaries")
            columns = hypothesis.get("column_boundaries")
            spans = hypothesis.get("spans")
            if (
                not isinstance(rows, list)
                or not isinstance(columns, list)
                or not isinstance(spans, list)
            ):
                continue
            row_count = len(rows) - 1
            column_count = len(columns) - 1
            canonical_rows = _geometry_boundaries_for_segments(
                _dicts(parser_geometry_observation.get("horizontal_signals")),
                expected_segments=row_count,
                cluster_tolerance=self.config.geometry_cluster_tolerance_normalized,
                minimum_coverage=self.config.minimum_geometry_boundary_coverage_normalized,
            )
            canonical_columns = _geometry_boundaries_for_segments(
                _dicts(parser_geometry_observation.get("vertical_signals")),
                expected_segments=column_count,
                cluster_tolerance=self.config.geometry_cluster_tolerance_normalized,
                minimum_coverage=self.config.minimum_geometry_boundary_coverage_normalized,
            )
            kept: list[Any] = []
            hypothesis_events: list[dict[str, Any]] = []
            for span in spans:
                if not isinstance(span, dict) or set(span) != {
                    "start_row",
                    "end_row",
                    "start_column",
                    "end_column",
                    "relation",
                }:
                    kept.append(span)
                    continue
                start_row = span.get("start_row")
                end_row = span.get("end_row")
                start_column = span.get("start_column")
                end_column = span.get("end_column")
                is_noop = bool(
                    all(
                        isinstance(item, int) and not isinstance(item, bool)
                        for item in (
                            start_row,
                            end_row,
                            start_column,
                            end_column,
                        )
                    )
                    and start_row == end_row
                    and start_column == end_column
                    and 1 <= int(start_row) <= row_count
                    and 1 <= int(start_column) <= column_count
                    and span.get("relation") in {"merged", "spanning_header"}
                )
                if is_noop:
                    hypothesis_events.append(
                        {
                            "operation": "drop_degenerate_single_cell_span",
                            "before": copy.deepcopy(span),
                            "after": None,
                            "candidate_assignment_change_allowed": False,
                            "parser_separator_boundaries": [],
                        }
                    )
                else:
                    normalized_span = copy.deepcopy(span)
                    conflicts: list[str] = []
                    if (
                        canonical_rows is not None
                        and canonical_columns is not None
                        and all(
                            isinstance(item, int) and not isinstance(item, bool)
                            for item in (
                                start_row,
                                end_row,
                                start_column,
                                end_column,
                            )
                        )
                        and 1 <= int(start_row) <= int(end_row) <= row_count
                        and 1
                        <= int(start_column)
                        <= int(end_column)
                        <= column_count
                    ):
                        conflicts, _ = self._span_separator_states(
                            span=normalized_span,
                            row_boundaries=canonical_rows,
                            column_boundaries=canonical_columns,
                            horizontal_signals=_dicts(
                                parser_geometry_observation.get(
                                    "horizontal_signals"
                                )
                            ),
                            vertical_signals=_dicts(
                                parser_geometry_observation.get("vertical_signals")
                            ),
                        )
                    if conflicts:
                        trimmed = _trim_span_at_separators(
                            normalized_span, conflicts
                        )
                        after = (
                            None if _single_position_span(trimmed) else trimmed
                        )
                        hypothesis_events.append(
                            {
                                "operation": (
                                    "drop_span_reduced_to_single_cell_by_parser_separator"
                                    if after is None
                                    else "trim_span_to_parser_separator"
                                ),
                                "before": copy.deepcopy(span),
                                "after": copy.deepcopy(after),
                                "candidate_assignment_change_allowed": True,
                                "parser_separator_boundaries": conflicts,
                            }
                        )
                        if after is not None:
                            kept.append(after)
                    else:
                        kept.append(normalized_span)
            hypothesis["spans"] = kept
            if hypothesis_events:
                events[index] = hypothesis_events
        return normalized, events

    def _bind_hypothesis(
        self,
        *,
        parser_observation: dict[str, Any],
        parser_geometry_observation: dict[str, Any],
        visual_package: dict[str, Any],
        hypothesis: dict[str, Any],
        hypothesis_id: str,
    ) -> dict[str, Any]:
        neutral_map = _object(
            visual_package.get("neutral_atom_to_candidate_id")
        )
        atoms = _dicts(_object(visual_package.get("model_facing")).get("atoms"))
        boxes = {
            str(neutral_map.get(str(atom.get("atom_id") or "")) or ""): [
                float(value) for value in atom.get("bbox") or []
            ]
            for atom in atoms
        }
        source_order = {
            str(item.get("candidate_id") or ""): int(
                item.get("source_order") or 0
            )
            for item in _dicts(parser_observation.get("candidates"))
        }
        row_boundaries = [
            float(item) for item in hypothesis.get("row_boundaries") or []
        ]
        column_boundaries = [
            float(item) for item in hypothesis.get("column_boundaries") or []
        ]
        spans = copy.deepcopy(hypothesis.get("spans") or [])
        row_count = len(row_boundaries) - 1
        column_count = len(column_boundaries) - 1
        issues: list[dict[str, Any]] = []
        adjustments: list[dict[str, Any]] = []
        if row_count * column_count > self.config.maximum_grid_positions:
            issues.append(
                _issue(
                    hypothesis_id,
                    "table",
                    None,
                    "pdf_topology_assembly_grid_budget_exceeded",
                )
            )

        row_result = self._canonicalize_axis_from_parser_geometry(
            axis="row",
            visual_boundaries=row_boundaries,
            signals=_dicts(
                parser_geometry_observation.get("horizontal_signals")
            ),
            expected_segments=row_count,
            hypothesis_id=hypothesis_id,
        )
        column_result = self._canonicalize_axis_from_parser_geometry(
            axis="column",
            visual_boundaries=column_boundaries,
            signals=_dicts(
                parser_geometry_observation.get("vertical_signals")
            ),
            expected_segments=column_count,
            hypothesis_id=hypothesis_id,
        )
        issues.extend(row_result["issues"])
        issues.extend(column_result["issues"])
        adjustments.extend(row_result["adjustments"])
        adjustments.extend(column_result["adjustments"])
        canonical_rows = row_result["boundaries"]
        canonical_columns = column_result["boundaries"]
        baseline_positions, baseline_position_issues = self._positions(
            boxes=boxes,
            row_boundaries=canonical_rows,
            column_boundaries=canonical_columns,
            hypothesis_id=hypothesis_id,
        )
        if not baseline_position_issues:
            row_gap_result = self._reconcile_internal_axis_boundaries(
                axis="row",
                boundaries=canonical_rows,
                boxes=boxes,
                baseline_positions=baseline_positions,
                spans=spans,
                geometry_status=str(row_result["evidence"]["status"]),
                hypothesis_id=hypothesis_id,
            )
            column_gap_result = self._reconcile_internal_axis_boundaries(
                axis="column",
                boundaries=canonical_columns,
                boxes=boxes,
                baseline_positions=baseline_positions,
                spans=spans,
                geometry_status=str(column_result["evidence"]["status"]),
                hypothesis_id=hypothesis_id,
            )
            canonical_rows = row_gap_result["boundaries"]
            canonical_columns = column_gap_result["boundaries"]
            adjustments.extend(row_gap_result["adjustments"])
            adjustments.extend(column_gap_result["adjustments"])
            issues.extend(row_gap_result["issues"])
            issues.extend(column_gap_result["issues"])
            positions, position_issues = self._positions(
                boxes=boxes,
                row_boundaries=canonical_rows,
                column_boundaries=canonical_columns,
                hypothesis_id=hypothesis_id,
            )
            if not position_issues and positions != baseline_positions:
                position_issues.append(
                    _issue(
                        hypothesis_id,
                        "table",
                        None,
                        (
                            "pdf_topology_assembly_source_gap_"
                            "candidate_assignment_changed"
                        ),
                    )
                )
        else:
            positions = baseline_positions
            position_issues = baseline_position_issues
        issues.extend(position_issues)
        candidate_separator_result = self._candidate_separator_issues(
            boxes=boxes,
            positions=positions,
            row_boundaries=canonical_rows,
            column_boundaries=canonical_columns,
            horizontal_signals=_dicts(
                parser_geometry_observation.get("horizontal_signals")
            ),
            vertical_signals=_dicts(
                parser_geometry_observation.get("vertical_signals")
            ),
            row_geometry_status=str(row_result["evidence"]["status"]),
            column_geometry_status=str(column_result["evidence"]["status"]),
            hypothesis_id=hypothesis_id,
        )
        issues.extend(candidate_separator_result["issues"])

        original_spans = copy.deepcopy(spans)
        span_result = self._canonicalize_spans(
            spans=spans,
            positions=positions,
            boxes=boxes,
            row_boundaries=canonical_rows,
            column_boundaries=canonical_columns,
            horizontal_signals=_dicts(
                parser_geometry_observation.get("horizontal_signals")
            ),
            vertical_signals=_dicts(
                parser_geometry_observation.get("vertical_signals")
            ),
            hypothesis_id=hypothesis_id,
        )
        spans = span_result["spans"]
        adjustments.extend(span_result["adjustments"])
        issues.extend(span_result["issues"])

        hierarchy: list[dict[str, Any]] = []
        for relation in hypothesis.get("header_hierarchy") or []:
            operation = None
            if (
                relation.get("child_start_column")
                == relation.get("child_end_column")
                == relation.get("parent_column")
            ):
                operation = "drop_redundant_identity_header_relation"
            elif not _relation_has_span(relation, spans):
                if _relation_has_span(relation, span_result["contradicted_spans"]):
                    operation = "drop_header_relation_with_contradicted_span"
                elif _relation_has_span(relation, original_spans):
                    issues.append(
                        _issue(
                            hypothesis_id,
                            "header",
                            None,
                            "pdf_topology_assembly_header_relation_span_uncertified",
                        )
                    )
                    continue
                else:
                    issues.append(
                        _issue(
                            hypothesis_id,
                            "header",
                            None,
                            "pdf_topology_assembly_header_relation_span_missing",
                        )
                    )
                    continue
            if operation is not None:
                adjustments.append(
                    {
                        "hypothesis_id": hypothesis_id,
                        "operation": operation,
                        "axis": "header",
                        "boundary_index": None,
                        "before": copy.deepcopy(relation),
                        "after": None,
                        "delta": None,
                        "row_or_column_count_changed": False,
                        "candidate_assignment_change_allowed": False,
                        "source_value_change_allowed": False,
                    }
                )
            else:
                hierarchy.append(copy.deepcopy(relation))

        anchored_positions = copy.deepcopy(positions)
        for candidate_id, position in positions.items():
            covering = _covering_span(spans, position[0], position[1])
            if covering is not None:
                anchored_positions[candidate_id] = (
                    int(covering["start_row"]),
                    int(covering["start_column"]),
                )

        grid = [
            [[] for _ in range(column_count)] for _ in range(row_count)
        ]
        for candidate_id in sorted(
            anchored_positions,
            key=lambda item: source_order.get(item, 0),
        ):
            row, column = anchored_positions[candidate_id]
            if not (1 <= row <= row_count and 1 <= column <= column_count):
                issues.append(
                    _issue(
                        hypothesis_id,
                        "table",
                        None,
                        "pdf_topology_assembly_candidate_out_of_grid",
                    )
                )
                continue
            grid[row - 1][column - 1].append(candidate_id)

        for span in spans:
            anchor = grid[int(span["start_row"]) - 1][
                int(span["start_column"]) - 1
            ]
            covered = [
                grid[row - 1][column - 1]
                for row in range(int(span["start_row"]), int(span["end_row"]) + 1)
                for column in range(
                    int(span["start_column"]), int(span["end_column"]) + 1
                )
                if (row, column)
                != (int(span["start_row"]), int(span["start_column"]))
            ]
            if not anchor or any(covered):
                issues.append(
                    _issue(
                        hypothesis_id,
                        "span",
                        None,
                        "pdf_topology_assembly_span_anchor_invalid",
                    )
                )

        used = [candidate_id for row in grid for cell in row for candidate_id in cell]
        expected = list(parser_observation.get("candidate_order") or [])
        omitted = sorted(set(expected) - set(used))
        extra = sorted(set(used) - set(expected))
        duplicates = sorted(
            candidate_id for candidate_id in set(used) if used.count(candidate_id) > 1
        )
        if omitted:
            issues.append(
                _issue(
                    hypothesis_id,
                    "table",
                    None,
                    "pdf_topology_assembly_candidate_coverage_incomplete",
                )
            )
        if extra:
            issues.append(
                _issue(
                    hypothesis_id,
                    "table",
                    None,
                    "pdf_topology_assembly_candidate_unknown",
                )
            )
        if duplicates:
            issues.append(
                _issue(
                    hypothesis_id,
                    "table",
                    None,
                    "pdf_topology_assembly_candidate_ownership_duplicate",
                )
            )

        uncertainty = list(hypothesis.get("uncertainty_codes") or [])
        binding = None
        if not issues:
            header_count = int(hypothesis.get("header_row_count") or 0)
            binding = {
                "schema_version": PDF_HYBRID_BINDING_OUTPUT_SCHEMA,
                "package_id": visual_package.get("package_id"),
                "crop_sha256": _object(
                    visual_package.get("crop_identity")
                ).get("crop_sha256"),
                "candidate_dictionary_hash": visual_package.get(
                    "candidate_dictionary_hash"
                ),
                "decision": "ambiguous" if uncertainty else "bound",
                "row_count": row_count,
                "column_count": column_count,
                "header_rows": list(range(1, header_count + 1)),
                "header_hierarchy": hierarchy,
                "rows": [
                    {
                        "row_ordinal": index,
                        "row_kind": "header" if index <= header_count else "unknown",
                        "cells": copy.deepcopy(cells),
                    }
                    for index, cells in enumerate(grid, start=1)
                ],
                "spans": spans,
                "uncertainty_codes": uncertainty,
            }
            shape_errors = validate_binding_output_shape(binding)
            if shape_errors:
                issues.extend(
                    _issue(
                        hypothesis_id,
                        "table",
                        None,
                        code,
                    )
                    for code in shape_errors
                )
                binding = None

        accounting = {
            "hypothesis_id": hypothesis_id,
            "binding_created": binding is not None,
            "expected_candidates": len(expected),
            "used_candidates": len(used),
            "unique_used_candidates": len(set(used)),
            "omitted_candidate_ids": omitted,
            "extra_candidate_ids": extra,
            "duplicate_candidate_ids": duplicates,
            "grid_positions": row_count * column_count,
            "explicit_empty_positions": sum(not cell for row in grid for cell in row),
            "structural_adjustments": len(adjustments),
            "regional_issues": len(issues),
        }
        geometry_evidence = {
            "hypothesis_id": hypothesis_id,
            "row_boundaries": row_result["evidence"],
            "column_boundaries": column_result["evidence"],
            "candidate_separators": candidate_separator_result["evidence"],
            "span_separators": span_result["evidence"],
        }
        return {
            "binding_output": binding,
            "proposed_geometry": {
                "rows": {
                    "kind": "consensus_normalized_boundaries",
                    "boundaries": canonical_rows,
                },
                "columns": {
                    "kind": "consensus_normalized_boundaries",
                    "boundaries": canonical_columns,
                },
            },
            "regional_issues": issues,
            "structural_adjustments": adjustments,
            "geometry_evidence": geometry_evidence,
            "accounting": accounting,
        }

    def _reconcile_internal_axis_boundaries(
        self,
        *,
        axis: str,
        boundaries: list[float],
        boxes: dict[str, list[float]],
        baseline_positions: dict[str, tuple[int, int]],
        spans: list[dict[str, Any]],
        geometry_status: str,
        hypothesis_id: str,
    ) -> dict[str, Any]:
        """Snap a cutting visual separator to one source-owned atom gap.

        Certified parser geometry remains authoritative.  This fallback is
        available only when independent line geometry is insufficient and the
        current center-based segment assignment already exists.  A replacement
        is accepted only when exactly one positive gap preserves every center
        assignment and the existing segment order.
        """

        result = list(boundaries)
        issues: list[dict[str, Any]] = []
        adjustments: list[dict[str, Any]] = []
        if (
            axis not in {"row", "column"}
            or geometry_status != "insufficient_evidence"
        ):
            return {
                "boundaries": result,
                "issues": issues,
                "adjustments": adjustments,
            }

        start_index, end_index = (1, 3) if axis == "row" else (0, 2)
        position_index = 0 if axis == "row" else 1
        tolerance = self.config.atom_band_tolerance_normalized
        epsilon = self.config.boundary_epsilon
        merged_intervals = _merged_axis_intervals(
            boxes=boxes,
            start_index=start_index,
            end_index=end_index,
        )
        source_gaps = [
            [left[1], right[0]]
            for left, right in zip(merged_intervals, merged_intervals[1:])
            if right[0] - left[1] > epsilon
        ]

        for boundary_index in range(1, len(result) - 1):
            boundary = result[boundary_index]
            crossing_candidate_ids = sorted(
                candidate_id
                for candidate_id, box in boxes.items()
                if box[start_index] + tolerance
                < boundary
                < box[end_index] - tolerance
            )
            if not crossing_candidate_ids:
                continue
            if any(
                _span_crosses_axis_boundary(
                    span,
                    axis=axis,
                    boundary_index=boundary_index,
                )
                for span in spans
            ):
                continue

            valid_gaps: list[tuple[list[float], float]] = []
            for gap in source_gaps:
                midpoint = round((gap[0] + gap[1]) / 2.0, 9)
                if (
                    not gap[0] < midpoint < gap[1]
                    or not result[boundary_index - 1]
                    < midpoint
                    < result[boundary_index + 1]
                ):
                    continue
                trial = list(result)
                trial[boundary_index] = midpoint
                assignments = {
                    candidate_id: _segment(
                        (box[start_index] + box[end_index]) / 2.0,
                        trial,
                        epsilon=epsilon,
                    )
                    for candidate_id, box in boxes.items()
                }
                if any(value is None for value in assignments.values()):
                    continue
                if any(
                    assignments.get(candidate_id)
                    != baseline_positions.get(candidate_id, (0, 0))[
                        position_index
                    ]
                    for candidate_id in boxes
                ):
                    continue
                valid_gaps.append((list(gap), midpoint))

            if len(valid_gaps) != 1:
                issues.append(
                    _issue(
                        hypothesis_id,
                        axis,
                        boundary_index,
                        (
                            "pdf_topology_assembly_internal_boundary_"
                            "source_gap_not_unique"
                        ),
                    )
                )
                continue

            gap, midpoint = valid_gaps[0]
            before = boundary
            result[boundary_index] = midpoint
            adjustments.append(
                {
                    "hypothesis_id": hypothesis_id,
                    "operation": (
                        "replace_visual_boundary_with_unique_source_atom_gap"
                    ),
                    "axis": axis,
                    "boundary_index": boundary_index,
                    "before": before,
                    "after": midpoint,
                    "delta": round(midpoint - before, 9),
                    "row_or_column_count_changed": False,
                    "candidate_assignment_change_allowed": False,
                    "source_value_change_allowed": False,
                    "evidence_basis": "unique_positive_source_atom_gap",
                    "source_atom_gap": gap,
                    "crossing_candidate_ids": crossing_candidate_ids,
                    "candidate_assignment_preserved": True,
                }
            )

        return {
            "boundaries": result,
            "issues": issues,
            "adjustments": adjustments,
        }

    def _canonicalize_axis_from_parser_geometry(
        self,
        *,
        axis: str,
        visual_boundaries: list[float],
        signals: list[dict[str, Any]],
        expected_segments: int,
        hypothesis_id: str,
    ) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        adjustments: list[dict[str, Any]] = []
        vector_signals = [
            item for item in signals if item.get("kind") == "vector_line"
        ]
        clusters = [
            item
            for item in _geometry_clusters(
                vector_signals,
                tolerance=self.config.geometry_cluster_tolerance_normalized,
            )
            if item["coverage"]
            >= self.config.minimum_geometry_boundary_coverage_normalized
        ]
        if len(clusters) != expected_segments + 1:
            reason_code = (
                "pdf_topology_assembly_parser_geometry_missing"
                if not vector_signals
                else "pdf_topology_assembly_parser_geometry_incomplete"
            )
            return {
                "boundaries": list(visual_boundaries),
                "issues": [],
                "adjustments": [],
                "evidence": _geometry_evidence_item(
                    status="insufficient_evidence",
                    observed_count=len(clusters),
                    required_count=expected_segments + 1,
                    reason_codes=[reason_code],
                ),
            }
        result = [float(item["position"]) for item in clusters]
        edge_tolerance = self.config.geometry_cluster_tolerance_normalized * 2
        if result[0] > edge_tolerance or 1.0 - result[-1] > edge_tolerance:
            issues.append(
                _issue(
                    hypothesis_id,
                    axis,
                    None,
                    "pdf_topology_assembly_parser_geometry_outer_boundary_missing",
                )
            )
        result[0] = 0.0
        result[-1] = 1.0
        if any(left >= right for left, right in zip(result, result[1:])):
            issues.append(
                _issue(
                    hypothesis_id,
                    axis,
                    None,
                    "pdf_topology_assembly_parser_geometry_boundary_order_invalid",
                )
            )
        for boundary_index, target in enumerate(result):
            before = float(visual_boundaries[boundary_index])
            if abs(target - before) > self.config.boundary_epsilon:
                adjustments.append(
                    {
                        "hypothesis_id": hypothesis_id,
                        "operation": "replace_visual_boundary_with_parser_geometry",
                        "axis": axis,
                        "boundary_index": boundary_index,
                        "before": before,
                        "after": target,
                        "delta": round(target - before, 9),
                        "row_or_column_count_changed": False,
                        "candidate_assignment_change_allowed": True,
                        "source_value_change_allowed": False,
                        "parser_geometry_coverage": round(
                            float(clusters[boundary_index]["coverage"]), 9
                        ),
                    }
                )
        return {
            "boundaries": result,
            "issues": issues,
            "adjustments": adjustments,
            "evidence": _geometry_evidence_item(
                status="contradicted" if issues else "confirmed",
                observed_count=len(clusters),
                required_count=expected_segments + 1,
                reason_codes=[
                    str(item.get("reason_code") or "")
                    for item in issues
                    if item.get("reason_code")
                ],
            ),
        }

    def _canonicalize_spans(
        self,
        *,
        spans: list[dict[str, Any]],
        positions: dict[str, tuple[int, int]],
        boxes: dict[str, list[float]],
        row_boundaries: list[float],
        column_boundaries: list[float],
        horizontal_signals: list[dict[str, Any]],
        vertical_signals: list[dict[str, Any]],
        hypothesis_id: str,
    ) -> dict[str, Any]:
        kept: list[dict[str, Any]] = []
        contradicted: list[dict[str, Any]] = []
        issues: list[dict[str, Any]] = []
        adjustments: list[dict[str, Any]] = []
        separator_conflict_count = 0
        separator_check_count = 0
        for source_span in spans:
            span = copy.deepcopy(source_span)
            separator_check_count += (
                int(span["end_row"])
                - int(span["start_row"])
                + int(span["end_column"])
                - int(span["start_column"])
            )
            separator_boundaries, _ = self._span_separator_states(
                span=span,
                row_boundaries=row_boundaries,
                column_boundaries=column_boundaries,
                horizontal_signals=horizontal_signals,
                vertical_signals=vertical_signals,
            )
            if separator_boundaries:
                separator_conflict_count += len(separator_boundaries)
                trimmed = _trim_span_at_separators(span, separator_boundaries)
                after = None if _single_position_span(trimmed) else trimmed
                adjustments.append(
                    {
                        "hypothesis_id": hypothesis_id,
                        "operation": (
                            "drop_span_reduced_to_single_cell_by_parser_separator"
                            if after is None
                            else "trim_span_to_parser_separator"
                        ),
                        "axis": "span",
                        "boundary_index": None,
                        "before": copy.deepcopy(source_span),
                        "after": copy.deepcopy(after),
                        "delta": None,
                        "row_or_column_count_changed": False,
                        "candidate_assignment_change_allowed": True,
                        "source_value_change_allowed": False,
                        "parser_separator_boundaries": separator_boundaries,
                    }
                )
                contradicted.append(copy.deepcopy(source_span))
                if after is None:
                    continue
                span = after

            members = [
                candidate_id
                for candidate_id, position in positions.items()
                if _span_contains(span, position[0], position[1])
            ]
            if not members:
                adjustments.append(
                    {
                        "hypothesis_id": hypothesis_id,
                        "operation": (
                            "project_geometry_certified_empty_span_to_explicit_empty_cells"
                        ),
                        "axis": "span",
                        "boundary_index": None,
                        "before": copy.deepcopy(span),
                        "after": None,
                        "delta": None,
                        "row_or_column_count_changed": False,
                        "candidate_assignment_change_allowed": False,
                        "source_value_change_allowed": False,
                        "parser_separator_boundaries": [],
                    }
                )
                continue

            selected_region = [
                column_boundaries[int(span["start_column"]) - 1],
                row_boundaries[int(span["start_row"]) - 1],
                column_boundaries[int(span["end_column"])],
                row_boundaries[int(span["end_row"])],
            ]
            if any(
                not _bbox_within_region(
                    boxes[item],
                    selected_region,
                    tolerance=self.config.atom_band_tolerance_normalized,
                )
                for item in members
            ):
                issues.append(
                    _issue(
                        hypothesis_id,
                        "span",
                        None,
                        "pdf_topology_assembly_span_atom_outside_selected_region",
                    )
                )
                continue
            kept.append(copy.deepcopy(span))
        if not spans or separator_check_count == 0:
            evidence_status = "not_applicable"
            evidence_reasons: list[str] = []
        elif separator_conflict_count:
            evidence_status = "contradicted"
            evidence_reasons = [
                "pdf_topology_assembly_span_crosses_parser_separator"
            ]
        else:
            evidence_status = "insufficient_evidence"
            evidence_reasons = [
                "pdf_topology_assembly_span_separator_evidence_incomplete"
            ]
        return {
            "spans": kept,
            "contradicted_spans": contradicted,
            "issues": issues,
            "adjustments": adjustments,
            "evidence": _geometry_evidence_item(
                status=evidence_status,
                observed_count=separator_conflict_count,
                required_count=0,
                reason_codes=evidence_reasons,
            ),
        }

    def _span_separator_states(
        self,
        *,
        span: dict[str, Any],
        row_boundaries: list[float],
        column_boundaries: list[float],
        horizontal_signals: list[dict[str, Any]],
        vertical_signals: list[dict[str, Any]],
    ) -> tuple[list[str], list[str]]:
        conflicts: list[str] = []
        ambiguous: list[str] = []
        row_start = int(span["start_row"])
        row_end = int(span["end_row"])
        column_start = int(span["start_column"])
        column_end = int(span["end_column"])
        row_extent = [row_boundaries[row_start - 1], row_boundaries[row_end]]
        column_extent = [
            column_boundaries[column_start - 1],
            column_boundaries[column_end],
        ]
        for boundary_index in range(row_start, row_end):
            coverage = _separator_coverage(
                signals=[
                    item
                    for item in horizontal_signals
                    if item.get("kind") == "vector_line"
                ],
                position=row_boundaries[boundary_index],
                target_extent=column_extent,
                tolerance=self.config.geometry_cluster_tolerance_normalized,
            )
            if coverage >= self.config.minimum_span_separator_coverage_ratio:
                conflicts.append(f"row:{boundary_index}")
            elif coverage > self.config.maximum_span_gap_coverage_ratio:
                ambiguous.append(f"row:{boundary_index}")
        for boundary_index in range(column_start, column_end):
            coverage = _separator_coverage(
                signals=[
                    item
                    for item in vertical_signals
                    if item.get("kind") == "vector_line"
                ],
                position=column_boundaries[boundary_index],
                target_extent=row_extent,
                tolerance=self.config.geometry_cluster_tolerance_normalized,
            )
            if coverage >= self.config.minimum_span_separator_coverage_ratio:
                conflicts.append(f"column:{boundary_index}")
            elif coverage > self.config.maximum_span_gap_coverage_ratio:
                ambiguous.append(f"column:{boundary_index}")
        return conflicts, ambiguous

    def _candidate_separator_issues(
        self,
        *,
        boxes: dict[str, list[float]],
        positions: dict[str, tuple[int, int]],
        row_boundaries: list[float],
        column_boundaries: list[float],
        horizontal_signals: list[dict[str, Any]],
        vertical_signals: list[dict[str, Any]],
        row_geometry_status: str,
        column_geometry_status: str,
        hypothesis_id: str,
    ) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        vector_horizontal = [
            item for item in horizontal_signals if item.get("kind") == "vector_line"
        ]
        vector_vertical = [
            item for item in vertical_signals if item.get("kind") == "vector_line"
        ]
        tolerance = self.config.atom_band_tolerance_normalized
        for candidate_id, (row, column) in positions.items():
            box = boxes[candidate_id]
            row_extent = [row_boundaries[row - 1], row_boundaries[row]]
            column_extent = [
                column_boundaries[column - 1],
                column_boundaries[column],
            ]
            for boundary_index, boundary in enumerate(
                column_boundaries[1:-1], start=1
            ):
                if not box[0] + tolerance < boundary < box[2] - tolerance:
                    continue
                coverage = _separator_coverage(
                    signals=vector_vertical,
                    position=boundary,
                    target_extent=row_extent,
                    tolerance=self.config.geometry_cluster_tolerance_normalized,
                )
                if coverage >= self.config.minimum_span_separator_coverage_ratio:
                    issues.append(
                        _issue(
                            hypothesis_id,
                            "column",
                            boundary_index,
                            "pdf_topology_assembly_candidate_bbox_crosses_parser_separator",
                        )
                    )
                    break
            for boundary_index, boundary in enumerate(
                row_boundaries[1:-1], start=1
            ):
                if not box[1] + tolerance < boundary < box[3] - tolerance:
                    continue
                coverage = _separator_coverage(
                    signals=vector_horizontal,
                    position=boundary,
                    target_extent=column_extent,
                    tolerance=self.config.geometry_cluster_tolerance_normalized,
                )
                if coverage >= self.config.minimum_span_separator_coverage_ratio:
                    issues.append(
                        _issue(
                            hypothesis_id,
                            "row",
                            boundary_index,
                            "pdf_topology_assembly_candidate_bbox_crosses_parser_separator",
                        )
                    )
                    break
        if not positions:
            evidence_status = "not_applicable"
            evidence_reasons: list[str] = []
        elif issues:
            evidence_status = "contradicted"
            evidence_reasons = sorted(
                {
                    str(item.get("reason_code") or "")
                    for item in issues
                    if item.get("reason_code")
                }
            )
        elif row_geometry_status == column_geometry_status == "confirmed":
            evidence_status = "confirmed"
            evidence_reasons = []
        else:
            evidence_status = "insufficient_evidence"
            evidence_reasons = [
                "pdf_topology_assembly_candidate_separator_evidence_incomplete"
            ]
        return {
            "issues": issues,
            "evidence": _geometry_evidence_item(
                status=evidence_status,
                observed_count=len(issues),
                required_count=0,
                reason_codes=evidence_reasons,
            ),
        }

    def _positions(
        self,
        *,
        boxes: dict[str, list[float]],
        row_boundaries: list[float],
        column_boundaries: list[float],
        hypothesis_id: str,
    ) -> tuple[dict[str, tuple[int, int]], list[dict[str, Any]]]:
        positions: dict[str, tuple[int, int]] = {}
        issues: list[dict[str, Any]] = []
        for candidate_id, box in boxes.items():
            center_x = (box[0] + box[2]) / 2
            center_y = (box[1] + box[3]) / 2
            row = _segment(
                center_y,
                row_boundaries,
                epsilon=self.config.boundary_epsilon,
            )
            column = _segment(
                center_x,
                column_boundaries,
                epsilon=self.config.boundary_epsilon,
            )
            if row is None:
                issues.append(
                    _issue(
                        hypothesis_id,
                        "row",
                        None,
                        "pdf_topology_assembly_atom_on_row_boundary",
                    )
                )
            if column is None:
                issues.append(
                    _issue(
                        hypothesis_id,
                        "column",
                        None,
                        "pdf_topology_assembly_atom_on_column_boundary",
                    )
                )
            if row is not None and column is not None:
                positions[candidate_id] = (row, column)
        return positions, issues

    def _same_parser_scope(
        self,
        *,
        parser_observation: dict[str, Any],
        parser_geometry_observation: dict[str, Any],
    ) -> bool:
        for key in (
            "document_ref",
            "pdf_sha256",
            "page_ref",
            "page_number",
            "table_ref",
        ):
            if parser_observation.get(key) != parser_geometry_observation.get(key):
                return False
        parser_bbox = _bbox(
            _object(parser_observation.get("coordinate_space")).get("table_bbox")
        )
        geometry_bbox = _bbox(
            _object(parser_geometry_observation.get("coordinate_space")).get(
                "table_bbox"
            )
        )
        return parser_bbox is not None and geometry_bbox == parser_bbox

    @staticmethod
    def _validate_attempt_evidence(value: dict[str, Any]) -> None:
        if set(value) != {
            "attempt_id",
            "attempt_number",
            "evidence_revision",
            "provider",
            "model",
            "provider_config_hash",
        }:
            raise PdfTopologyAssemblyError(
                "pdf_topology_assembly_attempt_evidence_keys_invalid"
            )
        if (
            not all(
                isinstance(value.get(key), str) and bool(value.get(key))
                for key in (
                    "attempt_id",
                    "evidence_revision",
                    "provider",
                    "model",
                    "provider_config_hash",
                )
            )
            or not isinstance(value.get("attempt_number"), int)
            or isinstance(value.get("attempt_number"), bool)
            or int(value.get("attempt_number") or 0) < 1
        ):
            raise PdfTopologyAssemblyError(
                "pdf_topology_assembly_attempt_evidence_invalid"
            )


def _merged_axis_intervals(
    *,
    boxes: dict[str, list[float]],
    start_index: int,
    end_index: int,
) -> list[list[float]]:
    intervals = sorted(
        (
            [float(box[start_index]), float(box[end_index])]
            for box in boxes.values()
        ),
        key=lambda item: (item[0], item[1]),
    )
    merged: list[list[float]] = []
    for start, end in intervals:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return merged


def _span_crosses_axis_boundary(
    span: dict[str, Any], *, axis: str, boundary_index: int
) -> bool:
    if axis == "row":
        start = span.get("start_row")
        end = span.get("end_row")
    else:
        start = span.get("start_column")
        end = span.get("end_column")
    return bool(
        isinstance(start, int)
        and not isinstance(start, bool)
        and isinstance(end, int)
        and not isinstance(end, bool)
        and start <= boundary_index < end
    )


def _geometry_clusters(
    signals: list[dict[str, Any]], *, tolerance: float
) -> list[dict[str, Any]]:
    groups: list[list[dict[str, Any]]] = []
    for signal in sorted(
        signals,
        key=lambda item: (
            float(item.get("position_normalized") or 0.0),
            str(item.get("signal_id") or ""),
        ),
    ):
        position = float(signal.get("position_normalized") or 0.0)
        if not groups or position - float(
            groups[-1][0].get("position_normalized") or 0.0
        ) > tolerance:
            groups.append([signal])
        else:
            groups[-1].append(signal)
    result = []
    for group in groups:
        positions = sorted(
            float(item.get("position_normalized") or 0.0) for item in group
        )
        midpoint = len(positions) // 2
        position = (
            positions[midpoint]
            if len(positions) % 2
            else (positions[midpoint - 1] + positions[midpoint]) / 2
        )
        result.append(
            {
                "position": round(position, 12),
                "coverage": _union_length(
                    [
                        [float(value) for value in item.get("extent_normalized") or []]
                        for item in group
                    ]
                ),
                "signal_count": len(group),
            }
        )
    return result


def _geometry_boundaries_for_segments(
    signals: list[dict[str, Any]],
    *,
    expected_segments: int,
    cluster_tolerance: float,
    minimum_coverage: float,
) -> list[float] | None:
    clusters = [
        item
        for item in _geometry_clusters(
            [item for item in signals if item.get("kind") == "vector_line"],
            tolerance=cluster_tolerance,
        )
        if float(item["coverage"]) >= minimum_coverage
    ]
    if len(clusters) != expected_segments + 1:
        return None
    result = [float(item["position"]) for item in clusters]
    if result[0] > cluster_tolerance * 2 or 1.0 - result[-1] > cluster_tolerance * 2:
        return None
    result[0] = 0.0
    result[-1] = 1.0
    return (
        result
        if all(left < right for left, right in zip(result, result[1:]))
        else None
    )


def _trim_span_at_separators(
    span: dict[str, Any], separators: list[str]
) -> dict[str, Any]:
    result = copy.deepcopy(span)
    row_boundaries = [
        int(item.split(":", 1)[1])
        for item in separators
        if item.startswith("row:")
    ]
    column_boundaries = [
        int(item.split(":", 1)[1])
        for item in separators
        if item.startswith("column:")
    ]
    if row_boundaries:
        result["end_row"] = min(int(result["end_row"]), min(row_boundaries))
    if column_boundaries:
        result["end_column"] = min(
            int(result["end_column"]), min(column_boundaries)
        )
    return result


def _single_position_span(span: dict[str, Any]) -> bool:
    return bool(
        int(span.get("start_row") or 0) == int(span.get("end_row") or 0)
        and int(span.get("start_column") or 0)
        == int(span.get("end_column") or 0)
    )


def _separator_coverage(
    *,
    signals: list[dict[str, Any]],
    position: float,
    target_extent: list[float],
    tolerance: float,
) -> float:
    length = target_extent[1] - target_extent[0]
    if length <= 0:
        return 0.0
    intervals = []
    for signal in signals:
        if abs(float(signal.get("position_normalized") or 0.0) - position) > tolerance:
            continue
        extent = signal.get("extent_normalized")
        if not isinstance(extent, list) or len(extent) != 2:
            continue
        start = max(float(extent[0]), target_extent[0])
        end = min(float(extent[1]), target_extent[1])
        if end > start:
            intervals.append([start, end])
    return _union_length(intervals) / length


def _union_length(intervals: list[list[float]]) -> float:
    ordered = sorted(
        (
            [float(item[0]), float(item[1])]
            for item in intervals
            if isinstance(item, list) and len(item) == 2 and item[1] > item[0]
        ),
        key=lambda item: (item[0], item[1]),
    )
    if not ordered:
        return 0.0
    total = 0.0
    start, end = ordered[0]
    for current_start, current_end in ordered[1:]:
        if current_start <= end:
            end = max(end, current_end)
        else:
            total += end - start
            start, end = current_start, current_end
    return total + end - start


def _bbox_within_region(
    bbox: list[float], region: list[float], *, tolerance: float
) -> bool:
    return bool(
        len(bbox) == 4
        and len(region) == 4
        and float(bbox[0]) >= float(region[0]) - tolerance
        and float(bbox[1]) >= float(region[1]) - tolerance
        and float(bbox[2]) <= float(region[2]) + tolerance
        and float(bbox[3]) <= float(region[3]) + tolerance
    )


def _geometry_evidence_item(
    *,
    status: str,
    observed_count: int,
    required_count: int,
    reason_codes: list[str],
) -> dict[str, Any]:
    if status not in _GEOMETRY_EVIDENCE_STATUSES:
        raise PdfTopologyAssemblyError(
            "pdf_topology_assembly_geometry_evidence_status_invalid"
        )
    return {
        "status": status,
        "observed_count": int(observed_count),
        "required_count": int(required_count),
        "reason_codes": sorted(set(reason_codes)),
    }


def _structural_adjustments_valid(
    value: Any,
    *,
    expected_hypothesis_ids: set[str],
) -> bool:
    if not isinstance(value, list) or any(
        not isinstance(item, dict) for item in value
    ):
        return False
    return all(
        _structural_adjustment_valid(
            item,
            expected_hypothesis_ids=expected_hypothesis_ids,
        )
        for item in value
    )


def _structural_adjustments_consistent(
    *,
    adjustments: Any,
    source_accounting: Any,
    binding_hypotheses: Any,
    expected_hypothesis_ids: set[str],
) -> bool:
    if not isinstance(adjustments, list):
        return False
    accounting = _object(source_accounting)
    alternatives_value = accounting.get("alternative_accounting")
    alternatives = _dicts(alternatives_value)
    if (
        not isinstance(alternatives_value, list)
        or len(alternatives) != len(alternatives_value)
    ):
        return False

    adjustment_counts = {
        hypothesis_id: 0 for hypothesis_id in expected_hypothesis_ids
    }
    for adjustment in adjustments:
        hypothesis_id = str(_object(adjustment).get("hypothesis_id") or "")
        if hypothesis_id not in adjustment_counts:
            return False
        adjustment_counts[hypothesis_id] += 1

    alternative_by_id: dict[str, dict[str, Any]] = {}
    for alternative in alternatives:
        hypothesis_id = str(alternative.get("hypothesis_id") or "")
        recorded = alternative.get("structural_adjustments")
        if (
            hypothesis_id not in expected_hypothesis_ids
            or hypothesis_id in alternative_by_id
            or not _nonnegative_integer(recorded)
            or recorded != adjustment_counts[hypothesis_id]
        ):
            return False
        alternative_by_id[hypothesis_id] = alternative
    if set(alternative_by_id) != expected_hypothesis_ids:
        return False

    binding_values = binding_hypotheses
    bindings = _dicts(binding_values)
    if not isinstance(binding_values, list) or len(bindings) != len(
        binding_values
    ):
        return False
    binding_by_id: dict[str, dict[str, Any]] = {}
    for binding in bindings:
        hypothesis_id = str(binding.get("hypothesis_id") or "")
        if (
            hypothesis_id not in expected_hypothesis_ids
            or hypothesis_id in binding_by_id
        ):
            return False
        binding_by_id[hypothesis_id] = binding

    for adjustment in adjustments:
        item = _object(adjustment)
        axis = item.get("axis")
        if axis not in {"row", "column"}:
            continue
        binding = binding_by_id.get(str(item.get("hypothesis_id") or ""))
        if binding is None:
            continue
        proposed_geometry = _object(binding.get("proposed_geometry"))
        geometry_axis = _object(
            proposed_geometry.get("rows" if axis == "row" else "columns")
        )
        boundaries = geometry_axis.get("boundaries")
        boundary_index = item.get("boundary_index")
        if (
            geometry_axis.get("kind")
            != "consensus_normalized_boundaries"
            or not isinstance(boundaries, list)
            or not isinstance(boundary_index, int)
            or isinstance(boundary_index, bool)
            or boundary_index < 0
            or boundary_index >= len(boundaries)
            or not _normalized_number(boundaries[boundary_index])
            or float(boundaries[boundary_index]) != float(item.get("after"))
        ):
            return False
    return True


def _structural_adjustment_valid(
    item: dict[str, Any],
    *,
    expected_hypothesis_ids: set[str],
) -> bool:
    hypothesis_id = item.get("hypothesis_id")
    operation = item.get("operation")
    if (
        not isinstance(hypothesis_id, str)
        or not hypothesis_id
        or hypothesis_id not in expected_hypothesis_ids
        or not isinstance(operation, str)
        or item.get("row_or_column_count_changed") is not False
        or item.get("source_value_change_allowed") is not False
        or not isinstance(
            item.get("candidate_assignment_change_allowed"), bool
        )
    ):
        return False

    if operation == "replace_visual_boundary_with_parser_geometry":
        return bool(
            set(item) == _PARSER_GEOMETRY_ADJUSTMENT_KEYS
            and _boundary_adjustment_common_valid(item, internal=False)
            and item.get("candidate_assignment_change_allowed") is True
            and _normalized_number(item.get("parser_geometry_coverage"))
        )

    if operation == "replace_visual_boundary_with_unique_source_atom_gap":
        gap = item.get("source_atom_gap")
        crossing_ids = item.get("crossing_candidate_ids")
        return bool(
            set(item) == _SOURCE_GAP_ADJUSTMENT_KEYS
            and _boundary_adjustment_common_valid(item, internal=True)
            and item.get("candidate_assignment_change_allowed") is False
            and item.get("candidate_assignment_preserved") is True
            and item.get("evidence_basis")
            == "unique_positive_source_atom_gap"
            and isinstance(gap, list)
            and len(gap) == 2
            and all(_normalized_number(current) for current in gap)
            and float(gap[0]) < float(item["after"]) < float(gap[1])
            and float(item["after"])
            == round((float(gap[0]) + float(gap[1])) / 2.0, 9)
            and isinstance(crossing_ids, list)
            and bool(crossing_ids)
            and all(
                isinstance(candidate_id, str) and bool(candidate_id)
                for candidate_id in crossing_ids
            )
            and crossing_ids == sorted(set(crossing_ids))
        )

    if operation in _SPAN_ADJUSTMENT_OPERATIONS:
        return _span_adjustment_valid(item)

    if operation in _HEADER_ADJUSTMENT_OPERATIONS:
        before = item.get("before")
        identity = bool(
            isinstance(before, dict)
            and before.get("child_start_column")
            == before.get("child_end_column")
            == before.get("parent_column")
        )
        return bool(
            set(item) == _STRUCTURAL_ADJUSTMENT_BASE_KEYS
            and item.get("axis") == "header"
            and item.get("boundary_index") is None
            and item.get("after") is None
            and item.get("delta") is None
            and item.get("candidate_assignment_change_allowed") is False
            and _header_relation_valid(before)
            and (
                operation == "drop_redundant_identity_header_relation"
                and identity
                or operation == "drop_header_relation_with_contradicted_span"
                and not identity
            )
        )

    return False


def _boundary_adjustment_common_valid(
    item: dict[str, Any],
    *,
    internal: bool,
) -> bool:
    boundary_index = item.get("boundary_index")
    before = item.get("before")
    after = item.get("after")
    delta = item.get("delta")
    return bool(
        item.get("axis") in {"row", "column"}
        and isinstance(boundary_index, int)
        and not isinstance(boundary_index, bool)
        and boundary_index >= (1 if internal else 0)
        and _normalized_number(before)
        and _normalized_number(after)
        and float(before) != float(after)
        and _finite_number(delta)
        and float(delta) == round(float(after) - float(before), 9)
    )


def _span_adjustment_valid(item: dict[str, Any]) -> bool:
    if (
        set(item) != _SPAN_ADJUSTMENT_KEYS
        or item.get("axis") != "span"
        or item.get("boundary_index") is not None
        or item.get("delta") is not None
        or not _span_value_valid(item.get("before"), allow_single_cell=True)
    ):
        return False
    operation = str(item.get("operation") or "")
    before = item["before"]
    after = item.get("after")
    separators = item.get("parser_separator_boundaries")
    if not _separator_boundaries_valid(separators, span=before):
        return False
    trimmed = _trim_span_at_separators(before, separators)
    if operation == "drop_degenerate_single_cell_span":
        return bool(
            _single_position_span(before)
            and after is None
            and separators == []
            and item.get("candidate_assignment_change_allowed") is False
        )
    if operation == "drop_span_reduced_to_single_cell_by_parser_separator":
        return bool(
            not _single_position_span(before)
            and after is None
            and bool(separators)
            and _single_position_span(trimmed)
            and item.get("candidate_assignment_change_allowed") is True
        )
    if operation == "trim_span_to_parser_separator":
        return bool(
            not _single_position_span(before)
            and _span_value_valid(after, allow_single_cell=False)
            and after == trimmed
            and bool(separators)
            and item.get("candidate_assignment_change_allowed") is True
        )
    if operation == (
        "project_geometry_certified_empty_span_to_explicit_empty_cells"
    ):
        return bool(
            not _single_position_span(before)
            and after is None
            and separators == []
            and item.get("candidate_assignment_change_allowed") is False
        )
    return False


def _span_value_valid(value: Any, *, allow_single_cell: bool) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "start_row",
        "end_row",
        "start_column",
        "end_column",
        "relation",
    }:
        return False
    coordinates = [
        value.get("start_row"),
        value.get("end_row"),
        value.get("start_column"),
        value.get("end_column"),
    ]
    if any(
        not isinstance(current, int)
        or isinstance(current, bool)
        or current < 1
        for current in coordinates
    ):
        return False
    return bool(
        int(value["start_row"]) <= int(value["end_row"])
        and int(value["start_column"]) <= int(value["end_column"])
        and value.get("relation") in {"merged", "spanning_header"}
        and (allow_single_cell or not _single_position_span(value))
    )


def _separator_boundaries_valid(value: Any, *, span: dict[str, Any]) -> bool:
    if not isinstance(value, list) or any(
        not isinstance(item, str) for item in value
    ):
        return False
    if len(value) != len(set(value)):
        return False
    for item in value:
        axis, separator, raw_index = item.partition(":")
        if (
            separator != ":"
            or axis not in {"row", "column"}
            or not raw_index.isdigit()
        ):
            return False
        index = int(raw_index)
        if axis == "row" and not (
            int(span["start_row"]) <= index < int(span["end_row"])
        ):
            return False
        if axis == "column" and not (
            int(span["start_column"]) <= index < int(span["end_column"])
        ):
            return False
    return True


def _header_relation_valid(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "parent_row",
        "parent_column",
        "child_start_column",
        "child_end_column",
    }:
        return False
    coordinates = list(value.values())
    return bool(
        all(
            isinstance(current, int)
            and not isinstance(current, bool)
            and current >= 1
            for current in coordinates
        )
        and int(value["child_start_column"])
        <= int(value["child_end_column"])
    )


def _finite_number(value: Any) -> bool:
    return bool(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _normalized_number(value: Any) -> bool:
    return bool(_finite_number(value) and 0.0 <= float(value) <= 1.0)


def _nonnegative_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _reason_codes(value: Any) -> bool:
    return bool(
        isinstance(value, list)
        and all(isinstance(item, str) and bool(item) for item in value)
        and value == sorted(set(value))
    )


def _relation_has_span(
    relation: dict[str, Any], spans: list[dict[str, Any]]
) -> bool:
    return any(
        int(span.get("start_row") or 0) == int(relation.get("parent_row") or 0)
        and int(span.get("start_column") or 0)
        == int(relation.get("parent_column") or 0)
        and int(span.get("end_column") or 0)
        >= int(relation.get("child_end_column") or 0)
        for span in spans
    )


def _segment(
    value: float,
    boundaries: list[float],
    *,
    epsilon: float,
) -> int | None:
    if not boundaries or value < boundaries[0] or value > boundaries[-1]:
        return None
    for boundary in boundaries[1:-1]:
        if abs(value - boundary) <= epsilon:
            return None
    for index, (start, end) in enumerate(zip(boundaries, boundaries[1:]), start=1):
        if start <= value < end or (
            index == len(boundaries) - 1 and start <= value <= end
        ):
            return index
    return None


def _covering_span(
    spans: list[dict[str, Any]], row: int, column: int
) -> dict[str, Any] | None:
    values = [span for span in spans if _span_contains(span, row, column)]
    return values[0] if len(values) == 1 else None


def _span_contains(span: dict[str, Any], row: int, column: int) -> bool:
    return bool(
        int(span.get("start_row") or 0)
        <= row
        <= int(span.get("end_row") or 0)
        and int(span.get("start_column") or 0)
        <= column
        <= int(span.get("end_column") or 0)
    )


def _issue(
    hypothesis_id: str,
    axis: str,
    boundary_index: int | None,
    reason_code: str,
) -> dict[str, Any]:
    return {
        "hypothesis_id": hypothesis_id,
        "axis": axis,
        "boundary_index": boundary_index,
        "reason_code": reason_code,
        "retry_scope": (
            "local_boundary_or_span_region"
            if axis in {"row", "column", "span"}
            else "full_table_crop"
        ),
    }


def _bbox(value: Any) -> list[float] | None:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(
            not isinstance(item, (int, float))
            or isinstance(item, bool)
            or not math.isfinite(float(item))
            for item in value
        )
    ):
        return None
    result = [float(item) for item in value]
    if result[2] <= result[0] or result[3] <= result[1]:
        return None
    return result


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
