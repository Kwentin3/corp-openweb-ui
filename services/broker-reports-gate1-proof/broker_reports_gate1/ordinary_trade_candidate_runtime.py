"""Composition root for the inactive ordinary-trade production candidate."""

from __future__ import annotations

from .artifact_models import ArtifactStorePort
from .gate4_ordinary_trade_candidate import (
    Gate4OrdinaryTradeCandidateRuntime,
    Gate4OrdinaryTradeCandidateRuntimeFactory,
)
from .gate5_deterministic_source_fact_consumption import (
    Gate5DeterministicSourceFactConsumptionRuntime,
)
from .gate5_trusted_methodology import Gate5TrustedMethodologyAuthorityFactory


FACTORY_REQUIRED = (
    "OrdinaryTradeCandidateRuntimeFactory.create is the only candidate "
    "composition entrypoint"
)
FORBIDDEN = (
    "production activation, legacy fallback, direct Canonical parsing in Gate 5, "
    "LLM calls in runtime binding or alternate tax methodology"
)


class OrdinaryTradeCandidateRuntimeFactory:
    """Compose candidate facts with the unchanged deterministic Gate 5 runtime."""

    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        read_enabled: bool,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> Gate5DeterministicSourceFactConsumptionRuntime:
        return self.create_with_current_fact_set()[1]

    def create_with_current_fact_set(self) -> tuple[
        Gate4OrdinaryTradeCandidateRuntime, Gate5DeterministicSourceFactConsumptionRuntime
    ]:
        """Expose readiness and consumption from the same active fact owner."""
        financial_case = Gate4OrdinaryTradeCandidateRuntimeFactory(
            store=self._store,
            read_enabled=self._read_enabled,
        ).create()
        return financial_case, Gate5DeterministicSourceFactConsumptionRuntime(
            financial_case=financial_case,
            authority=Gate5TrustedMethodologyAuthorityFactory.create(),
        )


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "OrdinaryTradeCandidateRuntimeFactory",
]
