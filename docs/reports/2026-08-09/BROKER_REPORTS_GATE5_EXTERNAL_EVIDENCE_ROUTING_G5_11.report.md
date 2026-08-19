# Broker Reports Gate 5 — External Evidence Routing (G5.11)

Date: 2026-08-09

Goal status: `G5.11_CLOSED`

Proof outcome: `PROVEN`

Architecture verdict: `BOUNDED_EXTERNAL_EVIDENCE_SEAM_WORKS`

Product status: `INACTIVE`

## Verdict

Да. Gate 5 способен отделить missing tax input от Financial Case, направить
его в targeted authoritative research и получить отдельный source-bound
Reference Fact без расширения смысла брокерского документа и без
преждевременного вопроса пользователю.

Доказанный минимальный seam:

```text
closed declaration-required input
-> Gate 4 source audit
-> external route decision
-> minimal agent-visible research projection
-> agent research over official sources
-> structured claim + exact evidence bytes
-> deterministic acceptance
-> external_authoritative_evidence fact
```

Positive proof принят. Non-authoritative и conflicting proposals отклонены без
факта. Gate 4 и ArtifactStore остались byte/logically unchanged. Persistence,
Tax Model и применение ставки не добавлялись.

## Data-origin audit and candidate selection

### Preferred candidate: organized-market status

G5.10 показал, что для classification ценных бумаг нужен organized-market
status. Но текущий representative Financial Case содержит:

```text
financial_type = SECURITY_DISPOSAL
date = 2025-02-11
asset = ACME
quantity = 1
amount = 100.00
currency = RUB
unit_price = 100.00
```

`ACME` — synthetic asset label. В current representative case нет ISIN,
ticker+issuer binding или иного стабильного identifier. Gate 2 contract умеет
представлять source-visible identifiers, но они не присутствуют в этом
Financial Case и не входят в Gate 4 disposal roles.

Следовательно:

```text
document proves: asset label = ACME
document does not prove: external instrument identity
document does not prove: organized-market status
```

Lookup `ACME -> instrument -> organized-market status` был бы недоказуемым
entity matching. Candidate получает `UNRESOLVED` и не используется для
positive proof.

### Selected candidate: 2025 group-02 rate schedule

Выбран реально необходимый G5.10 input:

```text
resident securities-income group 02 rate schedule
for tax period 2025
```

Origin classification:

| Question | Finding |
| --- | --- |
| Financial Case asserts it? | No. Gate 4 facts describe financial history, not tax rate tables. |
| Source-visible identifier required? | No instrument identifier; closed entity is jurisdiction RU + period 2025 + resident individual + income group 02. |
| Externally resolvable? | Yes, from the official FNS order/filling procedure. |
| Human/case-only fact? | No. A user is not authority for the official rate table. |
| Methodology-derived? | The rate table itself is external Reference Data; applying it to a case is methodology-derived. |

This selection is declaration-driven, not chosen because current code already
contains the values.

## Official research authority

The research agent used only primary FNS sources:

1. [FNS Order dated 20.10.2025 No. ЕД-7-11/913@](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/)
   establishes the form, procedure and format and states in item 3 that it
   applies starting with the declaration for tax period 2025.
2. [Appendix 2 — official filling procedure](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_2.docx)
   states in Section V, paragraph 48 that for income-group code `02` tax is
   13% when line 060 is at most 2.4 million RUB, otherwise 312 thousand RUB
   plus 15% of the excess.

Search snippets, blogs and model memory were not evidence. The agent used them
only, if encountered, for navigation and returned the official source URLs and
exact downloaded-byte hashes.

## Closed required input

```json
{
  "schema_version": "broker_reports_gate5_external_evidence_requirement_v0",
  "requirement_id": "ru-ndfl-2025-group-02-rate-schedule",
  "fact_key": "resident_securities_income_group_rate_schedule",
  "entity": {
    "jurisdiction": "RU",
    "tax_period": "2025",
    "income_group_code": "02",
    "taxpayer_status": "resident_individual"
  },
  "declaration_binding": {
    "form": "3-NDFL",
    "knd": "1151020"
  }
}
```

The G5.11 runtime accepts no other fact, group, period or declaration target.
This is intentionally not a generic reference query.

## Minimal seam

Implemented owner:

- [G5.11 contract](../../stage2/contracts/BROKER_REPORTS_GATE5_EXTERNAL_EVIDENCE_ROUTING.v0.md)
- [`Gate5ExternalEvidenceRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_external_evidence.py)
- [behavior tests](../../../services/broker-reports-gate1-proof/tests/test_broker_reports_gate5_external_evidence.py)

The factory composes `Gate4FinancialCaseRuntimeFactory.create`. It does not
read broker reports, CanonicalArtifact, Gate 3 targets or Gate 4 SQL.

### Prepare

`prepare(requirement, context)`:

1. validates the one closed requirement;
2. reads current Financial Case through Gate 4;
3. records `required_fact_status = not_asserted` and a fact-set hash;
4. returns `route = external_authoritative_research`;
5. emits a minimal research request and its canonical SHA-256.

If a future Gate 4 fact unexpectedly contains a tax-reference role with this
name, the boundary fails with `gate5_external_evidence_gate4_semantic_drift`
rather than silently treating external meaning as document provenance.

### Agent-visible payload

Exact top-level keys seen by the agent:

```json
[
  "effective_context",
  "entity",
  "required_fact",
  "required_output",
  "research_question",
  "schema_version",
  "source_policy"
]
```

Representative semantic payload:

```json
{
  "research_question": "Установить официальную шкалу НДФЛ для группы доходов 02 налогового резидента РФ за налоговый период 2025.",
  "required_fact": {
    "fact_key": "resident_securities_income_group_rate_schedule",
    "value_kind": "progressive_rate_schedule"
  },
  "entity": {
    "jurisdiction": "RU",
    "tax_period": "2025",
    "income_group_code": "02",
    "taxpayer_status": "resident_individual"
  },
  "source_policy": {
    "allowed_authority_kinds": [
      "official_legal_publication",
      "tax_authority_primary"
    ],
    "allowed_hosts": [
      "nalog.gov.ru",
      "publication.pravo.gov.ru",
      "www.nalog.gov.ru"
    ],
    "fallback_to_model_memory": false,
    "fallback_to_search_snippet": false
  }
}
```

Not model-visible:

```text
ACME
Financial Case payload
user_id / case_id / normalization_run_id
fact_id / artifact refs
Supplemental Facts
full Tax Methodology
G5.10 report
conversation history
```

### Structured proposal and evidence bytes

The agent returns strict
`broker_reports_gate5_external_evidence_proposal_v0`:

```text
request hash
+ claim(entity, value)
+ evidence refs(authority, URL, document id, locator, effective period, hash)
+ conflicts/unresolved state
```

Evidence bytes are supplied separately as immutable Python `bytes`. The LLM
does not mint their SHA-256. The validator recomputes it.

### Deterministic acceptance

Ordinary code checks:

- closed schema and exact request hash;
- fact/entity equality with the request;
- HTTPS authority host/class policy;
- exact evidence URL/document/hash binding;
- actual downloaded-byte SHA-256;
- effective-period coverage for 2025;
- claim-value and effective-period support;
- absence of conflicts;
- Decimal shape and mechanical threshold consistency.

The validator deliberately does not implement a second legal NLU. Semantic
extraction remains the agent proposal; authority remains the bound official
evidence.

## Live positive proof

The agent downloaded the two official sources to an OS temporary directory
outside Git and submitted a structured proposal. Actual evidence bindings:

| Evidence | Bytes | SHA-256 | Supports |
| --- | ---: | --- | --- |
| FNS order page | 72303 | `eda1ce4985e45d32660b2c3a942da1fc790a81de8873a8f2bfe0d0141c717af5` | applicability/effective period |
| FNS filling procedure DOCX | 106008 | `7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc` | group-02 claim value |

Runtime result:

```json
{
  "status": "accepted",
  "route": "external_authoritative_research",
  "research_request_sha256": "58994b0e4e06c1a8456fb3d3966202c7a07d34f5127637ec2a57d05f74ed1dd9",
  "external_fact_ref": "g5ext_c3fe9627707d39aa7f9a1d9b49ee0f75",
  "value": {
    "kind": "progressive_rate_schedule",
    "currency": "RUB",
    "threshold_amount": "2400000.00",
    "lower_rate_percent": "13.00",
    "amount_at_threshold": "312000.00",
    "excess_rate_percent": "15.00"
  },
  "source_kind": "external_authoritative_evidence",
  "persistence": "not_persisted_g5_11"
}
```

Repeated acceptance through a newly created runtime with the same request,
proposal and evidence bytes returns the same deterministic fact/result.

An independent redownload showed that the FNS HTML page can return different
transport bytes while keeping the same visible official content; the DOCX hash
remained stable. G5.11 therefore claims exact replay only for the captured
evidence snapshot, not stable identity across fresh HTML acquisitions. This is
one reason persistence/publication is deliberately left as a later authority
decision.

## Fail-closed proof

### Non-authoritative source

A proposal bound to `https://example.com/tax-rate` with matching supplied bytes
was rejected:

```json
{
  "status": "rejected",
  "errors": [
    "evidence_source_not_allowed",
    "evidence_support_incomplete"
  ],
  "external_fact": null
}
```

### Conflicting values

A proposal carrying a second conflicting schedule was rejected with:

```text
conflicting_evidence_values
```

An open-ended evidence period instead of the exact requested 2025 snapshot was
rejected with `evidence_effective_period_mismatch`.

### Unresolved

`action = unresolved` with no claim produces `status = unresolved` and
`external_fact = null`. A mismatched request hash changes this to `rejected`.

None of these paths writes a Supplemental Fact or another artifact.

## Anti-drift and provenance proof

The live run recorded:

```text
Financial Case required fact status = not_asserted
Gate 4 before == Gate 4 after = true
ArtifactStore records before == after = true
```

Accepted provenance is:

```text
source_kind = external_authoritative_evidence
evidence_class = externally_verified_reference
derived_tax_conclusion = false
```

It is not:

```text
financial_case
supplemental_fact
methodology_derived
```

## Evidence acquisition vs Tax Methodology

Boundary found:

```text
official evidence:
group 02 for resident / period 2025 has schedule S

Tax Methodology:
case facts/context belong to group 02
and schedule S must be applied to tax base B
```

G5.11 produces only the first statement. It does not select group `02` for a
specific disposal, calculate a base or tax, or map an instrument to operation
code `01`.

```text
Broker Document ──X──> official rate or market status

External Fact ──X──> case tax conclusion
                     without Tax Methodology
```

## Evidence Routing Matrix

This matrix tests the classification over known G5.10 gaps. It is not a new
ontology or implementation plan.

| Required fact | Document/source evidence? | Externally resolvable? | Human/case fact? | Derived by methodology? | Current verdict |
| --- | --- | --- | --- | --- | --- |
| disposal amount/date/currency | Yes, Gate 4 typed roles | No external lookup needed | No | No | `SOURCE_EVIDENCE_FACT / AVAILABLE` |
| acquisition cost missing from supplied documents | Not in current disposal fact; may exist in other documents | Generally no safe public lookup | Yes, with user/case evidence | Expense eligibility is derived later | `USER_CASE_FACT / G5.3` |
| organized-market status for `ACME` | Only label `ACME`; no stable identifier | In principle yes, but not for this ambiguous entity | A user assertion alone is insufficient authority | Mapping the property to operation category is derived | `UNRESOLVED / BLOCK` |
| taxpayer residency and IIS applicability | Not broker-document authority | Not reliably discoverable as public reference | Yes, trusted taxpayer/case context | Applicability follows methodology | `USER_CASE_CONTEXT / MISSING_OWNER` |
| resident group-02 2025 rate schedule | No | Yes, official FNS order/procedure | No | Applying it to a case is derived | `EXTERNAL_REFERENCE_FACT / PROVEN` |
| operation code `01` for the declaration | Not a source fact | Code table is externally available | Case supplies IIS/operation context | Yes: property/context -> declaration category | `REFERENCE + METHODOLOGY` |
| allowable expense total | Components may be document/user facts | Legal sources define rules, not this case value directly | Evidence components may be case facts | Yes, eligibility and aggregation | `METHODOLOGY_DERIVED / NOT_MODELLED` |
| payer/source identity for Appendix 1 | Document fact only if stated | Unsafe to infer from security identity alone | May require case evidence | Grouping/projection is derived | `SOURCE_OR_USER_CASE / MISSING` |

## Human-in-the-loop fallback

If authoritative research cannot prove the selected official rate schedule,
the calculation must remain blocked. This fact is **not** a G5.6-style human
question: the user is not the authority for an official tax rate/effective
period.

For a user-owned fact such as acquisition cost, G5.6 remains appropriate. For
organized-market status without a stable identifier, the correct next action
is to obtain stronger instrument evidence/identifier, not ask the user for an
unverified boolean.

No fallback orchestration is implemented.

## Persistence decision

G5.11 proves semantics and deterministic replay from the same exact evidence
bytes. It deliberately does not persist the external fact.

G5.3 is not reused because:

```text
user_provided_supplemental
!=
externally_verified_reference
```

If a later calculation requires cross-runtime replay without re-supplying the
official bytes, a separate minimal persistence/authority decision will be
needed. Current repository authority may be a candidate, but G5.11 does not
prejudge or implement it.

## Validation evidence

PowerShell execution context:

```text
python -m pytest -q tests/test_broker_reports_gate5_external_evidence.py --tb=short
5 passed

Gate 5 G5.2-G5.8 + G5.11 + gate architecture contour
57 passed
```

The first run had one test-only expected/actual mismatch:

```text
expected test fixture date: 11.02.2025
actual contract-normalized date: 2025-02-11
```

The assertion was corrected to the established Gate 4 ISO normalization; no
runtime behavior was weakened.

The complete historical service suite contains `3006` collected tests. A full
`python -m pytest -q --tb=short` run reached the external 15-minute command
limit (`exit 124`) without a terminal pytest summary and without an assertion
traceback. It is therefore neither claimed green nor attributed to G5.11; the
terminal proof for this slice is the focused 57-test contour above.

## KISS check

Added:

- one local runtime/factory;
- one closed response schema and deterministic validator;
- one contract, one test file and this report;
- no persistence.

Not added:

- generic web research agent/browser/search framework;
- provider route, retry or fallback;
- Reference Data service, registry, DB, table, cache or scheduler;
- Knowledge Graph/RAG;
- Tax Context/Tax Model/XML;
- Human routing workflow;
- Gate 4 enrichment or new financial label.

## Final answer and stop condition

**Да:** Gate 5 может определить один declaration-required input как externally
resolvable, дать агенту минимальный research projection и принять отдельный
Reference Fact только при наличии authoritative evidence, exact entity/effective
binding и совпадающих hashes фактических bytes.

Proof не приписывает внешний смысл брокерскому документу, не спрашивает
пользователя об официальной ставке и не превращает найденный reference fact в
налоговый вывод без Tax Methodology. `G5.11_CLOSED`; следующий Gate 5 slice не
начат.
