from __future__ import annotations

import copy
import math
import re
from dataclasses import asdict, dataclass
from typing import Any

from .contracts import stable_digest
from .pdf_dual_oracle_contracts import (
    PdfDualOracleContractFactory,
    PdfDualOracleContractRuntime,
)
from .pdf_hybrid_contracts import sha256_json
from .pdf_hybrid_materialization import (
    PdfHybridMaterializationFactory,
    PdfHybridMaterializationRuntime,
)
from .pdf_parser_geometry import (
    PdfParserGeometryFactory,
    PdfParserGeometryRuntime,
)
from .pdf_topology_assembly import (
    PDF_TOPOLOGY_SAFE_BOUNDARY_RECONCILIATION_OPERATIONS,
    PdfTopologyAssemblyFactory,
    PdfTopologyAssemblyRuntime,
)
from .pdf_visual_topology import (
    PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
    PdfVisualTopologyFactory,
    PdfVisualTopologyRuntime,
)


PDF_VLM_REGION_BINDING_RESULT_SCHEMA = (
    "broker_reports_pdf_vlm_region_binding_result_v2"
)
PDF_VLM_REGION_RECONCILIATION_PLAN_SCHEMA = (
    "broker_reports_pdf_vlm_region_reconciliation_plan_v2"
)
PDF_VLM_REGION_BINDING_POLICY_VERSION = "pdf_vlm_region_binding_policy_v2"
PDF_VLM_CANDIDATE_PARENT_SCOPE_EVIDENCE_SCHEMA = (
    "broker_reports_pdf_vlm_candidate_parent_scope_evidence_v1"
)

FACTORY_REQUIRED = (
    "PdfVlmRegionBindingFactory.create is the only deterministic VLM-region "
    "reselection, binding, and materialization entrypoint"
)
FORBIDDEN = (
    "Region binding must not call a provider, pad or guess crop bounds, split "
    "crossing atoms, choose among alternatives, invent values, or bypass the "
    "existing parser, geometry, assembly, and materialization factories"
)

_FACTORY_TOKEN = object()
_CODE = re.compile(r"^[a-z][a-z0-9_]{2,127}$")
_RESULT_KEYS = {
    "schema_version",
    "policy_version",
    "policy_configuration_hash",
    "binding_run_id",
    "proposal_package_id",
    "proposal_package_hash",
    "proposal_checksum",
    "proposal_scope",
    "document_ref",
    "pdf_sha256",
    "page_ref",
    "page_number",
    "parent_source_bbox",
    "parent_atom_accounting",
    "projection_checksum",
    "reconciliation_plan_hash",
    "table_presence",
    "alternatives_complete",
    "region_results",
    "source_accounting",
    "runtime_terminal_status",
    "reason_codes",
    "authority_state",
    "production_authority",
    "production_gate2_selection_changed",
    "provider_calls_performed",
    "value_mutation_performed",
    "model_invented_values_total",
    "result_checksum",
}
_REGION_KEYS = {
    "region_key",
    "table_ref",
    "normalized_bbox",
    "original_source_bbox",
    "source_bbox",
    "bbox_reconciliation",
    "crop_manifest_hash",
    "crop_sha256",
    "included_word_refs",
    "excluded_word_refs",
    "crossing_word_refs",
    "candidate_accounting",
    "parser_observation",
    "parser_geometry_observation",
    "visual_package",
    "topology_response",
    "assembly",
    "accepted_binding",
    "materialization",
    "runtime_terminal_status",
    "reason_codes",
}
_PARENT_ATOM_ACCOUNTING_KEYS = {
    "page_atoms_total",
    "all_parent_atoms",
    "parent_boundary_crossing_atoms",
    "outside_parent_atoms",
    "parent_boundary_crossing_word_refs",
    "parent_boundary_preserved",
    "candidate_parent_scope_evidence",
}
_CANDIDATE_PARENT_SCOPE_EVIDENCE_KEYS = {
    "schema_version",
    "candidate_table_ref",
    "original_source_bbox",
    "reconciled_source_bbox",
    "completion_applied",
    "adjustments",
    "owned_word_refs",
    "owned_word_refs_total",
    "uncontained_owned_word_refs",
    "all_owned_atoms_contained",
    "unowned_contained_word_refs",
    "adjacent_unowned_atom_evidence",
    "adjacent_unowned_word_refs",
    "candidate_parent_scope_complete",
    "evidence_checksum",
}
_CANDIDATE_PARENT_ADJUSTMENT_KEYS = {
    "edge",
    "from_coordinate",
    "to_coordinate",
    "adjustment_code",
    "word_refs",
    "forcing_atom_bboxes",
    "maximum_adjacent_gap_points",
}
_ADJACENT_UNOWNED_ATOM_KEYS = {
    "edge",
    "word_ref",
    "source_bbox",
    "gap_points",
    "maximum_gap_points",
    "orthogonal_overlap_points",
}
_BBOX_RECONCILIATION_KEYS = {
    "original_source_bbox",
    "reconciled_source_bbox",
    "adjustments",
    "included_word_refs_before",
    "excluded_word_refs_before",
    "crossing_word_refs_before",
    "included_word_refs_after",
    "excluded_word_refs_after",
    "crossing_word_refs_after",
    "included_atoms",
    "excluded_atoms",
    "crossing_atoms",
    "all_parent_atoms",
    "every_parent_atom_accounted",
}
_BBOX_ADJUSTMENT_KEYS = {
    "iteration",
    "edge",
    "from_coordinate",
    "to_coordinate",
    "reason_code",
    "word_refs",
}
_RECONCILIATION_PLAN_KEYS = {
    "schema_version",
    "policy_version",
    "proposal_package_id",
    "proposal_package_hash",
    "proposal_checksum",
    "projection_checksum",
    "proposal_scope",
    "document_ref",
    "pdf_sha256",
    "page_ref",
    "page_number",
    "parent_source_bbox",
    "parent_atom_accounting",
    "regions",
    "plan_checksum",
}
_RECONCILIATION_PLAN_REGION_KEYS = {
    "region_key",
    "normalized_bbox",
    "original_source_bbox",
    "reconciled_source_bbox",
    "bbox_reconciliation",
}
_CANDIDATE_ACCOUNTING_KEYS = {
    "scope_candidates_total",
    "included_candidate_ids",
    "excluded_candidate_ids",
    "crossing_candidate_ids",
    "every_scope_candidate_accounted",
}
_SOURCE_ACCOUNTING_KEYS = {
    "parent_word_refs_total",
    "unique_region_word_refs_included",
    "region_word_refs_crossing",
    "candidate_scope_total",
    "candidate_scope_accounted",
    "regions_proposed",
    "regions_accepted",
}
_TERMINALS = {
    "no_table_proposed",
    "proposal_ambiguous",
    "validation_blocked",
    "partially_validated",
    "accepted_physical_structure",
}
_REGION_TERMINALS = {
    "proposal_ambiguous",
    "validation_blocked",
    "accepted_physical_structure",
}


class PdfVlmRegionBindingError(ValueError):
    def __init__(self, code: str, subject: str = "") -> None:
        self.code = code
        self.subject = subject
        super().__init__(code if not subject else f"{code}:{subject}")


@dataclass(frozen=True)
class PdfVlmRegionBindingConfig:
    policy_version: str = PDF_VLM_REGION_BINDING_POLICY_VERSION
    source_coordinate_precision: int = 6


class PdfVlmRegionBindingFactory:
    def __init__(
        self,
        config: PdfVlmRegionBindingConfig | None = None,
        *,
        contracts: PdfDualOracleContractRuntime | None = None,
        parser_geometry: PdfParserGeometryRuntime | None = None,
        visual_topology: PdfVisualTopologyRuntime | None = None,
        topology_assembly: PdfTopologyAssemblyRuntime | None = None,
        materializer: PdfHybridMaterializationRuntime | None = None,
    ) -> None:
        self.config = config or PdfVlmRegionBindingConfig()
        self.contracts = contracts
        self.parser_geometry = parser_geometry
        self.visual_topology = visual_topology
        self.topology_assembly = topology_assembly
        self.materializer = materializer

    def create(self) -> "PdfVlmRegionBindingRuntime":
        if (
            self.config.policy_version != PDF_VLM_REGION_BINDING_POLICY_VERSION
            or not 0 <= self.config.source_coordinate_precision <= 12
        ):
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_config_invalid"
            )
        visual = self.visual_topology or PdfVisualTopologyFactory().create()
        geometry = self.parser_geometry or PdfParserGeometryFactory().create()
        return PdfVlmRegionBindingRuntime(
            self.config,
            contracts=self.contracts or PdfDualOracleContractFactory().create(),
            parser_geometry=geometry,
            visual_topology=visual,
            topology_assembly=self.topology_assembly
            or PdfTopologyAssemblyFactory(
                visual_topology=visual,
                parser_geometry=geometry,
            ).create(),
            materializer=self.materializer
            or PdfHybridMaterializationFactory().create(),
            _factory_token=_FACTORY_TOKEN,
        )


class PdfVlmRegionBindingRuntime:
    def __init__(
        self,
        config: PdfVlmRegionBindingConfig,
        *,
        contracts: PdfDualOracleContractRuntime,
        parser_geometry: PdfParserGeometryRuntime,
        visual_topology: PdfVisualTopologyRuntime,
        topology_assembly: PdfTopologyAssemblyRuntime,
        materializer: PdfHybridMaterializationRuntime,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_factory_required"
            )
        self.config = config
        self.contracts = contracts
        self.parser_geometry = parser_geometry
        self.visual = visual_topology
        self.assembler = topology_assembly
        self.materializer = materializer

    def reconcile_candidate_parent_scope(
        self,
        *,
        candidate_evidence: dict[str, Any],
        pdf_text_layer_projection: dict[str, Any],
        expected_page_ref: str,
        page_source_bbox: list[float],
    ) -> dict[str, Any]:
        """Complete only source-owned atoms and record adjacent uncertainty."""

        evidence = _candidate_parent_scope_evidence(
            candidate=candidate_evidence,
            projection=pdf_text_layer_projection,
            expected_page_ref=expected_page_ref,
            page_bbox=page_source_bbox,
        )
        if _candidate_parent_scope_evidence_invalid(evidence):
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_candidate_parent_scope_evidence_invalid"
            )
        return evidence

    def assert_parent_atom_geometry(
        self,
        *,
        proposal_package: dict[str, Any],
        pdf_text_layer_projection: dict[str, Any],
        parent_source_bbox: list[float],
    ) -> None:
        """Fail before provider execution when a parent splits source atoms."""

        package_errors = self.visual.validate_region_proposal_package(
            proposal_package
        )
        if package_errors:
            raise PdfVlmRegionBindingError(package_errors[0])
        parent_bbox = _bbox(parent_source_bbox)
        package_parent_bbox = _bbox(
            _object(proposal_package.get("crop_identity")).get(
                "declared_table_bbox"
            )
        )
        if (
            parent_bbox is None
            or parent_bbox[0] == parent_bbox[2]
            or parent_bbox[1] == parent_bbox[3]
            or package_parent_bbox != parent_bbox
        ):
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_parent_bbox_mismatch"
            )
        _, _, parent_crossing, parent_outside = _page_words(
            projection=pdf_text_layer_projection,
            expected_page_ref=str(proposal_package.get("page_ref") or ""),
            parent_bbox=parent_bbox,
            effective_word_bboxes=_effective_candidate_word_bboxes(
                proposal_package
            ),
        )
        if parent_crossing:
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_parent_atom_crossing"
            )
        if (
            proposal_package.get("proposal_scope") == "page_level"
            and parent_outside
        ):
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_parent_atom_outside_scope"
            )

    def _candidate_parent_scope_for_package(
        self,
        *,
        proposal_package: dict[str, Any],
        pdf_text_layer_projection: dict[str, Any],
        parent_bbox: list[float],
        page_ref: str,
    ) -> dict[str, Any] | None:
        if proposal_package.get("proposal_scope") != "candidate_crop":
            return None
        table_ref = str(proposal_package.get("table_ref") or "")
        page_candidates = [
            item
            for item in _dicts(
                pdf_text_layer_projection.get("table_candidate_inventory")
            )
            if item.get("page_ref") == page_ref
        ]
        if not page_candidates:
            return None
        candidates = [
            item
            for item in page_candidates
            if item.get("table_candidate_ref") == table_ref
        ]
        page_bbox = _projection_page_bbox(
            projection=pdf_text_layer_projection,
            expected_page_ref=page_ref,
        )
        if len(candidates) != 1 or page_bbox is None:
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_candidate_parent_scope_evidence_invalid"
            )
        if "contributing_word_refs" not in candidates[0]:
            return None
        evidence = self.reconcile_candidate_parent_scope(
            candidate_evidence=candidates[0],
            pdf_text_layer_projection=pdf_text_layer_projection,
            expected_page_ref=page_ref,
            page_source_bbox=page_bbox,
        )
        if evidence.get("reconciled_source_bbox") != parent_bbox:
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_candidate_parent_scope_mismatch"
            )
        return evidence

    def reconcile_proposal_regions(
        self,
        *,
        proposal_package: dict[str, Any],
        proposal: dict[str, Any],
        pdf_text_layer_projection: dict[str, Any],
        parent_source_bbox: list[float],
    ) -> dict[str, Any]:
        """Return the deterministic atom-complete crop plan for a proposal.

        The plan is deliberately provider-free and contains no crop bytes.  A
        caller must render each ``reconciled_source_bbox`` through the existing
        raster factory and then pass those exact crop manifests to ``bind``.
        ``bind`` independently rebuilds the plan, so a caller cannot substitute
        a wider or otherwise unanchored crop.
        """

        package_errors = self.visual.validate_region_proposal_package(
            proposal_package
        )
        if package_errors:
            raise PdfVlmRegionBindingError(package_errors[0])
        scope = str(proposal_package.get("proposal_scope") or "")
        try:
            parsed = self.visual.parse_region_proposal_response(
                proposal,
                expected_package_id=str(
                    proposal_package.get("package_id") or ""
                ),
                expected_proposal_scope=scope,
            )
        except ValueError as exc:
            raise PdfVlmRegionBindingError(
                _error_code(exc, "pdf_vlm_region_binding_proposal_invalid")
            ) from exc
        if parsed != proposal:
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_proposal_not_canonical"
            )

        parent_bbox = _bbox(parent_source_bbox)
        package_parent_bbox = _bbox(
            _object(proposal_package.get("crop_identity")).get(
                "declared_table_bbox"
            )
        )
        if (
            parent_bbox is None
            or parent_bbox[0] == parent_bbox[2]
            or parent_bbox[1] == parent_bbox[3]
            or package_parent_bbox != parent_bbox
        ):
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_parent_bbox_mismatch"
            )

        words, inferred_page_ref, parent_crossing, parent_outside = _page_words(
            projection=pdf_text_layer_projection,
            expected_page_ref=str(proposal_package.get("page_ref") or ""),
            parent_bbox=parent_bbox,
            effective_word_bboxes=_effective_candidate_word_bboxes(
                proposal_package
            ),
        )
        page_ref = str(proposal_package.get("page_ref") or inferred_page_ref)
        document_ref = str(proposal_package.get("document_ref") or "")
        pdf_sha256 = str(proposal_package.get("pdf_sha256") or "")
        page_number = proposal_package.get("page_number")
        if (
            not document_ref
            or not pdf_sha256
            or not page_ref
            or not isinstance(page_number, int)
            or isinstance(page_number, bool)
            or page_number < 1
        ):
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_scope_identity_invalid"
            )
        if parent_crossing:
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_parent_atom_crossing"
            )
        if scope == "page_level" and parent_outside:
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_parent_atom_outside_scope"
            )
        self._candidate_scope(
            proposal_package=proposal_package,
            words=words,
        )

        return self._build_reconciliation_plan(
            proposal_package=proposal_package,
            proposal=parsed,
            pdf_text_layer_projection=pdf_text_layer_projection,
            parent_bbox=parent_bbox,
            words=words,
            parent_crossing=parent_crossing,
            parent_outside=parent_outside,
            document_ref=document_ref,
            pdf_sha256=pdf_sha256,
            page_ref=page_ref,
            page_number=page_number,
        )

    def _build_reconciliation_plan(
        self,
        *,
        proposal_package: dict[str, Any],
        proposal: dict[str, Any],
        pdf_text_layer_projection: dict[str, Any],
        parent_bbox: list[float],
        words: dict[str, dict[str, Any]],
        parent_crossing: list[str],
        parent_outside: list[str],
        document_ref: str,
        pdf_sha256: str,
        page_ref: str,
        page_number: int,
    ) -> dict[str, Any]:
        regions: list[dict[str, Any]] = []
        reconciled_boxes: list[list[float]] = []
        for region in _dicts(proposal.get("regions")):
            original_bbox = _source_bbox(
                normalized_bbox=region.get("bbox"),
                parent_bbox=parent_bbox,
                precision=self.config.source_coordinate_precision,
            )
            evidence = _reconcile_source_bbox(
                words=words,
                original_bbox=original_bbox,
                parent_bbox=parent_bbox,
                precision=self.config.source_coordinate_precision,
            )
            reconciled_bbox = evidence["reconciled_source_bbox"]
            if any(
                _boxes_overlap(reconciled_bbox, prior)
                for prior in reconciled_boxes
            ):
                raise PdfVlmRegionBindingError(
                    "pdf_vlm_region_binding_reconciled_region_overlap"
                )
            reconciled_boxes.append(reconciled_bbox)
            regions.append(
                {
                    "region_key": str(region.get("region_key") or ""),
                    "normalized_bbox": copy.deepcopy(region.get("bbox")),
                    "original_source_bbox": original_bbox,
                    "reconciled_source_bbox": reconciled_bbox,
                    "bbox_reconciliation": evidence,
                }
            )

        candidate_parent_scope_evidence = (
            self._candidate_parent_scope_for_package(
                proposal_package=proposal_package,
                pdf_text_layer_projection=pdf_text_layer_projection,
                parent_bbox=parent_bbox,
                page_ref=page_ref,
            )
        )
        parent_accounting = {
            "page_atoms_total": (
                len(words) + len(parent_crossing) + len(parent_outside)
            ),
            "all_parent_atoms": len(words),
            "parent_boundary_crossing_atoms": len(parent_crossing),
            "outside_parent_atoms": len(parent_outside),
            "parent_boundary_crossing_word_refs": sorted(parent_crossing),
            "parent_boundary_preserved": True,
            "candidate_parent_scope_evidence": copy.deepcopy(
                candidate_parent_scope_evidence
            ),
        }
        result = {
            "schema_version": PDF_VLM_REGION_RECONCILIATION_PLAN_SCHEMA,
            "policy_version": self.config.policy_version,
            "proposal_package_id": proposal_package.get("package_id"),
            "proposal_package_hash": proposal_package.get("package_hash"),
            "proposal_checksum": sha256_json(proposal),
            "projection_checksum": sha256_json(pdf_text_layer_projection),
            "proposal_scope": proposal_package.get("proposal_scope"),
            "document_ref": document_ref,
            "pdf_sha256": pdf_sha256,
            "page_ref": page_ref,
            "page_number": page_number,
            "parent_source_bbox": copy.deepcopy(parent_bbox),
            "parent_atom_accounting": parent_accounting,
            "regions": regions,
        }
        result["plan_checksum"] = sha256_json(result)
        errors = self.validate_reconciliation_plan(result)
        if errors:
            raise PdfVlmRegionBindingError(errors[0])
        return result

    def validate_reconciliation_plan(self, value: Any) -> list[str]:
        data = _object(value)
        errors: list[str] = []
        if set(data) != _RECONCILIATION_PLAN_KEYS:
            return ["pdf_vlm_region_binding_reconciliation_plan_keys_invalid"]
        if (
            data.get("schema_version")
            != PDF_VLM_REGION_RECONCILIATION_PLAN_SCHEMA
            or data.get("policy_version") != self.config.policy_version
            or data.get("proposal_scope")
            not in {"candidate_crop", "page_level"}
            or _bbox(data.get("parent_source_bbox")) is None
        ):
            errors.append(
                "pdf_vlm_region_binding_reconciliation_plan_contract_invalid"
            )
        if not all(
            isinstance(data.get(key), str) and bool(data.get(key))
            for key in (
                "proposal_package_id",
                "proposal_package_hash",
                "proposal_checksum",
                "projection_checksum",
                "document_ref",
                "pdf_sha256",
                "page_ref",
            )
        ) or not _positive_int(data.get("page_number")):
            errors.append(
                "pdf_vlm_region_binding_reconciliation_plan_identity_invalid"
            )
        if _parent_atom_accounting_invalid(
            _object(data.get("parent_atom_accounting"))
        ):
            errors.append(
                "pdf_vlm_region_binding_parent_atom_accounting_invalid"
            )
        regions = _dicts(data.get("regions"))
        if (
            not isinstance(data.get("regions"), list)
            or len(regions) != len(data.get("regions") or [])
            or len(regions)
            > (1 if data.get("proposal_scope") == "candidate_crop" else 2)
        ):
            errors.append(
                "pdf_vlm_region_binding_reconciliation_regions_invalid"
            )
        region_keys: set[str] = set()
        reconciled_boxes: list[list[float]] = []
        for region in regions:
            if set(region) != _RECONCILIATION_PLAN_REGION_KEYS:
                errors.append(
                    "pdf_vlm_region_binding_reconciliation_region_keys_invalid"
                )
                continue
            region_key = str(region.get("region_key") or "")
            original_bbox = _bbox(region.get("original_source_bbox"))
            reconciled_bbox = _bbox(region.get("reconciled_source_bbox"))
            if (
                not region_key
                or region_key in region_keys
                or _bbox(region.get("normalized_bbox"), normalized=True)
                is None
                or original_bbox is None
                or reconciled_bbox is None
                or any(
                    _boxes_overlap(reconciled_bbox, prior)
                    for prior in reconciled_boxes
                )
            ):
                errors.append(
                    "pdf_vlm_region_binding_reconciliation_region_invalid"
                )
            region_keys.add(region_key)
            if reconciled_bbox is not None:
                reconciled_boxes.append(reconciled_bbox)
            errors.extend(
                _bbox_reconciliation_errors(
                    _object(region.get("bbox_reconciliation")),
                    expected_original_bbox=original_bbox,
                    expected_reconciled_bbox=reconciled_bbox,
                )
            )
        unsigned = dict(data)
        stored = unsigned.pop("plan_checksum", None)
        if stored != sha256_json(unsigned):
            errors.append(
                "pdf_vlm_region_binding_reconciliation_plan_checksum_invalid"
            )
        return sorted(set(errors))

    def bind(
        self,
        *,
        proposal_package: dict[str, Any],
        proposal: dict[str, Any],
        pdf_text_layer_projection: dict[str, Any],
        parent_source_bbox: list[float],
        region_crop_manifests: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Reselect exact source atoms and prove or block proposed regions.

        This method is deliberately provider-free.  It consumes one already
        parsed proposal and feeds its topology into the existing deterministic
        parser/geometry/assembly/materialization chain.
        """

        package_errors = self.visual.validate_region_proposal_package(
            proposal_package
        )
        if package_errors:
            raise PdfVlmRegionBindingError(package_errors[0])
        scope = str(proposal_package.get("proposal_scope") or "")
        try:
            parsed = self.visual.parse_region_proposal_response(
                proposal,
                expected_package_id=str(
                    proposal_package.get("package_id") or ""
                ),
                expected_proposal_scope=scope,
            )
        except ValueError as exc:
            raise PdfVlmRegionBindingError(
                _error_code(exc, "pdf_vlm_region_binding_proposal_invalid")
            ) from exc
        if parsed != proposal:
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_proposal_not_canonical"
            )

        parent_bbox = _bbox(parent_source_bbox)
        package_parent_bbox = _bbox(
            _object(proposal_package.get("crop_identity")).get(
                "declared_table_bbox"
            )
        )
        if (
            parent_bbox is None
            or parent_bbox[0] == parent_bbox[2]
            or parent_bbox[1] == parent_bbox[3]
            or package_parent_bbox != parent_bbox
        ):
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_parent_bbox_mismatch"
            )

        document_ref = str(proposal_package.get("document_ref") or "")
        pdf_sha256 = str(proposal_package.get("pdf_sha256") or "")
        page_number = proposal_package.get("page_number")
        words, inferred_page_ref, parent_crossing, parent_outside = _page_words(
            projection=pdf_text_layer_projection,
            expected_page_ref=str(proposal_package.get("page_ref") or ""),
            parent_bbox=parent_bbox,
            effective_word_bboxes=_effective_candidate_word_bboxes(
                proposal_package
            ),
        )
        page_ref = str(proposal_package.get("page_ref") or inferred_page_ref)
        if (
            not document_ref
            or not pdf_sha256
            or not page_ref
            or not isinstance(page_number, int)
            or isinstance(page_number, bool)
            or page_number < 1
        ):
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_scope_identity_invalid"
            )
        projection_checksum = sha256_json(pdf_text_layer_projection)
        proposal_checksum = sha256_json(parsed)

        regions = _dicts(parsed.get("regions"))
        expected_region_keys = {str(item.get("region_key") or "") for item in regions}
        if set(region_crop_manifests) != expected_region_keys:
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_crop_set_mismatch"
            )
        if parent_crossing:
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_parent_atom_crossing"
            )
        if scope == "page_level" and parent_outside:
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_parent_atom_outside_scope"
            )

        reconciliation_plan = self._build_reconciliation_plan(
            proposal_package=proposal_package,
            proposal=parsed,
            pdf_text_layer_projection=pdf_text_layer_projection,
            parent_bbox=parent_bbox,
            words=words,
            parent_crossing=parent_crossing,
            parent_outside=parent_outside,
            document_ref=document_ref,
            pdf_sha256=pdf_sha256,
            page_ref=page_ref,
            page_number=page_number,
        )
        planned_regions = {
            str(item.get("region_key") or ""): item
            for item in _dicts(reconciliation_plan.get("regions"))
        }

        candidate_scope = self._candidate_scope(
            proposal_package=proposal_package,
            words=words,
        )
        candidate_parent_scope_evidence = _object(
            _object(reconciliation_plan.get("parent_atom_accounting")).get(
                "candidate_parent_scope_evidence"
            )
        )
        region_results: list[dict[str, Any]] = []
        table_refs: set[str] = set()
        for region in regions:
            region_key = str(region.get("region_key") or "")
            planned_region = _object(planned_regions.get(region_key))
            original_source_bbox = _bbox(
                planned_region.get("original_source_bbox")
            )
            source_bbox = _bbox(planned_region.get("reconciled_source_bbox"))
            if original_source_bbox is None or source_bbox is None:
                raise PdfVlmRegionBindingError(
                    "pdf_vlm_region_binding_reconciliation_plan_invalid"
                )
            result = self._bind_region(
                proposal_package=proposal_package,
                proposal=parsed,
                region=region,
                original_source_bbox=original_source_bbox,
                source_bbox=source_bbox,
                bbox_reconciliation=_object(
                    planned_region.get("bbox_reconciliation")
                ),
                crop_manifest=region_crop_manifests[region_key],
                pdf_text_layer_projection=pdf_text_layer_projection,
                words=words,
                candidate_scope=candidate_scope,
                candidate_parent_scope_evidence=(
                    candidate_parent_scope_evidence
                ),
                document_ref=document_ref,
                pdf_sha256=pdf_sha256,
                page_ref=page_ref,
                page_number=page_number,
                proposal_checksum=proposal_checksum,
            )
            if result["table_ref"] in table_refs:
                raise PdfVlmRegionBindingError(
                    "pdf_vlm_region_binding_table_ref_duplicate"
                )
            table_refs.add(result["table_ref"])
            region_results.append(result)

        terminal, top_reasons = _top_terminal(
            table_presence=str(parsed.get("table_presence") or ""),
            proposal_uncertainty=[
                str(item) for item in parsed.get("uncertainty_codes") or []
            ],
            region_results=region_results,
        )
        included_word_refs = {
            str(ref)
            for item in region_results
            for ref in item.get("included_word_refs") or []
        }
        crossing_word_refs = {
            str(ref)
            for item in region_results
            for ref in item.get("crossing_word_refs") or []
        }
        candidate_total = len(candidate_scope)
        candidate_accounted = sum(
            1
            for candidate_id in candidate_scope
            if any(
                candidate_id
                in {
                    *item["candidate_accounting"]["included_candidate_ids"],
                    *item["candidate_accounting"]["excluded_candidate_ids"],
                    *item["candidate_accounting"]["crossing_candidate_ids"],
                }
                for item in region_results
            )
        )
        accounting = {
            "parent_word_refs_total": len(words),
            "unique_region_word_refs_included": len(included_word_refs),
            "region_word_refs_crossing": len(crossing_word_refs),
            "candidate_scope_total": candidate_total,
            "candidate_scope_accounted": candidate_accounted,
            "regions_proposed": len(regions),
            "regions_accepted": sum(
                item.get("runtime_terminal_status")
                == "accepted_physical_structure"
                for item in region_results
            ),
        }
        result = {
            "schema_version": PDF_VLM_REGION_BINDING_RESULT_SCHEMA,
            "policy_version": self.config.policy_version,
            "policy_configuration_hash": sha256_json(asdict(self.config)),
            "binding_run_id": "pdfvlmregionbinding_"
            + stable_digest(
                [
                    proposal_package.get("package_hash"),
                    proposal_checksum,
                    projection_checksum,
                    reconciliation_plan.get("plan_checksum"),
                    [item.get("crop_manifest_hash") for item in region_results],
                    self.config.policy_version,
                ],
                length=24,
            ),
            "proposal_package_id": proposal_package.get("package_id"),
            "proposal_package_hash": proposal_package.get("package_hash"),
            "proposal_checksum": proposal_checksum,
            "proposal_scope": scope,
            "document_ref": document_ref,
            "pdf_sha256": pdf_sha256,
            "page_ref": page_ref,
            "page_number": page_number,
            "parent_source_bbox": parent_bbox,
            "parent_atom_accounting": copy.deepcopy(
                reconciliation_plan["parent_atom_accounting"]
            ),
            "projection_checksum": projection_checksum,
            "reconciliation_plan_hash": reconciliation_plan.get(
                "plan_checksum"
            ),
            "table_presence": parsed.get("table_presence"),
            "alternatives_complete": parsed.get("alternatives_complete") is True,
            "region_results": region_results,
            "source_accounting": accounting,
            "runtime_terminal_status": terminal,
            "reason_codes": top_reasons,
            "authority_state": "shadow_non_authoritative",
            "production_authority": False,
            "production_gate2_selection_changed": False,
            "provider_calls_performed": 0,
            "value_mutation_performed": False,
            "model_invented_values_total": 0,
        }
        result["result_checksum"] = sha256_json(result)
        errors = self.validate_result_against_inputs(
            result,
            proposal_package=proposal_package,
            proposal=parsed,
            pdf_text_layer_projection=pdf_text_layer_projection,
            parent_source_bbox=parent_bbox,
            region_crop_manifests=region_crop_manifests,
        )
        if errors:
            raise PdfVlmRegionBindingError(errors[0])
        return result

    def validate_result(self, value: Any) -> list[str]:
        data = _object(value)
        errors: list[str] = []
        if set(data) != _RESULT_KEYS:
            return ["pdf_vlm_region_binding_result_keys_invalid"]
        if (
            data.get("schema_version") != PDF_VLM_REGION_BINDING_RESULT_SCHEMA
            or data.get("policy_version") != self.config.policy_version
            or data.get("policy_configuration_hash")
            != sha256_json(asdict(self.config))
            or data.get("proposal_scope") not in {"candidate_crop", "page_level"}
            or data.get("runtime_terminal_status") not in _TERMINALS
        ):
            errors.append("pdf_vlm_region_binding_result_contract_invalid")
        parent_bbox = _bbox(data.get("parent_source_bbox"))
        if (
            not all(
                isinstance(data.get(key), str) and bool(data.get(key))
                for key in (
                    "binding_run_id",
                    "proposal_package_id",
                    "proposal_package_hash",
                    "proposal_checksum",
                    "document_ref",
                    "pdf_sha256",
                    "page_ref",
                    "projection_checksum",
                    "reconciliation_plan_hash",
                )
            )
            or not _positive_int(data.get("page_number"))
            or parent_bbox is None
            or parent_bbox[0] == parent_bbox[2]
            or parent_bbox[1] == parent_bbox[3]
        ):
            errors.append("pdf_vlm_region_binding_scope_identity_invalid")
        if (
            data.get("authority_state") != "shadow_non_authoritative"
            or data.get("production_authority") is not False
            or data.get("production_gate2_selection_changed") is not False
            or data.get("provider_calls_performed") != 0
            or data.get("value_mutation_performed") is not False
            or data.get("model_invented_values_total") != 0
        ):
            errors.append("pdf_vlm_region_binding_authority_invalid")
        if not _reason_codes(data.get("reason_codes")):
            errors.append("pdf_vlm_region_binding_reason_codes_invalid")
        parent_accounting = _object(data.get("parent_atom_accounting"))
        if _parent_atom_accounting_invalid(parent_accounting):
            errors.append(
                "pdf_vlm_region_binding_parent_atom_accounting_invalid"
            )
        region_results = _dicts(data.get("region_results"))
        if (
            not isinstance(data.get("region_results"), list)
            or len(region_results) != len(data.get("region_results") or [])
            or len(region_results) > (1 if data.get("proposal_scope") == "candidate_crop" else 2)
        ):
            errors.append("pdf_vlm_region_binding_region_collection_invalid")
        region_keys: set[str] = set()
        table_refs: set[str] = set()
        accepted = 0
        for item in region_results:
            region_errors = self._validate_region_result(item)
            errors.extend(region_errors)
            errors.extend(
                _region_scope_binding_errors(
                    result=data,
                    region_result=item,
                    precision=self.config.source_coordinate_precision,
                )
            )
            region_key = str(item.get("region_key") or "")
            table_ref = str(item.get("table_ref") or "")
            if not region_key or region_key in region_keys:
                errors.append("pdf_vlm_region_binding_region_identity_invalid")
            if not table_ref or table_ref in table_refs:
                errors.append("pdf_vlm_region_binding_table_ref_duplicate")
            region_keys.add(region_key)
            table_refs.add(table_ref)
            accepted += (
                item.get("runtime_terminal_status")
                == "accepted_physical_structure"
            )
        accounting = _object(data.get("source_accounting"))
        if _source_accounting_invalid(
            accounting=accounting,
            region_results=region_results,
            accepted=accepted,
        ):
            errors.append("pdf_vlm_region_binding_source_accounting_invalid")
        if accounting.get("parent_word_refs_total") != parent_accounting.get(
            "all_parent_atoms"
        ):
            errors.append("pdf_vlm_region_binding_source_accounting_invalid")
        terminal = data.get("runtime_terminal_status")
        if terminal == "accepted_physical_structure" and (
            not region_results or accepted != len(region_results)
        ):
            errors.append("pdf_vlm_region_binding_acceptance_invalid")
        if terminal == "no_table_proposed" and region_results:
            errors.append("pdf_vlm_region_binding_absent_contract_invalid")
        unsigned = dict(data)
        stored = unsigned.pop("result_checksum", None)
        if stored != sha256_json(unsigned):
            errors.append("pdf_vlm_region_binding_result_checksum_invalid")
        return sorted(set(errors))

    def validate_result_against_inputs(
        self,
        value: Any,
        *,
        proposal_package: dict[str, Any],
        proposal: dict[str, Any],
        pdf_text_layer_projection: dict[str, Any],
        parent_source_bbox: list[float],
        region_crop_manifests: dict[str, dict[str, Any]],
    ) -> list[str]:
        """Validate self-consistency and bind every digest to caller evidence."""

        errors = self.validate_result(value)
        data = _object(value)
        if set(data) != _RESULT_KEYS:
            return errors
        package_errors = self.visual.validate_region_proposal_package(
            proposal_package
        )
        try:
            parsed = self.visual.parse_region_proposal_response(
                proposal,
                expected_package_id=str(
                    proposal_package.get("package_id") or ""
                ),
                expected_proposal_scope=str(
                    proposal_package.get("proposal_scope") or ""
                ),
            )
        except ValueError:
            parsed = {}
        if package_errors or parsed != proposal:
            errors.append("pdf_vlm_region_binding_input_anchor_invalid")
            return sorted(set(errors))

        expected_plan: dict[str, Any] = {}
        try:
            expected_plan = self.reconcile_proposal_regions(
                proposal_package=proposal_package,
                proposal=parsed,
                pdf_text_layer_projection=pdf_text_layer_projection,
                parent_source_bbox=parent_source_bbox,
            )
        except PdfVlmRegionBindingError:
            errors.append("pdf_vlm_region_binding_input_anchor_invalid")

        expected_parent_bbox = _bbox(parent_source_bbox)
        package_parent_bbox = _bbox(
            _object(proposal_package.get("crop_identity")).get(
                "declared_table_bbox"
            )
        )
        if (
            expected_parent_bbox is None
            or package_parent_bbox != expected_parent_bbox
            or data.get("parent_source_bbox") != expected_parent_bbox
        ):
            errors.append("pdf_vlm_region_binding_scope_identity_mismatch")
        expected_top = {
            "proposal_package_id": proposal_package.get("package_id"),
            "proposal_package_hash": proposal_package.get("package_hash"),
            "proposal_checksum": sha256_json(parsed),
            "proposal_scope": proposal_package.get("proposal_scope"),
            "document_ref": proposal_package.get("document_ref"),
            "pdf_sha256": proposal_package.get("pdf_sha256"),
            "page_ref": proposal_package.get("page_ref"),
            "page_number": proposal_package.get("page_number"),
            "table_presence": parsed.get("table_presence"),
            "alternatives_complete": parsed.get("alternatives_complete") is True,
            "parent_atom_accounting": expected_plan.get(
                "parent_atom_accounting"
            ),
            "reconciliation_plan_hash": expected_plan.get("plan_checksum"),
        }
        if any(data.get(key) != expected for key, expected in expected_top.items()):
            errors.append("pdf_vlm_region_binding_proposal_binding_mismatch")

        projection_checksum = sha256_json(pdf_text_layer_projection)
        if data.get("projection_checksum") != projection_checksum:
            errors.append("pdf_vlm_region_binding_projection_binding_mismatch")

        words: dict[str, dict[str, Any]] = {}
        parent_crossing: list[str] = []
        parent_outside: list[str] = []
        if expected_parent_bbox is not None:
            try:
                words, inferred_page_ref, parent_crossing, parent_outside = (
                    _page_words(
                        projection=pdf_text_layer_projection,
                        expected_page_ref=str(
                            proposal_package.get("page_ref") or ""
                        ),
                        parent_bbox=expected_parent_bbox,
                        effective_word_bboxes=(
                            _effective_candidate_word_bboxes(
                                proposal_package
                            )
                        ),
                    )
                )
            except PdfVlmRegionBindingError:
                errors.append("pdf_vlm_region_binding_input_anchor_invalid")
            else:
                if data.get("page_ref") != str(
                    proposal_package.get("page_ref") or inferred_page_ref
                ):
                    errors.append(
                        "pdf_vlm_region_binding_scope_identity_mismatch"
                    )
                if proposal_package.get("proposal_scope") == "page_level" and (
                    parent_crossing or parent_outside
                ):
                    errors.append("pdf_vlm_region_binding_input_anchor_invalid")

        candidate_scope: dict[str, str] = {}
        if words:
            try:
                candidate_scope = self._candidate_scope(
                    proposal_package=proposal_package,
                    words=words,
                )
            except PdfVlmRegionBindingError:
                errors.append("pdf_vlm_region_binding_input_anchor_invalid")
        accounting = _object(data.get("source_accounting"))
        if (
            words
            and (
                accounting.get("parent_word_refs_total") != len(words)
                or accounting.get("candidate_scope_total")
                != len(candidate_scope)
            )
        ):
            errors.append("pdf_vlm_region_binding_source_accounting_invalid")

        proposed_regions = _dicts(parsed.get("regions"))
        region_results = _dicts(data.get("region_results"))
        expected_region_keys = [
            str(item.get("region_key") or "") for item in proposed_regions
        ]
        if (
            [str(item.get("region_key") or "") for item in region_results]
            != expected_region_keys
            or set(region_crop_manifests) != set(expected_region_keys)
        ):
            errors.append("pdf_vlm_region_binding_proposal_binding_mismatch")
        result_by_key = {
            str(item.get("region_key") or ""): item for item in region_results
        }
        planned_by_key = {
            str(item.get("region_key") or ""): item
            for item in _dicts(expected_plan.get("regions"))
        }
        for region in proposed_regions:
            region_key = str(region.get("region_key") or "")
            result_region = _object(result_by_key.get(region_key))
            planned_region = _object(planned_by_key.get(region_key))
            crop_manifest = _object(region_crop_manifests.get(region_key))
            expected_original_bbox = planned_region.get(
                "original_source_bbox"
            )
            expected_source_bbox = planned_region.get(
                "reconciled_source_bbox"
            )
            if (
                not result_region
                or result_region.get("normalized_bbox") != region.get("bbox")
                or result_region.get("original_source_bbox")
                != expected_original_bbox
                or result_region.get("source_bbox") != expected_source_bbox
                or result_region.get("bbox_reconciliation")
                != planned_region.get("bbox_reconciliation")
            ):
                errors.append("pdf_vlm_region_binding_proposal_binding_mismatch")
            if words and expected_source_bbox is not None and result_region:
                included, excluded, crossing = _partition_words(
                    words,
                    expected_source_bbox,
                )
                expected_candidate_accounting = _candidate_partition(
                    candidate_scope=candidate_scope,
                    included_word_refs=included,
                    excluded_word_refs=excluded,
                    crossing_word_refs=crossing,
                )
                if (
                    result_region.get("included_word_refs")
                    != sorted(included)
                    or result_region.get("excluded_word_refs")
                    != sorted(excluded)
                    or result_region.get("crossing_word_refs")
                    != sorted(crossing)
                    or result_region.get("candidate_accounting")
                    != expected_candidate_accounting
                ):
                    errors.append(
                        "pdf_vlm_region_binding_partition_anchor_invalid"
                    )
            if (
                not crop_manifest
                or result_region.get("crop_manifest_hash")
                != crop_manifest.get("manifest_hash")
                or result_region.get("crop_sha256")
                != crop_manifest.get("png_sha256")
                or result_region.get("table_ref")
                != crop_manifest.get("table_ref")
            ):
                errors.append("pdf_vlm_region_binding_crop_binding_mismatch")

        expected_binding_run_id = "pdfvlmregionbinding_" + stable_digest(
            [
                proposal_package.get("package_hash"),
                sha256_json(parsed),
                projection_checksum,
                expected_plan.get("plan_checksum"),
                [
                    _object(region_crop_manifests.get(key)).get(
                        "manifest_hash"
                    )
                    for key in expected_region_keys
                ],
                self.config.policy_version,
            ],
            length=24,
        )
        if data.get("binding_run_id") != expected_binding_run_id:
            errors.append("pdf_vlm_region_binding_input_binding_mismatch")
        return sorted(set(errors))

    def _candidate_scope(
        self,
        *,
        proposal_package: dict[str, Any],
        words: dict[str, dict[str, Any]],
    ) -> dict[str, str]:
        if proposal_package.get("proposal_scope") != "candidate_crop":
            return {}
        dictionary = _object(proposal_package.get("private_candidate_dictionary"))
        neutral_map = _object(
            proposal_package.get("neutral_atom_to_candidate_id")
        )
        atoms = _dicts(_object(proposal_package.get("model_facing")).get("atoms"))
        result: dict[str, str] = {}
        if set(dictionary) != set(neutral_map.values()) or len(atoms) != len(dictionary):
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_candidate_identity_invalid"
            )
        for atom in atoms:
            candidate_id = str(neutral_map.get(str(atom.get("atom_id") or "")) or "")
            candidate = _object(dictionary.get(candidate_id))
            word_refs = [str(item) for item in candidate.get("word_refs") or []]
            candidate_bbox = _bbox(candidate.get("source_bbox"))
            if (
                not candidate_id
                or len(word_refs) != 1
                or word_refs[0] not in words
                or candidate_bbox
                != words[word_refs[0]]["original_bbox"]
            ):
                raise PdfVlmRegionBindingError(
                    "pdf_vlm_region_binding_candidate_provenance_mismatch"
                )
            result[candidate_id] = word_refs[0]
        return result

    def _bind_region(
        self,
        *,
        proposal_package: dict[str, Any],
        proposal: dict[str, Any],
        region: dict[str, Any],
        original_source_bbox: list[float],
        source_bbox: list[float],
        bbox_reconciliation: dict[str, Any],
        crop_manifest: dict[str, Any],
        pdf_text_layer_projection: dict[str, Any],
        words: dict[str, dict[str, Any]],
        candidate_scope: dict[str, str],
        candidate_parent_scope_evidence: dict[str, Any],
        document_ref: str,
        pdf_sha256: str,
        page_ref: str,
        page_number: int,
        proposal_checksum: str,
    ) -> dict[str, Any]:
        included, excluded, crossing = _partition_words(words, source_bbox)
        candidate_accounting = _candidate_partition(
            candidate_scope=candidate_scope,
            included_word_refs=included,
            excluded_word_refs=excluded,
            crossing_word_refs=crossing,
        )
        region_key = str(region.get("region_key") or "")
        crop_reasons = _crop_reasons(
            crop_manifest=crop_manifest,
            expected_bbox=source_bbox,
            document_ref=document_ref,
            pdf_sha256=pdf_sha256,
            page_number=page_number,
            candidate_table_ref=(
                str(proposal_package.get("table_ref") or "")
                if proposal_package.get("proposal_scope") == "candidate_crop"
                else None
            ),
        )
        table_ref = str(crop_manifest.get("table_ref") or "")
        reasons = list(crop_reasons)
        if (
            candidate_parent_scope_evidence
            and candidate_parent_scope_evidence.get(
                "candidate_parent_scope_complete"
            )
            is not True
        ):
            reasons.append(
                "pdf_vlm_region_binding_parent_scope_incomplete_"
                "adjacent_unowned_band"
            )
        if crossing:
            reasons.append("pdf_vlm_region_binding_atom_crosses_region_boundary")
        if not included:
            reasons.append("pdf_vlm_region_binding_region_has_no_word_atoms")
        if candidate_scope and not candidate_accounting["every_scope_candidate_accounted"]:
            reasons.append("pdf_vlm_region_binding_candidate_accounting_invalid")

        parser_observation: dict[str, Any] | None = None
        geometry_observation: dict[str, Any] | None = None
        visual_package: dict[str, Any] | None = None
        topology_response: dict[str, Any] | None = None
        assembly: dict[str, Any] | None = None
        binding: dict[str, Any] | None = None
        materialization: dict[str, Any] | None = None
        hypotheses = _dicts(region.get("hypotheses"))
        uncertainty = sorted(
            {
                *[str(item) for item in proposal.get("uncertainty_codes") or []],
                *[str(item) for item in region.get("uncertainty_codes") or []],
                *[
                    str(code)
                    for hypothesis in hypotheses
                    for code in hypothesis.get("uncertainty_codes") or []
                ],
            }
        )
        ambiguous = len(hypotheses) != 1 or bool(uncertainty)
        if ambiguous:
            reasons.append("pdf_vlm_region_binding_proposal_ambiguous")

        if not reasons or reasons == ["pdf_vlm_region_binding_proposal_ambiguous"]:
            try:
                parser_observation = self.contracts.build_parser_observation_from_word_atoms(
                    document_ref=document_ref,
                    pdf_sha256=pdf_sha256,
                    page_ref=page_ref,
                    page_number=page_number,
                    table_ref=table_ref,
                    table_bbox=source_bbox,
                    pdf_text_layer_projection=pdf_text_layer_projection,
                    scope_word_refs=sorted(included),
                )
                geometry_observation = self.parser_geometry.build_observation(
                    document_ref=document_ref,
                    pdf_sha256=pdf_sha256,
                    page_ref=page_ref,
                    page_number=page_number,
                    table_ref=table_ref,
                    table_bbox=source_bbox,
                    pdf_text_layer_projection=pdf_text_layer_projection,
                )
                visual_package = self.visual.build_package(
                    parser_observation=parser_observation,
                    crop_manifest=crop_manifest,
                )
                topology_response = {
                    "schema_version": PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
                    "package_id": visual_package["package_id"],
                    "decision": "ambiguous" if ambiguous else "bound",
                    "alternatives_complete": proposal.get("alternatives_complete") is True,
                    "hypotheses": copy.deepcopy(hypotheses),
                    "uncertainty_codes": uncertainty,
                }
                topology_response = self.visual.parse_response(
                    topology_response,
                    expected_package_id=visual_package["package_id"],
                )
                assembly = self.assembler.assemble(
                    parser_observation=parser_observation,
                    parser_geometry_observation=geometry_observation,
                    visual_package=visual_package,
                    topology_response=topology_response,
                    attempt_evidence={
                        "attempt_id": "pdfregionbindattempt_"
                        + stable_digest(
                            [proposal_checksum, region_key], length=24
                        ),
                        "attempt_number": 1,
                        "evidence_revision": proposal_checksum,
                        "provider": "deterministic_region_binding",
                        "model": "upstream_proposal_not_reexecuted",
                        "provider_config_hash": str(
                            proposal_package.get("package_hash") or ""
                        ),
                    },
                    hypothesis_id_prefix=f"region_{region_key}",
                )
            except ValueError as exc:
                reasons.append(
                    _error_code(
                        exc,
                        "pdf_vlm_region_binding_deterministic_validation_failed",
                    )
                )

        if not ambiguous and assembly is not None:
            reasons.extend(
                self._acceptance_reasons(
                    parser_observation=parser_observation or {},
                    visual_package=visual_package or {},
                    hypothesis=hypotheses[0],
                    assembly=assembly,
                )
            )
            bindings = _dicts(assembly.get("binding_hypotheses"))
            if not reasons and len(bindings) == 1:
                candidate_binding = _object(bindings[0].get("binding_output"))
                try:
                    candidate_materialization = self.materializer.materialize(
                        evidence_package=visual_package or {},
                        binding_output=candidate_binding,
                    )
                    materialization_errors = self.materializer.validate_materialization(
                        candidate_materialization
                    )
                except ValueError as exc:
                    reasons.append(
                        _error_code(
                            exc,
                            "pdf_vlm_region_binding_materialization_failed",
                        )
                    )
                else:
                    reasons.extend(materialization_errors)
                    reasons.extend(
                        _materialization_source_reasons(
                            materialization=candidate_materialization,
                            parser_observation=parser_observation or {},
                        )
                    )
                    if not reasons:
                        binding = candidate_binding
                        materialization = candidate_materialization

        reasons = sorted(set(reasons))
        terminal = (
            "proposal_ambiguous"
            if ambiguous
            else (
                "accepted_physical_structure"
                if binding is not None and materialization is not None and not reasons
                else "validation_blocked"
            )
        )
        return {
            "region_key": region_key,
            "table_ref": table_ref,
            "normalized_bbox": copy.deepcopy(region.get("bbox")),
            "original_source_bbox": copy.deepcopy(original_source_bbox),
            "source_bbox": source_bbox,
            "bbox_reconciliation": copy.deepcopy(bbox_reconciliation),
            "crop_manifest_hash": crop_manifest.get("manifest_hash"),
            "crop_sha256": crop_manifest.get("png_sha256"),
            "included_word_refs": sorted(included),
            "excluded_word_refs": sorted(excluded),
            "crossing_word_refs": sorted(crossing),
            "candidate_accounting": candidate_accounting,
            "parser_observation": parser_observation,
            "parser_geometry_observation": geometry_observation,
            "visual_package": visual_package,
            "topology_response": topology_response,
            "assembly": assembly,
            "accepted_binding": binding,
            "materialization": materialization,
            "runtime_terminal_status": terminal,
            "reason_codes": reasons,
        }

    def _acceptance_reasons(
        self,
        *,
        parser_observation: dict[str, Any],
        visual_package: dict[str, Any],
        hypothesis: dict[str, Any],
        assembly: dict[str, Any],
    ) -> list[str]:
        reasons: list[str] = []
        bindings = _dicts(assembly.get("binding_hypotheses"))
        if (
            assembly.get("reconstruction_status") != "assembled"
            or len(bindings) != 1
            or assembly.get("rejected_evidence")
            or assembly.get("regional_issues")
        ):
            reasons.append("pdf_vlm_region_binding_assembly_not_uniquely_bound")
        reasons.extend(
            str(item.get("reason_code") or "")
            for item in _dicts(assembly.get("regional_issues"))
            if item.get("reason_code")
        )
        if _object(assembly.get("source_accounting")).get(
            "all_bound_alternatives_exactly_once"
        ) is not True:
            reasons.append("pdf_vlm_region_binding_candidate_ownership_invalid")
        adjustments = _dicts(assembly.get("structural_adjustments"))
        if any(
            item.get("operation")
            not in PDF_TOPOLOGY_SAFE_BOUNDARY_RECONCILIATION_OPERATIONS
            for item in adjustments
        ):
            reasons.append("pdf_vlm_region_binding_proposal_repair_forbidden")
        if len(bindings) == 1:
            binding_hypothesis = bindings[0]
            binding = _object(binding_hypothesis.get("binding_output"))
            if binding.get("decision") != "bound":
                reasons.append("pdf_vlm_region_binding_binding_not_bound")
            if not _binding_bbox_compatible(
                parser_observation=parser_observation,
                visual_package=visual_package,
                binding_hypothesis=binding_hypothesis,
                tolerance=self.assembler.config.atom_band_tolerance_normalized,
            ):
                reasons.append(
                    "pdf_vlm_region_binding_atom_bbox_crosses_proposed_boundary"
                )
            if (
                binding.get("header_rows")
                != list(range(1, int(hypothesis.get("header_row_count") or 0) + 1))
                or binding.get("header_hierarchy")
                != hypothesis.get("header_hierarchy")
                or binding.get("spans") != hypothesis.get("spans")
            ):
                reasons.append(
                    "pdf_vlm_region_binding_header_or_span_mutation_forbidden"
                )
        if (
            assembly.get("package_id") != visual_package.get("package_id")
            or assembly.get("package_hash") != visual_package.get("package_hash")
            or assembly.get("parser_observation_checksum")
            != parser_observation.get("observation_checksum")
        ):
            reasons.append("pdf_vlm_region_binding_provenance_mismatch")
        return sorted(set(reasons))

    def _validate_region_result(self, value: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if set(value) != _REGION_KEYS:
            return ["pdf_vlm_region_binding_region_keys_invalid"]
        if (
            _bbox(value.get("normalized_bbox"), normalized=True) is None
            or _bbox(value.get("original_source_bbox")) is None
            or _bbox(value.get("source_bbox")) is None
            or value.get("runtime_terminal_status") not in _REGION_TERMINALS
            or not _reason_codes(value.get("reason_codes"))
        ):
            errors.append("pdf_vlm_region_binding_region_contract_invalid")
        included = value.get("included_word_refs")
        excluded = value.get("excluded_word_refs")
        crossing = value.get("crossing_word_refs")
        if not all(_unique_strings(item) for item in (included, excluded, crossing)):
            errors.append("pdf_vlm_region_binding_word_accounting_invalid")
        elif (
            set(included) & set(excluded)
            or set(included) & set(crossing)
            or set(excluded) & set(crossing)
        ):
            errors.append("pdf_vlm_region_binding_word_accounting_invalid")
        reconciliation = _object(value.get("bbox_reconciliation"))
        errors.extend(
            _bbox_reconciliation_errors(
                reconciliation,
                expected_original_bbox=_bbox(
                    value.get("original_source_bbox")
                ),
                expected_reconciled_bbox=_bbox(value.get("source_bbox")),
            )
        )
        if (
            crossing != []
            or reconciliation.get("included_word_refs_after") != included
            or reconciliation.get("excluded_word_refs_after") != excluded
            or reconciliation.get("crossing_word_refs_after") != crossing
        ):
            errors.append(
                "pdf_vlm_region_binding_reconciliation_accounting_invalid"
            )
        candidate = _object(value.get("candidate_accounting"))
        if (
            set(candidate) != _CANDIDATE_ACCOUNTING_KEYS
            or not _nonnegative_int(candidate.get("scope_candidates_total"))
            or not all(
                _unique_strings(candidate.get(key))
                for key in (
                    "included_candidate_ids",
                    "excluded_candidate_ids",
                    "crossing_candidate_ids",
                )
            )
            or candidate.get("scope_candidates_total")
            != len(candidate.get("included_candidate_ids") or [])
            + len(candidate.get("excluded_candidate_ids") or [])
            + len(candidate.get("crossing_candidate_ids") or [])
            or candidate.get("every_scope_candidate_accounted") is not True
        ):
            errors.append("pdf_vlm_region_binding_candidate_accounting_invalid")

        terminal = value.get("runtime_terminal_status")
        parser_observation = _object(value.get("parser_observation"))
        geometry = _object(value.get("parser_geometry_observation"))
        package = _object(value.get("visual_package"))
        response = _object(value.get("topology_response"))
        assembly = _object(value.get("assembly"))
        binding = value.get("accepted_binding")
        materialization = value.get("materialization")
        if parser_observation:
            errors.extend(self.contracts.validate_parser_observation(parser_observation))
        if geometry:
            errors.extend(self.parser_geometry.validate_observation(geometry))
        if package and parser_observation:
            errors.extend(
                self.visual.validate_package(
                    parser_observation=parser_observation,
                    package=package,
                )
            )
        if response and package:
            try:
                self.visual.parse_response(
                    response,
                    expected_package_id=str(package.get("package_id") or ""),
                )
            except ValueError:
                errors.append("pdf_vlm_region_binding_topology_response_invalid")
        if assembly:
            errors.extend(self.assembler.validate_result(assembly))
        if terminal == "accepted_physical_structure":
            bindings = _dicts(assembly.get("binding_hypotheses"))
            if (
                not parser_observation
                or not geometry
                or not package
                or not response
                or len(bindings) != 1
                or binding != bindings[0].get("binding_output")
                or not isinstance(materialization, dict)
                or self.materializer.validate_materialization(materialization)
            ):
                errors.append("pdf_vlm_region_binding_acceptance_invalid")
        elif binding is not None or materialization is not None:
            errors.append("pdf_vlm_region_binding_blocked_materialization_invalid")
        return sorted(set(errors))


def _region_scope_binding_errors(
    *,
    result: dict[str, Any],
    region_result: dict[str, Any],
    precision: int,
) -> list[str]:
    errors: list[str] = []
    parent_bbox = _bbox(result.get("parent_source_bbox"))
    original_source_bbox = _bbox(region_result.get("original_source_bbox"))
    source_bbox = _bbox(region_result.get("source_bbox"))
    normalized_bbox = _bbox(
        region_result.get("normalized_bbox"), normalized=True
    )
    if (
        parent_bbox is None
        or original_source_bbox is None
        or source_bbox is None
        or normalized_bbox is None
    ):
        return ["pdf_vlm_region_binding_scope_identity_mismatch"]
    try:
        expected_source_bbox = _source_bbox(
            normalized_bbox=normalized_bbox,
            parent_bbox=parent_bbox,
            precision=precision,
        )
    except PdfVlmRegionBindingError:
        expected_source_bbox = None
    if (
        expected_source_bbox != original_source_bbox
        or not _contained(source_bbox, parent_bbox)
    ):
        errors.append("pdf_vlm_region_binding_scope_identity_mismatch")

    expected_identity = {
        "document_ref": result.get("document_ref"),
        "pdf_sha256": result.get("pdf_sha256"),
        "page_ref": result.get("page_ref"),
        "page_number": result.get("page_number"),
        "table_ref": region_result.get("table_ref"),
    }
    parser_observation = _object(region_result.get("parser_observation"))
    geometry_observation = _object(
        region_result.get("parser_geometry_observation")
    )
    visual_package = _object(region_result.get("visual_package"))
    for evidence in (
        parser_observation,
        geometry_observation,
        visual_package,
    ):
        if evidence and any(
            evidence.get(key) != expected
            for key, expected in expected_identity.items()
        ):
            errors.append("pdf_vlm_region_binding_scope_identity_mismatch")

    for observation in (parser_observation, geometry_observation):
        if observation and _bbox(
            _object(observation.get("coordinate_space")).get("table_bbox")
        ) != source_bbox:
            errors.append("pdf_vlm_region_binding_scope_identity_mismatch")

    if parser_observation:
        observed_word_refs = {
            str(item.get("word_ref") or "")
            for item in _dicts(parser_observation.get("words"))
        }
        if observed_word_refs != set(
            region_result.get("included_word_refs") or []
        ):
            errors.append("pdf_vlm_region_binding_word_accounting_invalid")

    if visual_package:
        crop_identity = _object(visual_package.get("crop_identity"))
        if (
            _bbox(crop_identity.get("declared_table_bbox")) != source_bbox
            or _bbox(crop_identity.get("rendered_bbox")) != source_bbox
            or crop_identity.get("manifest_hash")
            != region_result.get("crop_manifest_hash")
            or crop_identity.get("crop_sha256")
            != region_result.get("crop_sha256")
        ):
            errors.append("pdf_vlm_region_binding_crop_binding_mismatch")
    return sorted(set(errors))


def _source_accounting_invalid(
    *,
    accounting: dict[str, Any],
    region_results: list[dict[str, Any]],
    accepted: int,
) -> bool:
    if (
        set(accounting) != _SOURCE_ACCOUNTING_KEYS
        or not all(
            _nonnegative_int(accounting.get(key))
            for key in _SOURCE_ACCOUNTING_KEYS
        )
        or accounting.get("regions_proposed") != len(region_results)
        or accounting.get("regions_accepted") != accepted
    ):
        return True
    if not region_results:
        return any(
            accounting.get(key) != 0
            for key in (
                "unique_region_word_refs_included",
                "region_word_refs_crossing",
                "candidate_scope_accounted",
                "regions_proposed",
                "regions_accepted",
            )
        )

    word_partitions: list[dict[str, set[str]]] = []
    candidate_partitions: list[dict[str, set[str]]] = []
    for item in region_results:
        words = _disjoint_partition(
            item,
            (
                "included_word_refs",
                "excluded_word_refs",
                "crossing_word_refs",
            ),
        )
        candidates = _disjoint_partition(
            _object(item.get("candidate_accounting")),
            (
                "included_candidate_ids",
                "excluded_candidate_ids",
                "crossing_candidate_ids",
            ),
        )
        if words is None or candidates is None:
            return True
        word_partitions.append(words)
        candidate_partitions.append(candidates)

    word_universes = [set().union(*item.values()) for item in word_partitions]
    candidate_universes = [
        set().union(*item.values()) for item in candidate_partitions
    ]
    if any(universe != word_universes[0] for universe in word_universes[1:]):
        return True
    if any(
        universe != candidate_universes[0]
        for universe in candidate_universes[1:]
    ):
        return True

    included_word_refs = set().union(
        *(item["included_word_refs"] for item in word_partitions)
    )
    crossing_word_refs = set().union(
        *(item["crossing_word_refs"] for item in word_partitions)
    )
    candidate_refs_accounted = set().union(*candidate_universes)
    return any(
        (
            accounting.get("parent_word_refs_total") != len(word_universes[0]),
            accounting.get("unique_region_word_refs_included")
            != len(included_word_refs),
            accounting.get("region_word_refs_crossing")
            != len(crossing_word_refs),
            accounting.get("candidate_scope_total")
            != len(candidate_universes[0]),
            accounting.get("candidate_scope_accounted")
            != len(candidate_refs_accounted),
        )
    )


def _disjoint_partition(
    value: dict[str, Any], keys: tuple[str, str, str]
) -> dict[str, set[str]] | None:
    if not all(_unique_strings(value.get(key)) for key in keys):
        return None
    partitions = {key: set(value.get(key) or []) for key in keys}
    if any(
        partitions[left] & partitions[right]
        for index, left in enumerate(keys)
        for right in keys[index + 1 :]
    ):
        return None
    return partitions


def _page_words(
    *,
    projection: dict[str, Any],
    expected_page_ref: str,
    parent_bbox: list[float],
    effective_word_bboxes: dict[str, dict[str, list[float]]],
) -> tuple[dict[str, dict[str, Any]], str, list[str], list[str]]:
    bbox_by_ref: dict[str, list[float]] = {}
    for item in _dicts(projection.get("bbox_inventory")):
        bbox_ref = str(item.get("bbox_ref") or "")
        bbox = _bbox(item.get("bbox"))
        if not bbox_ref or bbox is None or bbox_ref in bbox_by_ref:
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_bbox_inventory_invalid"
            )
        bbox_by_ref[bbox_ref] = bbox
    page_refs = {
        str(item.get("page_ref") or "")
        for item in _dicts(projection.get("word_inventory"))
        if item.get("page_ref")
    }
    page_ref = expected_page_ref
    if not page_ref:
        if len(page_refs) != 1:
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_page_ref_ambiguous"
            )
        page_ref = next(iter(page_refs))
    words: dict[str, dict[str, Any]] = {}
    crossing: list[str] = []
    outside: list[str] = []
    for item in _dicts(projection.get("word_inventory")):
        if item.get("page_ref") != page_ref:
            continue
        word_ref = str(item.get("word_ref") or "")
        bbox = bbox_by_ref.get(str(item.get("bbox_ref") or ""))
        if not word_ref or bbox is None or word_ref in words:
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_word_inventory_invalid"
            )
        effective_geometry = effective_word_bboxes.get(word_ref)
        effective_bbox = bbox
        if effective_geometry is not None:
            if bbox != effective_geometry["original_source_bbox"]:
                raise PdfVlmRegionBindingError(
                    "pdf_vlm_region_binding_candidate_provenance_mismatch"
                )
            effective_bbox = effective_geometry["reconciled_source_bbox"]
        if _contained(effective_bbox, parent_bbox):
            words[word_ref] = {
                "source": item,
                "original_bbox": bbox,
                "bbox": effective_bbox,
            }
        elif _boxes_overlap(effective_bbox, parent_bbox):
            crossing.append(word_ref)
        else:
            outside.append(word_ref)
    if not words:
        raise PdfVlmRegionBindingError(
            "pdf_vlm_region_binding_parent_word_scope_empty"
        )
    return words, page_ref, sorted(crossing), sorted(outside)


def _effective_candidate_word_bboxes(
    proposal_package: dict[str, Any],
) -> dict[str, dict[str, list[float]]]:
    if proposal_package.get("proposal_scope") != "candidate_crop":
        return {}
    dictionary = _object(proposal_package.get("private_candidate_dictionary"))
    evidence = _dicts(
        proposal_package.get("source_atom_geometry_evidence")
    )
    if len(evidence) != len(dictionary):
        raise PdfVlmRegionBindingError(
            "pdf_vlm_region_binding_candidate_provenance_mismatch"
        )
    result: dict[str, dict[str, list[float]]] = {}
    candidate_ids: set[str] = set()
    for geometry in evidence:
        candidate_id = str(geometry.get("candidate_id") or "")
        candidate = _object(dictionary.get(candidate_id))
        word_refs = [str(item) for item in candidate.get("word_refs") or []]
        original_bbox = _bbox(geometry.get("original_source_bbox"))
        reconciled_bbox = _bbox(geometry.get("reconciled_source_bbox"))
        if (
            not candidate_id
            or candidate_id in candidate_ids
            or len(word_refs) != 1
            or not word_refs[0]
            or word_refs[0] in result
            or original_bbox is None
            or reconciled_bbox is None
            or _bbox(candidate.get("source_bbox")) != original_bbox
        ):
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_candidate_provenance_mismatch"
            )
        candidate_ids.add(candidate_id)
        result[word_refs[0]] = {
            "original_source_bbox": original_bbox,
            "reconciled_source_bbox": reconciled_bbox,
        }
    if candidate_ids != set(dictionary):
        raise PdfVlmRegionBindingError(
            "pdf_vlm_region_binding_candidate_provenance_mismatch"
        )
    return result


def _partition_words(
    words: dict[str, dict[str, Any]], source_bbox: list[float]
) -> tuple[set[str], set[str], set[str]]:
    included: set[str] = set()
    excluded: set[str] = set()
    crossing: set[str] = set()
    for word_ref, record in words.items():
        bbox = record["bbox"]
        if _contained(bbox, source_bbox):
            included.add(word_ref)
        elif _boxes_overlap(bbox, source_bbox):
            crossing.add(word_ref)
        else:
            excluded.add(word_ref)
    return included, excluded, crossing


def _reconcile_source_bbox(
    *,
    words: dict[str, dict[str, Any]],
    original_bbox: list[float],
    parent_bbox: list[float],
    precision: int,
) -> dict[str, Any]:
    """Compute the least atom-complete expansion inside ``parent_bbox``."""

    del precision  # Source atom edges stay exact; only proposal conversion rounds.
    if not _contained(original_bbox, parent_bbox):
        raise PdfVlmRegionBindingError(
            "pdf_vlm_region_binding_reconciliation_parent_boundary_invalid"
        )
    included_before, excluded_before, crossing_before = _partition_words(
        words, original_bbox
    )
    current = list(original_bbox)
    adjustments: list[dict[str, Any]] = []
    for iteration in range(1, len(words) + 2):
        _, _, crossing = _partition_words(words, current)
        if not crossing:
            break
        crossing_boxes = {
            word_ref: words[word_ref]["bbox"]
            for word_ref in sorted(crossing)
        }
        next_bbox = [
            min([current[0], *[bbox[0] for bbox in crossing_boxes.values()]]),
            min([current[1], *[bbox[1] for bbox in crossing_boxes.values()]]),
            max([current[2], *[bbox[2] for bbox in crossing_boxes.values()]]),
            max([current[3], *[bbox[3] for bbox in crossing_boxes.values()]]),
        ]
        if next_bbox == current:
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_reconciliation_stalled"
            )
        if not _contained(next_bbox, parent_bbox):
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_reconciliation_parent_boundary_invalid"
            )
        edge_specs = (
            (0, "left"),
            (1, "top"),
            (2, "right"),
            (3, "bottom"),
        )
        for index, edge in edge_specs:
            if next_bbox[index] == current[index]:
                continue
            if index < 2:
                forcing = sorted(
                    word_ref
                    for word_ref, bbox in crossing_boxes.items()
                    if bbox[index] == next_bbox[index]
                    and bbox[index] < current[index]
                )
            else:
                forcing = sorted(
                    word_ref
                    for word_ref, bbox in crossing_boxes.items()
                    if bbox[index] == next_bbox[index]
                    and bbox[index] > current[index]
                )
            if not forcing:
                raise PdfVlmRegionBindingError(
                    "pdf_vlm_region_binding_reconciliation_adjustment_invalid"
                )
            adjustments.append(
                {
                    "iteration": iteration,
                    "edge": edge,
                    "from_coordinate": current[index],
                    "to_coordinate": next_bbox[index],
                    "reason_code": (
                        "complete_crossing_source_atom_boundary"
                    ),
                    "word_refs": forcing,
                }
            )
        current = next_bbox
    else:
        raise PdfVlmRegionBindingError(
            "pdf_vlm_region_binding_reconciliation_not_converged"
        )

    included_after, excluded_after, crossing_after = _partition_words(
        words, current
    )
    all_parent_atoms = len(words)
    every_accounted = (
        len(included_after) + len(excluded_after) + len(crossing_after)
        == all_parent_atoms
    )
    if crossing_after or not every_accounted:
        raise PdfVlmRegionBindingError(
            "pdf_vlm_region_binding_reconciliation_accounting_invalid"
        )
    return {
        "original_source_bbox": copy.deepcopy(original_bbox),
        "reconciled_source_bbox": copy.deepcopy(current),
        "adjustments": adjustments,
        "included_word_refs_before": sorted(included_before),
        "excluded_word_refs_before": sorted(excluded_before),
        "crossing_word_refs_before": sorted(crossing_before),
        "included_word_refs_after": sorted(included_after),
        "excluded_word_refs_after": sorted(excluded_after),
        "crossing_word_refs_after": sorted(crossing_after),
        "included_atoms": len(included_after),
        "excluded_atoms": len(excluded_after),
        "crossing_atoms": len(crossing_after),
        "all_parent_atoms": all_parent_atoms,
        "every_parent_atom_accounted": every_accounted,
    }


def _projection_page_bbox(
    *,
    projection: dict[str, Any],
    expected_page_ref: str,
) -> list[float] | None:
    pages = [
        item
        for item in _dicts(projection.get("page_inventory"))
        if item.get("page_ref") == expected_page_ref
    ]
    if len(pages) != 1:
        return None
    width = pages[0].get("layout_page_width")
    height = pages[0].get("layout_page_height")
    if (
        not _number(width)
        or not _number(height)
        or float(width) <= 0.0
        or float(height) <= 0.0
    ):
        return None
    return [0.0, 0.0, float(width), float(height)]


def _candidate_parent_scope_evidence(
    *,
    candidate: dict[str, Any],
    projection: dict[str, Any],
    expected_page_ref: str,
    page_bbox: list[float],
) -> dict[str, Any]:
    page_scope = _bbox(page_bbox)
    table_ref = str(candidate.get("table_candidate_ref") or "")
    candidate_page_ref = str(candidate.get("page_ref") or "")
    refs = candidate.get("contributing_word_refs")
    if (
        page_scope is None
        or page_scope[0] == page_scope[2]
        or page_scope[1] == page_scope[3]
        or not table_ref
        or not expected_page_ref
        or candidate_page_ref != expected_page_ref
        or not isinstance(refs, list)
        or not refs
        or any(not isinstance(ref, str) or not ref for ref in refs)
        or len(refs) != len(set(refs))
    ):
        raise PdfVlmRegionBindingError(
            "pdf_vlm_region_binding_candidate_parent_bbox_invalid"
        )

    bbox_by_ref: dict[str, list[float]] = {}
    for item in _dicts(projection.get("bbox_inventory")):
        bbox_ref = str(item.get("bbox_ref") or "")
        bbox = _bbox(item.get("bbox"))
        if not bbox_ref or bbox is None or bbox_ref in bbox_by_ref:
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_candidate_parent_bbox_invalid"
            )
        bbox_by_ref[bbox_ref] = bbox
    original = bbox_by_ref.get(str(candidate.get("bbox_ref") or ""))
    if original is None or not _contained(original, page_scope):
        raise PdfVlmRegionBindingError(
            "pdf_vlm_region_binding_candidate_parent_bbox_invalid"
        )

    page_words: dict[str, list[float]] = {}
    for word in _dicts(projection.get("word_inventory")):
        if word.get("page_ref") != expected_page_ref:
            continue
        word_ref = str(word.get("word_ref") or "")
        bbox = bbox_by_ref.get(str(word.get("bbox_ref") or ""))
        if (
            not word_ref
            or bbox is None
            or word_ref in page_words
            or not _contained(bbox, page_scope)
        ):
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_candidate_parent_bbox_invalid"
            )
        page_words[word_ref] = bbox
    owned = {ref: page_words.get(ref) for ref in refs}
    if any(bbox is None for bbox in owned.values()):
        raise PdfVlmRegionBindingError(
            "pdf_vlm_region_binding_candidate_parent_bbox_invalid"
        )
    owned_boxes = {
        ref: list(bbox)
        for ref, bbox in owned.items()
        if isinstance(bbox, list)
    }
    uncontained = {
        ref: bbox
        for ref, bbox in owned_boxes.items()
        if not _contained(bbox, original)
    }
    if any(not _boxes_overlap(bbox, original) for bbox in uncontained.values()):
        raise PdfVlmRegionBindingError(
            "pdf_vlm_region_binding_candidate_parent_bbox_invalid"
        )

    reconciled = [
        min(original[0], *(bbox[0] for bbox in owned_boxes.values())),
        min(original[1], *(bbox[1] for bbox in owned_boxes.values())),
        max(original[2], *(bbox[2] for bbox in owned_boxes.values())),
        max(original[3], *(bbox[3] for bbox in owned_boxes.values())),
    ]
    if not _contained(reconciled, page_scope) or any(
        not _contained(bbox, reconciled) for bbox in owned_boxes.values()
    ):
        raise PdfVlmRegionBindingError(
            "pdf_vlm_region_binding_candidate_parent_bbox_invalid"
        )

    adjustments: list[dict[str, Any]] = []
    for index, edge in enumerate(("left", "top", "right", "bottom")):
        if reconciled[index] == original[index]:
            continue
        forcing_refs = sorted(
            ref
            for ref, bbox in owned_boxes.items()
            if bbox[index] == reconciled[index]
            and (
                bbox[index] < original[index]
                if index < 2
                else bbox[index] > original[index]
            )
        )
        if not forcing_refs:
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_candidate_parent_bbox_invalid"
            )
        normal_extent_index = (0, 2) if edge in {"left", "right"} else (1, 3)
        maximum_gap = max(
            owned_boxes[ref][normal_extent_index[1]]
            - owned_boxes[ref][normal_extent_index[0]]
            for ref in forcing_refs
        )
        if maximum_gap <= 0.0:
            raise PdfVlmRegionBindingError(
                "pdf_vlm_region_binding_candidate_parent_bbox_invalid"
            )
        adjustments.append(
            {
                "edge": edge,
                "from_coordinate": original[index],
                "to_coordinate": reconciled[index],
                "adjustment_code": (
                    "complete_routed_candidate_source_atom_boundary"
                ),
                "word_refs": forcing_refs,
                "forcing_atom_bboxes": [
                    copy.deepcopy(owned_boxes[ref]) for ref in forcing_refs
                ],
                "maximum_adjacent_gap_points": round(maximum_gap, 9),
            }
        )

    owned_refs = set(owned_boxes)
    unowned_contained = sorted(
        ref
        for ref, bbox in page_words.items()
        if ref not in owned_refs and _contained(bbox, reconciled)
    )
    adjacent: list[dict[str, Any]] = []
    for adjustment in adjustments:
        edge = str(adjustment["edge"])
        maximum_gap = float(adjustment["maximum_adjacent_gap_points"])
        for word_ref, bbox in page_words.items():
            if word_ref in owned_refs or _contained(bbox, reconciled):
                continue
            if edge == "left":
                gap = reconciled[0] - bbox[2]
                overlap = _interval_overlap(
                    reconciled[1], reconciled[3], bbox[1], bbox[3]
                )
            elif edge == "top":
                gap = reconciled[1] - bbox[3]
                overlap = _interval_overlap(
                    reconciled[0], reconciled[2], bbox[0], bbox[2]
                )
            elif edge == "right":
                gap = bbox[0] - reconciled[2]
                overlap = _interval_overlap(
                    reconciled[1], reconciled[3], bbox[1], bbox[3]
                )
            else:
                gap = bbox[1] - reconciled[3]
                overlap = _interval_overlap(
                    reconciled[0], reconciled[2], bbox[0], bbox[2]
                )
            if gap < 0.0 or gap > maximum_gap or overlap <= 0.0:
                continue
            adjacent.append(
                {
                    "edge": edge,
                    "word_ref": word_ref,
                    "source_bbox": copy.deepcopy(bbox),
                    "gap_points": round(gap, 9),
                    "maximum_gap_points": round(maximum_gap, 9),
                    "orthogonal_overlap_points": round(overlap, 9),
                }
            )
    edge_order = {"left": 0, "top": 1, "right": 2, "bottom": 3}
    adjacent.sort(
        key=lambda item: (
            edge_order[str(item["edge"])],
            float(item["gap_points"]),
            str(item["word_ref"]),
        )
    )
    adjacent_refs = sorted(
        {str(item["word_ref"]) for item in adjacent}
    )
    completion_applied = bool(adjustments)
    evidence = {
        "schema_version": PDF_VLM_CANDIDATE_PARENT_SCOPE_EVIDENCE_SCHEMA,
        "candidate_table_ref": table_ref,
        "original_source_bbox": copy.deepcopy(original),
        "reconciled_source_bbox": copy.deepcopy(reconciled),
        "completion_applied": completion_applied,
        "adjustments": adjustments,
        "owned_word_refs": sorted(owned_refs),
        "owned_word_refs_total": len(owned_refs),
        "uncontained_owned_word_refs": sorted(uncontained),
        "all_owned_atoms_contained": True,
        "unowned_contained_word_refs": unowned_contained,
        "adjacent_unowned_atom_evidence": adjacent,
        "adjacent_unowned_word_refs": adjacent_refs,
        "candidate_parent_scope_complete": bool(
            not completion_applied
            or not unowned_contained
            and not adjacent_refs
        ),
    }
    evidence["evidence_checksum"] = sha256_json(evidence)
    return evidence


def _candidate_parent_scope_evidence_invalid(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != (
        _CANDIDATE_PARENT_SCOPE_EVIDENCE_KEYS
    ):
        return True
    unsigned = copy.deepcopy(value)
    stored_checksum = unsigned.pop("evidence_checksum", None)
    original = _bbox(value.get("original_source_bbox"))
    reconciled = _bbox(value.get("reconciled_source_bbox"))
    owned_refs = value.get("owned_word_refs")
    uncontained_refs = value.get("uncontained_owned_word_refs")
    unowned_contained_refs = value.get("unowned_contained_word_refs")
    adjacent_refs = value.get("adjacent_unowned_word_refs")
    adjustments = _dicts(value.get("adjustments"))
    adjacent = _dicts(value.get("adjacent_unowned_atom_evidence"))
    if (
        value.get("schema_version")
        != PDF_VLM_CANDIDATE_PARENT_SCOPE_EVIDENCE_SCHEMA
        or not isinstance(value.get("candidate_table_ref"), str)
        or not value.get("candidate_table_ref")
        or original is None
        or reconciled is None
        or reconciled[0] > original[0]
        or reconciled[1] > original[1]
        or reconciled[2] < original[2]
        or reconciled[3] < original[3]
        or not _unique_strings(owned_refs)
        or not owned_refs
        or not _unique_strings(uncontained_refs)
        or not set(uncontained_refs).issubset(set(owned_refs))
        or not _unique_strings(unowned_contained_refs)
        or set(unowned_contained_refs) & set(owned_refs)
        or not _unique_strings(adjacent_refs)
        or set(adjacent_refs) & set(owned_refs)
        or value.get("owned_word_refs_total") != len(owned_refs)
        or value.get("all_owned_atoms_contained") is not True
        or not isinstance(value.get("completion_applied"), bool)
        or not isinstance(value.get("candidate_parent_scope_complete"), bool)
        or not isinstance(value.get("adjustments"), list)
        or len(adjustments) != len(value.get("adjustments") or [])
        or not isinstance(value.get("adjacent_unowned_atom_evidence"), list)
        or len(adjacent)
        != len(value.get("adjacent_unowned_atom_evidence") or [])
        or stored_checksum != sha256_json(unsigned)
    ):
        return True

    current = list(original)
    edge_index = {"left": 0, "top": 1, "right": 2, "bottom": 3}
    observed_edges: list[str] = []
    for adjustment in adjustments:
        edge = str(adjustment.get("edge") or "")
        index = edge_index.get(edge)
        word_refs = adjustment.get("word_refs")
        forcing_bboxes = adjustment.get("forcing_atom_bboxes")
        if (
            set(adjustment) != _CANDIDATE_PARENT_ADJUSTMENT_KEYS
            or index is None
            or edge in observed_edges
            or observed_edges
            and edge_index[observed_edges[-1]] >= index
            or adjustment.get("adjustment_code")
            != "complete_routed_candidate_source_atom_boundary"
            or not _number(adjustment.get("from_coordinate"))
            or not _number(adjustment.get("to_coordinate"))
            or float(adjustment["from_coordinate"]) != current[index]
            or index < 2
            and float(adjustment["to_coordinate"]) >= current[index]
            or index >= 2
            and float(adjustment["to_coordinate"]) <= current[index]
            or not _unique_strings(word_refs)
            or not word_refs
            or not set(word_refs).issubset(set(owned_refs))
            or not isinstance(forcing_bboxes, list)
            or len(forcing_bboxes) != len(word_refs)
            or any(_bbox(bbox) is None for bbox in forcing_bboxes)
            or not _number(adjustment.get("maximum_adjacent_gap_points"))
            or float(adjustment["maximum_adjacent_gap_points"]) <= 0.0
        ):
            return True
        current[index] = float(adjustment["to_coordinate"])
        observed_edges.append(edge)
    if (
        current != reconciled
        or bool(adjustments) != value.get("completion_applied")
    ):
        return True

    observed_adjacent_refs: set[str] = set()
    previous_key: tuple[int, float, str] | None = None
    for item in adjacent:
        edge = str(item.get("edge") or "")
        key = (
            edge_index.get(edge, -1),
            float(item.get("gap_points") or 0.0),
            str(item.get("word_ref") or ""),
        )
        if (
            set(item) != _ADJACENT_UNOWNED_ATOM_KEYS
            or edge not in observed_edges
            or not isinstance(item.get("word_ref"), str)
            or not item.get("word_ref")
            or item.get("word_ref") in owned_refs
            or _bbox(item.get("source_bbox")) is None
            or not _number(item.get("gap_points"))
            or float(item["gap_points"]) < 0.0
            or not _number(item.get("maximum_gap_points"))
            or float(item["maximum_gap_points"]) <= 0.0
            or float(item["gap_points"]) > float(item["maximum_gap_points"])
            or not _number(item.get("orthogonal_overlap_points"))
            or float(item["orthogonal_overlap_points"]) <= 0.0
            or previous_key is not None
            and key < previous_key
        ):
            return True
        observed_adjacent_refs.add(str(item["word_ref"]))
        previous_key = key
    expected_complete = bool(
        not adjustments
        or not unowned_contained_refs
        and not observed_adjacent_refs
    )
    return bool(
        sorted(observed_adjacent_refs) != adjacent_refs
        or value.get("candidate_parent_scope_complete")
        is not expected_complete
    )


def _interval_overlap(
    first_start: float,
    first_end: float,
    second_start: float,
    second_end: float,
) -> float:
    return max(0.0, min(first_end, second_end) - max(first_start, second_start))


def _parent_atom_accounting_invalid(value: dict[str, Any]) -> bool:
    candidate_parent_scope_evidence = value.get(
        "candidate_parent_scope_evidence"
    )
    if (
        set(value) != _PARENT_ATOM_ACCOUNTING_KEYS
        or not all(
            _nonnegative_int(value.get(key))
            for key in (
                "page_atoms_total",
                "all_parent_atoms",
                "parent_boundary_crossing_atoms",
                "outside_parent_atoms",
            )
        )
        or not _unique_strings(value.get("parent_boundary_crossing_word_refs"))
        or value.get("parent_boundary_preserved") is not True
        or candidate_parent_scope_evidence is not None
        and _candidate_parent_scope_evidence_invalid(
            candidate_parent_scope_evidence
        )
    ):
        return True
    return bool(
        value.get("page_atoms_total")
        != value.get("all_parent_atoms")
        + value.get("parent_boundary_crossing_atoms")
        + value.get("outside_parent_atoms")
        or value.get("parent_boundary_crossing_atoms")
        != len(value.get("parent_boundary_crossing_word_refs") or [])
    )


def _bbox_reconciliation_errors(
    value: dict[str, Any],
    *,
    expected_original_bbox: list[float] | None,
    expected_reconciled_bbox: list[float] | None,
) -> list[str]:
    errors: list[str] = []
    if set(value) != _BBOX_RECONCILIATION_KEYS:
        return ["pdf_vlm_region_binding_bbox_reconciliation_keys_invalid"]
    original_bbox = _bbox(value.get("original_source_bbox"))
    reconciled_bbox = _bbox(value.get("reconciled_source_bbox"))
    if (
        original_bbox is None
        or reconciled_bbox is None
        or original_bbox != expected_original_bbox
        or reconciled_bbox != expected_reconciled_bbox
        or reconciled_bbox[0] > original_bbox[0]
        or reconciled_bbox[1] > original_bbox[1]
        or reconciled_bbox[2] < original_bbox[2]
        or reconciled_bbox[3] < original_bbox[3]
    ):
        errors.append("pdf_vlm_region_binding_bbox_reconciliation_invalid")

    ref_keys = (
        "included_word_refs_before",
        "excluded_word_refs_before",
        "crossing_word_refs_before",
        "included_word_refs_after",
        "excluded_word_refs_after",
        "crossing_word_refs_after",
    )
    if not all(_unique_strings(value.get(key)) for key in ref_keys):
        errors.append(
            "pdf_vlm_region_binding_reconciliation_accounting_invalid"
        )
    before = [set(value.get(key) or []) for key in ref_keys[:3]]
    after = [set(value.get(key) or []) for key in ref_keys[3:]]
    if (
        any(
            left & right
            for partitions in (before, after)
            for index, left in enumerate(partitions)
            for right in partitions[index + 1 :]
        )
        or set().union(*before) != set().union(*after)
        or value.get("included_atoms") != len(after[0])
        or value.get("excluded_atoms") != len(after[1])
        or value.get("crossing_atoms") != len(after[2])
        or value.get("all_parent_atoms") != len(set().union(*after))
        or value.get("all_parent_atoms")
        != len(after[0]) + len(after[1]) + len(after[2])
        or value.get("crossing_atoms") != 0
        or value.get("crossing_word_refs_after") != []
        or value.get("every_parent_atom_accounted") is not True
    ):
        errors.append(
            "pdf_vlm_region_binding_reconciliation_accounting_invalid"
        )

    adjustments = _dicts(value.get("adjustments"))
    if (
        not isinstance(value.get("adjustments"), list)
        or len(adjustments) != len(value.get("adjustments") or [])
    ):
        errors.append("pdf_vlm_region_binding_bbox_adjustments_invalid")
        adjustments = []
    current = list(original_bbox or [])
    edge_index = {"left": 0, "top": 1, "right": 2, "bottom": 3}
    previous_order = (0, -1)
    for adjustment in adjustments:
        edge = adjustment.get("edge")
        index = edge_index.get(str(edge))
        order = (
            adjustment.get("iteration")
            if _positive_int(adjustment.get("iteration"))
            else 0,
            index if index is not None else -1,
        )
        if (
            set(adjustment) != _BBOX_ADJUSTMENT_KEYS
            or index is None
            or not _positive_int(adjustment.get("iteration"))
            or order <= previous_order
            or not _number(adjustment.get("from_coordinate"))
            or not _number(adjustment.get("to_coordinate"))
            or adjustment.get("reason_code")
            != "complete_crossing_source_atom_boundary"
            or not _unique_strings(adjustment.get("word_refs"))
            or not adjustment.get("word_refs")
            or len(current) != 4
            or float(adjustment.get("from_coordinate")) != current[index]
            or (
                index < 2
                and float(adjustment.get("to_coordinate"))
                >= current[index]
            )
            or (
                index >= 2
                and float(adjustment.get("to_coordinate"))
                <= current[index]
            )
        ):
            errors.append("pdf_vlm_region_binding_bbox_adjustments_invalid")
            continue
        current[index] = float(adjustment["to_coordinate"])
        previous_order = order
    if reconciled_bbox is not None and current != reconciled_bbox:
        errors.append("pdf_vlm_region_binding_bbox_adjustments_invalid")
    if bool(adjustments) != (original_bbox != reconciled_bbox):
        errors.append("pdf_vlm_region_binding_bbox_adjustments_invalid")
    return sorted(set(errors))


def _candidate_partition(
    *,
    candidate_scope: dict[str, str],
    included_word_refs: set[str],
    excluded_word_refs: set[str],
    crossing_word_refs: set[str],
) -> dict[str, Any]:
    included = sorted(
        candidate_id
        for candidate_id, word_ref in candidate_scope.items()
        if word_ref in included_word_refs
    )
    excluded = sorted(
        candidate_id
        for candidate_id, word_ref in candidate_scope.items()
        if word_ref in excluded_word_refs
    )
    crossing = sorted(
        candidate_id
        for candidate_id, word_ref in candidate_scope.items()
        if word_ref in crossing_word_refs
    )
    return {
        "scope_candidates_total": len(candidate_scope),
        "included_candidate_ids": included,
        "excluded_candidate_ids": excluded,
        "crossing_candidate_ids": crossing,
        "every_scope_candidate_accounted": (
            len(candidate_scope) == len(included) + len(excluded) + len(crossing)
        ),
    }


def _crop_reasons(
    *,
    crop_manifest: dict[str, Any],
    expected_bbox: list[float],
    document_ref: str,
    pdf_sha256: str,
    page_number: int,
    candidate_table_ref: str | None,
) -> list[str]:
    reasons: list[str] = []
    unsigned = dict(crop_manifest)
    stored_hash = unsigned.pop("manifest_hash", None)
    if stored_hash != sha256_json(unsigned):
        reasons.append("pdf_vlm_region_binding_crop_manifest_hash_invalid")
    if (
        crop_manifest.get("schema_version") != "broker_reports_pdf_table_crop_v1"
        or crop_manifest.get("policy_version") != "pdf_table_raster_policy_v1"
        or crop_manifest.get("document_ref") != document_ref
        or crop_manifest.get("pdf_sha256") != pdf_sha256
        or crop_manifest.get("page_number") != page_number
        or not crop_manifest.get("table_ref")
        or (candidate_table_ref is not None and crop_manifest.get("table_ref") != candidate_table_ref)
    ):
        reasons.append("pdf_vlm_region_binding_crop_provenance_mismatch")
    if (
        _bbox(crop_manifest.get("declared_table_bbox")) != expected_bbox
        or _bbox(crop_manifest.get("rendered_bbox")) != expected_bbox
        or crop_manifest.get("padding_points") != 0.0
        or crop_manifest.get("page_rotation") != 0
        or crop_manifest.get("applied_rotation") != 0
    ):
        reasons.append("pdf_vlm_region_binding_crop_geometry_mismatch")
    if (
        crop_manifest.get("source_coordinate_space") != "pdf_top_left_points"
        or crop_manifest.get("pixel_coordinate_space") != "crop_top_left_pixels"
        or crop_manifest.get("dpi") not in {150, 200}
        or not crop_manifest.get("crop_id")
        or not crop_manifest.get("png_sha256")
        or not _positive_int(crop_manifest.get("width"))
        or not _positive_int(crop_manifest.get("height"))
        or not _positive_int(crop_manifest.get("png_bytes"))
        or crop_manifest.get("lossless") is not True
        or crop_manifest.get("silent_resize_performed") is not False
    ):
        reasons.append("pdf_vlm_region_binding_crop_contract_invalid")
    return sorted(set(reasons))


def _binding_bbox_compatible(
    *,
    parser_observation: dict[str, Any],
    visual_package: dict[str, Any],
    binding_hypothesis: dict[str, Any],
    tolerance: float,
) -> bool:
    binding = _object(binding_hypothesis.get("binding_output"))
    geometry = _object(binding_hypothesis.get("proposed_geometry"))
    rows = [float(item) for item in _object(geometry.get("rows")).get("boundaries") or []]
    columns = [float(item) for item in _object(geometry.get("columns")).get("boundaries") or []]
    row_count = binding.get("row_count")
    column_count = binding.get("column_count")
    if (
        not _positive_int(row_count)
        or not _positive_int(column_count)
        or len(rows) != row_count + 1
        or len(columns) != column_count + 1
    ):
        return False
    neutral_map = _object(visual_package.get("neutral_atom_to_candidate_id"))
    atom_boxes = {
        str(neutral_map.get(str(atom.get("atom_id") or "")) or ""): atom.get("bbox")
        for atom in _dicts(_object(visual_package.get("model_facing")).get("atoms"))
    }
    positions: dict[str, tuple[int, int]] = {}
    for row in _dicts(binding.get("rows")):
        row_ordinal = row.get("row_ordinal")
        cells = row.get("cells")
        if not _positive_int(row_ordinal) or not isinstance(cells, list):
            return False
        for column_ordinal, cell in enumerate(cells, start=1):
            if not isinstance(cell, list):
                return False
            for candidate_id in cell:
                key = str(candidate_id)
                if key in positions:
                    return False
                positions[key] = (row_ordinal, column_ordinal)
    expected = {str(item) for item in parser_observation.get("candidate_order") or []}
    if set(positions) != expected or set(atom_boxes) != expected:
        return False
    spans = _dicts(binding.get("spans"))
    for candidate_id, (row, column) in positions.items():
        end_row, end_column = row, column
        for span in spans:
            if span.get("start_row") == row and span.get("start_column") == column:
                end_row = span.get("end_row")
                end_column = span.get("end_column")
                break
        bbox = atom_boxes.get(candidate_id)
        if (
            not _positive_int(end_row)
            or not _positive_int(end_column)
            or not isinstance(bbox, list)
            or len(bbox) != 4
            or bbox[0] < columns[column - 1] - tolerance
            or bbox[1] < rows[row - 1] - tolerance
            or bbox[2] > columns[end_column] + tolerance
            or bbox[3] > rows[end_row] + tolerance
        ):
            return False
    return True


def _materialization_source_reasons(
    *,
    materialization: dict[str, Any],
    parser_observation: dict[str, Any],
) -> list[str]:
    candidates = _dicts(parser_observation.get("candidates"))
    candidate_ids = {str(item.get("candidate_id") or "") for item in candidates}
    source_refs = {
        str(ref) for item in candidates for ref in item.get("source_value_refs") or []
    }
    word_refs = {str(ref) for item in candidates for ref in item.get("word_refs") or []}
    if (
        set(materialization.get("selected_candidate_ids") or []) != candidate_ids
        or materialization.get("omitted_candidate_ids") != []
        or materialization.get("extra_candidate_ids") != []
        or materialization.get("duplicate_candidate_ids") != []
        or set(materialization.get("source_value_refs") or []) != source_refs
        or set(materialization.get("word_refs") or []) != word_refs
        or materialization.get("structural_provenance_conflicts") != []
        or materialization.get("model_invented_values_total") != 0
    ):
        return ["pdf_vlm_region_binding_source_materialization_invalid"]
    return []


def _top_terminal(
    *,
    table_presence: str,
    proposal_uncertainty: list[str],
    region_results: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    if table_presence == "absent":
        return "no_table_proposed", []
    if table_presence == "uncertain" or proposal_uncertainty:
        return "proposal_ambiguous", sorted(
            {"pdf_vlm_region_binding_proposal_ambiguous", *proposal_uncertainty}
        )
    accepted = sum(
        item.get("runtime_terminal_status") == "accepted_physical_structure"
        for item in region_results
    )
    reasons = sorted(
        {
            str(code)
            for item in region_results
            for code in item.get("reason_codes") or []
        }
    )
    if region_results and accepted == len(region_results):
        return "accepted_physical_structure", []
    if accepted:
        return "partially_validated", reasons
    if any(
        item.get("runtime_terminal_status") == "proposal_ambiguous"
        for item in region_results
    ):
        return "proposal_ambiguous", reasons
    return "validation_blocked", reasons


def _source_bbox(
    *,
    normalized_bbox: Any,
    parent_bbox: list[float],
    precision: int,
) -> list[float]:
    normalized = _bbox(normalized_bbox, normalized=True)
    if normalized is None or normalized[0] == normalized[2] or normalized[1] == normalized[3]:
        raise PdfVlmRegionBindingError(
            "pdf_vlm_region_binding_normalized_bbox_invalid"
        )
    width = parent_bbox[2] - parent_bbox[0]
    height = parent_bbox[3] - parent_bbox[1]
    return [
        round(parent_bbox[0] + normalized[0] * width, precision),
        round(parent_bbox[1] + normalized[1] * height, precision),
        round(parent_bbox[0] + normalized[2] * width, precision),
        round(parent_bbox[1] + normalized[3] * height, precision),
    ]


def _contained(value: list[float], scope: list[float]) -> bool:
    return (
        value[0] >= scope[0]
        and value[1] >= scope[1]
        and value[2] <= scope[2]
        and value[3] <= scope[3]
    )


def _boxes_overlap(left: list[float], right: list[float]) -> bool:
    return (
        min(left[2], right[2]) > max(left[0], right[0])
        and min(left[3], right[3]) > max(left[1], right[1])
    )


def _bbox(value: Any, *, normalized: bool = False) -> list[float] | None:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or not all(_number(item) for item in value)
    ):
        return None
    result = [float(item) for item in value]
    if result[0] > result[2] or result[1] > result[3]:
        return None
    if normalized and any(item < 0.0 or item > 1.0 for item in result):
        return None
    return result


def _number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _unique_strings(value: Any) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(item, str) and bool(item) for item in value)
        and value == sorted(set(value))
    )


def _reason_codes(value: Any) -> bool:
    return (
        isinstance(value, list)
        and value == sorted(set(value))
        and all(isinstance(item, str) and _CODE.fullmatch(item) for item in value)
    )


def _error_code(exc: BaseException, fallback: str) -> str:
    code = getattr(exc, "code", None)
    return str(code) if isinstance(code, str) and _CODE.fullmatch(code) else fallback


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
