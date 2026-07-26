from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable

from .gate2_financial_domain_contracts import (
    FINANCIAL_DOMAIN_CONTRACT_VERSION,
    FINANCIAL_DOMAIN_SNAPSHOT_SCHEMA_VERSION,
    FinancialDomainAccessContext,
    FinancialDomainAccessScope,
    canonical_json,
    fail,
    sha256_json,
    validate_timestamp,
)
from .gate2_financial_domain_projection import (
    coverage_record as build_coverage_record,
    domain_catalog as build_domain_catalog,
    domain_coverage as build_domain_coverage,
    domain_record as build_domain_record,
    provenance_record as build_provenance_record,
    record_index as build_record_index,
    snapshot_integrity_material,
    terminal,
)
from .gate2_financial_domain_validation import (
    validate_financial_domain_snapshot,
)
from .gate2_financial_evidence_materialization_contracts import (
    Gate2FinancialEvidenceSourcePackage,
)
from .gate2_financial_evidence_materialization_validation import (
    validate_financial_evidence_inputs,
)
from .gate2_financial_evidence_registry import (
    REGISTRY_ID,
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_evidence_source_package import (
    validate_source_package_integrity,
)
from .gate2_financial_semantic_contract import (
    Gate2FinancialSemanticContractFactory,
)
from .gate2_financial_semantic_model_assets import (
    load_gate2_financial_semantic_model_assets,
)


FACTORY_REQUIRED = (
    "Gate2FinancialDomainCatalogFactory.create is the only canonical "
    "financial domain snapshot entrypoint"
)
FORBIDDEN = (
    "Gate 3 callers must not read ArtifactStore, source documents, Gate 1 "
    "payloads, provider output, Knowledge, RAG or filesystem state"
)


@dataclass(frozen=True)
class Gate2FinancialDomainSnapshot:
    schema_version: str
    snapshot_id: str
    snapshot_seed_sha256: str
    integrity_sha256: str
    registry_version: str
    registry_hash: str
    completeness_status: str
    semantic_pack_identity_json: str
    snapshot_json: str
    catalog_json: str
    coverage_json: str
    typed_records_json: tuple[str, ...]
    unclassified_records_json: tuple[str, ...]
    record_index_json: tuple[str, ...]
    coverage_records_json: tuple[str, ...]
    provenance_records_json: tuple[str, ...]

    def identity_payload(self) -> dict[str, Any]:
        return _json_object(self.snapshot_json)

    def semantic_pack_identity(self) -> dict[str, str]:
        return _json_object(self.semantic_pack_identity_json)

    def declared_scope(self) -> dict[str, Any]:
        return _json_object(self.catalog_json)

    def coverage_summary(self) -> dict[str, Any]:
        return _json_object(self.coverage_json)

    def typed_records(self) -> list[dict[str, Any]]:
        return _json_values(self.typed_records_json)

    def unclassified_records(self) -> list[dict[str, Any]]:
        return _json_values(self.unclassified_records_json)

    def record_index(self) -> list[dict[str, Any]]:
        return _json_values(self.record_index_json)

    def coverage_records(self) -> list[dict[str, Any]]:
        return _json_values(self.coverage_records_json)

    def provenance_records(self) -> list[dict[str, Any]]:
        return _json_values(self.provenance_records_json)

    def access_scope_fingerprint(self) -> str:
        return str(
            self.identity_payload()["access_scope"][
                "access_scope_fingerprint"
            ]
        )

    def expires_at(self) -> str | None:
        value = self.identity_payload()["expires_at"]
        return str(value) if value is not None else None

    def validate(self) -> None:
        validate_financial_domain_snapshot(
            schema_version=self.schema_version,
            snapshot_id=self.snapshot_id,
            snapshot_seed_sha256=self.snapshot_seed_sha256,
            integrity_sha256=self.integrity_sha256,
            registry_version=self.registry_version,
            registry_hash=self.registry_hash,
            completeness_status=self.completeness_status,
            snapshot=self.identity_payload(),
            pack=self.semantic_pack_identity(),
            catalog=self.declared_scope(),
            coverage=self.coverage_summary(),
            typed_records=self.typed_records(),
            unclassified_records=self.unclassified_records(),
            record_index=self.record_index(),
            coverage_records=self.coverage_records(),
            provenance_records=self.provenance_records(),
        )


class Gate2FinancialDomainCatalogFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry
        self.semantic_contract = Gate2FinancialSemanticContractFactory(
            registry=registry
        ).create()
        pack = load_gate2_financial_semantic_model_assets()[
            "semantic_pack"
        ]
        self.pack_identity = {
            "pack_schema_version": str(pack["schema_version"]),
            "semantic_version": str(pack["semantic_version"]),
            "canonical_sha256": str(pack["integrity_sha256"]),
            "managed_asset_ref": str(pack["managed_asset_ref"]),
        }
        if (
            self.pack_identity["canonical_sha256"]
            != self.semantic_contract.integrity_sha256
        ):
            fail("financial_domain_semantic_pack_authority_invalid")

    def create(
        self,
        *,
        materialized_artifacts: Iterable[dict[str, Any]],
        source_packages: Iterable[Gate2FinancialEvidenceSourcePackage],
        access_context: FinancialDomainAccessContext,
        created_at: str,
        expires_at: str | None,
    ) -> Gate2FinancialDomainSnapshot:
        artifacts = tuple(materialized_artifacts)
        packages = self._packages(source_packages)
        access_scope = access_context.access_scope()
        normalized_created, normalized_expires = _retention_identity(
            access_scope=access_scope,
            created_at=created_at,
            expires_at=expires_at,
        )
        if not artifacts or not packages:
            fail("financial_domain_declared_scope_empty")
        if {
            _artifact_package_ref(artifact) for artifact in artifacts
        } != set(packages):
            fail("financial_domain_source_package_set_mismatch")
        validated = self._validated_pairs(
            artifacts=artifacts,
            packages=packages,
        )
        seed = _snapshot_seed(
            validated=validated,
            registry=self.registry,
            pack_identity=self.pack_identity,
            access_scope=access_scope,
            created_at=normalized_created,
            expires_at=normalized_expires,
        )
        snapshot_seed_sha256 = sha256_json(seed)
        snapshot_id = "findom_" + snapshot_seed_sha256[:32]
        (
            typed_records,
            unclassified_records,
            record_index,
            coverage_records,
            provenance_records,
        ) = _project_domain(
            snapshot_id=snapshot_id,
            pack_identity=self.pack_identity,
            validated=validated,
        )
        records = sorted(
            [*typed_records, *unclassified_records],
            key=lambda item: item["record_id"],
        )
        coverage = build_domain_coverage(
            snapshot_id=snapshot_id,
            coverage_records=coverage_records,
        )
        catalog = build_domain_catalog(
            snapshot_id=snapshot_id,
            pack_identity=self.pack_identity,
            type_contracts=self.semantic_contract.type_contracts,
            typed_records=typed_records,
            unclassified_records=unclassified_records,
        )
        snapshot_payload = _snapshot_payload(
            snapshot_id=snapshot_id,
            packages=packages,
            artifacts=artifacts,
            pack_identity=self.pack_identity,
            catalog_ref=catalog["catalog_ref"],
            coverage_ref=coverage["coverage_ref"],
            records=records,
            access_scope=access_scope,
            created_at=normalized_created,
            expires_at=normalized_expires,
        )
        completeness_status = _combined_completeness(packages.values())
        material = snapshot_integrity_material(
            snapshot=snapshot_payload,
            catalog=catalog,
            coverage=coverage,
            typed_records=typed_records,
            unclassified_records=unclassified_records,
            record_index_values=record_index,
            coverage_records=coverage_records,
            provenance_records=provenance_records,
            registry_version=self.registry.registry_version,
            registry_hash=self.registry.registry_hash,
            completeness_status=completeness_status,
            snapshot_seed_sha256=snapshot_seed_sha256,
        )
        snapshot = Gate2FinancialDomainSnapshot(
            schema_version=FINANCIAL_DOMAIN_SNAPSHOT_SCHEMA_VERSION,
            snapshot_id=snapshot_id,
            snapshot_seed_sha256=snapshot_seed_sha256,
            integrity_sha256=sha256_json(material),
            registry_version=self.registry.registry_version,
            registry_hash=self.registry.registry_hash,
            completeness_status=completeness_status,
            semantic_pack_identity_json=canonical_json(
                self.pack_identity
            ),
            snapshot_json=canonical_json(snapshot_payload),
            catalog_json=canonical_json(catalog),
            coverage_json=canonical_json(coverage),
            typed_records_json=_json_tuple(typed_records),
            unclassified_records_json=_json_tuple(
                unclassified_records
            ),
            record_index_json=_json_tuple(record_index),
            coverage_records_json=_json_tuple(coverage_records),
            provenance_records_json=_json_tuple(provenance_records),
        )
        snapshot.validate()
        return snapshot

    def _validated_pairs(
        self,
        *,
        artifacts: tuple[dict[str, Any], ...],
        packages: dict[str, Gate2FinancialEvidenceSourcePackage],
    ) -> list[
        tuple[dict[str, Any], Gate2FinancialEvidenceSourcePackage]
    ]:
        validated = []
        artifact_ids: set[str] = set()
        source_scopes: set[str] = set()
        terminal_ids: set[str] = set()
        for artifact in artifacts:
            package = packages[_artifact_package_ref(artifact)]
            validate_financial_evidence_inputs(
                payload=artifact,
                registry=self.registry,
                source_package=package,
            )
            artifact_id = str(artifact["artifact_id"])
            if artifact_id in artifact_ids:
                fail("financial_domain_artifact_duplicate")
            artifact_ids.add(artifact_id)
            if package.source_scope_ref in source_scopes:
                fail("financial_domain_source_scope_duplicate")
            source_scopes.add(package.source_scope_ref)
            terminal_record = terminal(artifact)
            if terminal_record is not None:
                terminal_id = str(
                    terminal_record.get("input_id")
                    or terminal_record.get("unclassified_input_id")
                    or ""
                )
                if not terminal_id or terminal_id in terminal_ids:
                    fail("financial_domain_terminal_record_duplicate")
                terminal_ids.add(terminal_id)
            validated.append((artifact, package))
        return validated

    def _packages(
        self,
        packages: Iterable[Gate2FinancialEvidenceSourcePackage],
    ) -> dict[str, Gate2FinancialEvidenceSourcePackage]:
        result = {}
        for package in packages:
            validate_source_package_integrity(package)
            if package.package_ref in result:
                fail("financial_domain_source_package_duplicate")
            result[package.package_ref] = package
        return result


def _retention_identity(
    *,
    access_scope: FinancialDomainAccessScope,
    created_at: str,
    expires_at: str | None,
) -> tuple[str, str | None]:
    access_scope.validate()
    created = validate_timestamp(created_at, field="created_at")
    normalized_expires = None
    if expires_at is not None:
        expires = validate_timestamp(expires_at, field="expires_at")
        if expires <= created:
            fail("financial_domain_expiry_invalid")
        normalized_expires = expires.isoformat()
    return created.isoformat(), normalized_expires


def _snapshot_seed(
    *,
    validated: list[
        tuple[dict[str, Any], Gate2FinancialEvidenceSourcePackage]
    ],
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    pack_identity: dict[str, str],
    access_scope: FinancialDomainAccessScope,
    created_at: str,
    expires_at: str | None,
) -> dict[str, Any]:
    return {
        "contract_version": FINANCIAL_DOMAIN_CONTRACT_VERSION,
        "registry": {
            "registry_id": REGISTRY_ID,
            "registry_version": registry.registry_version,
            "registry_hash": registry.registry_hash,
        },
        "semantic_pack_identity": pack_identity,
        "access_scope": access_scope.to_dict(),
        "created_at": created_at,
        "expires_at": expires_at,
        "artifacts": sorted(
            (
                {
                    "artifact_id": artifact["artifact_id"],
                    "integrity_sha256": artifact["integrity_hash"],
                    "source_package_ref": package.package_ref,
                    "source_package_integrity_sha256": (
                        package.integrity_hash
                    ),
                }
                for artifact, package in validated
            ),
            key=lambda item: item["artifact_id"],
        ),
    }


def _project_domain(
    *,
    snapshot_id: str,
    pack_identity: dict[str, str],
    validated: list[
        tuple[dict[str, Any], Gate2FinancialEvidenceSourcePackage]
    ],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    typed_records: list[dict[str, Any]] = []
    unclassified_records: list[dict[str, Any]] = []
    record_index: list[dict[str, Any]] = []
    coverage_records: list[dict[str, Any]] = []
    provenance_records: list[dict[str, Any]] = []
    for artifact, package in validated:
        terminal_record = terminal(artifact)
        provenance = build_provenance_record(
            snapshot_id=snapshot_id,
            source_package=package,
            terminal_record=terminal_record,
        )
        provenance_records.append(provenance)
        record = build_domain_record(
            snapshot_id=snapshot_id,
            semantic_pack_identity=pack_identity,
            artifact=artifact,
            source_package=package,
            terminal_record=terminal_record,
            provenance=provenance,
        )
        if record is not None:
            target = (
                typed_records
                if record["record_kind"] == "typed"
                else unclassified_records
            )
            target.append(record)
            record_index.append(
                build_record_index(
                    record=record,
                    source_package=package,
                    terminal_disposition=artifact[
                        "terminal_disposition"
                    ],
                )
            )
        coverage_records.append(
            build_coverage_record(
                artifact=artifact,
                source_package=package,
                provenance_ref=provenance["provenance_ref"],
                record=record,
            )
        )
    typed_records.sort(key=lambda item: item["record_id"])
    unclassified_records.sort(key=lambda item: item["record_id"])
    record_index.sort(key=lambda item: item["record_id"])
    coverage_records.sort(key=lambda item: item["source_scope_ref"])
    provenance_records.sort(key=lambda item: item["provenance_ref"])
    return (
        typed_records,
        unclassified_records,
        record_index,
        coverage_records,
        provenance_records,
    )


def _snapshot_payload(
    *,
    snapshot_id: str,
    packages: dict[str, Gate2FinancialEvidenceSourcePackage],
    artifacts: tuple[dict[str, Any], ...],
    pack_identity: dict[str, str],
    catalog_ref: str,
    coverage_ref: str,
    records: list[dict[str, Any]],
    access_scope: FinancialDomainAccessScope,
    created_at: str,
    expires_at: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": FINANCIAL_DOMAIN_SNAPSHOT_SCHEMA_VERSION,
        "contract_version": FINANCIAL_DOMAIN_CONTRACT_VERSION,
        "domain_snapshot_id": snapshot_id,
        "snapshot_status": "immutable",
        "source_extraction_run_refs": sorted(
            {package.normalization_run_ref for package in packages.values()}
        ),
        "gate2_run_refs": sorted(
            {
                str(artifact["execution"]["execution_ref"])
                for artifact in artifacts
            }
        ),
        "semantic_pack_identity": pack_identity,
        "catalog_ref": catalog_ref,
        "coverage_ref": coverage_ref,
        "records_total": len(records),
        "record_set_sha256": sha256_json(
            [
                {
                    "record_id": record["record_id"],
                    "record_sha256": record["record_sha256"],
                }
                for record in records
            ]
        ),
        "access_scope": access_scope.to_dict(),
        "created_at": created_at,
        "expires_at": expires_at,
    }


def _artifact_package_ref(artifact: Any) -> str:
    source_package = (
        artifact.get("source_package")
        if isinstance(artifact, dict)
        else None
    )
    package_ref = (
        source_package.get("package_ref")
        if isinstance(source_package, dict)
        else None
    )
    if not isinstance(package_ref, str) or not package_ref:
        fail("financial_domain_artifact_source_package_invalid")
    return package_ref


def _combined_completeness(
    packages: Iterable[Gate2FinancialEvidenceSourcePackage],
) -> str:
    values = {item.completeness for item in packages}
    for status in ("blocked", "partial", "restricted"):
        if status in values:
            return status
    return "complete"


def _json_tuple(
    values: list[dict[str, Any]],
) -> tuple[str, ...]:
    return tuple(canonical_json(value) for value in values)


def _json_values(values: tuple[str, ...]) -> list[dict[str, Any]]:
    return [_json_object(value) for value in values]


def _json_object(value: str) -> dict[str, Any]:
    try:
        result = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        fail("financial_domain_snapshot_integrity_invalid")
    if not isinstance(result, dict):
        fail("financial_domain_snapshot_integrity_invalid")
    return result
