# Broker Reports Gate 5 Human Fact Scope v1

Status: `CURRENT; ACTIVE FOR THE BOUNDED ISSUE #304/#310 PRODUCT ROUTE`

Issues: `#299`, review follow-up `#301`, product activation `#304`, product
surface gate `#310`

Date: 2026-08-24

## Boundary and owner

`Gate5HumanGapClosureRuntimeFactory.create` is the single owner of Human
request meaning, authenticated-answer normalization, typed fact publication,
current-request publication, conflict detection and fact validation:

```text
authenticated context + externally supplied taxpayer scope + tax period
-> owner request content + owner current-publication chain
-> authenticated answer
-> owner-published typed fact
-> exact owner validation
```

The implementation reuses `ArtifactStorePort` and `ArtifactResolver`. It adds
no registry, workflow/event engine, identity authority, receipt engine or
domain provider/LLM path. Issue #310 adds a separate presentation-only model
call for final dialogue wording outside this owner; it cannot interpret,
publish or validate a Human Fact.

## Scope and the product taxpayer slot

The immutable fact scope contains authenticated user, case, independent
`taxpayer_scope_ref`, four-digit tax period and a canonical scope hash. Run ID
is deliberately excluded so a valid fact can replay in a later run. Workspace
ID remains an ArtifactStore ACL boundary, not fact meaning.

The Human owner validates mechanical equality of the taxpayer scope across
request, fact and consumer. The Issue #304/#308 composition mints exactly one opaque
`primary_user_attested_taxpayer` slot from authenticated user and case.
The caller cannot choose it. It is workflow scope only: it is not an INN,
taxpayer identity, operation subject or claim that the portal authenticated a
taxpayer.

Issue #308 keeps tax-period choice separate from that stable taxpayer slot. A
single `selected_tax_period` request is published in reserved scope period
`0000`, which means only "selection not yet incorporated into a tax scope" and
must never reach methodology, calculation, release or XML. It is rejected as
a Human answer even though it remains valid inside the owner's scope contract.
The answer is an exact non-sentinel four-digit year. All later facts use the selected real year in their
ordinary Human scope. If the detected operation-year set changes, the owner
publishes a successor in the same semantic lane and the former selection fact
becomes stale; the caller cannot preserve an old evidence view by selecting a
parallel lane.

When the trusted methodology owner has no exact profile for the selected year,
the same Human owner publishes `profile_mismatch_mode` in that real-year scope.
Its closed values are `ANALYSIS_ONLY`, `SURROGATE_DRAFT` and
`STOP_RESUMABLE`. They are product-mode choices only and cannot authorize a
wrong-year declaration release or XML.

The mode request also binds the exact current owner-produced
`selected_tax_period` fact ref in its subject. Current-publication validation
replays that dependency against the neutral-scope period lane. Any period
successor therefore makes the dependent mode request and fact stale even if
the caller later returns to the same year (`2022 -> 2025 -> 2022`); a fresh
mode publication and answer are required.

Both `selected_tax_period` and `profile_mismatch_mode` use the same immutable
owner-produced correction mechanism as the other product facts. The successor
is cloned from the current owner request, binds
`change_of_user_case_fact_ref`, remains in the original semantic lane and real
scope (`0000` only for period selection, the selected year for mode), and
makes the old request/fact stale. The caller supplies only the fact key exposed
by the bounded product action and cannot choose the lane, scope or predecessor.

The mismatch question receives the available profile descriptions only from
the existing full-target projection Definition owner. Display text may change,
but it cannot create a profile or authorize release. The owner-produced public
label contains the form, tax year and electronic format version; internal
profile IDs and XSD names are not user vocabulary. The representation-only chat
adapter validates and displays the exact owner-produced labels and may not
replace them with a generic question that hides the available profile.

Issue #310 exposes period correction only through the bounded Russian phrase
`Изменить налоговый период: ГГГГ`. The adapter validates a non-sentinel
four-digit year and asks the existing Human owner to publish the successor; it
does not accept a caller request ref, semantic lane or fact key. Therefore the
public chat preserves the existing `2022 -> 2025 -> 2022` currentness proof and
cannot resurrect the former profile-mode choice.

Actual identity exists only as the current `taxpayer_identity` Human fact with
provenance `USER_ATTESTED_CASE_FACT`. A Canonical INN/FIO assertion is a private
candidate and has no identity authority until the user chooses confirm or
change on the current owner publication. `DEFER` creates no fact.

For the Issue #304/#310 product route, the bundled Pipe obtains that publication
from the Human owner and keeps its `request_publication_ref` on the server. The
representation-only adapter strips the request down to one public question,
safe answer help, human labels and a masked candidate. For an exact public
owner form it delegates directly to the current owner. For a free-form answer
it makes one bounded conversation-model call over only that public context and
the current reply. The strict result is `CLARIFY | CANDIDATE`, visible wording,
one proposed public answer and an exact evidence quote. It cannot supply or
select a publication ref, fact key, taxpayer scope or hidden action. The Pipe
replays a candidate against the current owner answer shape and vetoes direct
negation, but this still creates no fact. The user must explicitly confirm the
displayed interpretation through native OpenWebUI `__event_call__`, or provide
the exact owner form on a later bound turn. Only then may the already selected
current publication pass Human owner normalization. Refusal, ambiguity,
invalid model output, owner mismatch or missing confirmation leaves the
request current and creates no fact.

## Public dialogue context and presentation model

The cross-domain map for the Issue #310 seam is:

```text
current request, outcome and filing eligibility
-> existing domain owners in OrdinaryTradeProductionRuntime
-> ordinary_trade_public_dialogue_context_v1 (representation only)
-> authenticated native OpenWebUI completion endpoint -> presentation model
-> validated visible wording or deterministic human fallback

natural user reply + current public question
-> one bounded presentation-model call -> CLARIFY or public CANDIDATE
-> current owner answer validation -> explicit confirmation, still no fact
-> native confirmation or later exact owner-form reply
-> exact current request_publication_ref kept by Pipe
-> Gate5HumanGapClosureRuntime normalization and publication
```

The model-facing context contains only human-readable summary statements,
provenance labels, the one current question, allowed human actions, the next
step and filing/download booleans. It contains no raw request/artifact refs,
fact keys, owner names, reason codes, internal statuses, source rows or
methodology identifiers. Final private download URLs are appended by the Pipe
after validation and are never model-produced.

The presentation model returns either strict structured dialogue wording for
an initial/status turn or one strict
`broker_reports_ordinary_trade_public_interpretation_v1` answer proposal. A
proposal contains exactly `CLARIFY | CANDIDATE`, one short human-facing
interpretation or clarification, a normalized public answer and a verbatim
evidence quote. The model does not supply the contract version: the runtime
owns and adds it after strict shape validation. It cannot choose a request identity,
publish a fact or bypass the current owner's answer validation. The visible
confirmation is composed by the runtime from the validated short model message,
the exact normalized public value and the deterministic owner-context renderer;
therefore the model is neither a second owner renderer nor responsible for
copying owner statements. The composed message must retain every owner-produced
public statement and the exact current question. Internal vocabulary, positive filing claims when filing is not
eligible, private file URLs, unknown fields, non-verbatim evidence and
unconfirmed candidates fail closed. One conversation turn cannot make a
second presentation call: after interpretation, any post-confirmation state is
rendered from the new owner context deterministically. Model failure creates no
new meaning and no Human Fact; a call that exceeds its bounded runtime window
is treated as unavailable instead of holding the current request open.

The native completion target is an administrator-pinned HTTPS OpenWebUI origin,
never `request.base_url`, Host or another caller-derived address. Redirects are
denied and the response body is byte-bounded before JSON parsing. The incoming
user bearer token cannot be forwarded to a caller-selected or redirected
origin.

Metrics are separate: `presentation_llm_calls_total` counts the single bounded
conversation call used for either rendering or free-answer interpretation;
`domain_provider_calls_total` remains zero for the deterministic ordinary-trade
calculation, tax, release and XML path.

The former `gate5_case_taxpayer_scope_ref` case hash is removed. Hashing a case
ID only obfuscated the case and silently invented a one-taxpayer invariant.
The former case-hash helper and the authenticated-identity-provider surrogate
remain forbidden. Cross-user/case/workspace/period/slot use fails closed.

## Current request publication

Request content remains content-addressed. A separate immutable
`broker_reports_gate5_gap_request_publication_v1` records, for one semantic
request lane:

- the owner's stable `semantic_request_key`;
- exact request content binding;
- exact Human scope, fact key and closure type;
- predecessor publication ref;
- canonical publication hash/ref.

The lane identity is exactly
`sha256({scope_binding_sha256, semantic_request_key})`. The semantic key is
minted by the Human owner, never supplied by the answer caller. Its closed
families are:

- `human_fact:<fact_key>` for USER_FACT;
- `source_gap:<sha256(reason_code, asset, currency)>` for source gaps, preserving
  the source-review owner's pre-request grouping identity;
- fixed owner keys for withholding advisory, filing destination and the
  income-source methodology decision.

`kind`, priority, question/reason text, evidence state, routing, closure type,
demand refs and display subject are request state, not lane identity. Therefore
`DEFERRED <-> REQUIRED` and display/evidence changes supersede the same lane,
while two simultaneous source meanings remain independent even when
`fact_key=None`. Timestamps, list/insertion order and artifact-ref sorting are
excluded. Before returning a plan, `publish_requests` proves that every
returned request is still the current tip; a within-plan collision fails
closed instead of returning an already-stale request.

The owner accepts exactly one complete root-to-tip chain. Missing predecessors,
branches, multiple roots/tips or cycles fail closed. `A -> A` reuses the current
publication; `A -> B -> A` creates three publications and makes the final A
current even though request content A is reused. Selection uses neither record
timestamps, insertion/list order nor artifact-ref lexical order. Old requests
and facts bind the old publication ref and become stale.

## Unambiguous facts

Each fact binds the exact request content and exact request publication. Before
acceptance, the Human owner scans all genuine owner-visible facts for the same
scope, semantic key and request publication. More than one distinct fact hash
is an unresolved conflict, so A alone, B alone, both orders and caller omission
all fail closed. Repeating the same byte-equal answer reuses one artifact and
does not create a false conflict. No timestamp or caller list order chooses a
winner.

An explicit bounded product change command asks this same owner to publish a
successor in the existing semantic lane. This includes `selected_tax_period`,
`profile_mismatch_mode`, `taxpayer_identity`, `declaration_date` and the other
closed product fact keys. The successor answer contract binds the exact fact
being replaced. The old request and old fact become stale; the correction does
not overwrite either artifact and cannot bypass cross-scope validation.

## Authority ceiling

The closed Human fact keys include the historical preparation keys plus the
bounded product keys:

```text
taxpayer_identity_confirmed
selected_tax_period
profile_mismatch_mode
taxpayer_identity
taxpayer_capacity
filing_instance_identity
filing_destination_code
signer_and_representation
budget_disposition
budget_oktmo
residency_evidence
declaration_date
ordinary_trade_declaration_zero_scope_confirmed
```

`filing_instance_identity` remains only the closed election
`INITIAL | CORRECTION`. The Issue #304 route may collect the exact inspection
code and OKTMO as explicit user-attested fill values. KBK, source
applicability, deductibility and legal classification are never Human facts.
Free text cannot smuggle
residency/tax status, source classification, deductibility or settlement into
the filing fact. Declaration Preparation consumes only readiness and does not
reinterpret the election as destination or target data.

The Human owner validates a declaration date as a real ISO calendar date and
validates both control digits of a 12-digit INN before persistence. A malformed
value creates no fact and leaves the current action repairable. XML/XSD shape
validation is not used as a substitute for these Human-fact checks.

Residency remains raw interval evidence interpreted by
`Gate5ResidencyEvidenceRuntimeFactory.create`. Additional documents return
`NORMALIZATION_REQUIRED`; external/methodology actions cannot become Human
facts. Domain calculation/provider calls remain zero; presentation calls have
the bounded authority described above and are accounted separately.

## Compatibility and activation

`broker_reports_gate5_user_case_fact_v0` is historical-readable only and is
rejected on this v1 boundary. There is no silent migration. Issue #304 activates
only interactive preparation and private XML download for the exact bounded
scenario; it does not activate FNS filing/submission or identity authentication.
