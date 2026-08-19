# Broker Reports Gate 5 G5.35 End-to-End Full-target XML Report

Date: `2026-08-11`
Goal: `G5.35`
Verdict: `PROVEN`
Terminal: `END_TO_END_FULL_TARGET_XML_VALID`
Product status: inactive synthetic proof

## Answer

Yes, for the bounded supplied case. Starting from authenticated synthetic
broker-source bytes and a separately bound set of genuine case/filing facts,
the system passes the maintained Gate 1, Gate 2, Gate 3, Gate 4 and Gate 5
owners, produces the same complete target XML through the unchanged G5.34
projector, and validates the bytes against the packaged official FNS XSD.
There are no terminal blockers and no prebuilt Gate 4, Tax Model, Scope,
Resolved Package or Declaration Semantic Input fixtures.

## Representative input and provenance boundary

The proof uses one privacy-safe synthetic CSV transaction for tax period 2025.
The broker row owns the supplied financial evidence. Filing instance,
taxpayer/signer identity, election and external-reference facts are supplied
separately through the hash-pinned synthetic case resource; they are not
invented from the broker report.

```text
case fact set       g535_supplied_broker_source_2025
case version        2026-08-11.0-proof
resource SHA-256    f02611964fee15986fbec157253607a46b18db3a8459f659ae8ecc16529b3148
case facts SHA-256  a6edcd484daab0ab80e64b644408daa96d099f646a0fbff86df0e164b72171fc
source SHA-256      6b4ff0453368df9d7ab09293b1276e49ed5f66d45cadb4bf38a3cd7407163cbb
synthetic evidence  true
real user fact      false
```

Raw source, synthetic identity values and generated XML are absent from the
safe evidence report.

## Official owner route

| Stage | Runtime route |
| --- | --- |
| Gate 1 | `Gate1Normalizer.normalize` plus `persist_gate1_result` |
| Gate 2 | canonical publication from Gate 1; read through `CanonicalReaderFactory.create` |
| Gate 3 | `Gate3ChunkBatchLabelingFactory.create` plus `Gate3FinancialAnnotationsPersistenceFactory.create` |
| Gate 4 | `Gate4FinancialCaseRuntimeFactory.create` |
| Gate 5 | existing methodology, operation, aggregation, component, scope, package and semantic-input owners |
| Target | unchanged `Gate5FullTargetXmlProjectionRuntimeFactory.create` |

The deterministic Gate 3 boundary supplies two recorded external-model
proposals. They are not FinancialAnnotations fixtures: both proposals pass the
normal Gate 3 schema, literal, role, canonical-binding and persistence checks
before Gate 4 can consume them.

## Full replay result

```text
SOURCE
→ GATE 1
→ GATE 2
→ GATE 3
→ GATE 4
→ GATE 5
→ FULL TARGET XML
→ OFFICIAL VALIDATION

END_TO_END_FULL_TARGET_XML_VALID
```

| Evidence | Result |
| --- | --- |
| blockers | `0` |
| semantic obligations | `25` |
| Projection Definition mappings | `49` |
| XML bytes | `1112` |
| semantic result SHA-256 | `2cdca67c726eaebca88bb579b0921ae6ec057d0a843c3846c09ebc0592a0cd8d` |
| XML SHA-256 | `07d2a96d89776d71877bdd1f30ce142a4c6b6f905e09d3e8bcfe238195a8ef2a` |
| mapping proof SHA-256 | `c8bc9f1b5d900881efe65783b708157231c14f5ebca1756aea8df74672ee3449` |
| Projection Definition SHA-256 | `48109cc6b3de6fd4d242346648660d99b40863310e622ab2cec44dc641ec7b26` |
| Full Declaration Definition SHA-256 | `8d2a4ad11c766a5d346f4840b033d08e6c854fe07e336836541f9437ea8bf19d` |
| official XSD SHA-256 | `083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484` |
| source-to-XSD chain terminal | `c5a2b6899d369fcf8d80587c8791258d2672c8bda4466165e447a93ebdf3639a` |

The 16-stage compact chain covers the original source, Gate 1 custody, Gate 2
canonical artifact, Gate 3 annotations, Gate 4 Financial Case, the operation,
category and income-group Tax Models, trusted Declaration components, both
Definitions, Scope Receipt, Resolved Package, Semantic Input, XML and official
XSD. The safe projection is stored beside this report.

## Critical provenance audit

Ten critical values were followed through semantic origin, trusted owner,
sealed component, semantic-input path, Definition mapping and XML target:

- declaration date, tax authority code, taxpayer INN/status and signer capacity;
- source-party INN and OKTMO;
- budget KBK, OKTMO and disposition.

The safe receipt retains only value hashes and public structural mappings. Its
full audit has no raw private values.

## Blocker-closure loop

Two ordinary integration findings were closed by replaying from the source:

1. The public G5.33 view intentionally omits a private component reference;
   provenance was bound to its public component contract/hash and semantic
   payload hash instead.
2. The existing missing-source owner emits
   `provide_missing_source_or_values`; the E2E proof preserves that exact
   acquisition contract.

No test assertion or upstream tax meaning was weakened. Each correction was
followed by a fresh source-to-XSD replay.

## Negative proofs

1. Removing a required amount from the supplied transaction reaches Gate 4 as
   `role_incomplete`, returns the existing machine acquisition request and
   emits no XML.
2. Removing mandatory `declaration_date` returns the exact
   `gate5_e2e_case_fact_missing` blocker at the trusted case-fact boundary;
   no placeholder, empty string or default is used.
3. Changing a sealed Semantic Input is rejected by G5.34, and changing a
   receipt-chain artifact hash is rejected by the independent chain validator.

## Determinism and anti-drift

Two independent full replays produce the same target-independent semantic
result hash and byte-identical XML. Storage-owned `artifact_id`,
`canonical_version_id` and `created_at` vary externally and are excluded only
from the stable comparison; each remains bound inside its run-specific
receipt.

Source inspection and executable tests confirm:

- no direct Gate 4, Tax Model or Semantic Input fixture injection;
- no manual XML or target rules in the E2E runtime;
- no SQL hidden API or case-time LLM tax authority;
- no universal questionnaire and no second pipeline implementation;
- resource loading is package-relative and works outside the repository cwd;
- product bundles remain byte-identical.

## Verification

| Check | Result |
| --- | --- |
| focused G5.35 | `7 passed` |
| G5.35 plus G5.34 | `17 passed` |
| complete Gate 5 regression | `240 passed, 2978 deselected` |
| Gate architecture | `29 passed` |
| KT1 architecture stabilization | `18 passed` |
| type-first architecture audit | `13 passed, 1 skipped` |
| Ruff on new runtime/test | passed |
| dependency consistency (`pip check`) | passed |
| repository diff check | passed; line-ending notices only |
| safe receipt/resource/hash-chain integrity | passed; `16` stages, no exact private scalar leaks |
| official XSD validation | passed |
| semantic mapping proof | passed |

The complete Gate 5 run emitted five unrelated SWIG deprecation warnings and
no assertion failures.

## Acceptance boundary

The XML schema and package are bound to the official FNS 2025 3-NDFL format
published with the [FNS order](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/)
and the corresponding [official XSD](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/xsd/NO_NDFL3_1_033_00_05_20_01.xsd).
XSD validity is structural acceptance evidence, not a legal conclusion,
filing receipt or assurance that a real taxpayer supplied every relevant fact.

The representative source is one supported synthetic CSV case. Recorded Gate
3 proposals make the proof deterministic and exercise the official validation
path, but do not prove live provider transport.

## KISS and stop

G5.35 adds one proof-only composition orchestrator, one versioned proof
resource and focused tests. It reuses all semantic and target owners and
introduces no new Declaration Model, rule engine, registry, workflow or
persistence layer.

Work stops at G5.35. PDF pressure testing and OpenWebUI/product authoring or
real-user activation remain separately authorized strategic choices. No
commit, push or pull request is part of this proof.
