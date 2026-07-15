from __future__ import annotations

import copy
import itertools
import math
from dataclasses import asdict, dataclass
from typing import Any

from .contracts import stable_digest
from .pdf_dual_oracle_contracts import PdfDualOracleContractFactory
from .pdf_hybrid_contracts import sha256_json


PDF_STRUCTURAL_ROW_WINDOW_PLAN_SCHEMA = (
    "broker_reports_pdf_structural_row_window_plan_v1"
)
PDF_STRUCTURAL_ROW_WINDOW_STITCH_SCHEMA = (
    "broker_reports_pdf_structural_row_window_stitch_v1"
)
PDF_STRUCTURAL_ROW_WINDOW_POLICY_VERSION = (
    "pdf_structural_row_window_policy_v1"
)

FACTORY_REQUIRED = (
    "PdfStructuralRowWindowFactory.create is the only raw-word-atom window "
    "planning and attempt-local topology stitching entrypoint"
)
FORBIDDEN = (
    "Window planning must not consume parser rows, columns, cell values, legacy "
    "grids, compacted values, or mix hypotheses from different provider attempts"
)

_FACTORY_TOKEN = object()
_PLAN_KEYS = {
    "schema_version",
    "policy_version",
    "policy_configuration_hash",
    "mode",
    "parser_observation_id",
    "parser_observation_checksum",
    "table_bbox",
    "candidate_atoms",
    "maximum_owner_atoms_per_window",
    "window_count",
    "windows",
    "candidate_ownership_exact",
    "column_splitting_used",
    "legacy_grid_consumed",
    "plan_hash",
}
_WINDOW_KEYS = {
    "window_id",
    "window_index",
    "owner_candidate_ids",
    "owner_atom_count",
    "source_band_start",
    "source_band_end",
    "core_bbox",
    "crop_bbox",
    "core_y_normalized_in_table",
    "core_y_normalized_in_crop",
    "full_width",
    "column_splitting_used",
}
_STITCH_KEYS = {
    "schema_version",
    "policy_version",
    "policy_configuration_hash",
    "attempt_number",
    "plan_hash",
    "full_package_id",
    "window_package_ids",
    "window_response_checksums",
    "window_attempt_ids",
    "window_attempt_ids_checksum",
    "composite_attempt_id",
    "window_count",
    "candidate_ownership_exact",
    "attempts_mixed",
    "column_splitting_used",
    "stitched_response",
    "stitch_hash",
}


class PdfStructuralRowWindowError(ValueError):
    def __init__(self, code: str, subject: str = "") -> None:
        self.code = code
        self.subject = subject
        super().__init__(code if not subject else f"{code}:{subject}")


@dataclass(frozen=True)
class PdfStructuralRowWindowConfig:
    policy_version: str = PDF_STRUCTURAL_ROW_WINDOW_POLICY_VERSION
    whole_table_maximum_atoms: int = 192
    maximum_table_atoms: int = 1_000
    maximum_owner_atoms_per_window: int = 192
    maximum_windows: int = 16
    maximum_stitched_hypotheses: int = 4
    maximum_alternative_combinations: int = 4_096
    boundary_tolerance: float = 0.015
    band_overlap_epsilon_points: float = 0.001


class PdfStructuralRowWindowFactory:
    def __init__(
        self, config: PdfStructuralRowWindowConfig | None = None
    ) -> None:
        self.config = config or PdfStructuralRowWindowConfig()

    def create(self) -> "PdfStructuralRowWindowRuntime":
        if self.config.policy_version != PDF_STRUCTURAL_ROW_WINDOW_POLICY_VERSION:
            raise PdfStructuralRowWindowError(
                "pdf_structural_window_policy_invalid"
            )
        integers = (
            self.config.whole_table_maximum_atoms,
            self.config.maximum_table_atoms,
            self.config.maximum_owner_atoms_per_window,
            self.config.maximum_windows,
            self.config.maximum_stitched_hypotheses,
            self.config.maximum_alternative_combinations,
        )
        if (
            min(integers) < 1
            or self.config.whole_table_maximum_atoms
            > self.config.maximum_owner_atoms_per_window
            or self.config.maximum_owner_atoms_per_window
            > self.config.maximum_table_atoms
            or not 0.0 < self.config.boundary_tolerance < 0.1
            or self.config.band_overlap_epsilon_points < 0.0
        ):
            raise PdfStructuralRowWindowError(
                "pdf_structural_window_config_invalid"
            )
        return PdfStructuralRowWindowRuntime(
            self.config,
            _factory_token=_FACTORY_TOKEN,
        )


class PdfStructuralRowWindowRuntime:
    def __init__(
        self,
        config: PdfStructuralRowWindowConfig,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise PdfStructuralRowWindowError(
                "pdf_structural_window_factory_required"
            )
        self.config = config
        self.contracts = PdfDualOracleContractFactory().create()

    def execution_mode(self, parser_observation: dict[str, Any]) -> str:
        errors = self.contracts.validate_parser_observation(parser_observation)
        if errors:
            raise PdfStructuralRowWindowError(
                "pdf_structural_window_input_invalid"
            )
        construction = _object(parser_observation.get("candidate_construction"))
        candidates = _dicts(parser_observation.get("candidates"))
        if len(candidates) > self.config.maximum_table_atoms:
            raise PdfStructuralRowWindowError(
                "pdf_structural_window_atom_budget_exceeded"
            )
        if (
            construction.get("kind") != "raw_word_atoms"
            or construction.get("semantic_grid_dependency") is not False
            or not candidates
        ):
            raise PdfStructuralRowWindowError(
                "pdf_structural_window_input_invalid"
            )
        return (
            "whole_table"
            if len(candidates) <= self.config.whole_table_maximum_atoms
            else "vertical_atom_windows"
        )

    def plan(self, parser_observation: dict[str, Any]) -> dict[str, Any]:
        if self.execution_mode(parser_observation) != "vertical_atom_windows":
            raise PdfStructuralRowWindowError(
                "pdf_structural_window_mode_invalid"
            )
        table_bbox = _bbox(
            _object(parser_observation.get("coordinate_space")).get(
                "table_bbox"
            )
        )
        if table_bbox is None:
            raise PdfStructuralRowWindowError(
                "pdf_structural_window_input_invalid"
            )
        candidates = {
            str(item.get("candidate_id") or ""): item
            for item in _dicts(parser_observation.get("candidates"))
        }
        candidate_order = [
            str(item) for item in parser_observation.get("candidate_order") or []
        ]
        if (
            not candidate_order
            or len(candidate_order) != len(candidates)
            or set(candidate_order) != set(candidates)
        ):
            raise PdfStructuralRowWindowError(
                "pdf_structural_window_candidate_ownership_invalid"
            )

        ordered_intervals: list[dict[str, Any]] = []
        for candidate_id in candidate_order:
            candidate = candidates[candidate_id]
            bbox = _bbox(candidate.get("bbox"))
            if bbox is None or not _inside(bbox, table_bbox):
                raise PdfStructuralRowWindowError(
                    "pdf_structural_window_input_invalid"
                )
            ordered_intervals.append(
                {
                    "candidate_id": candidate_id,
                    "source_order": int(candidate.get("source_order") or 0),
                    "bbox": bbox,
                }
            )
        ordered_intervals.sort(
            key=lambda item: (
                item["bbox"][1],
                item["bbox"][3],
                item["bbox"][0],
                item["source_order"],
                item["candidate_id"],
            )
        )
        bands: list[dict[str, Any]] = []
        epsilon = self.config.band_overlap_epsilon_points
        for item in ordered_intervals:
            top = item["bbox"][1]
            bottom = item["bbox"][3]
            if not bands or top > bands[-1]["bottom"] + epsilon:
                bands.append(
                    {
                        "top": top,
                        "bottom": bottom,
                        "candidate_ids": [item["candidate_id"]],
                    }
                )
            else:
                bands[-1]["bottom"] = max(bands[-1]["bottom"], bottom)
                bands[-1]["candidate_ids"].append(item["candidate_id"])
        if any(
            len(band["candidate_ids"])
            > self.config.maximum_owner_atoms_per_window
            for band in bands
        ):
            raise PdfStructuralRowWindowError(
                "pdf_structural_window_owner_band_budget_exceeded"
            )

        packed: list[tuple[int, int]] = []
        start = 0
        owner_count = 0
        for band_index, band in enumerate(bands):
            band_count = len(band["candidate_ids"])
            if owner_count and (
                owner_count + band_count
                > self.config.maximum_owner_atoms_per_window
            ):
                packed.append((start, band_index - 1))
                start = band_index
                owner_count = 0
            owner_count += band_count
        packed.append((start, len(bands) - 1))
        if not 2 <= len(packed) <= self.config.maximum_windows:
            raise PdfStructuralRowWindowError(
                "pdf_structural_window_count_invalid"
            )

        cuts: list[float] = []
        for left, right in zip(packed, packed[1:]):
            left_bottom = float(bands[left[1]]["bottom"])
            right_top = float(bands[right[0]]["top"])
            if right_top - left_bottom <= epsilon:
                raise PdfStructuralRowWindowError(
                    "pdf_structural_window_safe_cut_unavailable"
                )
            cuts.append(round((left_bottom + right_top) / 2.0, 9))

        order_index = {
            candidate_id: index for index, candidate_id in enumerate(candidate_order)
        }
        table_width = table_bbox[2] - table_bbox[0]
        table_height = table_bbox[3] - table_bbox[1]
        if table_width <= 0.0 or table_height <= 0.0:
            raise PdfStructuralRowWindowError(
                "pdf_structural_window_input_invalid"
            )
        windows: list[dict[str, Any]] = []
        for window_offset, (band_start, band_end) in enumerate(packed):
            core_top = table_bbox[1] if window_offset == 0 else cuts[window_offset - 1]
            core_bottom = (
                table_bbox[3]
                if window_offset == len(packed) - 1
                else cuts[window_offset]
            )
            context_start = max(0, band_start - 1)
            context_end = min(len(bands) - 1, band_end + 1)
            crop_top = table_bbox[1] if window_offset == 0 else bands[context_start]["top"]
            crop_bottom = (
                table_bbox[3]
                if window_offset == len(packed) - 1
                else bands[context_end]["bottom"]
            )
            if not crop_top <= core_top < core_bottom <= crop_bottom:
                raise PdfStructuralRowWindowError(
                    "pdf_structural_window_safe_cut_unavailable"
                )
            owner_ids = [
                candidate_id
                for band in bands[band_start : band_end + 1]
                for candidate_id in band["candidate_ids"]
            ]
            owner_ids.sort(key=order_index.__getitem__)
            crop_height = crop_bottom - crop_top
            if (
                not owner_ids
                or len(owner_ids) > self.config.maximum_owner_atoms_per_window
                or crop_height <= 0.0
            ):
                raise PdfStructuralRowWindowError(
                    "pdf_structural_window_candidate_ownership_invalid"
                )
            core_bbox = [table_bbox[0], core_top, table_bbox[2], core_bottom]
            crop_bbox = [table_bbox[0], crop_top, table_bbox[2], crop_bottom]
            window_id = "pdfstructwin_" + stable_digest(
                [
                    parser_observation.get("observation_checksum"),
                    window_offset + 1,
                    owner_ids,
                    core_bbox,
                    crop_bbox,
                    self.config.policy_version,
                ],
                length=24,
            )
            windows.append(
                {
                    "window_id": window_id,
                    "window_index": window_offset + 1,
                    "owner_candidate_ids": owner_ids,
                    "owner_atom_count": len(owner_ids),
                    "source_band_start": band_start + 1,
                    "source_band_end": band_end + 1,
                    "core_bbox": _rounded_bbox(core_bbox),
                    "crop_bbox": _rounded_bbox(crop_bbox),
                    "core_y_normalized_in_table": [
                        _unit((core_top - table_bbox[1]) / table_height),
                        _unit((core_bottom - table_bbox[1]) / table_height),
                    ],
                    "core_y_normalized_in_crop": [
                        _unit((core_top - crop_top) / crop_height),
                        _unit((core_bottom - crop_top) / crop_height),
                    ],
                    "full_width": True,
                    "column_splitting_used": False,
                }
            )
        result = {
            "schema_version": PDF_STRUCTURAL_ROW_WINDOW_PLAN_SCHEMA,
            "policy_version": self.config.policy_version,
            "policy_configuration_hash": sha256_json(asdict(self.config)),
            "mode": "vertical_atom_windows",
            "parser_observation_id": parser_observation.get("observation_id"),
            "parser_observation_checksum": parser_observation.get(
                "observation_checksum"
            ),
            "table_bbox": _rounded_bbox(table_bbox),
            "candidate_atoms": len(candidate_order),
            "maximum_owner_atoms_per_window": (
                self.config.maximum_owner_atoms_per_window
            ),
            "window_count": len(windows),
            "windows": windows,
            "candidate_ownership_exact": True,
            "column_splitting_used": False,
            "legacy_grid_consumed": False,
        }
        result["plan_hash"] = sha256_json(result)
        errors = self.validate_plan(
            parser_observation=parser_observation,
            plan=result,
        )
        if errors:
            raise PdfStructuralRowWindowError(errors[0])
        return result

    def validate_plan(
        self,
        *,
        parser_observation: dict[str, Any],
        plan: Any,
    ) -> list[str]:
        errors = self.validate_plan_integrity(plan)
        data = _object(plan)
        if self.contracts.validate_parser_observation(parser_observation):
            errors.append("pdf_structural_window_input_invalid")
            return sorted(set(errors))
        candidate_order = [
            str(item) for item in parser_observation.get("candidate_order") or []
        ]
        candidate_by_id = {
            str(item.get("candidate_id") or ""): item
            for item in _dicts(parser_observation.get("candidates"))
        }
        owned = [
            str(candidate_id)
            for window in _dicts(data.get("windows"))
            for candidate_id in window.get("owner_candidate_ids") or []
        ]
        if (
            data.get("parser_observation_id")
            != parser_observation.get("observation_id")
            or data.get("parser_observation_checksum")
            != parser_observation.get("observation_checksum")
            or data.get("candidate_atoms") != len(candidate_order)
            or owned != candidate_order
            or len(owned) != len(set(owned))
        ):
            errors.append("pdf_structural_window_candidate_ownership_invalid")
        for window in _dicts(data.get("windows")):
            core = _bbox(window.get("core_bbox"))
            if core is None:
                continue
            for candidate_id in window.get("owner_candidate_ids") or []:
                candidate_bbox = _bbox(
                    _object(candidate_by_id.get(str(candidate_id))).get("bbox")
                )
                if (
                    candidate_bbox is None
                    or candidate_bbox[1] < core[1]
                    or candidate_bbox[3] > core[3]
                ):
                    errors.append(
                        "pdf_structural_window_safe_cut_unavailable"
                    )
                    break
        return sorted(set(errors))

    def validate_plan_integrity(self, plan: Any) -> list[str]:
        data = _object(plan)
        errors: list[str] = []
        if set(data) != _PLAN_KEYS:
            return ["pdf_structural_window_plan_keys_invalid"]
        if (
            data.get("schema_version") != PDF_STRUCTURAL_ROW_WINDOW_PLAN_SCHEMA
            or data.get("policy_version") != self.config.policy_version
            or data.get("policy_configuration_hash")
            != sha256_json(asdict(self.config))
            or data.get("mode") != "vertical_atom_windows"
            or data.get("candidate_ownership_exact") is not True
            or data.get("column_splitting_used") is not False
            or data.get("legacy_grid_consumed") is not False
        ):
            errors.append("pdf_structural_window_plan_identity_invalid")
        table_bbox = _bbox(data.get("table_bbox"))
        windows = _dicts(data.get("windows"))
        if (
            table_bbox is None
            or not isinstance(data.get("windows"), list)
            or len(windows) != data.get("window_count")
            or not 2 <= len(windows) <= self.config.maximum_windows
        ):
            errors.append("pdf_structural_window_count_invalid")
        prior_core_end: float | None = None
        owned: list[str] = []
        for index, window in enumerate(windows, start=1):
            core = _bbox(window.get("core_bbox"))
            crop = _bbox(window.get("crop_bbox"))
            owner_ids = window.get("owner_candidate_ids")
            if (
                set(window) != _WINDOW_KEYS
                or window.get("window_index") != index
                or not isinstance(window.get("window_id"), str)
                or not window.get("window_id")
                or not isinstance(owner_ids, list)
                or not owner_ids
                or not all(isinstance(item, str) and item for item in owner_ids)
                or len(owner_ids) != window.get("owner_atom_count")
                or len(owner_ids) > self.config.maximum_owner_atoms_per_window
                or core is None
                or crop is None
                or table_bbox is None
                or core[0] != table_bbox[0]
                or core[2] != table_bbox[2]
                or crop[0] != table_bbox[0]
                or crop[2] != table_bbox[2]
                or not crop[1] <= core[1] < core[3] <= crop[3]
                or window.get("full_width") is not True
                or window.get("column_splitting_used") is not False
            ):
                errors.append("pdf_structural_window_contract_invalid")
                continue
            if prior_core_end is not None and core[1] != prior_core_end:
                errors.append("pdf_structural_window_boundary_ambiguity")
            prior_core_end = core[3]
            owned.extend(owner_ids)
        if table_bbox is not None and windows:
            first_core = _bbox(windows[0].get("core_bbox"))
            last_core = _bbox(windows[-1].get("core_bbox"))
            if (
                first_core is None
                or last_core is None
                or first_core[1] != table_bbox[1]
                or last_core[3] != table_bbox[3]
            ):
                errors.append("pdf_structural_window_boundary_ambiguity")
        if (
            len(owned) != data.get("candidate_atoms")
            or len(owned) != len(set(owned))
        ):
            errors.append("pdf_structural_window_candidate_ownership_invalid")
        unsigned = dict(data)
        stored = unsigned.pop("plan_hash", None)
        if stored != sha256_json(unsigned):
            errors.append("pdf_structural_window_plan_hash_invalid")
        return sorted(set(errors))

    def stitch_attempt(
        self,
        *,
        plan: dict[str, Any],
        full_package_id: str,
        window_packages: list[dict[str, Any]],
        topology_responses: list[dict[str, Any]],
        window_attempt_ids: list[str],
        attempt_number: int,
    ) -> dict[str, Any]:
        plan_errors = self.validate_plan_integrity(plan)
        windows = _dicts(plan.get("windows"))
        if (
            plan_errors
            or not isinstance(full_package_id, str)
            or not full_package_id
            or not isinstance(attempt_number, int)
            or isinstance(attempt_number, bool)
            or attempt_number not in {1, 2}
            or len(window_packages) != len(windows)
            or len(topology_responses) != len(windows)
            or len(window_attempt_ids) != len(windows)
            or len(window_attempt_ids) != len(set(window_attempt_ids))
            or any(
                not isinstance(item, str)
                or not item
                or not item.endswith(f"_a{attempt_number}")
                for item in window_attempt_ids
            )
        ):
            raise PdfStructuralRowWindowError(
                plan_errors[0]
                if plan_errors
                else "pdf_structural_window_stitch_input_invalid"
            )
        hypotheses_by_window: list[list[dict[str, Any]]] = []
        package_ids: list[str] = []
        response_checksums: list[str] = []
        for window, package, response in zip(
            windows, window_packages, topology_responses
        ):
            identity = _object(package.get("window_identity"))
            package_id = str(package.get("package_id") or "")
            if (
                identity.get("window_id") != window.get("window_id")
                or package.get("window_plan_hash") != plan.get("plan_hash")
                or not package_id
                or response.get("package_id") != package_id
                or response.get("alternatives_complete") is not True
                or response.get("decision") == "unsupported"
            ):
                raise PdfStructuralRowWindowError(
                    "pdf_structural_window_response_invalid"
                )
            hypotheses = _dicts(response.get("hypotheses"))
            if not hypotheses:
                raise PdfStructuralRowWindowError(
                    "pdf_structural_window_response_invalid"
                )
            hypotheses_by_window.append(hypotheses)
            package_ids.append(package_id)
            response_checksums.append(sha256_json(response))
        combination_count = math.prod(len(items) for items in hypotheses_by_window)
        if combination_count > self.config.maximum_alternative_combinations:
            raise PdfStructuralRowWindowError(
                "pdf_structural_window_alternative_ambiguity"
            )

        stitched: dict[str, dict[str, Any]] = {}
        incompatibilities: set[str] = set()
        for combination in itertools.product(*hypotheses_by_window):
            try:
                hypothesis = self._stitch_hypothesis(
                    windows=windows,
                    combination=list(combination),
                )
            except PdfStructuralRowWindowError as exc:
                incompatibilities.add(exc.code)
                continue
            topology_key = sha256_json(
                {
                    key: hypothesis[key]
                    for key in (
                        "row_boundaries",
                        "column_boundaries",
                        "header_row_count",
                        "spans",
                        "header_hierarchy",
                        "continuation_required",
                        "uncertainty_codes",
                    )
                }
            )
            stitched.setdefault(topology_key, hypothesis)
            if len(stitched) > self.config.maximum_stitched_hypotheses:
                raise PdfStructuralRowWindowError(
                    "pdf_structural_window_alternative_ambiguity"
                )
        if not stitched:
            for code in (
                "pdf_structural_window_span_ambiguity",
                "pdf_structural_window_column_ambiguity",
                "pdf_structural_window_boundary_ambiguity",
            ):
                if code in incompatibilities:
                    raise PdfStructuralRowWindowError(code)
            raise PdfStructuralRowWindowError(
                "pdf_structural_window_alternative_ambiguity"
            )
        stitched_hypotheses = []
        for index, (_, hypothesis) in enumerate(sorted(stitched.items()), start=1):
            hypothesis["hypothesis_key"] = (
                f"stitched_a{attempt_number}_h{index:03d}"
            )
            stitched_hypotheses.append(hypothesis)
        stitched_response = {
            "schema_version": "broker_reports_pdf_visual_topology_response_v1",
            "package_id": full_package_id,
            "decision": "bound" if len(stitched_hypotheses) == 1 else "ambiguous",
            "alternatives_complete": True,
            "hypotheses": stitched_hypotheses,
            "uncertainty_codes": [],
        }
        attempt_ids_checksum = sha256_json(window_attempt_ids)
        composite_attempt_id = "pdfstructstitchattempt_" + stable_digest(
            [
                plan.get("plan_hash"),
                full_package_id,
                attempt_number,
                window_attempt_ids,
                attempt_ids_checksum,
            ],
            length=24,
        )
        result = {
            "schema_version": PDF_STRUCTURAL_ROW_WINDOW_STITCH_SCHEMA,
            "policy_version": self.config.policy_version,
            "policy_configuration_hash": sha256_json(asdict(self.config)),
            "attempt_number": attempt_number,
            "plan_hash": plan.get("plan_hash"),
            "full_package_id": full_package_id,
            "window_package_ids": package_ids,
            "window_response_checksums": response_checksums,
            "window_attempt_ids": copy.deepcopy(window_attempt_ids),
            "window_attempt_ids_checksum": attempt_ids_checksum,
            "composite_attempt_id": composite_attempt_id,
            "window_count": len(windows),
            "candidate_ownership_exact": True,
            "attempts_mixed": False,
            "column_splitting_used": False,
            "stitched_response": stitched_response,
        }
        result["stitch_hash"] = sha256_json(result)
        errors = self.validate_stitch(result)
        if errors:
            raise PdfStructuralRowWindowError(errors[0])
        return result

    def validate_stitch(self, value: Any) -> list[str]:
        data = _object(value)
        errors: list[str] = []
        if set(data) != _STITCH_KEYS:
            return ["pdf_structural_window_stitch_keys_invalid"]
        if (
            data.get("schema_version") != PDF_STRUCTURAL_ROW_WINDOW_STITCH_SCHEMA
            or data.get("policy_version") != self.config.policy_version
            or data.get("policy_configuration_hash")
            != sha256_json(asdict(self.config))
            or data.get("attempt_number") not in {1, 2}
            or data.get("candidate_ownership_exact") is not True
            or data.get("attempts_mixed") is not False
            or data.get("column_splitting_used") is not False
        ):
            errors.append("pdf_structural_window_stitch_identity_invalid")
        packages = data.get("window_package_ids")
        responses = data.get("window_response_checksums")
        attempt_ids = data.get("window_attempt_ids")
        if (
            not isinstance(packages, list)
            or not isinstance(responses, list)
            or len(packages) != data.get("window_count")
            or len(responses) != data.get("window_count")
            or len(packages) < 2
            or not all(isinstance(item, str) and item for item in packages)
            or not all(isinstance(item, str) and item for item in responses)
            or not isinstance(attempt_ids, list)
            or len(attempt_ids) != data.get("window_count")
            or len(attempt_ids) != len(set(attempt_ids))
            or not all(
                isinstance(item, str)
                and item.endswith(f"_a{data.get('attempt_number')}")
                for item in attempt_ids
            )
            or data.get("window_attempt_ids_checksum")
            != sha256_json(attempt_ids if isinstance(attempt_ids, list) else [])
            or data.get("composite_attempt_id")
            != "pdfstructstitchattempt_"
            + stable_digest(
                [
                    data.get("plan_hash"),
                    data.get("full_package_id"),
                    data.get("attempt_number"),
                    attempt_ids,
                    data.get("window_attempt_ids_checksum"),
                ],
                length=24,
            )
        ):
            errors.append("pdf_structural_window_stitch_lineage_invalid")
        unsigned = dict(data)
        stored = unsigned.pop("stitch_hash", None)
        if stored != sha256_json(unsigned):
            errors.append("pdf_structural_window_stitch_hash_invalid")
        return sorted(set(errors))

    def _stitch_hypothesis(
        self,
        *,
        windows: list[dict[str, Any]],
        combination: list[dict[str, Any]],
    ) -> dict[str, Any]:
        tolerance = self.config.boundary_tolerance
        columns_by_window = [
            [round(float(value), 9) for value in item.get("column_boundaries") or []]
            for item in combination
        ]
        if any(
            len(columns) != len(columns_by_window[0])
            or any(
                abs(left - right) > tolerance
                for left, right in zip(columns, columns_by_window[0])
            )
            for columns in columns_by_window[1:]
        ):
            raise PdfStructuralRowWindowError(
                "pdf_structural_window_column_ambiguity"
            )
        columns = [
            round(
                sum(values) / len(values),
                9,
            )
            for values in zip(*columns_by_window)
        ]
        columns[0] = 0.0
        columns[-1] = 1.0
        if any(left >= right for left, right in zip(columns, columns[1:])):
            raise PdfStructuralRowWindowError(
                "pdf_structural_window_column_ambiguity"
            )

        mapped_rows: list[list[float]] = []
        for window, hypothesis in zip(windows, combination):
            crop = [float(value) for value in window["crop_bbox"]]
            table_height = float(windows[-1]["core_bbox"][3]) - float(
                windows[0]["core_bbox"][1]
            )
            table_top = float(windows[0]["core_bbox"][1])
            if table_height <= 0.0:
                raise PdfStructuralRowWindowError(
                    "pdf_structural_window_boundary_ambiguity"
                )
            rows = [
                round(
                    (crop[1] + float(value) * (crop[3] - crop[1]) - table_top)
                    / table_height,
                    9,
                )
                for value in hypothesis.get("row_boundaries") or []
            ]
            if len(rows) < 2 or any(
                left >= right for left, right in zip(rows, rows[1:])
            ):
                raise PdfStructuralRowWindowError(
                    "pdf_structural_window_boundary_ambiguity"
                )
            mapped_rows.append(rows)
        for boundary_index in range(1, len(windows)):
            cut = float(windows[boundary_index]["core_y_normalized_in_table"][0])
            if any(
                not any(abs(value - cut) <= tolerance for value in rows)
                for rows in (
                    mapped_rows[boundary_index - 1],
                    mapped_rows[boundary_index],
                )
            ):
                raise PdfStructuralRowWindowError(
                    "pdf_structural_window_boundary_ambiguity"
                )

        global_rows: list[float] = [0.0, 1.0]
        for window, rows in zip(windows, mapped_rows):
            core_start, core_end = [
                float(value) for value in window["core_y_normalized_in_table"]
            ]
            if (
                not any(abs(value - core_start) <= tolerance for value in rows)
                or not any(abs(value - core_end) <= tolerance for value in rows)
            ):
                raise PdfStructuralRowWindowError(
                    "pdf_structural_window_boundary_ambiguity"
                )
            global_rows.extend(
                value
                for value in rows
                if core_start + tolerance < value < core_end - tolerance
            )
            global_rows.extend((core_start, core_end))
        rows = _dedupe_boundaries(global_rows, tolerance=tolerance)
        rows[0] = 0.0
        rows[-1] = 1.0
        if len(rows) > 65 or any(
            left >= right for left, right in zip(rows, rows[1:])
        ):
            raise PdfStructuralRowWindowError(
                "pdf_structural_window_boundary_ambiguity"
            )

        if any(
            int(item.get("header_row_count") or 0) != 0
            for item in combination[1:]
        ):
            raise PdfStructuralRowWindowError(
                "pdf_structural_window_span_ambiguity"
            )
        first_header_count = int(combination[0].get("header_row_count") or 0)
        first_mapped = mapped_rows[0]
        if first_header_count >= len(first_mapped):
            raise PdfStructuralRowWindowError(
                "pdf_structural_window_span_ambiguity"
            )
        header_bottom = first_mapped[first_header_count]
        first_core_end = float(windows[0]["core_y_normalized_in_table"][1])
        if header_bottom > first_core_end + tolerance:
            raise PdfStructuralRowWindowError(
                "pdf_structural_window_span_ambiguity"
            )
        header_row_count = _boundary_index(
            rows,
            header_bottom,
            tolerance=tolerance,
        )

        spans: list[dict[str, Any]] = []
        for window, hypothesis, local_rows in zip(
            windows, combination, mapped_rows
        ):
            core_start, core_end = [
                float(value) for value in window["core_y_normalized_in_table"]
            ]
            for span in _dicts(hypothesis.get("spans")):
                start_row = int(span.get("start_row") or 0)
                end_row = int(span.get("end_row") or 0)
                if (
                    start_row < 1
                    or end_row < start_row
                    or end_row >= len(local_rows)
                ):
                    raise PdfStructuralRowWindowError(
                        "pdf_structural_window_span_ambiguity"
                    )
                top = local_rows[start_row - 1]
                bottom = local_rows[end_row]
                overlaps_core = bottom > core_start + tolerance and top < core_end - tolerance
                inside_core = top >= core_start - tolerance and bottom <= core_end + tolerance
                if overlaps_core and not inside_core:
                    raise PdfStructuralRowWindowError(
                        "pdf_structural_window_span_ambiguity"
                    )
                if not inside_core:
                    continue
                global_start = _boundary_index(rows, top, tolerance=tolerance) + 1
                global_end = _boundary_index(rows, bottom, tolerance=tolerance)
                spans.append(
                    {
                        "start_row": global_start,
                        "end_row": global_end,
                        "start_column": int(span.get("start_column") or 0),
                        "end_column": int(span.get("end_column") or 0),
                        "relation": span.get("relation"),
                    }
                )
        spans = _unique_dicts(spans)

        hierarchy: list[dict[str, Any]] = []
        first_rows = mapped_rows[0]
        for relation in _dicts(combination[0].get("header_hierarchy")):
            parent_row = int(relation.get("parent_row") or 0)
            if parent_row < 1 or parent_row >= len(first_rows):
                raise PdfStructuralRowWindowError(
                    "pdf_structural_window_span_ambiguity"
                )
            top = first_rows[parent_row - 1]
            bottom = first_rows[parent_row]
            if bottom > first_core_end + tolerance:
                raise PdfStructuralRowWindowError(
                    "pdf_structural_window_span_ambiguity"
                )
            hierarchy.append(
                {
                    "parent_row": _boundary_index(
                        rows, top, tolerance=tolerance
                    )
                    + 1,
                    "parent_column": int(relation.get("parent_column") or 0),
                    "child_start_column": int(
                        relation.get("child_start_column") or 0
                    ),
                    "child_end_column": int(
                        relation.get("child_end_column") or 0
                    ),
                }
            )
        return {
            "hypothesis_key": "stitched_pending",
            "row_boundaries": rows,
            "column_boundaries": columns,
            "header_row_count": header_row_count,
            "spans": spans,
            "header_hierarchy": _unique_dicts(hierarchy),
            "continuation_required": False,
            "uncertainty_codes": [],
        }


def _boundary_index(
    boundaries: list[float], value: float, *, tolerance: float
) -> int:
    matches = [
        index
        for index, boundary in enumerate(boundaries)
        if abs(boundary - value) <= tolerance
    ]
    if len(matches) != 1:
        raise PdfStructuralRowWindowError(
            "pdf_structural_window_boundary_ambiguity"
        )
    return matches[0]


def _dedupe_boundaries(values: list[float], *, tolerance: float) -> list[float]:
    result: list[float] = []
    for value in sorted(round(float(item), 9) for item in values):
        if not result or value - result[-1] > tolerance:
            result.append(value)
        elif abs(value) < abs(result[-1]) or abs(value - 1.0) < abs(result[-1] - 1.0):
            result[-1] = value
    return result


def _unique_dicts(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for value in values:
        unique.setdefault(sha256_json(value), copy.deepcopy(value))
    return [unique[key] for key in sorted(unique)]


def _inside(bbox: list[float], outer: list[float]) -> bool:
    return (
        outer[0] <= bbox[0] < bbox[2] <= outer[2]
        and outer[1] <= bbox[1] < bbox[3] <= outer[3]
    )


def _bbox(value: Any) -> list[float] | None:
    if (
        not isinstance(value, (list, tuple))
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
    if result[0] >= result[2] or result[1] >= result[3]:
        return None
    return result


def _rounded_bbox(value: list[float]) -> list[float]:
    return [round(float(item), 9) for item in value]


def _unit(value: float) -> float:
    if -1e-9 <= value <= 0.0:
        return 0.0
    if 1.0 <= value <= 1.0 + 1e-9:
        return 1.0
    if not 0.0 <= value <= 1.0:
        raise PdfStructuralRowWindowError(
            "pdf_structural_window_boundary_ambiguity"
        )
    return round(value, 9)


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
