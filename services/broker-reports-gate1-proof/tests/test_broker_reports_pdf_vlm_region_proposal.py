from __future__ import annotations

import copy
import math
import unittest

from broker_reports_gate1.pdf_dual_oracle_contracts import (
    PdfDualOracleContractFactory,
)
from broker_reports_gate1.pdf_hybrid_contracts import sha256_json
from broker_reports_gate1.pdf_visual_topology import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    PDF_VISUAL_TOPOLOGY_REQUEST_SCHEMA,
    PDF_VISUAL_TOPOLOGY_REGION_PROPOSAL_REVISION,
    PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
    PdfVisualTopologyError,
    PdfVisualTopologyFactory,
)


class PdfVlmRegionProposalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = PdfVisualTopologyFactory().create()
        self.crop = _crop_manifest()
        self.observation = _observation()

    def test_factory_contract_names_the_bounded_text_exposure(self) -> None:
        self.assertIn("bounded region-proposal", FACTORY_REQUIRED)
        self.assertIn("candidate-crop region proposals", FORBIDDEN)
        self.assertIn("must not expose source refs", FORBIDDEN)
        self.assertIn("must not expose", FORBIDDEN)

    def test_candidate_crop_package_has_one_region_limit_and_exact_anonymous_words(
        self,
    ) -> None:
        package = self.runtime.build_region_proposal_package(
            proposal_scope="candidate_crop",
            parser_observation=self.observation,
            crop_manifest=self.crop,
        )

        model = package["model_facing"]
        self.assertEqual(PDF_VISUAL_TOPOLOGY_REQUEST_SCHEMA, model["schema_version"])
        self.assertEqual("candidate_crop", model["proposal_scope"])
        self.assertEqual(1, model["output_limits"]["maximum_regions"])
        self.assertEqual(4, package["component_accounting"]["atom_count"])
        self.assertLessEqual(
            package["component_accounting"]["atom_count"],
            package["component_accounting"]["maximum_atoms"],
        )
        self.assertLessEqual(
            package["component_accounting"]["model_json_bytes"], 48 * 1024
        )
        self.assertTrue(
            all(
                set(atom) == {"atom_id", "bbox", "order", "text"}
                for atom in model["atoms"]
            )
        )
        self.assertEqual(
            [
                "alpha-private",
                "beta-private",
                "gamma-private",
                "delta-private",
            ],
            [atom["text"] for atom in model["atoms"]],
        )
        rendered = repr(model)
        self.assertEqual(
            {"package_id": package["package_id"]}, model["identity"]
        )
        self.assertIn("alpha-private", rendered)
        self.assertNotIn(package["crop_identity"]["crop_sha256"], rendered)
        self.assertNotIn(package["neutral_atom_manifest_hash"], rendered)
        self.assertNotIn("source-1", rendered)
        self.assertNotIn("word-1", rendered)
        self.assertNotIn("checksum-1", rendered)
        self.assertTrue(package["source_values_exposed_to_model_view"])
        self.assertEqual(
            "immutable_pdf_word_atoms_with_exact_text_plus_exact_crop",
            package["source_authority"],
        )
        self.assertTrue(model["rules"]["exact_source_word_text_available"])
        self.assertFalse(
            model["rules"]["exact_source_word_text_may_be_returned"]
        )
        for candidate_id in package["neutral_atom_to_candidate_id"].values():
            self.assertNotIn(candidate_id, rendered)
        self.assertEqual([], self.runtime.validate_region_proposal_package(package))

    def test_legacy_package_keeps_value_free_three_field_atoms(self) -> None:
        package = self.runtime.build_package(
            parser_observation=self.observation,
            crop_manifest=self.crop,
        )

        atoms = package["model_facing"]["atoms"]
        self.assertTrue(
            all(set(atom) == {"atom_id", "bbox", "order"} for atom in atoms)
        )
        self.assertNotIn("alpha-private", repr(package["model_facing"]))
        self.assertFalse(package["source_values_exposed_to_model_view"])

    def test_page_level_package_has_no_atoms_and_two_region_limit(self) -> None:
        package = self.runtime.build_region_proposal_package(
            proposal_scope="page_level",
            crop_manifest=self.crop,
        )

        model = package["model_facing"]
        self.assertEqual([], model["atoms"])
        self.assertEqual(0, package["component_accounting"]["atom_count"])
        self.assertEqual(2, model["output_limits"]["maximum_regions"])
        self.assertEqual(
            2,
            package["output_schema"]["properties"]["regions"]["maxItems"],
        )
        self.assertLessEqual(
            package["component_accounting"]["static_input_token_estimate"],
            package["component_accounting"]["maximum_counted_input_tokens"],
        )
        self.assertEqual(
            20_000,
            package["component_accounting"]["maximum_counted_input_tokens"],
        )
        self.assertFalse(package["source_values_exposed_to_model_view"])
        self.assertFalse(model["rules"]["exact_source_word_text_available"])
        self.assertEqual([], self.runtime.validate_region_proposal_package(package))

    def test_candidate_atom_text_tampering_is_rejected(self) -> None:
        package = self.runtime.build_region_proposal_package(
            proposal_scope="candidate_crop",
            parser_observation=self.observation,
            crop_manifest=self.crop,
        )
        package["model_facing"]["atoms"][0]["text"] = "invented"
        package.pop("package_hash")
        package["package_hash"] = sha256_json(package)

        self.assertIn(
            "pdf_visual_topology_region_atom_text_derivation_invalid",
            self.runtime.validate_region_proposal_package(package),
        )

    def test_region_atom_schemas_reject_private_fields_and_page_atoms(self) -> None:
        candidate = self.runtime.build_region_proposal_package(
            proposal_scope="candidate_crop",
            parser_observation=self.observation,
            crop_manifest=self.crop,
        )
        candidate["model_facing"]["atoms"][0]["word_ref"] = "word-1"
        candidate.pop("package_hash")
        candidate["package_hash"] = sha256_json(candidate)
        self.assertIn(
            "pdf_visual_topology_region_atom_contract_invalid",
            self.runtime.validate_region_proposal_package(candidate),
        )

        page = self.runtime.build_region_proposal_package(
            proposal_scope="page_level",
            crop_manifest=self.crop,
        )
        page["model_facing"]["atoms"] = [
            {"atom_id": "a0001", "bbox": [0.0, 0.0, 1.0, 1.0], "order": 0}
        ]
        page.pop("package_hash")
        page["package_hash"] = sha256_json(page)
        self.assertIn(
            "pdf_visual_topology_region_page_atoms_forbidden",
            self.runtime.validate_region_proposal_package(page),
        )

    def test_candidate_exact_word_text_still_obeys_48k_model_budget(self) -> None:
        observation = _observation(word_text_size=13_000)

        with self.assertRaisesRegex(
            PdfVisualTopologyError,
            "pdf_visual_topology_model_json_budget_exceeded",
        ):
            self.runtime.build_region_proposal_package(
                proposal_scope="candidate_crop",
                parser_observation=observation,
                crop_manifest=self.crop,
            )

    def test_region_package_rejects_injected_model_fields_even_with_new_hash(
        self,
    ) -> None:
        package = self.runtime.build_region_proposal_package(
            proposal_scope="page_level",
            crop_manifest=self.crop,
        )
        package["model_facing"]["source_text"] = "private"
        package.pop("package_hash")
        package["package_hash"] = sha256_json(package)

        self.assertIn(
            "pdf_visual_topology_region_model_contract_invalid",
            self.runtime.validate_region_proposal_package(package),
        )

    def test_page_level_response_accepts_two_non_overlapping_regions(self) -> None:
        package = self.runtime.build_region_proposal_package(
            proposal_scope="page_level",
            crop_manifest=self.crop,
        )
        response = _proposal_response(
            package["package_id"],
            scope="page_level",
            regions=[
                _region("left_table", [0.05, 0.1, 0.45, 0.9]),
                _region("right_table", [0.55, 0.1, 0.95, 0.9]),
            ],
        )

        parsed = self.runtime.parse_region_proposal_response(
            response,
            expected_package_id=package["package_id"],
            expected_proposal_scope="page_level",
        )

        self.assertEqual("present", parsed["table_presence"])
        self.assertEqual(
            ["left_table", "right_table"],
            [region["region_key"] for region in parsed["regions"]],
        )
        self.assertEqual("alignment_based", parsed["regions"][0]["border_evidence"])
        self.assertEqual("mixed", parsed["regions"][0]["density"])
        self.assertEqual("unlikely", parsed["regions"][0]["continuation_likelihood"])

    def test_page_level_response_rejects_overlap_and_third_region(self) -> None:
        package = self.runtime.build_region_proposal_package(
            proposal_scope="page_level",
            crop_manifest=self.crop,
        )
        overlap = _proposal_response(
            package["package_id"],
            scope="page_level",
            regions=[
                _region("first", [0.05, 0.1, 0.6, 0.9]),
                _region("second", [0.5, 0.2, 0.95, 0.8]),
            ],
        )
        with self.assertRaisesRegex(
            PdfVisualTopologyError, "pdf_visual_topology_region_overlap"
        ):
            self.runtime.parse_region_proposal_response(overlap)

        third = copy.deepcopy(overlap)
        third["regions"] = [
            _region("first", [0.0, 0.0, 0.2, 0.2]),
            _region("second", [0.4, 0.4, 0.6, 0.6]),
            _region("third", [0.8, 0.8, 1.0, 1.0]),
        ]
        with self.assertRaisesRegex(
            PdfVisualTopologyError,
            "pdf_visual_topology_region_collection_invalid",
        ):
            self.runtime.parse_region_proposal_response(third)

    def test_candidate_response_rejects_second_region(self) -> None:
        package = self.runtime.build_region_proposal_package(
            proposal_scope="candidate_crop",
            parser_observation=self.observation,
            crop_manifest=self.crop,
        )
        response = _proposal_response(
            package["package_id"],
            scope="candidate_crop",
            regions=[
                _region("first", [0.0, 0.0, 0.4, 1.0]),
                _region("second", [0.6, 0.0, 1.0, 1.0]),
            ],
        )

        with self.assertRaisesRegex(
            PdfVisualTopologyError,
            "pdf_visual_topology_region_collection_invalid",
        ):
            self.runtime.parse_region_proposal_response(response)

    def test_region_response_cannot_return_source_text(self) -> None:
        package = self.runtime.build_region_proposal_package(
            proposal_scope="candidate_crop",
            parser_observation=self.observation,
            crop_manifest=self.crop,
        )
        response = _proposal_response(
            package["package_id"],
            scope="candidate_crop",
            regions=[_region("candidate", [0.0, 0.0, 1.0, 1.0])],
        )
        response["regions"][0]["source_text"] = "alpha-private"

        with self.assertRaisesRegex(
            PdfVisualTopologyError,
            "pdf_visual_topology_region_keys_invalid",
        ):
            self.runtime.parse_region_proposal_response(response)

    def test_absent_requires_zero_regions_and_uncertain_requires_reason(self) -> None:
        package = self.runtime.build_region_proposal_package(
            proposal_scope="page_level",
            crop_manifest=self.crop,
        )
        absent = _proposal_response(
            package["package_id"],
            scope="page_level",
            presence="absent",
            regions=[],
        )
        self.assertEqual(
            "absent",
            self.runtime.parse_region_proposal_response(absent)["table_presence"],
        )

        invalid_absent = copy.deepcopy(absent)
        invalid_absent["regions"] = [_region("invented", [0.1, 0.1, 0.9, 0.9])]
        with self.assertRaisesRegex(
            PdfVisualTopologyError,
            "pdf_visual_topology_region_absent_contract_invalid",
        ):
            self.runtime.parse_region_proposal_response(invalid_absent)

        uncertain = copy.deepcopy(absent)
        uncertain["table_presence"] = "uncertain"
        with self.assertRaisesRegex(
            PdfVisualTopologyError,
            "pdf_visual_topology_region_uncertain_contract_invalid",
        ):
            self.runtime.parse_region_proposal_response(uncertain)
        uncertain["uncertainty_codes"] = ["possible_borderless_table"]
        self.assertEqual(
            "uncertain",
            self.runtime.parse_region_proposal_response(uncertain)["table_presence"],
        )

    def test_region_bbox_must_be_finite_positive_and_inside_crop(self) -> None:
        package = self.runtime.build_region_proposal_package(
            proposal_scope="candidate_crop",
            parser_observation=self.observation,
            crop_manifest=self.crop,
        )
        response = _proposal_response(
            package["package_id"],
            scope="candidate_crop",
            regions=[_region("candidate", [0.1, 0.1, 0.9, 0.9])],
        )
        for invalid_bbox in (
            [0.1, 0.1, 0.1, 0.9],
            [-0.1, 0.1, 0.9, 0.9],
            [0.1, 0.1, math.inf, 0.9],
        ):
            invalid = copy.deepcopy(response)
            invalid["regions"][0]["bbox"] = invalid_bbox
            with self.subTest(bbox=invalid_bbox), self.assertRaisesRegex(
                PdfVisualTopologyError,
                "pdf_visual_topology_region_bbox_invalid",
            ):
                self.runtime.parse_region_proposal_response(invalid)


def _observation(*, word_text_size: int = 0) -> dict:
    bboxes: list[dict] = []
    words: list[dict] = []
    values = (
        ("alpha-private", [10.0, 10.0, 90.0, 40.0]),
        ("beta-private", [110.0, 10.0, 190.0, 40.0]),
        ("gamma-private", [10.0, 60.0, 90.0, 90.0]),
        ("delta-private", [110.0, 60.0, 190.0, 90.0]),
    )
    if word_text_size:
        values = tuple(
            (f"{text}:{'x' * word_text_size}", bbox) for text, bbox in values
        )
    for ordinal, (text, bbox) in enumerate(values, start=1):
        bbox_ref = f"bbox-{ordinal}"
        bboxes.append({"bbox_ref": bbox_ref, "bbox": bbox})
        words.append(
            {
                "parser_ordinal": ordinal,
                "word_ref": f"word-{ordinal}",
                "page_ref": "page-1",
                "bbox_ref": bbox_ref,
                "text": text,
                "geometry_reading_order": ordinal,
                "text_checksum_ref": f"checksum-{ordinal}",
                "source_value_ref": f"source-{ordinal}",
            }
        )
    projection = {
        "bbox_inventory": bboxes,
        "word_inventory": words,
        "line_inventory": [],
        "vector_line_inventory": [],
        "rect_inventory": [],
    }
    return (
        PdfDualOracleContractFactory()
        .create()
        .build_parser_observation_from_word_atoms(
            document_ref="document-1",
            pdf_sha256="pdf-sha",
            page_ref="page-1",
            page_number=1,
            table_ref="table-1",
            table_bbox=[0.0, 0.0, 200.0, 100.0],
            pdf_text_layer_projection=projection,
        )
    )


def _crop_manifest() -> dict:
    manifest = {
        "schema_version": "broker_reports_pdf_table_crop_v1",
        "policy_version": "pdf_table_raster_policy_v1",
        "crop_id": "crop-1",
        "document_ref": "document-1",
        "pdf_sha256": "pdf-sha",
        "page_ref": "page-1",
        "page_number": 1,
        "table_ref": "table-1",
        "declared_table_bbox": [0.0, 0.0, 200.0, 100.0],
        "rendered_bbox": [0.0, 0.0, 200.0, 100.0],
        "page_rotation": 0,
        "applied_rotation": 0,
        "padding_points": 0.0,
        "dpi": 150,
        "width": 400,
        "height": 200,
        "png_bytes": 100,
        "png_sha256": "crop-sha",
    }
    manifest["manifest_hash"] = sha256_json(manifest)
    return manifest


def _hypothesis(key: str = "primary") -> dict:
    return {
        "hypothesis_key": key,
        "row_boundaries": [0.0, 0.5, 1.0],
        "column_boundaries": [0.0, 0.5, 1.0],
        "header_row_count": 1,
        "spans": [],
        "header_hierarchy": [],
        "continuation_required": False,
        "uncertainty_codes": [],
    }


def _region(key: str, bbox: list[float]) -> dict:
    return {
        "region_key": key,
        "bbox": bbox,
        "border_evidence": "alignment_based",
        "density": "mixed",
        "continuation_likelihood": "unlikely",
        "hypotheses": [_hypothesis()],
        "uncertainty_codes": [],
    }


def _proposal_response(
    package_id: str,
    *,
    scope: str,
    regions: list[dict],
    presence: str = "present",
) -> dict:
    return {
        "schema_version": PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
        "contract_revision": PDF_VISUAL_TOPOLOGY_REGION_PROPOSAL_REVISION,
        "package_id": package_id,
        "proposal_scope": scope,
        "table_presence": presence,
        "alternatives_complete": True,
        "regions": regions,
        "uncertainty_codes": [],
    }


if __name__ == "__main__":
    unittest.main()
