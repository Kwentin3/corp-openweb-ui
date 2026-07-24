from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any, Iterable

from .gate2_financial_evidence_catalog import (
    EVIDENCE_KIND_IDS,
    FNS_SPECIALIZED_SCHEMA_FAMILIES,
    LEGACY_BROAD_FINANCIAL_IDS,
    LEGACY_TECHNICAL_DISPOSITIONS,
)
from .gate2_financial_evidence_legacy_validation import (
    LEGACY_VALIDATOR_ID,
    LEGACY_VALIDATOR_POLICY_VERSION,
    PinnedLegacySourceFactsValidatorFactory,
)
from .gate2_financial_evidence_materialization_contracts import (
    FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION,
    IDENTIFIER_RE,
    sha256_json,
)
from .gate2_financial_evidence_materialization_validation import (
    validate_financial_evidence_inputs,
)
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_fns_2ndfl_contracts import (
    TYPED_FACTS_SCHEMA_VERSION,
    validate_fns_2ndfl_typed_output,
)
from .gate2_source_fact_contracts import SOURCE_FACTS_SCHEMA_VERSION


COMPATIBILITY_POLICY_VERSION = (
    "broker_reports_financial_evidence_compatibility_v1"
)
DUAL_READ_RESULT_SCHEMA_VERSION = (
    "broker_reports_financial_evidence_dual_read_result_v1"
)
REPLAY_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_financial_evidence_replay_receipt_v1"
)
MIGRATION_WRITE_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_financial_evidence_migration_write_receipt_v1"
)

FACTORY_REQUIRED = (
    "Gate2FinancialEvidenceCompatibilityFactory.create is the only "
    "financial evidence dual-read and explicit migration entrypoint"
)
FORBIDDEN = (
    "Compatibility must not rewrite persisted payloads, auto-alias legacy "
    "broad IDs, map FNS families or write legacy contracts"
)


class Gate2FinancialEvidenceCompatibilityError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class FinancialEvidenceCompatibilityRecord:
    record_id: str
    source_type_id: str
    namespace: str
    mapping_status: str
    canonical_input_type_id: str | None


@dataclass(frozen=True)
class Gate2FinancialEvidenceReadResult:
    schema_version: str
    compatibility_policy_version: str
    artifact_ref: str
    artifact_schema_version: str
    artifact_sha256: str
    read_kind: str
    validator_id: str
    validator_policy_version: str
    validator_status: str
    records: tuple[FinancialEvidenceCompatibilityRecord, ...]
    payload_json: str

    def payload_copy(self) -> dict[str, Any]:
        payload = json.loads(self.payload_json)
        if not isinstance(payload, dict):
            raise Gate2FinancialEvidenceCompatibilityError(
                "financial_evidence_compatibility_payload_invalid"
            )
        return payload


@dataclass(frozen=True)
class ExplicitLegacyFinancialEvidenceMapping:
    legacy_record_id: str
    target_terminal_id: str
    mapping_basis_ref: str


@dataclass(frozen=True)
class PreparedFinancialEvidenceMigrationWrite:
    payload_json: str
    receipt: dict[str, Any]

    def payload_copy(self) -> dict[str, Any]:
        payload = json.loads(self.payload_json)
        if not isinstance(payload, dict):
            raise Gate2FinancialEvidenceCompatibilityError(
                "financial_evidence_compatibility_payload_invalid"
            )
        return payload


class Gate2FinancialEvidenceCompatibilityFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def create(self) -> "Gate2FinancialEvidenceCompatibility":
        canonical_ids = set(self.registry.provider_type_enum())
        aliases = {item.alias_id for item in self.registry.aliases}
        legacy_ids = set(LEGACY_BROAD_FINANCIAL_IDS)
        if canonical_ids & legacy_ids or aliases & legacy_ids:
            _fail("financial_evidence_legacy_automatic_alias_detected")
        return Gate2FinancialEvidenceCompatibility(registry=self.registry)


class Gate2FinancialEvidenceCompatibility:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry
        self.legacy_validator = (
            PinnedLegacySourceFactsValidatorFactory().create()
        )

    def read(
        self,
        *,
        artifact_ref: str,
        payload: dict[str, Any],
    ) -> Gate2FinancialEvidenceReadResult:
        _compat_identifier(artifact_ref, "compatibility_artifact_ref")
        if not isinstance(payload, dict):
            _fail("financial_evidence_compatibility_payload_invalid")
        before_sha256 = sha256_json(payload)
        schema_version = payload.get("schema_version")
        if schema_version == SOURCE_FACTS_SCHEMA_VERSION:
            result = self._read_legacy(
                artifact_ref=artifact_ref,
                payload=payload,
                artifact_sha256=before_sha256,
            )
        elif schema_version == FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION:
            result = self._read_successor(
                artifact_ref=artifact_ref,
                payload=payload,
                artifact_sha256=before_sha256,
            )
        elif schema_version == TYPED_FACTS_SCHEMA_VERSION:
            result = self._read_fns(
                artifact_ref=artifact_ref,
                payload=payload,
                artifact_sha256=before_sha256,
            )
        else:
            _fail("financial_evidence_compatibility_schema_unsupported")
        if sha256_json(payload) != before_sha256:
            _fail("financial_evidence_compatibility_silent_rewrite")
        return result

    def replay(
        self,
        *,
        expected: Gate2FinancialEvidenceReadResult,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        actual = self.read(
            artifact_ref=expected.artifact_ref,
            payload=payload,
        )
        if (
            actual.artifact_schema_version
            != expected.artifact_schema_version
            or actual.artifact_sha256 != expected.artifact_sha256
            or actual.read_kind != expected.read_kind
            or actual.validator_id != expected.validator_id
            or actual.validator_policy_version
            != expected.validator_policy_version
            or actual.records != expected.records
        ):
            _fail("financial_evidence_compatibility_replay_mismatch")
        return {
            "schema_version": REPLAY_RECEIPT_SCHEMA_VERSION,
            "compatibility_policy_version": COMPATIBILITY_POLICY_VERSION,
            "artifact_ref": expected.artifact_ref,
            "artifact_schema_version": expected.artifact_schema_version,
            "artifact_sha256": expected.artifact_sha256,
            "validator_id": expected.validator_id,
            "validator_policy_version": (
                expected.validator_policy_version
            ),
            "records_total": len(expected.records),
            "replay_status": "passed",
            "payload_rewritten": False,
        }

    def validate_write_contract(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version")
            != FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION
        ):
            _fail("financial_evidence_legacy_write_forbidden")
        validate_financial_evidence_inputs(
            payload=payload,
            registry=self.registry,
        )
        return copy.deepcopy(payload)

    def prepare_migration_write(
        self,
        *,
        source: Gate2FinancialEvidenceReadResult,
        target_payload: dict[str, Any],
        explicit_mappings: Iterable[
            ExplicitLegacyFinancialEvidenceMapping
        ],
    ) -> PreparedFinancialEvidenceMigrationWrite:
        if source.read_kind == "fns_specialized":
            _fail("financial_evidence_fns_mapping_not_adopted")
        if source.read_kind != "legacy_source_facts":
            _fail("financial_evidence_migration_source_not_legacy")
        source_payload = source.payload_copy()
        if sha256_json(source_payload) != source.artifact_sha256:
            _fail("financial_evidence_migration_source_provenance_invalid")
        target = self.validate_write_contract(target_payload)
        mappings = tuple(
            sorted(
                explicit_mappings,
                key=lambda item: item.legacy_record_id,
            )
        )
        source_record_ids = {item.record_id for item in source.records}
        mapping_ids = [item.legacy_record_id for item in mappings]
        if (
            len(mapping_ids) != len(set(mapping_ids))
            or set(mapping_ids) != source_record_ids
        ):
            _fail("financial_evidence_explicit_mapping_incomplete")
        target_ids = {
            item["input_id"] for item in target["typed_inputs"]
        } | {
            item["unclassified_input_id"]
            for item in target["unclassified_inputs"]
        }
        if not source.records:
            target_ids.add(target["coverage"]["coverage_id"])
        for mapping in mappings:
            _compat_identifier(mapping.mapping_basis_ref, "mapping_basis_ref")
            if mapping.target_terminal_id not in target_ids:
                _fail("financial_evidence_explicit_mapping_target_invalid")
        target_sha256 = sha256_json(target)
        mapping_payload = [
            {
                "legacy_record_id": item.legacy_record_id,
                "target_terminal_id": item.target_terminal_id,
                "mapping_basis_ref": item.mapping_basis_ref,
            }
            for item in mappings
        ]
        receipt = {
            "schema_version": MIGRATION_WRITE_RECEIPT_SCHEMA_VERSION,
            "compatibility_policy_version": COMPATIBILITY_POLICY_VERSION,
            "write_contract": "single_write_successor_only",
            "source_artifact_ref": source.artifact_ref,
            "source_artifact_schema_version": (
                source.artifact_schema_version
            ),
            "source_artifact_sha256": source.artifact_sha256,
            "source_validator_id": source.validator_id,
            "source_validator_policy_version": (
                source.validator_policy_version
            ),
            "source_payload_rewritten": False,
            "automatic_aliases_used": False,
            "explicit_mappings": mapping_payload,
            "explicit_mappings_sha256": sha256_json(mapping_payload),
            "target_schema_version": (
                FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION
            ),
            "target_artifact_id": target["artifact_id"],
            "target_artifact_sha256": target_sha256,
            "migration_status": "prepared",
        }
        return PreparedFinancialEvidenceMigrationWrite(
            payload_json=_canonical_json(target),
            receipt=receipt,
        )

    def _read_legacy(
        self,
        *,
        artifact_ref: str,
        payload: dict[str, Any],
        artifact_sha256: str,
    ) -> Gate2FinancialEvidenceReadResult:
        validation = self.legacy_validator.validate(payload)
        if validation["validator_status"] != "passed":
            _fail("financial_evidence_legacy_validation_failed")
        records = tuple(
            sorted(
                (
                    _legacy_record(fact)
                    for fact in payload.get("facts", [])
                ),
                key=lambda item: item.record_id,
            )
        )
        return self._result(
            artifact_ref=artifact_ref,
            payload=payload,
            artifact_sha256=artifact_sha256,
            read_kind="legacy_source_facts",
            validator_id=LEGACY_VALIDATOR_ID,
            validator_policy_version=LEGACY_VALIDATOR_POLICY_VERSION,
            records=records,
        )

    def _read_successor(
        self,
        *,
        artifact_ref: str,
        payload: dict[str, Any],
        artifact_sha256: str,
    ) -> Gate2FinancialEvidenceReadResult:
        validate_financial_evidence_inputs(
            payload=payload,
            registry=self.registry,
        )
        records: list[FinancialEvidenceCompatibilityRecord] = []
        for item in payload["typed_inputs"]:
            records.append(
                FinancialEvidenceCompatibilityRecord(
                    record_id=item["input_id"],
                    source_type_id=item["input_type_id"],
                    namespace="financial_input_type",
                    mapping_status="native",
                    canonical_input_type_id=item["input_type_id"],
                )
            )
        for item in payload["unclassified_inputs"]:
            records.append(
                FinancialEvidenceCompatibilityRecord(
                    record_id=item["unclassified_input_id"],
                    source_type_id="unclassified_financial_input",
                    namespace="terminal_disposition",
                    mapping_status="native",
                    canonical_input_type_id=None,
                )
            )
        if not records:
            records.append(
                FinancialEvidenceCompatibilityRecord(
                    record_id=payload["coverage"]["coverage_id"],
                    source_type_id=payload["terminal_disposition"],
                    namespace="terminal_disposition",
                    mapping_status="native",
                    canonical_input_type_id=None,
                )
            )
        return self._result(
            artifact_ref=artifact_ref,
            payload=payload,
            artifact_sha256=artifact_sha256,
            read_kind="successor_financial_evidence",
            validator_id=(
                "broker_reports_financial_evidence_inputs_validator_v1"
            ),
            validator_policy_version=(
                "broker_reports_financial_evidence_inputs_validation_v1"
            ),
            records=tuple(sorted(records, key=lambda item: item.record_id)),
        )

    def _read_fns(
        self,
        *,
        artifact_ref: str,
        payload: dict[str, Any],
        artifact_sha256: str,
    ) -> Gate2FinancialEvidenceReadResult:
        validation = validate_fns_2ndfl_typed_output(payload)
        if validation["validator_status"] != "passed":
            _fail("financial_evidence_fns_validation_failed")
        records = tuple(
            sorted(
                (
                    FinancialEvidenceCompatibilityRecord(
                        record_id=fact["fact_id"],
                        source_type_id=fact["fact_family"],
                        namespace="fns_specialized_fact_family",
                        mapping_status="separate",
                        canonical_input_type_id=None,
                    )
                    for fact in payload.get("facts", [])
                ),
                key=lambda item: item.record_id,
            )
        )
        return self._result(
            artifact_ref=artifact_ref,
            payload=payload,
            artifact_sha256=artifact_sha256,
            read_kind="fns_specialized",
            validator_id=(
                "broker_reports_fns_2ndfl_source_facts_validation_v1"
            ),
            validator_policy_version=(
                "broker_reports_fns_2ndfl_source_facts_validation_v1"
            ),
            records=records,
        )

    def _result(
        self,
        *,
        artifact_ref: str,
        payload: dict[str, Any],
        artifact_sha256: str,
        read_kind: str,
        validator_id: str,
        validator_policy_version: str,
        records: tuple[FinancialEvidenceCompatibilityRecord, ...],
    ) -> Gate2FinancialEvidenceReadResult:
        return Gate2FinancialEvidenceReadResult(
            schema_version=DUAL_READ_RESULT_SCHEMA_VERSION,
            compatibility_policy_version=COMPATIBILITY_POLICY_VERSION,
            artifact_ref=artifact_ref,
            artifact_schema_version=payload["schema_version"],
            artifact_sha256=artifact_sha256,
            read_kind=read_kind,
            validator_id=validator_id,
            validator_policy_version=validator_policy_version,
            validator_status="passed",
            records=records,
            payload_json=_canonical_json(payload),
        )


def _legacy_record(
    fact: dict[str, Any],
) -> FinancialEvidenceCompatibilityRecord:
    fact_type = fact["fact_type"]
    if fact_type in LEGACY_BROAD_FINANCIAL_IDS:
        namespace = "legacy_financial_input"
    elif fact_type in EVIDENCE_KIND_IDS:
        namespace = "evidence_kind"
    elif fact_type in LEGACY_TECHNICAL_DISPOSITIONS:
        namespace = "legacy_technical_disposition"
    else:
        _fail("financial_evidence_legacy_namespace_unknown")
    return FinancialEvidenceCompatibilityRecord(
        record_id=fact["fact_id"],
        source_type_id=fact_type,
        namespace=namespace,
        mapping_status="unmapped",
        canonical_input_type_id=None,
    )


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _compat_identifier(value: Any, field: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 240
        or not IDENTIFIER_RE.fullmatch(value)
    ):
        _fail(f"financial_evidence_{field}_invalid")


def _fail(code: str) -> None:
    raise Gate2FinancialEvidenceCompatibilityError(code)


assert FNS_SPECIALIZED_SCHEMA_FAMILIES == (TYPED_FACTS_SCHEMA_VERSION,)
