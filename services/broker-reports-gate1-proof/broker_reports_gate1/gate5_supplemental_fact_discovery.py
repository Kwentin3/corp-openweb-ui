"""Restore eligible supplemental refs before the existing G5.4 check."""

from __future__ import annotations

from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStorePort, RetentionPolicy
from .artifact_resolver import ArtifactResolver
from .gate5_combined_requirement_check import (
    Gate5CombinedRequirementCheckRuntime,
    Gate5CombinedRequirementCheckRuntimeFactory,
)
from .gate5_supplemental_fact import GATE5_SUPPLEMENTAL_FACT_ARTIFACT_TYPE


FACTORY_REQUIRED = (
    "Gate5SupplementalFactDiscoveryRuntimeFactory.create",
    "ArtifactResolver.catalog_case supplies trusted case metadata",
    "Gate5CombinedRequirementCheckRuntimeFactory.create owns the decision",
)
FORBIDDEN = (
    "caller-provided supplemental refs or scope identity",
    "direct ArtifactStore, SQL or payload reads",
    "cross-run rebinding, registry, generic query or conflict resolution",
    "Gate 4 mutation, Tax Case, LLM or persistence",
)


class Gate5SupplementalFactDiscoveryRuntimeFactory:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        read_enabled: bool,
        retention_policy: RetentionPolicy,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._retention_policy = retention_policy

    def create(self) -> "Gate5SupplementalFactDiscoveryRuntime":
        combined = Gate5CombinedRequirementCheckRuntimeFactory(
            store=self._store,
            read_enabled=self._read_enabled,
            retention_policy=self._retention_policy,
        ).create()
        return Gate5SupplementalFactDiscoveryRuntime(
            resolver=ArtifactResolver(self._store),
            combined=combined,
        )


class Gate5SupplementalFactDiscoveryRuntime:
    def __init__(
        self,
        *,
        resolver: ArtifactResolver,
        combined: Gate5CombinedRequirementCheckRuntime,
    ) -> None:
        self._resolver = resolver
        self._combined = combined

    def check(
        self,
        *,
        methodology: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        supplemental_fact_refs = [
            record.artifact_id
            for record in self._resolver.catalog_case(context)
            if record.artifact_type == GATE5_SUPPLEMENTAL_FACT_ARTIFACT_TYPE
            and record.normalization_run_id == context.normalization_run_id
        ]
        return self._combined.check(
            methodology=methodology,
            supplemental_fact_refs=supplemental_fact_refs,
            context=context,
        )
