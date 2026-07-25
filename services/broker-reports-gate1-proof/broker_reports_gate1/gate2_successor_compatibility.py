from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from .gate2_financial_evidence_compatibility import (
    Gate2FinancialEvidenceCompatibility,
    Gate2FinancialEvidenceCompatibilityFactory,
    Gate2FinancialEvidenceReadResult,
)
from .gate2_financial_evidence_materialization_contracts import (
    FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION,
    IDENTIFIER_RE,
    sha256_json,
)
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_fns_2ndfl_contracts import TYPED_FACTS_SCHEMA_VERSION
from .gate2_source_fact_contracts import SOURCE_FACTS_SCHEMA_VERSION
from .gate2_successor_artifacts import (
    SUCCESSOR_COMPATIBILITY_PROJECTION_SCHEMA_VERSION,
    SUCCESSOR_EXECUTION_RECEIPT_SCHEMA_VERSION,
    SUCCESSOR_PACKAGE_ARTIFACT_SCHEMA_VERSION,
    SUCCESSOR_RUN_ARTIFACT_SCHEMA_VERSION,
    validate_successor_compatibility_projection,
    validate_successor_execution_receipt,
    validate_successor_package_artifact,
    validate_successor_run_artifact,
)


SUCCESSOR_COMPATIBILITY_READER_POLICY_VERSION = (
    "gate2_successor_compatibility_reader_v1"
)
SUCCESSOR_COMPATIBILITY_READ_RESULT_SCHEMA_VERSION = (
    "broker_reports_gate2_successor_compatibility_read_result_v1"
)

FACTORY_REQUIRED = (
    "Gate2SuccessorCompatibilityReaderFactory.create is the only explicit "
    "dual-read dispatch entrypoint for legacy and successor artifact families"
)
FORBIDDEN = (
    "The successor reader must not rewrite legacy payloads, silently upcast "
    "schemas, adopt the separate FNS family or admit successor writes"
)

_DELEGATED_SCHEMAS = frozenset(
    {
        SOURCE_FACTS_SCHEMA_VERSION,
        FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION,
        TYPED_FACTS_SCHEMA_VERSION,
    }
)
_SUCCESSOR_VALIDATORS: dict[
    str,
    tuple[str, Callable[[dict[str, Any]], None]],
] = {
    SUCCESSOR_PACKAGE_ARTIFACT_SCHEMA_VERSION: (
        "successor_package_artifact",
        validate_successor_package_artifact,
    ),
    SUCCESSOR_RUN_ARTIFACT_SCHEMA_VERSION: (
        "successor_run_artifact",
        validate_successor_run_artifact,
    ),
    SUCCESSOR_EXECUTION_RECEIPT_SCHEMA_VERSION: (
        "successor_execution_receipt",
        validate_successor_execution_receipt,
    ),
    SUCCESSOR_COMPATIBILITY_PROJECTION_SCHEMA_VERSION: (
        "successor_compatibility_projection",
        validate_successor_compatibility_projection,
    ),
}


class Gate2SuccessorCompatibilityError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2SuccessorCompatibilityReadResult:
    schema_version: str
    reader_policy_version: str
    artifact_ref: str
    artifact_schema_version: str
    artifact_sha256: str
    read_kind: str
    validator_id: str
    validator_status: str
    records_total: int
    legacy_reader_retained: bool
    legacy_payload_rewritten: bool
    silent_conversion_used: bool
    fns_specialized_separate: bool
    compatibility_projection_ref: str | None
    payload_json: str

    def payload_copy(self) -> dict[str, Any]:
        payload = json.loads(self.payload_json)
        if not isinstance(payload, dict):
            _fail("successor_compatibility_payload_invalid")
        return payload

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "reader_policy_version": self.reader_policy_version,
            "artifact_schema_version": self.artifact_schema_version,
            "read_kind": self.read_kind,
            "validator_id": self.validator_id,
            "validator_status": self.validator_status,
            "records_total": self.records_total,
            "legacy_reader_retained": self.legacy_reader_retained,
            "legacy_payloads_rewritten_total": 0,
            "silent_conversions_total": 0,
            "fns_specialized_separate": (
                self.fns_specialized_separate
            ),
            "compatibility_projection_explicit": (
                self.compatibility_projection_ref is not None
            ),
        }


class Gate2SuccessorCompatibilityReaderFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def create(self) -> "Gate2SuccessorCompatibilityReader":
        legacy_reader = Gate2FinancialEvidenceCompatibilityFactory(
            registry=self.registry
        ).create()
        return Gate2SuccessorCompatibilityReader(
            legacy_reader=legacy_reader
        )


class Gate2SuccessorCompatibilityReader:
    def __init__(
        self,
        *,
        legacy_reader: Gate2FinancialEvidenceCompatibility,
    ) -> None:
        self._legacy_reader = legacy_reader

    def read(
        self,
        *,
        artifact_ref: str,
        payload: dict[str, Any],
    ) -> Gate2SuccessorCompatibilityReadResult:
        _identifier(artifact_ref, "artifact_ref")
        if not isinstance(payload, dict):
            _fail("successor_compatibility_payload_invalid")
        before_sha256 = sha256_json(payload)
        schema_version = payload.get("schema_version")
        if schema_version in _DELEGATED_SCHEMAS:
            result = self._delegated_read(
                artifact_ref=artifact_ref,
                payload=payload,
            )
        else:
            validator_entry = _SUCCESSOR_VALIDATORS.get(schema_version)
            if validator_entry is None:
                _fail("successor_compatibility_schema_unsupported")
            read_kind, validator = validator_entry
            validator(payload)
            result = self._successor_result(
                artifact_ref=artifact_ref,
                payload=payload,
                artifact_sha256=before_sha256,
                read_kind=read_kind,
                validator_id=f"{read_kind}_validator_v1",
            )
        if sha256_json(payload) != before_sha256:
            _fail("successor_compatibility_silent_rewrite")
        if (
            result.artifact_schema_version != schema_version
            or result.artifact_sha256 != before_sha256
            or result.legacy_payload_rewritten
            or result.silent_conversion_used
        ):
            _fail("successor_compatibility_read_result_invalid")
        return result

    def validate_successor_single_write(
        self,
        payload: dict[str, Any],
    ) -> None:
        if not isinstance(payload, dict):
            _fail("successor_compatibility_payload_invalid")
        if payload.get("schema_version") not in _SUCCESSOR_VALIDATORS:
            _fail("successor_single_write_schema_unsupported")
        _fail("successor_single_write_not_admitted")

    def _delegated_read(
        self,
        *,
        artifact_ref: str,
        payload: dict[str, Any],
    ) -> Gate2SuccessorCompatibilityReadResult:
        delegated = self._legacy_reader.read(
            artifact_ref=artifact_ref,
            payload=payload,
        )
        if delegated.artifact_schema_version == TYPED_FACTS_SCHEMA_VERSION:
            if delegated.read_kind != "fns_specialized":
                _fail("successor_compatibility_fns_dispatch_invalid")
            fns_specialized_separate = True
        else:
            fns_specialized_separate = False
        return self._from_delegated(
            delegated=delegated,
            fns_specialized_separate=fns_specialized_separate,
        )

    def _from_delegated(
        self,
        *,
        delegated: Gate2FinancialEvidenceReadResult,
        fns_specialized_separate: bool,
    ) -> Gate2SuccessorCompatibilityReadResult:
        return Gate2SuccessorCompatibilityReadResult(
            schema_version=(
                SUCCESSOR_COMPATIBILITY_READ_RESULT_SCHEMA_VERSION
            ),
            reader_policy_version=(
                SUCCESSOR_COMPATIBILITY_READER_POLICY_VERSION
            ),
            artifact_ref=delegated.artifact_ref,
            artifact_schema_version=(
                delegated.artifact_schema_version
            ),
            artifact_sha256=delegated.artifact_sha256,
            read_kind=delegated.read_kind,
            validator_id=delegated.validator_id,
            validator_status=delegated.validator_status,
            records_total=len(delegated.records),
            legacy_reader_retained=True,
            legacy_payload_rewritten=False,
            silent_conversion_used=False,
            fns_specialized_separate=fns_specialized_separate,
            compatibility_projection_ref=None,
            payload_json=delegated.payload_json,
        )

    def _successor_result(
        self,
        *,
        artifact_ref: str,
        payload: dict[str, Any],
        artifact_sha256: str,
        read_kind: str,
        validator_id: str,
    ) -> Gate2SuccessorCompatibilityReadResult:
        projection_ref = None
        if (
            payload["schema_version"]
            == SUCCESSOR_COMPATIBILITY_PROJECTION_SCHEMA_VERSION
        ):
            projection_ref = payload["projection_ref"]
        return Gate2SuccessorCompatibilityReadResult(
            schema_version=(
                SUCCESSOR_COMPATIBILITY_READ_RESULT_SCHEMA_VERSION
            ),
            reader_policy_version=(
                SUCCESSOR_COMPATIBILITY_READER_POLICY_VERSION
            ),
            artifact_ref=artifact_ref,
            artifact_schema_version=payload["schema_version"],
            artifact_sha256=artifact_sha256,
            read_kind=read_kind,
            validator_id=validator_id,
            validator_status="passed",
            records_total=_records_total(payload),
            legacy_reader_retained=True,
            legacy_payload_rewritten=False,
            silent_conversion_used=False,
            fns_specialized_separate=False,
            compatibility_projection_ref=projection_ref,
            payload_json=_canonical_json(payload),
        )


def _records_total(payload: dict[str, Any]) -> int:
    schema_version = payload["schema_version"]
    if schema_version == SUCCESSOR_RUN_ARTIFACT_SCHEMA_VERSION:
        return len(payload["package_artifacts"])
    if schema_version == SUCCESSOR_EXECUTION_RECEIPT_SCHEMA_VERSION:
        return payload["packages_total"]
    return 1


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _identifier(value: Any, field: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 240
        or not IDENTIFIER_RE.fullmatch(value)
    ):
        _fail(f"successor_compatibility_{field}_invalid")


def _fail(code: str) -> None:
    raise Gate2SuccessorCompatibilityError(code)


assert SOURCE_FACTS_SCHEMA_VERSION not in _SUCCESSOR_VALIDATORS
assert FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION not in (
    _SUCCESSOR_VALIDATORS
)
assert TYPED_FACTS_SCHEMA_VERSION not in _SUCCESSOR_VALIDATORS
