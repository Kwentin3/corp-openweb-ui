from __future__ import annotations

import unittest

from broker_reports_gate1 import (
    CSV_SUPPORTED_PROFILE_ID,
    CsvSupportedProfileConfig,
    CsvSupportedProfileError,
    CsvSupportedProfileFactory,
    FileInput,
    Gate1Normalizer,
)
from broker_reports_gate1.csv_profile import FACTORY_REQUIRED, FORBIDDEN


class BrokerReportsCsvSupportedProfileTest(unittest.TestCase):
    def test_factory_parses_supported_encodings_delimiters_quotes_and_sparse_rows(self):
        self.assertIn("CsvSupportedProfileFactory.create", FACTORY_REQUIRED)
        self.assertIn("must not guess a delimiter", FORBIDDEN)
        parser = CsvSupportedProfileFactory().create()
        examples = (
            ("utf-8", ",", "utf-8"),
            ("utf-8-sig", ";", "utf-8-sig"),
            ("cp1251", "\t", "cp1251"),
            ("utf-8", "|", "utf-8"),
        )
        for encoding, delimiter, expected_encoding in examples:
            text = (
                f"Date{delimiter}Description{delimiter}Amount\r\n"
                f"2026-01-01{delimiter}\"Quoted {delimiter} value\"{delimiter}10.00\r\n"
                "\r\n"
                "Summary\r\n"
                f"2026-01-02{delimiter}\"escaped \"\"quote\"\" Доход\"{delimiter}20.00\r\n"
            )
            result = parser.parse(text.encode(encoding))
            self.assertEqual(result.encoding, expected_encoding)
            self.assertEqual(result.delimiter, delimiter)
            self.assertEqual(result.rows_total, 5)
            self.assertEqual(result.blank_rows_total, 1)
            self.assertEqual(result.data_rows_total, 3)
            self.assertEqual(result.rows[3], ["Summary"])
            self.assertEqual(result.rows[4][1], 'escaped "quote" Доход')
            self.assertEqual(
                result.safe_profile()["profile_id"], CSV_SUPPORTED_PROFILE_ID
            )

    def test_profile_fails_closed_without_truncation_or_repair(self):
        parser = CsvSupportedProfileFactory(
            CsvSupportedProfileConfig(
                max_input_bytes=256,
                max_rows=3,
                max_cells=8,
                max_columns=4,
                max_field_characters=12,
                max_materialized_json_bytes=256,
            )
        ).create()
        cases = {
            "csv_profile_header_duplicate": b"A,A\n1,2\n",
            "csv_profile_header_cell_empty": b"A,\n1,2\n",
            "csv_profile_data_row_required": b"A,B\n\n",
            "csv_profile_parse_failed": b'A,B\n\"unterminated,2\n',
            "csv_profile_nul_character_forbidden": b"A,B\n1,\x002\n",
            "csv_profile_row_budget_exceeded": b"A,B\n1,2\n3,4\n5,6\n",
            "csv_profile_field_budget_exceeded": b"A,B\n1,1234567890123\n",
        }
        for expected, content in cases.items():
            with self.subTest(expected=expected):
                with self.assertRaises(CsvSupportedProfileError) as raised:
                    parser.parse(content)
                self.assertEqual(raised.exception.code, expected)

        uneven = parser.parse(b"A,B\n1,2,3\nSummary\n")
        self.assertEqual(uneven.rows[1], ["1", "2", "3"])
        self.assertEqual(uneven.columns_total, 3)
        self.assertEqual(uneven.uneven_rows_total, 2)

    def test_gate1_uses_same_profile_for_preview_and_complete_source_unit(self):
        content = b"Date,Type,Amount\n2026-01-01,income,10.00\n\nSummary\n"
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="csv-profile-contract",
                    filename="supported.csv",
                    content=content,
                    mime_type="text/csv",
                )
            ]
        )
        profile = result.package["technical_readability_profiles"][0]
        summary = result.package["full_source_coverage_summary"]
        unit = result.package["private_normalized_source_units"][0]
        self.assertEqual(profile["supported_csv_profile_status"], "accepted")
        self.assertEqual(
            profile["supported_csv_profile_id"], CSV_SUPPORTED_PROFILE_ID
        )
        self.assertEqual(summary["full_coverage_documents_total"], 1)
        self.assertFalse(unit["source_slice_truncated"])
        self.assertEqual(unit["parent_remainder_status"], "not_applicable_parent_complete")
        self.assertEqual(unit["rows"], unit["cells"])


if __name__ == "__main__":
    unittest.main()
