from __future__ import annotations

from .gate2_financial_evidence_registry import (
    REGISTRY_VERSION_V1,
    FinancialEvidenceCompatibility,
    FinancialEvidenceIdentityPolicy,
    FinancialEvidenceInputTypeDeclaration,
    FinancialEvidenceRoleSpec,
)


INITIAL_CATALOG_VERSION = "broker_reports_gate2_initial_financial_catalog_v1"

FACTORY_REQUIRED = (
    "Gate2FinancialEvidenceRegistryFactory.create with the initial catalog is "
    "the only production financial input type catalog entrypoint"
)
FORBIDDEN = (
    "Router domains, source labels, evidence kinds, technical dispositions "
    "and legacy broad fact IDs must not become catalog type IDs"
)

SUPPORTED_SOURCE_FAMILIES = (
    "broker_reports_normalized_table_projection_v0",
    "semantic_visual_logical_table_v1",
)

LEGACY_BROAD_FINANCIAL_IDS = (
    "cash_movement",
    "currency_fx",
    "fee_commission",
    "income",
    "position_snapshot",
    "trade_operation",
    "withholding_tax",
)
EVIDENCE_KIND_IDS = ("document_summary_evidence",)
LEGACY_TECHNICAL_DISPOSITIONS = ("unknown_source_row",)
FNS_SPECIALIZED_SCHEMA_FAMILIES = (
    "broker_reports_fns_2ndfl_source_facts_v1",
)
DEFERRED_CANDIDATE_IDS = (
    "credit_loss_allowance_movement_v1",
    "credit_loss_allowance_snapshot_v1",
    "equity_balance_snapshot_v1",
    "lease_liability_snapshot_v1",
    "lease_payment_schedule_item_v1",
    "lease_right_of_use_asset_snapshot_v1",
    "payable_balance_snapshot_v1",
    "receivable_balance_snapshot_v1",
    "regulated_asset_balance_snapshot_v1",
    "security_inventory_balance_snapshot_v1",
)

_CORPUS_EVIDENCE_REFS = (
    "safe_receipt:f8862b9a2104a8b4f08b24b6ebe06fc784ce78bb27524e2dd67e8cce92eff1f5",
    "safe_report:BROKER_REPORTS_GATE2_CANONICAL_DOMAIN_GOAL1_ACTUAL_CORPUS_CONCEPT_INVENTORY",
)
_CATALOG_TEST_REF = (
    "test_broker_reports_gate2_financial_evidence_catalog"
)


CASH_BALANCE_SNAPSHOT_V1 = FinancialEvidenceInputTypeDeclaration(
    input_type_id="cash_balance_snapshot_v1",
    registry_version=REGISTRY_VERSION_V1,
    title="Cash balance snapshot",
    definition=(
        "A source-stated cash-class balance for an explicit statement scope "
        "and reporting date. Restricted or segregated balances are excluded "
        "unless the source explicitly classifies them as ordinary cash."
    ),
    semantic_class="state",
    lifecycle="active",
    compatible_source_families=SUPPORTED_SOURCE_FAMILIES,
    required_roles=("amount", "as_of_date", "statement_scope"),
    optional_roles=(
        "balance_class",
        "currency",
        "source_label",
        "unit",
    ),
    forbidden_roles=("event_date", "period_end", "period_start"),
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
            role_id="balance_class",
            value_type="source_text",
            cardinality="zero_or_one",
        ),
        FinancialEvidenceRoleSpec(
            role_id="currency",
            value_type="source_currency",
            cardinality="zero_or_one",
        ),
        FinancialEvidenceRoleSpec(
            role_id="source_label",
            value_type="source_text",
            cardinality="zero_or_one",
        ),
        FinancialEvidenceRoleSpec(
            role_id="unit",
            value_type="source_unit",
            cardinality="zero_or_one",
        ),
    ),
    date_period_requirement="as_of_date_required",
    currency_unit_requirement="currency_or_unit_required",
    source_sign_policy="preserve_source_sign",
    identity_policy=FinancialEvidenceIdentityPolicy(
        identity_roles=(
            "as_of_date",
            "statement_scope",
            "balance_class",
        )
    ),
    provider_description=(
        "Choose only for a source-stated ordinary cash-class balance with an "
        "explicit reporting date, statement scope and source value. Do not "
        "infer unrestricted liquidity from a regulated or segregated asset."
    ),
    materialization_profile_id="cash_balance_materialization_v1",
    validation_profile_id="cash_balance_validation_v1",
    context_projection_rule_id="cash_balance_context_v1",
    examples=(
        "A synthetic statement row explicitly states an ordinary cash balance "
        "for a reporting date and statement scope.",
    ),
    counterexamples=(
        "A synthetic row states a segregated regulatory asset without an "
        "ordinary cash classification.",
        "A synthetic deposit event records movement rather than an as-of "
        "balance.",
    ),
    evidence_refs=_CORPUS_EVIDENCE_REFS,
    test_refs=(_CATALOG_TEST_REF,),
    compatibility=FinancialEvidenceCompatibility(),
)


PRINTED_FINANCIAL_METRIC_V1 = FinancialEvidenceInputTypeDeclaration(
    input_type_id="printed_financial_metric_v1",
    registry_version=REGISTRY_VERSION_V1,
    title="Printed financial metric",
    definition=(
        "A financial total or metric printed by the source for an explicit "
        "reporting scope and date or period. It remains distinct from every "
        "aggregate calculated by Gate 2."
    ),
    semantic_class="aggregate",
    lifecycle="active",
    compatible_source_families=SUPPORTED_SOURCE_FAMILIES,
    required_roles=(
        "amount",
        "printed_label_evidence_ref",
        "statement_scope",
    ),
    optional_roles=(
        "as_of_date",
        "currency",
        "period",
        "source_label",
        "unit",
    ),
    forbidden_roles=("calculation_method", "component_kind"),
    role_specs=(
        FinancialEvidenceRoleSpec(
            role_id="amount",
            value_type="source_decimal",
            cardinality="one",
        ),
        FinancialEvidenceRoleSpec(
            role_id="printed_label_evidence_ref",
            value_type="source_reference",
            cardinality="one",
        ),
        FinancialEvidenceRoleSpec(
            role_id="statement_scope",
            value_type="source_reference",
            cardinality="one",
        ),
        FinancialEvidenceRoleSpec(
            role_id="as_of_date",
            value_type="source_date",
            cardinality="zero_or_one",
        ),
        FinancialEvidenceRoleSpec(
            role_id="currency",
            value_type="source_currency",
            cardinality="zero_or_one",
        ),
        FinancialEvidenceRoleSpec(
            role_id="period",
            value_type="source_period",
            cardinality="zero_or_one",
        ),
        FinancialEvidenceRoleSpec(
            role_id="source_label",
            value_type="source_text",
            cardinality="zero_or_one",
        ),
        FinancialEvidenceRoleSpec(
            role_id="unit",
            value_type="source_unit",
            cardinality="zero_or_one",
        ),
    ),
    date_period_requirement="date_or_period_required",
    currency_unit_requirement="currency_or_unit_required",
    source_sign_policy="preserve_source_sign",
    identity_policy=FinancialEvidenceIdentityPolicy(
        identity_roles=(
            "printed_label_evidence_ref",
            "statement_scope",
            "as_of_date",
            "period",
        )
    ),
    provider_description=(
        "Choose only for a financial total or metric explicitly printed by "
        "the source with a bound label, source value, reporting scope and date "
        "or period. Never use for a Gate 2 calculated aggregate."
    ),
    materialization_profile_id="printed_metric_materialization_v1",
    validation_profile_id="printed_metric_validation_v1",
    context_projection_rule_id="printed_metric_context_v1",
    examples=(
        "A synthetic statement prints a labelled total for an explicit period "
        "and statement scope.",
    ),
    counterexamples=(
        "A total calculated by Gate 2 from child rows.",
        "A repeated visual representation of the same printed source metric.",
    ),
    evidence_refs=_CORPUS_EVIDENCE_REFS,
    test_refs=(_CATALOG_TEST_REF,),
    compatibility=FinancialEvidenceCompatibility(),
)


INITIAL_FINANCIAL_EVIDENCE_DECLARATIONS = (
    CASH_BALANCE_SNAPSHOT_V1,
    PRINTED_FINANCIAL_METRIC_V1,
)

# These pins are deliberately literals. A semantic declaration change must
# update the pin in an explicit review instead of silently reusing the type ID.
INITIAL_SEMANTIC_IDENTITY_PINS = (
    (
        "cash_balance_snapshot_v1",
        "651f655772e728c895d8f94d32ff34eba1dc1ee719232398dbb44f67ae1ba008",
    ),
    (
        "printed_financial_metric_v1",
        "758ca2eadf1a82285d18dd3e13e43a78846bd21c99961263a0cd4be9c1431983",
    ),
)
