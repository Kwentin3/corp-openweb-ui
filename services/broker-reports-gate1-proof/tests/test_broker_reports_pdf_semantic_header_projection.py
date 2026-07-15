from __future__ import annotations

import copy
import unittest

from broker_reports_gate1.pdf_hybrid_contracts import sha256_json
from broker_reports_gate1.pdf_semantic_header_contracts import (
    PDF_SEMANTIC_HEADER_CONFIGURATION_SCHEMA,
    SEMANTIC_CURRENCY_CODE_ALLOWLIST,
    SEMANTIC_CURRENCY_CODE_POLICY_VERSION,
    SEMANTIC_HEADER_VOCABULARY,
    SEMANTIC_UNIT_CODE_ALLOWLIST,
    physical_column_id,
    validate_semantic_header_projection,
)
from broker_reports_gate1.pdf_semantic_header_projection import (
    PdfSemanticHeaderProjectionConfig,
    PdfSemanticHeaderProjectionError,
    PdfSemanticHeaderProjectionFactory,
    PdfSemanticHeaderProjectionRuntime,
)


EXPECTED_VOCABULARY = {
    "description",
    "entity",
    "date",
    "period",
    "amount",
    "currency",
    "unit",
    "quantity",
    "percentage",
    "total_or_subtotal",
    "group_header",
    "leaf_header",
    "unknown",
}


class PdfSemanticHeaderProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = PdfSemanticHeaderProjectionFactory().create()

    def _project(
        self,
        *,
        physical_topology_status: str,
        physical_alternatives: list[dict[str, object]],
        runtime: PdfSemanticHeaderProjectionRuntime | None = None,
    ) -> dict[str, object]:
        structural_result_checksum = sha256_json(
            {
                "fixture_structural_status": physical_topology_status,
                "fixture_physical_alternatives": physical_alternatives,
            }
        )
        return (runtime or self.runtime).project(
            structural_result_checksum=structural_result_checksum,
            physical_topology_status=physical_topology_status,
            physical_alternatives=physical_alternatives,
        )

    def test_factory_is_required_and_vocabulary_is_exact(self) -> None:
        self.assertEqual(EXPECTED_VOCABULARY, SEMANTIC_HEADER_VOCABULARY)
        with self.assertRaises(PdfSemanticHeaderProjectionError) as raised:
            PdfSemanticHeaderProjectionRuntime(
                config=PdfSemanticHeaderProjectionConfig()
            )
        self.assertEqual(
            "pdf_semantic_header_projection_factory_required", raised.exception.code
        )

    def test_columns_and_all_semantic_evidence_are_physically_bound(self) -> None:
        alternative = _physical_alternative(
            headers=("Description", "Currency", "Amount"),
            data_rows=(("Trade", "$", "100.00"),),
        )

        result = self._project(
            physical_topology_status="accepted_supplied_consensus",
            physical_alternatives=[alternative],
        )

        projected = result["physical_alternatives"][0]
        self.assertEqual("projected", result["projection_status"])
        self.assertEqual(
            [
                physical_column_id(alternative["grid_checksum"], 1),
                physical_column_id(alternative["grid_checksum"], 2),
                physical_column_id(alternative["grid_checksum"], 3),
            ],
            [item["physical_column_id"] for item in projected["physical_columns"]],
        )
        available_cells = {item["cell_ref"] for item in alternative["cells"]}
        available_atoms = {
            atom_id
            for item in alternative["cells"]
            for atom_id in item["candidate_ids"]
        }
        available_columns = {
            item["physical_column_id"] for item in projected["physical_columns"]
        }
        for field in projected["semantic_fields"]:
            self.assertTrue(field["physical_column_ids"])
            self.assertLessEqual(set(field["physical_column_ids"]), available_columns)
            self.assertLessEqual(set(field["header_cell_refs"]), available_cells)
            self.assertLessEqual(set(field["header_atom_ids"]), available_atoms)
        self.assertEqual(
            [],
            validate_semantic_header_projection(
                result, physical_alternatives=[alternative]
            ),
        )

    def test_separate_and_embedded_currency_are_semantically_equivalent(self) -> None:
        separate = _physical_alternative(
            headers=("Description", "Currency", "Amount"),
            data_rows=(("Trade", "$", "100.00"),),
            seed="separate",
        )
        embedded = _physical_alternative(
            headers=("Description", "Amount"),
            data_rows=(("Trade", "$100.00"),),
            seed="embedded",
        )

        result = self._project(
            physical_topology_status="ambiguous_multiple_consensus",
            physical_alternatives=[separate, embedded],
        )

        self.assertTrue(result["physical_ambiguity_preserved"])
        self.assertEqual(
            "ambiguous_multiple_consensus", result["physical_topology_status"]
        )
        self.assertEqual("equivalent", result["semantic_equivalence_status"])
        self.assertTrue(result["semantic_equivalence_does_not_select_topology"])
        signatures = {
            tuple(item["logical_schema_signature"])
            for item in result["physical_alternatives"]
        }
        self.assertEqual({("description", "monetary_amount")}, signatures)
        embedded_qualifiers = result["physical_alternatives"][1]["qualifiers"]
        self.assertTrue(
            any(
                item["kind"] == "currency" and item["scope"] == "cell"
                for item in embedded_qualifiers
            )
        )
        self.assertEqual(
            [],
            validate_semantic_header_projection(
                result, physical_alternatives=[separate, embedded]
            ),
        )

    def test_currency_scope_and_literal_code_do_not_invent_iso_identity(self) -> None:
        alternative = _physical_alternative(
            headers=("Description", "Currency", "Amount"),
            data_rows=(
                ("First", "$", "100.00"),
                ("Second", "EUR", "200.00"),
            ),
        )

        result = self._project(
            physical_topology_status="accepted_supplied_consensus",
            physical_alternatives=[alternative],
        )

        qualifiers = result["physical_alternatives"][0]["qualifiers"]
        column_qualifier = next(
            item
            for item in qualifiers
            if item["kind"] == "currency" and item["scope"] == "column"
        )
        self.assertIsNone(column_qualifier["normalized_code"])
        row_qualifiers = [item for item in qualifiers if item["scope"] == "row"]
        self.assertEqual([None, "EUR"], [item["normalized_code"] for item in row_qualifiers])
        self.assertNotIn("USD", [item["normalized_code"] for item in qualifiers])

    def test_table_currency_and_header_node_roles_are_structural_only(self) -> None:
        alternative = _physical_alternative(
            headers=("USD", ""),
            data_rows=(("Description", "Amount"), ("Trade", "10.00")),
            header_rows=(1, 2),
            spans=(
                {
                    "start_row": 1,
                    "end_row": 1,
                    "start_column": 1,
                    "end_column": 2,
                    "relation": "merged",
                },
            ),
        )

        result = self._project(
            physical_topology_status="accepted_supplied_consensus",
            physical_alternatives=[alternative],
        )

        projected = result["physical_alternatives"][0]
        roles = {item["role"] for item in projected["semantic_fields"]}
        self.assertIn("group_header", roles)
        self.assertIn("leaf_header", roles)
        table_currency = next(
            item
            for item in projected["qualifiers"]
            if item["kind"] == "currency" and item["scope"] == "table"
        )
        self.assertEqual("USD", table_currency["normalized_code"])
        self.assertFalse(result["geometry_change_allowed"])
        self.assertFalse(result["source_value_change_allowed"])
        self.assertFalse(result["reference_answer_used"])

    def test_unknown_is_valid_and_prevents_equivalence_claim(self) -> None:
        known = _physical_alternative(
            headers=("Description", "Amount"),
            data_rows=(("Trade", "10.00"),),
            seed="known",
        )
        unknown = _physical_alternative(
            headers=("Description", "Mystery"),
            data_rows=(("Trade", "10.00"),),
            seed="unknown",
        )

        result = self._project(
            physical_topology_status="ambiguous_multiple_consensus",
            physical_alternatives=[known, unknown],
        )

        self.assertEqual("incomplete", result["semantic_equivalence_status"])
        second = result["physical_alternatives"][1]
        self.assertIn("unknown", {item["role"] for item in second["semantic_fields"]})
        self.assertTrue(second["unmapped_physical_column_ids"])
        self.assertIn(
            "pdf_semantic_header_unknown_or_unmapped_columns",
            result["reason_codes"],
        )

    def test_amount_and_quantity_keep_explicit_unknown_qualifiers(self) -> None:
        alternative = _physical_alternative(
            headers=("Amount", "Quantity"),
            data_rows=(("10.00", "2"),),
        )

        result = self._project(
            physical_topology_status="accepted_supplied_consensus",
            physical_alternatives=[alternative],
        )

        qualifiers = result["physical_alternatives"][0]["qualifiers"]
        self.assertTrue(
            any(item["kind"] == "currency" and item["scope"] == "unknown" for item in qualifiers)
        )
        self.assertTrue(
            any(item["kind"] == "unit" and item["scope"] == "unknown" for item in qualifiers)
        )

    def test_context_overflow_is_typed_incomplete_without_truncation(self) -> None:
        runtime = PdfSemanticHeaderProjectionFactory(
            PdfSemanticHeaderProjectionConfig(max_context_bytes=512)
        ).create()
        alternative = _physical_alternative(
            headers=("Description " + "x" * 800, "Amount"),
            data_rows=(("Trade", "10.00"),),
        )
        before = copy.deepcopy(alternative)

        result = self._project(
            runtime=runtime,
            physical_topology_status="accepted_supplied_consensus",
            physical_alternatives=[alternative],
        )

        self.assertEqual(before, alternative)
        self.assertEqual("incomplete", result["projection_status"])
        self.assertEqual("incomplete", result["semantic_equivalence_status"])
        self.assertIn(
            "pdf_semantic_header_context_budget_exceeded", result["reason_codes"]
        )
        self.assertEqual(
            "context_budget_exceeded",
            result["physical_alternatives"][0]["projection_status"],
        )

    def test_input_is_immutable_and_reference_shaped_input_is_rejected(self) -> None:
        alternative = _physical_alternative(
            headers=("Description", "Amount"),
            data_rows=(("Trade", "10.00"),),
        )
        before = copy.deepcopy(alternative)

        self._project(
            physical_topology_status="accepted_supplied_consensus",
            physical_alternatives=[alternative],
        )
        self.assertEqual(before, alternative)

        forbidden = copy.deepcopy(alternative)
        forbidden["reference_answer"] = {"columns": 2}
        with self.assertRaises(PdfSemanticHeaderProjectionError) as raised:
            self._project(
                physical_topology_status="accepted_supplied_consensus",
                physical_alternatives=[forbidden],
            )
        self.assertEqual(
            "pdf_semantic_header_physical_alternative_keys_invalid",
            raised.exception.code,
        )

    def test_conflict_and_unsupported_topology_statuses_are_rejected(self) -> None:
        alternative = _physical_alternative(
            headers=("Description", "Amount"),
            data_rows=(("Trade", "10.00"),),
        )
        checksum = sha256_json({"fixture": alternative})
        for status in ("conflict", "unsupported"):
            with self.subTest(status=status):
                with self.assertRaises(PdfSemanticHeaderProjectionError) as raised:
                    self.runtime.project(
                        structural_result_checksum=checksum,
                        physical_topology_status=status,
                        physical_alternatives=[alternative],
                    )
                self.assertEqual(
                    "pdf_semantic_header_physical_topology_status_invalid",
                    raised.exception.code,
                )

    def test_representative_value_evidence_is_bounded_without_truncation(self) -> None:
        runtime = PdfSemanticHeaderProjectionFactory(
            PdfSemanticHeaderProjectionConfig(max_representative_rows=1)
        ).create()
        alternative = _physical_alternative(
            headers=("Description", "Currency", "Amount"),
            data_rows=(
                ("First", "$", "100.00"),
                ("Second", "EUR", "200.00"),
            ),
        )

        result = self._project(
            runtime=runtime,
            physical_topology_status="accepted_supplied_consensus",
            physical_alternatives=[alternative],
        )

        row_qualifiers = [
            item
            for item in result["physical_alternatives"][0]["qualifiers"]
            if item["scope"] == "row"
        ]
        self.assertEqual([None], [item["normalized_code"] for item in row_qualifiers])
        self.assertEqual("incomplete", result["projection_status"])
        self.assertEqual(
            "representative_sample_incomplete",
            result["physical_alternatives"][0]["projection_status"],
        )
        self.assertIn(
            "pdf_semantic_header_representative_rows_incomplete",
            result["reason_codes"],
        )

    def test_non_literal_iso_code_is_rejected_by_validator(self) -> None:
        alternative = _physical_alternative(
            headers=("Description", "Amount"),
            data_rows=(("Trade", "$100.00"),),
        )
        result = self._project(
            physical_topology_status="accepted_supplied_consensus",
            physical_alternatives=[alternative],
        )
        qualifier = next(
            item
            for item in result["physical_alternatives"][0]["qualifiers"]
            if item["scope"] == "cell"
        )
        qualifier["normalized_code"] = "USD"
        unsigned = dict(result)
        unsigned.pop("projection_checksum")
        result["projection_checksum"] = sha256_json(unsigned)

        self.assertIn(
            "pdf_semantic_header_qualifier_code_not_literal_evidence",
            validate_semantic_header_projection(
                result, physical_alternatives=[alternative]
            ),
        )

    def test_missing_header_remains_valid_unknown(self) -> None:
        alternative = _physical_alternative(
            headers=("Trade", "10.00"),
            data_rows=(),
            header_rows=(),
        )

        result = self._project(
            physical_topology_status="accepted_supplied_consensus",
            physical_alternatives=[alternative],
        )

        projected = result["physical_alternatives"][0]
        self.assertEqual("incomplete", result["semantic_equivalence_status"])
        self.assertEqual(
            ["unknown", "unknown"],
            projected["logical_schema_signature"],
        )
        self.assertEqual(
            [],
            validate_semantic_header_projection(
                result, physical_alternatives=[alternative]
            ),
        )

    def test_logical_signature_preserves_repeated_field_roles(self) -> None:
        alternative = _physical_alternative(
            headers=("Amount", "Amount"),
            data_rows=(("10.00", "20.00"),),
        )

        result = self._project(
            physical_topology_status="accepted_supplied_consensus",
            physical_alternatives=[alternative],
        )

        self.assertEqual(
            ["monetary_amount", "monetary_amount"],
            result["physical_alternatives"][0]["logical_schema_signature"],
        )

    def test_configuration_is_versioned_checksummed_and_part_of_identity(self) -> None:
        alternative = _physical_alternative(
            headers=("Description", "Amount"),
            data_rows=(("Trade", "10.00"),),
        )
        default_result = self._project(
            physical_topology_status="accepted_supplied_consensus",
            physical_alternatives=[alternative],
        )
        smaller_sample_runtime = PdfSemanticHeaderProjectionFactory(
            PdfSemanticHeaderProjectionConfig(max_representative_rows=2)
        ).create()
        configured_result = self._project(
            runtime=smaller_sample_runtime,
            physical_topology_status="accepted_supplied_consensus",
            physical_alternatives=[alternative],
        )

        configuration = default_result["configuration"]
        self.assertEqual(
            PDF_SEMANTIC_HEADER_CONFIGURATION_SCHEMA,
            configuration["schema_version"],
        )
        self.assertEqual(
            SEMANTIC_CURRENCY_CODE_POLICY_VERSION,
            configuration["currency_code_policy_version"],
        )
        self.assertNotEqual(
            default_result["configuration_checksum"],
            configured_result["configuration_checksum"],
        )
        self.assertNotEqual(
            default_result["projection_id"],
            configured_result["projection_id"],
        )
        self.assertNotEqual(
            default_result["projection_checksum"],
            configured_result["projection_checksum"],
        )

        tampered = copy.deepcopy(default_result)
        tampered["configuration"]["max_context_bytes"] += 1
        _resign_projection(tampered)
        errors = validate_semantic_header_projection(
            tampered,
            physical_alternatives=[alternative],
        )
        self.assertIn(
            "pdf_semantic_header_configuration_checksum_mismatch",
            errors,
        )

        identity_tamper = copy.deepcopy(default_result)
        identity_tamper["configuration"]["max_representative_rows"] = 2
        identity_tamper["configuration_checksum"] = sha256_json(
            identity_tamper["configuration"]
        )
        _resign_projection(identity_tamper)
        self.assertIn(
            "pdf_semantic_header_projection_id_mismatch",
            validate_semantic_header_projection(
                identity_tamper,
                physical_alternatives=[alternative],
            ),
        )

    def test_validator_recomputes_input_hash_and_column_local_evidence(self) -> None:
        alternative = _physical_alternative(
            headers=("Description", "Currency", "Amount"),
            data_rows=(("Trade", "EUR", "10.00"),),
        )
        result = self._project(
            physical_topology_status="accepted_supplied_consensus",
            physical_alternatives=[alternative],
        )

        wrong_hash = copy.deepcopy(result)
        wrong_hash["input_hash"] = "0" * 64
        _resign_projection(wrong_hash)
        self.assertIn(
            "pdf_semantic_header_input_hash_mismatch",
            validate_semantic_header_projection(
                wrong_hash,
                physical_alternatives=[alternative],
            ),
        )

        wrong_field = copy.deepcopy(result)
        description_field = next(
            field
            for field in wrong_field["physical_alternatives"][0]["semantic_fields"]
            if field["role"] == "description"
        )
        amount_header = next(
            cell
            for cell in alternative["cells"]
            if cell["row_ordinal"] == 1 and cell["column_ordinal"] == 3
        )
        description_field["header_cell_refs"] = [amount_header["cell_ref"]]
        description_field["header_atom_ids"] = list(amount_header["candidate_ids"])
        _resign_projection(wrong_field)
        field_errors = validate_semantic_header_projection(
            wrong_field,
            physical_alternatives=[alternative],
        )
        self.assertIn(
            "pdf_semantic_header_field_header_cell_refs_column_unbound",
            field_errors,
        )
        self.assertIn(
            "pdf_semantic_header_field_header_atom_ids_column_unbound",
            field_errors,
        )

        wrong_qualifier = copy.deepcopy(result)
        row_qualifier = next(
            qualifier
            for qualifier in wrong_qualifier["physical_alternatives"][0]["qualifiers"]
            if qualifier["scope"] == "row"
        )
        description_cell = next(
            cell
            for cell in alternative["cells"]
            if cell["row_ordinal"] == 2 and cell["column_ordinal"] == 1
        )
        row_qualifier["evidence_cell_refs"] = [description_cell["cell_ref"]]
        row_qualifier["evidence_atom_ids"] = list(description_cell["candidate_ids"])
        _resign_projection(wrong_qualifier)
        qualifier_errors = validate_semantic_header_projection(
            wrong_qualifier,
            physical_alternatives=[alternative],
        )
        self.assertIn(
            "pdf_semantic_header_qualifier_evidence_cell_refs_column_unbound",
            qualifier_errors,
        )
        self.assertIn(
            "pdf_semantic_header_qualifier_evidence_atom_ids_column_unbound",
            qualifier_errors,
        )

    def test_currency_codes_use_versioned_allowlist_and_embedded_literals(self) -> None:
        self.assertIn("USD", SEMANTIC_CURRENCY_CODE_ALLOWLIST)
        self.assertIn("EUR", SEMANTIC_CURRENCY_CODE_ALLOWLIST)
        self.assertNotIn("ABC", SEMANTIC_CURRENCY_CODE_ALLOWLIST)
        alternative = _physical_alternative(
            headers=("Description", "Amount EUR"),
            data_rows=(("Trade", "100 EUR"),),
        )

        result = self._project(
            physical_topology_status="accepted_supplied_consensus",
            physical_alternatives=[alternative],
        )

        qualifiers = result["physical_alternatives"][0]["qualifiers"]
        self.assertEqual(
            ["EUR", "EUR"],
            [
                item["normalized_code"]
                for item in qualifiers
                if item["scope"] in {"column", "cell"}
            ],
        )

        arbitrary = _physical_alternative(
            headers=("Description", "Amount ABC"),
            data_rows=(("Trade", "100 ABC"),),
            seed="arbitrary-code",
        )
        arbitrary_result = self._project(
            physical_topology_status="accepted_supplied_consensus",
            physical_alternatives=[arbitrary],
        )
        arbitrary_qualifiers = arbitrary_result["physical_alternatives"][0][
            "qualifiers"
        ]
        self.assertNotIn(
            "ABC",
            [item["normalized_code"] for item in arbitrary_qualifiers],
        )
        self.assertTrue(
            any(
                item["kind"] == "currency" and item["scope"] == "unknown"
                for item in arbitrary_qualifiers
            )
        )

    def test_shared_qualifier_column_with_multiple_measures_is_incomplete(self) -> None:
        for qualifier_header, measure_header, qualifier_kind in (
            ("Currency", "Amount", "currency"),
            ("Unit", "Quantity", "unit"),
        ):
            with self.subTest(qualifier_kind=qualifier_kind):
                alternative = _physical_alternative(
                    headers=(qualifier_header, measure_header, measure_header),
                    data_rows=(("EUR" if qualifier_kind == "currency" else "pcs", "10", "20"),),
                    seed=qualifier_kind,
                )
                result = self._project(
                    physical_topology_status="accepted_supplied_consensus",
                    physical_alternatives=[alternative],
                )

                self.assertEqual("incomplete", result["projection_status"])
                self.assertEqual(
                    "qualifier_binding_incomplete",
                    result["physical_alternatives"][0]["projection_status"],
                )
                self.assertIn(
                    "pdf_semantic_header_qualifier_measure_binding_ambiguous",
                    result["reason_codes"],
                )
                qualifiers = result["physical_alternatives"][0]["qualifiers"]
                self.assertEqual(
                    2,
                    sum(
                        item["kind"] == qualifier_kind
                        and item["scope"] == "unknown"
                        for item in qualifiers
                    ),
                )

    def test_literal_unit_evidence_supports_table_column_row_and_cell(self) -> None:
        self.assertEqual({"kg", "pcs", "shares"}, SEMANTIC_UNIT_CODE_ALLOWLIST)
        table = _physical_alternative(
            headers=("kg", ""),
            data_rows=(("Description", "Quantity"), ("Trade", "10")),
            header_rows=(1, 2),
            spans=(
                {
                    "start_row": 1,
                    "end_row": 1,
                    "start_column": 1,
                    "end_column": 2,
                    "relation": "merged",
                },
            ),
            seed="unit-table",
        )
        separate = _physical_alternative(
            headers=("Description", "Unit", "Quantity"),
            data_rows=(("Trade", "pcs", "10"),),
            seed="unit-separate",
        )
        embedded = _physical_alternative(
            headers=("Description", "Quantity shares"),
            data_rows=(("Trade", "10 shares"),),
            seed="unit-embedded",
        )

        table_result = self._project(
            physical_topology_status="accepted_supplied_consensus",
            physical_alternatives=[table],
        )
        separate_result = self._project(
            physical_topology_status="accepted_supplied_consensus",
            physical_alternatives=[separate],
        )
        embedded_result = self._project(
            physical_topology_status="accepted_supplied_consensus",
            physical_alternatives=[embedded],
        )

        self.assertTrue(
            any(
                item["scope"] == "table" and item["normalized_code"] == "kg"
                for item in table_result["physical_alternatives"][0]["qualifiers"]
            )
        )
        self.assertTrue(
            any(
                item["scope"] == "row" and item["normalized_code"] == "pcs"
                for item in separate_result["physical_alternatives"][0]["qualifiers"]
            )
        )
        embedded_qualifiers = embedded_result["physical_alternatives"][0][
            "qualifiers"
        ]
        self.assertEqual(
            ["shares", "shares"],
            [
                item["normalized_code"]
                for item in embedded_qualifiers
                if item["scope"] in {"column", "cell"}
            ],
        )

    def test_deepest_merged_leaf_uses_anchor_evidence(self) -> None:
        alternative = _physical_alternative(
            headers=("Description", ""),
            data_rows=(("Trade", "Other"),),
            spans=(
                {
                    "start_row": 1,
                    "end_row": 1,
                    "start_column": 1,
                    "end_column": 2,
                    "relation": "merged",
                },
            ),
            seed="merged-leaf",
        )

        result = self._project(
            physical_topology_status="accepted_supplied_consensus",
            physical_alternatives=[alternative],
        )

        second_leaf = next(
            field
            for field in result["physical_alternatives"][0]["semantic_fields"]
            if field["role"] == "leaf_header"
            and field["physical_column_ids"]
            == [physical_column_id(alternative["grid_checksum"], 2)]
        )
        self.assertEqual(["cell_merged-leaf_1_1"], second_leaf["header_cell_refs"])
        self.assertTrue(second_leaf["header_span_refs"])
        self.assertEqual(
            [],
            validate_semantic_header_projection(
                result,
                physical_alternatives=[alternative],
            ),
        )

    def test_configuration_caps_and_alternative_cap_are_fail_closed(self) -> None:
        for config in (
            PdfSemanticHeaderProjectionConfig(max_context_bytes=48 * 1024 + 1),
            PdfSemanticHeaderProjectionConfig(max_physical_alternatives=9),
            PdfSemanticHeaderProjectionConfig(max_representative_rows=4),
        ):
            with self.subTest(config=config):
                with self.assertRaises(PdfSemanticHeaderProjectionError) as raised:
                    PdfSemanticHeaderProjectionFactory(config).create()
                self.assertEqual(
                    "pdf_semantic_header_projection_budget_invalid",
                    raised.exception.code,
                )

        with self.assertRaises(PdfSemanticHeaderProjectionError) as raised:
            self.runtime.project(
                structural_result_checksum="0" * 64,
                physical_topology_status="ambiguous_multiple_consensus",
                physical_alternatives=[_NoDeepcopy() for _ in range(9)],
            )
        self.assertEqual(
            "pdf_semantic_header_alternative_budget_exceeded",
            raised.exception.code,
        )

    def test_validator_rejects_projected_top_status_with_unknown_columns(self) -> None:
        alternative = _physical_alternative(
            headers=("Description", "Mystery"),
            data_rows=(("Trade", "10"),),
        )
        result = self._project(
            physical_topology_status="accepted_supplied_consensus",
            physical_alternatives=[alternative],
        )
        result["projection_status"] = "projected"
        _resign_projection(result)

        self.assertIn(
            "pdf_semantic_header_projection_status_inconsistent",
            validate_semantic_header_projection(
                result,
                physical_alternatives=[alternative],
            ),
        )


def _resign_projection(result: dict[str, object]) -> None:
    unsigned = dict(result)
    unsigned.pop("projection_checksum", None)
    result["projection_checksum"] = sha256_json(unsigned)


class _NoDeepcopy(dict[str, object]):
    def __deepcopy__(self, memo: dict[int, object]) -> dict[str, object]:
        raise AssertionError("alternative cap must be checked before deepcopy")


def _physical_alternative(
    *,
    headers: tuple[str, ...],
    data_rows: tuple[tuple[str, ...], ...],
    seed: str = "default",
    header_rows: tuple[int, ...] = (1,),
    spans: tuple[dict[str, object], ...] = (),
) -> dict[str, object]:
    width = len(headers)
    raw_rows = (headers, *data_rows)
    rows = []
    cells = []
    for row_ordinal, values in enumerate(raw_rows, start=1):
        rows.append(
            {
                "row_ordinal": row_ordinal,
                "row_kind": "header" if row_ordinal in header_rows else "data",
            }
        )
        for column_ordinal, value in enumerate(values, start=1):
            cell_ref = f"cell_{seed}_{row_ordinal}_{column_ordinal}"
            candidate_ids = [] if value == "" else [f"atom_{seed}_{row_ordinal}_{column_ordinal}"]
            exact_values = [] if value == "" else [value]
            cells.append(
                {
                    "cell_ref": cell_ref,
                    "row_ordinal": row_ordinal,
                    "column_ordinal": column_ordinal,
                    "candidate_ids": candidate_ids,
                    "exact_values": exact_values,
                }
            )
    grid_checksum = sha256_json(
        {
            "seed": seed,
            "headers": headers,
            "data_rows": data_rows,
            "header_rows": header_rows,
            "spans": spans,
        }
    )
    return {
        "grid_checksum": grid_checksum,
        "row_count": len(raw_rows),
        "column_count": width,
        "header_rows": list(header_rows),
        "header_hierarchy": [],
        "spans": [copy.deepcopy(item) for item in spans],
        "rows": rows,
        "cells": cells,
    }


if __name__ == "__main__":
    unittest.main()
