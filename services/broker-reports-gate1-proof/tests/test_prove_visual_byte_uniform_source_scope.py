from __future__ import annotations

import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

import fitz
from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)

from scripts.prove_visual_byte_uniform_source_scope import (
    SCHEMA_VERSION,
    VisualSourceCorrectionProofError,
    build_source_correction_proof,
)


def _three_page_pdf(*, target_page_contentful: bool) -> bytes:
    writer = PdfWriter()
    for page_number in range(1, 4):
        page = writer.add_blank_page(width=300, height=300)
        if page_number == 2 and not target_page_contentful:
            continue
        stream = DecodedStreamObject()
        stream.set_data(b"0 0 20 20 re f")
        page[NameObject("/Contents")] = writer._add_object(stream)
        page[NameObject("/Resources")] = DictionaryObject()
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _render_page(pdf_bytes: bytes, page_number: int) -> bytes:
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    pixmap = document.load_page(page_number - 1).get_pixmap(
        matrix=fitz.Matrix(2.0, 2.0),
        colorspace=fitz.csRGB,
        alpha=False,
        annots=True,
    )
    return pixmap.tobytes("png")


class ProveVisualByteUniformSourceScopeTest(unittest.TestCase):
    def test_exact_blank_source_produces_terminal_source_correction_receipt(self):
        pdf_bytes = _three_page_pdf(target_page_contentful=False)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = root / "first.pdf"
            second = root / "second.pdf"
            first.write_bytes(pdf_bytes)
            second.write_bytes(pdf_bytes)

            proof = build_source_correction_proof(
                source_pdf_paths=[first, second],
                page_number=2,
                source_identity_count=2,
                normalized_page_renders=[
                    _render_page(pdf_bytes, 2),
                    _render_page(pdf_bytes, 2),
                ],
                artifactstore_unchanged=True,
            )

        self.assertEqual(proof["schema_version"], SCHEMA_VERSION)
        self.assertEqual(proof["status"], "NOT_CLOSED")
        self.assertEqual(
            proof["goal_3_status"],
            "correctly_deferred_source_correction_required",
        )
        self.assertTrue(
            proof["original_source_page_proof"][
                "all_visible_content_signals_zero"
            ]
        )
        self.assertTrue(
            proof["original_source_page_proof"][
                "target_is_only_blank_page_in_document"
            ]
        )
        self.assertTrue(
            proof["artifactstore_page_render_proof"][
                "normalized_render_pixel_equal_source_render"
            ]
        )
        self.assertEqual(
            proof["recovery_feasibility"][
                "canonical_table_recovery_from_current_source"
            ],
            "impossible_without_source_correction",
        )
        self.assertFalse(
            proof["recovery_feasibility"]["material_scope_reclassified"]
        )
        rendered = json.dumps(proof, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(str(first), rendered)
        self.assertNotIn("first.pdf", rendered)

    def test_contentful_target_page_fails_instead_of_requesting_correction(self):
        pdf_bytes = _three_page_pdf(target_page_contentful=True)
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "source.pdf"
            source.write_bytes(pdf_bytes)
            with self.assertRaisesRegex(
                VisualSourceCorrectionProofError,
                "source_scope_target_page_not_byte_uniform",
            ):
                build_source_correction_proof(
                    source_pdf_paths=[source],
                    page_number=2,
                    source_identity_count=1,
                    normalized_page_renders=[_render_page(pdf_bytes, 2)],
                    artifactstore_unchanged=True,
                )

    def test_nonidentical_source_copies_fail_closed(self):
        first_bytes = _three_page_pdf(target_page_contentful=False)
        second_bytes = _three_page_pdf(target_page_contentful=True)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = root / "first.pdf"
            second = root / "second.pdf"
            first.write_bytes(first_bytes)
            second.write_bytes(second_bytes)
            with self.assertRaisesRegex(
                VisualSourceCorrectionProofError,
                "source_scope_pdf_copies_not_exact",
            ):
                build_source_correction_proof(
                    source_pdf_paths=[first, second],
                    page_number=2,
                    source_identity_count=2,
                    normalized_page_renders=[_render_page(first_bytes, 2)],
                    artifactstore_unchanged=True,
                )


if __name__ == "__main__":
    unittest.main()
