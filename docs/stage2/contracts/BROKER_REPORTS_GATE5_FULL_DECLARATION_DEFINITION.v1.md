# Broker Reports Gate 5 Full Declaration Definition Authoring v1

Status: `CURRENT SUPPORTING CONTRACT`

Implementation status: `INACTIVE G5.28B OBLIGATION-BACKED AUTHORING PROOF`

G5.28B verdict: `PROVEN`

Trusted publication status: `TRUSTED_REPOSITORY_PUBLISHED`

This contract owns the smallest tested authoring and repository-publication
boundary for one full root Declaration Definition. It does not own case-time
scope resolution, a questionnaire, tax calculation, Declaration Model,
PROJECT, XML or PDF.

The previous [v0](./BROKER_REPORTS_GATE5_FULL_DECLARATION_DEFINITION.v0.md)
remains exact G5.28 rejected-candidate history and is not current publication
authority.

## Sole owners

```text
Gate5FullDeclarationDefinitionAuthoringFactory.create
Gate5FullDeclarationDefinitionCandidateFactory.create
Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create
```

The first factory owns the frozen model payload and deterministic validator.
The second exposes exact untrusted model evidence. The third is the only
trusted publication gate. No DB, registry service, alternate reader or
provider path exists.

## Frozen reviewed obligation authority

The package resource is:

```text
gate5_full_declaration_obligations.ru_3ndfl_2025.v1.json
SHA-256 8065a2047b2d7bf5a1a3b87ed4dd49f65bd39e97b6a42c1acf24d2d62548b23c
25 reviewed obligations
14 official semantic surfaces
4 exact official sources
```

Each obligation contains only:

```text
obligation_id
semantic_requirement
applicability_policy_id
official_evidence_refs
```

The package is authoring evidence, not a runtime Tax Model, ontology, graph or
rules language. All four official source bytes were fetched and matched again
on `2026-08-10`:

| Official FNS source | SHA-256 |
| --- | --- |
| [form PDF](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_1.pdf) | `d751043f63af1f0095a14228a65a3831acf47fcd82c397e2eb38b0f9f8dc9565` |
| [filling procedure DOCX](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_2.docx) | `7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc` |
| [electronic format DOCX](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_3.docx) | `f5215c237a8af73dd7a251cee94a2e09aacd8540173fcde2904b4c311129e3c2` |
| [XSD 5.20.01](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/xsd/NO_NDFL3_1_033_00_05_20_01.xsd) | `083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484` |

## Minimal Definition language

The model returns exactly:

```json
{
  "schema_version": "broker_reports_gate5_full_declaration_definition_v1",
  "definition_id": "stable-id",
  "definition_version": "exact-version",
  "declaration_identity": {},
  "obligation_package_binding": {},
  "domains": [
    {
      "domain_id": "stable-id",
      "semantic_meaning": "target-independent meaning",
      "obligation_refs": [],
      "expected_component": {
        "family": "stable-family-id",
        "availability": "missing|published_bounded|published_exact",
        "contract_ids": []
      }
    }
  ]
}
```

Policy, applicability mode, authority classes and official evidence refs are
not repeated by the model. The validator derives them from the exact
obligation refs. The validator does not contain an expected domain count,
domain ID list or partition.

## Deterministic invariants

Validation fails closed on:

- missing, duplicated, unknown or empty obligation refs;
- more than one closed policy inside a domain;
- duplicate domain IDs, meanings or component families;
- an unknown component contract or a contract outside the domain obligation
  scope;
- promotion of a `bounded_partial_only` contract to `published_exact`;
- target-layout identity or executable keys and logic;
- identity or obligation-package hash mismatch;
- malformed, multiple, non-object or non-finite JSON.

All 25 obligations must be present exactly once. The closed policy determines
the applicability mode and authority allowlist. Current component contracts
are the four existing bounded contracts; the runtime capability basis is
unchanged.

## Aggregate review rule

A root aggregate is valid when any relevant member can make the domain
applicable and one component family retains the member variants separately.
Independent optional inner values do not force separate root domains.

Publication review is limited to:

1. one honest applicability decision for the domain;
2. one coherent aggregate-aware typed component family;
3. completeness of the reviewed obligation package.

It does not invent an ontology, answer key or runtime rule engine.

## One clean authoring trial

```text
client                 codex-cli 0.147.0-alpha.6.5
model                  gpt-5.6-sol
reasoning              high
session                ephemeral, no history
working directory      new empty temporary directory
sandbox                read-only
user config/rules      ignored
semantic inferences    1
retry/follow-up/repair 0/0/0
reported tokens        7,667
duration               56.029 seconds
```

Frozen payload:

```text
17,576 UTF-8 bytes
5a51aa10b3aa5e880254722f79543fefe234c189969b25d2deae8291e30bc541
```

Exact unedited candidate:

```text
5,391 UTF-8 bytes
8d2a4ad11c766a5d346f4840b033d08e6c854fe07e336836541f9437ea8bf19d
11 model-authored domains
```

Deterministic validation accounts for `25/25` obligations exactly once and
passes policy, component and target-independence checks.

## Trusted publication

The bounded review passes all four recorded checks, including aggregate
variant retention. The immutable candidate bytes are therefore the published
Definition artifact. The separate review receipt is hash-pinned:

```text
candidate SHA-256  8d2a4ad11c766a5d346f4840b033d08e6c854fe07e336836541f9437ea8bf19d
validation SHA-256 f3e4993ac54f154be53cb5d21a4ffaed0713cf49b3025b10d4e9b8b9c1bf79f6
review SHA-256     731ae53ed77046cfd89b2aac8e53f5416c51cdb732709327a7702c2c28de1619
```

The trusted authority resolves only this tuple:

```text
definition_id      ru_3ndfl_2025_root_declaration
definition_version 2026-08-10.1
definition_sha256  8d2a4ad11c766a5d346f4840b033d08e6c854fe07e336836541f9437ea8bf19d
```

Any ID, version, hash, validation receipt or package mismatch fails closed.
Candidate evidence alone remains non-authoritative.

## Scope stops

G5.28B does not add or change:

- provider/model integration or the five runtime primitive families;
- Scope Resolver, case-time applicability or human ACQUIRE flow;
- missing typed components or Tax Models;
- taxpayer/filing context, tax settlement or Declaration Model;
- PROJECT, XML/PDF, DB, service, GUI or product activation.

## Next boundary and first blocker

`G5.29` is implemented by the separate
[Declaration Scope Resolution v0](./BROKER_REPORTS_GATE5_DECLARATION_SCOPE_RESOLUTION.v0.md)
boundary. It remains outside this G5.28B authoring/publication owner.

The first real prerequisite for a bounded G5.29 receipt is a trusted
case/period filing-context binding for `filing_and_party_identity`: declaration
instance, taxpayer/period status, signer and representation authority. The
published Definition honestly marks that component family `missing`; the
existing Financial Case is not authority for those filing identities. The
bounded G5.29 receipt returns this as its first downstream component blocker.
G5.28B does not implement the missing filing context.

“First” above is local to the bounded G5.29 filing/context consumer. It is not
a dependency-order claim for Gate 4 or independent Gate 5 financial
calculation; signer and filing-instance facts become mandatory only for their
named declaration/release consumers.
