# Broker Reports Gate 2 — Financial Semantic V6 Goal 14 proof

## Terminal result

`NOT_CLOSED`

The independent Gate 3 successor consumer is implemented and proven to read
only through the Financial Domain API. Goal 14 as a whole is not accepted:
there is no accepted V6 model and Goal 13 therefore produced no authorized
actual-corpus V6 domain snapshot on which full-scope and production query
parity could be proved.

## Gate 3 domain-only consumer

`Gate3FinancialDomainContextFactory.create` is the only consumer entrypoint.
The resulting consumer calls exactly these Financial Domain API methods:

- `describe_domain`;
- `query_typed_records`;
- `query_unclassified_records`;
- `get_coverage`;
- `get_provenance`.

It validates every response, follows bounded deterministic continuation,
rejects page authority drift, continuation cycles, duplicate results,
incomplete coverage, catalog/count drift and incomplete provenance. It has no
Artifact Store, source document, Gate 1, provider, Knowledge, RAG or
filesystem dependency.

Focused verification:

```text
python -m pytest -q tests/test_broker_reports_gate2_financial_domain_query.py
24 passed
```

The deterministic domain fixture proves:

- catalog exact;
- query parity exact;
- provenance complete;
- source LLM calls `0`;
- domain LLM calls `0`.

This is consumer readiness proof, not customer/full-scope V6 activation.
The existing Artifact Store-backed `Gate3ContextManifestService` remains the
legacy read path; this goal does not silently reroute production before Goal
15 release prerequisites are met.

## Frozen baseline and proof boundary

The accepted prior shadow receipt remains preserved and hash-linked. It
records:

| Metric | Frozen accepted value |
| --- | ---: |
| selected refs | 455 |
| accounted refs | 455 |
| uncovered refs | 0 |
| duplicate interpretations | 0 |
| ownership conflicts | 0 |
| unclassified retention | 100% |

That receipt predates V6 and is not relabelled as V6 evidence. Likewise, the
accepted prior checksum remains `3/3`, but no V6 actual-corpus run repeated
that checksum.

Both authorized V6 candidate qualifications ended
`MODEL_NOT_SAFE_FOR_SHADOW`. Under the Goal 13 prerequisite, actual-corpus
execution was skipped with zero calls and zero stage mutations. Therefore:

- `GATE3_DOMAIN_ONLY`: `PASSED`;
- `FULL_SCOPE`: `NOT_RUN_NO_ACCEPTED_V6_ACTUAL_CORPUS`;
- `QUERY_PARITY`: `SYNTHETIC_EXACT_PRODUCTION_NOT_RUN`;
- `CHECKSUM`: `LEGACY_THREE_OF_THREE_NOT_V6`.

The safe machine-readable receipt is
[BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_V6_GOAL14_PROOF.receipt.safe.json](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_V6_GOAL14_PROOF.receipt.safe.json).

## Narrowest corrective slice

An explicit new exact model or policy decision is required. That candidate
must first qualify as `MODEL_SAFE_FOR_SHADOW`; only then may Goal 13 execute
once, after which the full-scope part of Goal 14 can be repeated. No provider
call, retry, fallback, repair or production mutation was introduced here.
