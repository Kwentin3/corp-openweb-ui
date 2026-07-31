from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .gate2_deterministic_financial_scopes import (
    Gate2DeterministicFinancialScope,
    Gate2DeterministicFinancialScopeFromGate1V2Factory,
)
from .gate2_financial_evidence_materialization import (
    Gate2FinancialEvidenceSourcePackage,
)
from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_semantic_contract import (
    Gate2FinancialSemanticContractFactory,
)
from .gate2_financial_semantic_model_assets import (
    load_gate2_financial_semantic_model_assets,
)
from .gate2_financial_semantic_v6_bundle import (
    Gate2FinancialEvidenceBundle,
    Gate2FinancialEvidenceBundleFactory,
)
from .gate2_financial_semantic_v6_candidate_compiler import (
    Gate2FinancialCandidateCompilation,
    Gate2FinancialCandidateCompilerFactory,
)
from .gate2_financial_semantic_v6_choice import (
    TYPE_FIRST_RESPONSE_SCHEMA_VERSION,
    Gate2FinancialSemanticV6ChoiceContract,
    Gate2FinancialSemanticV6ChoiceContractFactory,
    Gate2FinancialSemanticV6TypeFirstResponseProfile,
    normalize_financial_semantic_v6_type_first_response,
)
from .gate2_financial_semantic_v6_expansion import (
    Gate2FinancialSemanticV6DecisionExpansionFactory,
    Gate2FinancialSemanticV6ExpandedDecision,
)
from .gate2_financial_semantic_v6_packet import (
    Gate2FinancialSemanticV6Packet,
    Gate2FinancialSemanticV6PacketFactory,
)
from .gate2_financial_semantic_v6_totality import (
    Gate2FinancialSemanticV6TotalMaterialization,
    Gate2FinancialSemanticV6TotalMaterializerFactory,
)


TYPE_FIRST_REQUEST_SCHEMA_VERSION = "broker_reports_type_first_request_v1"
TYPE_FIRST_MAPPING_SCHEMA_VERSION = (
    "broker_reports_gate2_same_source_type_first_mapping_v1"
)
TYPE_FIRST_PROOF_SCHEMA_VERSION = (
    "broker_reports_gate2_same_source_type_first_proof_v1"
)
TYPE_CARD_PROJECTION_VERSION = (
    "broker_reports_gate2_financial_type_card_projection_v1"
)

FACTORY_REQUIRED = (
    "Gate2SameSourceTypeFirstProof.prepare and execute are proof-only subordinate "
    "entrypoints inside current_source_fact_orchestration"
)
FORBIDDEN = (
    "This module must not be imported by a product route or Function bundle, "
    "call a provider, mint source values or refs, parse a second response "
    "contract, validate canonical decisions, or materialize canonical output"
)


class Gate2SameSourceTypeFirstProofError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2TypeFirstCandidate:
    schema_version: str
    projection_version: str
    active: bool
    transport_eligible: bool
    request_key: str
    payload: dict[str, Any]
    type_card_projection_hash: str
    request_hash: str
    provider_calls_total: int

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "projection_version": self.projection_version,
            "active": self.active,
            "transport_eligible": self.transport_eligible,
            "request_key": self.request_key,
            "type_card_projection_hash": self.type_card_projection_hash,
            "request_hash": self.request_hash,
            "source_units_total": len(self.payload["source_units"]),
            "type_cards_total": len(self.payload["type_cards"]),
            "provider_calls_total": self.provider_calls_total,
            "canonical_type_ids_visible_total": 0,
            "source_refs_visible_total": 0,
            "prebound_options_visible_total": 0,
        }


@dataclass(frozen=True)
class Gate2TypeFirstMappingReceipt:
    schema_version: str
    request_key: str
    request_hash: str
    semantic_pack_id: str
    semantic_pack_version: str
    semantic_pack_integrity_sha256: str
    type_restoration: tuple[dict[str, str], ...]
    option_restoration: tuple[dict[str, Any], ...]
    source_unit_bindings: tuple[dict[str, str], ...]
    provider_calls_total: int
    integrity_hash: str

    def to_private_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_key": self.request_key,
            "request_hash": self.request_hash,
            "semantic_pack_id": self.semantic_pack_id,
            "semantic_pack_version": self.semantic_pack_version,
            "semantic_pack_integrity_sha256": (
                self.semantic_pack_integrity_sha256
            ),
            "type_restoration": copy.deepcopy(list(self.type_restoration)),
            "option_restoration": copy.deepcopy(list(self.option_restoration)),
            "source_unit_bindings": copy.deepcopy(list(self.source_unit_bindings)),
            "provider_calls_total": self.provider_calls_total,
            "integrity_hash": self.integrity_hash,
        }

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_hash": self.request_hash,
            "semantic_pack_id": self.semantic_pack_id,
            "semantic_pack_version": self.semantic_pack_version,
            "semantic_pack_integrity_sha256": (
                self.semantic_pack_integrity_sha256
            ),
            "type_restoration_total": len(self.type_restoration),
            "prebound_options_total": len(self.option_restoration),
            "source_units_total": len(self.source_unit_bindings),
            "provider_calls_total": self.provider_calls_total,
            "contains_source_literals": False,
            "contains_source_refs": False,
            "integrity_hash": self.integrity_hash,
        }


@dataclass(frozen=True)
class Gate2TypeFirstUnitAuthorities:
    source_unit_key: str
    scope: Gate2DeterministicFinancialScope
    evidence_bundle: Gate2FinancialEvidenceBundle
    source_package: Gate2FinancialEvidenceSourcePackage
    compilation: Gate2FinancialCandidateCompilation
    packet: Gate2FinancialSemanticV6Packet
    choice_contract: Gate2FinancialSemanticV6ChoiceContract


@dataclass(frozen=True)
class Gate2TypeFirstPreparedProof:
    schema_version: str
    candidate: Gate2TypeFirstCandidate
    mapping_receipt: Gate2TypeFirstMappingReceipt
    response_profile: Gate2FinancialSemanticV6TypeFirstResponseProfile
    units: tuple[Gate2TypeFirstUnitAuthorities, ...]
    source_package_batch_hash: str
    integrity_hash: str


@dataclass(frozen=True)
class Gate2TypeFirstUnitExecution:
    source_unit_key: str
    plausible_type_keys: tuple[str, ...]
    plausible_type_ids: tuple[str, ...]
    exact_restored_option_keys: tuple[str, ...]
    code_reason: str
    disposition: str
    expansion: Gate2FinancialSemanticV6ExpandedDecision
    total_materialization: Gate2FinancialSemanticV6TotalMaterialization
    trace_hash: str


@dataclass(frozen=True)
class Gate2TypeFirstExecution:
    schema_version: str
    request_hash: str
    mapping_hash: str
    simulated_response_hash: str
    restored_decisions_hash: str
    units: tuple[Gate2TypeFirstUnitExecution, ...]
    accounting: dict[str, int]
    provider_calls_total: int
    retries_total: int
    repairs_total: int
    fallbacks_total: int
    model_generated_values_total: int
    integrity_hash: str

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_hash": self.request_hash,
            "mapping_hash": self.mapping_hash,
            "simulated_response_hash": self.simulated_response_hash,
            "restored_decisions_hash": self.restored_decisions_hash,
            "unit_trace_hashes": [item.trace_hash for item in self.units],
            "accounting": copy.deepcopy(self.accounting),
            "provider_calls_total": self.provider_calls_total,
            "retries_total": self.retries_total,
            "repairs_total": self.repairs_total,
            "fallbacks_total": self.fallbacks_total,
            "model_generated_values_total": self.model_generated_values_total,
            "integrity_hash": self.integrity_hash,
        }


class Gate2SameSourceTypeFirstProof:
    """Inactive same-source proof that delegates every canonical boundary."""

    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def prepare(
        self,
        *,
        gate2_packages: Iterable[dict[str, Any]],
    ) -> Gate2TypeFirstPreparedProof:
        packages = tuple(copy.deepcopy(tuple(gate2_packages)))
        if not packages:
            _fail("type_first_gate2_packages_empty")
        batch = Gate2DeterministicFinancialScopeFromGate1V2Factory(
            registry=self.registry
        ).create(gate1_packages=packages)
        if len(batch.scopes) < 3:
            _fail("type_first_source_units_insufficient")
        ordered_scopes = tuple(
            sorted(
                batch.scopes,
                key=lambda item: item.source_package.integrity_hash,
            )
        )
        units: list[Gate2TypeFirstUnitAuthorities] = []
        for index, scope in enumerate(ordered_scopes, start=1):
            source_unit_key = f"u{index:02d}"
            bundle = Gate2FinancialEvidenceBundleFactory().create(
                source_package=scope.source_package,
                gate1_packages=packages,
            )
            compilation = Gate2FinancialCandidateCompilerFactory(
                registry=self.registry
            ).create(
                evidence_bundle=bundle,
                source_package=scope.source_package,
            )
            packet = Gate2FinancialSemanticV6PacketFactory(
                registry=self.registry
            ).create(
                evidence_bundle=bundle,
                source_package=scope.source_package,
                compilation=compilation,
            )
            choice_contract = Gate2FinancialSemanticV6ChoiceContractFactory(
                registry=self.registry
            ).create(
                packet=packet,
                evidence_bundle=bundle,
                source_package=scope.source_package,
                compilation=compilation,
            )
            units.append(
                Gate2TypeFirstUnitAuthorities(
                    source_unit_key=source_unit_key,
                    scope=scope,
                    evidence_bundle=bundle,
                    source_package=scope.source_package,
                    compilation=compilation,
                    packet=packet,
                    choice_contract=choice_contract,
                )
            )

        type_cards, type_restoration, projection_hash, pack_identity = (
            self._type_cards()
        )
        source_units = [self._model_source_unit(unit) for unit in units]
        request_key = "type-first:" + sha256_json(
            {
                "pack": pack_identity,
                "unit_hashes": [
                    unit.scope.package["integrity_hash"] for unit in units
                ],
            }
        )[:24]
        payload = {
            "schema_version": TYPE_FIRST_REQUEST_SCHEMA_VERSION,
            "request_key": request_key,
            "task": {
                "operation": "return_all_plausible_type_keys_per_source_unit",
                "plural_results_allowed": True,
                "empty_results_allowed": True,
                "values_or_refs_must_not_be_returned": True,
            },
            "source_units": source_units,
            "type_cards": type_cards,
            "type_card_projection_version": TYPE_CARD_PROJECTION_VERSION,
            "type_card_projection_hash": projection_hash,
        }
        request_hash = sha256_json(payload)
        candidate = Gate2TypeFirstCandidate(
            schema_version=TYPE_FIRST_REQUEST_SCHEMA_VERSION,
            projection_version=TYPE_CARD_PROJECTION_VERSION,
            active=False,
            transport_eligible=False,
            request_key=request_key,
            payload=copy.deepcopy(payload),
            type_card_projection_hash=projection_hash,
            request_hash=request_hash,
            provider_calls_total=0,
        )
        mapping = self._mapping_receipt(
            candidate=candidate,
            pack_identity=pack_identity,
            type_restoration=type_restoration,
            units=tuple(units),
        )
        profile = Gate2FinancialSemanticV6ChoiceContractFactory(
            registry=self.registry
        ).create_type_first_response_profile(
            request_key=request_key,
            request_hash=request_hash,
            mapping_hash=mapping.integrity_hash,
            semantic_pack_integrity_sha256=(
                mapping.semantic_pack_integrity_sha256
            ),
            source_unit_keys=tuple(unit.source_unit_key for unit in units),
            local_type_keys=tuple(
                item["local_type_key"] for item in mapping.type_restoration
            ),
        )
        source_package_batch_hash = sha256_json(
            [unit.source_package.integrity_hash for unit in units]
        )
        material = {
            "schema_version": TYPE_FIRST_PROOF_SCHEMA_VERSION,
            "candidate_request_hash": candidate.request_hash,
            "mapping_hash": mapping.integrity_hash,
            "response_profile_hash": profile.integrity_hash,
            "source_package_batch_hash": source_package_batch_hash,
            "unit_authority_hashes": [
                {
                    "source_unit_key": unit.source_unit_key,
                    "scope_hash": unit.scope.package["integrity_hash"],
                    "bundle_hash": unit.evidence_bundle.integrity_hash,
                    "compilation_hash": unit.compilation.integrity_hash,
                    "packet_hash": unit.packet.packet_hash,
                    "choice_schema_hash": unit.choice_contract.choice_schema_hash,
                }
                for unit in units
            ],
        }
        return Gate2TypeFirstPreparedProof(
            schema_version=TYPE_FIRST_PROOF_SCHEMA_VERSION,
            candidate=candidate,
            mapping_receipt=mapping,
            response_profile=profile,
            units=tuple(units),
            source_package_batch_hash=source_package_batch_hash,
            integrity_hash=sha256_json(material),
        )

    def execute(
        self,
        *,
        prepared: Gate2TypeFirstPreparedProof,
        simulated_response: str | dict[str, Any],
    ) -> Gate2TypeFirstExecution:
        self._validate_prepared(prepared)
        type_restoration = {
            item["local_type_key"]: item["canonical_type_id"]
            for item in prepared.mapping_receipt.type_restoration
        }
        restored = normalize_financial_semantic_v6_type_first_response(
            model_output=simulated_response,
            response_profile=prepared.response_profile,
            type_restoration=type_restoration,
        )
        response_object = _response_object(simulated_response)
        results: list[Gate2TypeFirstUnitExecution] = []
        for unit, decision in zip(prepared.units, restored, strict=True):
            results.append(
                self._execute_unit(
                    unit=unit,
                    decision=decision,
                    mapping=prepared.mapping_receipt,
                )
            )
        accounting = _accounting(results)
        material = {
            "schema_version": TYPE_FIRST_PROOF_SCHEMA_VERSION,
            "request_hash": prepared.candidate.request_hash,
            "mapping_hash": prepared.mapping_receipt.integrity_hash,
            "simulated_response_hash": sha256_json(response_object),
            "restored_decisions_hash": sha256_json(
                [_restored_payload(item) for item in restored]
            ),
            "unit_trace_hashes": [item.trace_hash for item in results],
            "accounting": accounting,
            "provider_calls_total": 0,
            "retries_total": 0,
            "repairs_total": 0,
            "fallbacks_total": 0,
            "model_generated_values_total": 0,
        }
        return Gate2TypeFirstExecution(
            schema_version=TYPE_FIRST_PROOF_SCHEMA_VERSION,
            request_hash=prepared.candidate.request_hash,
            mapping_hash=prepared.mapping_receipt.integrity_hash,
            simulated_response_hash=sha256_json(response_object),
            restored_decisions_hash=sha256_json(
                [_restored_payload(item) for item in restored]
            ),
            units=tuple(results),
            accounting=accounting,
            provider_calls_total=0,
            retries_total=0,
            repairs_total=0,
            fallbacks_total=0,
            model_generated_values_total=0,
            integrity_hash=sha256_json(material),
        )

    def response(
        self,
        *,
        prepared: Gate2TypeFirstPreparedProof,
        plausible_types_by_unit: dict[str, tuple[str, ...]],
    ) -> dict[str, Any]:
        """Build frozen simulated output from opaque local keys only."""

        if set(plausible_types_by_unit) != {
            unit.source_unit_key for unit in prepared.units
        }:
            _fail("type_first_simulated_response_unit_coverage_invalid")
        return {
            "schema_version": TYPE_FIRST_RESPONSE_SCHEMA_VERSION,
            "request_key": prepared.candidate.request_key,
            "request_hash": prepared.candidate.request_hash,
            "mapping_hash": prepared.mapping_receipt.integrity_hash,
            "semantic_pack_integrity_sha256": (
                prepared.mapping_receipt.semantic_pack_integrity_sha256
            ),
            "unit_decisions": [
                {
                    "source_unit_key": unit.source_unit_key,
                    "plausible_type_keys": list(
                        plausible_types_by_unit[unit.source_unit_key]
                    ),
                }
                for unit in prepared.units
            ],
        }

    def _type_cards(
        self,
    ) -> tuple[
        list[dict[str, Any]],
        tuple[dict[str, str], ...],
        str,
        dict[str, str],
    ]:
        semantic_contract = Gate2FinancialSemanticContractFactory(
            registry=self.registry
        ).create()
        assets = load_gate2_financial_semantic_model_assets()
        pack = copy.deepcopy(assets["semantic_pack"])
        if (
            pack.get("pack_id") != semantic_contract.pack_id
            or pack.get("semantic_version") != semantic_contract.semantic_version
            or pack.get("integrity_sha256")
            != semantic_contract.integrity_sha256
        ):
            _fail("type_first_semantic_pack_identity_mismatch")
        declarations = sorted(
            pack["full_compact_snapshot"],
            key=lambda item: item["input_type_id"],
        )
        local_key_by_type_id = {
            declaration["input_type_id"]: f"t{index:02d}"
            for index, declaration in enumerate(declarations, start=1)
        }
        cards: list[dict[str, Any]] = []
        restoration: list[dict[str, str]] = []
        for index, declaration in enumerate(declarations, start=1):
            local_key = f"t{index:02d}"
            distinctions = declaration.get("semantic_distinctions") or []
            card = {
                "local_type_key": local_key,
                "display_name": declaration["title"],
                "definition": declaration["definition"],
                "positive_signals": [
                    *declaration.get("examples", []),
                    declaration["model_guidance"],
                ],
                "negative_signals": list(
                    declaration.get("ambiguity_guidance") or []
                ),
                "competitors": [
                    {
                        "competitor": local_key_by_type_id.get(
                            item["against"],
                            item["against"].replace("_", " "),
                        ),
                        "distinction": item["rule"],
                    }
                    for item in distinctions
                ],
                "counterexamples": list(
                    declaration.get("counterexamples") or []
                ),
                "supported_source_shapes": list(
                    declaration["compatible_source_families"]
                ),
                "projection_version": TYPE_CARD_PROJECTION_VERSION,
            }
            if (
                not card["positive_signals"]
                or not card["negative_signals"]
                or not card["competitors"]
                or not card["counterexamples"]
            ):
                _fail("type_first_type_card_quality_invalid")
            cards.append(card)
            restoration.append(
                {
                    "local_type_key": local_key,
                    "canonical_type_id": declaration["input_type_id"],
                    "semantic_pack_version": semantic_contract.semantic_version,
                    "semantic_pack_integrity_sha256": (
                        semantic_contract.integrity_sha256
                    ),
                }
            )
        projection_hash = sha256_json(
            {
                "projection_version": TYPE_CARD_PROJECTION_VERSION,
                "semantic_pack": semantic_contract.identity_payload(),
                "type_cards": cards,
            }
        )
        return (
            cards,
            tuple(restoration),
            projection_hash,
            semantic_contract.identity_payload(),
        )

    def _model_source_unit(
        self,
        unit: Gate2TypeFirstUnitAuthorities,
    ) -> dict[str, Any]:
        visible = [
            value
            for value in unit.evidence_bundle.source_values
            if value.value_type != "source_reference"
        ]
        return {
            "source_unit_key": unit.source_unit_key,
            "source_shape": unit.evidence_bundle.source_family_id,
            "values": [
                {
                    "local_value_key": f"v{index:02d}",
                    "value_type": value.value_type,
                    "literal_value": value.literal_value,
                    "column_meaning": value.column_meaning,
                    "visible_label": value.visible_label,
                    "row_role": value.row_role,
                    "section_role": value.section_role,
                }
                for index, value in enumerate(visible, start=1)
            ],
        }

    def _mapping_receipt(
        self,
        *,
        candidate: Gate2TypeFirstCandidate,
        pack_identity: dict[str, str],
        type_restoration: tuple[dict[str, str], ...],
        units: tuple[Gate2TypeFirstUnitAuthorities, ...],
    ) -> Gate2TypeFirstMappingReceipt:
        local_type_by_id = {
            item["canonical_type_id"]: item["local_type_key"]
            for item in type_restoration
        }
        option_restoration: list[dict[str, Any]] = []
        option_index = 0
        for unit in units:
            for option in sorted(
                unit.compilation.typed_options,
                key=lambda item: item.typed_option_id,
            ):
                option_index += 1
                bindings = [asdict(item) for item in option.role_bindings]
                source_refs = sorted(
                    {item["source_value_ref"] for item in bindings}
                )
                option_restoration.append(
                    {
                        "local_option_key": f"o{option_index:03d}",
                        "local_type_key": local_type_by_id[option.input_type_id],
                        "canonical_type_id": option.input_type_id,
                        "canonical_typed_option_id": option.typed_option_id,
                        "source_unit_key": unit.source_unit_key,
                        "value_bindings": bindings,
                        "source_refs": source_refs,
                        "constructibility_status": "exact_materializable",
                        "option_hash": option.integrity_hash,
                    }
                )
        source_bindings = tuple(
            {
                "source_unit_key": unit.source_unit_key,
                "source_package_integrity_hash": (
                    unit.source_package.integrity_hash
                ),
                "source_unit_integrity_hash": unit.scope.package[
                    "integrity_hash"
                ],
            }
            for unit in units
        )
        material = {
            "schema_version": TYPE_FIRST_MAPPING_SCHEMA_VERSION,
            "request_key": candidate.request_key,
            "request_hash": candidate.request_hash,
            "semantic_pack_id": pack_identity["pack_id"],
            "semantic_pack_version": pack_identity["semantic_version"],
            "semantic_pack_integrity_sha256": pack_identity[
                "integrity_sha256"
            ],
            "type_restoration": list(type_restoration),
            "option_restoration": option_restoration,
            "source_unit_bindings": list(source_bindings),
            "provider_calls_total": 0,
        }
        return Gate2TypeFirstMappingReceipt(
            schema_version=TYPE_FIRST_MAPPING_SCHEMA_VERSION,
            request_key=candidate.request_key,
            request_hash=candidate.request_hash,
            semantic_pack_id=pack_identity["pack_id"],
            semantic_pack_version=pack_identity["semantic_version"],
            semantic_pack_integrity_sha256=pack_identity[
                "integrity_sha256"
            ],
            type_restoration=copy.deepcopy(type_restoration),
            option_restoration=tuple(copy.deepcopy(option_restoration)),
            source_unit_bindings=copy.deepcopy(source_bindings),
            provider_calls_total=0,
            integrity_hash=sha256_json(material),
        )

    def _execute_unit(
        self,
        *,
        unit: Gate2TypeFirstUnitAuthorities,
        decision: dict[str, Any],
        mapping: Gate2TypeFirstMappingReceipt,
    ) -> Gate2TypeFirstUnitExecution:
        plausible_type_ids = tuple(decision["plausible_type_ids"])
        plausible_type_keys = tuple(decision["plausible_type_keys"])
        exact_options = [
            item
            for item in mapping.option_restoration
            if item["source_unit_key"] == unit.source_unit_key
            and item["canonical_type_id"] in plausible_type_ids
        ]
        if len(plausible_type_ids) == 1:
            exact_for_type = [
                item
                for item in exact_options
                if item["canonical_type_id"] == plausible_type_ids[0]
            ]
            if len(exact_for_type) == 1:
                code_reason = "UNIQUE_PLAUSIBLE_TYPE_AND_EXACT_OPTION"
                canonical_choice = {
                    "disposition": "typed_input",
                    "typed_option_id": exact_for_type[0][
                        "canonical_typed_option_id"
                    ],
                }
            elif not exact_for_type:
                code_reason = "PLAUSIBLE_TYPE_WITHOUT_EXACT_OPTION"
                canonical_choice = {
                    "choice": "unclassified",
                    "reason": "single_registry_type_no_safe_record",
                }
            else:
                code_reason = "MULTIPLE_EXACT_OPTIONS"
                canonical_choice = {
                    "choice": "unclassified",
                    "reason": "single_registry_type_no_safe_record",
                }
        elif not plausible_type_ids:
            code_reason = "NO_PLAUSIBLE_TYPE"
            canonical_choice = {
                "disposition": "unclassified_financial_input",
                "reason_code": "no_registry_type",
            }
        else:
            code_reason = "MULTIPLE_PLAUSIBLE_TYPES"
            canonical_choice = {
                "disposition": "unclassified_financial_input",
                "reason_code": "ambiguous_registry_type",
            }
        use_context_v2_1 = code_reason in {
            "PLAUSIBLE_TYPE_WITHOUT_EXACT_OPTION",
            "MULTIPLE_EXACT_OPTIONS",
        }
        expansion_factory = Gate2FinancialSemanticV6DecisionExpansionFactory(
            registry=self.registry
        )
        expansion = (
            expansion_factory.create_from_context_v2_1_candidate(
                model_output=canonical_choice,
                choice_contract=unit.choice_contract,
                packet=unit.packet,
                evidence_bundle=unit.evidence_bundle,
                source_package=unit.source_package,
                compilation=unit.compilation,
            )
            if use_context_v2_1
            else expansion_factory.create(
                model_output=canonical_choice,
                choice_contract=unit.choice_contract,
                packet=unit.packet,
                evidence_bundle=unit.evidence_bundle,
                source_package=unit.source_package,
                compilation=unit.compilation,
            )
        )
        total_factory = Gate2FinancialSemanticV6TotalMaterializerFactory(
            registry=self.registry
        )
        total = (
            total_factory.create_context_v2_1_candidate(
                expansion=expansion,
                model_output=canonical_choice,
                choice_contract=unit.choice_contract,
                packet=unit.packet,
                evidence_bundle=unit.evidence_bundle,
                source_package=unit.source_package,
                compilation=unit.compilation,
            )
            if use_context_v2_1
            else total_factory.create(
                expansion=expansion,
                model_output=canonical_choice,
                choice_contract=unit.choice_contract,
                packet=unit.packet,
                evidence_bundle=unit.evidence_bundle,
                source_package=unit.source_package,
                compilation=unit.compilation,
            )
        )
        trace = {
            "source_unit_key": unit.source_unit_key,
            "source_package_integrity_hash": unit.source_package.integrity_hash,
            "plausible_type_keys": list(plausible_type_keys),
            "plausible_type_ids": list(plausible_type_ids),
            "exact_restored_option_keys": [
                item["local_option_key"] for item in exact_options
            ],
            "code_reason": code_reason,
            "disposition": expansion.disposition,
            "validator_output_hash": expansion.canonical_decision_hash,
            "materialized_fact_hash": total.canonical_artifact_hash,
        }
        return Gate2TypeFirstUnitExecution(
            source_unit_key=unit.source_unit_key,
            plausible_type_keys=plausible_type_keys,
            plausible_type_ids=plausible_type_ids,
            exact_restored_option_keys=tuple(
                item["local_option_key"] for item in exact_options
            ),
            code_reason=code_reason,
            disposition=expansion.disposition,
            expansion=expansion,
            total_materialization=total,
            trace_hash=sha256_json(trace),
        )

    def _validate_prepared(
        self,
        prepared: Gate2TypeFirstPreparedProof,
    ) -> None:
        if (
            not isinstance(prepared, Gate2TypeFirstPreparedProof)
            or prepared.schema_version != TYPE_FIRST_PROOF_SCHEMA_VERSION
            or prepared.candidate.active
            or prepared.candidate.transport_eligible
            or prepared.candidate.provider_calls_total != 0
            or prepared.mapping_receipt.request_hash
            != prepared.candidate.request_hash
            or prepared.response_profile.request_hash
            != prepared.candidate.request_hash
            or prepared.response_profile.mapping_hash
            != prepared.mapping_receipt.integrity_hash
        ):
            _fail("type_first_prepared_proof_invalid")


def false_singleton_comparator(
    *,
    prepared: Gate2TypeFirstPreparedProof,
    execution: Gate2TypeFirstExecution,
) -> dict[str, int | bool]:
    cases = 0
    detected = 0
    typed = 0
    unsafe_typed = 0
    wrong_singleton = 0
    result_by_unit = {item.source_unit_key: item for item in execution.units}
    for unit in prepared.units:
        result = result_by_unit[unit.source_unit_key]
        full_plausible = set(result.plausible_type_ids)
        legacy_visible = set(unit.scope.decision_contract.eligible_type_ids)
        if len(full_plausible) > 1 and len(full_plausible & legacy_visible) == 1:
            cases += 1
            if result.code_reason == "MULTIPLE_PLAUSIBLE_TYPES":
                detected += 1
            if result.disposition == "typed_input":
                typed += 1
                unsafe_typed += 1
            if len(full_plausible) == 1:
                wrong_singleton += 1
    return {
        "false_singleton_cases_total": cases,
        "false_singleton_detected_total": detected,
        "false_singleton_typed_total": typed,
        "unsafe_typed_total": unsafe_typed,
        "wrong_singleton_total": wrong_singleton,
        "provider_calls_total": 0,
        "proof_passed": cases > 0 and detected == cases and typed == 0,
    }


def safe_trace_pack(
    *,
    prepared: Gate2TypeFirstPreparedProof,
    response: dict[str, Any],
    execution: Gate2TypeFirstExecution,
) -> dict[str, Any]:
    response_by_unit = {
        item["source_unit_key"]: item for item in response["unit_decisions"]
    }
    source_by_unit = {
        item["source_unit_key"]: item
        for item in prepared.candidate.payload["source_units"]
    }
    option_by_unit: dict[str, list[dict[str, Any]]] = {}
    for option in prepared.mapping_receipt.option_restoration:
        option_by_unit.setdefault(option["source_unit_key"], []).append(
            {
                "local_option_key": option["local_option_key"],
                "local_type_key": option["local_type_key"],
                "constructibility_status": option["constructibility_status"],
                "option_hash": option["option_hash"],
                "value_bindings_total": len(option["value_bindings"]),
                "source_refs_hash": sha256_json(option["source_refs"]),
            }
        )
    traces = []
    for result in execution.units:
        traces.append(
            {
                "source_unit": copy.deepcopy(source_by_unit[result.source_unit_key]),
                "type_cards": copy.deepcopy(prepared.candidate.payload["type_cards"]),
                "prebound_options": copy.deepcopy(
                    option_by_unit.get(result.source_unit_key, [])
                ),
                "simulated_response": copy.deepcopy(
                    response_by_unit[result.source_unit_key]
                ),
                "restored_local_keys": list(result.plausible_type_keys),
                "code_reason": result.code_reason,
                "validator_result": {
                    "status": "accepted",
                    "output_hash": result.expansion.canonical_decision_hash,
                },
                "materialization": {
                    "owner": "Gate2FinancialEvidenceMaterializerFactory",
                    "disposition": result.disposition,
                    "artifact_hash": (
                        result.total_materialization.canonical_artifact_hash
                    ),
                },
                "replay": {"status": "pending_evidence_replay"},
                "trace_hash": result.trace_hash,
            }
        )
    payload = {
        "schema_version": "broker_reports_kt2_type_first_safe_trace_pack_v1",
        "request": copy.deepcopy(prepared.candidate.payload),
        "response_schema_hash": prepared.response_profile.response_schema_hash,
        "mapping_safe_summary": prepared.mapping_receipt.safe_summary(),
        "simulated_response_hash": execution.simulated_response_hash,
        "traces": traces,
        "privacy": {
            "evidence_class": "PRIVACY_SAFE_STRUCTURAL_COPY",
            "customer_values": False,
            "raw_customer_refs": False,
            "provider_payload": False,
        },
    }
    payload["integrity_hash"] = sha256_json(payload)
    return payload


def _accounting(
    results: list[Gate2TypeFirstUnitExecution],
) -> dict[str, int]:
    counts = {
        "total_units": len(results),
        "typed": 0,
        "unclassified": 0,
        "no_fact": 0,
        "unsupported": 0,
        "technical_failure": 0,
        "excluded": 0,
    }
    for result in results:
        if result.disposition == "typed_input":
            counts["typed"] += 1
        elif result.disposition == "unclassified_financial_input":
            counts["unclassified"] += 1
        elif result.disposition == "no_financial_input":
            counts["no_fact"] += 1
        elif result.disposition == "unsupported":
            counts["unsupported"] += 1
        else:
            counts["technical_failure"] += 1
    terminal = sum(
        counts[key]
        for key in (
            "typed",
            "unclassified",
            "no_fact",
            "unsupported",
            "technical_failure",
            "excluded",
        )
    )
    counts["unaccounted_units"] = counts["total_units"] - terminal
    return counts


def _restored_payload(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_unit_key": item["source_unit_key"],
        "plausible_type_keys": list(item["plausible_type_keys"]),
        "plausible_type_ids": list(item["plausible_type_ids"]),
    }


def _response_object(value: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    import json

    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        _fail("type_first_simulated_response_invalid")
    return parsed


def _fail(code: str) -> None:
    raise Gate2SameSourceTypeFirstProofError(code)
