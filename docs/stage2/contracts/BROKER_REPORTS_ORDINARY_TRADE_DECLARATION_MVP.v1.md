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
| taxpayer workflow scope | `primary_taxpayer_scope_ref` owned by product composition | opaque stable user+case slot; the selected period stays a separate Human Fact/scope dimension; the slot is neither INN nor taxpayer identity and is not caller-selectable |
| selected tax period | `Gate5HumanGapClosureRuntime` fact `selected_tax_period` | owner-published request in the reserved pre-period `0000` scope; `0000` itself is never a valid answer; a correction is an immutable same-lane successor before any declaration profile is resolved |
| observed operation period | `Gate5DeterministicSourceFactConsumptionRuntime.assemble_available` | exact years/dates from source-bound Fact roles; not a document-period or evidence-horizon completeness claim |
| exact year profile and mode | `Gate5TrustedMethodologyAuthorityFactory.create`, the full-target XML projection Definition owner, plus Human Fact `profile_mismatch_mode` | profile absence is decided only from the Definition owner's available profile identities; methodology/source failures retain their exact blocker; only alignment of selected year, methodology and form/KND/order/format/XSD permits filing XML; mode correction is a same-lane successor in the selected-year scope |
| position/source/tax state | deterministic source-fact consumer | position quantities, source completeness and tax activation are separate fields; open groups cannot erase independent closed calculations |
| taxpayer identity | `Gate5HumanGapClosureRuntime` fact `taxpayer_identity` | current request-bound `USER_ATTESTED_CASE_FACT`; an exact Canonical value is only a candidate until confirm/change |
| current Canonical document scope and operation coverage | active Canonical pointers plus `OrdinaryTradeProjectionRuntime.current_case_coverage` | every active Canonical manifest must have exactly one current projection bound to the same document/version/root; a missing whole projection or any `RELEVANT_UNMAPPED` observation blocks XML |
| current broker facts | `Gate4OrdinaryTradeCandidateRuntimeFactory.create` | exact case-bound Fact v2 set and disposal fact ID, consumed only after Canonical coverage passes |
| human declaration choices/facts | `Gate5HumanGapClosureRuntime` | current request-bound facts with exact user, case, taxpayer, period and publication-lane binding; stale/conflicting facts are rejected by that owner |
| public chat interaction | maintained bundled `Pipe.pipe` plus the representation-only declaration chat adapter | native OpenWebUI `__event_call__` binds one browser response to the current owner request inside the same server call; no request ref, fact key or hidden action is caller-selectable |
| capacity, inspection code, signer, filing instance/date and OKTMO | `Gate5HumanGapClosureRuntime` | current user-attested facts; missing fill-only values permit draft but never XML |
| source party and exact applicability assertions | existing `Gate3MetadataSourceFactRuntime` source owner | exact labels from Canonical versions named by current coverage; ambiguity or absence is a source blocker; no LLM or financial Gate 3 execution |
| legal/methodology version, applicability, KBK and declarant category | `Gate5TrustedMethodologyAuthorityFactory.create` | repository resource identity/SHA-256 and exact pinned rules |
| Fact -> Operation -> Category -> Tax Base | existing source, Tax Model and aggregation owners | owner-produced hashes and input/member bindings |
| Scope -> Package -> release -> projection | existing declaration owners | owner replay plus exact adjacency validation |
| XML/XSD representation | `Gate5FullTargetXmlProjectionRuntimeFactory.create` | deterministic bytes, official XSD conformance, and representation-only extraction of serialized literals; no rate or tax formula |
| released semantics -> serialized XML values | `Gate5DeclarationSemanticInputRuntimeFactory.create` | exact equality between extracted numeric fields and owner-produced released values |
| active persistence | `OrdinaryTradeDeclarationMvpRuntime` through the existing ArtifactStore | private XML and MVP receipt artifacts |
| downloadable file delivery | native OpenWebUI `Storage` plus `Files` | deterministic private Files identity binds authenticated user, case hash, current receipt and XML hashes; each physical upload attempt has a distinct path, exact existing bytes/record are verified and reused, and only an unowned losing/failed attempt is removed |

Caller supplies only `ArtifactAccessContext` and canonical artifact refs to the
production root. Caller cannot supply a taxpayer ref, disposal fact ID,
methodology version, Scope, Package, released values, projection, or receipt.
The selected tax period and unsupported-profile mode are accepted only as
current request-bound Human Facts; Pipe parameters and free chat text do not
select them.

Period/profile preparation runs for every Canonical-complete security case,
including purchase-only and partially blocked cases. It does not wait for a
closed disposal. The source consumer still owns position and calculation; the
declaration adapter only composes its result with current Human/profile state.

## Supported case

- explicitly selected tax period 2025 with the exact published 2025
  methodology/form/XSD profile; initial declaration only; individual resident whose external
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

An exact source-labelled negative exchange assertion such as `NOT_ADMITTED` is
still a source fact; it is not dropped as if the label were absent. The trusted
product methodology rejects that assertion with
`gate5_ordinary_trade_product_source_evidence_unresolved`. Resource/hash/rule
failures likewise keep their own methodology reason and never become an
unsupported-year choice.

Before a Human fact is persisted, `declaration_date` must be a real calendar
date and a 12-digit taxpayer INN must pass both control-digit checks. An invalid
answer leaves the current request active. Explicit date/INN correction is an
immutable successor publication in the existing Human semantic lane; it is not
an overwrite or a second fact owner.

## Persistence and replay

The wire XML is stored as Base64 inside private
`broker_reports_ordinary_trade_declaration_xml_v1`; its SHA-256 is over the
original official `windows-1251` bytes. The maintained OpenWebUI composition
also publishes those exact bytes through the authenticated private File owner.
The file ID is deterministic for authenticated user, case scope, receipt hash
and XML hash. Before reuse, Files metadata, owner, stored-byte hash and binding
metadata are checked. A sequential retry therefore performs no second upload
or record insertion. Concurrent identical calls may both upload because native
Files/Storage do not expose a shared atomic create-if-absent operation; their
physical attempt paths are distinct, the losing insert revalidates the winning
owner record and deletes only its own attempt, and both callers return the one
valid deterministic file ID. A different corrected receipt/XML gets a
different file. Storage bytes are deleted after a failed insert only when no
valid owner record claims that exact attempt.
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

- `INPUT_REQUIRED` with `selected_tax_period`: detected operation years are
  shown, but no year or profile is inferred and no XML is possible.
- `INPUT_REQUIRED`: a calculation/scope-critical user fact is missing; no
  calculated result and no XML are claimed.
- `DRAFT_READY`: the existing assembler's pre-XML preview has produced the
  calculation, while fill-only facts remain a typed checklist; no Package,
  release, projection or XML is built.
- `DECLARATION_XML_READY`: all real required values are current, the official
  XML has no placeholders, and XSD plus semantic reconciliation pass.
- `ANALYSIS_ONLY_READY`: an explicitly selected unsupported year retains
  owner-produced operation/position calculations and a final note; no filing
  eligibility, release, projection, XML or download is claimed.
- `NON_FILING_SURROGATE_READY`: a distinct structured preview names the
  Definition-owned available profile, selected/profile years and mismatch,
  fills current source/position/calculation fields, lists owner-bound
  placeholders/checks, and carries an explicit non-filing warning; no official
  XML/download is created and no alternate XML serializer is called.
- `STOPPED_RESUMABLE`: the exact case remains persisted and resumable without
  a profile substitution.
- `OPEN_POSITION_RETAINED`: source-proven open position evidence is retained;
  absence of a closing event is not reported as a source-completeness failure.
- `ANALYSIS_READY_WITH_OPEN_ITEMS`: independent closed calculations are kept
  while exact unresolved groups remain blocked from filing.

Every preparation state includes `broker_reports_ordinary_trade_case_note_v1`.
It projects, without re-deciding, the selected period, observed operation
years, exact profile identity, open position states, owner-produced calculated
disposals, remaining checks and actual release eligibility. Profile
availability and release eligibility are distinct: even an exact 2025 profile
does not make a draft or open position filing-eligible.

The no-Canonical branch is included in that rule. It reports source
completeness as `CANONICAL_EVIDENCE_MISSING`, position evaluation as
`NOT_EVALUATED_SOURCE_FACTS_UNAVAILABLE`, no detected/selected period, and
profile support as `NOT_EVALUATED_SOURCE_COVERAGE_INCOMPLETE`. It must not
relabel an extraction boundary as an open position, period mismatch, or
unsupported declaration profile.
