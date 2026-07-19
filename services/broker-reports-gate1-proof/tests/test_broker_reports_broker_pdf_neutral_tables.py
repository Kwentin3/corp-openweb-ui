from __future__ import annotations

import copy
import unittest

from broker_reports_gate1 import (
    BROKER_PDF_NEUTRAL_TABLE_PROFILE_ID,
    FullSourceArtifactFactory,
    Gate2TablePackageFactory,
    NormalizedTableProjectionFactory,
    REGION_DECISION_SCHEMA_VERSION,
    TableProjectionValidator,
    validate_canonical_integrity,
    validate_canonical_neutral_projection,
    validate_region_decision,
)
from broker_reports_gate1.broker_pdf_neutral_tables import (
    FACTORY_REQUIRED,
    FORBIDDEN,
)
from tests.test_broker_reports_table_projection import (
    _broker_profile_ruled_table_pdf,
)
from tests.test_broker_reports_pdf_layout_slice2 import _ruled_table_pdf


class BrokerPdfNeutralTablesTest(unittest.TestCase):
    def _projection(self) -> dict:
        built = (
            FullSourceArtifactFactory()
            .create()
            .build(
                normalization_run_id="neutral_table_run",
                document_id="neutral_table_document",
                profile_id="neutral_table_profile",
                container_format="pdf",
                content_bytes=_broker_profile_ruled_table_pdf(),
                source_checksum_sha256="a" * 64,
            )
        )
        result = (
            NormalizedTableProjectionFactory()
            .create()
            .build_for_document(
                source_format="pdf",
                payloads=built.payloads,
                source_units=built.units,
            )
        )
        self.assertEqual(len(result.projections), 1)
        return result.projections[0]

    def test_factory_profile_is_structural_deterministic_and_model_free(self):
        projection = self._projection()

        self.assertIn("BrokerPdfNeutralTableFactory.create", FACTORY_REQUIRED)
        self.assertIn("must not select", FORBIDDEN)
        self.assertEqual(
            projection["canonical_profile_id"],
            BROKER_PDF_NEUTRAL_TABLE_PROFILE_ID,
        )
        reconstruction = projection["canonical_contract"]["reconstruction"]
        self.assertFalse(reconstruction["provider_or_model_used"])
        self.assertFalse(
            reconstruction["filename_path_id_hash_or_value_allowlist_used"]
        )
        self.assertEqual(projection["validator_status"], "passed")
        self.assertTrue(validate_canonical_integrity(projection))
        self.assertEqual(
            validate_canonical_neutral_projection(projection)["validator_status"],
            "passed",
        )
        package = (
            Gate2TablePackageFactory()
            .create()
            .build(
                projection=projection,
                case_id="neutral-table-case",
            )
        )
        self.assertEqual(
            package["source_unit"]["canonical_table_scope"],
            "ready_validated_projection_only",
        )
        self.assertFalse(package["prompt_contract"]["model_call_performed"])

    def test_out_of_profile_ruled_table_stays_geometry_only_and_gate2_blocked(self):
        built = (
            FullSourceArtifactFactory()
            .create()
            .build(
                normalization_run_id="negative_run",
                document_id="negative_document",
                profile_id="negative_profile",
                container_format="pdf",
                content_bytes=_ruled_table_pdf(),
                source_checksum_sha256="b" * 64,
            )
        )
        result = (
            NormalizedTableProjectionFactory()
            .create()
            .build_for_document(
                source_format="pdf",
                payloads=built.payloads,
                source_units=built.units,
            )
        )
        projection = result.projections[0]

        self.assertNotIn("canonical_contract", projection)
        self.assertEqual(projection["table_candidate_status"], "validated_geometry")
        with self.assertRaisesRegex(
            ValueError, "gate2_pdf_canonical_table_not_validated"
        ):
            Gate2TablePackageFactory().create().build(
                projection=projection,
                case_id="negative-case",
            )

    def test_typed_non_table_decisions_are_non_promoting_and_malformed_promotion_fails(
        self,
    ):
        for region_type in (
            "structured_form_panel",
            "section_heading",
            "material_non_table_region",
            "non_material_region",
            "unknown_or_ambiguous",
        ):
            decision = {
                "schema_version": REGION_DECISION_SCHEMA_VERSION,
                "source_unit_ref": f"unit_{region_type}",
                "document_ref": "document_ref",
                "region_type": region_type,
                "status": "not_promoted",
                "detector_authority": "proposal_only",
                "promotion_authority": None,
            }
            self.assertEqual(
                validate_region_decision(decision)["validator_status"],
                "passed",
            )

        malformed = {
            "schema_version": REGION_DECISION_SCHEMA_VERSION,
            "source_unit_ref": "unit_malformed",
            "document_ref": "document_ref",
            "region_type": "structured_form_panel",
            "status": "canonical_table_accepted",
            "detector_authority": "model_authority",
            "promotion_authority": "model_output",
        }
        validation = validate_region_decision(malformed)
        self.assertEqual(validation["validator_status"], "failed")
        self.assertIn(
            "typed_region_decision_promotion_type_mismatch",
            validation["reason_codes"],
        )
        self.assertIn(
            "typed_region_decision_detector_authority_invalid",
            validation["reason_codes"],
        )

    def test_contract_mutations_fail_specific_deterministic_invariants(self):
        projection = self._projection()
        cases = []

        wrong_parent = copy.deepcopy(projection)
        wrong_parent["canonical_contract"]["provenance"][
            "parent_payload_ref"
        ] = "foreign_parent"
        cases.append(
            (
                "wrong_parent",
                wrong_parent,
                "canonical_neutral_table_provenance_mismatch",
            )
        )

        wrong_page = copy.deepcopy(projection)
        wrong_page["canonical_contract"]["contributing_page_refs"] = ["foreign_page"]
        cases.append(
            (
                "wrong_page",
                wrong_page,
                "canonical_neutral_table_source_membership_mismatch",
            )
        )

        clipped_row = copy.deepcopy(projection)
        clipped_row["rows"].pop()
        cases.append(
            (
                "clipped_final_row",
                clipped_row,
                "canonical_neutral_table_row_order_invalid",
            )
        )

        missing_total = copy.deepcopy(projection)
        self.assertTrue(missing_total["canonical_contract"]["total_row_refs"])
        missing_total["canonical_contract"]["total_row_refs"] = []
        cases.append(
            (
                "missing_total",
                missing_total,
                "canonical_neutral_table_total_row_inventory_invalid",
            )
        )

        reordered_columns = copy.deepcopy(projection)
        reordered_columns["column_refs"] = list(
            reversed(reordered_columns["column_refs"])
        )
        cases.append(
            (
                "reordered_columns",
                reordered_columns,
                "canonical_neutral_table_column_order_invalid",
            )
        )

        wrong_header = copy.deepcopy(projection)
        wrong_header["header_model"]["column_labels"][0][
            "column_ref"
        ] = "foreign_column"
        cases.append(
            (
                "incorrect_header",
                wrong_header,
                "canonical_neutral_table_header_column_mapping_invalid",
            )
        )

        ambiguous_merge = copy.deepcopy(projection)
        ambiguous_merge["cells"][0]["ambiguous_cell_boundary"] = True
        cases.append(
            (
                "merged_cell_ambiguity",
                ambiguous_merge,
                "canonical_neutral_table_cell_ambiguity_unresolved",
            )
        )

        wrong_continuation = copy.deepcopy(projection)
        wrong_continuation["canonical_contract"]["continuation"]["fragment_order"] = 2
        cases.append(
            (
                "wrong_continuation_order",
                wrong_continuation,
                "canonical_neutral_table_continuation_order_invalid",
            )
        )

        repeated_header_as_data = copy.deepcopy(projection)
        ordinal_ref = repeated_header_as_data["canonical_contract"]["header_hierarchy"][
            "ordinal_marker_row_ref"
        ]
        ordinal_row = next(
            row
            for row in repeated_header_as_data["rows"]
            if row["row_ref"] == ordinal_ref
        )
        ordinal_row["canonical_structural_role"] = "data_row"
        cases.append(
            (
                "ordinal_header_as_data",
                repeated_header_as_data,
                "canonical_neutral_table_ordinal_header_invalid",
            )
        )

        missing_source_object = copy.deepcopy(projection)
        missing_source_object["canonical_contract"]["source_accounting"][
            "cell_owned_word_refs"
        ].pop()
        cases.append(
            (
                "missing_source_object",
                missing_source_object,
                "canonical_neutral_table_region_membership_incomplete",
            )
        )

        duplicate_source = copy.deepcopy(projection)
        duplicate_source["source_value_index"].append(
            copy.deepcopy(duplicate_source["source_value_index"][0])
        )
        cases.append(
            (
                "duplicate_source_value",
                duplicate_source,
                "canonical_neutral_table_source_value_index_invalid",
            )
        )

        for label, mutated, expected in cases:
            with self.subTest(label=label):
                validation = validate_canonical_neutral_projection(mutated)
                self.assertEqual(validation["validator_status"], "failed")
                self.assertIn(expected, validation["reason_codes"])
                self.assertFalse(validate_canonical_integrity(mutated))

    def test_private_value_checksum_drift_fails_outer_validator(self):
        projection = self._projection()
        drifted = copy.deepcopy(projection)
        indexed_path = drifted["source_value_index"][0]["value_path"]["value_path_ref"]
        private_value = next(
            item
            for item in drifted["private_values"]
            if item["value_path_ref"] == indexed_path
        )
        private_value["normalized_value"] += "x"

        validation = TableProjectionValidator().validate(drifted)

        self.assertEqual(validation["validator_status"], "failed")
        codes = {item["code"] for item in validation["errors"]}
        self.assertIn("source_value_checksum_mismatch", codes)
        self.assertIn("canonical_neutral_table_integrity_mismatch", codes)
        self.assertIn("table_projection_checksum_mismatch", codes)

    def test_canonical_validation_indexes_source_values_in_bounded_passes(self):
        projection = self._projection()

        class CountingList(list):
            def __init__(self, values):
                super().__init__(values)
                self.iterations = 0

            def __iter__(self):
                self.iterations += 1
                return super().__iter__()

        source_index = CountingList(projection["source_value_index"])
        private_values = CountingList(projection["private_values"])
        projection["source_value_index"] = source_index
        projection["private_values"] = private_values

        validation = TableProjectionValidator().validate(projection)

        self.assertEqual(validation["validator_status"], "passed")
        self.assertLessEqual(source_index.iterations, 6)
        self.assertLessEqual(private_values.iterations, 6)


if __name__ == "__main__":
    unittest.main()
