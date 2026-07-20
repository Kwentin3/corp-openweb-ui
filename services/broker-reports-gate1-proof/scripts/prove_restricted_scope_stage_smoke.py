#!/usr/bin/env python3
"""Synthetic restricted-scope smoke through maintained Gate 1/Gate 2 factories."""

from __future__ import annotations

import base64
import io
import json
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
    Gate2InputReadinessFactory,
    NormalizedTableProjectionConfig,
    build_retention_policy,
    persist_gate1_result,
)


REPOSITORY_BUNDLE_SHA256 = "__REPOSITORY_BUNDLE_SHA256__"
FNS_XML_BASE64 = (
    "PNCU0L7QutGD0LzQtdC90YIg0J7RgtGH0LXRgtCT0L7QtD0iMjAyNCIg0J/RgNC40LfQvdCw0Lo9IjEiINCU0LDRgtCw0JTQvtC6PSIwMS4wMy4yMDI1Ij480KHQstCd0JAg0J7QmtCi0JzQnj0iMTIzNDU2NzgiINCi0LvRhD0iMDAwMDAwMCI+PNCh0LLQndCQ0K7QmyDQmNCd0J3QrtCbPSIxMjM0NTY3ODkwIiDQmtCf0J89IjEyMzQ1Njc4OSIg0J3QsNC40LzQntGA0LM9IlN5bnRoZXRpYyBBZ2VudCI+PNCh0LLQoNC10L7RgNCz0K7Qmy8+PC/QodCy0J3QkNCu0Js+PC/QodCy0J3QkD480J3QlNCk0JstMiDQndC+0LzQodC/0YA9IlNZTlRILTAwMSIg0J3QvtC80JrQvtGA0YA9IjAwIj480J/QvtC70YPRh9CU0L7RhSDQk9GA0LDQttC0PSI2NDMiINCh0YLQsNGC0YPRgT0iMSIg0JjQndCd0KTQmz0iMTIzNDU2Nzg5MDEyIiDQlNCw0YLQsNCg0L7QttC0PSIwMS4wMi4xOTkwIj480KPQtNCb0LjRh9C90KTQmyDQmtC+0LTQo9C00JvQuNGH0L09IjIxIiDQodC10YDQndC+0LzQlNC+0Lo9IlNZTlRIRVRJQyIvPjzQpNCY0J4g0KTQsNC80LjQu9C40Y89IlRlc3QiINCY0LzRjz0iQ2FzZSIg0J7RgtGH0LXRgdGC0LLQvj0iU3ludGhldGljIi8+PC/Qn9C+0LvRg9GH0JTQvtGFPjzQodCy0LXQtNCU0L7RhSDQodGC0LDQstC60LA9IjEzIj480JTQvtGF0JLRi9GHPjzQodCy0KHRg9C80JTQvtGFINCc0LXRgdGP0YY9IjAxIiDQmtC+0LTQlNC+0YXQvtC0PSIxMDEwIiDQodGD0LzQlNC+0YXQvtC0PSIxMjAwLjUwIj480KHQstCh0YPQvNCS0YvRhyDQmtC+0LTQktGL0YfQtdGCPSI1MDMiINCh0YPQvNCS0YvRh9C10YI9IjEwLDI1Ii8+PC/QodCy0KHRg9C80JTQvtGFPjwv0JTQvtGF0JLRi9GHPjzQndCw0LvQktGL0YfQodCh0JgvPjzQodGD0LzQmNGC0J3QsNC70J/QtdGAINCh0YPQvNCU0L7RhdCe0LHRiT0iMTIwMC41MCIg0J3QsNC70JHQsNC30LA9IjExOTAuMjUiINCd0LDQu9CY0YHRh9C40YHQuz0iMTU0LjczIiDQndCw0LvQo9C00LXRgNC2PSIxNTQuNzMiINCd0LDQu9Cj0LTQtdGA0LbQm9C40Yg9IjAuMDAiINCh0YPQvNCk0LjQutGBPSIwLjAwIiDQodGD0LzQndCw0LvQn9GA0LjQsdCX0LDRhz0iMC4wMCIg0KHRg9C80J3QsNC70JjQvdCT0L7RgT0iMC4wMCIvPjzQodGD0LzQlNC+0YXQndC10KPQtCDQodGD0LzQlNC+0YXQndC10KPQtNC10YDQtj0iMC4wMCIg0KHRg9C80J3QtdCj0LTQndCw0Ls9IjAuMDAiLz48L9Ch0LLQtdC00JTQvtGFPjwv0J3QlNCk0JstMj48L9CU0L7QutGD0LzQtdC90YI+"
)


def _zip_bytes() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "synthetic_report.pdf",
            _text_pdf(),
        )
    return output.getvalue()


def _text_pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
    )
    stream = DecodedStreamObject()
    stream.set_data(
        b"BT /F1 12 Tf 20 260 Td (Synthetic Broker Report) Tj "
        b"0 -20 Td (Amount 10.00 USD) Tj ET"
    )
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _visual_pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    image = DecodedStreamObject()
    image.set_data(b"\x00")
    image.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(1),
            NameObject("/Height"): NumberObject(1),
            NameObject("/ColorSpace"): NameObject("/DeviceGray"),
            NameObject("/BitsPerComponent"): NumberObject(8),
        }
    )
    image_ref = writer._add_object(image)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/XObject"): DictionaryObject({NameObject("/Im1"): image_ref})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"q 10 0 0 10 20 20 cm /Im1 Do Q")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _inputs() -> list[FileInput]:
    return [
        FileInput.from_bytes(
            private_ref="restricted-scope-stage-zip",
            filename="synthetic_sources.zip",
            content=_zip_bytes(),
            mime_type="application/zip",
            source_kind="synthetic_stage_smoke",
        ),
        FileInput.from_bytes(
            private_ref="restricted-scope-stage-fns",
            filename="synthetic_fns_2ndfl.xml",
            content=base64.b64decode(FNS_XML_BASE64),
            mime_type="application/xml",
            source_kind="synthetic_stage_smoke",
        ),
        FileInput.from_bytes(
            private_ref="restricted-scope-stage-visual",
            filename="synthetic_visual.pdf",
            content=_visual_pdf(),
            mime_type="application/pdf",
            source_kind="synthetic_stage_smoke",
        ),
    ]


def build_proof() -> dict:
    inputs = _inputs()
    result = Gate1Normalizer().normalize(
        inputs,
        input_context={
            "clarification_criticality_refinement_enabled": True,
            "proof_scope": "synthetic_restricted_scope_stage_smoke_v1",
        },
        entrypoint="restricted_scope_stage_smoke",
        trigger_type="backend_core",
    )
    package = result.package
    memory = package["document_memory_manifest"]
    memory_by_format = {
        item["container_format"]: item for item in memory["documents"]
    }
    zip_memory = memory_by_format["zip"]
    visual_memory = next(
        item
        for item in memory["documents"]
        if item["source_scope"]["declared"].get("visual_pages") == 1
    )
    member_memory = next(
        item
        for item in memory["documents"]
        if item["source_lineage"].get("archive_parent_source_ref")
    )
    zip_ref = zip_memory["source_file_ref"]
    visual_ref = visual_memory["source_file_ref"]
    member_ref = member_memory["source_file_ref"]
    next_refs = package["domain_context_packet"]["next_stage_refs"]
    visual_units = [
        item
        for item in package["private_normalized_source_units"]
        if item.get("document_id") == visual_ref
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root / "artifacts.sqlite3",
                payload_root=root / "payloads",
            )
        ).create()
        context = ArtifactAccessContext(
            user_id="synthetic-restricted-scope-stage-user",
            case_id="synthetic-restricted-scope-stage-case",
            chat_id="synthetic-restricted-scope-stage-chat",
            workspace_model_id="broker_reports_gate1_pipe",
            normalization_run_id=package["normalization_run"]["run_id"],
            allow_private=True,
            require_source_available=True,
        )
        persisted = persist_gate1_result(
            store=store,
            result=result,
            context=context,
            retention_policy=build_retention_policy(mode="api_smoke"),
            source_file_refs=[
                {
                    "provider": "synthetic_stage_smoke",
                    "openwebui_file_id": f"synthetic-stage-{index}",
                    "content_type": item.mime_type,
                    "size_bytes": item.declared_size_bytes,
                    "source_deleted": False,
                }
                for index, item in enumerate(inputs, start=1)
            ],
        )
        dcp_ref = persisted.artifact_refs_by_type["domain_context_packet_v0"][0]
        before = store.list_by_run(context.normalization_run_id)
        readiness = Gate2InputReadinessFactory(store=store).create().audit_and_build(
            domain_context_packet_ref=dcp_ref,
            context=context,
        )
        after = store.list_by_run(context.normalization_run_id)

        package_document_refs = {
            item["document_ref"] for item in readiness.packages
        }
        typed_packages = [
            item
            for item in readiness.packages
            if isinstance(item.get("typed_source_facts"), dict)
        ]
        provider_calls = sum(
            item.get("prompt_contract", {}).get("model_call_performed") is True
            for item in readiness.packages
        )
        checks = {
            "normalization_validation_passed": package["validation_result"]["status"]
            == "passed",
            "zip_container_lineage_only": zip_memory["gate2_memory_status"]
            == "lineage_only",
            "zip_container_in_archive_lineage_refs": zip_ref
            in next_refs["archive_lineage_refs"],
            "zip_container_not_source_fact_ready": zip_ref
            not in next_refs["source_fact_ready_refs"],
            "promoted_member_source_fact_ready": member_ref
            in next_refs["source_fact_ready_refs"],
            "promoted_member_package_built": member_ref in package_document_refs,
            "fns_typed_output_validated": len(typed_packages) == 1
            and typed_packages[0]["typed_source_facts"]["terminal_status"]
            == "validated",
            "visual_scope_ready_but_consumer_restricted": (
                visual_memory["source_scope"]["scope_readiness"]["visual_scope"]
                == "ready"
                and visual_ref not in next_refs["source_fact_ready_refs"]
                and visual_ref not in package_document_refs
            ),
            "visual_provider_not_used": bool(visual_units)
            and all(item.get("ocr_vlm_used") is False for item in visual_units),
            "gate2_validator_passed": readiness.validation["validator_status"]
            == "passed",
            "gate2_errors_zero": readiness.validation["errors_count"] == 0,
            "package_preparation_provider_calls_zero": provider_calls == 0,
            "sber_profile_disabled_by_default": (
                NormalizedTableProjectionConfig().broker_pdf_neutral_table_profile_v1_enabled
                is False
            ),
            "artifactstore_unchanged_after_gate2": [item.artifact_id for item in before]
            == [item.artifact_id for item in after],
            "knowledge_records_zero": readiness.validation["knowledge_records"] == 0
            and all(item.storage_backend != "openwebui_knowledge" for item in before),
        }
        return {
            "schema_version": "broker_reports_restricted_scope_stage_smoke_safe_v1",
            "status": "passed" if all(checks.values()) else "failed",
            "checks": checks,
            "accounting": {
                "source_records": len(memory["documents"]),
                "archive_containers": 1,
                "promoted_members": 1,
                "source_ready_documents": readiness.validation["source_ready_refs_total"],
                "packages": readiness.validation["packages_total"],
                "fns_typed_packages": readiness.validation[
                    "fns_2ndfl_typed_packages_total"
                ],
                "provider_calls": provider_calls,
                "package_unit_kind_counts": dict(
                    sorted(
                        Counter(
                            str(item["source_unit"].get("unit_kind"))
                            for item in readiness.packages
                        ).items()
                    )
                ),
            },
            "operational_valves": {
                "broker_pdf_neutral_table_profile_v1_enabled": False,
                "visual_provider_transfer_enabled": False,
            },
            "bundle": {"repository_bundle_sha256": REPOSITORY_BUNDLE_SHA256},
            "privacy": {
                "synthetic_inputs_only": True,
                "customer_values_included": False,
                "knowledge_rag_used": False,
                "vectorization_performed": False,
            },
        }


def main() -> int:
    proof = build_proof()
    print(json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if proof["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
