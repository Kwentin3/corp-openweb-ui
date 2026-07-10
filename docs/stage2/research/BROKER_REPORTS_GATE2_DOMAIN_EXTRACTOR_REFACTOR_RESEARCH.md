# Broker Reports Gate 2 Domain Extractor Refactor Research

Date: 2026-07-10

Status: implementation-grounded research complete.

## 1. Decision

The broad Gate 2 extractor remains a compatibility and synthetic path. It is
not the preferred customer path when domain routing is available.

The real-case path is:

```text
validated domain_context_packet_v0
  -> deterministic source-unit router
  -> broker_reports_source_unit_domain_route_v0
  -> narrow broker_reports_domain_extraction_package_v0 packages
  -> one managed structured-output Prompt per extractor domain
  -> unchanged strict source-fact validator in domain mode
  -> validator-passed broker_reports_source_facts_v0
  -> deterministic stitcher and coverage validator
  -> broker_reports_source_fact_stitch_result_v0
```

This narrows the model task without weakening schema, provenance, source-value,
issue, privacy, lifecycle, or coverage validation.

## 2. Evidence reviewed

The refactor is grounded in the current Gate 1/Gate 2 code, source-unit
provenance factory, ArtifactStore/resolver, DCP/DUC/issue contracts, Gate 2
input-readiness audit, broad-extractor research/blueprint/contracts, and the
2026-07-10 implementation report.

The input-readiness proof established that `case_group_002` has 15 source-ready
documents and 37 packageable source units with 1,598 selected row/segment refs
and 2,232 source-value refs. That was input availability, not extraction proof.

The controlled broad primary batch then produced 3/3 rejected packages, 0
accepted fact sets, 6 private raw outputs, and these error totals across initial
and repair attempts:

| Validator code | Count |
| --- | ---: |
| `source_fact_provenance_missing` | 66 |
| `source_fact_completeness_overstated` | 14 |
| `source_fact_coverage_gap` | 5 |
| `source_fact_issue_not_carried` | 4 |
| `source_fact_missing_field` | 1 |

All selected real source slices were also marked truncated. Therefore the old
run cannot establish full-document or Gate 3 readiness even if a bounded unit
later passes.

## 3. Why the broad extractor failed

The broad prompt asked one call to do five different jobs over heterogeneous
rows:

1. classify every row/segment into one of nine fact types;
2. choose and reproduce exact evidence/source-value refs;
3. populate a large discriminated union with type-specific required fields;
4. copy deterministic issue impact and conservative completeness state;
5. reconcile every selected ref as fact or an allowed no-fact result.

The strict validator correctly rejected outputs when any job drifted. The
failure is therefore useful evidence of task overload, not evidence that the
validator should be relaxed.

### 3.1 Prompt/task overload findings

- Completeness was overstated because the model had to interpret unresolved
  issue impact while simultaneously extracting values.
- Issue refs were omitted because document/unit issue carry-forward competed
  with fact construction in a wide schema.
- Coverage gaps occurred because one call had to reconcile headers, blanks,
  layout rows, facts of many types, and unknown rows.
- Missing type-specific fields occurred because the model selected a union
  branch and filled it in the same step.
- Wide provider schemas increased the number of legal-looking but semantically
  invalid completions.

### 3.2 Package/provenance-shape findings

The broad package did contain stable refs, but it exposed all refs for the
whole bounded unit. The model had to discover the relevant row, then the cells,
then matching value refs, and construct a full source location. This is valid
but unnecessarily difficult.

The domain package now contains only candidate rows/segments. Its private
normalized projection, model projection, row/cell/segment provenance,
source-value index, allowed evidence refs, and allowed source-value refs are
physically narrowed together. Original ordinals and opaque refs remain stable;
private payload paths used for mechanical value reproduction are deterministically
re-indexed inside the narrow package.

## 4. Responsibility split

| Responsibility | Deterministic runtime/finalizer | LLM extractor |
| --- | --- | --- |
| source-ready selection | yes | no |
| row/segment route candidates | yes | no |
| primary suggested domain | yes | no |
| final ownership/conflict | yes | no |
| allowed fact-type set | yes | no |
| evidence/value/issue whitelist | yes | no |
| prompt/schema/model audit constants | yes | copy exact schema-bound values |
| stable package/set/fact ids | yes | `pending` placeholder only |
| source location scope constants | schema-bound/deterministic | select allowed row/cell/segment refs |
| issue impact arrays and forbidden assumptions | schema-bound/deterministic | copy only |
| normalized value reproduction | deterministic validator | select one allowed value ref and proposed normalized value |
| domain-specific fact interpretation | no | yes, within one domain |
| no-fact versus domain fact for a candidate | validator-checked | yes |
| unknown coverage classification | finalizer-checked | yes, as `unknown_source_row` |
| tax/profit/loss/declaration/XLS | forbidden | forbidden |

Audit/provenance fields may be filled or constrained by code only when the
value is already bound by the package, route, prompt snapshot, source-unit
provenance, or ArtifactStore ref. The finalizer never invents a source ref or
source value.

## 5. Safe routing signals

The router uses only package-local signals:

- existing exact `fact_type_hint`;
- normalized safe header descriptors and per-cell header labels;
- exact visible operation/category helper labels;
- non-content value kinds such as decimal-like, ISO-date-like, visible currency
  code, identifier-like, blank, or text;
- passport document kind;
- DUC usage modes;
- DCP/issue refs;
- row/segment provenance and coverage class.

Regex is limited to token normalization and value-kind hints. It is not a
source-of-record fact parser. No external knowledge, RAG, OCR/VLM, or raw file
inspection is introduced.

An exact fact-type hint has the highest score. Distinct visible labels are
secondary signals. Generic headers such as `operation`, `amount`, `currency`,
or `date` do not independently force a fact domain. Ties within the bounded
threshold produce at most two ordered candidates. No signal produces the
unknown fallback.

## 6. Ownership, ambiguity, and unknowns

Every selected ref gets exactly one route entry.

- Header/blank/layout refs are deterministically owned as no-fact coverage and
  are not sent to a model.
- A high-confidence row goes to one primary domain extractor.
- An ambiguous row may go to at most two candidate extractors.
- An unclassified row goes to `unknown_source_row_extractor`.
- No v0 multi-fact rule is enabled.

The stitcher considers only validator-passed outputs. One typed claim owns the
row. More than one typed claim creates an explicit conflict and no silent
owner. A typed claim plus unknown claim selects the typed claim by policy. One
or more unknown claims collapse to one coverage-preserving unknown owner.
No-fact claims are accepted only under the domain coverage contract. Missing
validator-passed claims remain uncovered.

This is deterministic fan-in. The LLM never decides final ownership.

## 7. Issue propagation

Issue authority remains Gate 1's issue ledger and DCP.

1. The broad readiness package derives unit/document issue context.
2. The router copies only issue refs, not new issue conclusions.
3. Every domain package carries the same applicable issue context and exact
   allowed issue-ref set.
4. Provider schema binds package issue refs and deterministic impact arrays.
5. The unchanged validator rejects omitted or changed issue linkage and rejects
   overstated completeness.
6. The stitch result aggregates fact/issue links without resolving issue state.

## 8. Smallest useful real vertical

The safe first real target is one primary document, one table source unit, and
the one or two domains with the strongest exact route signals. Required success
conditions are:

- at least one validator-passed `broker_reports_source_facts_v0`;
- every selected ref in that unit is fact-owned, unknown, no-fact, or explicit
  conflict (with success requiring no uncovered refs and no conflicts);
- zero provenance-missing, issue-not-carried, completeness-overstated, and
  coverage-gap findings in the accepted output;
- rejected raw attempts remain private;
- zero ordinary upload, document, Knowledge, RAG, or vector delta.

The runtime defaults to one document and one source unit. Primary expansion is
allowed only after this vertical is terminal, conflict-free, fully covered, and
validator-passed. Non-primary remains withheld.

## 9. Implementation slices

- `gate2_domain_routing.py`: deterministic route contract, signals, candidates,
  fallback, and factory.
- `gate2_domain_packages.py`: physically narrow private packages and factory.
- `gate2_domain_contracts.py`: managed Prompt registry, domain schema
  projection, and domain source-facts wrapper.
- `gate2_domain_finalization.py`: package-bound pre-validation finalizer for
  deterministic scope, provenance, issue/audit/restriction fields and exact
  header/mechanical value candidates; it cannot create a fact or choose its
  type.
- `gate2_source_fact_validation.py`: unchanged validator families plus explicit
  domain allowed-fact-type enforcement and domain package artifact support.
- `gate2_source_fact_stitching.py`: deterministic ownership, conflict,
  unknown/no-fact, issue-linkage, coverage, and summary.
- `gate2_domain_runtime.py`: ArtifactStore orchestration and terminal result.
- `broker_reports_gate2_domain_source_fact_pipe.py`: production OpenWebUI
  adapter; no prompt body and no business rules.

The broad runtime remains intact for compatibility/synthetic comparison. The
new domain Pipe is the intended customer route when the managed domain Prompts
are installed.

## 10. Research outcome

The architecture answers all ten research questions and is implemented in
small explicit boundaries rather than a generic agent framework. The
unknown-only real vertical proves the live runtime boundary and complete
selected-unit coverage. The remaining evidence gate is a smallest real typed
non-fallback unit: all real slices are truncated and the safe preflight found
no complete one/two-typed-domain target. Case expansion and Gate 3 therefore
remain blocked.

Status: `GATE2_DOMAIN_EXTRACTOR_RESEARCH_READY`.
