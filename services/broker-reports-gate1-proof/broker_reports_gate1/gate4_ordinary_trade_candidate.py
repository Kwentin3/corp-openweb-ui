"""Gate 4 fact adapter for the ordinary-trade production candidate."""

from __future__ import annotations

import copy
from typing import Any

from .artifact_models import ArtifactAccessContext
from .gate4_financial_case_materialization import (
    GATE4_FINANCIAL_CASE_FACT_SCHEMA_VERSION,
    gate4_financial_case_fact_id,
)
from .ordinary_trade_projection import OrdinaryTradeProjectionFactory


_FACT_V2_HISTORICAL_ANNOTATION_SCHEMA_DISCRIMINATOR = (
    "broker_reports_financial_annotations_v2"
)
GATE4_ORDINARY_TRADE_CURRENT_FACT_SET_SCHEMA_VERSION = (
    "broker_reports_gate4_ordinary_trade_current_fact_set_v1"
)
GATE4_ORDINARY_TRADE_BLOCKER_SCHEMA_VERSION = (
    "broker_reports_gate4_ordinary_trade_blocker_v1"
)
GATE4_ORDINARY_TRADE_SECURITY_POSITION_SOURCE_CONTRACT_MISSING = (
    "gate4_ordinary_trade_security_position_source_contract_missing"
)


FACTORY_REQUIRED = (
    "Gate4OrdinaryTradeCandidateRuntimeFactory.create is the only projection "
    "to existing Gate 4 fact contract adapter entrypoint"
)
FORBIDDEN = (
    "Canonical reads, LLM calls, financial classification, value invention, "
    "value-based deduplication, tax logic or a second SQL cache"
)


class Gate4OrdinaryTradeCandidateError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Gate4OrdinaryTradeCandidateRuntimeFactory:
    def __init__(self, *, store: Any, read_enabled: bool) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> "Gate4OrdinaryTradeCandidateRuntime":
        return Gate4OrdinaryTradeCandidateRuntime(
            projections=OrdinaryTradeProjectionFactory(
                store=self._store,
                read_enabled=self._read_enabled,
            ).create()
        )


class Gate4OrdinaryTradeCandidateRuntime:
    """Expose candidate records through the existing Gate 4 fact shape."""

    def __init__(self, *, projections: Any) -> None:
        self._projections = projections

    def current_fact_set(
        self, *, context: ArtifactAccessContext
    ) -> dict[str, Any]:
        case_binding = _case_binding(context)
        facts: list[dict[str, Any]] = []
        projections = self._projections.current_case(context=context)
        for record, projection in projections:
            projection_binding = projection["canonical_binding"]
            canonical_binding = {
                "document_id": projection_binding["document_id"],
                "canonical_version_id": projection_binding["canonical_version_id"],
            }
            observations = {
                item["observation_id"]: item
                for item in projection["source_observations"]
            }
            for annotation_index, runtime_record in enumerate(
                projection["runtime_records"]
            ):
                observation = observations.get(
                    runtime_record.get("source_observation_id")
                )
                mapping_id = (
                    observation.get("mapping_id")
                    if isinstance(observation, dict)
                    else None
                )
                if not isinstance(mapping_id, str) or not mapping_id.startswith(
                    "otmap_"
                ):
                    raise Gate4OrdinaryTradeCandidateError(
                        "gate4_ordinary_trade_mapping_authority_invalid"
                    )
                semantic_binding = {
                    "dictionary": {
                        "authority_id": (
                            f"ordinary_trade_schema_mapping:{mapping_id}"
                        ),
                        "semantic_version": "1.0.0",
                    },
                    "role_pack": {
                        "authority_id": "ordinary_trade_runtime_projection",
                        "semantic_version": "1.0.0",
                    },
                }
                roles = [_fact_role(item) for item in runtime_record["roles"]]
                fact = {
                    "schema_version": GATE4_FINANCIAL_CASE_FACT_SCHEMA_VERSION,
                    "fact_id": "",
                    "case_binding": copy.deepcopy(case_binding),
                    # Historical field names and the v2 discriminator are
                    # retained by the published Gate 4/5 compatibility port.
                    # The artifact id binds the candidate projection; current
                    # Gate 3 is not executed on this route.
                    "gate3_binding": {
                        "financial_annotations_artifact_id": record.artifact_id,
                        "financial_annotations_schema_version": (
                            _FACT_V2_HISTORICAL_ANNOTATION_SCHEMA_DISCRIMINATOR
                        ),
                        "annotation_index": annotation_index,
                        "canonical_binding": copy.deepcopy(canonical_binding),
                    },
                    "semantic_kind": "normalized_source_fact",
                    "semantic_binding": copy.deepcopy(semantic_binding),
                    "financial_type": runtime_record["record_type"],
                    "annotation_target": copy.deepcopy(
                        runtime_record["annotation_target"]
                    ),
                    "roles": roles,
                    "status": "role_complete",
                }
                fact["fact_id"] = gate4_financial_case_fact_id(fact)
                _validate_compatibility_fact(fact)
                facts.append(fact)
        ids = [item["fact_id"] for item in facts]
        if len(ids) != len(set(ids)):
            raise Gate4OrdinaryTradeCandidateError(
                "gate4_ordinary_trade_fact_duplicate"
            )
        security_facts = [
            item
            for item in facts
            if item["financial_type"] in {"SECURITY_PURCHASE", "SECURITY_DISPOSAL"}
        ]
        relevant_unmapped = any(
            observation.get("disposition") == "RELEVANT_UNMAPPED"
            for _record, projection in projections
            for observation in projection["source_observations"]
        )
        blockers = []
        if projections and not security_facts and not relevant_unmapped:
            blockers.append(
                {
                    "schema_version": GATE4_ORDINARY_TRADE_BLOCKER_SCHEMA_VERSION,
                    "reason_code": (
                        GATE4_ORDINARY_TRADE_SECURITY_POSITION_SOURCE_CONTRACT_MISSING
                    ),
                    "required_input": (
                        "ordinary_trade_projection.runtime_records."
                        "security_position_semantics"
                    ),
                    "gap_owner_classification": (
                        "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT"
                    ),
                    "owner": "Gate4OrdinaryTradeCandidateRuntime",
                    "blocking_scope": (
                        "active_security_position_source_contract"
                    ),
                }
            )
        return {
            "schema_version": GATE4_ORDINARY_TRADE_CURRENT_FACT_SET_SCHEMA_VERSION,
            "status": (
                "SECURITY_POSITION_SOURCE_CONTRACT_MISSING"
                if blockers
                else "READY"
            ),
            "facts": copy.deepcopy(facts),
            "blockers": copy.deepcopy(blockers),
        }

    def list_facts(
        self, *, context: ArtifactAccessContext
    ) -> list[dict[str, Any]]:
        return self.current_fact_set(context=context)["facts"]


def _case_binding(context: ArtifactAccessContext) -> dict[str, str]:
    if (
        not isinstance(context, ArtifactAccessContext)
        or not context.user_id
        or not context.case_id
        or not context.allow_private
    ):
        raise Gate4OrdinaryTradeCandidateError(
            "gate4_ordinary_trade_private_case_context_required"
        )
    return {"scope_kind": "case", "scope_id": context.case_id}


def _fact_role(item: dict[str, Any]) -> dict[str, Any]:
    binding = item.get("source_binding")
    cell = binding.get("canonical_cell") if isinstance(binding, dict) else None
    if (
        not isinstance(cell, dict)
        or not isinstance(cell.get("node_id"), str)
        or not isinstance(cell.get("row"), int)
        or not isinstance(cell.get("column"), int)
        or not isinstance(binding.get("source_literal"), str)
        or not binding["source_literal"]
    ):
        raise Gate4OrdinaryTradeCandidateError(
            "gate4_ordinary_trade_role_source_invalid"
        )
    return {
        "role": item["role"],
        "requirement": "required",
        "status": "value",
        "value": item["value"],
        "source_binding": {
            "target": {
                "kind": "table_cell",
                "node_id": cell["node_id"],
                "row": cell["row"],
                "column": cell["column"],
            },
            "exact_text": binding["source_literal"],
            "source_literal": binding["source_literal"],
        },
    }


def _validate_compatibility_fact(fact: dict[str, Any]) -> None:
    """Fail closed before the candidate crosses the published Fact v2 port."""

    binding = fact.get("gate3_binding")
    semantic = fact.get("semantic_binding")
    roles = fact.get("roles")
    if (
        fact.get("schema_version") != GATE4_FINANCIAL_CASE_FACT_SCHEMA_VERSION
        or fact.get("fact_id") != gate4_financial_case_fact_id(fact)
        or not isinstance(binding, dict)
        or binding.get("financial_annotations_schema_version")
        != _FACT_V2_HISTORICAL_ANNOTATION_SCHEMA_DISCRIMINATOR
        or not isinstance(semantic, dict)
        or set(semantic) != {"dictionary", "role_pack"}
        or not isinstance(roles, list)
        or not roles
        or any(
            not isinstance(item, dict)
            or set(item)
            != {"role", "requirement", "status", "value", "source_binding"}
            or set(item.get("source_binding", {}))
            != {"target", "exact_text", "source_literal"}
            for item in roles
        )
    ):
        raise Gate4OrdinaryTradeCandidateError(
            "gate4_ordinary_trade_fact_contract_invalid"
        )


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE4_ORDINARY_TRADE_BLOCKER_SCHEMA_VERSION",
    "GATE4_ORDINARY_TRADE_CURRENT_FACT_SET_SCHEMA_VERSION",
    "GATE4_ORDINARY_TRADE_SECURITY_POSITION_SOURCE_CONTRACT_MISSING",
    "Gate4OrdinaryTradeCandidateError",
    "Gate4OrdinaryTradeCandidateRuntime",
    "Gate4OrdinaryTradeCandidateRuntimeFactory",
]
