# Broker Reports Financial Domain Matching Method

Asset ID: `broker-reports-financial-domain-matching`

Version: `1.0.0`

Status: `managed_target_not_live`

## Authority

The exact Financial Semantic Pack returned by the managed
`broker_reports_financial_semantic_pack` Tool is the only authority for
financial type meanings, roles, distinctions, examples, counterexamples,
synonyms, and ambiguity guidance.

Do not use general model knowledge, a prompt, Python predicates, regular
expressions, supporting Knowledge, embeddings, vector search, or retrieved
documents as a second semantic authority. Knowledge may later illustrate the
method, but it must never replace, narrow, widen, or override the exact Pack.

## Required method

1. Load the full Pack through `load_financial_semantic_pack`.
2. Require Pack ID `broker_reports_managed_financial_semantic_pack`, semantic
   version `1.0.0`, and integrity SHA-256
   `ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8`.
   If any identity differs, do not make a semantic decision; the execution
   path must reject the mismatched Pack before accepting model output.
3. Read the entire supplied bounded source context. Do not decide from one
   isolated label when its section, row, column, literal, or source-group
   context is also supplied.
4. Consider only types declared by the exact Pack and only candidates and
   role/ref combinations declared structurally eligible in the bounded input.
5. Select a typed disposition only when one Pack definition is uniquely
   supported, every required role is explicitly bound, and no Pack
   counterexample or ambiguity rule applies.
6. Select `unclassified_financial_input` for source-stated financial values
   that cannot be typed safely. Preserve every supplied value through exact
   allowed refs and roles.
7. Select `no_financial_input` only when the bounded source group contains no
   source-stated financial value. Select `unsupported` only when the source
   shape or required strict contract cannot represent the operation.
8. Return exactly one JSON object conforming to
   `broker_reports_gate2_financial_evidence_decision_v1`.

## Prohibitions

- Do not invent a type, value, label, date, period, currency, unit, role, or
  source ref.
- Do not calculate, aggregate, net, convert, normalize, repair, or transform
  a missing or source-stated value.
- Do not infer a financial meaning from visual position, emphasis, adjacency,
  or a matching literal alone.
- Do not omit a source-stated financial value merely because it is ambiguous.
- Do not return confidence, reasoning, prose, provenance graphs, internal
  paths, audit metadata, or fields outside the strict decision contract.
- Do not apply Gate 3 tax, declaration, ledger, cost-basis, profit/loss,
  netting, or FX methodology.
