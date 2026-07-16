from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "pdf_dual_vlm_fact_review.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "pdf_dual_vlm_fact_review_test", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REVIEW = _load_module()


class PdfDualVlmFactReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)
        self.page_bytes = b"\x89PNG\r\nsource-page"
        self.crop_bytes = b"\x89PNG\r\nimmutable-crop"
        self.page_path = self.root / "page.png"
        self.crop_path = self.root / "crop.png"
        self.page_path.write_bytes(self.page_bytes)
        self.crop_path.write_bytes(self.crop_bytes)
        self.page_sha = hashlib.sha256(self.page_bytes).hexdigest()
        self.crop_sha = hashlib.sha256(self.crop_bytes).hexdigest()

    def test_pack_generates_every_card_and_accessible_explicit_states(self) -> None:
        proposal = self._proposal(include_negative=True)
        generated = self._generate(proposal)
        review_index = generated["review_index"]
        rendered = Path(generated["review_html_path"]).read_text(encoding="utf-8")

        self.assertEqual([], REVIEW.validate_review_index(review_index))
        self.assertEqual(2, len(review_index["cards"]))
        table_card = next(
            card
            for card in review_index["cards"]
            if card["card_kind"] == "table_region"
        )
        negative_card = next(
            card
            for card in review_index["cards"]
            if card["card_kind"] == "negative_case"
        )
        self.assertIn("evidence_medium", table_card["checklist_fields"])
        self.assertNotIn("evidence_medium", negative_card["checklist_fields"])
        self.assertEqual(2, rendered.count("data-card-id="))
        for state in ("state-loading", "state-error", "state-empty", "state-success"):
            self.assertIn(f'id="{state}"', rendered)
        self.assertIn('role="alert"', rendered)
        self.assertIn('role="status"', rendered)
        self.assertIn('aria-live="polite"', rendered)
        self.assertIn(":focus-visible", rendered)
        self.assertIn('aria-busy="false"', rendered)
        self.assertIn("button[disabled]", rendered)
        self.assertIn('type="radio" value="approve"', rendered)
        self.assertIn('type="radio" value="correct"', rendered)
        self.assertIn('type="radio" value="ambiguous"', rendered)
        self.assertIn('type="radio" value="reject"', rendered)
        self.assertIn('type="radio" value="confirm"', rendered)
        self.assertIn('<html lang="ru">', rendered)
        self.assertIn("Проверка таблиц и финансовых данных из PDF", rendered)
        self.assertIn("Готовим файл с результатами проверки…", rendered)
        self.assertIn("Материалы загружены.", rendered)
        self.assertIn("Кто проверяет", rendered)
        self.assertIn(
            "Что можно проверить в PDF:</strong> текстовый слой PDF", rendered
        )
        self.assertIn('value="approve" required> Всё верно', rendered)
        self.assertIn('value="correct" required> Нужно исправить', rendered)
        self.assertIn('value="confirm" required> Подтвердить', rendered)
        self.assertIn('<option value="pass">Да, всё верно</option>', rendered)
        self.assertIn("Нет пропущенных или выдуманных фактов", rendered)
        self.assertIn("Скачать результаты проверки (JSON)", rendered)
        self.assertIn("check-evidence_medium", rendered)
        self.assertIn("new Blob", rendered)
        self.assertIn(REVIEW.REVIEW_INTENT_SCHEMA, rendered)
        self.assertIn("region_decision: regionDecision", rendered)
        self.assertIn("fact_id: fact.fact_id", rendered)
        self.assertNotIn("human_reviewed", rendered)
        self.assertNotIn("accepted_for_scoring", rendered)
        self.assertNotIn("finalize_human_reference", rendered)

    def test_empty_pack_has_visible_empty_state_and_disabled_export(self) -> None:
        proposal = self._proposal()
        proposal["cases"] = []
        generated = REVIEW.generate_review_pack(
            proposed_reference=proposal,
            page_artifact_paths={},
            crop_artifact_paths={},
            output_dir=self.root / "empty-pack",
        )
        rendered = Path(generated["review_html_path"]).read_text(encoding="utf-8")

        self.assertIn('id="state-empty" class="state" role="status">', rendered)
        self.assertIn(
            'id="state-success" class="state" role="status" hidden>', rendered
        )
        self.assertIn("Карточек для проверки нет.", rendered)
        self.assertIn("Файл ещё не создан.", rendered)
        self.assertIn('id="export-intent" class="primary"', rendered)
        self.assertIn('aria-describedby="export-feedback" disabled', rendered)

    def test_index_checksum_and_decision_ledger_tamper_fail_closed(self) -> None:
        generated = self._generate(self._proposal())
        review_index = generated["review_index"]
        tampered_index = copy.deepcopy(review_index)
        tampered_index["cards"][0]["page_number"] = 99
        self.assertTrue(
            any(
                error.startswith("review_index_checksum_mismatch")
                for error in REVIEW.validate_review_index(tampered_index)
            )
        )

        decisions = self._decisions(review_index)
        tampered_decisions = copy.deepcopy(decisions)
        tampered_decisions["entries"][0]["region_note"] = "Changed after ledger seal"
        self.assertTrue(
            any(
                error.startswith("review_ledger_entry_not_current")
                for error in REVIEW.validate_review_decisions(
                    tampered_decisions, review_index
                )
            )
        )

    def test_evidence_medium_is_required_and_strict(self) -> None:
        proposal = self._proposal()
        proposal["cases"][0]["regions"][0]["evidence_medium"] = "vision_guess"

        errors = REVIEW.validate_proposed_reference(proposal)

        self.assertTrue(
            any(
                error.startswith("review_region_evidence_medium_invalid")
                for error in errors
            )
        )

        missing = self._proposal()
        del missing["cases"][0]["regions"][0]["evidence_medium"]
        self.assertTrue(
            any(
                error.startswith("review_object_keys_invalid")
                for error in REVIEW.validate_proposed_reference(missing)
            )
        )

    def test_pending_or_missing_corrected_payload_is_terminal_rejection(self) -> None:
        review_index = self._generate(self._proposal())["review_index"]
        entries = self._entries(review_index)
        entries[0]["region_decision"] = "pending"
        with self.assertRaisesRegex(
            REVIEW.ReviewContractError, "review_entries_invalid"
        ):
            REVIEW.PdfDualVlmFactReviewDecisionFactory().create(
                review_index=review_index,
                reviewer=self._reviewer(),
                entries=entries,
            )

        entries = self._entries(review_index)
        entries[0]["region_decision"] = "correct"
        entries[0]["corrected_region"] = copy.deepcopy(
            review_index["cards"][0]["region"]
        )
        entries[0]["corrected_region"]["crop_sha256"] = "c" * 64
        with self.assertRaisesRegex(
            REVIEW.ReviewContractError, "review_entries_invalid"
        ):
            REVIEW.PdfDualVlmFactReviewDecisionFactory().create(
                review_index=review_index,
                reviewer=self._reviewer(),
                entries=entries,
            )

        entries = self._entries(review_index)
        entries[0]["fact_decisions"][0]["decision"] = "correct"
        entries[0]["fact_decisions"][0]["corrected_fact"] = None
        with self.assertRaisesRegex(
            REVIEW.ReviewContractError, "review_entries_invalid"
        ):
            REVIEW.PdfDualVlmFactReviewDecisionFactory().create(
                review_index=review_index,
                reviewer=self._reviewer(),
                entries=entries,
            )

    def test_agent_kind_and_ai_identity_cannot_mint_human_review(self) -> None:
        review_index = self._generate(self._proposal())["review_index"]
        entries = self._entries(review_index)
        for reviewer in (
            {
                "kind": "agent",
                "identity": "Roman Reviewer",
                "reviewed_at": "2026-07-16T12:00:00+03:00",
            },
            {
                "kind": "human",
                "identity": "Codex Agent",
                "reviewed_at": "2026-07-16T12:00:00+03:00",
            },
        ):
            with self.subTest(reviewer=reviewer):
                with self.assertRaisesRegex(
                    REVIEW.ReviewContractError, "reviewer_not_human"
                ):
                    REVIEW.PdfDualVlmFactReviewDecisionFactory().create(
                        review_index=review_index,
                        reviewer=reviewer,
                        entries=entries,
                    )

    def test_approved_fact_without_header_source_cannot_finalize(self) -> None:
        proposal = self._proposal()
        proposal["cases"][0]["regions"][0]["facts"][0]["source_regions"]["header"] = []
        review_index = self._generate(proposal)["review_index"]
        decisions = self._decisions(review_index)

        with self.assertRaisesRegex(
            REVIEW.ReviewContractError, "review_accepted_fact_incomplete"
        ):
            REVIEW.finalize_human_reference(
                proposed_reference=proposal,
                review_index=review_index,
                review_decisions=decisions,
                output_dir=self.root / "final",
            )
        self.assertFalse(
            (self.root / "final" / "reference.human-reviewed.private.json").exists()
        )

    def test_approved_fact_with_explicit_empty_header_path_can_finalize(self) -> None:
        proposal = self._proposal()
        fact = proposal["cases"][0]["regions"][0]["facts"][0]
        fact["header_path"] = []
        fact["source_regions"]["header"] = []
        fact["uncertainty"].append("header_not_present_in_source")
        review_index = self._generate(proposal)["review_index"]
        decisions = self._decisions(review_index)

        result = REVIEW.finalize_human_reference(
            proposed_reference=proposal,
            review_index=review_index,
            review_decisions=decisions,
            output_dir=self.root / "empty-header-final",
        )

        reviewed_fact = result["reference"]["cases"][0]["regions"][0]["facts"][0]
        self.assertEqual(reviewed_fact["fact"]["header_path"], [])
        self.assertEqual(reviewed_fact["fact"]["source_regions"]["header"], [])
        self.assertTrue(reviewed_fact["accepted_for_scoring"])

    def test_approved_empty_header_path_requires_explicit_source_classification(
        self,
    ) -> None:
        proposal = self._proposal()
        fact = proposal["cases"][0]["regions"][0]["facts"][0]
        fact["header_path"] = []
        fact["source_regions"]["header"] = []
        review_index = self._generate(proposal)["review_index"]
        decisions = self._decisions(review_index)

        with self.assertRaisesRegex(
            REVIEW.ReviewContractError, "review_accepted_fact_incomplete"
        ):
            REVIEW.finalize_human_reference(
                proposed_reference=proposal,
                review_index=review_index,
                review_decisions=decisions,
                output_dir=self.root / "unclassified-empty-header-final",
            )

    def test_approved_fact_header_source_must_match_reviewed_header_path(self) -> None:
        proposal = self._proposal()
        proposal["cases"][0]["regions"][0]["facts"][0]["source_regions"]["header"][0][
            "visible_text"
        ] = "Wrong header"
        review_index = self._generate(proposal)["review_index"]
        decisions = self._decisions(review_index)

        with self.assertRaisesRegex(
            REVIEW.ReviewContractError, "review_accepted_fact_incomplete"
        ):
            REVIEW.finalize_human_reference(
                proposed_reference=proposal,
                review_index=review_index,
                review_decisions=decisions,
                output_dir=self.root / "header-mismatch-final",
            )

    def test_approved_context_source_must_share_crop_lineage(self) -> None:
        proposal = self._proposal()
        fact = proposal["cases"][0]["regions"][0]["facts"][0]
        fact["source_regions"]["context"] = [
            {
                "artifact_sha256": "d" * 64,
                "bbox_normalized": [0.05, 0.05, 0.3, 0.12],
                "visible_text": "Context",
            }
        ]
        review_index = self._generate(proposal)["review_index"]
        decisions = self._decisions(review_index)

        with self.assertRaisesRegex(
            REVIEW.ReviewContractError, "review_accepted_fact_incomplete"
        ):
            REVIEW.finalize_human_reference(
                proposed_reference=proposal,
                review_index=review_index,
                review_decisions=decisions,
                output_dir=self.root / "context-lineage-final",
            )

    def test_corrected_fact_is_explicit_and_becomes_scoring_reference(self) -> None:
        proposal = self._proposal()
        review_index = self._generate(proposal)["review_index"]
        entries = self._entries(review_index)
        source_fact = review_index["cards"][0]["region"]["facts"][0]
        corrected = copy.deepcopy(source_fact)
        corrected["visible_value"] = "$ 101"
        corrected["numeric_value"] = "101"
        corrected["source_regions"]["value"]["visible_text"] = "$ 101"
        entries[0]["region_decision"] = "correct"
        entries[0]["region_note"] = "Human corrected the evidence medium and fact."
        entries[0]["corrected_region"] = copy.deepcopy(
            review_index["cards"][0]["region"]
        )
        entries[0]["corrected_region"]["evidence_medium"] = "mixed"
        entries[0]["corrected_region"]["facts"][0] = copy.deepcopy(source_fact)
        entries[0]["fact_decisions"][0] = {
            "fact_id": source_fact["fact_id"],
            "decision": "correct",
            "note": "Human corrected the visible amount.",
            "corrected_fact": corrected,
        }
        decisions = REVIEW.PdfDualVlmFactReviewDecisionFactory().create(
            review_index=review_index,
            reviewer=self._reviewer(),
            entries=entries,
        )

        finalized = REVIEW.finalize_human_reference(
            proposed_reference=proposal,
            review_index=review_index,
            review_decisions=decisions,
            output_dir=self.root / "corrected-final",
        )
        reviewed = finalized["reference"]["cases"][0]["regions"][0]["facts"][0]
        self.assertEqual("correct", reviewed["review_decision"])
        self.assertEqual("$ 101", reviewed["fact"]["visible_value"])
        self.assertTrue(reviewed["accepted_for_scoring"])
        self.assertEqual(
            "mixed", finalized["reference"]["cases"][0]["regions"][0]["evidence_medium"]
        )

    def test_successful_human_finalization_writes_immutable_reference_and_seal(
        self,
    ) -> None:
        proposal = self._proposal(include_negative=True)
        review_index = self._generate(proposal)["review_index"]
        decisions = self._decisions(review_index)
        output = self.root / "accepted"

        finalized = REVIEW.finalize_human_reference(
            proposed_reference=proposal,
            review_index=review_index,
            review_decisions=decisions,
            output_dir=output,
        )

        reference_path = Path(finalized["reference_path"])
        seal_path = Path(finalized["seal_path"])
        payload = reference_path.read_bytes()
        seal = json.loads(seal_path.read_text(encoding="utf-8"))
        self.assertTrue(finalized["reference"]["human_reviewed"])
        self.assertEqual("human", finalized["reference"]["reviewer"]["kind"])
        self.assertEqual(hashlib.sha256(payload).hexdigest(), seal["reference_sha256"])
        self.assertEqual(len(payload), seal["reference_size_bytes"])
        self.assertEqual(
            REVIEW.sha256_json(
                {key: value for key, value in seal.items() if key != "seal_sha256"}
            ),
            seal["seal_sha256"],
        )
        self.assertEqual([], REVIEW.validate_review_decisions(decisions, review_index))
        self.assertEqual(
            "text_layer",
            finalized["reference"]["cases"][0]["regions"][0]["evidence_medium"],
        )

        with self.assertRaisesRegex(
            REVIEW.ReviewContractError, "review_final_output_exists"
        ):
            REVIEW.finalize_human_reference(
                proposed_reference=proposal,
                review_index=review_index,
                review_decisions=decisions,
                output_dir=output,
            )

    def test_decision_updates_preserve_append_only_ledger_prefix(self) -> None:
        review_index = self._generate(self._proposal())["review_index"]
        factory = REVIEW.PdfDualVlmFactReviewDecisionFactory()
        first = factory.create(
            review_index=review_index,
            reviewer=self._reviewer(),
            entries=self._entries(review_index),
        )
        updated_entries = copy.deepcopy(first["entries"])
        updated_entries[0]["region_note"] = "Second explicit human review note."
        second = factory.create(
            review_index=review_index,
            reviewer=self._reviewer(),
            entries=updated_entries,
            prior_decisions=first,
        )

        self.assertEqual(first["ledger"], second["ledger"][: len(first["ledger"])])
        self.assertEqual(len(first["ledger"]) + 1, len(second["ledger"]))
        self.assertEqual([], REVIEW.validate_review_decisions(second, review_index))

    def test_factory_and_forbidden_anchors_are_present(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn("FACTORY_REQUIRED", source)
        self.assertIn("FORBIDDEN", source)
        self.assertIn("PdfDualVlmFactReviewDecisionFactory", source)
        self.assertNotIn("requests", source)
        self.assertNotIn("httpx", source)

    def _generate(self, proposal: dict) -> dict:
        page_paths = {case["case_id"]: self.page_path for case in proposal["cases"]}
        crop_paths = {
            f"{case['case_id']}:{region['region_id']}": self.crop_path
            for case in proposal["cases"]
            for region in case["regions"]
        }
        return REVIEW.generate_review_pack(
            proposed_reference=proposal,
            page_artifact_paths=page_paths,
            crop_artifact_paths=crop_paths,
            output_dir=self.root / f"pack-{len(list(self.root.glob('pack-*')))}",
        )

    def _decisions(self, review_index: dict) -> dict:
        return REVIEW.PdfDualVlmFactReviewDecisionFactory().create(
            review_index=review_index,
            reviewer=self._reviewer(),
            entries=self._entries(review_index),
        )

    def _entries(self, review_index: dict) -> list[dict]:
        entries = []
        for card in review_index["cards"]:
            facts = card["region"]["facts"] if card["region"] is not None else []
            entries.append(
                {
                    "card_id": card["card_id"],
                    "region_decision": "approve",
                    "region_note": "Human checked this region against the source page.",
                    "corrected_region": None,
                    "checklist": {field: "pass" for field in card["checklist_fields"]},
                    "fact_decisions": [
                        {
                            "fact_id": fact["fact_id"],
                            "decision": "confirm",
                            "note": "Human confirmed value and source relation.",
                            "corrected_fact": None,
                        }
                        for fact in facts
                    ],
                }
            )
        return entries

    @staticmethod
    def _reviewer() -> dict:
        return {
            "kind": "human",
            "identity": "Roman Reviewer",
            "reviewed_at": "2026-07-16T12:00:00+03:00",
        }

    def _proposal(self, *, include_negative: bool = False) -> dict:
        def locator(text: str, bbox: list[float]) -> dict:
            return {
                "artifact_sha256": self.crop_sha,
                "bbox_normalized": bbox,
                "visible_text": text,
            }

        fact = {
            "fact_id": "fact_cash",
            "fact_type": "monetary_balance",
            "row_label": "Cash",
            "normalized_row_identity": "cash",
            "header_path": ["Amount"],
            "visible_value": "$ 100",
            "numeric_value": "100",
            "sign": "positive",
            "period": "2025-12-31",
            "currency": "unknown",
            "unit": "currency",
            "scale": "1",
            "entity": "Example Broker",
            "qualifiers": ["visible_currency_symbol"],
            "source_regions": {
                "row_label": locator("Cash", [0.05, 0.2, 0.35, 0.3]),
                "header": [locator("Amount", [0.6, 0.05, 0.95, 0.15])],
                "value": locator("$ 100", [0.65, 0.2, 0.95, 0.3]),
                "context": [],
            },
            "uncertainty": [],
            "alternative_interpretation": None,
        }
        cases = [
            {
                "case_id": "example_p01",
                "document_id": "example_document",
                "pdf_sha256": "a" * 64,
                "page_number": 1,
                "page_sha256": self.page_sha,
                "expected_kind": "table",
                "regions": [
                    {
                        "region_id": "r1",
                        "bbox_normalized": [0.1, 0.1, 0.9, 0.8],
                        "crop_sha256": self.crop_sha,
                        "evidence_medium": "text_layer",
                        "one_complete_table": True,
                        "cuts": {
                            "header": False,
                            "total": False,
                            "row": False,
                            "column": False,
                        },
                        "includes_neighboring_prose": False,
                        "includes_other_table": False,
                        "facts": [fact],
                    }
                ],
            }
        ]
        if include_negative:
            cases.append(
                {
                    "case_id": "negative_p02",
                    "document_id": "example_document",
                    "pdf_sha256": "a" * 64,
                    "page_number": 2,
                    "page_sha256": self.page_sha,
                    "expected_kind": "negative",
                    "regions": [],
                }
            )
        return {
            "schema_version": REVIEW.PROPOSED_REFERENCE_SCHEMA,
            "benchmark_id": "dual_vlm_fact_v1",
            "manifest_sha256": "b" * 64,
            "cases": cases,
        }


if __name__ == "__main__":
    unittest.main()
