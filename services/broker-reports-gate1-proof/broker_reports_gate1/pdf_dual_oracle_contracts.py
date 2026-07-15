from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest
from .pdf_hybrid_contracts import sha256_json, validate_binding_output_shape


PDF_PARSER_OBSERVATION_SCHEMA = "broker_reports_pdf_parser_observation_v1"
PDF_VLM_TOPOLOGY_HYPOTHESIS_SCHEMA = (
    "broker_reports_pdf_vlm_topology_hypothesis_v1"
)
PDF_VLM_TOPOLOGY_HYPOTHESIS_SET_SCHEMA = (
    "broker_reports_pdf_vlm_topology_hypothesis_set_v1"
)
PDF_DUAL_ORACLE_CONTINUATION_FRAGMENT_EVIDENCE_SCHEMA = (
    "broker_reports_pdf_dual_oracle_continuation_fragment_evidence_v1"
)
PDF_DUAL_ORACLE_REPEAT_HISTORY_SCHEMA = (
    "broker_reports_pdf_dual_oracle_repeat_history_v1"
)
PDF_DUAL_ORACLE_REPEAT_HISTORY_EVENT_SCHEMA = (
    "broker_reports_pdf_dual_oracle_repeat_history_event_v1"
)
PDF_DUAL_ORACLE_CONTINUATION_CONTRACT_SCHEMA = (
    "broker_reports_pdf_hybrid_continuation_contract_v2"
)
PDF_DUAL_ORACLE_CONTRACT_POLICY_VERSION = "pdf_dual_oracle_contract_policy_v1"

FACTORY_REQUIRED = (
    "PdfDualOracleContractFactory.create is the only parser-observation and "
    "VLM-topology contract entrypoint"
)
FORBIDDEN = (
    "Parser observations must not claim row/column semantics; VLM hypotheses "
    "must not contain values, source refs, checksums, or business facts"
)

_FORBIDDEN_PARSER_KEYS = {
    "expected_row_ordinal",
    "expected_column_ordinal",
    "row_count",
    "column_count",
    "cell_inventory",
}
_FORBIDDEN_VLM_KEYS = {
    "value",
    "values",
    "text",
    "amount",
    "currency_value",
    "tax_value",
    "source_value_ref",
    "source_value_refs",
    "word_ref",
    "word_refs",
    "checksum",
    "candidate_checksum",
    "business_fact",
}
_GEOMETRY_KINDS = {
    "not_observed",
    "normalized_boundaries",
    "consensus_normalized_boundaries",
}
_DECISIONS = {"bound", "ambiguous", "unsupported"}
_ROW_KINDS = {
    "header",
    "column_numbers",
    "data",
    "section",
    "subtotal",
    "total",
    "unknown",
}
_TOPOLOGY_INPUT_BASES = {
    "visual_crop_without_parser_grid",
    "parser_seeded_grid",
    "legacy_candidate_placement_only",
    "unknown",
}
_TOPOLOGY_DIMENSION_SOURCES = {
    "vlm_visual_observation",
    "parser_seeded",
    "not_observed",
    "unknown",
}
_ALTERNATIVE_GENERATION_CONTRACTS = {
    "explicit_exhaustive_bounded_alternatives",
    "single_response_only",
    "legacy_repeated_response",
    "unknown",
}
_EXECUTION_MODES = {"whole_table", "vertical_atom_windows"}
_REPEATED_HEADER_POLICIES = {"source_header", "no_repeated_header"}
_REPEAT_HISTORY_TERMINALS = {
    "accepted_unique_consensus",
    "ambiguous_multiple_consensus",
    "parser_vlm_conflict",
    "no_valid_consensus",
    "human_review_required",
    "unsupported",
}
_FACTORY_TOKEN = object()

_PARSER_OBSERVATION_KEYS = {
    "schema_version",
    "policy_version",
    "observation_id",
    "document_ref",
    "pdf_sha256",
    "page_ref",
    "page_number",
    "table_ref",
    "coordinate_space",
    "candidate_construction",
    "candidate_order",
    "candidates",
    "words",
    "lines",
    "ordering_evidence",
    "duplicate_value_ambiguities",
    "vector_line_signals",
    "source_accounting",
    "observation_checksum",
}
_CANDIDATE_KEYS = {
    "candidate_id",
    "exact_visible_value",
    "exact_visible_value_checksum",
    "source_value_refs",
    "word_refs",
    "bbox",
    "source_bbox_refs",
    "source_text_checksum_refs",
    "source_order",
    "candidate_observation_checksum",
}
_WORD_KEYS = {
    "word_ref",
    "exact_visible_value",
    "source_value_ref",
    "source_text_checksum_ref",
    "bbox_ref",
    "bbox",
    "geometry_reading_order",
    "word_observation_checksum",
}
_LINE_KEYS = {
    "line_ref",
    "exact_visible_value",
    "source_value_ref",
    "source_text_checksum_ref",
    "bbox",
    "word_refs",
    "line_observation_checksum",
}
_HYPOTHESIS_SET_KEYS = {
    "schema_version",
    "policy_version",
    "hypothesis_set_id",
    "parser_observation_id",
    "parser_observation_checksum",
    "table_ref",
    "candidate_ids",
    "model_context",
    "hypotheses",
    "rejected_evidence",
    "alternative_topologies_explicit",
    "reference_answer_used",
    "authoritative_values_present",
    "hypothesis_set_checksum",
}
_HYPOTHESIS_KEYS = {
    "schema_version",
    "hypothesis_id",
    "decision",
    "row_count",
    "column_count",
    "header_rows",
    "header_hierarchy",
    "rows",
    "spans",
    "proposed_geometry",
    "continuation",
    "uncertainty_codes",
    "evidence",
    "candidate_id_only",
    "authoritative_values_present",
    "canonical_grid_checksum",
    "topology_checksum",
    "hypothesis_checksum",
}
_HYPOTHESIS_EVIDENCE_KEYS = {
    "attempt_id",
    "attempt_number",
    "evidence_revision",
    "provider",
    "model",
    "provider_config_hash",
    "binding_output_hash",
    "package_ids",
    "packages",
}
_ROW_KEYS = {"row_ordinal", "row_kind", "cells"}
_GEOMETRY_KEYS = {"rows", "columns"}
_GEOMETRY_AXIS_KEYS = {"kind", "boundaries"}
_CONTINUATION_KEYS = {
    "required",
    "continuation_group_id",
    "fragment_order",
    "fragment_count",
    "shared_column_count",
    "repeated_header_policy",
}
_EVIDENCE_PACKAGE_KEYS = {
    "package_id",
    "crop_sha256",
    "candidate_dictionary_hash",
}
_MODEL_CONTEXT_KEYS = {
    "provider",
    "model",
    "configuration_hash",
    "bounded_row_windows",
    "provider_calls_replayed",
    "new_provider_calls",
    "execution_mode",
    "window_count",
    "raw_provider_calls",
    "stitched_oracle_observations",
    "window_lineage_checksum",
    "topology_input_basis",
    "topology_dimensions_source",
    "alternative_generation_contract",
    "topology_prompt_contract_hash",
    "crop_manifest_hash",
    "observed_image_bytes",
    "maximum_image_bytes",
    "observed_output_tokens",
    "maximum_output_tokens",
    "image_and_output_budgets_attested",
    "provider_token_accounting_exact",
    "candidate_ownership_exact",
    "no_silent_truncation",
    "column_splitting_used",
    "hidden_provider_failover",
    "topology_dimensions_independently_observed",
    "alternative_topology_hypotheses_complete",
    "context_guard_attested",
}
_CONTINUATION_FRAGMENT_EVIDENCE_KEYS = {
    "schema_version",
    "policy_version",
    "fragment_evidence_id",
    "table_ref",
    "fragment_order",
    "page_number",
    "repeated_header_policy",
    "consensus_result_checksum",
    "canonical_grid_checksum",
    "parser_observation_id",
    "parser_observation_checksum",
    "binding_checksum",
    "row_count",
    "column_count",
    "header_rows",
    "header_hierarchy",
    "rows",
    "spans",
    "candidate_ids",
    "candidate_ownership_exact",
    "fragment_evidence_checksum",
}
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
_CONTINUATION_CONTRACT_FRAGMENT_KEYS = {
    "fragment_order",
    "page_number",
    "table_ref",
    "repeated_header_policy",
}
_CONTINUATION_EVIDENCE_ROW_KEYS = {
    "row_ordinal",
    "row_kind",
    "cells",
    "row_content_checksum",
}
_REPEAT_HISTORY_SCOPE_LEGACY_KEYS = {
    "parser_observation_checksum",
    "provider",
    "model",
    "configuration_hash",
    "crop_manifest_hash",
    "solver_version",
}
_REPEAT_HISTORY_SCOPE_KEYS = {
    *_REPEAT_HISTORY_SCOPE_LEGACY_KEYS,
    "runtime_policy_version",
    "execution_mode",
    "window_policy_version",
    "window_plan_hash",
}
_REPEAT_HISTORY_KEYS = {
    "schema_version",
    "policy_version",
    "history_id",
    "scope",
    "scope_checksum",
    "events",
    "ever_conflicted",
    "latest_event_checksum",
    "history_checksum",
}
_REPEAT_HISTORY_EVENT_KEYS = {
    "schema_version",
    "sequence",
    "event_id",
    "previous_event_checksum",
    "prior_history_checksum",
    "attempt_id",
    "attempt_number",
    "evidence_revision",
    "canonical_grid_checksum",
    "topology_checksum",
    "terminal_status",
    "conflict_observed",
    "event_checksum",
}


class PdfDualOracleContractError(ValueError):
    def __init__(self, code: str, subject: str = "") -> None:
        self.code = code
        self.subject = subject
        super().__init__(code if not subject else f"{code}:{subject}")


@dataclass(frozen=True)
class PdfDualOracleContractConfig:
    policy_version: str = PDF_DUAL_ORACLE_CONTRACT_POLICY_VERSION
    maximum_candidates: int = 2048
    maximum_words: int = 12000
    maximum_lines: int = 4096
    maximum_hypotheses: int = 16
    maximum_grid_positions: int = 4096
    maximum_parser_observation_bytes: int = 16 * 1024 * 1024
    maximum_hypothesis_set_bytes: int = 8 * 1024 * 1024


class PdfDualOracleContractFactory:
    def __init__(self, config: PdfDualOracleContractConfig | None = None) -> None:
        self.config = config or PdfDualOracleContractConfig()

    def create(self) -> "PdfDualOracleContractRuntime":
        if self.config.policy_version != PDF_DUAL_ORACLE_CONTRACT_POLICY_VERSION:
            raise PdfDualOracleContractError("pdf_dual_oracle_contract_policy_invalid")
        if min(
            self.config.maximum_candidates,
            self.config.maximum_words,
            self.config.maximum_lines,
            self.config.maximum_hypotheses,
            self.config.maximum_grid_positions,
        ) < 1:
            raise PdfDualOracleContractError("pdf_dual_oracle_contract_budget_invalid")
        return PdfDualOracleContractRuntime(self.config, _factory_token=_FACTORY_TOKEN)


class PdfDualOracleContractRuntime:
    def __init__(
        self,
        config: PdfDualOracleContractConfig,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise PdfDualOracleContractError(
                "pdf_dual_oracle_contract_factory_required"
            )
        self.config = config

    def build_continuation_contract(
        self,
        *,
        continuation_group_id: str,
        fragments: list[dict[str, Any]],
        shared_column_count: int,
        subtotal_policy: str = "preserve_fragment_subtotals",
        duplicate_row_policy: str = "forbid",
    ) -> dict[str, Any]:
        """Build the only supported two-fragment continuation join contract.

        The fragment order is intentionally caller-visible and exact: the input
        must already be ordered ``1, 2`` and the pages must strictly increase.
        This prevents a later solver from silently sorting or guessing a join.
        """

        if (
            not _nonempty_string(continuation_group_id)
            or not _integer_at_least(shared_column_count, 1)
            or isinstance(shared_column_count, bool)
            or not isinstance(fragments, list)
            or len(fragments) != 2
            or any(
                not isinstance(fragment, dict)
                or set(fragment) != _CONTINUATION_CONTRACT_FRAGMENT_KEYS
                for fragment in fragments
            )
        ):
            raise PdfDualOracleContractError(
                "pdf_dual_oracle_continuation_contract_invalid"
            )
        normalized_fragments = [copy.deepcopy(fragment) for fragment in fragments]
        if [fragment.get("fragment_order") for fragment in normalized_fragments] != [
            1,
            2,
        ]:
            raise PdfDualOracleContractError(
                "pdf_dual_oracle_continuation_fragment_order_invalid"
            )
        pages = [fragment.get("page_number") for fragment in normalized_fragments]
        table_refs = [fragment.get("table_ref") for fragment in normalized_fragments]
        if (
            not all(_integer_at_least(page, 1) for page in pages)
            or pages[0] >= pages[1]
            or not all(_nonempty_string(table_ref) for table_ref in table_refs)
            or len(set(table_refs)) != 2
            or any(
                fragment.get("repeated_header_policy")
                not in _REPEATED_HEADER_POLICIES
                for fragment in normalized_fragments
            )
        ):
            raise PdfDualOracleContractError(
                "pdf_dual_oracle_continuation_fragment_identity_invalid"
            )
        if subtotal_policy not in {
            "preserve_fragment_subtotals",
            "deduplicate_exact_boundary_subtotal",
        }:
            raise PdfDualOracleContractError(
                "pdf_dual_oracle_continuation_subtotal_policy_invalid"
            )
        if duplicate_row_policy not in {
            "forbid",
            "allow_explicit_repeated_header_only",
        }:
            raise PdfDualOracleContractError(
                "pdf_dual_oracle_continuation_duplicate_policy_invalid"
            )
        contract = {
            "schema_version": PDF_DUAL_ORACLE_CONTINUATION_CONTRACT_SCHEMA,
            "continuation_group_id": continuation_group_id,
            "shared_column_count": shared_column_count,
            "fragments": normalized_fragments,
            "subtotal_policy": subtotal_policy,
            "duplicate_row_policy": duplicate_row_policy,
            "fragment_coverage_required": True,
            "joined_coverage_required": True,
            "authoritative": False,
        }
        if set(contract) != _CONTINUATION_CONTRACT_KEYS:
            raise PdfDualOracleContractError(
                "pdf_dual_oracle_continuation_contract_invalid"
            )
        return contract

    def build_parser_observation(
        self,
        *,
        compact_ledger: dict[str, Any],
        pdf_text_layer_projection: dict[str, Any],
    ) -> dict[str, Any]:
        dictionary = _object(compact_ledger.get("private_candidate_dictionary"))
        candidate_order = [str(item) for item in compact_ledger.get("candidate_order") or []]
        if not candidate_order or set(candidate_order) != set(dictionary):
            raise PdfDualOracleContractError(
                "pdf_parser_observation_candidate_scope_invalid"
            )
        if len(candidate_order) > self.config.maximum_candidates:
            raise PdfDualOracleContractError(
                "pdf_parser_observation_candidate_budget_exceeded"
            )

        table_bbox = _bbox(compact_ledger.get("table_bbox"))
        if table_bbox is None:
            raise PdfDualOracleContractError("pdf_parser_observation_table_bbox_invalid")
        page_ref = str(compact_ledger.get("page_ref") or "")
        bbox_by_ref = {
            str(item.get("bbox_ref") or ""): _bbox(item.get("bbox"))
            for item in _dicts(pdf_text_layer_projection.get("bbox_inventory"))
            if item.get("bbox_ref")
        }
        words_by_ref = {
            str(item.get("word_ref") or ""): item
            for item in _dicts(pdf_text_layer_projection.get("word_inventory"))
            if item.get("page_ref") == page_ref and item.get("word_ref")
        }

        candidates: list[dict[str, Any]] = []
        word_observations: dict[str, dict[str, Any]] = {}
        for candidate_id in candidate_order:
            source = _object(dictionary.get(candidate_id))
            source_bbox = _bbox(source.get("source_bbox"))
            word_refs = [str(item) for item in source.get("word_refs") or []]
            source_refs = [str(item) for item in source.get("source_value_refs") or []]
            if source_bbox is None or not word_refs or len(word_refs) != len(set(word_refs)):
                raise PdfDualOracleContractError(
                    "pdf_parser_observation_candidate_geometry_invalid", candidate_id
                )
            if len(source_refs) != len(word_refs):
                raise PdfDualOracleContractError(
                    "pdf_parser_observation_candidate_source_ref_invalid", candidate_id
                )
            for word_ref in word_refs:
                word = _object(words_by_ref.get(word_ref))
                word_bbox = bbox_by_ref.get(str(word.get("bbox_ref") or ""))
                if not word or word_bbox is None:
                    raise PdfDualOracleContractError(
                        "pdf_parser_observation_word_missing", word_ref
                    )
                record = {
                    "word_ref": word_ref,
                    "exact_visible_value": str(word.get("text") or ""),
                    "source_value_ref": str(word.get("source_value_ref") or ""),
                    "source_text_checksum_ref": str(
                        word.get("text_checksum_ref") or ""
                    ),
                    "bbox_ref": str(word.get("bbox_ref") or ""),
                    "bbox": word_bbox,
                    "geometry_reading_order": int(
                        word.get("geometry_reading_order") or 0
                    ),
                }
                record["word_observation_checksum"] = sha256_json(record)
                word_observations[word_ref] = record
            candidate = {
                "candidate_id": candidate_id,
                "exact_visible_value": str(source.get("exact_source_span") or ""),
                "exact_visible_value_checksum": sha256_json(
                    str(source.get("exact_source_span") or "")
                ),
                "source_value_refs": source_refs,
                "word_refs": word_refs,
                "bbox": source_bbox,
                "source_bbox_refs": [
                    str(item) for item in source.get("source_bbox_refs") or []
                ],
                "source_text_checksum_refs": [
                    str(item)
                    for item in source.get("source_text_checksum_refs") or []
                ],
                "source_order": int(source.get("source_order") or 0),
            }
            candidate["candidate_observation_checksum"] = sha256_json(candidate)
            candidates.append(candidate)

        if len(word_observations) > self.config.maximum_words:
            raise PdfDualOracleContractError("pdf_parser_observation_word_budget_exceeded")
        owned_words = set(word_observations)
        lines = []
        for line in _dicts(pdf_text_layer_projection.get("line_inventory")):
            line_word_refs = [str(item) for item in line.get("word_refs") or []]
            if line.get("page_ref") != page_ref or not (set(line_word_refs) & owned_words):
                continue
            line_bbox = bbox_by_ref.get(str(line.get("bbox_ref") or ""))
            if line_bbox is None or not _overlaps(line_bbox, table_bbox):
                continue
            record = {
                "line_ref": str(line.get("line_ref") or ""),
                "exact_visible_value": str(line.get("text") or ""),
                "source_value_ref": str(line.get("source_value_ref") or ""),
                "source_text_checksum_ref": str(
                    line.get("text_checksum_ref") or ""
                ),
                "bbox": line_bbox,
                "word_refs": [item for item in line_word_refs if item in owned_words],
            }
            record["line_observation_checksum"] = sha256_json(record)
            lines.append(record)
        if len(lines) > self.config.maximum_lines:
            raise PdfDualOracleContractError("pdf_parser_observation_line_budget_exceeded")

        duplicate_groups = _duplicate_groups(candidates)

        geometry_order = [
            str(item["candidate_id"])
            for item in sorted(
                candidates,
                key=lambda item: (
                    float(item["bbox"][1]),
                    float(item["bbox"][0]),
                    int(item["source_order"]),
                ),
            )
        ]
        candidate_construction = {
            "kind": "legacy_compact_ledger_candidate_groups",
            "semantic_grid_dependency": True,
            "source_ledger_checksum": str(
                compact_ledger.get("ledger_checksum") or ""
            ),
            "source_candidate_dictionary_hash": str(
                compact_ledger.get("candidate_dictionary_hash") or ""
            ),
            "word_atoms_exactly_once": True,
        }
        result = {
            "schema_version": PDF_PARSER_OBSERVATION_SCHEMA,
            "policy_version": self.config.policy_version,
            "observation_id": "pdfparserobs_"
            + stable_digest(
                [
                    compact_ledger.get("pdf_sha256"),
                    compact_ledger.get("table_ref"),
                    compact_ledger.get("ledger_checksum"),
                    self.config.policy_version,
                ],
                length=24,
            ),
            "document_ref": compact_ledger.get("document_ref"),
            "pdf_sha256": compact_ledger.get("pdf_sha256"),
            "page_ref": page_ref,
            "page_number": int(compact_ledger.get("page_number") or 0),
            "table_ref": compact_ledger.get("table_ref"),
            "coordinate_space": {
                "unit": "pdf_point",
                "origin": "top_left",
                "x_axis": "right",
                "y_axis": "down",
                "table_bbox": table_bbox,
            },
            "candidate_construction": candidate_construction,
            "candidate_order": candidate_order,
            "candidates": candidates,
            "words": [word_observations[key] for key in sorted(word_observations)],
            "lines": sorted(
                lines,
                key=lambda item: (
                    float(item["bbox"][1]),
                    float(item["bbox"][0]),
                    str(item["line_ref"]),
                ),
            ),
            "ordering_evidence": {
                "kind": "parser_geometry_reading_order",
                "candidate_ids": candidate_order,
                "geometry_sorted_candidate_ids": geometry_order,
                "candidate_order_matches_geometry_sort": (
                    candidate_order == geometry_order
                ),
            },
            "duplicate_value_ambiguities": duplicate_groups,
            "vector_line_signals": {
                "included": False,
                "reason_code": "pdf_dual_oracle_vectors_not_material_to_v1_solver",
                "signals": [],
            },
            "source_accounting": {
                "candidates": len(candidates),
                "candidate_ids_unique": len(set(candidate_order)),
                "words": len(word_observations),
                "word_refs_unique": len(word_observations),
                "lines": len(lines),
                "exactly_once_candidate_ownership": True,
                "semantic_grid_claimed": False,
            },
        }
        result["observation_checksum"] = sha256_json(result)
        errors = self.validate_parser_observation(result)
        if errors:
            raise PdfDualOracleContractError(errors[0])
        return result

    def build_parser_observation_from_word_atoms(
        self,
        *,
        document_ref: str,
        pdf_sha256: str,
        page_ref: str,
        page_number: int,
        table_ref: str,
        table_bbox: list[float],
        pdf_text_layer_projection: dict[str, Any],
        scope_word_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        """Build the topology-neutral contract directly from immutable word atoms.

        This is the only construction mode eligible for automatic consensus in
        v1.  The legacy compact-ledger adapter remains available for replay, but
        its parser-cell grouping lineage is preserved and forces review.
        """

        scope = _bbox(table_bbox)
        if scope is None or not document_ref or not pdf_sha256 or not page_ref:
            raise PdfDualOracleContractError(
                "pdf_parser_observation_word_atom_scope_invalid"
            )
        bbox_by_ref = {
            str(item.get("bbox_ref") or ""): _bbox(item.get("bbox"))
            for item in _dicts(pdf_text_layer_projection.get("bbox_inventory"))
            if item.get("bbox_ref")
        }
        requested = (
            set(str(item) for item in scope_word_refs)
            if scope_word_refs is not None
            else None
        )
        selected: list[tuple[dict[str, Any], list[float]]] = []
        for word in _dicts(pdf_text_layer_projection.get("word_inventory")):
            word_ref = str(word.get("word_ref") or "")
            bbox = bbox_by_ref.get(str(word.get("bbox_ref") or ""))
            if (
                word.get("page_ref") != page_ref
                or not word_ref
                or bbox is None
                or not _contained(bbox, scope)
                or (requested is not None and word_ref not in requested)
            ):
                continue
            selected.append((word, bbox))
        if requested is not None and {str(item[0].get("word_ref")) for item in selected} != requested:
            raise PdfDualOracleContractError(
                "pdf_parser_observation_word_atom_scope_incomplete"
            )
        selected.sort(
            key=lambda item: (
                int(item[0].get("geometry_reading_order") or 0),
                float(item[1][1]),
                float(item[1][0]),
                str(item[0].get("word_ref") or ""),
            )
        )
        if not selected:
            raise PdfDualOracleContractError(
                "pdf_parser_observation_word_atom_scope_empty"
            )

        dictionary: dict[str, dict[str, Any]] = {}
        candidate_order: list[str] = []
        for source_order, (word, bbox) in enumerate(selected):
            word_ref = str(word.get("word_ref") or "")
            candidate_id = "wa_" + stable_digest(
                [pdf_sha256, page_ref, word_ref], length=16
            )
            if candidate_id in dictionary:
                raise PdfDualOracleContractError(
                    "pdf_parser_observation_word_atom_identity_collision"
                )
            dictionary[candidate_id] = {
                "candidate_id": candidate_id,
                "exact_source_span": str(word.get("text") or ""),
                "source_value_refs": [str(word.get("source_value_ref") or "")],
                "word_refs": [word_ref],
                "source_bbox": bbox,
                "source_bbox_refs": [str(word.get("bbox_ref") or "")],
                "source_text_checksum_refs": [
                    str(word.get("text_checksum_ref") or "")
                ],
                "source_order": source_order,
            }
            candidate_order.append(candidate_id)
        pseudo_ledger = {
            "document_ref": document_ref,
            "pdf_sha256": pdf_sha256,
            "page_ref": page_ref,
            "page_number": page_number,
            "table_ref": table_ref,
            "table_bbox": scope,
            "candidate_order": candidate_order,
            "private_candidate_dictionary": dictionary,
            "candidate_dictionary_hash": sha256_json(dictionary),
        }
        pseudo_ledger["ledger_checksum"] = sha256_json(pseudo_ledger)
        result = self.build_parser_observation(
            compact_ledger=pseudo_ledger,
            pdf_text_layer_projection=pdf_text_layer_projection,
        )
        result["candidate_construction"] = {
            "kind": "raw_word_atoms",
            "semantic_grid_dependency": False,
            "source_ledger_checksum": None,
            "source_candidate_dictionary_hash": None,
            "word_atoms_exactly_once": True,
        }
        result["observation_id"] = "pdfparserobs_" + stable_digest(
            [
                pdf_sha256,
                table_ref,
                [item["candidate_observation_checksum"] for item in result["candidates"]],
                self.config.policy_version,
            ],
            length=24,
        )
        result.pop("observation_checksum", None)
        result["observation_checksum"] = sha256_json(result)
        errors = self.validate_parser_observation(result)
        if errors:
            raise PdfDualOracleContractError(errors[0])
        return result

    def validate_parser_observation(self, value: Any) -> list[str]:
        data = _object(value)
        errors: list[str] = []
        if data.get("schema_version") != PDF_PARSER_OBSERVATION_SCHEMA:
            errors.append("pdf_parser_observation_schema_invalid")
        if set(data) != _PARSER_OBSERVATION_KEYS:
            errors.append("pdf_parser_observation_keys_invalid")
        if data.get("policy_version") != self.config.policy_version:
            errors.append("pdf_parser_observation_policy_invalid")
        if _recursive_keys(data) & _FORBIDDEN_PARSER_KEYS:
            errors.append("pdf_parser_observation_semantic_grid_forbidden")
        coordinate_space = _object(data.get("coordinate_space"))
        table_bbox = _bbox(coordinate_space.get("table_bbox"))
        if (
            set(coordinate_space)
            != {"unit", "origin", "x_axis", "y_axis", "table_bbox"}
            or coordinate_space.get("unit") != "pdf_point"
            or coordinate_space.get("origin") != "top_left"
            or coordinate_space.get("x_axis") != "right"
            or coordinate_space.get("y_axis") != "down"
            or table_bbox is None
        ):
            errors.append("pdf_parser_observation_coordinate_space_invalid")

        construction = _object(data.get("candidate_construction"))
        if set(construction) != {
            "kind",
            "semantic_grid_dependency",
            "source_ledger_checksum",
            "source_candidate_dictionary_hash",
            "word_atoms_exactly_once",
        }:
            errors.append("pdf_parser_observation_candidate_construction_invalid")
        construction_kind = construction.get("kind")
        if construction_kind == "raw_word_atoms":
            if (
                construction.get("semantic_grid_dependency") is not False
                or construction.get("source_ledger_checksum") is not None
                or construction.get("source_candidate_dictionary_hash") is not None
            ):
                errors.append(
                    "pdf_parser_observation_word_atom_construction_invalid"
                )
        elif construction_kind == "legacy_compact_ledger_candidate_groups":
            if (
                construction.get("semantic_grid_dependency") is not True
                or not construction.get("source_ledger_checksum")
                or not construction.get("source_candidate_dictionary_hash")
            ):
                errors.append(
                    "pdf_parser_observation_legacy_construction_lineage_invalid"
                )
        else:
            errors.append("pdf_parser_observation_candidate_construction_invalid")
        if construction.get("word_atoms_exactly_once") is not True:
            errors.append("pdf_parser_observation_word_atom_accounting_invalid")

        candidates = _dicts(data.get("candidates"))
        candidate_order = [str(item) for item in data.get("candidate_order") or []]
        ids = [str(item.get("candidate_id") or "") for item in candidates]
        if not ids or ids != candidate_order or len(ids) != len(set(ids)):
            errors.append("pdf_parser_observation_candidate_accounting_invalid")
        words = _dicts(data.get("words"))
        word_ids = [str(item.get("word_ref") or "") for item in words]
        if len(word_ids) != len(set(word_ids)):
            errors.append("pdf_parser_observation_word_identity_duplicate")
        word_by_id = {
            str(item.get("word_ref") or ""): item for item in words
        }
        word_set = set(word_by_id)
        for word in words:
            if set(word) != _WORD_KEYS:
                errors.append("pdf_parser_observation_word_keys_invalid")
            word_copy = dict(word)
            stored = word_copy.pop("word_observation_checksum", None)
            bbox = _bbox(word.get("bbox"))
            if (
                stored != sha256_json(word_copy)
                or bbox is None
                or (table_bbox is not None and not _contained(bbox, table_bbox))
                or not word.get("word_ref")
                or not word.get("source_value_ref")
                or not word.get("source_text_checksum_ref")
                or not word.get("bbox_ref")
                or not isinstance(word.get("geometry_reading_order"), int)
            ):
                errors.append("pdf_parser_observation_word_contract_invalid")
        used_words: list[str] = []
        for expected_order, candidate in enumerate(candidates):
            if set(candidate) != _CANDIDATE_KEYS:
                errors.append("pdf_parser_observation_candidate_keys_invalid")
            candidate_copy = dict(candidate)
            stored = candidate_copy.pop("candidate_observation_checksum", None)
            if stored != sha256_json(candidate_copy):
                errors.append("pdf_parser_observation_candidate_checksum_invalid")
            bbox = _bbox(candidate.get("bbox"))
            if bbox is None or (table_bbox is not None and not _contained(bbox, table_bbox)):
                errors.append("pdf_parser_observation_candidate_bbox_invalid")
            refs = [str(item) for item in candidate.get("word_refs") or []]
            if not refs or not set(refs) <= word_set:
                errors.append("pdf_parser_observation_candidate_word_scope_invalid")
            selected_words = [word_by_id.get(ref, {}) for ref in refs]
            expected_bbox = _bbox_union(
                [
                    current
                    for current in (_bbox(item.get("bbox")) for item in selected_words)
                    if current is not None
                ]
            )
            expected_value = " ".join(
                str(item.get("exact_visible_value") or "")
                for item in selected_words
            )
            if (
                expected_bbox != bbox
                or candidate.get("exact_visible_value") != expected_value
                or candidate.get("exact_visible_value_checksum")
                != sha256_json(expected_value)
                or [str(item.get("source_value_ref") or "") for item in selected_words]
                != [str(item) for item in candidate.get("source_value_refs") or []]
                or [str(item.get("bbox_ref") or "") for item in selected_words]
                != [str(item) for item in candidate.get("source_bbox_refs") or []]
                or [
                    str(item.get("source_text_checksum_ref") or "")
                    for item in selected_words
                ]
                != [
                    str(item)
                    for item in candidate.get("source_text_checksum_refs") or []
                ]
                or candidate.get("source_order") != expected_order
            ):
                errors.append("pdf_parser_observation_candidate_derivation_invalid")
            if construction_kind == "raw_word_atoms" and len(refs) != 1:
                errors.append("pdf_parser_observation_word_atom_grouping_invalid")
            used_words.extend(refs)
        if set(used_words) != word_set or len(used_words) != len(set(used_words)):
            errors.append("pdf_parser_observation_word_ownership_invalid")

        lines = _dicts(data.get("lines"))
        line_ids: list[str] = []
        for line in lines:
            line_ids.append(str(line.get("line_ref") or ""))
            line_copy = dict(line)
            stored = line_copy.pop("line_observation_checksum", None)
            if (
                set(line) != _LINE_KEYS
                or not line.get("line_ref")
                or stored != sha256_json(line_copy)
                or _bbox(line.get("bbox")) is None
                or not set(str(item) for item in line.get("word_refs") or [])
                <= word_set
            ):
                errors.append("pdf_parser_observation_line_contract_invalid")
        if len(line_ids) != len(set(line_ids)):
            errors.append("pdf_parser_observation_line_identity_duplicate")

        expected_duplicates = _duplicate_groups(candidates)
        if data.get("duplicate_value_ambiguities") != expected_duplicates:
            errors.append("pdf_parser_observation_duplicate_derivation_invalid")
        expected_geometry_order = [
            str(item["candidate_id"])
            for item in sorted(
                candidates,
                key=lambda item: (
                    float(item["bbox"][1]),
                    float(item["bbox"][0]),
                    int(item["source_order"]),
                ),
            )
        ] if all(_bbox(item.get("bbox")) is not None for item in candidates) else []
        expected_ordering = {
            "kind": "parser_geometry_reading_order",
            "candidate_ids": candidate_order,
            "geometry_sorted_candidate_ids": expected_geometry_order,
            "candidate_order_matches_geometry_sort": (
                candidate_order == expected_geometry_order
            ),
        }
        if data.get("ordering_evidence") != expected_ordering:
            errors.append("pdf_parser_observation_ordering_derivation_invalid")
        expected_accounting = {
            "candidates": len(candidates),
            "candidate_ids_unique": len(set(candidate_order)),
            "words": len(words),
            "word_refs_unique": len(word_set),
            "lines": len(lines),
            "exactly_once_candidate_ownership": (
                set(used_words) == word_set
                and len(used_words) == len(set(used_words))
            ),
            "semantic_grid_claimed": False,
        }
        if data.get("source_accounting") != expected_accounting:
            errors.append("pdf_parser_observation_source_accounting_invalid")
        if data.get("vector_line_signals") != {
            "included": False,
            "reason_code": "pdf_dual_oracle_vectors_not_material_to_v1_solver",
            "signals": [],
        }:
            errors.append("pdf_parser_observation_vector_signal_contract_invalid")

        expected_observation_id = "pdfparserobs_" + stable_digest(
            (
                [
                    data.get("pdf_sha256"),
                    data.get("table_ref"),
                    construction.get("source_ledger_checksum"),
                    self.config.policy_version,
                ]
                if construction_kind == "legacy_compact_ledger_candidate_groups"
                else [
                    data.get("pdf_sha256"),
                    data.get("table_ref"),
                    [item.get("candidate_observation_checksum") for item in candidates],
                    self.config.policy_version,
                ]
            ),
            length=24,
        )
        if data.get("observation_id") != expected_observation_id:
            errors.append("pdf_parser_observation_identity_invalid")
        copy_without_checksum = dict(data)
        stored_checksum = copy_without_checksum.pop("observation_checksum", None)
        if stored_checksum != sha256_json(copy_without_checksum):
            errors.append("pdf_parser_observation_checksum_invalid")
        if len(_json_bytes(data)) > self.config.maximum_parser_observation_bytes:
            errors.append("pdf_parser_observation_byte_budget_exceeded")
        return sorted(set(errors))

    def build_continuation_fragment_evidence(
        self,
        *,
        parser_observation: dict[str, Any],
        consensus_result: dict[str, Any],
        binding_output: dict[str, Any],
        fragment_order: int,
        page_number: int,
        repeated_header_policy: str,
    ) -> dict[str, Any]:
        parser_errors = self.validate_parser_observation(parser_observation)
        if parser_errors:
            raise PdfDualOracleContractError(parser_errors[0])
        if (
            not _integer_at_least(fragment_order, 1)
            or not _integer_at_least(page_number, 1)
            or repeated_header_policy not in _REPEATED_HEADER_POLICIES
        ):
            raise PdfDualOracleContractError(
                "pdf_dual_oracle_continuation_fragment_identity_invalid"
            )
        result_copy = dict(consensus_result) if isinstance(consensus_result, dict) else {}
        result_checksum = result_copy.pop("result_checksum", None)
        if (
            result_checksum != sha256_json(result_copy)
            or consensus_result.get("terminal_status")
            != "accepted_unique_consensus"
            or consensus_result.get("uniqueness_proven") is not True
            or consensus_result.get("solver_search_complete") is not True
            or consensus_result.get("table_ref") != parser_observation.get("table_ref")
        ):
            raise PdfDualOracleContractError(
                "pdf_dual_oracle_continuation_consensus_result_invalid"
            )
        shape_errors = validate_binding_output_shape(binding_output)
        if shape_errors or binding_output.get("decision") != "bound":
            raise PdfDualOracleContractError(
                "pdf_dual_oracle_continuation_binding_invalid"
            )
        projection = {
            key: copy.deepcopy(binding_output.get(key))
            for key in (
                "row_count",
                "column_count",
                "header_rows",
                "header_hierarchy",
                "rows",
                "spans",
            )
        }
        canonical_grid_checksum = sha256_json(projection)
        if consensus_result.get("canonical_grid_checksum") != canonical_grid_checksum:
            raise PdfDualOracleContractError(
                "pdf_dual_oracle_continuation_grid_checksum_mismatch"
            )
        candidates = {
            str(item.get("candidate_id") or ""): item
            for item in _dicts(parser_observation.get("candidates"))
        }
        candidate_order = [
            str(item) for item in parser_observation.get("candidate_order") or []
        ]
        used = [
            str(candidate_id)
            for row in _dicts(binding_output.get("rows"))
            for cell in row.get("cells") or []
            if isinstance(cell, list)
            for candidate_id in cell
        ]
        if (
            set(used) != set(candidate_order)
            or len(used) != len(set(used))
            or set(candidates) != set(candidate_order)
        ):
            raise PdfDualOracleContractError(
                "pdf_dual_oracle_continuation_candidate_ownership_invalid"
            )
        rows = []
        for row in _dicts(binding_output.get("rows")):
            cells = copy.deepcopy(row.get("cells") or [])
            value_checksum_grid = [
                [
                    str(candidates[candidate_id].get("exact_visible_value_checksum") or "")
                    for candidate_id in cell
                ]
                for cell in cells
            ]
            if any(not checksum for cell in value_checksum_grid for checksum in cell):
                raise PdfDualOracleContractError(
                    "pdf_dual_oracle_continuation_candidate_provenance_invalid"
                )
            rows.append(
                {
                    "row_ordinal": row.get("row_ordinal"),
                    "row_kind": row.get("row_kind"),
                    "cells": cells,
                    "row_content_checksum": sha256_json(value_checksum_grid),
                }
            )
        evidence = {
            "schema_version": PDF_DUAL_ORACLE_CONTINUATION_FRAGMENT_EVIDENCE_SCHEMA,
            "policy_version": self.config.policy_version,
            "fragment_evidence_id": "pdfdualfrag_"
            + stable_digest(
                [
                    parser_observation.get("observation_checksum"),
                    result_checksum,
                    canonical_grid_checksum,
                    fragment_order,
                    page_number,
                    repeated_header_policy,
                ],
                length=24,
            ),
            "table_ref": parser_observation.get("table_ref"),
            "fragment_order": fragment_order,
            "page_number": page_number,
            "repeated_header_policy": repeated_header_policy,
            "consensus_result_checksum": result_checksum,
            "canonical_grid_checksum": canonical_grid_checksum,
            "parser_observation_id": parser_observation.get("observation_id"),
            "parser_observation_checksum": parser_observation.get(
                "observation_checksum"
            ),
            "binding_checksum": sha256_json(binding_output),
            "row_count": binding_output.get("row_count"),
            "column_count": binding_output.get("column_count"),
            "header_rows": copy.deepcopy(binding_output.get("header_rows") or []),
            "header_hierarchy": copy.deepcopy(
                binding_output.get("header_hierarchy") or []
            ),
            "rows": rows,
            "spans": copy.deepcopy(binding_output.get("spans") or []),
            "candidate_ids": candidate_order,
            "candidate_ownership_exact": True,
        }
        evidence["fragment_evidence_checksum"] = sha256_json(evidence)
        errors = self.validate_continuation_fragment_evidence(evidence)
        if errors:
            raise PdfDualOracleContractError(errors[0])
        return evidence

    def validate_continuation_fragment_evidence(self, value: Any) -> list[str]:
        if not isinstance(value, dict):
            return ["pdf_dual_oracle_continuation_fragment_evidence_not_object"]
        data = value
        errors: list[str] = []
        if (
            set(data) != _CONTINUATION_FRAGMENT_EVIDENCE_KEYS
            or data.get("schema_version")
            != PDF_DUAL_ORACLE_CONTINUATION_FRAGMENT_EVIDENCE_SCHEMA
            or data.get("policy_version") != self.config.policy_version
        ):
            errors.append("pdf_dual_oracle_continuation_fragment_evidence_contract_invalid")
        if (
            not _nonempty_string(data.get("fragment_evidence_id"))
            or not _nonempty_string(data.get("table_ref"))
            or not _integer_at_least(data.get("fragment_order"), 1)
            or not _integer_at_least(data.get("page_number"), 1)
            or data.get("repeated_header_policy") not in _REPEATED_HEADER_POLICIES
            or not _nonempty_string(data.get("consensus_result_checksum"))
            or not _nonempty_string(data.get("canonical_grid_checksum"))
            or not _nonempty_string(data.get("parser_observation_id"))
            or not _nonempty_string(data.get("parser_observation_checksum"))
            or not _nonempty_string(data.get("binding_checksum"))
        ):
            errors.append("pdf_dual_oracle_continuation_fragment_identity_invalid")
        rows = data.get("row_count")
        columns = data.get("column_count")
        row_items = _dicts(data.get("rows"))
        candidate_ids = data.get("candidate_ids")
        if (
            not _integer_at_least(rows, 1)
            or not _integer_at_least(columns, 1)
            or not isinstance(data.get("rows"), list)
            or len(row_items) != rows
            or not isinstance(candidate_ids, list)
            or not all(_nonempty_string(item) for item in candidate_ids)
            or len(candidate_ids) != len(set(candidate_ids))
            or data.get("candidate_ownership_exact") is not True
        ):
            errors.append("pdf_dual_oracle_continuation_fragment_shape_invalid")
        used: list[str] = []
        for ordinal, row in enumerate(row_items, start=1):
            cells = row.get("cells")
            if (
                set(row) != _CONTINUATION_EVIDENCE_ROW_KEYS
                or row.get("row_ordinal") != ordinal
                or row.get("row_kind") not in _ROW_KINDS
                or not isinstance(cells, list)
                or len(cells) != columns
                or not _nonempty_string(row.get("row_content_checksum"))
            ):
                errors.append("pdf_dual_oracle_continuation_fragment_row_invalid")
                continue
            for cell in cells:
                if not isinstance(cell, list) or not all(
                    _nonempty_string(item) for item in cell
                ):
                    errors.append(
                        "pdf_dual_oracle_continuation_fragment_cell_invalid"
                    )
                    continue
                used.extend(str(item) for item in cell)
        if (
            isinstance(candidate_ids, list)
            and (
                set(used) != set(candidate_ids)
                or len(used) != len(set(used))
            )
        ):
            errors.append(
                "pdf_dual_oracle_continuation_fragment_candidate_ownership_invalid"
            )
        headers = data.get("header_rows")
        if (
            not isinstance(headers, list)
            or not all(_integer_at_least(item, 1) for item in headers)
            or headers != list(range(1, len(headers) + 1))
            or any(item > rows for item in headers)
        ):
            errors.append("pdf_dual_oracle_continuation_fragment_headers_invalid")
        topology_projection = {
            "row_count": rows,
            "column_count": columns,
            "header_rows": copy.deepcopy(headers),
            "header_hierarchy": copy.deepcopy(data.get("header_hierarchy")),
            "rows": [
                {
                    "row_ordinal": row.get("row_ordinal"),
                    "row_kind": row.get("row_kind"),
                    "cells": copy.deepcopy(row.get("cells")),
                }
                for row in row_items
            ],
            "spans": copy.deepcopy(data.get("spans")),
        }
        topology_errors = _topology_errors(
            {
                **topology_projection,
                "proposed_geometry": {
                    "rows": {"kind": "not_observed", "boundaries": []},
                    "columns": {"kind": "not_observed", "boundaries": []},
                },
            },
            int(rows or 0),
            int(columns or 0),
        )
        errors.extend(topology_errors)
        if data.get("canonical_grid_checksum") != sha256_json(topology_projection):
            errors.append(
                "pdf_dual_oracle_continuation_fragment_grid_checksum_invalid"
            )
        expected_id = "pdfdualfrag_" + stable_digest(
            [
                data.get("parser_observation_checksum"),
                data.get("consensus_result_checksum"),
                data.get("canonical_grid_checksum"),
                data.get("fragment_order"),
                data.get("page_number"),
                data.get("repeated_header_policy"),
            ],
            length=24,
        )
        if data.get("fragment_evidence_id") != expected_id:
            errors.append("pdf_dual_oracle_continuation_fragment_identity_invalid")
        checksum_copy = dict(data)
        stored_checksum = checksum_copy.pop("fragment_evidence_checksum", None)
        if stored_checksum != sha256_json(checksum_copy):
            errors.append(
                "pdf_dual_oracle_continuation_fragment_evidence_checksum_invalid"
            )
        return sorted(set(errors))

    def create_repeat_history(self, *, scope: dict[str, Any]) -> dict[str, Any]:
        normalized_scope = _repeat_history_scope(scope)
        return _repeat_history_value(
            policy_version=self.config.policy_version,
            scope=normalized_scope,
            events=[],
        )

    def append_repeat_history_event(
        self,
        *,
        history: dict[str, Any],
        attempt_id: str,
        attempt_number: int,
        evidence_revision: str,
        canonical_grid_checksum: str | None,
        topology_checksum: str | None,
        terminal_status: str,
        expected_prior_history_checksum: str | None = None,
    ) -> dict[str, Any]:
        errors = self.validate_repeat_history(history)
        if errors:
            raise PdfDualOracleContractError(errors[0])
        if (
            expected_prior_history_checksum is not None
            and history.get("history_checksum")
            != expected_prior_history_checksum
        ):
            raise PdfDualOracleContractError(
                "pdf_dual_oracle_repeat_history_prior_checksum_mismatch"
            )
        if (
            not _nonempty_string(attempt_id)
            or not _integer_at_least(attempt_number, 1)
            or not _nonempty_string(evidence_revision)
            or terminal_status not in _REPEAT_HISTORY_TERMINALS
            or canonical_grid_checksum is not None
            and not _nonempty_string(canonical_grid_checksum)
            or topology_checksum is not None
            and not _nonempty_string(topology_checksum)
            or terminal_status == "accepted_unique_consensus"
            and not _nonempty_string(canonical_grid_checksum)
        ):
            raise PdfDualOracleContractError(
                "pdf_dual_oracle_repeat_history_event_input_invalid"
            )
        events = _dicts(history.get("events"))
        semantic = {
            "attempt_id": attempt_id,
            "attempt_number": attempt_number,
            "evidence_revision": evidence_revision,
            "canonical_grid_checksum": canonical_grid_checksum,
            "topology_checksum": topology_checksum,
            "terminal_status": terminal_status,
        }
        existing = next(
            (item for item in events if item.get("attempt_id") == attempt_id), None
        )
        if existing is not None:
            if any(existing.get(key) != value for key, value in semantic.items()):
                raise PdfDualOracleContractError(
                    "pdf_dual_oracle_repeat_history_attempt_rewrite_forbidden"
                )
            return copy.deepcopy(history)
        if attempt_number != len(events) + 1 or any(
            item.get("attempt_number") == attempt_number for item in events
        ):
            raise PdfDualOracleContractError(
                "pdf_dual_oracle_repeat_history_attempt_sequence_invalid"
            )
        conflict_observed = _repeat_history_conflicted(
            [*events, {**semantic, "conflict_observed": False}]
        )
        event = {
            "schema_version": PDF_DUAL_ORACLE_REPEAT_HISTORY_EVENT_SCHEMA,
            "sequence": len(events) + 1,
            "event_id": "pdfdualrepevent_"
            + stable_digest(
                [history.get("scope_checksum"), attempt_id, attempt_number],
                length=24,
            ),
            "previous_event_checksum": history.get("latest_event_checksum"),
            "prior_history_checksum": history.get("history_checksum"),
            **semantic,
            "conflict_observed": conflict_observed,
        }
        event["event_checksum"] = sha256_json(event)
        appended = _repeat_history_value(
            policy_version=self.config.policy_version,
            scope=_object(history.get("scope")),
            events=[*events, event],
        )
        validation_errors = self.validate_repeat_history(appended)
        if validation_errors:
            raise PdfDualOracleContractError(validation_errors[0])
        return appended

    def validate_repeat_history(self, value: Any) -> list[str]:
        if not isinstance(value, dict):
            return ["pdf_dual_oracle_repeat_history_not_object"]
        data = value
        errors: list[str] = []
        if (
            set(data) != _REPEAT_HISTORY_KEYS
            or data.get("schema_version") != PDF_DUAL_ORACLE_REPEAT_HISTORY_SCHEMA
            or data.get("policy_version") != self.config.policy_version
        ):
            errors.append("pdf_dual_oracle_repeat_history_contract_invalid")
        try:
            scope = _repeat_history_scope(_object(data.get("scope")))
        except PdfDualOracleContractError as exc:
            errors.append(exc.code)
            scope = _object(data.get("scope"))
        events_value = data.get("events")
        events = _dicts(events_value)
        if not isinstance(events_value, list) or len(events) != len(
            events_value if isinstance(events_value, list) else []
        ):
            errors.append("pdf_dual_oracle_repeat_history_events_invalid")
        prefix: list[dict[str, Any]] = []
        seen_attempt_ids: set[str] = set()
        for sequence, event in enumerate(events, start=1):
            prior = _repeat_history_value(
                policy_version=self.config.policy_version,
                scope=scope,
                events=prefix,
            )
            semantic = {
                "attempt_id": event.get("attempt_id"),
                "attempt_number": event.get("attempt_number"),
                "evidence_revision": event.get("evidence_revision"),
                "canonical_grid_checksum": event.get("canonical_grid_checksum"),
                "topology_checksum": event.get("topology_checksum"),
                "terminal_status": event.get("terminal_status"),
            }
            expected_conflict = _repeat_history_conflicted(
                [*prefix, {**semantic, "conflict_observed": False}]
            )
            event_copy = dict(event)
            stored_event_checksum = event_copy.pop("event_checksum", None)
            if (
                set(event) != _REPEAT_HISTORY_EVENT_KEYS
                or event.get("schema_version")
                != PDF_DUAL_ORACLE_REPEAT_HISTORY_EVENT_SCHEMA
                or event.get("sequence") != sequence
                or event.get("attempt_number") != sequence
                or not _nonempty_string(event.get("attempt_id"))
                or event.get("attempt_id") in seen_attempt_ids
                or not _nonempty_string(event.get("evidence_revision"))
                or event.get("terminal_status") not in _REPEAT_HISTORY_TERMINALS
                or event.get("canonical_grid_checksum") is not None
                and not _nonempty_string(event.get("canonical_grid_checksum"))
                or event.get("topology_checksum") is not None
                and not _nonempty_string(event.get("topology_checksum"))
                or event.get("terminal_status") == "accepted_unique_consensus"
                and not _nonempty_string(event.get("canonical_grid_checksum"))
                or event.get("previous_event_checksum")
                != prior.get("latest_event_checksum")
                or event.get("prior_history_checksum")
                != prior.get("history_checksum")
                or event.get("conflict_observed") is not expected_conflict
                or event.get("event_id")
                != "pdfdualrepevent_"
                + stable_digest(
                    [data.get("scope_checksum"), event.get("attempt_id"), sequence],
                    length=24,
                )
                or stored_event_checksum != sha256_json(event_copy)
            ):
                errors.append("pdf_dual_oracle_repeat_history_event_invalid")
            if _nonempty_string(event.get("attempt_id")):
                seen_attempt_ids.add(str(event.get("attempt_id")))
            prefix.append(event)
        expected = _repeat_history_value(
            policy_version=self.config.policy_version,
            scope=scope,
            events=events,
        )
        if data != expected:
            errors.append("pdf_dual_oracle_repeat_history_integrity_invalid")
        return sorted(set(errors))

    def build_vlm_hypothesis_set(
        self,
        *,
        parser_observation: dict[str, Any],
        binding_hypotheses: list[dict[str, Any]],
        rejected_evidence: list[dict[str, Any]] | None = None,
        model_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        parser_errors = self.validate_parser_observation(parser_observation)
        if parser_errors:
            raise PdfDualOracleContractError(parser_errors[0])
        if len(binding_hypotheses) > self.config.maximum_hypotheses:
            raise PdfDualOracleContractError(
                "pdf_vlm_hypothesis_count_budget_exceeded"
            )
        candidate_ids = [
            str(item) for item in parser_observation.get("candidate_order") or []
        ]
        safe_model_context = _safe_model_context(model_context)
        hypotheses: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for item in rejected_evidence or []:
            if not isinstance(item, dict):
                raise PdfDualOracleContractError(
                    "pdf_vlm_hypothesis_rejected_evidence_invalid"
                )
            rejected.append(_safe_rejected_evidence(item))
        seen_hypothesis_ids: set[str] = set()
        for item in binding_hypotheses:
            binding = _object(item.get("binding_output"))
            binding_errors = validate_binding_output_shape(binding)
            hypothesis_id = str(item.get("hypothesis_id") or "")
            if not hypothesis_id:
                hypothesis_id = "pdfvlmhyp_" + stable_digest(
                    [
                        parser_observation.get("observation_id"),
                        sha256_json(binding),
                        len(hypotheses),
                    ],
                    length=24,
                )
            if hypothesis_id in seen_hypothesis_ids:
                raise PdfDualOracleContractError(
                    "pdf_vlm_hypothesis_identity_duplicate", hypothesis_id
                )
            seen_hypothesis_ids.add(hypothesis_id)
            if binding_errors:
                rejected.append(
                    {
                        "evidence_id": hypothesis_id,
                        "reason_codes": _canonical_reason_codes(binding_errors),
                    }
                )
                continue
            geometry = _normalized_geometry(item.get("proposed_geometry"))
            evidence = _safe_hypothesis_evidence(
                item.get("evidence"), model_context=safe_model_context
            )
            evidence["binding_output_hash"] = sha256_json(binding)
            continuation = _safe_continuation(item.get("continuation"))
            rows = [
                {
                    "row_ordinal": int(row.get("row_ordinal") or 0),
                    "row_kind": str(row.get("row_kind") or "unknown"),
                    "cells": [
                        [str(candidate_id) for candidate_id in cell]
                        for cell in row.get("cells") or []
                        if isinstance(cell, list)
                    ],
                }
                for row in _dicts(binding.get("rows"))
            ]
            grid_projection = {
                "row_count": int(binding.get("row_count") or 0),
                "column_count": int(binding.get("column_count") or 0),
                "header_rows": [int(value) for value in binding.get("header_rows") or []],
                "header_hierarchy": copy.deepcopy(
                    binding.get("header_hierarchy") or []
                ),
                "rows": rows,
                "spans": copy.deepcopy(binding.get("spans") or []),
            }
            topology_projection = {
                **grid_projection,
                "proposed_geometry": geometry,
                "continuation": continuation,
            }
            hypothesis = {
                "schema_version": PDF_VLM_TOPOLOGY_HYPOTHESIS_SCHEMA,
                "hypothesis_id": hypothesis_id,
                "decision": str(binding.get("decision") or ""),
                **topology_projection,
                "uncertainty_codes": _normalized_reason_codes(
                    binding.get("uncertainty_codes")
                ),
                "evidence": evidence,
                "candidate_id_only": True,
                "authoritative_values_present": False,
                "canonical_grid_checksum": sha256_json(grid_projection),
                "topology_checksum": sha256_json(topology_projection),
            }
            hypothesis["hypothesis_checksum"] = sha256_json(hypothesis)
            hypothesis_errors = self._validate_vlm_hypothesis(
                hypothesis, candidate_ids, safe_model_context
            )
            if hypothesis_errors:
                rejected.append(
                    {
                        "evidence_id": hypothesis_id,
                        "reason_codes": sorted(set(hypothesis_errors)),
                    }
                )
                continue
            hypotheses.append(hypothesis)

        result = {
            "schema_version": PDF_VLM_TOPOLOGY_HYPOTHESIS_SET_SCHEMA,
            "policy_version": self.config.policy_version,
            "hypothesis_set_id": "pdfvlmhypset_"
            + stable_digest(
                [
                    parser_observation.get("observation_id"),
                    [item.get("hypothesis_checksum") for item in hypotheses],
                    rejected,
                    safe_model_context,
                    self.config.policy_version,
                ],
                length=24,
            ),
            "parser_observation_id": parser_observation.get("observation_id"),
            "parser_observation_checksum": parser_observation.get(
                "observation_checksum"
            ),
            "table_ref": parser_observation.get("table_ref"),
            "candidate_ids": candidate_ids,
            "model_context": safe_model_context,
            "hypotheses": hypotheses,
            "rejected_evidence": rejected,
            "alternative_topologies_explicit": len(
                {
                    str(item.get("topology_checksum") or "")
                    for item in hypotheses
                }
            ) > 1,
            "reference_answer_used": False,
            "authoritative_values_present": False,
        }
        result["hypothesis_set_checksum"] = sha256_json(result)
        errors = self.validate_vlm_hypothesis_set(
            parser_observation=parser_observation,
            hypothesis_set=result,
        )
        if errors:
            raise PdfDualOracleContractError(errors[0])
        return result

    def validate_vlm_hypothesis_set(
        self,
        *,
        parser_observation: dict[str, Any],
        hypothesis_set: Any,
    ) -> list[str]:
        data = _object(hypothesis_set)
        errors: list[str] = []
        if data.get("schema_version") != PDF_VLM_TOPOLOGY_HYPOTHESIS_SET_SCHEMA:
            errors.append("pdf_vlm_hypothesis_set_schema_invalid")
        if set(data) != _HYPOTHESIS_SET_KEYS:
            errors.append("pdf_vlm_hypothesis_set_keys_invalid")
        if data.get("policy_version") != self.config.policy_version:
            errors.append("pdf_vlm_hypothesis_set_policy_invalid")
        if data.get("parser_observation_id") != parser_observation.get(
            "observation_id"
        ) or data.get("parser_observation_checksum") != parser_observation.get(
            "observation_checksum"
        ):
            errors.append("pdf_vlm_hypothesis_parser_identity_mismatch")
        expected_ids = [
            str(item) for item in parser_observation.get("candidate_order") or []
        ]
        candidate_ids = data.get("candidate_ids")
        if (
            not isinstance(candidate_ids, list)
            or not all(_nonempty_string(item) for item in candidate_ids)
            or len(candidate_ids) != len(set(candidate_ids))
            or candidate_ids != expected_ids
        ):
            errors.append("pdf_vlm_hypothesis_candidate_namespace_mismatch")
        context = _object(data.get("model_context"))
        errors.extend(_model_context_errors(context))
        rejected_value = data.get("rejected_evidence")
        rejected = _dicts(rejected_value)
        rejected_ids: list[str] = []
        if not isinstance(rejected_value, list) or len(rejected) != len(
            rejected_value if isinstance(rejected_value, list) else []
        ):
            errors.append("pdf_vlm_hypothesis_rejected_evidence_invalid")
        for item in rejected:
            evidence_id = item.get("evidence_id")
            reason_codes = item.get("reason_codes")
            rejected_ids.append(str(evidence_id or ""))
            if (
                set(item) != {"evidence_id", "reason_codes"}
                or not _nonempty_string(evidence_id)
                or not isinstance(reason_codes, list)
                or not reason_codes
                or not all(_strict_reason_code(value) for value in reason_codes)
                or reason_codes != sorted(set(reason_codes))
            ):
                errors.append("pdf_vlm_hypothesis_rejected_evidence_invalid")
        hypotheses_value = data.get("hypotheses")
        hypotheses = _dicts(hypotheses_value)
        if not isinstance(hypotheses_value, list) or len(hypotheses) != len(
            hypotheses_value if isinstance(hypotheses_value, list) else []
        ):
            errors.append("pdf_vlm_hypothesis_collection_invalid")
        if len(hypotheses) > self.config.maximum_hypotheses:
            errors.append("pdf_vlm_hypothesis_count_budget_exceeded")
        hypothesis_ids: list[str] = []
        for hypothesis in hypotheses:
            hypothesis_ids.append(str(hypothesis.get("hypothesis_id") or ""))
            errors.extend(
                self._validate_vlm_hypothesis(
                    hypothesis, expected_ids, context
                )
            )
        if (
            len(hypothesis_ids) != len(set(hypothesis_ids))
            or len(rejected_ids) != len(set(rejected_ids))
            or set(hypothesis_ids) & set(rejected_ids)
        ):
            errors.append("pdf_vlm_hypothesis_identity_duplicate")
        expected_explicit = len(
            {
                str(item.get("topology_checksum") or "")
                for item in hypotheses
            }
        ) > 1
        if (
            not isinstance(data.get("alternative_topologies_explicit"), bool)
            or data.get("alternative_topologies_explicit") is not expected_explicit
        ):
            errors.append("pdf_vlm_hypothesis_alternative_flag_invalid")
        if (
            data.get("reference_answer_used") is not False
            or data.get("authoritative_values_present") is not False
        ):
            errors.append("pdf_vlm_hypothesis_authority_boundary_invalid")
        expected_set_id = "pdfvlmhypset_" + stable_digest(
            [
                parser_observation.get("observation_id"),
                [item.get("hypothesis_checksum") for item in hypotheses],
                rejected,
                context,
                self.config.policy_version,
            ],
            length=24,
        )
        if data.get("hypothesis_set_id") != expected_set_id:
            errors.append("pdf_vlm_hypothesis_set_identity_invalid")
        copy_without_checksum = dict(data)
        stored_checksum = copy_without_checksum.pop("hypothesis_set_checksum", None)
        if stored_checksum != sha256_json(copy_without_checksum):
            errors.append("pdf_vlm_hypothesis_set_checksum_invalid")
        if len(_json_bytes(data)) > self.config.maximum_hypothesis_set_bytes:
            errors.append("pdf_vlm_hypothesis_set_byte_budget_exceeded")
        return sorted(set(errors))

    def _validate_vlm_hypothesis(
        self,
        hypothesis: dict[str, Any],
        expected_ids: list[str],
        model_context: dict[str, Any],
    ) -> list[str]:
        errors: list[str] = []
        if hypothesis.get("schema_version") != PDF_VLM_TOPOLOGY_HYPOTHESIS_SCHEMA:
            errors.append("pdf_vlm_hypothesis_schema_invalid")
        if set(hypothesis) != _HYPOTHESIS_KEYS:
            errors.append("pdf_vlm_hypothesis_keys_invalid")
        if _recursive_keys(hypothesis) & _FORBIDDEN_VLM_KEYS:
            errors.append("pdf_vlm_hypothesis_value_or_source_evidence_forbidden")
        if not _nonempty_string(hypothesis.get("hypothesis_id")):
            errors.append("pdf_vlm_hypothesis_identity_invalid")
        if (
            hypothesis.get("candidate_id_only") is not True
            or hypothesis.get("authoritative_values_present") is not False
        ):
            errors.append("pdf_vlm_hypothesis_authority_boundary_invalid")
        decision = hypothesis.get("decision")
        if decision not in _DECISIONS:
            errors.append("pdf_vlm_hypothesis_decision_invalid")
        row_count = hypothesis.get("row_count")
        column_count = hypothesis.get("column_count")
        rows = row_count if _integer_at_least(row_count, 0) else 0
        columns = column_count if _integer_at_least(column_count, 0) else 0
        if (
            not _integer_at_least(row_count, 0)
            or not _integer_at_least(column_count, 0)
        ):
            errors.append("pdf_vlm_hypothesis_shape_type_invalid")
        if rows * columns > self.config.maximum_grid_positions:
            errors.append("pdf_vlm_hypothesis_grid_budget_exceeded")
        rows_value = hypothesis.get("rows")
        grid_rows = _dicts(rows_value)
        if not isinstance(rows_value, list) or len(grid_rows) != len(
            rows_value if isinstance(rows_value, list) else []
        ):
            errors.append("pdf_vlm_hypothesis_rows_contract_invalid")
        if decision in {"bound", "ambiguous"}:
            if rows < 1 or columns < 1 or len(grid_rows) != rows:
                errors.append("pdf_vlm_hypothesis_rectangular_grid_incomplete")
        elif decision == "unsupported" and (
            rows != 0 or columns != 0 or grid_rows
        ):
            errors.append("pdf_vlm_hypothesis_unsupported_grid_not_empty")
        used: list[str] = []
        for expected_row, row in enumerate(grid_rows, start=1):
            cells = row.get("cells")
            if set(row) != _ROW_KEYS:
                errors.append("pdf_vlm_hypothesis_row_contract_invalid")
            if (
                not _integer_at_least(row.get("row_ordinal"), 1)
                or row.get("row_ordinal") != expected_row
                or not _nonempty_string(row.get("row_kind"))
                or row.get("row_kind") not in _ROW_KINDS
                or not isinstance(cells, list)
            ):
                errors.append("pdf_vlm_hypothesis_row_identity_invalid")
                continue
            if decision in {"bound", "ambiguous"} and len(cells) != columns:
                errors.append("pdf_vlm_hypothesis_row_width_invalid")
            for cell in cells:
                if not isinstance(cell, list) or not all(
                    _nonempty_string(item) for item in cell
                ):
                    errors.append("pdf_vlm_hypothesis_candidate_cell_invalid")
                    continue
                used.extend(cell)
        if decision in {"bound", "ambiguous"}:
            if set(used) != set(expected_ids):
                errors.append("pdf_vlm_hypothesis_candidate_coverage_incomplete")
            if len(used) != len(set(used)):
                errors.append("pdf_vlm_hypothesis_candidate_ownership_duplicate")
        if set(used) - set(expected_ids):
            errors.append("pdf_vlm_hypothesis_candidate_unknown")
        headers = hypothesis.get("header_rows")
        if (
            not isinstance(headers, list)
            or not all(_integer_at_least(item, 1) for item in headers)
            or headers != list(range(1, len(headers) + 1))
            or any(item > min(rows, 8) for item in headers)
        ):
            errors.append("pdf_vlm_hypothesis_header_rows_invalid")
        errors.extend(_topology_errors(hypothesis, rows, columns))
        errors.extend(_continuation_errors(hypothesis.get("continuation"), columns))
        uncertainty = hypothesis.get("uncertainty_codes")
        if (
            not isinstance(uncertainty, list)
            or not all(_strict_reason_code(value) for value in uncertainty)
            or uncertainty != sorted(set(uncertainty))
        ):
            errors.append("pdf_vlm_hypothesis_uncertainty_contract_invalid")
        evidence = _object(hypothesis.get("evidence"))
        if (
            set(evidence) != _HYPOTHESIS_EVIDENCE_KEYS
            or not _nonempty_string(evidence.get("attempt_id"))
            or not _integer_at_least(evidence.get("attempt_number"), 1)
            or not _nonempty_string(evidence.get("evidence_revision"))
            or not _nonempty_string(evidence.get("provider"))
            or not _nonempty_string(evidence.get("model"))
            or not _nonempty_string(evidence.get("provider_config_hash"))
            or not _nonempty_string(evidence.get("binding_output_hash"))
            or not isinstance(evidence.get("package_ids"), list)
            or not evidence.get("package_ids")
            or not all(
                _nonempty_string(item) for item in evidence.get("package_ids") or []
            )
            or len(evidence.get("package_ids") or [])
            != len(set(evidence.get("package_ids") or []))
            or not isinstance(evidence.get("packages"), list)
            or not evidence.get("packages")
            or len(evidence.get("packages") or []) != len(
                _dicts(evidence.get("packages"))
            )
        ):
            errors.append("pdf_vlm_hypothesis_evidence_identity_invalid")
        for package in _dicts(evidence.get("packages")):
            if (
                set(package) != _EVIDENCE_PACKAGE_KEYS
                or not all(_nonempty_string(value) for value in package.values())
            ):
                errors.append("pdf_vlm_hypothesis_evidence_package_invalid")
        package_ids = (
            evidence.get("package_ids")
            if isinstance(evidence.get("package_ids"), list)
            else []
        )
        package_record_ids = [
            str(item.get("package_id") or "")
            for item in _dicts(evidence.get("packages"))
        ]
        if package_ids != package_record_ids:
            errors.append("pdf_vlm_hypothesis_evidence_package_scope_invalid")
        if (
            evidence.get("provider") != model_context.get("provider")
            or evidence.get("model") != model_context.get("model")
            or evidence.get("provider_config_hash")
            != model_context.get("configuration_hash")
        ):
            errors.append("pdf_vlm_hypothesis_evidence_model_context_mismatch")
        hypothesis_copy = dict(hypothesis)
        stored = hypothesis_copy.pop("hypothesis_checksum", None)
        if stored != sha256_json(hypothesis_copy):
            errors.append("pdf_vlm_hypothesis_checksum_invalid")
        projection = {
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
        if hypothesis.get("canonical_grid_checksum") != sha256_json(projection):
            errors.append("pdf_vlm_hypothesis_grid_checksum_invalid")
        topology_projection = {
            **projection,
            "proposed_geometry": copy.deepcopy(hypothesis.get("proposed_geometry")),
            "continuation": copy.deepcopy(hypothesis.get("continuation")),
        }
        if hypothesis.get("topology_checksum") != sha256_json(topology_projection):
            errors.append("pdf_vlm_hypothesis_topology_checksum_invalid")
        return errors


def _topology_errors(
    hypothesis: dict[str, Any], rows: int, columns: int
) -> list[str]:
    errors: list[str] = []
    spans_value = hypothesis.get("spans")
    spans = _dicts(spans_value)
    if not isinstance(spans_value, list) or len(spans) != len(
        spans_value if isinstance(spans_value, list) else []
    ):
        errors.append("pdf_vlm_hypothesis_span_contract_invalid")
    grid: dict[tuple[int, int], list[Any]] = {}
    for row in _dicts(hypothesis.get("rows")):
        row_ordinal = row.get("row_ordinal")
        cells = row.get("cells")
        if not _integer_at_least(row_ordinal, 1) or not isinstance(cells, list):
            continue
        for column, cell in enumerate(cells, start=1):
            if isinstance(cell, list):
                grid[(row_ordinal, column)] = cell
    header_rows = {
        item
        for item in (hypothesis.get("header_rows") or [])
        if _integer_at_least(item, 1)
    }
    occupied: set[tuple[int, int]] = set()
    for span in spans:
        start_row = span.get("start_row")
        end_row = span.get("end_row")
        start_column = span.get("start_column")
        end_column = span.get("end_column")
        if (
            set(span)
            != {
                "start_row",
                "end_row",
                "start_column",
                "end_column",
                "relation",
            }
            or span.get("relation") not in {"merged", "spanning_header"}
            or not all(
                _integer_at_least(value, 1)
                for value in (start_row, end_row, start_column, end_column)
            )
            or not (1 <= start_row <= end_row <= rows)
            or not (1 <= start_column <= end_column <= columns)
            or (start_row == end_row and start_column == end_column)
        ):
            errors.append("pdf_vlm_hypothesis_span_invalid")
            continue
        positions = {
            (row, column)
            for row in range(start_row, end_row + 1)
            for column in range(start_column, end_column + 1)
        }
        if occupied & positions:
            errors.append("pdf_vlm_hypothesis_span_overlap")
        occupied.update(positions)
        anchor = (start_row, start_column)
        covered_nonanchors = positions - {anchor}
        if not grid.get(anchor) or any(grid.get(position) for position in covered_nonanchors):
            errors.append("pdf_vlm_hypothesis_span_anchor_or_empty_coverage_invalid")
        if span.get("relation") == "spanning_header" and start_row not in header_rows:
            errors.append("pdf_vlm_hypothesis_spanning_header_outside_header")
    hierarchy_value = hypothesis.get("header_hierarchy")
    hierarchy = _dicts(hierarchy_value)
    if not isinstance(hierarchy_value, list) or len(hierarchy) != len(
        hierarchy_value if isinstance(hierarchy_value, list) else []
    ):
        errors.append("pdf_vlm_hypothesis_header_hierarchy_invalid")
    for relation in hierarchy:
        parent_row = relation.get("parent_row")
        parent_column = relation.get("parent_column")
        child_start = relation.get("child_start_column")
        child_end = relation.get("child_end_column")
        if not (
            set(relation)
            == {
                "parent_row",
                "parent_column",
                "child_start_column",
                "child_end_column",
            }
            and all(
                _integer_at_least(value, 1)
                for value in (parent_row, parent_column, child_start, child_end)
            )
            and 1 <= parent_row <= min(rows, 8)
            and 1 <= parent_column <= columns
            and 1 <= child_start <= child_end <= columns
        ):
            errors.append("pdf_vlm_hypothesis_header_hierarchy_invalid")
            continue
        parent = (parent_row, parent_column)
        if parent[0] not in header_rows or not grid.get(parent):
            errors.append("pdf_vlm_hypothesis_header_hierarchy_anchor_invalid")
        if not any(
            span.get("start_row") == parent[0]
            and span.get("start_column") == parent[1]
            and _integer_at_least(span.get("end_column"), 1)
            and span.get("end_column") >= child_end
            for span in spans
        ):
            errors.append("pdf_vlm_hypothesis_header_hierarchy_span_missing")
    geometry = _object(hypothesis.get("proposed_geometry"))
    if set(geometry) != _GEOMETRY_KEYS:
        errors.append("pdf_vlm_hypothesis_geometry_contract_invalid")
    for axis, segments in (("rows", rows), ("columns", columns)):
        axis_geometry = _object(geometry.get(axis))
        kind = axis_geometry.get("kind")
        boundaries = axis_geometry.get("boundaries")
        if (
            set(axis_geometry) != _GEOMETRY_AXIS_KEYS
            or kind not in _GEOMETRY_KINDS
            or not isinstance(boundaries, list)
        ):
            errors.append("pdf_vlm_hypothesis_geometry_contract_invalid")
            continue
        if kind == "not_observed" and boundaries:
            errors.append("pdf_vlm_hypothesis_unobserved_geometry_not_empty")
        if kind in {
            "normalized_boundaries",
            "consensus_normalized_boundaries",
        } and not _valid_boundaries(
            boundaries, segments
        ):
            errors.append("pdf_vlm_hypothesis_boundaries_invalid")
    return errors


def _continuation_errors(value: Any, columns: int) -> list[str]:
    continuation = _object(value)
    if set(continuation) != _CONTINUATION_KEYS:
        return ["pdf_vlm_hypothesis_continuation_contract_invalid"]
    required = continuation.get("required")
    if not isinstance(required, bool):
        return ["pdf_vlm_hypothesis_continuation_contract_invalid"]
    if not required:
        if continuation != {
            "required": False,
            "continuation_group_id": None,
            "fragment_order": 0,
            "fragment_count": 0,
            "shared_column_count": 0,
            "repeated_header_policy": None,
        }:
            return ["pdf_vlm_hypothesis_continuation_contract_invalid"]
        return []
    fragment_order = continuation.get("fragment_order")
    fragment_count = continuation.get("fragment_count")
    shared_columns = continuation.get("shared_column_count")
    if (
        not _nonempty_string(continuation.get("continuation_group_id"))
        or not _integer_at_least(fragment_order, 1)
        or not _integer_at_least(fragment_count, 2)
        or fragment_order > fragment_count
        or not _integer_at_least(shared_columns, 1)
        or shared_columns != columns
        or continuation.get("repeated_header_policy")
        not in _REPEATED_HEADER_POLICIES
    ):
        return ["pdf_vlm_hypothesis_continuation_contract_invalid"]
    return []


def _normalized_geometry(value: Any) -> dict[str, Any]:
    source = _object(value)
    result: dict[str, Any] = {}
    for axis in ("rows", "columns"):
        current = _object(source.get(axis))
        kind = current.get("kind", "not_observed")
        boundaries = current.get("boundaries", [])
        if isinstance(boundaries, list) and all(
            isinstance(item, (int, float)) and not isinstance(item, bool)
            for item in boundaries
        ):
            boundaries = [float(item) for item in boundaries]
        else:
            boundaries = copy.deepcopy(boundaries)
        result[axis] = {
            "kind": copy.deepcopy(kind),
            "boundaries": boundaries,
        }
    return result


def _safe_hypothesis_evidence(
    value: Any, *, model_context: dict[str, Any]
) -> dict[str, Any]:
    source = _object(value)
    result = {
        "attempt_id": copy.deepcopy(source.get("attempt_id")),
        "attempt_number": copy.deepcopy(source.get("attempt_number")),
        "evidence_revision": copy.deepcopy(source.get("evidence_revision")),
        # Set-level model_context is the authority for model execution lineage.
        # The child evidence cannot create a divergent provider/model/config tuple.
        "provider": model_context.get("provider"),
        "model": model_context.get("model"),
        "provider_config_hash": model_context.get("configuration_hash"),
        "binding_output_hash": copy.deepcopy(source.get("binding_output_hash")),
    }
    raw_packages = source.get("packages")
    if isinstance(raw_packages, list):
        packages: Any = [
            (
                {
                    "package_id": copy.deepcopy(item.get("package_id")),
                    "crop_sha256": copy.deepcopy(item.get("crop_sha256")),
                    "candidate_dictionary_hash": copy.deepcopy(
                        item.get("candidate_dictionary_hash")
                    ),
                }
                if isinstance(item, dict)
                else {
                    "package_id": None,
                    "crop_sha256": None,
                    "candidate_dictionary_hash": None,
                }
            )
            for item in raw_packages
        ]
    else:
        packages = copy.deepcopy(raw_packages)
    raw_package_ids = source.get("package_ids")
    if raw_package_ids is None and isinstance(packages, list):
        raw_package_ids = [item.get("package_id") for item in packages]
    result["package_ids"] = copy.deepcopy(raw_package_ids)
    result["packages"] = packages
    return result


def _safe_model_context(value: Any) -> dict[str, Any]:
    source = _object(value)
    provider = _lineage_string(source.get("provider"))
    model = _lineage_string(source.get("model"))
    configuration_hash = _lineage_string(source.get("configuration_hash"))
    topology_input_basis = _enum_or_unknown(
        source.get("topology_input_basis"), _TOPOLOGY_INPUT_BASES
    )
    topology_dimensions_source = _enum_or_unknown(
        source.get("topology_dimensions_source"), _TOPOLOGY_DIMENSION_SOURCES
    )
    alternative_generation = _enum_or_unknown(
        source.get("alternative_generation_contract"),
        _ALTERNATIVE_GENERATION_CONTRACTS,
    )
    prompt_hash = _optional_string(source.get("topology_prompt_contract_hash"))
    crop_manifest_hash = _optional_string(source.get("crop_manifest_hash"))
    observed_image_bytes = _optional_nonnegative_integer(
        source.get("observed_image_bytes")
    )
    maximum_image_bytes = _optional_nonnegative_integer(
        source.get("maximum_image_bytes")
    )
    observed_output_tokens = _optional_nonnegative_integer(
        source.get("observed_output_tokens")
    )
    maximum_output_tokens = _optional_nonnegative_integer(
        source.get("maximum_output_tokens")
    )
    provider_calls_replayed = _nonnegative_integer_or_zero(
        source.get("provider_calls_replayed")
    )
    new_provider_calls = _nonnegative_integer_or_zero(
        source.get("new_provider_calls")
    )
    execution_mode = (
        str(source.get("execution_mode"))
        if source.get("execution_mode") in _EXECUTION_MODES
        else "whole_table"
    )
    window_count = _nonnegative_integer_or_zero(source.get("window_count"))
    if window_count < 1:
        window_count = 1
    raw_provider_calls = _nonnegative_integer_or_zero(
        source.get("raw_provider_calls")
    )
    if "raw_provider_calls" not in source:
        raw_provider_calls = provider_calls_replayed + new_provider_calls
    stitched_oracle_observations = _nonnegative_integer_or_zero(
        source.get("stitched_oracle_observations")
    )
    if "stitched_oracle_observations" not in source:
        stitched_oracle_observations = raw_provider_calls
    window_lineage_checksum = _optional_string(
        source.get("window_lineage_checksum")
    )
    if execution_mode == "whole_table" and not window_lineage_checksum:
        window_lineage_checksum = "not_applicable"
    execution_accounting_valid = bool(
        raw_provider_calls == provider_calls_replayed + new_provider_calls
        and (
            execution_mode == "whole_table"
            and window_count == 1
            and stitched_oracle_observations == raw_provider_calls
            or execution_mode == "vertical_atom_windows"
            and window_count >= 2
            and stitched_oracle_observations == 2
            and raw_provider_calls == window_count * 2
            and bool(window_lineage_checksum)
        )
    )
    image_and_output_budgets_attested = bool(
        observed_image_bytes is not None
        and maximum_image_bytes is not None
        and maximum_image_bytes > 0
        and observed_image_bytes <= maximum_image_bytes
        and observed_output_tokens is not None
        and maximum_output_tokens is not None
        and maximum_output_tokens > 0
        and observed_output_tokens <= maximum_output_tokens
    )
    lineage_complete = all(
        value != "unknown" for value in (provider, model, configuration_hash)
    )
    independently_observed = bool(
        lineage_complete
        and
        topology_input_basis == "visual_crop_without_parser_grid"
        and topology_dimensions_source == "vlm_visual_observation"
        and prompt_hash
        and crop_manifest_hash
    )
    alternatives_complete = bool(
        independently_observed
        and alternative_generation == "explicit_exhaustive_bounded_alternatives"
        and source.get("alternative_topology_hypotheses_complete") is True
    )
    context_guard = bool(
        source.get("bounded_row_windows") is True
        and (
            provider_calls_replayed + new_provider_calls > 0
        )
        and execution_accounting_valid
        and source.get("provider_token_accounting_exact") is True
        and source.get("candidate_ownership_exact") is True
        and source.get("no_silent_truncation") is True
        and source.get("column_splitting_used") is False
        and source.get("hidden_provider_failover") is False
        and image_and_output_budgets_attested
    )
    return {
        "provider": provider,
        "model": model,
        "configuration_hash": configuration_hash,
        "bounded_row_windows": source.get("bounded_row_windows") is True,
        "provider_calls_replayed": provider_calls_replayed,
        "new_provider_calls": new_provider_calls,
        "execution_mode": execution_mode,
        "window_count": window_count,
        "raw_provider_calls": raw_provider_calls,
        "stitched_oracle_observations": stitched_oracle_observations,
        "window_lineage_checksum": window_lineage_checksum,
        "topology_input_basis": topology_input_basis,
        "topology_dimensions_source": topology_dimensions_source,
        "alternative_generation_contract": alternative_generation,
        "topology_prompt_contract_hash": prompt_hash,
        "crop_manifest_hash": crop_manifest_hash,
        "observed_image_bytes": observed_image_bytes,
        "maximum_image_bytes": maximum_image_bytes,
        "observed_output_tokens": observed_output_tokens,
        "maximum_output_tokens": maximum_output_tokens,
        "image_and_output_budgets_attested": image_and_output_budgets_attested,
        "provider_token_accounting_exact": (
            source.get("provider_token_accounting_exact") is True
        ),
        "candidate_ownership_exact": source.get("candidate_ownership_exact") is True,
        "no_silent_truncation": source.get("no_silent_truncation") is True,
        "column_splitting_used": source.get("column_splitting_used") is not False,
        "hidden_provider_failover": source.get("hidden_provider_failover") is not False,
        "topology_dimensions_independently_observed": independently_observed,
        "alternative_topology_hypotheses_complete": alternatives_complete,
        "context_guard_attested": context_guard,
    }


def _safe_continuation(value: Any) -> dict[str, Any]:
    source = _object(value)
    return {
        "required": copy.deepcopy(source.get("required", False)),
        "continuation_group_id": copy.deepcopy(
            source.get("continuation_group_id")
        ),
        "fragment_order": copy.deepcopy(source.get("fragment_order", 0)),
        "fragment_count": copy.deepcopy(source.get("fragment_count", 0)),
        "shared_column_count": copy.deepcopy(
            source.get("shared_column_count", 0)
        ),
        "repeated_header_policy": copy.deepcopy(
            source.get("repeated_header_policy")
        ),
    }


def _safe_rejected_evidence(value: dict[str, Any]) -> dict[str, Any]:
    evidence_id = value.get("evidence_id")
    reason_codes = value.get("reason_codes")
    if (
        set(value) != {"evidence_id", "reason_codes"}
        or not _nonempty_string(evidence_id)
        or not isinstance(reason_codes, list)
        or not reason_codes
        or not all(_strict_reason_code(item) for item in reason_codes)
    ):
        raise PdfDualOracleContractError(
            "pdf_vlm_hypothesis_rejected_evidence_invalid"
        )
    return {
        "evidence_id": evidence_id,
        "reason_codes": _canonical_reason_codes(reason_codes),
    }


def _model_context_errors(context: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(context) != _MODEL_CONTEXT_KEYS:
        errors.append("pdf_vlm_hypothesis_model_context_invalid")
    if not all(
        _nonempty_string(context.get(key))
        for key in ("provider", "model", "configuration_hash")
    ) or not all(
        isinstance(context.get(key), str)
        for key in ("topology_prompt_contract_hash", "crop_manifest_hash")
    ):
        errors.append("pdf_vlm_hypothesis_model_context_type_invalid")
    if (
        context.get("topology_input_basis") not in _TOPOLOGY_INPUT_BASES
        or context.get("topology_dimensions_source")
        not in _TOPOLOGY_DIMENSION_SOURCES
        or context.get("alternative_generation_contract")
        not in _ALTERNATIVE_GENERATION_CONTRACTS
    ):
        errors.append("pdf_vlm_hypothesis_model_context_lineage_invalid")
    if (
        context.get("execution_mode") not in _EXECUTION_MODES
        or not _nonempty_string(context.get("window_lineage_checksum"))
    ):
        errors.append("pdf_vlm_hypothesis_model_context_execution_invalid")
    boolean_keys = {
        "bounded_row_windows",
        "provider_token_accounting_exact",
        "candidate_ownership_exact",
        "no_silent_truncation",
        "column_splitting_used",
        "hidden_provider_failover",
        "image_and_output_budgets_attested",
        "topology_dimensions_independently_observed",
        "alternative_topology_hypotheses_complete",
        "context_guard_attested",
    }
    if any(not isinstance(context.get(key), bool) for key in boolean_keys):
        errors.append("pdf_vlm_hypothesis_model_context_type_invalid")
    if any(
        not _integer_at_least(context.get(key), 0)
        for key in (
            "provider_calls_replayed",
            "new_provider_calls",
            "window_count",
            "raw_provider_calls",
            "stitched_oracle_observations",
        )
    ):
        errors.append("pdf_vlm_hypothesis_model_context_type_invalid")
    raw_calls = _nonnegative_integer_or_zero(context.get("raw_provider_calls"))
    stitched = _nonnegative_integer_or_zero(
        context.get("stitched_oracle_observations")
    )
    window_count = _nonnegative_integer_or_zero(context.get("window_count"))
    if (
        raw_calls
        != _nonnegative_integer_or_zero(context.get("provider_calls_replayed"))
        + _nonnegative_integer_or_zero(context.get("new_provider_calls"))
        or context.get("execution_mode") == "whole_table"
        and (window_count != 1 or stitched != raw_calls)
        or context.get("execution_mode") == "vertical_atom_windows"
        and (
            window_count < 2
            or stitched != 2
            or raw_calls != window_count * 2
        )
    ):
        errors.append("pdf_vlm_hypothesis_model_context_execution_invalid")
    budget_values = [
        context.get("observed_image_bytes"),
        context.get("maximum_image_bytes"),
        context.get("observed_output_tokens"),
        context.get("maximum_output_tokens"),
    ]
    if any(value is not None for value in budget_values):
        if (
            not all(_integer_at_least(value, 0) for value in budget_values)
            or context.get("maximum_image_bytes", 0) < 1
            or context.get("maximum_output_tokens", 0) < 1
        ):
            errors.append("pdf_vlm_hypothesis_model_context_budget_invalid")
    canonical = _safe_model_context(context)
    if context != canonical:
        errors.append("pdf_vlm_hypothesis_model_context_derived_fields_invalid")
    return errors


def _normalized_reason_codes(value: Any) -> Any:
    if not isinstance(value, list) or not all(
        _strict_reason_code(item) for item in value
    ):
        return copy.deepcopy(value)
    return _canonical_reason_codes(value)


def _canonical_reason_codes(value: list[str]) -> list[str]:
    return sorted(set(value))


def _strict_reason_code(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and 1 <= len(value) <= 160
        and value == value.strip()
        and value[0] in "abcdefghijklmnopqrstuvwxyz"
        and all(character in "abcdefghijklmnopqrstuvwxyz0123456789_" for character in value)
    )


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and value == value.strip()


def _lineage_string(value: Any) -> str:
    return value if _nonempty_string(value) else "unknown"


def _optional_string(value: Any) -> str:
    return value if isinstance(value, str) and value == value.strip() else ""


def _enum_or_unknown(value: Any, allowed: set[str]) -> str:
    return value if isinstance(value, str) and value in allowed else "unknown"


def _integer_at_least(value: Any, minimum: int) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= minimum
    )


def _optional_nonnegative_integer(value: Any) -> int | None:
    return value if _integer_at_least(value, 0) else None


def _nonnegative_integer_or_zero(value: Any) -> int:
    return value if _integer_at_least(value, 0) else 0


def _valid_boundaries(value: list[Any], segments: int) -> bool:
    if segments < 1 or len(value) != segments + 1:
        return False
    if any(
        not isinstance(item, (int, float)) or isinstance(item, bool) for item in value
    ):
        return False
    values = [float(item) for item in value]
    return (
        all(math.isfinite(item) for item in values)
        and
        values[0] == 0.0
        and values[-1] == 1.0
        and all(right > left for left, right in zip(values, values[1:]))
    )


def _json_bytes(value: Any) -> bytes:
    import json

    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _bbox(value: Any) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        result = [float(item) for item in value]
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(item) for item in result):
        return None
    if result[2] <= result[0] or result[3] <= result[1]:
        return None
    return result


def _bbox_union(values: list[list[float]]) -> list[float] | None:
    if not values:
        return None
    return [
        min(item[0] for item in values),
        min(item[1] for item in values),
        max(item[2] for item in values),
        max(item[3] for item in values),
    ]


def _duplicate_groups(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    by_value: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        by_value.setdefault(
            str(candidate.get("exact_visible_value_checksum") or ""), []
        ).append(candidate)
    for value_checksum, items in sorted(by_value.items()):
        if len(items) < 2:
            continue
        bboxes = [tuple(item.get("bbox") or []) for item in items]
        result.append(
            {
                "exact_visible_value_checksum": value_checksum,
                "candidate_ids": [str(item.get("candidate_id") or "") for item in items],
                "coordinates_distinguish_identities": len(set(bboxes)) == len(bboxes),
            }
        )
    return result


def _contained(value: list[float], scope: list[float], tolerance: float = 0.75) -> bool:
    return (
        value[0] >= scope[0] - tolerance
        and value[1] >= scope[1] - tolerance
        and value[2] <= scope[2] + tolerance
        and value[3] <= scope[3] + tolerance
    )


def _overlaps(left: list[float], right: list[float]) -> bool:
    return min(left[2], right[2]) > max(left[0], right[0]) and min(
        left[3], right[3]
    ) > max(left[1], right[1])


def _recursive_keys(value: Any) -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        result.update(str(key) for key in value)
        for item in value.values():
            result.update(_recursive_keys(item))
    elif isinstance(value, list):
        for item in value:
            result.update(_recursive_keys(item))
    return result


def _repeat_history_scope(value: Any) -> dict[str, Any]:
    keys = set(value) if isinstance(value, dict) else set()
    allowed = {
        frozenset(_REPEAT_HISTORY_SCOPE_LEGACY_KEYS),
        frozenset(_REPEAT_HISTORY_SCOPE_KEYS),
    }
    if (
        not isinstance(value, dict)
        or frozenset(keys) not in allowed
        or any(not _nonempty_string(value.get(key)) for key in keys)
    ):
        raise PdfDualOracleContractError(
            "pdf_dual_oracle_repeat_history_scope_invalid"
        )
    return {key: str(value[key]) for key in sorted(keys)}


def _repeat_history_conflicted(events: list[dict[str, Any]]) -> bool:
    canonical = {
        str(item.get("canonical_grid_checksum") or "")
        for item in events
        if item.get("canonical_grid_checksum")
    }
    topologies = {
        str(item.get("topology_checksum") or "")
        for item in events
        if item.get("topology_checksum")
    }
    return bool(
        any(item.get("conflict_observed") is True for item in events)
        or any(
            item.get("terminal_status")
            in {"ambiguous_multiple_consensus", "parser_vlm_conflict"}
            for item in events
        )
        or len(canonical) > 1
        or len(topologies) > 1
    )


def _repeat_history_value(
    *,
    policy_version: str,
    scope: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    scope_checksum = sha256_json(scope)
    result = {
        "schema_version": PDF_DUAL_ORACLE_REPEAT_HISTORY_SCHEMA,
        "policy_version": policy_version,
        "history_id": "pdfdualrephistory_"
        + stable_digest([scope_checksum, policy_version], length=24),
        "scope": copy.deepcopy(scope),
        "scope_checksum": scope_checksum,
        "events": copy.deepcopy(events),
        "ever_conflicted": _repeat_history_conflicted(events),
        "latest_event_checksum": (
            events[-1].get("event_checksum") if events else None
        ),
    }
    result["history_checksum"] = sha256_json(result)
    return result


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return (
        [item for item in value if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )
