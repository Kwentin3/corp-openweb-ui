# Broker Reports Gate 5 Full Declaration Definition Authoring v0

Status: `CURRENT SUPPORTING CONTRACT`

Implementation status: `INACTIVE G5.28 AUTHORING PROOF`

G5.28 verdict: `PARTIALLY_PROVEN`

Trusted publication status: `REVIEW_REJECTED`

This contract owns the smallest tested authoring boundary for a full root
Declaration Definition. It does not own case-time scope resolution, declaration
assembly, tax calculation, projection, XML or PDF.

## Owners

The only candidate-payload and deterministic-validation construction path is:

```text
Gate5FullDeclarationDefinitionAuthoringFactory.create
```

The exact clean-model candidate is loaded and replayed only through:

```text
Gate5FullDeclarationDefinitionCandidateFactory.create
```

The repository publication gate is:

```text
Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create
```

The G5.28 review resource is `review_rejected`; therefore the last factory must
fail with `gate5_full_declaration_definition_not_published`. A validated LLM
candidate is evidence, not authority.

## Minimal Definition language

The candidate contains exactly:

```json
{
  "schema_version": "broker_reports_gate5_full_declaration_definition_v0",
  "definition_id": "stable-id",
  "definition_version": "exact-version",
  "declaration_identity": {},
  "official_evidence_binding": {},
  "domains": [
    {
      "domain_id": "stable-id",
      "semantic_meaning": "target-independent meaning",
      "applicability_mode": "always|conditional",
      "evidence_policy": "closed-policy-id",
      "expected_component": {
        "family": "stable-family-id",
        "availability": "missing|published_bounded|published_exact",
        "contract_ids": []
      },
      "allowed_authority_classes": [],
      "official_evidence_refs": []
    }
  ]
}
```

There is no status, gap narrative, target mapping, expression or workflow in
the candidate. Publication status and review findings are separate
repository-owned records.

## Closed applicability policies

Exactly one policy belongs to each root domain:

| Policy | Meaning |
| --- | --- |
| `definition_mandatory` | the Definition makes the domain applicable; negative evidence is forbidden |
| `factual_occurrence` | facts or a validated component prove occurrence; exact negative attestation/coverage is allowed only when explicitly allowlisted and unconflicted |
| `typed_legal_classification` | an exact reviewed typed classifier owns the legal decision; declarant denial is forbidden as decision authority |
| `elective_claim` | an authenticated filing election opens scope and non-election may close it; eligibility/value stays in the typed component |
| `exhaustive_coverage` | only exact period/domain coverage proves absence; declarant denial alone is forbidden |

`always` accepts only `definition_mandatory` and
`trusted_declaration_definition`. `conditional` cannot use
`definition_mandatory`.

## Typed component expectation

`contract_ids` can contain only exact current inventory members. All current
members are explicitly `bounded_partial_only`, so they can be cited only with
`published_bounded`. `published_exact` requires a separately proven exact-root
contract. An unknown or absent contract is represented as `missing` with an
empty list; `Any`, invented contracts and free-form schemas are invalid.

The current inventory reuses:

- `broker_reports_gate5_securities_disposal_tax_model_v0`;
- `broker_reports_gate5_securities_disposal_operation_tax_model_v0`;
- `broker_reports_gate5_tax_period_category_tax_model_v0`;
- `broker_reports_gate5_income_group_tax_base_model_v0`.

## Official evidence binding

The frozen package binds the RU 3-NDFL declaration for tax period 2025 to
exact official FNS attachment bytes:

| Source | SHA-256 |
| --- | --- |
| form PDF | `d751043f63af1f0095a14228a65a3831acf47fcd82c397e2eb38b0f9f8dc9565` |
| filling procedure DOCX | `7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc` |
| electronic format DOCX | `f5215c237a8af73dd7a251cee94a2e09aacd8540173fcde2904b4c311129e3c2` |
| XSD 5.20.01 | `083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484` |

The whole evidence package hash is:

```text
af3b42a5cf9e543275e6913b7e8645d3d4548efa786f9136cecd0f9a1039c62d
```

Target locators exist only inside official evidence. Candidate domain IDs and
meanings reject XML/XSD/PDF/layout terms.

## Deterministic validation

Validation fails closed on:

- identity or evidence-package mismatch;
- duplicate Definition/domain identities or meanings;
- any of the 14 official surfaces without a semantic owner;
- `always`/conditional policy mismatch;
- attestation in `typed_legal_classification` or `exhaustive_coverage`;
- unknown or overclaimed component contracts;
- target-layout language or executable keys/logic;
- malformed, non-object, multiple or non-finite JSON output.

Passing validation returns `eligible_for_review`, never `trusted`.

## G5.28 clean trial

The one actual inference used:

```text
codex-cli 0.147.0-alpha.6.5
model gpt-5.6-sol
reasoning high
ephemeral session
empty temporary working directory
read-only sandbox
ignored user config and repository rules
0 history messages
0 provider retries
0 follow-ups
0 repairs
```

Frozen payload:

```text
21,536 UTF-8 bytes
e37001463b156034bee6c0843d30f9068b66d1dbdda96dd8265159bd81d5cf90
```

Exact candidate:

```text
7,472 UTF-8 bytes
3a5cf39a0a70b308c72e8f8688c6785618746a4634d2c41360d6ee5f871db639
```

Two disclosed local launch mistakes ended before any input/model inference;
the successful process is the only provider inference. No candidate byte was
changed after capture.

## Review result

Closed validation reports 12 unique domains, 14/14 official surface IDs,
closed policies, honest component gaps and no target/runtime language.

Semantic review nevertheless rejects trusted publication. Official procedure
paragraph 18 says that Appendix 3 both covers entrepreneurial/advocate/private
practice income and calculates professional deductions under paragraphs 2 and
3 of Tax Code article 221. The latter includes civil-contract and author/creator
deduction semantics. The candidate's
`independent_professional_activity_income` narrows all professional deductions
to entrepreneurial/advocate/notarial/private-practice activity and assigns one
`typed_legal_classification` policy. It therefore does not account for the
separate elective-claim applicability meaning.

The localized authoring-language defect is not a missing runtime primitive. It
is insufficient semantic atomization of one official surface plus a validator
that checks surface-reference coverage but not coverage of multiple semantic
obligations inside one surface.

## Publication boundary

```text
exact model candidate
    -> deterministic validation: eligible_for_review
    -> semantic review: review_rejected
    -> trusted authority factory: FAIL CLOSED
```

This proves the cheap repository-versioned boundary without publishing the
candidate. G5.29 must not consume it.

## Scope stops

G5.28 does not add or change:

- a provider/model client;
- any of the five runtime primitive families;
- a case-time scope resolver or human questionnaire;
- missing domain Tax Models or filing context;
- declaration package/model/assembly;
- tax payable, full PROJECT, XML or PDF;
- DB, service, registry, GUI or product activation.

## Next boundary

`G5.29` is not allowed. The first blocker is an authoring-only evidence/validator
revision that represents multiple independent semantic obligations within one
official surface without supplying an expected domain partition, followed by a
new independent no-repair trial. That revision is not implemented in G5.28.
