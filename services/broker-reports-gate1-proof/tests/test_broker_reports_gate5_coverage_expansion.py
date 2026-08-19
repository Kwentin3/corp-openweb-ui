from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
from types import SimpleNamespace

from broker_reports_gate1.artifact_models import ArtifactAccessContext
from broker_reports_gate1.artifact_retention import build_retention_policy
from broker_reports_gate1.artifact_store import ArtifactStoreConfig, ArtifactStoreFactory
from broker_reports_gate1.gate2_handoff import persist_gate1_result
from broker_reports_gate1.gate2_model_clients import (
    Gate2StructuredModelClientConfig,
    Gate2StructuredModelClientFactory,
)
from broker_reports_gate1.gate2_model_requests import (
    GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
)
from broker_reports_gate1.gate3_ndfl_workflow import NdflWorkflowFactory
from broker_reports_gate1.gate4_financial_case_cache import (
    CASE_COMPLETE_FOR_CURRENT_INPUT_SET,
    Gate4FinancialCaseRuntimeFactory,
)
from broker_reports_gate1.gate5_end_to_end_full_target_xml import (
    FACTORY_REQUIRED as END_TO_END_FACTORY_REQUIRED,
    FORBIDDEN as END_TO_END_FORBIDDEN,
    GATE5_END_TO_END_STATUS,
    Gate5EndToEndFullTargetXmlRuntimeFactory,
    Gate5EndToEndSuppliedCaseAuthorityFactory,
)
from broker_reports_gate1.gate5_openwebui_product import (
    FACTORY_REQUIRED as PRODUCT_FACTORY_REQUIRED,
    FORBIDDEN as PRODUCT_FORBIDDEN,
)
from broker_reports_gate1.inputs import FileInput
from broker_reports_gate1.normalizer import Gate1Normalizer


SERVICE_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = SERVICE_ROOT / "tests/fixtures"
MODEL_ID = "models/gemini-3.5-flash"
PROVIDER_PROFILE_ID = "google_gemini"
SAMPLES = (
    (
        "baseline",
        FIXTURES / "g536_openwebui_broker.csv",
        "text/csv",
        "completed",
    ),
    (
        "html",
        FIXTURES / "g537_russian_vocabulary_disposal.html",
        "text/html",
        "completed_with_blockers",
    ),
    (
        "xlsx",
        FIXTURES / "g537_multisheet_disposal.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "completed",
    ),
)


def test_versioned_corpus_hashes_origins_and_binary_builder_are_exact() -> None:
    manifest = json.loads(
        (FIXTURES / "g537_coverage_corpus.v0.json").read_text(encoding="utf-8")
    )
    assert manifest["schema_version"] == "broker_reports_gate5_coverage_corpus_v0"
    assert manifest["corpus_version"] == "2026-08-11.0"
    samples = manifest["samples"]
    assert len(samples) == 4
    assert len({item["sample_id"] for item in samples}) == len(samples)

    for sample in samples:
        origin = sample["evidence_origin"]
        repository_path = origin.get("repository_path")
        if repository_path:
            source = SERVICE_ROOT / repository_path
            assert source.is_file()
            assert hashlib.sha256(source.read_bytes()).hexdigest() == sample[
                "content_sha256"
            ]
        else:
            assert sample["sample_id"] == "g537_tbank_public_pdf_purchase"
            assert origin["repository_bytes_present"] is False
            assert origin["source_url"].startswith("https://cdn.tbank.ru/")
            assert sample["real_broker_format_claimed"] is True

    builder_path = SERVICE_ROOT / "scripts/build_gate5_coverage_corpus_fixtures.py"
    spec = importlib.util.spec_from_file_location("g537_fixture_builder", builder_path)
    assert spec is not None and spec.loader is not None
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    assert builder.build() == (FIXTURES / "g537_multisheet_disposal.xlsx").read_bytes()


def test_csv_html_and_xlsx_converge_to_same_gate4_tax_declaration_and_xml(
    tmp_path: Path,
) -> None:
    outcomes = {
        label: _run_product_route(
            source_path=source_path,
            mime_type=mime_type,
            label=label,
            root=tmp_path / label,
            expected_gate1_status=gate1_status,
        )
        for label, source_path, mime_type, gate1_status in SAMPLES
    }
    baseline = outcomes["baseline"]
    for label, outcome in outcomes.items():
        assert outcome["terminal"] == GATE5_END_TO_END_STATUS
        assert outcome["official_xsd_valid"] is True
        assert outcome["gate4_semantics"] == baseline["gate4_semantics"], label
        assert outcome["declaration_semantics"] == baseline[
            "declaration_semantics"
        ], label
        assert outcome["domain_semantics"] == baseline["domain_semantics"], label
        assert outcome["xml_bytes"] == baseline["xml_bytes"], label
        assert outcome["role_provider_calls"] == 1
        assert outcome["provider_calls"] >= 2

    assert outcomes["html"]["gate1_blocker_codes"] == ["unknown_role"]
    assert outcomes["xlsx"]["gate1_blocker_codes"] == []
    assert outcomes["xlsx"]["source_transport"] == "content_base64"
    assert outcomes["html"]["source_transport"] == "content_utf8"


def test_coverage_extension_preserves_factory_route_and_no_broker_tax_coupling() -> None:
    assert len(END_TO_END_FACTORY_REQUIRED) == 6
    assert END_TO_END_FORBIDDEN
    assert "Gate5OpenWebUIProductRuntimeFactory.create" in PRODUCT_FACTORY_REQUIRED
    assert PRODUCT_FORBIDDEN

    downstream = (
        "gate5_securities_disposal_tax_model.py",
        "gate5_tax_period_category_aggregation.py",
        "gate5_resolved_declaration_package.py",
        "gate5_declaration_semantic_input.py",
        "gate5_full_target_xml_projection.py",
    )
    source = "\n".join(
        (SERVICE_ROOT / "broker_reports_gate1" / name).read_text(encoding="utf-8")
        for name in downstream
    ).lower()
    for forbidden in (
        "g537",
        "tbank",
        "t-bank",
        "тинькофф",
        "реализация",
        "вид операции",
        "xlsx",
        "html_text",
    ):
        assert forbidden not in source

    browser_script = (
        SERVICE_ROOT / "scripts/live_gate5_openwebui_browser_proof.mjs"
    ).read_text(encoding="utf-8")
    assert "G536_SOURCE_MIME_TYPE" in browser_script
    assert 'new File([bytes], filename, { type: mimeType })' in browser_script
    assert "Gate5EndToEndFullTargetXmlRuntimeFactory" not in browser_script


def _run_product_route(
    *,
    source_path: Path,
    mime_type: str,
    label: str,
    root: Path,
    expected_gate1_status: str,
) -> dict[str, object]:
    root.mkdir(parents=True)
    source_bytes = source_path.read_bytes()
    source_file_id = f"g537-{label}-source"
    file_input = FileInput.from_bytes(
        private_ref=source_file_id,
        filename=source_path.name,
        content=source_bytes,
        mime_type=mime_type,
        source_kind="synthetic",
    )
    normalizer = Gate1Normalizer()
    normalization_run_id = normalizer.plan_run_id([file_input])
    normalization = normalizer.normalize(
        [file_input],
        entrypoint="broker_reports_gate1_pipe",
        trigger_type="pipe_backend_normalizer",
        input_context={
            "canonical_gate2_write_enabled": True,
            "canonical_gate2_read_enabled": True,
            "normalizer_version": "g537-coverage-proof-v0",
        },
    )
    assert normalization.package["normalization_run"]["run_status"] == (
        expected_gate1_status
    )

    proof = Gate5EndToEndSuppliedCaseAuthorityFactory.create().load()
    binding = proof["binding"]
    binding["case_id"] = f"g537-{label}-case"
    binding["normalization_run_ref"] = normalization_run_id
    context = ArtifactAccessContext(
        user_id=binding["authenticated_user_ref"],
        normalization_run_id=normalization_run_id,
        case_id=binding["case_id"],
        workspace_model_id=binding["workspace_model_id"],
        allow_private=True,
        require_source_available=True,
    )
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()
    retention = build_retention_policy(mode="synthetic_dev")
    manifest = persist_gate1_result(
        store=store,
        result=normalization,
        context=context,
        retention_policy=retention,
        source_file_refs=[
            {
                "provider": "openwebui",
                "openwebui_file_id": source_file_id,
                "source_deleted": False,
            }
        ],
    )
    canonical_refs = manifest.artifact_refs_by_type.get(
        "broker_reports_canonical_artifact_v1", []
    )
    assert len(canonical_refs) == 1

    model_client, captured = _proposal_model_client(user_id=context.user_id)
    execution = asyncio.run(
        NdflWorkflowFactory(
            store=store,
            read_enabled=True,
            model_client=model_client,
            model_id=MODEL_ID,
            provider_profile_id=PROVIDER_PROFILE_ID,
        )
        .create()
        .run_product_path(
            canonical_artifact_ref=canonical_refs[0],
            context=context,
        )
    )

    proof["case_fact_set_id"] = f"g537_{label}_supplied_case"
    proof["case_fact_set_version"] = "2026-08-11.0"
    source = proof["supplied_source"]
    source.update(
        {
            "private_ref": source_file_id,
            "filename": source_path.name,
            "mime_type": mime_type,
            "content_sha256": hashlib.sha256(source_bytes).hexdigest(),
        }
    )
    source["custody"]["openwebui_file_id"] = source_file_id
    source.pop("content_utf8", None)
    source.pop("content_base64", None)
    try:
        source["content_utf8"] = source_bytes.decode("utf-8")
        source_transport = "content_utf8"
    except UnicodeDecodeError:
        source["content_base64"] = base64.b64encode(source_bytes).decode("ascii")
        source_transport = "content_base64"

    result = Gate5EndToEndFullTargetXmlRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=retention,
        gate3_model_client=model_client,
        gate3_model_id=MODEL_ID,
        gate3_provider_profile_id=PROVIDER_PROFILE_ID,
    ).create().continue_from_validated_gate3(
        proof_input=proof,
        context=context,
        financial_annotations_artifact_id=execution.gate3.annotations_artifact_id,
    )
    financial_case = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create().rebuild_case(context=context)
    assert financial_case.status == CASE_COMPLETE_FOR_CURRENT_INPUT_SET
    role_calls = sum(
        item["response_format"]["json_schema"]["name"]
        == "broker_reports_gate3_role_labeling_response_v1"
        for item in captured
    )
    semantic_input = result["semantic_input"]
    return {
        "terminal": result["status"],
        "official_xsd_valid": result["receipt"]["target_result"][
            "conformance_proof"
        ]["xsd_valid"],
        "gate1_blocker_codes": sorted(
            {item["code"] for item in normalization.package["normalization_blockers"]}
        ),
        "gate4_semantics": _gate4_semantics(financial_case.facts),
        "declaration_semantics": semantic_input["declaration_semantics"],
        "domain_semantics": _domain_semantics(semantic_input["domains"]),
        "xml_bytes": result["xml_bytes"],
        "provider_calls": len(captured),
        "role_provider_calls": role_calls,
        "source_transport": source_transport,
    }


def _proposal_model_client(*, user_id: str):
    captured: list[dict] = []

    def complete(*, form_data, **_kwargs):
        captured.append(copy.deepcopy(form_data))
        schema_name = form_data["response_format"]["json_schema"]["name"]
        aliases = _transaction_aliases(form_data["messages"][-1]["content"])
        if schema_name == "broker_reports_gate3_labeling_response_v1":
            response = {
                "schema_version": schema_name,
                "annotations": (
                    []
                    if aliases is None
                    else [
                        {
                            "target_alias": aliases["target"],
                            "financial_label": "SECURITY_DISPOSAL",
                        }
                    ]
                ),
            }
        else:
            assert schema_name == "broker_reports_gate3_role_labeling_response_v1"
            assert aliases is not None
            response = {
                "schema_version": schema_name,
                "facts": [
                    {
                        "fact_alias": "f001",
                        "financial_label": "SECURITY_DISPOSAL",
                        "roles": [
                            {
                                "role": role,
                                "status": "bound",
                                "target_alias": aliases[role],
                            }
                            for role in (
                                "date",
                                "asset",
                                "quantity",
                                "amount",
                                "currency",
                                "unit_price",
                            )
                        ],
                    }
                ],
            }
        return {
            "id": f"g537-boundary-proposal-{len(captured)}",
            "model": MODEL_ID,
            "choices": [
                {
                    "message": {
                        "content": json.dumps(response, ensure_ascii=False)
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
            },
        }

    user = SimpleNamespace(id=user_id)
    client = Gate2StructuredModelClientFactory(
        config=Gate2StructuredModelClientConfig(
            request_profile=GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
            provider_profile_id=PROVIDER_PROFILE_ID,
        ),
        user=user,
        request=SimpleNamespace(),
        completion_resolver=lambda _user_id: (complete, user),
    ).create()
    return client, captured


def _transaction_aliases(content: str) -> dict[str, str] | None:
    rows = [
        _alias_cells(line)
        for line in content.splitlines()
        if line.startswith("|")
        and "2025-02-11" in line
        and "ASSET-G536" in line
        and "RUB" in line
    ]
    if len(rows) != 1:
        return None
    row = rows[0]

    def aliases_for(value: str) -> list[str]:
        return [alias for alias, literal in row if literal == value]

    money = aliases_for("100.00")
    assert len(money) == 2
    return {
        "target": row[0][0],
        "date": aliases_for("2025-02-11")[0],
        "asset": aliases_for("ASSET-G536")[0],
        "quantity": aliases_for("1")[0],
        "unit_price": money[0],
        "amount": money[1],
        "currency": aliases_for("RUB")[0],
    }


def _alias_cells(line: str) -> list[tuple[str, str]]:
    return [
        (alias, literal.strip())
        for alias, literal in re.findall(
            r"\[(t\d+)\]\s+([^|\n]*?)\s*(?=\||$)", line
        )
    ]


def _gate4_semantics(facts: list[dict]) -> list[dict]:
    return [
        {
            "financial_type": fact["financial_type"],
            "status": fact["status"],
            "roles": {
                item["role"]: {
                    "status": item["status"],
                    "value": item.get("value"),
                }
                for item in fact["roles"]
            },
        }
        for fact in facts
    ]


def _domain_semantics(domains: list[dict]) -> list[dict]:
    return [
        {
            "domain_id": domain["domain_id"],
            "state": domain["state"],
            "semantic_payloads": [
                copy.deepcopy(item["semantic_payload"])
                for item in domain["typed_components"]
            ],
        }
        for domain in domains
    ]
