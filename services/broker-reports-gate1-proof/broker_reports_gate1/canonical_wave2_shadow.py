"""Read-only DOC29 compatibility shadows for the six Wave 2 consumers.

The shadows deliberately stop at the consumer boundary.  They use the active
canonical version through ``CanonicalReaderFactory`` and never invoke product
side effects, providers, legacy fallback, or financial interpretation.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStoreError
from .canonical_consumer_migration import (
    CANONICAL_ACCESS_DENIED,
    CANONICAL_INCOMPLETE,
    CANONICAL_OK,
    CANONICAL_STORAGE_FAILURE,
    CANONICAL_VERSION_UNSUPPORTED,
    classify_consumer_artifact,
)
from .canonical_store import CanonicalReaderFactory


FACTORY_REQUIRED = (
    "Every DOC29 Wave 2 shadow enters through CanonicalWave2ShadowFactory "
    "and CanonicalReaderFactory.create"
)
FORBIDDEN = (
    "Direct SQLite or payload reads, legacy fallback, product writes, provider "
    "requests, notifications, financial facts, and consumer cutover are forbidden"
)


@dataclass(frozen=True)
class Wave2ShadowContract:
    consumer_id: str
    source_file: str
    compatibility_contract_version: str
    projection_kind: str


WAVE2_SHADOW_CONTRACTS = (
    Wave2ShadowContract(
        "gate2_input_readiness",
        "broker_reports_gate1/gate2_input_readiness.py",
        "gate2_input_readiness_canonical_shadow_v1",
        "readiness",
    ),
    Wave2ShadowContract(
        "gate2_source_fact_runtime",
        "broker_reports_gate1/gate2_source_fact_runtime.py",
        "gate2_source_fact_runtime_canonical_shadow_v1",
        "source_fact_input",
    ),
    Wave2ShadowContract(
        "live_case_group_eligibility",
        "scripts/live_case_group_eligibility_rerun.py",
        "live_case_group_eligibility_canonical_shadow_v1",
        "eligibility",
    ),
    Wave2ShadowContract(
        "live_case_group_process_false",
        "scripts/live_case_group_process_false_gate1_run.py",
        "live_case_group_process_false_canonical_shadow_v1",
        "process_false",
    ),
    Wave2ShadowContract(
        "live_pdf_table_operator",
        "scripts/live_pdf_table_intake_gate1_operator_proof.py",
        "live_pdf_table_operator_canonical_shadow_v1",
        "table_operator",
    ),
    Wave2ShadowContract(
        "live_private_intake_smoke",
        "scripts/live_process_false_private_intake_smoke.py",
        "live_private_intake_canonical_shadow_v1",
        "private_intake",
    ),
)


@dataclass(frozen=True)
class Wave2ShadowResult:
    consumer_id: str
    compatibility_status: str
    error_code: str | None
    output: dict[str, Any] | None
    telemetry: dict[str, Any]


@dataclass
class Wave2ShadowLedger:
    events: list[dict[str, Any]] = field(default_factory=list)

    def append(self, event: dict[str, Any]) -> None:
        self.events.append(dict(event))


class CanonicalWave2ShadowFactory:
    def __init__(
        self,
        *,
        store,
        contract: Wave2ShadowContract,
        enabled: bool,
        ledger: Wave2ShadowLedger | None = None,
    ) -> None:
        if contract not in WAVE2_SHADOW_CONTRACTS:
            raise ValueError("wave2_shadow_contract_not_frozen")
        self.store = store
        self.contract = contract
        self.enabled = enabled
        self.ledger = ledger or Wave2ShadowLedger()

    def create(self) -> "CanonicalWave2Shadow":
        return CanonicalWave2Shadow(
            reader=CanonicalReaderFactory(
                store=self.store, read_enabled=self.enabled
            ).create(),
            contract=self.contract,
            ledger=self.ledger,
        )


class CanonicalWave2Shadow:
    def __init__(self, *, reader, contract, ledger) -> None:
        self._reader = reader
        self._contract = contract
        self._ledger = ledger

    def read_active(
        self, *, document_id: str, context: ArtifactAccessContext
    ) -> Wave2ShadowResult:
        started = time.perf_counter()
        try:
            envelope = self._reader.read_active_envelope(document_id, context)
        except ArtifactStoreError as exc:
            return self._blocked(exc.code, started)
        status, error = classify_consumer_artifact(envelope.artifact)
        if error:
            return self._result(
                status=status,
                error_code=error,
                output=None,
                started=started,
                payload_bytes=envelope.payload_bytes,
                chunks=envelope.component_count,
            )
        artifact = envelope.artifact
        containers = list(artifact.get("containers") or [])
        nodes = list(artifact.get("nodes") or [])
        provenance = list(artifact.get("provenance") or [])
        issues = list(artifact.get("issues") or [])
        ordered_refs = [
            *(str(item.get("container_id") or "") for item in containers),
            *(str(item.get("node_id") or "") for item in nodes),
        ]
        output = {
            "schema_version": self._contract.compatibility_contract_version,
            "projection_kind": self._contract.projection_kind,
            "containers_total": len(containers),
            "nodes_total": len(nodes),
            "tables_total": sum(item.get("node_type") == "TABLE" for item in nodes),
            "provenance_total": len(provenance),
            "issues_total": len(issues),
            "blocking_issues_total": sum(
                item.get("severity") in {"blocking", "critical"} for item in issues
            ),
            "ordering_sha256": hashlib.sha256(
                json.dumps(ordered_refs, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "physical_layout": envelope.physical_layout,
            "canonical_schema_version": envelope.schema_version,
            "provider_requests": 0,
            "product_writes": 0,
            "notifications": 0,
            "financial_facts_created": 0,
            "legacy_fallback": False,
        }
        return self._result(
            status=CANONICAL_OK,
            error_code=None,
            output=output,
            started=started,
            payload_bytes=envelope.payload_bytes,
            chunks=envelope.component_count,
        )

    def _blocked(self, code: str, started: float) -> Wave2ShadowResult:
        status = {
            "artifact_access_denied": CANONICAL_ACCESS_DENIED,
            "artifact_scope_unverified": CANONICAL_ACCESS_DENIED,
            "canonical_read_disabled": CANONICAL_INCOMPLETE,
            "canonical_version_not_active": CANONICAL_INCOMPLETE,
            "canonical_chunk_missing": CANONICAL_INCOMPLETE,
            "canonical_chunk_hash_mismatch": CANONICAL_STORAGE_FAILURE,
            "canonical_schema_version_unsupported": CANONICAL_VERSION_UNSUPPORTED,
        }.get(code, CANONICAL_STORAGE_FAILURE)
        return self._result(
            status=status,
            error_code=code,
            output=None,
            started=started,
            payload_bytes=0,
            chunks=0,
        )

    def _result(
        self,
        *,
        status: str,
        error_code: str | None,
        output: dict[str, Any] | None,
        started: float,
        payload_bytes: int,
        chunks: int,
    ) -> Wave2ShadowResult:
        event = {
            "schema_version": "broker_reports_wave2_shadow_telemetry_v1",
            "consumer_id": self._contract.consumer_id,
            "compatibility_status": status,
            "error_code": error_code,
            "canonical_read_attempts": 1,
            "canonical_read_success": int(status == CANONICAL_OK),
            "canonical_read_latency_ms": round(
                (time.perf_counter() - started) * 1000.0, 6
            ),
            "canonical_payload_bytes": payload_bytes,
            "canonical_chunks_read": chunks,
            "provider_requests": 0,
            "product_side_effects": 0,
            "legacy_fallbacks": 0,
        }
        self._ledger.append(event)
        return Wave2ShadowResult(
            consumer_id=self._contract.consumer_id,
            compatibility_status=status,
            error_code=error_code,
            output=output,
            telemetry=event,
        )
