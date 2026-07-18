# Broker Reports Gate 2 Domain Candidate-Binding Profiles v0

Date: 2026-07-11

Status: `GATE2_DOMAIN_BINDING_PROFILES_READY`

Schema version: `broker_reports_domain_candidate_binding_profile_v0`

## 1. Purpose

One shared candidate-binding kernel discovers reproducible values and
mechanical relations. A domain profile supplies only the semantic allowlist
needed to bind those shared candidates to one source-fact domain.

Profiles prevent two failure modes:

- copying a different candidate-discovery implementation into every domain;
- using one unconstrained generic schema that permits meaningless role
  assignments.

## 2. Profile envelope

```json
{
  "schema_version": "broker_reports_domain_candidate_binding_profile_v0",
  "profile_id": "binding_profile_income_v0",
  "domain": "income",
  "roles": {},
  "required_roles": [],
  "required_role_groups": [],
  "required_relation_kinds": [],
  "required_relation_role_sets": {},
  "optional_relation_kinds": [],
  "forbidden_relation_kinds": [],
  "candidate_reuse": {},
  "candidate_reuse_policy": "forbidden_unless_explicitly_allowed",
  "allowed_candidate_kinds": [],
  "allowed_fact_field_paths": [],
  "optional_roles": [],
  "mutually_exclusive_role_groups": [],
  "role_cardinality": {},
  "subtypes": [],
  "unknown_policy": "null_or_unknown_source_row",
  "ambiguity_policy": "explicit_model_resolution_required",
  "minimum_evidence": {},
  "completeness_policy": "complete_forbidden_when_linked_issues_limit_confirmation",
  "confidence_policy": "model_assigned_but_validator_bounded",
  "downstream_policy": "gate2_source_facts_only",
  "finalizer_semantic_choice_allowed": false,
  "tax_calculation_allowed": false,
  "declaration_mapping_allowed": false,
  "cross_document_consolidation_allowed": false
}
```

Every `roles.<semantic_role>` contains exactly:

```json
{
  "fact_field_path": "normalized_values.amount",
  "candidate_kinds": ["decimal_amount"]
}
```

The allowed candidate-kind set is the union of `roles[].candidate_kinds`.
Allowed fact fields are the role paths. A candidate is usable only when its
kind, domain, role, and field path all agree with the profile and its own
allowlists.

## 3. Common cardinality and null rules

The v0 common rules are:

- each semantic role may be assigned at most once;
- each fact field path may be assigned at most once;
- every `required_roles[]` role must be assigned exactly once for a typed fact;
- every `required_role_groups[]` group requires at least one member;
- other roles are optional and may be omitted when no valid candidate exists;
- candidate reuse is forbidden unless every reused role is explicitly `true`
  in `candidate_reuse`;
- all shipped v0 profiles have an empty `candidate_reuse` map;
- an absent required role does not become a guessed or null accepted typed
  fact; the model must return a valid `unknown_source_row` or the selection
  fails;
- equal-value ambiguity must be resolved explicitly by candidate id and
  `resolved_ambiguity_group_refs`;
- a row with unresolved issue refs cannot claim `completeness=complete`;
- confidence never overrides missing role, relation, provenance, issue, or
  coverage checks.

Relations present in the package but not required by the profile are optional
mechanical evidence. A foreign, invalid, cross-row, or wrong-domain relation is
always forbidden. A profile does not authorize the model to create a relation.
For a required relation, `required_relation_role_sets` names the selected roles
whose candidate ids must participate in that exact relation; selecting an
unrelated relation of the same kind fails closed.

## 4. Profile matrix

### 4.1 `cash_movement`

| Semantic role | Fact field | Allowed kinds | Requirement |
| --- | --- | --- | --- |
| `movement_amount` | `normalized_values.amount` | `decimal_amount` | required |
| `movement_currency` | `normalized_values.currency` | `currency_code` | optional |
| `movement_date` | `normalized_values.date` | `date` | optional |
| `movement_direction` | `extracted_fields.movement_type_candidate` | `categorical_direction` | optional |
| `movement_description` | `extracted_fields.description_value_refs` | `short_visible_label` | optional |

Required relations: none. Subtypes:
`deposit|withdrawal|credit|debit|unknown`.

### 4.2 `income`

| Semantic role | Fact field | Allowed kinds | Requirement |
| --- | --- | --- | --- |
| `income_amount` | `normalized_values.amount` | `decimal_amount` | required |
| `income_currency` | `normalized_values.currency` | `currency_code` | optional |
| `income_date` | `normalized_values.date` | `date` | optional |
| `income_subtype` | `extracted_fields.income_type_candidate` | `categorical_direction`, `short_visible_label` | optional |
| `income_source_country` | `extracted_fields.source_country_value_refs` | `short_visible_label` | optional |

Required relations: none. Subtypes:
`dividend|coupon|interest|sale_proceeds|other|unknown`.

### 4.3 `withholding_tax`

| Semantic role | Fact field | Allowed kinds | Requirement |
| --- | --- | --- | --- |
| `tax_amount` | `normalized_values.amount` | `decimal_amount` | required |
| `tax_currency` | `normalized_values.currency` | `currency_code` | required |
| `tax_date` | `normalized_values.date` | `date` | optional |
| `tax_country` | `normalized_values.label` | `short_visible_label` | optional |

Required relation: `amount_with_currency`. Subtypes:
`domestic|foreign|unknown`.

The relation does not assert creditability, tax jurisdiction, or linkage to an
income fact.

### 4.4 `fee_commission`

| Semantic role | Fact field | Allowed kinds | Requirement |
| --- | --- | --- | --- |
| `fee_amount` | `normalized_values.amount` | `decimal_amount` | required |
| `fee_currency` | `normalized_values.currency` | `currency_code` | optional |
| `fee_date` | `normalized_values.date` | `date` | optional |
| `fee_subtype` | `extracted_fields.fee_type_candidate` | `categorical_direction`, `short_visible_label` | optional |

Required relations: none. Subtypes:
`broker_commission|exchange_fee|custody_fee|other|unknown`.

### 4.5 `position_snapshot`

| Semantic role | Fact field | Allowed kinds | Requirement |
| --- | --- | --- | --- |
| `position_instrument` | `normalized_values.identifier` | `instrument_identifier`, `instrument_label` | required |
| `position_quantity` | `normalized_values.quantity` | `quantity` | quantity-or-valuation group |
| `position_valuation` | `normalized_values.amount` | `decimal_amount`, `source_provided_total` | quantity-or-valuation group |
| `position_currency` | `normalized_values.currency` | `currency_code` | optional |
| `snapshot_date` | `normalized_values.date` | `date` | optional |

At least one of `position_quantity|position_valuation` is required. Required
relations: none. A discovered `quantity_with_instrument` relation is optional
in v0. Subtypes: `security_position|cash_position|other|unknown`.

### 4.6 `trade_operation`

| Semantic role | Fact field | Allowed kinds | Requirement |
| --- | --- | --- | --- |
| `trade_direction` | `extracted_fields.operation_type_candidate` | `categorical_direction` | required |
| `trade_instrument` | `normalized_values.identifier` | `instrument_identifier`, `instrument_label` | required |
| `trade_quantity` | `normalized_values.quantity` | `quantity` | quantity-or-amount group |
| `trade_amount` | `normalized_values.amount` | `decimal_amount` | quantity-or-amount group |
| `trade_price` | `normalized_values.rate` | `decimal_amount`, `explicit_fx_rate` | optional |
| `trade_date` | `normalized_values.date` | `date` | optional |
| `trade_fee` | `normalized_values.converted_amount` | `decimal_amount` | optional |

At least one of `trade_quantity|trade_amount` is required. Required relations:
none in v0. `same_row_candidate_group` and `quantity_with_instrument` are
optional structural evidence. Subtypes:
`buy|sell|redemption|transfer|corporate_action|unknown`.

The profile does not decide trade versus settlement date, unit price, gross
amount, fee deductibility, or consolidation.

### 4.7 `currency_fx`

| Semantic role | Fact field | Allowed kinds | Requirement |
| --- | --- | --- | --- |
| `base_amount` | `normalized_values.amount` | `decimal_amount` | required |
| `quote_amount` | `normalized_values.converted_amount` | `decimal_amount` | required |
| `base_currency` | `normalized_values.currency` | `currency_code` | required |
| `quote_currency` | `normalized_values.label` | `currency_code` | required |
| `explicit_rate` | `normalized_values.rate` | `explicit_fx_rate`, `decimal_amount` | optional |
| `rate_date` | `normalized_values.date` | `date` | optional |

Required relation: `base_quote_amount_currency_group`. Subtypes:
`currency_amount|explicit_rate|source_provided_conversion|unknown`.

Source order and the mechanical group do not choose base versus quote. Those
assignments are model choices constrained to exact candidate ids.

### 4.8 `document_summary_evidence`

| Semantic role | Fact field | Allowed kinds | Requirement |
| --- | --- | --- | --- |
| `summary_value` | `normalized_values.amount` | `source_provided_total`, `decimal_amount` | required |
| `summary_currency` | `normalized_values.currency` | `currency_code` | optional |
| `summary_date` | `normalized_values.date` | `date` | optional |
| `summary_label` | `normalized_values.label` | `short_visible_label` | optional |

Required relations: none. Subtypes:
`source_summary|document_total|section_total|unknown`.

Only a source-provided value is represented. The model and finalizer must not
calculate a new total.

### 4.9 `unknown_source_row`

This profile has no roles, required role groups, or relations. Its only subtype
is `unknown`.

A valid unknown result has no selected bindings or relations, has at least one
safe uncertainty code, uses `confidence=low|none`, and uses
`completeness=uncertain|blocked`.

## 5. Semantic responsibility

The model chooses the candidate id, semantic role, fact field triple; optional
relation ids; subtype; uncertainty; confidence; and completeness within the
profile and provider schema.

The profile does not let the finalizer choose among candidates, assign a role,
resolve ambiguity, infer gross/net or base/quote, link income/tax/fee facts, or
repair an incomplete model decision.

## 6. Downstream restrictions

All profiles set:

```text
finalizer_semantic_choice_allowed=false
tax_calculation_allowed=false
declaration_mapping_allowed=false
cross_document_consolidation_allowed=false
```

Candidate binding produces source facts only. Gate 3 ledgers and
cross-document consolidation, plus Gate 4 tax logic, declaration mapping and
spreadsheet generation,
remain out of scope.

## 7. Versioning and extension rule

A new domain or role requires an explicit profile version and tests through the
same kernel, binding validator, finalizer, strict source-fact validator, and
stitcher. It must not add a private domain-specific discovery kernel.

Candidate binding remains opt-in. Packages without the complete v0 candidate,
relation, and profile contracts remain on the legacy runtime and are not
silently upgraded.
