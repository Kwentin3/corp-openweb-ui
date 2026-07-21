from __future__ import annotations

import copy
import re
import unittest

from broker_reports_gate1 import (
    Gate2Fns2NdflAdapterFactory,
    Gate2Fns2NdflParityError,
    Gate2Fns2NdflParityFactory,
    render_fns_2ndfl_parity_safe_report,
    validate_fns_2ndfl_parity,
)
from tests.test_broker_reports_gate2_fns_2ndfl_adapter import _source_unit, _xml


def _pdf_unit(unit_id: str, text: str) -> dict:
    return {
        "document_ref": "brdoc_synthetic_pdf",
        "unit_id": unit_id,
        "unit_kind": "pdf_table_candidate",
        "source_unit_checksum_ref": f"srcunitchk_{unit_id}",
        "normalized_source_projection": {"text": text},
    }


def _parity_inputs():
    typed = Gate2Fns2NdflAdapterFactory().create().adapt(
        source_package_ref="sfpkg_synthetic_xml",
        source_unit=_source_unit(_xml()),
    )
    material_values = [
        str(field["value"])
        for fact in typed["facts"]
        if fact["fact_family"]
        in {"income_source_row", "deduction_source_row", "tax_summary_source_fact"}
        for field in fact["fields"]
    ]
    values = " ".join(material_values)
    pdf_units = [
        _pdf_unit(
            "pdfcand_income",
            "Месяц Код Код Сумма дохода Сумма вычета " + values,
        ),
        _pdf_unit(
            "pdfcand_summary",
            (
                "Общая сумма дохода Налоговая база Сумма налога исчисленная "
                "Сумма налога удержанная "
            )
            + values,
        ),
        _pdf_unit(
            "pdfcand_nonwithheld",
            (
                "Сумма дохода, с которого не удержан налог "
                "Сумма неудержанного налога "
            )
            + values,
        ),
        _pdf_unit("pdfcand_heading", "Сведения о физическом лице Раздел 1"),
    ]
    return typed, pdf_units


class BrokerReportsGate2Fns2NdflParityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = Gate2Fns2NdflParityFactory().create()

    def test_bidirectional_material_parity_and_representation_satisfaction(self):
        typed, pdf_units = _parity_inputs()
        result = self.service.reconcile(
            typed_xml_output=typed,
            paired_pdf_document_ref="brdoc_synthetic_pdf",
            pdf_source_units=pdf_units,
        )
        validation = validate_fns_2ndfl_parity(
            result,
            expected_pdf_candidate_refs=[item["unit_id"] for item in pdf_units],
        )
        safe = render_fns_2ndfl_parity_safe_report(result)

        self.assertEqual(validation["validator_status"], "passed")
        self.assertEqual(result["terminal_status"], "validated")
        self.assertEqual(result["unmatched_material_errors"], 0)
        self.assertGreater(
            result["terminal_class_counts"]["matched_material_financial"], 0
        )
        self.assertGreater(
            result["terminal_class_counts"]["xml_only_certificate_metadata"], 0
        )
        self.assertEqual(
            result["representation_satisfaction"]["selected_representation"],
            "typed_fns_2ndfl_xml",
        )
        self.assertTrue(
            result["representation_satisfaction"][
                "typed_xml_satisfies_named_workflow"
            ]
        )
        self.assertEqual(
            result["representation_satisfaction"]["pdf_candidates_preserved"],
            4,
        )
        self.assertEqual(
            result["representation_satisfaction"]["pdf_candidates_canonicalized"],
            0,
        )
        self.assertFalse(
            result["representation_satisfaction"][
                "source_identities_merged_or_deleted"
            ]
        )
        self.assertEqual(result["provider_accounting"]["calls"], 0)
        self.assertFalse(safe["customer_values_in_report"])
        self.assertNotIn("1200.50", str(safe))

    def test_value_contradiction_fails_closed(self):
        typed, pdf_units = _parity_inputs()
        for unit in pdf_units:
            projection = unit["normalized_source_projection"]
            projection["text"] = projection["text"].replace("1200.50", "9999.99")
        with self.assertRaises(Gate2Fns2NdflParityError) as raised:
            self.service.reconcile(
                typed_xml_output=typed,
                paired_pdf_document_ref="brdoc_synthetic_pdf",
                pdf_source_units=pdf_units,
            )
        self.assertEqual(
            raised.exception.code, "fns_2ndfl_parity_unmatched_material_error"
        )

    def test_explicit_zero_month_and_decimal_representation_equivalences(self):
        typed, pdf_units = _parity_inputs()
        for unit in pdf_units:
            projection = unit["normalized_source_projection"]
            text = projection["text"]
            text = re.sub(r"(?<!\d)0\.00(?!\d)", "", text)
            text = re.sub(r"(?<!\d)01(?!\d)", "1", text)
            text = re.sub(r"(?<!\d)13(?!\d)", "13.0", text)
            projection["text"] = text

        result = self.service.reconcile(
            typed_xml_output=typed,
            paired_pdf_document_ref="brdoc_synthetic_pdf",
            pdf_source_units=pdf_units,
        )
        policies = {
            item["comparison_policy"] for item in result["forward_field_results"]
        }

        self.assertEqual(result["terminal_status"], "validated")
        self.assertEqual(result["unmatched_material_errors"], 0)
        self.assertIn(
            "schema_zero_to_blank_representation_equivalence_v1", policies
        )
        self.assertIn("schema_month_leading_zero_equivalence_v1", policies)
        self.assertIn("schema_integer_decimal_token_equivalence_v1", policies)

    def test_missing_reverse_scope_and_candidate_cardinality_fail_closed(self):
        typed, pdf_units = _parity_inputs()
        pdf_units[0]["normalized_source_projection"]["text"] = (
            "unrelated numeric block 1200.50 10.25 13"
        )
        with self.assertRaises(Gate2Fns2NdflParityError):
            self.service.reconcile(
                typed_xml_output=typed,
                paired_pdf_document_ref="brdoc_synthetic_pdf",
                pdf_source_units=pdf_units,
            )

        typed, pdf_units = _parity_inputs()
        pdf_units.append(
            _pdf_unit(
                "pdfcand_extra_summary",
                "Общая сумма дохода Налоговая база Сумма налога исчисленная "
                "Сумма налога удержанная",
            )
        )
        with self.assertRaises(Gate2Fns2NdflParityError):
            self.service.reconcile(
                typed_xml_output=typed,
                paired_pdf_document_ref="brdoc_synthetic_pdf",
                pdf_source_units=pdf_units,
            )

    def test_identity_scope_and_integrity_tamper_fail_closed(self):
        typed, pdf_units = _parity_inputs()
        foreign = copy.deepcopy(pdf_units)
        foreign[0]["document_ref"] = "brdoc_foreign"
        with self.assertRaises(Gate2Fns2NdflParityError) as raised:
            self.service.reconcile(
                typed_xml_output=typed,
                paired_pdf_document_ref="brdoc_synthetic_pdf",
                pdf_source_units=foreign,
            )
        self.assertEqual(
            raised.exception.code,
            "fns_2ndfl_parity_pdf_document_scope_mismatch",
        )

        result = self.service.reconcile(
            typed_xml_output=typed,
            paired_pdf_document_ref="brdoc_synthetic_pdf",
            pdf_source_units=pdf_units,
        )
        result["representation_satisfaction"]["pdf_candidates_canonicalized"] = 1
        validation = validate_fns_2ndfl_parity(result)
        self.assertEqual(validation["validator_status"], "failed")
        self.assertIn(
            "fns_2ndfl_parity_representation_guard_failed",
            {item["code"] for item in validation["errors"]},
        )
        self.assertIn(
            "fns_2ndfl_parity_integrity_mismatch",
            {item["code"] for item in validation["errors"]},
        )


if __name__ == "__main__":
    unittest.main()
