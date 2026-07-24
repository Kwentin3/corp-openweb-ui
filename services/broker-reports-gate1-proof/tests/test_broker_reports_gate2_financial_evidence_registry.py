from __future__ import annotations

import ast
import sys
from dataclasses import fields, replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    REGISTRY_ID,
    REGISTRY_VERSION_V1,
    FinancialEvidenceCompatibility,
    FinancialEvidenceIdentityPolicy,
    FinancialEvidenceInputTypeDeclaration,
    FinancialEvidenceLegacyMapping,
    FinancialEvidenceRoleSpec,
    FinancialEvidenceTypeAlias,
    Gate2FinancialEvidenceRegistryError,
    Gate2FinancialEvidenceRegistryFactory,
    financial_evidence_semantic_fingerprint,
)


MODULE_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_evidence_registry.py"
)


def _declaration(
    *,
    input_type_id: str = "synthetic_balance_snapshot_v1",
    lifecycle: str = "active",
) -> FinancialEvidenceInputTypeDeclaration:
    return FinancialEvidenceInputTypeDeclaration(
        input_type_id=input_type_id,
        registry_version=REGISTRY_VERSION_V1,
        title="Synthetic balance snapshot",
        definition=(
            "A source-stated balance for an explicit statement scope and "
            "reporting date."
        ),
        semantic_class="state",
        lifecycle=lifecycle,
        compatible_source_families=("statement_balance",),
        required_roles=("amount", "as_of_date", "statement_scope"),
        optional_roles=("currency", "unit", "source_label"),
        forbidden_roles=("event_date",),
        role_specs=(
            FinancialEvidenceRoleSpec(
                role_id="amount",
                value_type="source_decimal",
                cardinality="one",
            ),
            FinancialEvidenceRoleSpec(
                role_id="as_of_date",
                value_type="source_date",
                cardinality="one",
            ),
            FinancialEvidenceRoleSpec(
                role_id="statement_scope",
                value_type="source_reference",
                cardinality="one",
            ),
            FinancialEvidenceRoleSpec(
                role_id="currency",
                value_type="source_currency",
                cardinality="zero_or_one",
            ),
            FinancialEvidenceRoleSpec(
                role_id="unit",
                value_type="source_unit",
                cardinality="zero_or_one",
            ),
            FinancialEvidenceRoleSpec(
                role_id="source_label",
                value_type="source_text",
                cardinality="zero_or_one",
            ),
        ),
        date_period_requirement="as_of_date_required",
        currency_unit_requirement="currency_or_unit_required",
        source_sign_policy="preserve_source_sign",
        identity_policy=FinancialEvidenceIdentityPolicy(
            identity_roles=("as_of_date", "statement_scope"),
        ),
        provider_description=(
            "Choose only for a source-stated balance with an explicit date "
            "and statement scope."
        ),
        materialization_profile_id="source_balance_materialization_v1",
        validation_profile_id="source_balance_validation_v1",
        context_projection_rule_id="source_balance_context_v1",
        examples=(
            "Synthetic statement line with a balance and reporting date.",
        ),
        counterexamples=(
            "Synthetic cash movement event without an as-of balance.",
        ),
        evidence_refs=("safe_fixture:synthetic_statement_balance_v1",),
        test_refs=(
            "test_broker_reports_gate2_financial_evidence_registry",
        ),
        compatibility=FinancialEvidenceCompatibility(),
    )


def _factory(
    *declarations: FinancialEvidenceInputTypeDeclaration,
    aliases: tuple[FinancialEvidenceTypeAlias, ...] = (),
) -> Gate2FinancialEvidenceRegistryFactory:
    return Gate2FinancialEvidenceRegistryFactory(
        declarations=declarations,
        aliases=aliases,
        semantic_identity_pins=tuple(
            (
                declaration.input_type_id,
                financial_evidence_semantic_fingerprint(declaration),
            )
            for declaration in declarations
        ),
    )


def _assert_code(
    code: str,
    factory: Gate2FinancialEvidenceRegistryFactory,
) -> None:
    with pytest.raises(Gate2FinancialEvidenceRegistryError) as exc:
        factory.create()
    assert exc.value.code == code


def test_empty_registry_snapshot_is_pure_deterministic_and_immutable():
    first = Gate2FinancialEvidenceRegistryFactory(
        declarations=(),
        semantic_identity_pins=(),
    ).create()
    second = Gate2FinancialEvidenceRegistryFactory(
        declarations=(),
        semantic_identity_pins=(),
    ).create()

    assert first == second
    assert first.registry_id == REGISTRY_ID
    assert first.registry_version == REGISTRY_VERSION_V1
    assert first.registry_hash == second.registry_hash
    assert len(first.registry_hash) == 64
    assert first.declarations == ()
    assert first.aliases == ()
    assert first.provider_type_enum() == ()

    with pytest.raises(AttributeError):
        first.registry_hash = "changed"  # type: ignore[misc]


def test_registry_is_the_single_ordered_source_for_all_type_profiles():
    experimental = _declaration(
        input_type_id="experimental_metric_v1",
        lifecycle="experimental",
    )
    active = _declaration()
    snapshot = _factory(experimental, active).create()

    assert tuple(
        item.input_type_id for item in snapshot.declarations
    ) == (
        "experimental_metric_v1",
        "synthetic_balance_snapshot_v1",
    )
    assert snapshot.provider_type_enum() == (
        "synthetic_balance_snapshot_v1",
    )
    assert snapshot.provider_type_enum(include_experimental=True) == (
        "experimental_metric_v1",
        "synthetic_balance_snapshot_v1",
    )
    assert (
        snapshot.provider_description(active.input_type_id)
        == active.provider_description
    )
    assert (
        snapshot.materialization_profile_id(active.input_type_id)
        == active.materialization_profile_id
    )
    assert (
        snapshot.validation_profile_id(active.input_type_id)
        == active.validation_profile_id
    )
    assert (
        snapshot.context_projection_rule_id(active.input_type_id)
        == active.context_projection_rule_id
    )
    _assert_code(
        "financial_evidence_registry_type_unknown",
        _UnknownTypeFactory(snapshot),
    )


class _UnknownTypeFactory:
    def __init__(self, snapshot) -> None:
        self.snapshot = snapshot

    def create(self):
        return self.snapshot.get("free_form_model_type_v1")


def test_declaration_order_does_not_change_registry_hash():
    first = _declaration(input_type_id="first_synthetic_type_v1")
    second = _declaration(input_type_id="second_synthetic_type_v1")

    assert _factory(first, second).create().registry_hash == _factory(
        second, first
    ).create().registry_hash


def test_duplicate_type_ids_fail_closed():
    declaration = _declaration()
    _assert_code(
        "financial_evidence_registry_duplicate_type_id",
        Gate2FinancialEvidenceRegistryFactory(
            declarations=(declaration, declaration),
            semantic_identity_pins=(
                (
                    declaration.input_type_id,
                    financial_evidence_semantic_fingerprint(declaration),
                ),
            ),
        ),
    )


def test_conflicting_roles_fail_closed():
    declaration = _declaration()
    changed = replace(
        declaration,
        forbidden_roles=("amount",),
    )
    _assert_code(
        "financial_evidence_registry_conflicting_roles",
        _factory(changed),
    )


def test_missing_role_specs_fail_closed():
    declaration = _declaration()
    changed = replace(
        declaration,
        role_specs=declaration.role_specs[:-1],
    )
    _assert_code(
        "financial_evidence_registry_role_specs_incomplete",
        _factory(changed),
    )


def test_active_type_without_corpus_evidence_or_tests_fails_closed():
    declaration = replace(
        _declaration(),
        evidence_refs=(),
        test_refs=(),
    )
    _assert_code(
        "financial_evidence_registry_active_evidence_missing",
        _factory(declaration),
    )


def test_silent_semantic_change_under_pinned_id_fails_closed():
    declaration = _declaration()
    old_fingerprint = financial_evidence_semantic_fingerprint(declaration)
    changed = replace(
        declaration,
        definition="A different source-local meaning under the same ID.",
    )
    _assert_code(
        "financial_evidence_registry_semantic_identity_changed",
        Gate2FinancialEvidenceRegistryFactory(
            declarations=(changed,),
            semantic_identity_pins=(
                (changed.input_type_id, old_fingerprint),
            ),
        ),
    )


def test_alias_cycles_and_unknown_targets_fail_closed():
    declaration = _declaration()
    cycle = (
        FinancialEvidenceTypeAlias(
            alias_id="legacy_balance_a_v1",
            target_id="legacy_balance_b_v1",
            artifact_schema_versions=("legacy_facts_v0",),
        ),
        FinancialEvidenceTypeAlias(
            alias_id="legacy_balance_b_v1",
            target_id="legacy_balance_a_v1",
            artifact_schema_versions=("legacy_facts_v0",),
        ),
    )
    _assert_code(
        "financial_evidence_registry_alias_cycle",
        _factory(declaration, aliases=cycle),
    )
    _assert_code(
        "financial_evidence_registry_alias_target_unknown",
        _factory(
            declaration,
            aliases=(
                FinancialEvidenceTypeAlias(
                    alias_id="legacy_balance_v1",
                    target_id="missing_balance_v1",
                    artifact_schema_versions=("legacy_facts_v0",),
                ),
            ),
        ),
    )


def test_version_scoped_alias_resolves_without_changing_canonical_id():
    declaration = _declaration()
    alias = FinancialEvidenceTypeAlias(
        alias_id="legacy_balance_v1",
        target_id=declaration.input_type_id,
        artifact_schema_versions=("legacy_facts_v0",),
    )
    snapshot = _factory(declaration, aliases=(alias,)).create()

    assert snapshot.resolve_type_id(alias.alias_id) == declaration.input_type_id
    assert snapshot.get(alias.alias_id) is declaration
    assert snapshot.provider_type_enum() == (declaration.input_type_id,)


def test_unknown_compatibility_target_and_unversioned_legacy_mapping_fail():
    declaration = _declaration()
    unknown_predecessor = replace(
        declaration,
        compatibility=FinancialEvidenceCompatibility(
            predecessor_input_type_ids=("missing_predecessor_v1",),
        ),
    )
    _assert_code(
        "financial_evidence_registry_compatibility_target_unknown",
        _factory(unknown_predecessor),
    )

    unversioned = replace(
        declaration,
        compatibility=FinancialEvidenceCompatibility(
            legacy_mappings=(
                FinancialEvidenceLegacyMapping(
                    legacy_type_id="legacy_balance",
                    artifact_schema_versions=(),
                    status="candidate",
                ),
            ),
        ),
    )
    _assert_code(
        "financial_evidence_registry_legacy_version_scope_missing",
        _factory(unversioned),
    )


def test_registry_contract_has_no_gate3_tax_or_declaration_fields():
    names = {
        field.name
        for field in fields(FinancialEvidenceInputTypeDeclaration)
    }
    assert not names & {
        "tax_rate",
        "deductibility",
        "declaration_field",
        "gate3_relevance",
        "cost_basis",
        "profit_loss_methodology",
    }


def test_registry_module_is_closed_world_and_has_no_runtime_dependencies():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(
                alias.name.split(".", 1)[0] for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])

    assert imported_roots <= {
        "__future__",
        "dataclasses",
        "hashlib",
        "json",
        "re",
        "typing",
        "gate2_financial_evidence_catalog",
    }
    for forbidden in (
        "ArtifactStore",
        "requests",
        "httpx",
        "provider_client",
        "customer",
        "process.env",
        "os.environ",
    ):
        assert forbidden not in source
    assert "FACTORY_REQUIRED" in source
    assert "FORBIDDEN" in source
