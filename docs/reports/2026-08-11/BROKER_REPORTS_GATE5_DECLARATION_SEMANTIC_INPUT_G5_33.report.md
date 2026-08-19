# Broker Reports Gate 5 G5.33 Declaration Semantic Input Boundary Proof

Date: `2026-08-11`

Status: `PROVEN`

Boundary verdict: `H2_MINIMAL_SEMANTIC_VIEW`

Terminal result: `DECLARATION_SEMANTIC_INPUT_READY`

Scope: inactive bounded synthetic proof only. No full PROJECT, Projection
Definition, XML/XSD/PDF generation, filing, persistence, deployment, product
activation, commit, push or PR is authorized or performed.

## Verdict

The complete G5.32 Resolved Declaration Package contains all required tax and
case semantics, so a separate Declaration Model authority is unnecessary.
However, its direct DTO is not the minimal PROJECT input: it mixes semantic
results with receipt mechanics, component bindings/owners, diagnostics,
methodology/provenance and target-adjacent Definition metadata.

G5.33 therefore selects `H2_MINIMAL_SEMANTIC_VIEW`. One deterministic compiler
validates only the sealed Package, projects already-resolved result fields from
five exact-root components, preserves six explicit non-activation meanings and
emits a content-addressed target-independent input. It performs no tax
reasoning or upstream lookup.

The governing contract is
[Declaration Semantic Input v0](../../stage2/contracts/BROKER_REPORTS_GATE5_DECLARATION_SEMANTIC_INPUT.v0.md).

## Boundary audit

| PROJECT requirement | Complete Package evidence | Direct consumer verdict |
| --- | --- | --- |
| semantic value exists | five exact-root typed component snapshots | yes |
| semantic meaning is unambiguous | Definition domain meaning, ordered obligations and component contracts are sealed | yes |
| stable typed contract exists | native component schema/version/hash is preserved | yes |
| no external lookup is needed | Package validation-only replay uses no store or Gate 4 | yes |
| zero/absence/not-activated/not-applicable remain distinct | tagged money plus explicit terminal resolution states | yes |
| case/period identity survives | exact scope/case/taxpayer/period binding is sealed | yes |
| same semantics can serve XML and PDF | values are target-neutral, but the direct DTO also carries receipts, diagnostics and `electronic_format_version`/`knd`/order metadata | semantic content yes; direct DTO no |

The last row and the package-mechanics burden reject H1 as a direct PROJECT
contract. No missing semantic value was found, so H3 has no justification.

## Minimal semantic contract

`Gate5DeclarationSemanticInputRuntimeFactory.create` is the sole construction
route. It delegates sealed input validation to
`Gate5ResolvedDeclarationPackageRuntimeFactory.create_validation_only` and
emits only:

```text
source Package/Definition/scope/component-set/resolution hashes
declaration kind, jurisdiction and period
case/taxpayer scope identity
supplied-case completeness disclaimer
11 Definition domain rows
  semantic meaning
  ordered obligation refs
  terminal state
  zero or more semantic result payloads
semantic input SHA-256
```

Each resolved payload keeps the source component contract/hash link and its own
semantic payload hash. The payloads preserve:

- filing instance, taxpayer and signer semantics;
- declaration-level budget disposition;
- income-group totals, expenses, base, rate, settlement and payable/refundable
  outcomes;
- taxable income source semantics;
- financial category results and obligation states.

They omit native `input_snapshot`, methodology bindings, derivations,
provenance, nested dependency components, receipt mechanics and target
locators. Tagged money and other useful nested semantic types remain intact;
there is no giant flattened Form DTO.

## Closure and no-new-knowledge proof

For the representative complete supplied case:

```text
Definition domains                         11 / 11 accounted
Definition obligations                     25 / 25 accounted
RESOLVED domains                            5
NOT_ACTIVATED_FOR_SUPPLIED_CASE domains     6
semantic result payloads                    5
machine blockers                            0
```

Construction iterates the already validated Definition and resolution rows in
the same order. A resolved row must have an exact-root Package component and a
closed semantic result selector. A non-resolved terminal row carries no
component. An unknown newly resolved domain fails with an exact
`component_projection_unavailable` blocker instead of being guessed or hidden
inside PROJECT.

The compiler copies fields and computes hashes. It does not calculate tax,
choose a rate/source/claim/component, decide applicability, select a Tax Model,
promote bounded coverage or infer real-world absence.

## Semantic and audit surface separation

One observed fresh bound fixture measured:

```text
sealed Package canonical bytes       148959
semantic input canonical bytes        10186
semantic input / Package                6.84%
```

This reduction is not a compression trick: it is removal of audit mechanics
and nested input history from the consumer surface. Auditability remains via
Package, Definition, scope, component-set, resolution-manifest and individual
source-component SHA-256 links.

Observed hash chain for that fresh proof fixture:

```text
Definition       8d2a4ad11c766a5d346f4840b033d08e6c854fe07e336836541f9437ea8bf19d
Package          45e5e6f13f8413005bdcaabac3e5b089652a77dba6987dc82a8eac709da6d9c1
Semantic input   6148c58fcf8bfc85a8436e666f34f887435344477886d337da09b17bf3fd5c0d
```

A fresh synthetic fixture can have different upstream artifact identities and
therefore different Package/view hashes. Compiling the same sealed Package is
byte-equal and produces the same semantic-input hash.

## Supplied-case completeness preservation

The consumer boundary carries exactly:

```text
completeness_kind = supplied_case_evidence_set
real_world_taxpayer_completeness_asserted = false
```

It does not upgrade G5.32 into a claim about every real-world taxpayer event,
election, source or document.

## Projection-readiness and second-target pressure

The disposable consumer probe reads, without backward lookup:

```text
taxpayer period status
one income-group tax base and payable result
declaration-level budget disposition
one supplied financial result
one NOT_ACTIVATED_FOR_SUPPLIED_CASE conditional state
```

Two cheap pressure consumers labelled XML and PDF read the same semantic input
and return identical representative semantic values. Neither uses Gate 4,
ArtifactStore, documents, methodology execution, component owners or tax
calculation. No XML tree, PDF field map or target serializer was implemented.

Target-specific keys such as XML element/attribute, PDF field, form
section/appendix/line, KND locator and electronic-format version are absent and
fail closed if injected and rehashed.

## Validation and anti-drift evidence

```text
Focused semantic/package/financial suite       21 passed
All tests selected by -k gate5                 223 passed
Gate 5 + architecture + bundle suite           298 passed, 1 skipped
Architecture focused audit                     14 passed, 1 skipped
Ruff / py_compile                              passed
Same sealed Package compilation                byte-equal
Standalone semantic-input validation           equal
Tampered semantic payload/hash                 rejected
Rehashed target locator injection              rejected
Machine blockers                               0
```

The skip is the pre-existing optional Windows symlink capability check. Six
dependency/deprecation warnings are non-assertion output.

One preceding unchanged-command combined attempt reached the outer 124-second
runner limit without an assertion summary. It was treated as unverified, not as
a test failure or success. The unchanged-code replay with a 240-second limit
completed with the terminal `298 passed, 1 skipped` result above.

The product-bundle build was replayed after the change. All three artifacts
remain byte-identical to baseline and contain neither the new module nor its
terminal status:

```text
gate1 pipe          a0f919c4957cf64c21603e1e9599b171ee3472cfc8076a480c904926d2b64fcd
gate2 source        3ab3d64fa0598167e3c15a00b203fbf8587399f9d767eeee593875487ec0c616
gate2 domain        29cd51c8568ebcaaebc3c597f1741fc62795bdd5fb28613edae1f8c3df2e4add
```

## Anti-drift and KISS review

- One G5.32 Package remains the audit/completeness authority.
- One additive factory owns the semantic consumer view.
- Five direct result selections cover the five currently resolved domains;
  there is no plugin system, generic graph, registry or rules engine.
- No new tax owner, Tax Model, calculation, DB/table or external lookup exists.
- No complete native snapshot or provenance graph leaks into the consumer
  surface.
- No form DTO, target locator, Projection Definition, XML/PDF implementation or
  product route was added.
- Tests assert terminal values, completeness accounting, consumer behavior and
  fail-closed tamper rather than snapshot-only approval.

The architecture guardrails changed the implementation materially: the first
whole-component view was rejected during the loop because it still exposed
audit history. The final view keeps only semantic results and hash links.

## Final result and scope stop

Final result: `DECLARATION_SEMANTIC_INPUT_READY`.

This proves that the next stage can be mapping-only when it receives this
sealed semantic input plus one exact trusted target Projection Definition. It
does not prove a target definition, full 3-NDFL document, XSD/PDF validity,
filing readiness or product activation.

The next allowed boundary is a separately authorized `FULL-TARGET PROJECT`
GOAL. G5.33 stops here.
