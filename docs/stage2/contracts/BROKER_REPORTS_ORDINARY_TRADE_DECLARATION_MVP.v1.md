# Broker Reports ordinary-trade declaration MVP contract v1

Status: active, deliberately bounded production path.

## Boundary

`OrdinaryTradeProductionRuntimeFactory.create` is the only activation and
composition root. It may construct `OrdinaryTradeDeclarationMvpRuntime` only
when a retention policy enables the product owner set. Request-bound personal
and filing values are read only through the existing
`Gate5HumanGapClosureRuntime`; exact labelled case metadata is read only from
the current Canonical coverage; legal classifications and KBK remain pinned
methodology outputs. Without the product owner set, the established
source-fact-only production behavior remains unchanged and fail-closed.

The adapter coordinates existing owners; it does not calculate tax or assemble
XML. Fact v2, source consumption, Operation, Category, Tax Base, right-side
components, Scope, Package, semantic release, and target projection retain
their existing owners.

## Stable identities and owners

| Meaning | Owner | Consumer proof |
| --- | --- | --- |
| authenticated user and case | server-attested OpenWebUI context plus ArtifactStore ACL | upload, actions, facts and artifacts resolve under the same user/case |
| taxpayer workflow scope | `primary_taxpayer_scope_ref` owned by product composition | opaque user+case+period slot; it is neither INN nor taxpayer identity and is not caller-selectable |
| taxpayer identity | `Gate5HumanGapClosureRuntime` fact `taxpayer_identity` | current request-bound `USER_ATTESTED_CASE_FACT`; an exact Canonical value is only a candidate until confirm/change |
| current Canonical document scope and operation coverage | active Canonical pointers plus `OrdinaryTradeProjectionRuntime.current_case_coverage` | every active Canonical manifest must have exactly one current projection bound to the same document/version/root; a missing whole projection or any `RELEVANT_UNMAPPED` observation blocks XML |
| current broker facts | `Gate4OrdinaryTradeCandidateRuntimeFactory.create` | exact case-bound Fact v2 set and disposal fact ID, consumed only after Canonical coverage passes |
| human declaration choices/facts | `Gate5HumanGapClosureRuntime` | current request-bound facts with exact user, case, taxpayer, period and publication-lane binding; stale/conflicting facts are rejected by that owner |
| capacity, inspection code, signer, filing instance/date and OKTMO | `Gate5HumanGapClosureRuntime` | current user-attested facts; missing fill-only values permit draft but never XML |
| source party and exact applicability assertions | existing `Gate3MetadataSourceFactRuntime` source owner | exact labels from Canonical versions named by current coverage; ambiguity or absence is a source blocker; no LLM or financial Gate 3 execution |
| legal/methodology version, applicability, KBK and declarant category | `Gate5TrustedMethodologyAuthorityFactory.create` | repository resource identity/SHA-256 and exact pinned rules |
| Fact -> Operation -> Category -> Tax Base | existing source, Tax Model and aggregation owners | owner-produced hashes and input/member bindings |
| Scope -> Package -> release -> projection | existing declaration owners | owner replay plus exact adjacency validation |
| XML/XSD representation | `Gate5FullTargetXmlProjectionRuntimeFactory.create` | deterministic bytes, official XSD conformance, and representation-only extraction of serialized literals; no rate or tax formula |
| released semantics -> serialized XML values | `Gate5DeclarationSemanticInputRuntimeFactory.create` | exact equality between extracted numeric fields and owner-produced released values |
| active persistence | `OrdinaryTradeDeclarationMvpRuntime` through the existing ArtifactStore | private XML and MVP receipt artifacts |

Caller supplies only `ArtifactAccessContext` and canonical artifact refs to the
production root. Caller cannot supply a taxpayer ref, disposal fact ID,
methodology version, Scope, Package, released values, projection, or receipt.

## Supported case

- tax period 2025; initial declaration only; individual resident whose external
  user-attested capacity is `individual_not_ip_not_private_practice`; taxpayer signs for self;
- exactly one ordinary organized-market security purchase and one disposal,
  outside IIS, in RUB, with a positive result;
- zero or more disposal-row transaction charges already represented by current
  Fact v2 and consumed exactly once;
- no acquisition commission, derivatives, dividends, coupons, IIS, carried
  loss, foreign currency/source/tax, representative filing, or FNS transport;
- ten current request-bound Human Facts: taxpayer identity, taxpayer capacity,
  residency evidence, filing instance, declaration date, destination code,
  self-signer choice, payment disposition, OKTMO, and one explicit bounded
  zero-scope confirmation covering other
  selected-group income, non-taxable income, deductions, loss claim, credits,
  withholding and simplified return/credit;
- explicit current Canonical source assertions for source party,
  organized-market/IIS/exemption inputs and Russian-source jurisdiction;
- pinned methodology output for declarant category, applicability normalization
  and the Article 228 payment KBK.

`CORRECTION` is not converted to an invented number. Until a separate exact
owner supplies the correction number, it stops with
`ordinary_trade_declaration_correction_number_required`.

Anything outside this matrix stops with a typed blocker. Missing or malformed
identity/user/source/methodology owner output never produces XML. Partial acquisition
commission remains `LEGAL_INTERPRETATION_REQUIRED`.

## Persistence and replay

The wire XML is stored as Base64 inside private
`broker_reports_ordinary_trade_declaration_xml_v1`; its SHA-256 is over the
original official `windows-1251` bytes. The maintained OpenWebUI composition
also publishes those exact bytes through the authenticated private File owner.
The paired
`broker_reports_ordinary_trade_declaration_mvp_receipt_v1` binds taxpayer,
current Canonical coverage, current Fact v2 set, all ten exact Human Fact
artifact refs, current source metadata and product-methodology binding, active assembly receipt, projection
receipt, XML bytes, XSD status, semantic accounting and exact released-value to
serialized-value reconciliation. The coverage binding includes the complete
active Canonical document scope and exact manifest/version/root identities.

`validate_current_declaration` first asks the XML owner to validate XSD and
extract serialized values without formulas. The existing declaration-semantic
owner then compares those literals with owner-produced released values. It
finally replays all current owners. Recalculating caller hashes cannot make an
inconsistent, old or mixed result current. A Human Fact publication successor,
Canonical/Fact successor, foreign case/taxpayer, different run output, or
projection mutation is rejected.

The filing component carries field-level provenance for filing instance,
destination, taxpayer identity, period status, declarant category and signer.
Its aggregate evidence is explicitly owner-composed and is not labelled as a
single user-owned fact.

## Prohibitions

No PDF reread, Gate 3 financial/LLM runtime, SQL, LLM calculation, declaration-specific calculator, second
assembler, authority registry, workflow framework, inferred source fact,
case-hash taxpayer surrogate, partial XML, or FNS submission is permitted.

## Product readiness states

- `INPUT_REQUIRED`: a calculation/scope-critical user fact is missing; no
  calculated result and no XML are claimed.
- `DRAFT_READY`: the existing assembler's pre-XML preview has produced the
  calculation, while fill-only facts remain a typed checklist; no Package,
  release, projection or XML is built.
- `DECLARATION_XML_READY`: all real required values are current, the official
  XML has no placeholders, and XSD plus semantic reconciliation pass.
