# Broker Reports Gate 2 Type-First Inactive Implementation Amendment v1

Status: normative implementation amendment; inactive and transport-ineligible.

Amendment identity:
`broker_reports_gate2_type_first_inactive_implementation_v1`.

Base semantic contract:
[Broker Reports Gate 2 Type-First Fail-Closed v1](BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.md),
identity `broker_reports_gate2_type_first_fail_closed_v1`.

Machine-readable amendment:
[BROKER_REPORTS_GATE2_TYPE_FIRST_INACTIVE_IMPLEMENTATION.v1.json](BROKER_REPORTS_GATE2_TYPE_FIRST_INACTIVE_IMPLEMENTATION.v1.json).

This amendment makes the GOAL 16 contract executable inside existing V6
owners. It does not replace or weaken GOAL 16, implement provider transport,
activate a product route, change production admissions or create an authority.

## 1. Fixed profile identities

| Concern | Exact identity |
| --- | --- |
| Context | `broker_reports_gate2_type_first_context_v1_candidate` |
| Private mapping receipt | `broker_reports_gate2_type_first_mapping_receipt_v1` |
| Response | `broker_reports_gate2_type_first_plausible_types_response_v1` |
| Sealed request receipt | `broker_reports_gate2_type_first_sealed_request_receipt_v1` |
| Request builder | `financial_semantic_v6_type_first_local_proof_v1` |
| Decision | `broker_reports_gate2_type_first_fail_closed_policy_v1` |
| Expansion | `broker_reports_gate2_type_first_decision_expansion_v1` |
| Evidence | `broker_reports_gate2_type_first_decision_evidence_v1` |
| Technical-failure evidence | `broker_reports_gate2_type_first_technical_failure_evidence_v1` |
| Replay | `broker_reports_gate2_type_first_decision_replay_v1` |
| Economy | `broker_reports_gate2_type_first_one_call_no_fallback_v1` |
| Qualification declaration | `broker_reports_gate2_type_first_qualification_profile_v1` |

Every profile is `active=false`, `transport_eligible=false` and
`runtime_activation=false`. GOAL 17 provider submissions, provider responses,
retries, repairs, semantic repairs and fallbacks are all zero.

## 2. Packet profile

`Gate2FinancialSemanticV6PacketFactory.create_type_first_candidate` is the
only additive construction entrypoint. It must consume an already validated
current V6 Packet, Evidence Bundle, source package and Candidate Compilation.
It must not call the historical Context V2.0 builder or create a second
projection.

The model-visible user object has exactly three root members in this insertion
order:

1. `task`
2. `source`
3. `type_cards`

`task` is the exact GOAL 16 task. `source` is a deep byte-equivalent copy of
the current Context V2.1 `source`. `type_cards` are a deep byte-equivalent copy
of the current Context V2.1 `type_cards`, in the same order. Serialization is
UTF-8 minified JSON with insertion order preserved and non-finite values
forbidden.

The candidate contains no `choices`, complete options, differentiators,
unclassified reasons, canonical type IDs, Typed Option IDs, Compiler counts,
bindings, refs, hashes or materialization metadata. The active four-block V6
Packet and all historical sidecars remain byte- and behavior-exact.

## 3. Private mapping receipt

The Packet owner also creates the sole private receipt. It has these ordered
members:

1. `schema_version`
2. `policy_version`
3. `context_profile`
4. `context_view_sha256`
5. `source_projection_sha256`
6. `visible_type_card_order`
7. `local_to_canonical_type_ids`
8. `semantic_pack_identity`
9. `managed_projection_identity`
10. `evidence_bundle_scope`
11. `candidate_compilation_scope`
12. `provider_calls_total`
13. `integrity_sha256`

`local_to_canonical_type_ids` is derived from the current Context V2.1
`type_mappings`; it is never inferred from list position and is never model
visible. `visible_type_card_order` is exactly the candidate card order. The
receipt binds the source projection, Pack, managed projection, Evidence Bundle
and Candidate Compilation used to create the candidate.

`integrity_sha256` is SHA-256 of canonical sorted compact JSON over the receipt
without `integrity_sha256`. Unknown, removed, reordered or resealed mappings
fail with `mapping_receipt_mismatch`. A changed source projection fails with
`source_hash_drift`; a source projection no longer matching the bound Evidence
Bundle fails with `evidence_bundle_scope_mismatch`. Pack/projection and
Compilation scope drift fail with `pack_projection_drift` and
`candidate_compilation_scope_mismatch`.

## 4. Response schema and parser

The Choice owner creates the response profile and owns parsing through
`Gate2FinancialSemanticV6ChoiceContractFactory.create_type_first_response_profile` and
`normalize_financial_semantic_v6_type_first_response`.

The logical schema is exactly:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "plausible_types": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": [
          "type_1",
          "type_2"
        ]
      },
      "minItems": 0,
      "maxItems": 2,
      "uniqueItems": true
    }
  },
  "required": [
    "plausible_types"
  ]
}
```

For each real candidate, `enum` is derived from
`type_cards[*].type_key` and `maxItems` equals the visible card count. The
parser must independently re-enforce the complete logical schema after
provider extraction. It must not sort, deduplicate, repair, retry or fall
back.

Parser error precedence is normative:

| Order | Condition | Exact technical error |
| ---: | --- | --- |
| 1 | JSON text cannot be decoded | `malformed_json` |
| 2 | duplicate root JSON member | `duplicate_response_field` |
| 3 | decoded root is not an object | `response_root_not_object` |
| 4 | `plausible_types` is absent | `missing_plausible_types` |
| 5 | any other root member exists | `extra_response_field` |
| 6 | value is null | `plausible_types_null` |
| 7 | value is not an array | `plausible_types_not_array` |
| 8 | a canonical backend type ID is present | `backend_type_id_forbidden` |
| 9 | a member is not a visible local key | `unknown_type_key` |
| 10 | a local key occurs more than once | `duplicate_type_key` |
| 11 | keys are not an exact subsequence of card order | `out_of_order_type_keys` |

`response_root_not_object` is present in the GOAL 16 machine contract but was
omitted from its Markdown failure table. This amendment makes the machine
contract behavior explicit. `duplicate_response_field` closes the previously
unspecified duplicate-root-member case; it is a technical parser totality
extension and does not change semantic outcomes.

## 5. Sealed logical request

`Gate2FinancialSemanticV6ContextLinterFactory.create_type_first` is the only
additive linter/sealer entrypoint. It consumes:

- the exact GOAL 16 Type-First system message;
- the exact Type-First candidate;
- the Choice-owned exact response schema;
- the Packet-owned private mapping receipt;
- the exact Evidence Bundle, source package and Candidate Compilation.

It validates the complete logical request, exact field order, exact source and
card reuse, receipt integrity, Pack/projection/scope bindings, absence of
private identities and the GOAL 16 byte budget. The provider-neutral logical
request measured as exact `response_schema` plus exact user context must be at
most `2500` UTF-8 bytes. The sealed message/response-format envelope also
records its complete byte size and hash but is not substituted for that GOAL
16 measurement basis.

The sealed request has exactly two messages and one strict provider-neutral
response format. Its receipt binds the complete model-visible request hash,
context hash, schema hash, Prompt hash, mapping receipt hash and invariant
counters. A technical sealing failure writes no Financial Domain result.

## 6. Request builder and provider adapter

`Gate2OpenWebUIRequestBuilder` remains the sole request builder. The additive
profile is accepted only through
`build_from_sealed_type_first`; generic `build` must reject it with the
existing sealed-context-required class of failure. The profile stays outside
the production `GATE2_REQUEST_PROFILES` set and is not imported by a product
Pipe.

The additive method accepts the exact immutable
`Gate2FinancialSemanticV6TypeFirstSealedRequest`, not a caller-built
`model_visible_request` dictionary. Before projecting `model`, it recomputes
the receipt self-hash and the bound request, schema, Prompt, context, source,
logical-request byte and token-estimator values. Raw shape-valid dictionaries,
stale receipts and self-resealed wrong-profile receipts fail closed. The
request also carries a non-serialized builder capability issued only by
`Gate2FinancialSemanticV6ContextLinterFactory.create_type_first`. The builder
binds that capability to the original receipt integrity hash, so a caller
cannot change context metadata or model-visible bytes and then make the
request acceptable merely by recomputing public hashes. Evidence and replay
persist the exact request fields but never serialize or recreate this
capability; replay obtains a fresh sealed request through the Linter owner.

`Gate2ProviderAdapterFactory.create` remains the sole provider-adapter
authority and its semantic behavior is unchanged. The local proof composes the
existing OpenAI profile and public generic entrypoints only:

1. `Gate2ProviderAdapter.prepare_form_data`;
2. the internally invoked
   `Gate2PreparedProviderRequest.validate_schema_binding`;
3. `Gate2ProviderAdapter.extract_prepared_content`.

The support builder/test passes the exact Type-First `response_format`, keeps
the prepared-request and provider-visible-schema hashes, and supplies exactly
one simulated terminal OpenAI envelope. The Choice parser then enforces the
complete Type-First response contract. No Type-First adapter method,
prepared-request method or projection policy is added, and GOAL 17 makes no
three-provider proof claim. The adapter does not decide financial meaning,
sort values or repair responses.

No native transport or model-client execute method is part of GOAL 17.

## 7. Deterministic expansion

`Gate2FinancialSemanticV6DecisionExpansionFactory.create_from_type_first_candidate`
owns the additive decision path. It consumes the Choice-owned parsed ordered
set and Packet-owned mapping receipt, then derives:

| Parsed plausible set | Complete validly prebound options of mapped singleton type | Canonical result |
| --- | --- | --- |
| zero | any | `unclassified_financial_input` / `no_registry_type` |
| two or more | any | `unclassified_financial_input` / `ambiguous_registry_type` |
| one | zero | `unclassified_financial_input` / `single_registry_type_no_safe_record` |
| one | two or more | `unclassified_financial_input` / `single_registry_type_no_safe_record` |
| one | exactly one | restore the exact unchanged V6 Typed Option |

Only `compilation.typed_options` count as complete validly prebound options.
Blocked Compiler attempts never count. Option counts never change the
plausible type set. A missing, changed or multiply restored selected option
fails with `exact_code_owned_typed_option_mismatch`.

The existing canonical validator remains
`Gate2FinancialEvidenceValidatedDecisionFactory.create`. The existing
canonical materializer remains
`Gate2FinancialEvidenceMaterializerFactory.create().materialize`. The local
proof calls these existing APIs directly. No method or behavior is added to
`Gate2FinancialSemanticV6TotalMaterializerFactory`.

## 8. Persistence, evidence and replay

After canonical materialization, the local proof creates the Financial Domain
snapshot only through `Gate2FinancialDomainCatalogFactory.create`, then
serializes/restores it only through
`Gate2FinancialDomainPersistenceFactory.serialize/restore`. Only after that
does the Evidence factory assemble success evidence. It accepts and verifies
the existing snapshot identity, serialized hash and restored equality; it
does not materialize or persist.

`Gate2FinancialSemanticV6DecisionEvidenceFactory.create_type_first_candidate`
owns exact semantic-outcome private evidence, safe projection and per-case
oracle comparison.
`Gate2FinancialSemanticV6DecisionEvidenceFactory.create_type_first_technical_failure`
owns technical-failure evidence. The corresponding versioned serialize,
restore and replay entrypoints stay in the same evidence module; one replay
dispatcher may cover both versioned branches.

Successful-outcome private evidence binds:

- exact logical and prepared requests;
- exact simulated terminal envelope and adapter-extracted content;
- parsed ordered plausible type set;
- code-derived canonical Choice and Expansion;
- canonical materialization and serialized Financial Domain snapshot;
- all Packet, mapping, Pack, projection, Evidence Bundle and Compilation
  authority hashes;
- zero-call Economy accounting;
- independent oracle answer and comparator counters.

Safe evidence contains only allowlisted identities, hashes, cardinalities,
outcome/error classes and counters. It contains no source literals, customer
values, raw provider content, credentials or local paths.

Replay must rebuild the prepared request, parser result and Expansion, verify
the already materialized artifact, and restore the serialized Financial
Domain snapshot through the existing Persistence owner with exact equality.
Replay performs no provider call.

Technical failures retain the exact private invalid input needed to reproduce
the failure plus stage, exact error code and available authority hashes. They
create no canonical decision, materialized record or Financial Domain
snapshot. Exact invalid input is private-only; its safe projection contains
only the input hash, exact error code, failure stage and non-sensitive counts.
Failure replay must reproduce the same exact code and prove zero canonical
decisions, materializations and snapshots without repair. This branch is
normative even though the successful local E2E is shown as a linear pipeline.

## 9. Economy and qualification declaration

The request profile maps to the existing financial-evidence workload through
`Gate2EconomyBudgetSessionFactory.create`. Its additive Type-First enforcement
is:

```json
{
  "maximum_provider_calls_per_operation": 1,
  "maximum_fallback_calls_per_operation": 0,
  "provider_calls_authorized_total": 0,
  "provider_submissions_total": 0,
  "provider_responses_total": 0,
  "retry_total": 0,
  "repair_total": 0,
  "semantic_repair_total": 0,
  "fallback_total": 0
}
```

The current generic financial-evidence workload permits one fallback. Reusing
that value without a request-profile-specific zero-fallback guard would
violate GOAL 16. The additive guard must not change historical workload
profiles.

The existing
`Gate2FinancialSemanticV6ContextV21BudgetSmokeCoordinator` may expose only
`type_first_profile_declaration` in GOAL 17. The declaration contains the
profile identities, counters and hard gates. It must not call
`execute_slot`, create clients, consume slots or invoke transport.

The Evidence owner computes per-case comparator counters from an independent
test oracle. The oracle never affects the product decision. Required counters
and hard gates remain exactly those in GOAL 16.

## 10. Zero-call local proof

The zero-call proof is orchestrated only by the maintained GOAL 17 support
builder and tests. It is not imported by product runtime and is not a new
domain owner or qualification coordinator.

The executable proof uses the existing OpenAI adapter generic
`prepare_form_data` and `extract_prepared_content` entrypoints with exactly one
simulated terminal envelope:

```text
Packet candidate and private mapping receipt
-> Choice response profile
-> Context Linter and sealed logical request
-> Request Builder
-> OpenAI prepared request
-> one simulated terminal OpenAI envelope
-> Provider Adapter extraction
-> Type-First parser
-> Expansion
-> canonical validation and materialization
-> Financial Domain snapshot serialize/restore
-> Decision Evidence serialize/restore
-> replay and exact snapshot comparison
```

The minimum adversarial matrix is:

1. true zero, response empty;
2. true singleton, one matching option;
3. true singleton, zero matching options;
4. true singleton, multiple matching options;
5. true multiple, response multiple;
6. true multiple, false singleton, one matching option;
7. true zero, false singleton, one matching option;
8. wrong singleton type;
9. unknown local key;
10. duplicate local key;
11. out-of-order local keys;
12. mapping receipt drift;
13. Pack/projection hash drift;
14. source hash or Evidence Bundle scope drift;
15. exact option restoration mismatch;
16. non-object response root;
17. duplicate root response member.

False-singleton cases are allowed to expose the known structural weakness:
one semantically wrong singleton plus one complete option can materialize.
The comparator must record the unsafe outcome; it must not rewrite or suppress
the product-path result.

## 11. Activation and compatibility

GOAL 17 must leave unchanged:

- active V6 Packet payload and hash;
- historical Slim, Context V2.0 and Context V2.1 profiles;
- active and historical Choice schemas;
- Prompt and managed asset bytes;
- Semantic Pack and type boundaries;
- provider transport behavior;
- OpenWebUI imports and generated bundle module/import topology;
- feature valves and product Pipes;
- production admissions and model identities.

Because the maintained request-builder and Economy modules are embedded
closed-world sources, all three generated Pipe bundle bytes are rebuilt
deterministically. This generated parity change adds no Type-First product
consumer and changes no active Pipe behavior.

The Type-First request profile is supported only by local proof entrypoints.
Provider calls, runtime activation and production admission changes are zero.

## 12. Authority and traceability matrix

All rows reuse an existing owner. The table is a compact human-readable index;
its symbol and test labels are intentionally abbreviated and do not enumerate
every governed anchor. The companion JSON is the sole machine-readable
traceability authority: it records the complete symbol set as
`module:qualname` and the complete test set as exact pytest node IDs. The
architecture test resolves every JSON anchor and fails closed on drift.

| Clause | Existing owner | Representative symbol(s) or unchanged entrypoint | Representative test anchor | Evidence |
| --- | --- | --- | --- | --- |
| `TF-01` identities/inactive state | V6 Packet, Choice, Linter owners | `TYPE_FIRST_PROFILE_IDENTITIES` | `test_type_first_contract_is_inactive_and_changes_no_admission_or_valve`; `test_type_first_request_profile_is_exact_sealed_only_and_inactive`; `test_type_first_qualification_declaration_is_frozen_and_non_executable` | safe profile summaries |
| `TF-02` exact three-field Packet | `Gate2FinancialSemanticV6PacketFactory` | `create_type_first_candidate` | `test_type_first_candidate_reuses_exact_context_v2_1_semantics`; `test_context_v2_1_has_exact_minimal_surface_and_literal_occurrence_parity` | candidate hash and byte counts |
| `TF-03` private mapping | same Packet owner | `Gate2FinancialSemanticV6TypeFirstMappingReceipt`; `validate_financial_semantic_v6_type_first_material` | `test_type_first_candidate_reuses_exact_context_v2_1_semantics`; `test_type_first_mapping_receipt_fails_closed_by_drift_class` | private receipt hash; safe hash only |
| `TF-04` response/parser | `Gate2FinancialSemanticV6ChoiceContractFactory` | `create_type_first_response_profile`; `normalize_financial_semantic_v6_type_first_response` | `test_exact_nine_response_negative_fixtures_fail_closed`; `test_type_first_schema_and_parser_are_exact_and_fail_closed` | parser result or exact technical code |
| `TF-05` sealed request | `Gate2FinancialSemanticV6ContextLinterFactory` | `create_type_first` | `test_type_first_linter_enforces_exact_2500_byte_measurement`; `test_all_governed_context_v2_1_requests_are_exact_sealed_and_within_budget` | sealed-request receipt |
| `TF-06` request construction | `Gate2OpenWebUIRequestBuilder` | `build_from_sealed_type_first` | `test_type_first_request_profile_is_exact_sealed_only_and_inactive`; `test_type_first_request_builder_requires_exact_integrity_bound_seal`; existing Context V2.1 sealed-entrypoint test | exact logical/prepared request hashes |
| `TF-07` provider binding/extraction | `Gate2ProviderAdapterFactory` and `Gate2PreparedProviderRequest` | existing `prepare_form_data`, `validate_schema_binding`, `extract_prepared_content` | `test_type_first_prepared_request_and_schema_drift_fail_closed`; `test_success_chain_is_terminal_exact_and_zero_call` | provider-visible schema and prepared-request hashes |
| `TF-08` decision table | `Gate2FinancialSemanticV6DecisionExpansionFactory` | `create_from_type_first_candidate` | `test_real_compiler_zero_one_and_multiple_option_fixtures_are_proven`; `test_semantic_false_sets_are_measured_without_repair`; `test_at_least_fifteen_adversarial_cases_fail_closed_and_replay` | parsed set, canonical Choice and Expansion hashes |
| `TF-09` validation/materialization | canonical Validation and Materialization owners | existing `create`; existing `materialize` | `test_validated_decision_uses_canonical_materialization_totality`; `test_typed_expansion_always_materializes_with_all_structural_checks` | canonical artifact hash |
| `TF-10` V6 totality compatibility | `Gate2FinancialSemanticV6TotalMaterializerFactory` | unchanged `create`; not used as a Type-First entrypoint | `test_success_chain_is_terminal_exact_and_zero_call`; `test_totality_module_delegates_to_canonical_materializer_without_repair` | canonical artifact hash |
| `TF-11` snapshot persistence | Financial Domain Catalog and Persistence owners | existing `create`, `serialize`, `restore` | `test_success_chain_is_terminal_exact_and_zero_call`; `test_all_twelve_provider_case_paths_are_exact_terminal_proofs` | serialized snapshot hash |
| `TF-12` evidence/replay/comparator | `Gate2FinancialSemanticV6DecisionEvidenceFactory` | `create_type_first_candidate`, `create_type_first_technical_failure` and versioned restore/replay | `test_success_chain_is_terminal_exact_and_zero_call`, `test_semantic_false_sets_are_measured_without_repair` and `test_at_least_fifteen_adversarial_cases_fail_closed_and_replay` | private evidence hash and privacy-safe counter projection |
| `TF-13` Economy | `Gate2EconomyBudgetSessionFactory` | `create`; `type_first_accounting_receipt`; `validate_type_first_economy_accounting_receipt` | `test_type_first_economy_is_one_call_no_fallback_without_policy_drift`; `test_default_and_fallback_call_budgets_are_enforced` | zero-call accounting |
| `TF-14` local proof | maintained GOAL 17 support builder/tests | `build_type_first_zero_call_e2e_evidence` | `test_success_chain_is_terminal_exact_and_zero_call`; `test_at_least_fifteen_adversarial_cases_fail_closed_and_replay`; `test_support_runner_has_no_transport_or_provider_invocation_callsite`; current-output and self-integrity tests | exact private proof and safe projection |
| `TF-15` qualification declaration | existing Context V2.1 Budget Smoke coordinator | `type_first_profile_declaration` | `test_type_first_qualification_declaration_is_frozen_and_non_executable`; `test_goal12_reuses_plan_client_evidence_and_report_authorities` | declaration hash; calls zero |
| `TF-16` compatibility/activation | architecture authority tests | no additive implementation symbol | `test_type_first_contract_is_inactive_and_changes_no_admission_or_valve`; `test_product_pipes_imports_valves_and_consumers_are_immutable`; `test_generated_bundle_module_topology_is_unchanged`; `test_generated_bundle_modules_match_maintained_source` | change accounting all zero |

The implementation PR must update this matrix only when a symbol or test name
changes. Evidence paths remain the later GOAL 17 report and safe receipt; this
docs-first amendment does not claim that implementation evidence already
exists.

**STOP: this amendment alone does not authorize provider transport or runtime
activation.**
