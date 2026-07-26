from __future__ import annotations

import json
from dataclasses import fields
from typing import Any

from .gate2_financial_domain_catalog import Gate2FinancialDomainSnapshot
from .gate2_financial_domain_contracts import (
    canonical_json,
    fail,
    sha256_json,
    validate_snapshot_authority_key,
    verify_snapshot_authority_hmac,
)


FINANCIAL_DOMAIN_PERSISTENCE_SCHEMA_VERSION = (
    "broker_reports_managed_financial_domain_persistence_v1"
)

FACTORY_REQUIRED = (
    "Gate2FinancialDomainPersistenceFactory is the only snapshot "
    "serialization and restoration contract"
)
FORBIDDEN = (
    "The persistence contract must not write storage, mint snapshot "
    "authority, weaken snapshot validation or expose server-held keys"
)

_TUPLE_FIELDS = frozenset(
    {
        "typed_records_json",
        "unclassified_records_json",
        "record_index_json",
        "coverage_records_json",
        "provenance_records_json",
    }
)
_SNAPSHOT_FIELDS = tuple(
    item.name for item in fields(Gate2FinancialDomainSnapshot)
)


class Gate2FinancialDomainPersistenceFactory:
    def __init__(self, *, snapshot_authority_key: bytes) -> None:
        validate_snapshot_authority_key(snapshot_authority_key)
        self._snapshot_authority_key = bytes(snapshot_authority_key)

    def serialize(
        self,
        *,
        snapshot: Gate2FinancialDomainSnapshot,
    ) -> str:
        self._validate_authority(snapshot)
        payload = {
            name: (
                list(getattr(snapshot, name))
                if name in _TUPLE_FIELDS
                else getattr(snapshot, name)
            )
            for name in _SNAPSHOT_FIELDS
        }
        envelope = {
            "schema_version": (
                FINANCIAL_DOMAIN_PERSISTENCE_SCHEMA_VERSION
            ),
            "snapshot_payload": payload,
            "snapshot_payload_sha256": sha256_json(payload),
        }
        return canonical_json(envelope)

    def restore(self, *, serialized: str) -> Gate2FinancialDomainSnapshot:
        try:
            envelope = json.loads(serialized)
        except (TypeError, json.JSONDecodeError):
            fail("financial_domain_persistence_envelope_invalid")
        if (
            not isinstance(envelope, dict)
            or set(envelope)
            != {
                "schema_version",
                "snapshot_payload",
                "snapshot_payload_sha256",
            }
            or envelope.get("schema_version")
            != FINANCIAL_DOMAIN_PERSISTENCE_SCHEMA_VERSION
        ):
            fail("financial_domain_persistence_envelope_invalid")
        payload = envelope.get("snapshot_payload")
        if (
            not isinstance(payload, dict)
            or set(payload) != set(_SNAPSHOT_FIELDS)
            or envelope.get("snapshot_payload_sha256")
            != sha256_json(payload)
        ):
            fail("financial_domain_persistence_payload_invalid")
        normalized: dict[str, Any] = {}
        for name in _SNAPSHOT_FIELDS:
            value = payload[name]
            if name in _TUPLE_FIELDS:
                if not isinstance(value, list) or any(
                    not isinstance(item, str) for item in value
                ):
                    fail("financial_domain_persistence_payload_invalid")
                normalized[name] = tuple(value)
            else:
                normalized[name] = value
        try:
            snapshot = Gate2FinancialDomainSnapshot(**normalized)
        except TypeError:
            fail("financial_domain_persistence_payload_invalid")
        self._validate_authority(snapshot)
        return snapshot

    def _validate_authority(
        self,
        snapshot: Gate2FinancialDomainSnapshot,
    ) -> None:
        if not isinstance(snapshot, Gate2FinancialDomainSnapshot):
            fail("financial_domain_persistence_snapshot_invalid")
        snapshot.validate()
        verify_snapshot_authority_hmac(
            claimed_hmac=snapshot.authority_hmac_sha256,
            schema_version=snapshot.schema_version,
            snapshot_id=snapshot.snapshot_id,
            snapshot_seed_sha256=snapshot.snapshot_seed_sha256,
            integrity_sha256=snapshot.integrity_sha256,
            registry_version=snapshot.registry_version,
            registry_hash=snapshot.registry_hash,
            completeness_status=snapshot.completeness_status,
            authority_key=self._snapshot_authority_key,
        )
