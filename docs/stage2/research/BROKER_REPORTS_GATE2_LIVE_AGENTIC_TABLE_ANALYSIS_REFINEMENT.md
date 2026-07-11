# Broker Reports Gate 2 Live Agentic Table Analysis Refinement

Date: 2026-07-11

Status: live proof passed for one real native normalized-table row and one real PDF normalized-table row.

## Scope

This note covers only:

```text
normalized table projection
-> bounded Gate 2 package
-> deterministic source-unit route
-> single domain extractor
-> provider-native strict JSON Schema
-> deterministic validator/stitcher
```

It does not cover Gate 3, ledgers, tax, declaration mapping, XLS/XLSX, OCR/VLM,
page rendering, Knowledge/RAG/vector search, whole-document extraction, or a
semantic PDF table-truth claim.

## Research answers

1. The clearest real native target is a medium-quality HTML cash-movement
   table: one selected data row, six cells, and one deterministic
   `cash_movement` route.
2. The clearest real PDF target is a high-quality reconstructed cash-movement
   table: one selected data row, three selected cells, and one deterministic
   `cash_movement` route.
3. The native row has sufficient context in the visible date, operation
   description, currency, and separate credit/debit amount columns. The PDF row
   has sufficient structural amount/currency context.
4. A semantic router is not required for either selected target. Each route has
   one selected row, one model candidate, and exactly one typed domain.
5. One selected row plus its ordered headers/cells is sufficient. No neighboring
   data row or whole table is required.
6. Exact decimal/currency normalization, source-value reproduction, stable ids,
   audit constants, issue policy, ownership, and coverage remain deterministic.
7. The finalizer may bind package/document/unit scope, source location,
   whitelisted evidence, issue/audit/restriction fields, and common value
   objects.
8. The LLM decides whether the selected row is the allowed typed fact or
   `unknown_source_row`, selects the movement subtype, and selects which
   package-provided value candidate belongs to the typed field.
9. A mixed table must first be partitioned into disjoint row groups. No mixed
   table was required for this single-domain vertical.
10. Limited expansion requires a validator-passed typed fact, strict
    provider-native output without fallback, private raw/fact persistence,
    complete conflict-free stitch, zero uncovered refs, and zero
    Knowledge/RAG/vector/document deltas.

## Failure attribution and refinement

The original native failure was not a model transport or storage failure.
Composite source headers were conservatively projected as `unknown`, leaving
only currency as an exact deterministic candidate. The model then emitted
date/amount strings that the strict validator could not reproduce exactly.

The refinement keeps the validator unchanged:

- native composite cash headers are mechanically normalized for future
  projections;
- for the existing projection, every mechanically reproducible decimal cell in
  the bounded `cash_movement` row is retained as an amount candidate;
- the model selects among candidates rather than inventing a normalized value;
- the package-bound provider schema permits only candidate values/refs and
  forces fields without an exact candidate to null/empty;
- the finalizer may bind a missing ref only when the model selected one unique
  exact candidate value;
- raw model output remains private and the unchanged validator re-resolves the
  source-value ref/checksum before acceptance.

This preserves semantic responsibility: deterministic code offers exact
choices; the LLM chooses the business-relevant one.

## Live result

Case: `customer_case_group_002_process_false_gate1_20260711124118`.

Native proof:

- source format: HTML;
- quality: medium;
- domain: `cash_movement`;
- model: `gpt-5.6-sol`;
- run: `sfdrun_cccfd45bf3dbe1b298f13235`;
- typed facts: `cash_movement=1`;
- accepted/rejected packages: `1/0`;
- selected/owned/uncovered/conflict: `1/1/0/0`;
- validation errors: none;
- raw outputs: one strict private output, no fallback.

PDF regression proof on the same deployed bundle:

- source format: PDF;
- quality: high;
- domain: `cash_movement`;
- model: `gpt-5.6-sol`;
- run: `sfdrun_3bcfffa3d028c3f4ef1d7292`;
- typed facts: `cash_movement=1`;
- accepted/rejected packages: `1/0`;
- selected/owned/uncovered/conflict: `1/1/0/0`;
- validation errors: none;
- raw outputs: one strict private output, no fallback.

Both runs produced zero file/document/Knowledge/vector deltas and performed no
tax, declaration, consolidation, or XLS/XLSX work.

## Expansion boundary

Limited expansion is safe only for the same bounded topology:

- `prefer_table_projections=True`;
- one complete parent unit and one selected row window;
- one deterministic domain;
- package-bound exact value candidates;
- provider-native `response_format=json_schema`, `strict=true`;
- private raw output and validated facts;
- terminal validator and stitch checks;
- no Gate 3 work.

Broad mixed-table fan-out remains deferred until a suitable two-domain table is
selected and proven. Its absence is not a blocker for this completed
single-domain slice.
