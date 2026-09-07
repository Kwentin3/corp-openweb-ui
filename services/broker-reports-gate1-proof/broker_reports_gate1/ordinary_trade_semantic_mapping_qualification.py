"""Local-only qualification seam for ordinary-trade semantic mapping.

This module deliberately has no ArtifactStore, case, projection or declaration
dependency.  It is a small R&D runner over an already frozen Canonical: the
production semantic owner builds the package and validates the one model
response, while this runner returns a receipt containing only hashes, counts
and verdicts.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .canonical_artifact import validate_canonical_artifact
from .gate2_model_contracts import Gate2StructuredModelClient, Gate2StructuredModelResult
from .ordinary_trade_semantic_mapping import OrdinaryTradeSemanticMappingFactory


QUALIFICATION_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_semantic_mapping_qualification_receipt_v1"
)


class OrdinaryTradeSemanticMappingQualificationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class OrdinaryTradeSemanticMappingQualificationFactory:
    """Construct the local runner with an explicitly injected model client."""

    def __init__(self, *, model_client: Gate2StructuredModelClient) -> None:
        self._model_client = model_client

    def create(self) -> "OrdinaryTradeSemanticMappingQualificationRunner":
        if self._model_client is None:
            raise OrdinaryTradeSemanticMappingQualificationError(
                "ordinary_trade_mapping_qualification_client_required"
            )
        return OrdinaryTradeSemanticMappingQualificationRunner(
            model_client=self._model_client,
            semantic=OrdinaryTradeSemanticMappingFactory.create(),
        )


class OrdinaryTradeSemanticMappingQualificationRunner:
    def __init__(self, *, model_client: Gate2StructuredModelClient, semantic: Any) -> None:
        self._model_client = model_client
        self._semantic = semantic

    async def run(
        self,
        *,
        fixture: Mapping[str, Any],
        model_id: str,
        provider_profile_id: str,
    ) -> dict[str, Any]:
        """Perform exactly one strict mapping call and return a value-free receipt."""

        input_data = _validated_fixture(fixture)
        package = self._semantic.build_mapping_package(
            canonical=input_data["canonical"],
            confirmed_understandings=input_data["confirmed_understandings"],
            target_table_node_ids=input_data["target_table_node_ids"],
        )
        response = await self._model_client.extract(
            prompt=self._semantic.mapping_prompt(),
            package=package,
            model_id=model_id,
            response_format=self._semantic.mapping_response_format(),
        )
        _require_one_strict_result(response)
        failure = self._semantic.mapping_response_contract_failure_code(response)
        if failure is not None:
            raise OrdinaryTradeSemanticMappingQualificationError(failure)
        outcome = self._semantic.validate_mapping_response(
            response=response,
            canonical=input_data["canonical"],
            canonical_binding=input_data["canonical_binding"],
            model_id=model_id,
            provider_profile_id=provider_profile_id,
            execution_metadata=response.execution_metadata,
            confirmed_understandings=input_data["confirmed_understandings"],
            user_scope_sha256=input_data["user_scope_sha256"],
            target_table_node_ids=input_data["target_table_node_ids"],
            frozen_mappings=input_data["frozen_mappings"],
        )
        verdict = _safe_verdict(outcome, response=response)
        expected = input_data["expected_verdict"]
        if any(verdict.get(key) != value for key, value in expected.items()):
            raise OrdinaryTradeSemanticMappingQualificationError(
                "ordinary_trade_mapping_qualification_verdict_mismatch"
            )
        return {
            "schema_version": QUALIFICATION_RECEIPT_SCHEMA_VERSION,
            "status": "PASSED",
            "provider_calls_total": 1,
            "fixture_sha256": _sha256(input_data["fixture_identity"]),
            "prompt_version": self._semantic.mapping_prompt().version,
            "prompt_sha256": _sha256(self._semantic.mapping_prompt().content),
            "response_format_sha256": _sha256(self._semantic.mapping_response_format()),
            "package_sha256": _sha256(package),
            "execution_metadata_sha256": _sha256(response.execution_metadata),
            "table_count": len(package["case"]["tables"]),
            "verdict": verdict,
        }


def load_frozen_fixture(path: str | Path) -> dict[str, Any]:
    """Read one local fixture JSON; provider setup remains caller-owned."""

    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OrdinaryTradeSemanticMappingQualificationError(
            "ordinary_trade_mapping_qualification_fixture_json_invalid"
        ) from exc
    return _validated_fixture(value)


def _validated_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "canonical",
        "canonical_binding",
        "user_scope_sha256",
        "expected_verdict",
        "confirmed_understandings",
        "target_table_node_ids",
        "frozen_mappings",
        "fixture_identity",
    }
    if not isinstance(fixture, Mapping) or set(fixture) != required:
        raise OrdinaryTradeSemanticMappingQualificationError(
            "ordinary_trade_mapping_qualification_fixture_invalid"
        )
    canonical_binding = fixture["canonical_binding"]
    if (
        not isinstance(fixture["canonical"], Mapping)
        or not isinstance(canonical_binding, Mapping)
        or not isinstance(fixture["user_scope_sha256"], str)
        or not fixture["user_scope_sha256"]
        or not isinstance(fixture["expected_verdict"], Mapping)
        or not isinstance(fixture["confirmed_understandings"], list)
        or not isinstance(fixture["frozen_mappings"], list)
        or not isinstance(fixture["fixture_identity"], Mapping)
        or fixture["target_table_node_ids"] is not None
        and not isinstance(fixture["target_table_node_ids"], list)
    ):
        raise OrdinaryTradeSemanticMappingQualificationError(
            "ordinary_trade_mapping_qualification_fixture_invalid"
        )
    validation = validate_canonical_artifact(dict(fixture["canonical"]))
    if validation.get("passed") is not True:
        raise OrdinaryTradeSemanticMappingQualificationError(
            "ordinary_trade_mapping_qualification_canonical_invalid"
        )
    _validate_exact_canonical_binding(
        canonical=fixture["canonical"], canonical_binding=canonical_binding
    )
    allowed_expected = {
        "status",
        "qualified_mapping_count",
        "qualification_receipt_count",
        "table_resolution_count",
        "currency_table_count",
        "role_map_sha256",
    }
    if (
        not fixture["expected_verdict"]
        or not set(fixture["expected_verdict"]).issubset(allowed_expected)
        or not isinstance(fixture["expected_verdict"].get("role_map_sha256"), str)
        or len(fixture["expected_verdict"]["role_map_sha256"]) != 64
    ):
        raise OrdinaryTradeSemanticMappingQualificationError(
            "ordinary_trade_mapping_qualification_expected_verdict_invalid"
        )
    return dict(fixture)


def _require_one_strict_result(response: Any) -> None:
    if (
        not isinstance(response, Gate2StructuredModelResult)
        or response.structured_output_mode != "openwebui_response_format_json_schema"
        or response.response_format_type != "json_schema"
        or response.response_format_schema_mode != "strict_json_schema"
        or response.fallback_used is not False
        or response.repair_attempt_count != 0
        or response.execution_metadata is None
    ):
        raise OrdinaryTradeSemanticMappingQualificationError(
            "ordinary_trade_mapping_qualification_strict_output_required"
        )


def _safe_verdict(
    outcome: Mapping[str, Any], *, response: Gate2StructuredModelResult
) -> dict[str, Any]:
    return {
        "status": outcome.get("status"),
        "qualified_mapping_count": len(outcome.get("qualified_mappings") or []),
        "qualification_receipt_count": len(outcome.get("qualification_receipts") or []),
        "table_resolution_count": len(outcome.get("table_resolutions") or []),
        "currency_table_count": len(outcome.get("currency_table_node_ids") or []),
        "role_map_sha256": safe_role_map_sha256(response),
    }


def safe_role_map_sha256(response: Gate2StructuredModelResult | Mapping[str, Any]) -> str:
    """Hash the model's per-table decision map without retaining source content."""

    value = getattr(response, "content", response)
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, Mapping) or not isinstance(value.get("table_decisions"), list):
        raise OrdinaryTradeSemanticMappingQualificationError(
            "ordinary_trade_mapping_qualification_response_map_invalid"
        )
    projection = [
        {
            "table_ref": decision["table_ref"],
            "header_row": decision["header_row"],
            "disposition": decision["disposition"],
            "columns": sorted(
                [
                    {
                        "column": column["column"],
                        "semantic_role": column["semantic_role"],
                    }
                    for column in decision["columns"]
                ],
                key=lambda item: item["column"],
            ),
            "amount_currency_bindings": sorted(
                [
                    {
                        "amount_column": binding["amount_column"],
                        "currency_column": binding["currency_column"],
                    }
                    for binding in decision["amount_currency_bindings"]
                ],
                key=lambda item: item["amount_column"],
            ),
            "side_values": sorted(
                [
                    {
                        "source_literal": side["source_literal"],
                        "normalized_value": side["normalized_value"],
                    }
                    for side in decision["side_values"]
                ],
                key=lambda item: item["source_literal"],
            ),
            "row_dispositions": sorted(
                [
                    {"row": row["row"], "disposition": row["disposition"]}
                    for row in decision["row_dispositions"]
                ],
                key=lambda item: item["row"],
            ),
            **(
                {"no_consumer_kind": decision["no_consumer_kind"]}
                if "no_consumer_kind" in decision
                else {}
            ),
        }
        for decision in value["table_decisions"]
    ]
    return _sha256(sorted(projection, key=lambda item: item["table_ref"]))


def _validate_exact_canonical_binding(
    *, canonical: Mapping[str, Any], canonical_binding: Mapping[str, Any]
) -> None:
    required = {
        "document_id",
        "canonical_version_id",
        "canonical_root_sha256",
        "source_artifact_ref",
        "source_sha256",
    }
    source = canonical.get("source") or {}
    if (
        set(canonical_binding) != required
        or not all(
            isinstance(canonical_binding.get(key), str) and canonical_binding[key]
            for key in required
        )
        or canonical_binding["canonical_root_sha256"]
        != canonical.get("canonical_root_hash")
        or canonical_binding["source_artifact_ref"]
        != source.get("source_artifact_ref")
        or canonical_binding["source_sha256"] != source.get("source_sha256")
    ):
        raise OrdinaryTradeSemanticMappingQualificationError(
            "ordinary_trade_mapping_qualification_canonical_binding_invalid"
        )


def _sha256(value: Any) -> str:
    if hasattr(value, "__dict__"):
        value = value.__dict__
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = [
    "QUALIFICATION_RECEIPT_SCHEMA_VERSION",
    "OrdinaryTradeSemanticMappingQualificationError",
    "OrdinaryTradeSemanticMappingQualificationFactory",
    "OrdinaryTradeSemanticMappingQualificationRunner",
    "load_frozen_fixture",
    "safe_role_map_sha256",
]
