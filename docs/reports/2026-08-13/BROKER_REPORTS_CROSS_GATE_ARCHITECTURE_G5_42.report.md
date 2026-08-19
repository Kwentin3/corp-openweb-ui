# Broker Reports Cross-Gate Architecture G5.42

Date: 2026-08-13

Scope: Gate 1 through Gate 5, runtime composition, LLM boundaries, source and
financial facts, relations, metadata, declaration scope, human closure and
projection. The checkout already contained the in-progress G5.40D-G5.41 work;
G5.42 preserved that work and refactored only overlapping architecture debt.

## Terminal

```text
CROSS_GATE_CORE_ARCHITECTURE_PROVEN
TECHNICAL_DEBT_REFRACTORED
DOMAIN_OWNERSHIP_EXPLICIT
COMPATIBILITY_DEBT_REMAINS=[gate2_candidate_relation_compatibility,published_income_source_and_residency_methodology]
```

`CROSS_GATE_CONTRACT_ARCHITECTURE_PROVEN` is not claimed. The active core has
one explicit owner per meaning and passed bounded regression, but two named
boundaries remain: a default-off Gate 2 relation compatibility surface and no
published exact legal methodology for real income-source/residency/allowability
classification.

## Ownership map

The normative one-way map is published in
[Cross-Gate Domain Ownership v1](../../stage2/contracts/BROKER_REPORTS_CROSS_GATE_DOMAIN_OWNERSHIP.v1.md).
Pipeline Gates v1 remains the sole gate-number/status authority; the new map is
a supporting ownership/call-direction contract.

The current direction is:

```text
source -> canonical -> financial/metadata labels -> normalized source facts
       -> deterministic methodology/Tax Models -> declaration semantics
       -> representation-only projection
```

Human or external evidence re-enters through a typed owner and cannot bypass
normalization, methodology or validation.

## Debt matrix

| Finding | Before | Decision and change | Evidence after |
| --- | --- | --- | --- |
| gate placement authority drift | machine policy named the superseded global blueprint and placed financial interpretation in Gate 2 | policy v3 points to Pipeline Gates v1; the old blueprint is narrow visual-table history; exact Gate 1-5/projection ownership is machine-readable | architecture and semantic visual authority tests |
| mixed Gate 3/Gate 4 intake | `gate3_tax_case_evidence_intake` mixed canonical metadata extraction, Gate 4 financial counts and a tax-case name | split into strict `gate3_metadata_source_facts.py` and compositional `gate5_evidence_intake.py`; the mixed module was removed | boundary imports and strict-label negative tests |
| unsupported metadata inference | unlabelled broker-name and generic INN text could become broker facts | only explicitly labelled broker/name/tax-ID text is admitted; source provenance is retained; no tax meaning assigned | metadata negative tests and cross-gate import guard |
| duplicate declaration scope owner | final scope resolution and G5.41 activation lived in separate modules | activation moved into `gate5_declaration_scope_resolution.py`; both factories now expose one scope decision domain | old module absent, one-owner architecture test, 21 focused passes |
| copied declaration domain IDs | activation copied Definition domain IDs into Python control flow | activation selects versioned obligation refs, then resolves domains from the trusted Full Definition | existing no-copied-domain-authority test passes |
| user-authored tax conclusion | `income_source_classification` was accepted as a user case fact | removed from factual keys; source/residency/allowability gaps require documents and published methodology; document answers return to Gate 1-4 normalization | human-gap negative assertions and G5.41 suite |
| unconstrained budget disposition answer | arbitrary text could enter a filing election fact | narrowed to the existing enumerated payment/additional-payment/reduction/refund codes | typed answer validation tests |
| generated bundle not closed-world after scope merge | scope imported real case assembly that was absent from bundle module order | added transitive owner before scope in the builder and regenerated all three bundles | isolated bundle import/order assertions and 125 Gate 1 passes |
| duplicated frozen bundle hashes in two Gate 5 tests | unrelated XML tests asserted one historical Gate 1 SHA and failed every legitimate rebuild | removed duplicate historical pins; dedicated bundle owner now asserts module presence/order and closed-world execution | Gate 5 422 passes and bundle/release 60 passes |
| stale atomic-release policy pin | release test expected architecture policy v2 | updated the release contract expectation to current v3; runtime manifest already consumed the sole source constant | atomic/bundle/architecture 60 passes |

## LLM call-point audit

The complete classification is in Cross-Gate Domain Ownership v1. Maintained
calls are limited to externally variable document/language boundaries:

- Gate 1 Document Passport and visual page/table proposals;
- Gate 2 source/financial semantic proposal paths through the canonical request,
  provider-adapter, validator and materializer owners;
- Gate 3 bounded label and role proposals through published Dictionary/Role Pack
  validators;
- one inactive Gate 5 single-money-input human language adapter.

Shadow/qualification/experiment calls remain classified as research evidence.
Gate 4, deterministic Gate 5 calculations, declaration scope/preparation,
semantic-input and projection contain no structured-model call sites. A new
architecture test freezes the exact gate-file call-site inventory.

LLM authority remains zero for arithmetic, persistence, relation construction,
scope, final classification and target projection.

## Contract-authority audit

The authority order is now explicit:

1. Pipeline Gates v1 owns placement and status;
2. versioned contracts/resources own DTO semantics;
3. maintained factories own construction and execution;
4. compatibility adapters validate and delegate only;
5. generated bundles project maintained source;
6. dated reports and research are evidence only.

The Full Declaration Definition is the sole domain/obligation catalog. Scope
resolution is the sole supplied-case scope decision domain. Trusted methodology
owns tax calculation/classification. Projection definitions own representation
only. The Architecture Authorities index now routes to the G5.42 map.

## Relations and reconciliation

No Gate 4 or Gate 5 financial-event relation owner exists. The former related
securities runtime remains removed. No Gate 4/Gate 5 module imports candidate
relation sets, selected relation IDs, transaction graphs or the compatibility
Gate 3 context manifest.

Detail and aggregate observations stay independent. Disagreement does not
trigger reconciliation. Purchase/disposal/commission/withholding identity is
not inferred by proximity, equal literals, FIFO, allocation or model
navigation. Insufficient exact methodology inputs remain an insufficiency
terminal.

## Research scars

| Scar | Classification | Consumer/risk | Removal condition |
| --- | --- | --- | --- |
| Gate 2 candidate relation sets and `gate3_context_manifest` | compatibility, default off | retained artifacts/tests; naming can be mistaken for event authority | prove no retained artifacts/callers, migrate readers, then remove under a separate goal |
| V5/V6, successor, checksum and provider experiment runners | research/qualification evidence | reproducibility surface and stale names, but no new authority | an explicit evidence-retention/migration decision |
| pre-renumbering `gate2_*` financial names | compatibility naming | bundle/import migration risk | versioned consumer and bundle migration |
| rejected Gate 5 event-relation experiments | historical evidence only | no runtime consumer | retain as dated evidence; never re-enable without new proof |

## Remaining external methodology boundary

The repository does not contain an officially reviewed exact methodology that
can classify real broker income as Russian/foreign source, establish taxpayer
residency or decide the related allowability questions for the supplied case.
G5.42 does not invent one and no user statement is accepted as that legal
conclusion.

Removal path:

1. obtain/review the applicable official legal authority;
2. publish a versioned exact methodology through the existing trusted authority
   factory and hash-pinned review path;
3. add deterministic positive/negative/insufficient fixtures;
4. bind declaration demands to its typed output;
5. rerun the same cross-gate suite before any product activation.

## Regression evidence

All reported pass counts are pytest terminal outcomes on the final relevant
checkout. Timeouts are not counted as passes.

| Slice | Result |
| --- | --- |
| focused architecture/source-fact/G5.41 after bundle rebuild | `64 passed` |
| Gate 1 complete prefix suite | `125 passed` |
| Gate 2 complete fixed 81-file set, executed as non-overlapping terminal shards after runner limits | `982 passed` (`340 + 242 + 59 + 47 + 108 + 186`) |
| Gate 3 complete prefix suite | `120 passed` |
| Gate 4 complete prefix suite | `30 passed` |
| Gate 5 complete prefix suite after debt fixes | `422 passed` |
| final atomic-release/bundle/architecture slice | `60 passed`, five unrelated SWIG deprecation warnings |
| managed financial assets | `--check` passed |
| Python build/import syntax | `compileall` passed |
| patch whitespace | `git diff --check` passed; Windows CRLF conversion warnings only |
| safe contract scan | no secret-like matches |

One monolithic `pytest -q` run reached the orchestration limit after 904 seconds
without a pytest terminal. A monolithic Gate 2 run likewise reached 604 seconds.
Neither is treated as pass or assertion failure. The exact Gate 2 file set was
then partitioned into non-overlapping shards; every file reached a terminal pass.

## Bundle evidence

| Artifact | SHA-256 |
| --- | --- |
| Gate 1 product bundle | `e088ebe88b062d6c554984ed906768881192a45b1b7a7229f458b9f56885a705` |
| Gate 2 source-fact bundle | `4bf54deb3493648023166059bd0ce6a812530253276bc34d749186337087ff6d` |
| Gate 2 domain bundle | `4a90751e798af28137917dbc231d2f6c7876213ae08d48f60ce4b235905e8d69` |

No third-party dependency, environment variable, DB schema, external service,
product valve or deployment state was added by G5.42. No commit, push, PR or
product activation was performed.

## KISS check

G5.42 added one small metadata adapter, one contract-composition intake and one
architecture test/contract. It removed a mixed-domain module, a duplicate scope
module and duplicate frozen-hash tests. It did not add a TaxCase database,
relation/reconciliation/risk/workflow engine, universal questionnaire, generic
metadata ontology, new provider layer, new persistence platform or target
format.

## GitHub journal

The safe G5.42 terminal and evidence summary is appended to
[issue #278](https://github.com/Kwentin3/corp-openweb-ui/issues/278), the existing
Broker Reports structural-evidence/relation journal. The comment explicitly
preserves the no-relation and no-product-activation boundary.

## Next allowed boundary

No product activation follows from G5.42. The next architectural closure is a
separately authorized compatibility migration for the default-off Gate 2
relation surface. The real declaration capability remains blocked until an
officially reviewed exact income-source/residency/allowability methodology is
published and deterministically bound.
