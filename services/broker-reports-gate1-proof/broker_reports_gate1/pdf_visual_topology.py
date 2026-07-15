from __future__ import annotations

import copy
import math
import re
from dataclasses import asdict, dataclass
from typing import Any

from .contracts import stable_digest
from .pdf_dual_oracle_contracts import PdfDualOracleContractFactory
from .pdf_hybrid_contracts import canonical_json_bytes, sha256_json


PDF_VISUAL_TOPOLOGY_REQUEST_SCHEMA = (
    "broker_reports_pdf_visual_topology_request_v1"
)
PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA = (
    "broker_reports_pdf_visual_topology_response_v1"
)
PDF_VISUAL_TOPOLOGY_PACKAGE_SCHEMA = (
    "broker_reports_pdf_visual_topology_package_v1"
)
PDF_VISUAL_TOPOLOGY_WINDOW_PACKAGE_SCHEMA = (
    "broker_reports_pdf_visual_topology_window_package_v1"
)
PDF_VISUAL_TOPOLOGY_LEDGER_PACKAGE_SCHEMA = (
    "broker_reports_pdf_visual_topology_ledger_package_v1"
)
PDF_VISUAL_TOPOLOGY_POLICY_VERSION = "pdf_visual_topology_policy_v5"
PDF_VISUAL_TOPOLOGY_REGION_PROPOSAL_REVISION = (
    "pdf_visual_topology_region_proposal_v1"
)

FACTORY_REQUIRED = (
    "PdfVisualTopologyFactory.create is the only topology-neutral visual "
    "package and bounded region-proposal response-contract entrypoint"
)
FORBIDDEN = (
    "Legacy visual topology input must not contain source text, values, parser "
    "rows, parser columns, header-depth hints, legacy cells, or expected "
    "topology; candidate-crop region proposals may expose only exact source "
    "word text with anonymous geometry and must not expose source refs, "
    "checksums, candidate ids, or permit source text in a response"
)

_FACTORY_TOKEN = object()
_DECISIONS = {"bound", "ambiguous", "unsupported"}
_REGION_PROPOSAL_SCOPES = {"candidate_crop", "page_level"}
_TABLE_PRESENCE = {"present", "absent", "uncertain"}
_BORDER_EVIDENCE = {"ruled", "alignment_based", "mixed", "uncertain"}
_DENSITY = {"sparse", "mixed", "dense", "uncertain"}
_CONTINUATION_LIKELIHOOD = {"likely", "unlikely", "uncertain"}
_CANONICAL_SPAN_RELATION = "merged"
_ACCEPTED_SPAN_RELATIONS = {_CANONICAL_SPAN_RELATION, "spanning_header"}
_CODE = re.compile(r"^[a-z][a-z0-9_]{2,95}$")
_HYPOTHESIS_ID = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,95}$")

_PACKAGE_KEYS = {
    "schema_version",
    "policy_version",
    "policy_configuration_hash",
    "package_id",
    "document_ref",
    "pdf_sha256",
    "page_ref",
    "page_number",
    "table_ref",
    "parser_observation_id",
    "parser_observation_checksum",
    "crop_identity",
    "neutral_atom_manifest_hash",
    "neutral_atom_to_candidate_id",
    "candidate_dictionary_hash",
    "private_candidate_dictionary",
    "model_facing",
    "output_schema",
    "component_accounting",
    "source_authority",
    "legacy_grid_consumed",
    "source_values_exposed_to_model_view",
    "package_hash",
}
_WINDOW_PACKAGE_KEYS = {
    *_PACKAGE_KEYS,
    "full_package_id",
    "full_package_hash",
    "window_plan_hash",
    "window_identity",
}
_LEDGER_PACKAGE_KEYS = {
    *_PACKAGE_KEYS,
    "package_purpose",
    "provider_input_allowed",
}
_RESPONSE_KEYS = {
    "schema_version",
    "package_id",
    "decision",
    "alternatives_complete",
    "hypotheses",
    "uncertainty_codes",
}
_REGION_PROPOSAL_PACKAGE_KEYS = {
    *_PACKAGE_KEYS,
    "contract_revision",
    "proposal_scope",
}
_REGION_PROPOSAL_RESPONSE_KEYS = {
    "schema_version",
    "contract_revision",
    "package_id",
    "proposal_scope",
    "table_presence",
    "alternatives_complete",
    "regions",
    "uncertainty_codes",
}
_REGION_PROPOSAL_KEYS = {
    "region_key",
    "bbox",
    "border_evidence",
    "density",
    "continuation_likelihood",
    "hypotheses",
    "uncertainty_codes",
}
_REGION_MODEL_KEYS = {
    "schema_version",
    "contract_revision",
    "task",
    "proposal_scope",
    "input_basis",
    "identity",
    "coordinate_space",
    "atoms",
    "output_limits",
    "rules",
}
_CROP_IDENTITY_KEYS = {
    "crop_id",
    "crop_sha256",
    "manifest_hash",
    "dpi",
    "width",
    "height",
    "png_bytes",
    "declared_table_bbox",
    "rendered_bbox",
    "page_rotation",
    "padding_points",
}
_HYPOTHESIS_KEYS = {
    "hypothesis_key",
    "row_boundaries",
    "column_boundaries",
    "header_row_count",
    "spans",
    "header_hierarchy",
    "continuation_required",
    "uncertainty_codes",
}
_SPAN_KEYS = {
    "start_row",
    "end_row",
    "start_column",
    "end_column",
    "relation",
}
_HEADER_RELATION_KEYS = {
    "parent_row",
    "parent_column",
    "child_start_column",
    "child_end_column",
}


class PdfVisualTopologyError(ValueError):
    def __init__(self, code: str, subject: str = "") -> None:
        self.code = code
        self.subject = subject
        super().__init__(code if not subject else f"{code}:{subject}")


@dataclass(frozen=True)
class PdfVisualTopologyConfig:
    policy_version: str = PDF_VISUAL_TOPOLOGY_POLICY_VERSION
    maximum_atoms: int = 1_000
    maximum_hypotheses: int = 4
    maximum_rows: int = 64
    maximum_columns: int = 24
    maximum_model_json_bytes: int = 48 * 1024
    maximum_response_json_bytes: int = 512 * 1024
    maximum_static_input_tokens: int = 18_000
    maximum_counted_input_tokens: int = 20_000
    maximum_output_tokens: int = 8192


class PdfVisualTopologyFactory:
    def __init__(self, config: PdfVisualTopologyConfig | None = None) -> None:
        self.config = config or PdfVisualTopologyConfig()

    def create(self) -> "PdfVisualTopologyRuntime":
        if self.config.policy_version != PDF_VISUAL_TOPOLOGY_POLICY_VERSION:
            raise PdfVisualTopologyError("pdf_visual_topology_policy_invalid")
        positive = (
            self.config.maximum_atoms,
            self.config.maximum_hypotheses,
            self.config.maximum_rows,
            self.config.maximum_columns,
            self.config.maximum_model_json_bytes,
            self.config.maximum_response_json_bytes,
            self.config.maximum_static_input_tokens,
            self.config.maximum_counted_input_tokens,
            self.config.maximum_output_tokens,
        )
        if min(positive) < 1:
            raise PdfVisualTopologyError("pdf_visual_topology_budget_invalid")
        return PdfVisualTopologyRuntime(
            self.config,
            _factory_token=_FACTORY_TOKEN,
        )


class PdfVisualTopologyRuntime:
    TASK_TEXT = (
        "Inspect only the supplied table crop and infer its visible grid topology. "
        "Return full normalized row and column boundary arrays; each starts with "
        "exactly 0.0 and ends with exactly 1.0, plus header depth, spans, header "
        "relations, and every materially plausible topology within the limit. "
        "Never return cell text, values, candidate ids, source refs, or business "
        "facts. Boundary evidence may be stable whitespace gutters, repeated "
        "horizontal or vertical alignment, consistent atom bands, or visible "
        "separators when present. A drawn grid is optional: the absence of drawn "
        "grid lines alone must not force unsupported. Non-line evidence must repeat "
        "coherently; one gap or text baseline is insufficient. Wrapped lines in one "
        "cell are not rows. If two-column and three-column structures are both "
        "plausible, return both hypotheses with decision ambiguous. Empty neighbors "
        "do not imply a span. Each span must cross a boundary and cover at least two "
        "positions. Use relation merged for every span, including spanning headers; "
        "header depth and hierarchy carry header meaning. Omit single-column "
        "identity header relations. Atoms are anonymous observations, not a parser "
        "grid. If no bounded answer is supportable, return unsupported, no "
        "hypotheses, and at least one precise snake_case uncertainty code in sorted "
        "order. Cross-page continuation is outside this slice."
    )
    REGION_PROPOSAL_TASK_TEXT = {
        "candidate_crop": (
            "Inspect only the supplied candidate crop. Decide whether a table is "
            "present, absent, or uncertain. If a table may be present, propose at "
            "most one normalized positive-area region inside the crop and include "
            "every materially plausible grid topology for it. Anonymous source-word "
            "atoms carry exact word text and boxes as bounded context only; they "
            "are not a parser grid and their text must not be returned."
        ),
        "page_level": (
            "Inspect only the supplied single-page image. Decide whether a table is "
            "present, absent, or uncertain. If a table may be present, propose at "
            "most two normalized positive-area, non-overlapping regions and include "
            "every materially plausible grid topology for each region. No word atoms "
            "are supplied on this path."
        ),
    }
    REGION_PROPOSAL_COMMON_TASK_TEXT = (
        "For each region report border evidence, visual density, continuation "
        "likelihood, header depth, normalized row and column boundaries, physical "
        "spans, header relations, alternatives, and precise uncertainty codes. "
        "Never return source text, values, source identifiers, business facts, "
        "acceptance thresholds, validator bypasses, or parser configuration. The "
        "proposal is untrusted: a deterministic parser and validator will reselect "
        "exact source atoms and either prove or block it."
    )

    def __init__(
        self,
        config: PdfVisualTopologyConfig,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise PdfVisualTopologyError("pdf_visual_topology_factory_required")
        self.config = config
        self.contracts = PdfDualOracleContractFactory().create()

    def build_package(
        self,
        *,
        parser_observation: dict[str, Any],
        crop_manifest: dict[str, Any],
    ) -> dict[str, Any]:
        errors = self.contracts.validate_parser_observation(parser_observation)
        construction = _object(parser_observation.get("candidate_construction"))
        if errors:
            raise PdfVisualTopologyError(errors[0])
        if (
            construction.get("kind") != "raw_word_atoms"
            or construction.get("semantic_grid_dependency") is not False
        ):
            raise PdfVisualTopologyError(
                "pdf_visual_topology_raw_word_atoms_required"
            )
        self._validate_crop_identity(parser_observation, crop_manifest)

        candidates = _dicts(parser_observation.get("candidates"))
        candidates.sort(key=lambda item: int(item.get("source_order") or 0))
        if not candidates or len(candidates) > self.config.maximum_atoms:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_atom_budget_exceeded"
            )
        table_bbox = _bbox(
            _object(parser_observation.get("coordinate_space")).get("table_bbox")
        )
        if table_bbox is None:
            raise PdfVisualTopologyError("pdf_visual_topology_table_bbox_invalid")

        atoms: list[dict[str, Any]] = []
        neutral_map: dict[str, str] = {}
        dictionary: dict[str, dict[str, Any]] = {}
        for order, candidate in enumerate(candidates):
            candidate_id = str(candidate.get("candidate_id") or "")
            bbox = _bbox(candidate.get("bbox"))
            if not candidate_id or bbox is None:
                raise PdfVisualTopologyError(
                    "pdf_visual_topology_atom_contract_invalid"
                )
            neutral_id = f"a{order + 1:04d}"
            atoms.append(
                {
                    "atom_id": neutral_id,
                    "bbox": _normalized_bbox(bbox, table_bbox),
                    "order": order,
                }
            )
            neutral_map[neutral_id] = candidate_id
            dictionary[candidate_id] = {
                "candidate_id": candidate_id,
                "exact_source_span": str(
                    candidate.get("exact_visible_value") or ""
                ),
                "source_value_refs": copy.deepcopy(
                    candidate.get("source_value_refs") or []
                ),
                "word_refs": copy.deepcopy(candidate.get("word_refs") or []),
                "source_bbox": list(bbox),
                "source_bbox_refs": copy.deepcopy(
                    candidate.get("source_bbox_refs") or []
                ),
                "source_text_checksum_refs": copy.deepcopy(
                    candidate.get("source_text_checksum_refs") or []
                ),
                "source_order": int(candidate.get("source_order") or 0),
            }

        atom_manifest_hash = sha256_json(atoms)
        dictionary_hash = sha256_json(dictionary)
        crop_hash = str(crop_manifest.get("png_sha256") or "")
        package_id = "pdfvisualtopopkg_" + stable_digest(
            [
                parser_observation.get("observation_checksum"),
                crop_manifest.get("manifest_hash"),
                atom_manifest_hash,
                self.config.policy_version,
            ],
            length=24,
        )
        model_view = {
            "schema_version": PDF_VISUAL_TOPOLOGY_REQUEST_SCHEMA,
            "task": self.TASK_TEXT,
            "input_basis": "visual_crop_plus_anonymous_word_boxes_without_parser_grid",
            "identity": {
                "package_id": package_id,
                "crop_sha256": crop_hash,
                "neutral_atom_manifest_hash": atom_manifest_hash,
            },
            "coordinate_space": {
                "kind": "crop_normalized",
                "origin": "top_left",
                "x_axis": "right",
                "y_axis": "down",
                "bounds": [0.0, 0.0, 1.0, 1.0],
            },
            "atoms": atoms,
            "output_limits": {
                "maximum_hypotheses": self.config.maximum_hypotheses,
                "maximum_rows": self.config.maximum_rows,
                "maximum_columns": self.config.maximum_columns,
                "maximum_output_tokens": self.config.maximum_output_tokens,
            },
            "rules": {
                "parser_grid_available": False,
                "parser_dimensions_available": False,
                "parser_header_depth_available": False,
                "source_values_may_be_returned": False,
                "candidate_ids_may_be_returned": False,
                "all_material_alternatives_required": True,
                "cross_page_continuation_supported": False,
                "wrapped_text_line_is_separate_row": False,
                "empty_neighbors_imply_merged_cell": False,
                "identity_header_relations_allowed": False,
                "span_requires_visible_physical_merge": True,
                "single_cell_spans_allowed": False,
                "boundary_arrays_start_at_zero_and_end_at_one": True,
                "boundary_evidence_requires_drawn_grid": False,
                "borderless_table_implies_unsupported": False,
                "unsupported_requires_uncertainty_code": True,
            },
        }
        output_schema = self.output_schema()
        model_bytes = len(canonical_json_bytes(model_view))
        schema_bytes = len(canonical_json_bytes(output_schema))
        static_tokens = (model_bytes + schema_bytes + 3) // 4
        if model_bytes > self.config.maximum_model_json_bytes:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_model_json_budget_exceeded"
            )
        if static_tokens > self.config.maximum_static_input_tokens:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_static_token_budget_exceeded"
            )

        crop_identity = {
            "crop_id": crop_manifest.get("crop_id"),
            "crop_sha256": crop_hash,
            "manifest_hash": crop_manifest.get("manifest_hash"),
            "dpi": crop_manifest.get("dpi"),
            "width": crop_manifest.get("width"),
            "height": crop_manifest.get("height"),
            "png_bytes": crop_manifest.get("png_bytes"),
            "declared_table_bbox": copy.deepcopy(
                crop_manifest.get("declared_table_bbox")
            ),
            "rendered_bbox": copy.deepcopy(crop_manifest.get("rendered_bbox")),
            "page_rotation": crop_manifest.get("page_rotation"),
            "padding_points": crop_manifest.get("padding_points"),
        }
        result = {
            "schema_version": PDF_VISUAL_TOPOLOGY_PACKAGE_SCHEMA,
            "policy_version": self.config.policy_version,
            "policy_configuration_hash": sha256_json(asdict(self.config)),
            "package_id": package_id,
            "document_ref": parser_observation.get("document_ref"),
            "pdf_sha256": parser_observation.get("pdf_sha256"),
            "page_ref": parser_observation.get("page_ref"),
            "page_number": parser_observation.get("page_number"),
            "table_ref": parser_observation.get("table_ref"),
            "parser_observation_id": parser_observation.get("observation_id"),
            "parser_observation_checksum": parser_observation.get(
                "observation_checksum"
            ),
            "crop_identity": crop_identity,
            "neutral_atom_manifest_hash": atom_manifest_hash,
            "neutral_atom_to_candidate_id": neutral_map,
            "candidate_dictionary_hash": dictionary_hash,
            "private_candidate_dictionary": dictionary,
            "model_facing": model_view,
            "output_schema": output_schema,
            "component_accounting": {
                "atom_count": len(atoms),
                "model_json_bytes": model_bytes,
                "schema_json_bytes": schema_bytes,
                "static_input_token_estimate": static_tokens,
                "maximum_atoms": self.config.maximum_atoms,
                "maximum_model_json_bytes": self.config.maximum_model_json_bytes,
                "maximum_static_input_tokens": self.config.maximum_static_input_tokens,
                "maximum_counted_input_tokens": self.config.maximum_counted_input_tokens,
                "maximum_output_tokens": self.config.maximum_output_tokens,
                "legacy_shape_tokens": 0,
            },
            "source_authority": "immutable_pdf_word_atoms_only",
            "legacy_grid_consumed": False,
            "source_values_exposed_to_model_view": False,
        }
        result["package_hash"] = sha256_json(result)
        package_errors = self.validate_package(
            parser_observation=parser_observation,
            package=result,
        )
        if package_errors:
            raise PdfVisualTopologyError(package_errors[0])
        return result

    def build_region_proposal_package(
        self,
        *,
        proposal_scope: str,
        crop_manifest: dict[str, Any],
        parser_observation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a bounded VLM proposal package without adding another wire schema."""

        if proposal_scope not in _REGION_PROPOSAL_SCOPES:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_region_proposal_scope_invalid"
            )
        maximum_regions = 1 if proposal_scope == "candidate_crop" else 2
        if proposal_scope == "candidate_crop":
            if not isinstance(parser_observation, dict):
                raise PdfVisualTopologyError(
                    "pdf_visual_topology_region_parser_observation_required"
                )
            base = self.build_package(
                parser_observation=parser_observation,
                crop_manifest=crop_manifest,
            )
            atoms = copy.deepcopy(base["model_facing"]["atoms"])
            crop_identity = copy.deepcopy(base["crop_identity"])
            neutral_map = copy.deepcopy(base["neutral_atom_to_candidate_id"])
            dictionary = copy.deepcopy(base["private_candidate_dictionary"])
            for atom in atoms:
                candidate_id = neutral_map.get(str(atom.get("atom_id") or ""))
                source = _object(dictionary.get(candidate_id))
                exact_source_span = source.get("exact_source_span")
                if not isinstance(exact_source_span, str):
                    raise PdfVisualTopologyError(
                        "pdf_visual_topology_region_atom_text_invalid"
                    )
                atom["text"] = exact_source_span
            metadata = {
                key: base.get(key)
                for key in (
                    "document_ref",
                    "pdf_sha256",
                    "page_ref",
                    "page_number",
                    "table_ref",
                    "parser_observation_id",
                    "parser_observation_checksum",
                )
            }
            source_authority = (
                "immutable_pdf_word_atoms_with_exact_text_plus_exact_crop"
            )
            source_values_exposed = True
        else:
            if parser_observation is not None:
                raise PdfVisualTopologyError(
                    "pdf_visual_topology_region_page_atoms_forbidden"
                )
            self._validate_region_crop_identity(crop_manifest)
            atoms = []
            crop_identity = self._region_crop_identity(crop_manifest)
            neutral_map = {}
            dictionary = {}
            metadata = {
                "document_ref": crop_manifest.get("document_ref"),
                "pdf_sha256": crop_manifest.get("pdf_sha256"),
                "page_ref": crop_manifest.get("page_ref"),
                "page_number": crop_manifest.get("page_number"),
                "table_ref": None,
                "parser_observation_id": None,
                "parser_observation_checksum": None,
            }
            source_authority = "immutable_single_pdf_page_crop_only"
            source_values_exposed = False

        atom_manifest_hash = sha256_json(atoms)
        dictionary_hash = sha256_json(dictionary)
        package_id = "pdfvisualregionpkg_" + stable_digest(
            [
                metadata["pdf_sha256"],
                metadata["page_number"],
                crop_identity.get("manifest_hash"),
                proposal_scope,
                atom_manifest_hash,
                self.config.policy_version,
                PDF_VISUAL_TOPOLOGY_REGION_PROPOSAL_REVISION,
            ],
            length=24,
        )
        model_view = {
            "schema_version": PDF_VISUAL_TOPOLOGY_REQUEST_SCHEMA,
            "contract_revision": PDF_VISUAL_TOPOLOGY_REGION_PROPOSAL_REVISION,
            "task": self._region_proposal_task(proposal_scope),
            "proposal_scope": proposal_scope,
            "input_basis": self._region_proposal_input_basis(proposal_scope),
            "identity": {
                "package_id": package_id,
            },
            "coordinate_space": {
                "kind": "crop_normalized",
                "origin": "top_left",
                "x_axis": "right",
                "y_axis": "down",
                "bounds": [0.0, 0.0, 1.0, 1.0],
            },
            "atoms": atoms,
            "output_limits": self._region_proposal_output_limits(proposal_scope),
            "rules": self._region_proposal_rules(proposal_scope),
        }
        output_schema = self.region_proposal_output_schema(
            proposal_scope=proposal_scope
        )
        model_bytes = len(canonical_json_bytes(model_view))
        schema_bytes = len(canonical_json_bytes(output_schema))
        static_tokens = (model_bytes + schema_bytes + 3) // 4
        if model_bytes > self.config.maximum_model_json_bytes:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_model_json_budget_exceeded"
            )
        if static_tokens > self.config.maximum_static_input_tokens:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_static_token_budget_exceeded"
            )
        if static_tokens > self.config.maximum_counted_input_tokens:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_counted_input_budget_exceeded"
            )

        result = {
            "schema_version": PDF_VISUAL_TOPOLOGY_PACKAGE_SCHEMA,
            "contract_revision": PDF_VISUAL_TOPOLOGY_REGION_PROPOSAL_REVISION,
            "proposal_scope": proposal_scope,
            "policy_version": self.config.policy_version,
            "policy_configuration_hash": sha256_json(asdict(self.config)),
            "package_id": package_id,
            **metadata,
            "crop_identity": crop_identity,
            "neutral_atom_manifest_hash": atom_manifest_hash,
            "neutral_atom_to_candidate_id": neutral_map,
            "candidate_dictionary_hash": dictionary_hash,
            "private_candidate_dictionary": dictionary,
            "model_facing": model_view,
            "output_schema": output_schema,
            "component_accounting": {
                "atom_count": len(atoms),
                "maximum_regions": maximum_regions,
                "model_json_bytes": model_bytes,
                "schema_json_bytes": schema_bytes,
                "static_input_token_estimate": static_tokens,
                "maximum_atoms": self.config.maximum_atoms,
                "maximum_model_json_bytes": self.config.maximum_model_json_bytes,
                "maximum_static_input_tokens": self.config.maximum_static_input_tokens,
                "maximum_counted_input_tokens": self.config.maximum_counted_input_tokens,
                "maximum_output_tokens": self.config.maximum_output_tokens,
                "legacy_shape_tokens": 0,
            },
            "source_authority": source_authority,
            "legacy_grid_consumed": False,
            "source_values_exposed_to_model_view": source_values_exposed,
        }
        result["package_hash"] = sha256_json(result)
        errors = self.validate_region_proposal_package(result)
        if errors:
            raise PdfVisualTopologyError(errors[0])
        return result

    def _region_proposal_task(self, proposal_scope: str) -> str:
        return (
            self.REGION_PROPOSAL_TASK_TEXT[proposal_scope]
            + " "
            + self.REGION_PROPOSAL_COMMON_TASK_TEXT
        )

    @staticmethod
    def _region_proposal_input_basis(proposal_scope: str) -> str:
        return (
            "visual_candidate_crop_plus_anonymous_exact_word_text_and_boxes_"
            "without_parser_grid"
            if proposal_scope == "candidate_crop"
            else "visual_single_page_crop_without_word_atoms_or_parser_grid"
        )

    def _region_proposal_output_limits(
        self, proposal_scope: str
    ) -> dict[str, int]:
        return {
            "maximum_regions": 1 if proposal_scope == "candidate_crop" else 2,
            "maximum_hypotheses_per_region": self.config.maximum_hypotheses,
            "maximum_rows": self.config.maximum_rows,
            "maximum_columns": self.config.maximum_columns,
            "maximum_output_tokens": self.config.maximum_output_tokens,
        }

    @staticmethod
    def _region_proposal_rules(proposal_scope: str) -> dict[str, bool]:
        return {
            "parser_grid_available": False,
            "parser_dimensions_available": False,
            "exact_source_word_text_available": proposal_scope == "candidate_crop",
            "exact_source_word_text_may_be_returned": False,
            "source_values_may_be_returned": False,
            "source_identifiers_may_be_returned": False,
            "business_facts_may_be_returned": False,
            "acceptance_thresholds_may_be_returned": False,
            "validator_bypasses_may_be_returned": False,
            "parser_configuration_may_be_returned": False,
            "region_boxes_are_normalized": True,
            "region_boxes_must_have_positive_area": True,
            "regions_must_not_overlap": True,
            "all_material_alternatives_required": True,
            "exact_atoms_are_reselected_after_proposal": True,
        }

    def validate_region_proposal_package(self, package: Any) -> list[str]:
        data = _object(package)
        errors: list[str] = []
        if set(data) != _REGION_PROPOSAL_PACKAGE_KEYS:
            return ["pdf_visual_topology_region_package_keys_invalid"]
        scope = data.get("proposal_scope")
        if scope not in _REGION_PROPOSAL_SCOPES:
            errors.append("pdf_visual_topology_region_proposal_scope_invalid")
            return errors
        if (
            data.get("schema_version") != PDF_VISUAL_TOPOLOGY_PACKAGE_SCHEMA
            or data.get("contract_revision")
            != PDF_VISUAL_TOPOLOGY_REGION_PROPOSAL_REVISION
            or data.get("policy_version") != self.config.policy_version
            or data.get("policy_configuration_hash")
            != sha256_json(asdict(self.config))
        ):
            errors.append("pdf_visual_topology_region_package_contract_invalid")

        model_view = _object(data.get("model_facing"))
        atoms = model_view.get("atoms")
        maximum_regions = 1 if scope == "candidate_crop" else 2
        if (
            set(model_view) != _REGION_MODEL_KEYS
            or model_view.get("schema_version") != PDF_VISUAL_TOPOLOGY_REQUEST_SCHEMA
            or model_view.get("contract_revision")
            != PDF_VISUAL_TOPOLOGY_REGION_PROPOSAL_REVISION
            or model_view.get("proposal_scope") != scope
            or model_view.get("task") != self._region_proposal_task(scope)
            or model_view.get("input_basis")
            != self._region_proposal_input_basis(scope)
            or model_view.get("coordinate_space")
            != {
                "kind": "crop_normalized",
                "origin": "top_left",
                "x_axis": "right",
                "y_axis": "down",
                "bounds": [0.0, 0.0, 1.0, 1.0],
            }
            or model_view.get("output_limits")
            != self._region_proposal_output_limits(scope)
            or model_view.get("rules") != self._region_proposal_rules(scope)
            or not isinstance(atoms, list)
        ):
            errors.append("pdf_visual_topology_region_model_contract_invalid")
            atoms = []
        if scope == "page_level" and atoms != []:
            errors.append("pdf_visual_topology_region_page_atoms_forbidden")
        if scope == "candidate_crop" and (
            not atoms or len(atoms) > self.config.maximum_atoms
        ):
            errors.append("pdf_visual_topology_atom_budget_exceeded")
        if isinstance(atoms, list):
            for order, atom in enumerate(atoms):
                expected_keys = (
                    {"atom_id", "bbox", "order", "text"}
                    if scope == "candidate_crop"
                    else {"atom_id", "bbox", "order"}
                )
                if (
                    not isinstance(atom, dict)
                    or set(atom) != expected_keys
                    or atom.get("atom_id") != f"a{order + 1:04d}"
                    or atom.get("order") != order
                    or not _normalized_box(atom.get("bbox"))
                    or (
                        scope == "candidate_crop"
                        and not isinstance(atom.get("text"), str)
                    )
                ):
                    errors.append("pdf_visual_topology_region_atom_contract_invalid")
                    break
        if data.get("neutral_atom_manifest_hash") != sha256_json(atoms):
            errors.append("pdf_visual_topology_region_atom_manifest_invalid")
        neutral_map = _object(data.get("neutral_atom_to_candidate_id"))
        dictionary = _object(data.get("private_candidate_dictionary"))
        if (
            data.get("candidate_dictionary_hash") != sha256_json(dictionary)
            or (scope == "page_level" and (neutral_map or dictionary))
            or (
                scope == "candidate_crop"
                and (
                    set(neutral_map) != {
                        str(atom.get("atom_id"))
                        for atom in atoms
                        if isinstance(atom, dict)
                    }
                    or set(dictionary) != set(neutral_map.values())
                )
            )
        ):
            errors.append("pdf_visual_topology_region_dictionary_invalid")
        if scope == "candidate_crop" and isinstance(atoms, list):
            for atom in atoms:
                candidate_id = neutral_map.get(str(atom.get("atom_id") or ""))
                source = _object(dictionary.get(candidate_id))
                if (
                    not isinstance(candidate_id, str)
                    or not candidate_id
                    or set(source)
                    != {
                        "candidate_id",
                        "exact_source_span",
                        "source_value_refs",
                        "word_refs",
                        "source_bbox",
                        "source_bbox_refs",
                        "source_text_checksum_refs",
                        "source_order",
                    }
                    or source.get("candidate_id") != candidate_id
                    or source.get("exact_source_span") != atom.get("text")
                ):
                    errors.append(
                        "pdf_visual_topology_region_atom_text_derivation_invalid"
                    )
                    break
        identity = _object(model_view.get("identity"))
        crop = _object(data.get("crop_identity"))
        if (
            set(crop) != _CROP_IDENTITY_KEYS
            or _bbox(crop.get("declared_table_bbox")) is None
            or crop.get("rendered_bbox") != crop.get("declared_table_bbox")
            or crop.get("page_rotation") != 0
            or crop.get("padding_points") != 0.0
        ):
            errors.append("pdf_visual_topology_region_crop_identity_invalid")
        if identity != {"package_id": data.get("package_id")}:
            errors.append("pdf_visual_topology_region_model_identity_invalid")
        expected_package_id = "pdfvisualregionpkg_" + stable_digest(
            [
                data.get("pdf_sha256"),
                data.get("page_number"),
                crop.get("manifest_hash"),
                scope,
                data.get("neutral_atom_manifest_hash"),
                self.config.policy_version,
                PDF_VISUAL_TOPOLOGY_REGION_PROPOSAL_REVISION,
            ],
            length=24,
        )
        if data.get("package_id") != expected_package_id:
            errors.append("pdf_visual_topology_region_package_identity_invalid")
        if data.get("output_schema") != self.region_proposal_output_schema(
            proposal_scope=scope
        ):
            errors.append("pdf_visual_topology_region_output_schema_invalid")
        accounting = _object(data.get("component_accounting"))
        model_bytes = len(canonical_json_bytes(model_view))
        schema_bytes = len(canonical_json_bytes(data.get("output_schema")))
        static_tokens = (model_bytes + schema_bytes + 3) // 4
        if (
            accounting.get("atom_count") != len(atoms)
            or accounting.get("maximum_regions") != maximum_regions
            or accounting.get("model_json_bytes") != model_bytes
            or accounting.get("schema_json_bytes") != schema_bytes
            or accounting.get("static_input_token_estimate") != static_tokens
            or accounting.get("maximum_atoms") != self.config.maximum_atoms
            or accounting.get("maximum_model_json_bytes")
            != self.config.maximum_model_json_bytes
            or accounting.get("maximum_static_input_tokens")
            != self.config.maximum_static_input_tokens
            or accounting.get("maximum_counted_input_tokens")
            != self.config.maximum_counted_input_tokens
            or accounting.get("maximum_output_tokens")
            != self.config.maximum_output_tokens
            or accounting.get("legacy_shape_tokens") != 0
            or model_bytes > self.config.maximum_model_json_bytes
            or static_tokens > self.config.maximum_static_input_tokens
            or static_tokens > self.config.maximum_counted_input_tokens
        ):
            errors.append("pdf_visual_topology_region_accounting_invalid")
        expected_authority = (
            "immutable_pdf_word_atoms_with_exact_text_plus_exact_crop"
            if scope == "candidate_crop"
            else "immutable_single_pdf_page_crop_only"
        )
        expected_source_values_exposed = scope == "candidate_crop"
        if (
            data.get("source_authority") != expected_authority
            or data.get("legacy_grid_consumed") is not False
            or data.get("source_values_exposed_to_model_view")
            is not expected_source_values_exposed
        ):
            errors.append("pdf_visual_topology_region_source_authority_invalid")
        unsigned = dict(data)
        stored_hash = unsigned.pop("package_hash", None)
        if stored_hash != sha256_json(unsigned):
            errors.append("pdf_visual_topology_region_package_hash_invalid")
        return sorted(set(errors))

    def build_ledger_package(
        self,
        *,
        parser_observation: dict[str, Any],
        crop_manifest: dict[str, Any],
    ) -> dict[str, Any]:
        """Build a sealed full-table ledger that is forbidden as provider input."""

        base = self.build_package(
            parser_observation=parser_observation,
            crop_manifest=crop_manifest,
        )
        result = copy.deepcopy(base)
        result["schema_version"] = PDF_VISUAL_TOPOLOGY_LEDGER_PACKAGE_SCHEMA
        result["package_purpose"] = "sealed_full_table_assembly_ledger_only"
        result["provider_input_allowed"] = False
        result["package_hash"] = sha256_json(
            {key: value for key, value in result.items() if key != "package_hash"}
        )
        errors = self.validate_ledger_package(
            parser_observation=parser_observation,
            package=result,
        )
        if errors:
            raise PdfVisualTopologyError(errors[0])
        return result

    def validate_ledger_package(
        self,
        *,
        parser_observation: dict[str, Any],
        package: Any,
    ) -> list[str]:
        data = _object(package)
        errors: list[str] = []
        if set(data) != _LEDGER_PACKAGE_KEYS:
            return ["pdf_visual_topology_ledger_package_keys_invalid"]
        if (
            data.get("schema_version")
            != PDF_VISUAL_TOPOLOGY_LEDGER_PACKAGE_SCHEMA
            or data.get("package_purpose")
            != "sealed_full_table_assembly_ledger_only"
            or data.get("provider_input_allowed") is not False
        ):
            errors.append("pdf_visual_topology_ledger_authority_invalid")
        unsigned = dict(data)
        stored = unsigned.pop("package_hash", None)
        if stored != sha256_json(unsigned):
            errors.append("pdf_visual_topology_ledger_package_hash_invalid")
        base = copy.deepcopy(data)
        base.pop("package_purpose", None)
        base.pop("provider_input_allowed", None)
        base["schema_version"] = PDF_VISUAL_TOPOLOGY_PACKAGE_SCHEMA
        base["package_hash"] = sha256_json(
            {key: value for key, value in base.items() if key != "package_hash"}
        )
        errors.extend(
            self.validate_package(
                parser_observation=parser_observation,
                package=base,
            )
        )
        return sorted(set(errors))

    def build_window_package(
        self,
        *,
        parser_observation: dict[str, Any],
        full_package: dict[str, Any],
        window_plan: dict[str, Any],
        window: dict[str, Any],
        crop_manifest: dict[str, Any],
    ) -> dict[str, Any]:
        """Build a value-free request for one full-width vertical crop."""

        if self.contracts.validate_parser_observation(parser_observation):
            raise PdfVisualTopologyError(
                "pdf_visual_topology_window_parser_invalid"
            )
        if (
            full_package.get("parser_observation_id")
            != parser_observation.get("observation_id")
            or full_package.get("parser_observation_checksum")
            != parser_observation.get("observation_checksum")
            or not full_package.get("package_id")
            or not full_package.get("package_hash")
        ):
            raise PdfVisualTopologyError(
                "pdf_visual_topology_window_full_package_invalid"
            )
        owner_ids = [
            str(item) for item in window.get("owner_candidate_ids") or []
        ]
        candidate_order = [
            str(item) for item in parser_observation.get("candidate_order") or []
        ]
        candidate_by_id = {
            str(item.get("candidate_id") or ""): item
            for item in _dicts(parser_observation.get("candidates"))
        }
        maximum_owner_atoms = int(
            window_plan.get("maximum_owner_atoms_per_window") or 0
        )
        if (
            window_plan.get("parser_observation_checksum")
            != parser_observation.get("observation_checksum")
            or window_plan.get("plan_hash") is None
            or window.get("window_id") is None
            or window not in _dicts(window_plan.get("windows"))
            or not owner_ids
            or len(owner_ids) != len(set(owner_ids))
            or len(owner_ids) != window.get("owner_atom_count")
            or len(owner_ids) > maximum_owner_atoms
            or any(candidate_id not in candidate_by_id for candidate_id in owner_ids)
            or owner_ids
            != [item for item in candidate_order if item in set(owner_ids)]
            or window.get("full_width") is not True
            or window.get("column_splitting_used") is not False
        ):
            raise PdfVisualTopologyError(
                "pdf_visual_topology_window_contract_invalid"
            )
        self._validate_window_crop_identity(
            parser_observation=parser_observation,
            window=window,
            crop_manifest=crop_manifest,
        )
        crop_bbox = _bbox(window.get("crop_bbox"))
        if crop_bbox is None:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_window_crop_identity_invalid"
            )

        atoms: list[dict[str, Any]] = []
        neutral_map: dict[str, str] = {}
        dictionary: dict[str, dict[str, Any]] = {}
        for order, candidate_id in enumerate(owner_ids):
            candidate = candidate_by_id[candidate_id]
            bbox = _bbox(candidate.get("bbox"))
            if bbox is None or not (
                crop_bbox[0] <= bbox[0] < bbox[2] <= crop_bbox[2]
                and crop_bbox[1] <= bbox[1] < bbox[3] <= crop_bbox[3]
            ):
                raise PdfVisualTopologyError(
                    "pdf_visual_topology_window_atom_outside_crop"
                )
            neutral_id = f"a{order + 1:04d}"
            atoms.append(
                {
                    "atom_id": neutral_id,
                    "bbox": _normalized_bbox(bbox, crop_bbox),
                    "order": order,
                }
            )
            neutral_map[neutral_id] = candidate_id
            dictionary[candidate_id] = {
                "candidate_id": candidate_id,
                "exact_source_span": str(
                    candidate.get("exact_visible_value") or ""
                ),
                "source_value_refs": copy.deepcopy(
                    candidate.get("source_value_refs") or []
                ),
                "word_refs": copy.deepcopy(candidate.get("word_refs") or []),
                "source_bbox": list(bbox),
                "source_bbox_refs": copy.deepcopy(
                    candidate.get("source_bbox_refs") or []
                ),
                "source_text_checksum_refs": copy.deepcopy(
                    candidate.get("source_text_checksum_refs") or []
                ),
                "source_order": int(candidate.get("source_order") or 0),
            }

        atom_manifest_hash = sha256_json(atoms)
        dictionary_hash = sha256_json(dictionary)
        crop_hash = str(crop_manifest.get("png_sha256") or "")
        package_id = "pdfvisualtopowinpkg_" + stable_digest(
            [
                full_package.get("package_hash"),
                window_plan.get("plan_hash"),
                window.get("window_id"),
                crop_manifest.get("manifest_hash"),
                atom_manifest_hash,
                self.config.policy_version,
            ],
            length=24,
        )
        core_y = copy.deepcopy(window.get("core_y_normalized_in_crop"))
        window_identity = {
            "window_id": window.get("window_id"),
            "window_index": window.get("window_index"),
            "window_count": window_plan.get("window_count"),
            "owner_atom_count": len(atoms),
            "core_y_normalized_in_crop": core_y,
            "full_width": True,
            "column_splitting_used": False,
        }
        model_view = {
            "schema_version": PDF_VISUAL_TOPOLOGY_REQUEST_SCHEMA,
            "task": (
                self.TASK_TEXT
                + " This request is one full-width vertical window of a larger "
                "table. Infer every physical row boundary visible in this crop, "
                "including the two stated core edges when visually supported. "
                "Only the first window may report table header rows; every later "
                "window must return header_row_count 0. The window scheduler "
                "already handles adjacent vertical windows: continuation_required "
                "MUST be false in every hypothesis and must not describe the next "
                "window."
            ),
            "input_basis": (
                "visual_full_width_vertical_crop_plus_anonymous_owner_word_boxes_"
                "without_parser_grid"
            ),
            "identity": {
                "package_id": package_id,
                "crop_sha256": crop_hash,
                "neutral_atom_manifest_hash": atom_manifest_hash,
            },
            "coordinate_space": {
                "kind": "crop_normalized",
                "origin": "top_left",
                "x_axis": "right",
                "y_axis": "down",
                "bounds": [0.0, 0.0, 1.0, 1.0],
            },
            "window": copy.deepcopy(window_identity),
            "atoms": atoms,
            "output_limits": {
                "maximum_hypotheses": self.config.maximum_hypotheses,
                "maximum_rows": self.config.maximum_rows,
                "maximum_columns": self.config.maximum_columns,
                "maximum_output_tokens": self.config.maximum_output_tokens,
            },
            "rules": {
                "parser_grid_available": False,
                "parser_dimensions_available": False,
                "parser_header_depth_available": False,
                "source_values_may_be_returned": False,
                "candidate_ids_may_be_returned": False,
                "all_material_alternatives_required": True,
                "cross_page_continuation_supported": False,
                "wrapped_text_line_is_separate_row": False,
                "empty_neighbors_imply_merged_cell": False,
                "identity_header_relations_allowed": False,
                "span_requires_visible_physical_merge": True,
                "single_cell_spans_allowed": False,
                "boundary_arrays_start_at_zero_and_end_at_one": True,
                "boundary_evidence_requires_drawn_grid": False,
                "borderless_table_implies_unsupported": False,
                "unsupported_requires_uncertainty_code": True,
                "full_width_vertical_window": True,
                "column_splitting_used": False,
                "header_rows_allowed": window.get("window_index") == 1,
            },
        }
        output_schema = self.output_schema()
        model_bytes = len(canonical_json_bytes(model_view))
        schema_bytes = len(canonical_json_bytes(output_schema))
        static_tokens = (model_bytes + schema_bytes + 3) // 4
        if model_bytes > self.config.maximum_model_json_bytes:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_model_json_budget_exceeded"
            )
        if static_tokens > self.config.maximum_static_input_tokens:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_static_token_budget_exceeded"
            )
        crop_identity = {
            "crop_id": crop_manifest.get("crop_id"),
            "crop_sha256": crop_hash,
            "manifest_hash": crop_manifest.get("manifest_hash"),
            "dpi": crop_manifest.get("dpi"),
            "width": crop_manifest.get("width"),
            "height": crop_manifest.get("height"),
            "png_bytes": crop_manifest.get("png_bytes"),
            "declared_table_bbox": copy.deepcopy(
                crop_manifest.get("declared_table_bbox")
            ),
            "rendered_bbox": copy.deepcopy(crop_manifest.get("rendered_bbox")),
            "page_rotation": crop_manifest.get("page_rotation"),
            "padding_points": crop_manifest.get("padding_points"),
        }
        result = {
            "schema_version": PDF_VISUAL_TOPOLOGY_WINDOW_PACKAGE_SCHEMA,
            "policy_version": self.config.policy_version,
            "policy_configuration_hash": sha256_json(asdict(self.config)),
            "package_id": package_id,
            "document_ref": parser_observation.get("document_ref"),
            "pdf_sha256": parser_observation.get("pdf_sha256"),
            "page_ref": parser_observation.get("page_ref"),
            "page_number": parser_observation.get("page_number"),
            "table_ref": parser_observation.get("table_ref"),
            "parser_observation_id": parser_observation.get("observation_id"),
            "parser_observation_checksum": parser_observation.get(
                "observation_checksum"
            ),
            "full_package_id": full_package.get("package_id"),
            "full_package_hash": full_package.get("package_hash"),
            "window_plan_hash": window_plan.get("plan_hash"),
            "window_identity": window_identity,
            "crop_identity": crop_identity,
            "neutral_atom_manifest_hash": atom_manifest_hash,
            "neutral_atom_to_candidate_id": neutral_map,
            "candidate_dictionary_hash": dictionary_hash,
            "private_candidate_dictionary": dictionary,
            "model_facing": model_view,
            "output_schema": output_schema,
            "component_accounting": {
                "atom_count": len(atoms),
                "model_json_bytes": model_bytes,
                "schema_json_bytes": schema_bytes,
                "static_input_token_estimate": static_tokens,
                "maximum_atoms": maximum_owner_atoms,
                "maximum_model_json_bytes": self.config.maximum_model_json_bytes,
                "maximum_static_input_tokens": self.config.maximum_static_input_tokens,
                "maximum_counted_input_tokens": self.config.maximum_counted_input_tokens,
                "maximum_output_tokens": self.config.maximum_output_tokens,
                "legacy_shape_tokens": 0,
            },
            "source_authority": "immutable_pdf_word_atoms_only",
            "legacy_grid_consumed": False,
            "source_values_exposed_to_model_view": False,
        }
        result["package_hash"] = sha256_json(result)
        errors = self.validate_window_package(
            parser_observation=parser_observation,
            full_package=full_package,
            window_plan=window_plan,
            window=window,
            package=result,
        )
        if errors:
            raise PdfVisualTopologyError(errors[0])
        return result

    def validate_window_package(
        self,
        *,
        parser_observation: dict[str, Any],
        full_package: dict[str, Any],
        window_plan: dict[str, Any],
        window: dict[str, Any],
        package: Any,
    ) -> list[str]:
        data = _object(package)
        errors: list[str] = []
        if set(data) != _WINDOW_PACKAGE_KEYS:
            return ["pdf_visual_topology_window_package_keys_invalid"]
        if (
            data.get("schema_version")
            != PDF_VISUAL_TOPOLOGY_WINDOW_PACKAGE_SCHEMA
            or data.get("policy_version") != self.config.policy_version
            or data.get("policy_configuration_hash")
            != sha256_json(asdict(self.config))
            or data.get("parser_observation_id")
            != parser_observation.get("observation_id")
            or data.get("parser_observation_checksum")
            != parser_observation.get("observation_checksum")
            or data.get("full_package_id") != full_package.get("package_id")
            or data.get("full_package_hash") != full_package.get("package_hash")
            or data.get("window_plan_hash") != window_plan.get("plan_hash")
            or data.get("legacy_grid_consumed") is not False
            or data.get("source_values_exposed_to_model_view") is not False
            or data.get("source_authority") != "immutable_pdf_word_atoms_only"
        ):
            errors.append("pdf_visual_topology_window_identity_invalid")
        model_view = _object(data.get("model_facing"))
        if (
            set(model_view)
            != {
                "schema_version",
                "task",
                "input_basis",
                "identity",
                "coordinate_space",
                "window",
                "atoms",
                "output_limits",
                "rules",
            }
            or model_view.get("schema_version")
            != PDF_VISUAL_TOPOLOGY_REQUEST_SCHEMA
            or model_view.get("window") != data.get("window_identity")
            or _object(model_view.get("rules")).get("parser_grid_available")
            is not False
            or _object(model_view.get("rules")).get("column_splitting_used")
            is not False
        ):
            errors.append("pdf_visual_topology_window_model_view_invalid")
        atoms = _dicts(model_view.get("atoms"))
        atom_ids = [str(item.get("atom_id") or "") for item in atoms]
        owner_ids = [str(item) for item in window.get("owner_candidate_ids") or []]
        neutral_map = _object(data.get("neutral_atom_to_candidate_id"))
        if (
            not atoms
            or len(atoms) != window.get("owner_atom_count")
            or len(atoms)
            > int(window_plan.get("maximum_owner_atoms_per_window") or 0)
            or any(
                set(atom) != {"atom_id", "bbox", "order"}
                or atom.get("atom_id") != f"a{index:04d}"
                or atom.get("order") != index - 1
                or not _normalized_box(atom.get("bbox"))
                for index, atom in enumerate(atoms, start=1)
            )
            or list(neutral_map) != atom_ids
            or [neutral_map.get(atom_id) for atom_id in atom_ids] != owner_ids
            or data.get("neutral_atom_manifest_hash") != sha256_json(atoms)
        ):
            errors.append("pdf_visual_topology_window_atom_manifest_invalid")
        dictionary = _object(data.get("private_candidate_dictionary"))
        candidates = {
            str(item.get("candidate_id") or ""): item
            for item in _dicts(parser_observation.get("candidates"))
        }
        if (
            set(dictionary) != set(owner_ids)
            or data.get("candidate_dictionary_hash") != sha256_json(dictionary)
            or any(candidate_id not in candidates for candidate_id in owner_ids)
        ):
            errors.append("pdf_visual_topology_window_dictionary_invalid")
        identity = _object(model_view.get("identity"))
        crop = _object(data.get("crop_identity"))
        if identity != {
            "package_id": data.get("package_id"),
            "crop_sha256": crop.get("crop_sha256"),
            "neutral_atom_manifest_hash": data.get("neutral_atom_manifest_hash"),
        }:
            errors.append("pdf_visual_topology_window_model_identity_invalid")
        expected_package_id = "pdfvisualtopowinpkg_" + stable_digest(
            [
                full_package.get("package_hash"),
                window_plan.get("plan_hash"),
                window.get("window_id"),
                crop.get("manifest_hash"),
                data.get("neutral_atom_manifest_hash"),
                self.config.policy_version,
            ],
            length=24,
        )
        if data.get("package_id") != expected_package_id:
            errors.append("pdf_visual_topology_window_package_identity_invalid")
        if data.get("output_schema") != self.output_schema():
            errors.append("pdf_visual_topology_output_schema_invalid")
        if len(canonical_json_bytes(model_view)) > self.config.maximum_model_json_bytes:
            errors.append("pdf_visual_topology_model_json_budget_exceeded")
        unsigned = dict(data)
        stored = unsigned.pop("package_hash", None)
        if stored != sha256_json(unsigned):
            errors.append("pdf_visual_topology_window_package_hash_invalid")
        return sorted(set(errors))

    def validate_package(
        self,
        *,
        parser_observation: dict[str, Any],
        package: Any,
    ) -> list[str]:
        data = _object(package)
        if data.get("schema_version") == PDF_VISUAL_TOPOLOGY_LEDGER_PACKAGE_SCHEMA:
            return self.validate_ledger_package(
                parser_observation=parser_observation,
                package=data,
            )
        errors: list[str] = []
        if set(data) != _PACKAGE_KEYS:
            errors.append("pdf_visual_topology_package_keys_invalid")
        if data.get("schema_version") != PDF_VISUAL_TOPOLOGY_PACKAGE_SCHEMA:
            errors.append("pdf_visual_topology_package_schema_invalid")
        if data.get("policy_version") != self.config.policy_version:
            errors.append("pdf_visual_topology_package_policy_invalid")
        if data.get("policy_configuration_hash") != sha256_json(
            asdict(self.config)
        ):
            errors.append("pdf_visual_topology_package_config_invalid")
        if (
            data.get("parser_observation_id")
            != parser_observation.get("observation_id")
            or data.get("parser_observation_checksum")
            != parser_observation.get("observation_checksum")
        ):
            errors.append("pdf_visual_topology_parser_identity_mismatch")
        if (
            data.get("legacy_grid_consumed") is not False
            or data.get("source_values_exposed_to_model_view") is not False
            or data.get("source_authority") != "immutable_pdf_word_atoms_only"
        ):
            errors.append("pdf_visual_topology_authority_boundary_invalid")

        model_view = _object(data.get("model_facing"))
        allowed_model_keys = {
            "schema_version",
            "task",
            "input_basis",
            "identity",
            "coordinate_space",
            "atoms",
            "output_limits",
            "rules",
        }
        if (
            set(model_view) != allowed_model_keys
            or model_view.get("schema_version")
            != PDF_VISUAL_TOPOLOGY_REQUEST_SCHEMA
        ):
            errors.append("pdf_visual_topology_model_view_invalid")
        atoms_value = model_view.get("atoms")
        atoms = _dicts(atoms_value)
        if (
            not isinstance(atoms_value, list)
            or len(atoms) != len(atoms_value)
            or not atoms
            or len(atoms) > self.config.maximum_atoms
        ):
            errors.append("pdf_visual_topology_atom_manifest_invalid")
        atom_ids: list[str] = []
        for order, atom in enumerate(atoms):
            atom_ids.append(str(atom.get("atom_id") or ""))
            if (
                set(atom) != {"atom_id", "bbox", "order"}
                or atom.get("atom_id") != f"a{order + 1:04d}"
                or atom.get("order") != order
                or not _normalized_box(atom.get("bbox"))
            ):
                errors.append("pdf_visual_topology_atom_contract_invalid")
        if len(atom_ids) != len(set(atom_ids)):
            errors.append("pdf_visual_topology_atom_identity_duplicate")
        if data.get("neutral_atom_manifest_hash") != sha256_json(atoms):
            errors.append("pdf_visual_topology_atom_manifest_hash_invalid")
        neutral_map = _object(data.get("neutral_atom_to_candidate_id"))
        candidate_order = [
            str(item) for item in parser_observation.get("candidate_order") or []
        ]
        if (
            set(neutral_map) != set(atom_ids)
            or [neutral_map.get(atom_id) for atom_id in atom_ids] != candidate_order
        ):
            errors.append("pdf_visual_topology_atom_candidate_map_invalid")
        dictionary = _object(data.get("private_candidate_dictionary"))
        if (
            set(dictionary) != set(candidate_order)
            or data.get("candidate_dictionary_hash") != sha256_json(dictionary)
        ):
            errors.append("pdf_visual_topology_candidate_dictionary_invalid")
        candidates = {
            str(item.get("candidate_id") or ""): item
            for item in _dicts(parser_observation.get("candidates"))
        }
        for candidate_id in candidate_order:
            source = _object(dictionary.get(candidate_id))
            candidate = _object(candidates.get(candidate_id))
            if (
                set(source)
                != {
                    "candidate_id",
                    "exact_source_span",
                    "source_value_refs",
                    "word_refs",
                    "source_bbox",
                    "source_bbox_refs",
                    "source_text_checksum_refs",
                    "source_order",
                }
                or source.get("candidate_id") != candidate_id
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
                errors.append("pdf_visual_topology_candidate_derivation_invalid")
                break
        identity = _object(model_view.get("identity"))
        crop = _object(data.get("crop_identity"))
        if (
            identity
            != {
                "package_id": data.get("package_id"),
                "crop_sha256": crop.get("crop_sha256"),
                "neutral_atom_manifest_hash": data.get(
                    "neutral_atom_manifest_hash"
                ),
            }
        ):
            errors.append("pdf_visual_topology_model_identity_invalid")
        expected_package_id = "pdfvisualtopopkg_" + stable_digest(
            [
                parser_observation.get("observation_checksum"),
                crop.get("manifest_hash"),
                data.get("neutral_atom_manifest_hash"),
                self.config.policy_version,
            ],
            length=24,
        )
        if data.get("package_id") != expected_package_id:
            errors.append("pdf_visual_topology_package_identity_invalid")
        if data.get("output_schema") != self.output_schema():
            errors.append("pdf_visual_topology_output_schema_invalid")
        if len(canonical_json_bytes(model_view)) > self.config.maximum_model_json_bytes:
            errors.append("pdf_visual_topology_model_json_budget_exceeded")
        unsigned = dict(data)
        stored = unsigned.pop("package_hash", None)
        if stored != sha256_json(unsigned):
            errors.append("pdf_visual_topology_package_hash_invalid")
        return sorted(set(errors))

    def region_proposal_output_schema(
        self, *, proposal_scope: str
    ) -> dict[str, Any]:
        if proposal_scope not in _REGION_PROPOSAL_SCOPES:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_region_proposal_scope_invalid"
            )
        maximum_regions = 1 if proposal_scope == "candidate_crop" else 2
        hypothesis = copy.deepcopy(
            self.output_schema()["properties"]["hypotheses"]["items"]
        )
        region = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "region_key": {"type": "string"},
                "bbox": {
                    "type": "array",
                    "minItems": 4,
                    "maxItems": 4,
                    "items": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                    },
                    "description": (
                        "Normalized [x0,y0,x1,y1] inside the supplied crop, with "
                        "strictly positive width and height."
                    ),
                },
                "border_evidence": {
                    "type": "string",
                    "enum": sorted(_BORDER_EVIDENCE),
                },
                "density": {"type": "string", "enum": sorted(_DENSITY)},
                "continuation_likelihood": {
                    "type": "string",
                    "enum": sorted(_CONTINUATION_LIKELIHOOD),
                },
                "hypotheses": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": self.config.maximum_hypotheses,
                    "items": hypothesis,
                },
                "uncertainty_codes": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": sorted(_REGION_PROPOSAL_KEYS),
        }
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "schema_version": {
                    "type": "string",
                    "enum": [PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA],
                },
                "contract_revision": {
                    "type": "string",
                    "enum": [PDF_VISUAL_TOPOLOGY_REGION_PROPOSAL_REVISION],
                },
                "package_id": {"type": "string"},
                "proposal_scope": {
                    "type": "string",
                    "enum": [proposal_scope],
                },
                "table_presence": {
                    "type": "string",
                    "enum": sorted(_TABLE_PRESENCE),
                },
                "alternatives_complete": {"type": "boolean", "enum": [True]},
                "regions": {
                    "type": "array",
                    "minItems": 0,
                    "maxItems": maximum_regions,
                    "items": region,
                },
                "uncertainty_codes": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": sorted(_REGION_PROPOSAL_RESPONSE_KEYS),
        }

    def parse_region_proposal_response(
        self,
        value: Any,
        *,
        expected_package_id: str | None = None,
        expected_proposal_scope: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise PdfVisualTopologyError(
                "pdf_visual_topology_region_response_not_object"
            )
        if len(canonical_json_bytes(value)) > self.config.maximum_response_json_bytes:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_response_budget_exceeded"
            )
        data = copy.deepcopy(value)
        if set(data) != _REGION_PROPOSAL_RESPONSE_KEYS:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_region_response_keys_invalid"
            )
        if (
            data.get("schema_version") != PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA
            or data.get("contract_revision")
            != PDF_VISUAL_TOPOLOGY_REGION_PROPOSAL_REVISION
        ):
            raise PdfVisualTopologyError(
                "pdf_visual_topology_region_response_schema_invalid"
            )
        package_id = data.get("package_id")
        if (
            not isinstance(package_id, str)
            or not package_id
            or (
                expected_package_id is not None
                and package_id != expected_package_id
            )
        ):
            raise PdfVisualTopologyError(
                "pdf_visual_topology_response_package_mismatch"
            )
        scope = data.get("proposal_scope")
        if (
            scope not in _REGION_PROPOSAL_SCOPES
            or (
                expected_proposal_scope is not None
                and scope != expected_proposal_scope
            )
        ):
            raise PdfVisualTopologyError(
                "pdf_visual_topology_region_proposal_scope_invalid"
            )
        presence = data.get("table_presence")
        if presence not in _TABLE_PRESENCE:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_region_table_presence_invalid"
            )
        if data.get("alternatives_complete") is not True:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_region_alternative_set_incomplete"
            )
        uncertainty = _codes(data.get("uncertainty_codes"))
        raw_regions = data.get("regions")
        regions = _dicts(raw_regions)
        maximum_regions = 1 if scope == "candidate_crop" else 2
        if (
            not isinstance(raw_regions, list)
            or len(regions) != len(raw_regions)
            or len(regions) > maximum_regions
        ):
            raise PdfVisualTopologyError(
                "pdf_visual_topology_region_collection_invalid"
            )
        if presence == "present" and not regions:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_region_present_contract_invalid"
            )
        if presence == "absent" and regions:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_region_absent_contract_invalid"
            )
        if presence == "uncertain" and not uncertainty:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_region_uncertain_contract_invalid"
            )

        canonical_regions: list[dict[str, Any]] = []
        seen_region_keys: set[str] = set()
        seen_boxes: list[list[float]] = []
        for region in regions:
            if set(region) != _REGION_PROPOSAL_KEYS:
                raise PdfVisualTopologyError(
                    "pdf_visual_topology_region_keys_invalid"
                )
            region_key = region.get("region_key")
            if (
                not isinstance(region_key, str)
                or not _HYPOTHESIS_ID.fullmatch(region_key)
                or region_key in seen_region_keys
            ):
                raise PdfVisualTopologyError(
                    "pdf_visual_topology_region_identity_invalid"
                )
            bbox = _region_bbox(region.get("bbox"))
            if any(_boxes_overlap(bbox, prior) for prior in seen_boxes):
                raise PdfVisualTopologyError(
                    "pdf_visual_topology_region_overlap"
                )
            border_evidence = region.get("border_evidence")
            density = region.get("density")
            continuation = region.get("continuation_likelihood")
            if border_evidence not in _BORDER_EVIDENCE:
                raise PdfVisualTopologyError(
                    "pdf_visual_topology_region_border_evidence_invalid"
                )
            if density not in _DENSITY:
                raise PdfVisualTopologyError(
                    "pdf_visual_topology_region_density_invalid"
                )
            if continuation not in _CONTINUATION_LIKELIHOOD:
                raise PdfVisualTopologyError(
                    "pdf_visual_topology_region_continuation_invalid"
                )
            raw_hypotheses = region.get("hypotheses")
            hypotheses = _dicts(raw_hypotheses)
            if (
                not isinstance(raw_hypotheses, list)
                or len(hypotheses) != len(raw_hypotheses)
                or not hypotheses
                or len(hypotheses) > self.config.maximum_hypotheses
            ):
                raise PdfVisualTopologyError(
                    "pdf_visual_topology_hypothesis_collection_invalid"
                )
            canonical_hypotheses: list[dict[str, Any]] = []
            seen_hypotheses: set[str] = set()
            for hypothesis in hypotheses:
                canonical_hypothesis = self._parse_hypothesis(hypothesis)
                hypothesis_key = canonical_hypothesis["hypothesis_key"]
                if hypothesis_key in seen_hypotheses:
                    raise PdfVisualTopologyError(
                        "pdf_visual_topology_hypothesis_identity_duplicate"
                    )
                seen_hypotheses.add(hypothesis_key)
                canonical_hypotheses.append(canonical_hypothesis)
            seen_region_keys.add(region_key)
            seen_boxes.append(bbox)
            canonical_regions.append(
                {
                    "region_key": region_key,
                    "bbox": bbox,
                    "border_evidence": border_evidence,
                    "density": density,
                    "continuation_likelihood": continuation,
                    "hypotheses": canonical_hypotheses,
                    "uncertainty_codes": _codes(region.get("uncertainty_codes")),
                }
            )
        data["regions"] = canonical_regions
        data["uncertainty_codes"] = uncertainty
        return data

    def output_schema(self) -> dict[str, Any]:
        integer = {"type": "integer", "minimum": 1}
        span = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "start_row": integer,
                "end_row": integer,
                "start_column": integer,
                "end_column": integer,
                "relation": {
                    "type": "string",
                    "enum": [_CANONICAL_SPAN_RELATION],
                },
            },
            "required": sorted(_SPAN_KEYS),
        }
        hierarchy = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "parent_row": integer,
                "parent_column": integer,
                "child_start_column": integer,
                "child_end_column": integer,
            },
            "required": sorted(_HEADER_RELATION_KEYS),
        }
        boundary = {
            "type": "array",
            "minItems": 2,
            "items": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        }
        hypothesis = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "hypothesis_key": {"type": "string"},
                "row_boundaries": {
                    **boundary,
                    "description": (
                        "Full row-band edges: first item must be exactly 0.0, last "
                        "1.0. Evidence: whitespace gutters, repeated horizontal "
                        "alignment, atom bands, or visible separators; not one "
                        "text baseline."
                    ),
                },
                "column_boundaries": {
                    **boundary,
                    "description": (
                        "Full column edges: first item must be exactly 0.0, last 1.0. "
                        "Evidence: whitespace gutters, repeated vertical alignment, "
                        "atom bands, or visible separators."
                    ),
                },
                "header_row_count": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 8,
                    "description": (
                        "Number of logical header rows, including a visible "
                        "column-number row; wrapped lines remain in their cell row."
                    ),
                },
                "spans": {
                    "type": "array",
                    "items": span,
                    "description": (
                        "Physical spans only, always relation merged. Empty neighbors "
                        "are not spans; one-cell spans are forbidden."
                    ),
                },
                "header_hierarchy": {
                    "type": "array",
                    "items": hierarchy,
                    "description": (
                        "Header relations require a merged header span; omit "
                        "single-column identity relations."
                    ),
                },
                "continuation_required": {"type": "boolean", "enum": [False]},
                "uncertainty_codes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "For unsupported, include at least one precise snake_case "
                        "reason and return no hypotheses."
                    ),
                },
            },
            "required": sorted(_HYPOTHESIS_KEYS),
        }
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "schema_version": {
                    "type": "string",
                    "enum": [PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA],
                },
                "package_id": {"type": "string"},
                "decision": {"type": "string", "enum": sorted(_DECISIONS)},
                "alternatives_complete": {"type": "boolean"},
                "hypotheses": {"type": "array", "items": hypothesis},
                "uncertainty_codes": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": sorted(_RESPONSE_KEYS),
        }

    def parse_response(
        self,
        value: Any,
        *,
        expected_package_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise PdfVisualTopologyError("pdf_visual_topology_response_not_object")
        if len(canonical_json_bytes(value)) > self.config.maximum_response_json_bytes:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_response_budget_exceeded"
            )
        data = copy.deepcopy(value)
        if set(data) != _RESPONSE_KEYS:
            raise PdfVisualTopologyError("pdf_visual_topology_response_keys_invalid")
        if data.get("schema_version") != PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA:
            raise PdfVisualTopologyError("pdf_visual_topology_response_schema_invalid")
        package_id = data.get("package_id")
        if (
            not isinstance(package_id, str)
            or not package_id
            or (
                expected_package_id is not None
                and package_id != expected_package_id
            )
        ):
            raise PdfVisualTopologyError(
                "pdf_visual_topology_response_package_mismatch"
            )
        decision = data.get("decision")
        if decision not in _DECISIONS:
            raise PdfVisualTopologyError("pdf_visual_topology_decision_invalid")
        if not isinstance(data.get("alternatives_complete"), bool):
            raise PdfVisualTopologyError(
                "pdf_visual_topology_alternative_flag_invalid"
            )
        uncertainty = _codes(data.get("uncertainty_codes"))
        data["uncertainty_codes"] = uncertainty
        raw_hypotheses = data.get("hypotheses")
        hypotheses = _dicts(raw_hypotheses)
        if (
            not isinstance(raw_hypotheses, list)
            or len(hypotheses) != len(raw_hypotheses)
            or len(hypotheses) > self.config.maximum_hypotheses
        ):
            raise PdfVisualTopologyError(
                "pdf_visual_topology_hypothesis_collection_invalid"
            )
        if decision == "unsupported":
            if hypotheses or not uncertainty:
                raise PdfVisualTopologyError(
                    "pdf_visual_topology_unsupported_contract_invalid"
                )
            return data
        if not hypotheses or data.get("alternatives_complete") is not True:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_alternative_set_incomplete"
            )
        if decision == "bound" and uncertainty:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_bound_uncertainty_invalid"
            )

        seen: set[str] = set()
        canonical_hypotheses: list[dict[str, Any]] = []
        for hypothesis in hypotheses:
            canonical = self._parse_hypothesis(hypothesis)
            key = canonical["hypothesis_key"]
            if key in seen:
                raise PdfVisualTopologyError(
                    "pdf_visual_topology_hypothesis_identity_duplicate"
                )
            seen.add(key)
            canonical_hypotheses.append(canonical)
        if decision == "ambiguous" and len(canonical_hypotheses) < 2 and not uncertainty:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_ambiguity_contract_invalid"
            )
        data["hypotheses"] = canonical_hypotheses
        return data

    def _parse_hypothesis(self, value: dict[str, Any]) -> dict[str, Any]:
        if set(value) != _HYPOTHESIS_KEYS:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_hypothesis_keys_invalid"
            )
        key = value.get("hypothesis_key")
        if not isinstance(key, str) or not _HYPOTHESIS_ID.fullmatch(key):
            raise PdfVisualTopologyError(
                "pdf_visual_topology_hypothesis_identity_invalid"
            )
        rows = _boundaries(
            value.get("row_boundaries"),
            maximum_segments=self.config.maximum_rows,
            subject="row",
        )
        columns = _boundaries(
            value.get("column_boundaries"),
            maximum_segments=self.config.maximum_columns,
            subject="column",
        )
        row_count = len(rows) - 1
        column_count = len(columns) - 1
        header_count = value.get("header_row_count")
        if (
            not isinstance(header_count, int)
            or isinstance(header_count, bool)
            or not 0 <= header_count <= min(row_count, 8)
        ):
            raise PdfVisualTopologyError(
                "pdf_visual_topology_header_count_invalid"
            )
        if value.get("continuation_required") is not False:
            raise PdfVisualTopologyError(
                "pdf_visual_topology_continuation_unsupported"
            )
        spans = _spans(
            value.get("spans"),
            rows=row_count,
            columns=column_count,
            header_count=header_count,
        )
        hierarchy = _hierarchy(
            value.get("header_hierarchy"),
            rows=row_count,
            columns=column_count,
            header_count=header_count,
            spans=spans,
        )
        return {
            "hypothesis_key": key,
            "row_boundaries": rows,
            "column_boundaries": columns,
            "header_row_count": header_count,
            "spans": spans,
            "header_hierarchy": hierarchy,
            "continuation_required": False,
            "uncertainty_codes": _codes(value.get("uncertainty_codes")),
        }

    @staticmethod
    def _validate_region_crop_identity(crop_manifest: dict[str, Any]) -> None:
        declared = _bbox(crop_manifest.get("declared_table_bbox"))
        rendered = _bbox(crop_manifest.get("rendered_bbox"))
        page_number = crop_manifest.get("page_number")
        padding = crop_manifest.get("padding_points")
        if (
            not isinstance(crop_manifest.get("pdf_sha256"), str)
            or not crop_manifest.get("pdf_sha256")
            or not isinstance(page_number, int)
            or isinstance(page_number, bool)
            or page_number < 1
            or not crop_manifest.get("crop_id")
            or declared is None
            or rendered != declared
            or not isinstance(padding, (int, float))
            or isinstance(padding, bool)
            or not math.isfinite(float(padding))
            or float(padding) != 0.0
            or crop_manifest.get("page_rotation") != 0
            or crop_manifest.get("applied_rotation") != 0
            or crop_manifest.get("dpi") not in {150, 200}
            or not crop_manifest.get("png_sha256")
            or not crop_manifest.get("manifest_hash")
        ):
            raise PdfVisualTopologyError(
                "pdf_visual_topology_region_crop_identity_invalid"
            )

    @staticmethod
    def _region_crop_identity(
        crop_manifest: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "crop_id": crop_manifest.get("crop_id"),
            "crop_sha256": crop_manifest.get("png_sha256"),
            "manifest_hash": crop_manifest.get("manifest_hash"),
            "dpi": crop_manifest.get("dpi"),
            "width": crop_manifest.get("width"),
            "height": crop_manifest.get("height"),
            "png_bytes": crop_manifest.get("png_bytes"),
            "declared_table_bbox": copy.deepcopy(
                crop_manifest.get("declared_table_bbox")
            ),
            "rendered_bbox": copy.deepcopy(crop_manifest.get("rendered_bbox")),
            "page_rotation": crop_manifest.get("page_rotation"),
            "padding_points": crop_manifest.get("padding_points"),
        }

    @staticmethod
    def _validate_crop_identity(
        parser_observation: dict[str, Any], crop_manifest: dict[str, Any]
    ) -> None:
        table_bbox = _bbox(
            _object(parser_observation.get("coordinate_space")).get("table_bbox")
        )
        declared = _bbox(crop_manifest.get("declared_table_bbox"))
        rendered = _bbox(crop_manifest.get("rendered_bbox"))
        if (
            crop_manifest.get("pdf_sha256") != parser_observation.get("pdf_sha256")
            or crop_manifest.get("table_ref") != parser_observation.get("table_ref")
            or crop_manifest.get("page_number")
            != parser_observation.get("page_number")
            or table_bbox is None
            or declared != table_bbox
            or rendered != declared
            or float(crop_manifest.get("padding_points") or 0.0) != 0.0
            or crop_manifest.get("page_rotation") != 0
            or crop_manifest.get("applied_rotation") != 0
            or crop_manifest.get("dpi") not in {150, 200}
            or not crop_manifest.get("png_sha256")
            or not crop_manifest.get("manifest_hash")
        ):
            raise PdfVisualTopologyError(
                "pdf_visual_topology_crop_identity_invalid"
            )

    @staticmethod
    def _validate_window_crop_identity(
        *,
        parser_observation: dict[str, Any],
        window: dict[str, Any],
        crop_manifest: dict[str, Any],
    ) -> None:
        table_bbox = _bbox(
            _object(parser_observation.get("coordinate_space")).get("table_bbox")
        )
        expected = _bbox(window.get("crop_bbox"))
        declared = _bbox(crop_manifest.get("declared_table_bbox"))
        rendered = _bbox(crop_manifest.get("rendered_bbox"))
        if (
            crop_manifest.get("pdf_sha256") != parser_observation.get("pdf_sha256")
            or crop_manifest.get("table_ref") != parser_observation.get("table_ref")
            or crop_manifest.get("page_number")
            != parser_observation.get("page_number")
            or table_bbox is None
            or expected is None
            or expected[0] != table_bbox[0]
            or expected[2] != table_bbox[2]
            or declared != expected
            or rendered != expected
            or float(crop_manifest.get("padding_points") or 0.0) != 0.0
            or crop_manifest.get("page_rotation") != 0
            or crop_manifest.get("applied_rotation") != 0
            or crop_manifest.get("dpi") not in {150, 200}
            or not crop_manifest.get("png_sha256")
            or not crop_manifest.get("manifest_hash")
        ):
            raise PdfVisualTopologyError(
                "pdf_visual_topology_window_crop_identity_invalid"
            )


def _boundaries(
    value: Any,
    *,
    maximum_segments: int,
    subject: str,
) -> list[float]:
    if (
        not isinstance(value, list)
        or len(value) < 2
        or len(value) > maximum_segments + 1
        or any(
            not isinstance(item, (int, float))
            or isinstance(item, bool)
            or not math.isfinite(float(item))
            for item in value
        )
    ):
        raise PdfVisualTopologyError(
            f"pdf_visual_topology_{subject}_boundaries_invalid"
        )
    result = [round(float(item), 9) for item in value]
    if (
        result[0] != 0.0
        or result[-1] != 1.0
        or any(left >= right for left, right in zip(result, result[1:]))
    ):
        raise PdfVisualTopologyError(
            f"pdf_visual_topology_{subject}_boundaries_invalid"
        )
    return result


def _spans(
    value: Any,
    *,
    rows: int,
    columns: int,
    header_count: int,
) -> list[dict[str, Any]]:
    raw = value
    spans = _dicts(raw)
    if not isinstance(raw, list) or len(spans) != len(raw):
        raise PdfVisualTopologyError("pdf_visual_topology_spans_invalid")
    occupied: set[tuple[int, int]] = set()
    result: list[dict[str, Any]] = []
    for item in spans:
        relation = item.get("relation")
        if (
            set(item) != _SPAN_KEYS
            or relation not in _ACCEPTED_SPAN_RELATIONS
        ):
            raise PdfVisualTopologyError("pdf_visual_topology_span_invalid")
        values = [
            item.get("start_row"),
            item.get("end_row"),
            item.get("start_column"),
            item.get("end_column"),
        ]
        if any(
            not isinstance(current, int) or isinstance(current, bool)
            for current in values
        ):
            raise PdfVisualTopologyError("pdf_visual_topology_span_invalid")
        start_row, end_row, start_column, end_column = values
        if (
            not 1 <= start_row <= end_row <= rows
            or not 1 <= start_column <= end_column <= columns
            or (start_row == end_row and start_column == end_column)
            or (
                relation == "spanning_header"
                and start_row > header_count
            )
        ):
            raise PdfVisualTopologyError("pdf_visual_topology_span_invalid")
        positions = {
            (row, column)
            for row in range(start_row, end_row + 1)
            for column in range(start_column, end_column + 1)
        }
        if positions & occupied:
            raise PdfVisualTopologyError("pdf_visual_topology_span_overlap")
        occupied.update(positions)
        result.append(
            {
                "start_row": start_row,
                "end_row": end_row,
                "start_column": start_column,
                "end_column": end_column,
                "relation": _CANONICAL_SPAN_RELATION,
            }
        )
    return sorted(
        result,
        key=lambda item: (
            item["start_row"],
            item["start_column"],
            item["end_row"],
            item["end_column"],
            item["relation"],
        ),
    )


def _hierarchy(
    value: Any,
    *,
    rows: int,
    columns: int,
    header_count: int,
    spans: list[dict[str, Any]],
) -> list[dict[str, int]]:
    raw = value
    relations = _dicts(raw)
    if not isinstance(raw, list) or len(relations) != len(raw):
        raise PdfVisualTopologyError(
            "pdf_visual_topology_header_hierarchy_invalid"
        )
    result: list[dict[str, int]] = []
    for item in relations:
        values = [
            item.get("parent_row"),
            item.get("parent_column"),
            item.get("child_start_column"),
            item.get("child_end_column"),
        ]
        if (
            set(item) != _HEADER_RELATION_KEYS
            or any(
                not isinstance(current, int) or isinstance(current, bool)
                for current in values
            )
        ):
            raise PdfVisualTopologyError(
                "pdf_visual_topology_header_hierarchy_invalid"
            )
        parent_row, parent_column, child_start, child_end = values
        identity_relation = (
            child_start == child_end == parent_column
        )
        if (
            not 1 <= parent_row <= min(rows, header_count)
            or not 1 <= parent_column <= columns
            or not 1 <= child_start <= child_end <= columns
            or (
                not identity_relation
                and not any(
                    span["start_row"] == parent_row
                    and span["start_column"] == parent_column
                    and span["end_column"] >= child_end
                    for span in spans
                )
            )
        ):
            raise PdfVisualTopologyError(
                "pdf_visual_topology_header_hierarchy_invalid"
            )
        result.append(
            {
                "parent_row": parent_row,
                "parent_column": parent_column,
                "child_start_column": child_start,
                "child_end_column": child_end,
            }
        )
    return sorted(
        result,
        key=lambda item: (
            item["parent_row"],
            item["parent_column"],
            item["child_start_column"],
            item["child_end_column"],
        ),
    )


def _codes(value: Any) -> list[str]:
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not _CODE.fullmatch(item) for item in value)
        or value != sorted(set(value))
    ):
        raise PdfVisualTopologyError(
            "pdf_visual_topology_uncertainty_codes_invalid"
        )
    return list(value)


def _normalized_bbox(value: list[float], scope: list[float]) -> list[float]:
    width = scope[2] - scope[0]
    height = scope[3] - scope[1]
    if width <= 0 or height <= 0:
        raise PdfVisualTopologyError("pdf_visual_topology_table_bbox_invalid")
    result = [
        (value[0] - scope[0]) / width,
        (value[1] - scope[1]) / height,
        (value[2] - scope[0]) / width,
        (value[3] - scope[1]) / height,
    ]
    if not _normalized_box(result):
        raise PdfVisualTopologyError("pdf_visual_topology_atom_bbox_invalid")
    return [round(item, 9) for item in result]


def _normalized_box(value: Any) -> bool:
    return bool(
        isinstance(value, list)
        and len(value) == 4
        and all(
            isinstance(item, (int, float))
            and not isinstance(item, bool)
            and math.isfinite(float(item))
            for item in value
        )
        and 0.0 <= float(value[0]) < float(value[2]) <= 1.0
        and 0.0 <= float(value[1]) < float(value[3]) <= 1.0
    )


def _region_bbox(value: Any) -> list[float]:
    if not _normalized_box(value):
        raise PdfVisualTopologyError("pdf_visual_topology_region_bbox_invalid")
    result = [round(float(item), 9) for item in value]
    if not _normalized_box(result):
        raise PdfVisualTopologyError("pdf_visual_topology_region_bbox_invalid")
    return result


def _boxes_overlap(left: list[float], right: list[float]) -> bool:
    return bool(
        min(left[2], right[2]) > max(left[0], right[0])
        and min(left[3], right[3]) > max(left[1], right[1])
    )


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
