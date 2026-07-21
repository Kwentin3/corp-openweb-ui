from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
    Gate2Fns2NdflAdapterFactory,
    Gate2Fns2NdflError,
    Gate2InputReadinessFactory,
    build_retention_policy,
    persist_gate1_result,
    render_fns_2ndfl_safe_report,
    validate_fns_2ndfl_typed_output,
)
from broker_reports_gate1.gate2_fns_2ndfl_adapter import (
    FACTORY_REQUIRED as ADAPTER_FACTORY_REQUIRED,
    FORBIDDEN as ADAPTER_FORBIDDEN,
    is_fns_2ndfl_neutral_event_source_unit,
)


def _xml(
    *,
    year: str = "2024",
    income_code: str = "1010",
    income_amount: str = "1200.50",
    include_deduction: bool = True,
    include_optional_identity: bool = True,
    include_nonwithheld: bool = True,
    extra: str = "",
) -> bytes:
    deduction = (
        '<СвСумВыч КодВычет="503" СумВычет="10,25"/>'
        if include_deduction
        else ""
    )
    optional_identity = (
        ' ИННФЛ="123456789012" ДатаРожд="01.02.1990"'
        if include_optional_identity
        else ""
    )
    nonwithheld = (
        '<СумДохНеУд СумДохНеУдерж="0.00" СумНеУдНал="0.00"/>'
        if include_nonwithheld
        else ""
    )
    return (
        f'<Документ ОтчетГод="{year}" Признак="1" ДатаДок="01.03.2025">'
        '<СвНА ОКТМО="12345678" Тлф="0000000">'
        '<СвНАЮЛ ИННЮЛ="1234567890" КПП="123456789" НаимОрг="Synthetic Agent">'
        "<СвРеоргЮЛ/>"
        "</СвНАЮЛ>"
        "</СвНА>"
        '<НДФЛ-2 НомСпр="SYNTH-001" НомКорр="00">'
        f'<ПолучДох Гражд="643" Статус="1"{optional_identity}>'
        '<УдЛичнФЛ КодУдЛичн="21" СерНомДок="SYNTHETIC"/>'
        '<ФИО Фамилия="Test" Имя="Case" Отчество="Synthetic"/>'
        "</ПолучДох>"
        '<СведДох Ставка="13">'
        "<ДохВыч>"
        f'<СвСумДох Месяц="01" КодДоход="{income_code}" СумДоход="{income_amount}">'
        f"{deduction}"
        "</СвСумДох>"
        "</ДохВыч>"
        "<НалВычССИ/>"
        '<СумИтНалПер СумДохОбщ="1200.50" НалБаза="1190.25" '
        'НалИсчисл="154.73" НалУдерж="154.73" НалУдержЛиш="0.00" '
        'СумФикс="0.00" СумНалПрибЗач="0.00" СумНалИнГос="0.00"/>'
        f"{nonwithheld}{extra}"
        "</СведДох>"
        "</НДФЛ-2>"
        "</Документ>"
    ).encode("utf-8")


def _normalization(xml_bytes: bytes):
    result = Gate1Normalizer().normalize(
        [
            FileInput.from_bytes(
                private_ref="synthetic-fns-2ndfl",
                filename="synthetic.xml",
                content=xml_bytes,
                mime_type="application/xml",
            )
        ],
        input_context={"clarification_criticality_refinement_enabled": True},
    )
    if result.package["validation_result"]["status"] != "passed":
        raise AssertionError(result.package["validation_result"])
    return result


def _source_unit(xml_bytes: bytes) -> dict:
    result = _normalization(xml_bytes)
    return next(
        item
        for item in result.package["private_normalized_source_units"]
        if item.get("parser") == "python_expat_neutral_events"
    )


class BrokerReportsGate2Fns2NdflAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = Gate2Fns2NdflAdapterFactory().create()

    def test_family_recognizer_does_not_capture_generic_neutral_xml(self):
        generic_result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="generic-xml",
                    filename="generic.xml",
                    content=b"<report><amount>12</amount></report>",
                    mime_type="application/xml",
                )
            ]
        )
        generic_unit = next(
            item
            for item in generic_result.package["private_normalized_source_units"]
            if item.get("parser") == "python_expat_neutral_events"
        )

        self.assertFalse(is_fns_2ndfl_neutral_event_source_unit(generic_unit))
        self.assertTrue(
            is_fns_2ndfl_neutral_event_source_unit(_source_unit(_xml()))
        )

    def test_typed_families_refs_amounts_identity_metadata_and_safe_report(self):
        unit = _source_unit(_xml())
        output = self.adapter.adapt(
            source_package_ref="sfpkg_synthetic", source_unit=unit
        )
        validation = validate_fns_2ndfl_typed_output(
            output, allowed_source_value_refs=unit["source_value_refs"]
        )
        families = [item["fact_family"] for item in output["facts"]]
        safe = render_fns_2ndfl_safe_report(output)

        self.assertEqual(validation["validator_status"], "passed")
        self.assertEqual(output["terminal_status"], "validated")
        self.assertEqual(output["report_period"], "2024")
        self.assertIn("source_certificate_identity", families)
        self.assertIn("tax_agent_identity", families)
        self.assertIn("recipient_identity", families)
        self.assertIn("income_source_row", families)
        self.assertIn("deduction_source_row", families)
        self.assertIn("tax_summary_source_fact", families)
        self.assertIn("certificate_metadata", families)
        income = next(
            item for item in output["facts"] if item["fact_family"] == "income_source_row"
        )
        income_fields = {item["field_code"]: item for item in income["fields"]}
        self.assertEqual(income_fields["СумДоход"]["value"], "1200.50")
        deduction = next(
            item
            for item in output["facts"]
            if item["fact_family"] == "deduction_source_row"
        )
        deduction_fields = {
            item["field_code"]: item for item in deduction["fields"]
        }
        self.assertEqual(deduction_fields["СумВычет"]["value"], "10.25")
        metadata = next(
            item
            for item in output["facts"]
            if item["fact_family"] == "certificate_metadata"
        )
        metadata_codes = {item["field_code"] for item in metadata["fields"]}
        financial_codes = {
            item["field_code"]
            for fact in output["facts"]
            if fact["fact_family"] in {
                "income_source_row",
                "deduction_source_row",
                "tax_summary_source_fact",
            }
            for item in fact["fields"]
        }
        self.assertIn("НомСпр", metadata_codes)
        self.assertNotIn("НомСпр", financial_codes)
        self.assertEqual(output["provider_accounting"]["calls"], 0)
        self.assertEqual(output["provider_accounting"]["tokens"], 0)
        self.assertEqual(output["provider_accounting"]["cost"], 0)
        self.assertFalse(safe["customer_values_in_report"])
        self.assertNotIn("Synthetic Agent", str(safe))
        self.assertNotIn("1200.50", str(safe))

    def test_deterministic_replay_and_seventeen_optional_variants(self):
        structural_signatures = set()
        for variant in range(17):
            unit = _source_unit(
                _xml(
                    include_deduction=bool(variant & 1),
                    include_optional_identity=bool(variant & 2),
                    include_nonwithheld=bool(variant & 4),
                    income_amount=("1200,50" if variant & 8 else "1200.50"),
                    extra=(
                        '<СвСумДох Месяц="02" КодДоход="1010" СумДоход="1.00"/>'
                        if variant in {15, 16}
                        else ""
                    ),
                )
            )
            first = self.adapter.adapt(
                source_package_ref=f"sfpkg_variant_{variant}", source_unit=unit
            )
            second = self.adapter.adapt(
                source_package_ref=f"sfpkg_variant_{variant}", source_unit=unit
            )
            self.assertEqual(first, second)
            structural_signatures.add(
                tuple((item["fact_family"], len(item["fields"])) for item in first["facts"])
            )
        self.assertGreaterEqual(len(structural_signatures), 8)

    def test_period_selects_historical_and_current_profiles(self):
        expected = {
            "2016": "fns_2ndfl_mmv_7_11_485_document_fragment_5_04",
            "2018": "fns_2ndfl_mmv_7_11_566_document_fragment",
            "2024": "fns_lk_signed_2ndfl_certificate_document_fragment_v1",
        }
        for year, schema_version_id in expected.items():
            with self.subTest(year=year):
                output = self.adapter.adapt(
                    source_package_ref=f"sfpkg_{year}",
                    source_unit=_source_unit(_xml(year=year)),
                )
                self.assertEqual(output["schema_version_id"], schema_version_id)

    def test_invalid_unknown_duplicate_missing_extension_and_amount_fail_closed(self):
        cases = {
            "unknown_schema": (
                b"<root><item>1</item></root>",
                "fns_2ndfl_schema_family_unknown",
            ),
            "unknown_period": (_xml(year="2026"), "fns_2ndfl_report_period_unknown"),
            "invalid_code": (
                _xml(income_code="ABCD"),
                "fns_2ndfl_code_value_invalid",
            ),
            "invalid_amount": (
                _xml(income_amount="12.3.4"),
                "fns_2ndfl_amount_invalid",
            ),
            "vendor_extension": (
                _xml(extra="<VendorPrivateField value='1'/ >".replace("/ >", "/>")),
                "fns_2ndfl_vendor_extension_not_allowed",
            ),
            "duplicate_singleton": (
                _xml().replace(
                    b"</\xd0\xa1\xd0\xb2\xd0\x9d\xd0\x90>",
                    b"</\xd0\xa1\xd0\xb2\xd0\x9d\xd0\x90><\xd0\xa1\xd0\xb2\xd0\x9d\xd0\x90/>",
                    1,
                ),
                "fns_2ndfl_duplicate_singleton_node",
            ),
            "missing_required_node": (
                _xml().replace(
                    '<ФИО Фамилия="Test" Имя="Case" Отчество="Synthetic"/>'.encode(),
                    b"",
                ),
                "fns_2ndfl_required_node_missing",
            ),
        }
        for name, (xml_bytes, expected_code) in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(Gate2Fns2NdflError) as raised:
                    self.adapter.adapt(
                        source_package_ref=f"sfpkg_{name}",
                        source_unit=_source_unit(xml_bytes),
                    )
                self.assertEqual(raised.exception.code, expected_code)

    def test_factory_route_import_isolation_and_integrity_tamper(self):
        self.assertIn("Gate2Fns2NdflAdapterFactory.create", ADAPTER_FACTORY_REQUIRED)
        self.assertIn("must not import an XML parser", ADAPTER_FORBIDDEN)
        adapter_source = Path(
            "broker_reports_gate1/gate2_fns_2ndfl_adapter.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("xml.parsers", adapter_source)
        self.assertNotIn("ElementTree", adapter_source)

        unit = _source_unit(_xml())
        output = self.adapter.adapt(
            source_package_ref="sfpkg_integrity", source_unit=unit
        )
        tampered = copy.deepcopy(output)
        tampered["facts"][0]["fields"][0]["value"] = "2099"
        validation = validate_fns_2ndfl_typed_output(
            tampered, allowed_source_value_refs=unit["source_value_refs"]
        )
        self.assertEqual(validation["validator_status"], "failed")
        self.assertIn(
            "fns_2ndfl_fact_integrity_mismatch",
            {item["code"] for item in validation["errors"]},
        )

    def test_canonical_readiness_is_read_only_access_scoped_and_purge_closed(self):
        result = _normalization(_xml())
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = ArtifactStoreFactory(
                ArtifactStoreConfig(
                    mode="sqlite",
                    sqlite_path=root / "artifacts.sqlite3",
                    payload_root=root / "payloads",
                )
            ).create()
            run_id = result.package["normalization_run"]["run_id"]
            context = ArtifactAccessContext(
                user_id="fns-adapter-user",
                normalization_run_id=run_id,
                case_id="fns-adapter-case",
                chat_id="fns-adapter-chat",
                workspace_model_id="fns-adapter-model",
                allow_private=True,
                require_source_available=True,
            )
            persisted = persist_gate1_result(
                store=store,
                result=result,
                context=context,
                retention_policy=build_retention_policy(mode="api_smoke"),
            )
            dcp_ref = persisted.artifact_refs_by_type["domain_context_packet_v0"][0]
            before = [
                (record.artifact_id, record.payload_ref, record.lifecycle_status)
                for record in store.list_by_run(run_id)
            ]
            readiness = Gate2InputReadinessFactory(store=store).create().audit_and_build(
                domain_context_packet_ref=dcp_ref, context=context
            )
            after = [
                (record.artifact_id, record.payload_ref, record.lifecycle_status)
                for record in store.list_by_run(run_id)
            ]

            self.assertEqual(readiness.validation["validator_status"], "passed")
            self.assertEqual(readiness.validation["fns_2ndfl_typed_packages_total"], 1)
            self.assertEqual(before, after)
            typed = readiness.packages[0]["typed_source_facts"]
            self.assertEqual(typed["terminal_status"], "validated")
            self.assertTrue(
                readiness.packages[0]["document_context"][
                    "financial_interpretation_allowed"
                ]
            )
            with self.assertRaises(ArtifactStoreError) as denied:
                Gate2InputReadinessFactory(store=store).create().audit_and_build(
                    domain_context_packet_ref=dcp_ref,
                    context=ArtifactAccessContext(
                        **{**context.__dict__, "user_id": "wrong-user"}
                    ),
                )
            self.assertEqual(denied.exception.code, "artifact_access_denied")
            store.purge_run(context)
            with self.assertRaises(ArtifactStoreError) as purged:
                Gate2InputReadinessFactory(store=store).create().audit_and_build(
                    domain_context_packet_ref=dcp_ref, context=context
                )
            self.assertEqual(purged.exception.code, "artifact_purged")

    def test_generic_xml_stays_neutral_and_never_falls_back_to_model(self):
        result = _normalization(b"<root><item code='a'>10</item></root>")
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = ArtifactStoreFactory(
                ArtifactStoreConfig(
                    mode="sqlite",
                    sqlite_path=root / "artifacts.sqlite3",
                    payload_root=root / "payloads",
                )
            ).create()
            run_id = result.package["normalization_run"]["run_id"]
            context = ArtifactAccessContext(
                user_id="unknown-xml-user",
                normalization_run_id=run_id,
                case_id="unknown-xml-case",
                chat_id="unknown-xml-chat",
                workspace_model_id="unknown-xml-model",
                allow_private=True,
                require_source_available=True,
            )
            persisted = persist_gate1_result(
                store=store,
                result=result,
                context=context,
                retention_policy=build_retention_policy(mode="api_smoke"),
            )
            readiness = Gate2InputReadinessFactory(store=store).create().audit_and_build(
                domain_context_packet_ref=persisted.artifact_refs_by_type[
                    "domain_context_packet_v0"
                ][0],
                context=context,
            )
            self.assertEqual(readiness.validation["validator_status"], "passed")
            self.assertNotIn(
                "fns_2ndfl_schema_family_unknown",
                readiness.validation["error_code_counts"],
            )
            package = readiness.packages[0]
            self.assertNotIn("typed_source_facts", package)
            self.assertNotIn("typed_adapter_terminal", package)
            self.assertFalse(package["prompt_contract"]["model_call_performed"])


if __name__ == "__main__":
    unittest.main()
