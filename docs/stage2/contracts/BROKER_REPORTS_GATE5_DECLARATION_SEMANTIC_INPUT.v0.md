# Broker Reports Gate 5 Declaration Semantic Input v0

Status: `CURRENT SUPPORTING CONTRACT`

Implementation status: `INACTIVE G5.33 SYNTHETIC PROOF`

G5.33 verdict: `PROVEN`

Boundary verdict: `H2_MINIMAL_SEMANTIC_VIEW`

Terminal status: `DECLARATION_SEMANTIC_INPUT_READY`

This contract defines the minimum target-independent semantic boundary between
the G5.32 sealed complete Resolved Declaration Package and a future
target-specific PROJECT. It does not authorize PROJECT, XML/XSD, PDF/form
generation, filing or product activation.

## Boundary decision

The existing complete Package remains the sole audit and completeness
authority, but its direct DTO is not the PROJECT consumer contract.

`H1 PACKAGE_IS_MODEL` was rejected for the direct consumer surface because the
Package deliberately mixes declaration semantics with:

- Definition and scope receipt snapshots;
- component owner, coverage and binding mechanics;
- requirement-resolution diagnostics and manifests;
- target-adjacent Definition metadata such as `electronic_format_version`,
  `knd` and authority-order identity.

Requiring every target projector to parse or ignore those fields would leak
Gate 5/package mechanics into PROJECT.

`H3 SEPARATE_DECLARATION_MODEL_REQUIRED` was rejected because no semantic value
is missing. The sealed Package already contains stable typed exact-root
components, explicit terminal conditional meanings, case/period identity and
the supplied-case completeness receipt. A new tax-semantic owner or flattened
DTO would duplicate established contracts.

Therefore G5.33 selects `H2_MINIMAL_SEMANTIC_VIEW`: a deterministic sealed view
that projects only already-resolved target-independent result fields from exact
native components and keeps their hashes as audit links.

## Canonical route

The only construction route is:

```text
Gate5DeclarationSemanticInputRuntimeFactory.create
  -> Gate5ResolvedDeclarationPackageRuntimeFactory.create_validation_only
  -> validate sealed complete Package
  -> project semantic result fields from existing exact-root components
  -> emit and self-validate semantic input
```

The compiler has no store, context, document or provider parameter. It does
not call Gate 4, SQL, ArtifactStore, methodology execution, an LLM or a tax
calculation owner.

## Semantic consumer surface

The consumer receives one content-addressed
`broker_reports_gate5_declaration_semantic_input_v0` object:

```text
schema_version
status = DECLARATION_SEMANTIC_INPUT_READY

source_binding
  package_sha256
  definition_sha256
  scope_receipt_sha256
  component_set_sha256
  resolution_manifest_sha256

declaration_semantics
  definition_id
  definition_version
  jurisdiction
  declaration_kind
  tax_period

case_identity
  scope_ref
  taxpayer_scope_ref
  tax_period
  case_id
  scope_binding_sha256

completeness
  completeness_kind = supplied_case_evidence_set
  real_world_taxpayer_completeness_asserted = false

domains[]
  domain_id
  semantic_meaning
  obligation_refs[]
  state
  typed_components[]

semantic_input_sha256
```

Each resolved semantic component retains only:

```text
source_component_contract_id
source_component_sha256
semantic_payload
semantic_payload_sha256
```

The payload preserves already typed semantic result structures such as tagged
money, filing/taxpayer/signer objects, income-group results, source entries,
budget disposition and financial category results. It does not carry native
`input_snapshot`, methodology, derivation, provenance or nested dependency
components. Those fields, bounded intermediate components and package
owner/binding/diagnostic mechanics remain on the Package audit surface.

G5.34 target pressure corrected an ordinary selection loss inside this same
boundary. The view now also retains the already-owned declaration date and tax
authority code, exact taxpayer and source-party identity meanings, budget
KBK/OKTMO and simplified-procedure amount, non-taxable income and tax
deductions, and domestic/foreign source obligation outcomes. This is not a new
Declaration Definition or Form DTO: the values remain nested in their existing
target-independent component meanings and still exclude target locators.

The compiler does not flatten these results into form fields. It performs five
closed result selections for the five currently resolved component families.
If another Definition domain becomes `RESOLVED` without an explicit semantic
result selection, construction fails with
`gate5_declaration_semantic_component_projection_unavailable`.

## Definition completeness accounting

Construction iterates the already validated Definition domain order and the
Package requirement-resolution order together. It fails closed unless every
row has the same domain identity and one terminal state:

```text
RESOLVED
NOT_APPLICABLE
NOT_ACTIVATED_FOR_SUPPLIED_CASE
```

A `RESOLVED` Package row must contain at least one validated exact-root native
component. Its view row must expose the resulting semantic payload plus the
source component contract/hash link. A non-resolved terminal row must expose
no component. The domain row preserves the complete ordered Definition
obligation list, so all active and inactive meanings remain accounted without
a new ontology.

## No-new-knowledge invariant

The compiler may:

- validate the sealed Package through its existing owner;
- copy Definition semantic labels and terminal Package states;
- select components already marked and validated as `exact_root_domain`;
- copy only named result fields and preserve source component hashes;
- project a small set of case/completeness/source bindings;
- compute the semantic-input content hash.

It may not:

- calculate a base, rate, tax, deduction or declaration outcome;
- decide applicability or select a Tax Model;
- choose a source, claim, taxpayer, signer or component meaning;
- promote a bounded component;
- infer absence from missing evidence;
- alter the trusted Definition or supplied-case completeness semantics.

Any need for those operations is an upstream blocker, not PROJECT work.

## Target independence

The semantic surface contains no XML element/attribute, PDF field, form
section/appendix/line, KND locator or electronic-format version. It retains
`declaration_kind = 3-NDFL` as the semantic declaration kind, but target layout
and serialization identities belong to a future exact Projection Definition.

Both a future XML projector and a future PDF/form projector receive the same:

```text
complete semantic input + one exact trusted target Projection Definition
```

Their allowed operation is mapping only. They may not perform tax reasoning,
case discovery, completeness checks or semantic reconstruction.

## Sealing and replay

The emitted view is content-addressed by canonical JSON SHA-256. Standalone
validation checks its exact shape, terminal state accounting, supplied-case
completeness disclaimer, source/semantic payload hashes, target-specific key
exclusion and outer content hash.

Compilation additionally binds the view to the validated sealed Package and
its Definition, scope, component-set and resolution-manifest hashes. No
upstream business-value read is needed for either compilation or
validation-only replay.

## Scope stop

G5.33 stops at `DECLARATION_SEMANTIC_INPUT_READY`. It does not implement a
Projection Definition, XML serializer/tree, XSD validation, PDF filler,
filing, persistence, GUI, deployment or product path.

The next allowed boundary is a separately authorized `FULL-TARGET PROJECT`
GOAL that consumes this semantic input plus one exact trusted target Projection
Definition and proves deterministic mapping only.
