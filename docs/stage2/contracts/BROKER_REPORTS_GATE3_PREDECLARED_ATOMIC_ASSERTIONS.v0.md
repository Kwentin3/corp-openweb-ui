# Broker Reports Gate 3 Predeclared Atomic Assertions v0

Status: `REJECTED INACTIVE EXPERIMENT`

Goal: `G5.92`

Date: 2026-08-17

## Authority and boundary

This document preserves the exact rejected G5.92 candidate for audit and
replay. It is not current Gate 3 authority. Current production remains the
two-pass route owned by `Gate3ChunkBatchLabelingFactory.create`, with pass 1
owned by `Gate3BoundedLabelingFactory` and current Dictionary/Role Pack
defaults unchanged.

The candidate is an additive method of the existing pass-1 owner:
`Gate3BoundedLabelingFactory.create_from_predeclared_assertions`. It consumes
an exact `Gate3StructuralChunkFactory` chunk, reuses the existing row aliases,
Dictionary loader and `Gate2StructuredModelClientFactory` provider path, and
does not persist or activate its result.

## Candidate contract

Deterministic code enumerates every table-row target already present in the
chunk. The existing bare alias is both `assertion_id` and `source_target_ref`;
no second target grammar or source object is minted. Each assertion carries
its exact rendered row as `local_source_text`; non-row lines form shared
structural context.

The model returns every predeclared `assertion_id` exactly once and in the
same order. Each result contains current Dictionary financial types or the
single value `UNMAPPED`. A list is retained only because the maintained Gate 3
contract permits one exact target to state more than one independent current
fact, such as a purchase/disposal plus a transaction charge. Roles, values,
normalization, relations and tax meaning are absent.

The response is closed by
[`BROKER_REPORTS_GATE3_PREDECLARED_ASSERTION_LABELING_RESPONSE.v1.schema.json`](./BROKER_REPORTS_GATE3_PREDECLARED_ASSERTION_LABELING_RESPONSE.v1.schema.json).
Validation rejects missing, unknown, duplicate or reordered assertion IDs,
unknown labels, mixed `UNMAPPED`, duplicate labels and any extra field. Raw
provider output is retained before validation outside Git.

## Qualification result

The single frozen semantic candidate classified all 303 development row
assertions in seven batch calls with zero unknown IDs, duplicate IDs or
invented objects. It preserved ordinary withholding `113/113`, true dividends
`25/25`, structural/unmapped controls `12/12` and cross-type controls `4/4`.
It classified only `26/105` source-true tax-adjustment rows correctly and
classified the other `79/105` as `DIVIDEND_INCOME`. The comparable current
whole-table baseline was `53/105`, with `52/105` wrong dividends.

The candidate therefore terminates as
`PREDECLARED_ASSERTION_SEMANTIC_RELIABILITY_INSUFFICIENT`. The pre-frozen
holdout was not opened because the required development proof failed. No
semantic retry, second prompt/model, literal rule, role binding, persistence,
production activation or downstream Gate 4/5 change is authorized.
