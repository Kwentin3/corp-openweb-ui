# Broker Reports G3.4D-LIVE exact-model execution preflight

Status: `BLOCKED_EXTERNAL`

Date: 2026-08-07

## GOAL_STATUS

`G3.4D-LIVE = BLOCKED_EXTERNAL`.

The one authorized execution attempt stopped at the exact-model publication
check with terminal error `exact_model_not_published`. The frozen script checks
the OpenWebUI catalog before constructing the submission counter or executing
either predeclared provider call. Therefore provider submissions were zero and
the acceptance requirement `provider submissions > 0` was not met.

## WHAT_WAS_ACHIEVED

- Reproduced both frozen document/chunk shapes through the existing canonical
  reader, structural chunker and dictionary owners before transport.
- Executed exactly one model-availability preflight for provider profile
  `google_gemini` and exact model `models/gemini-3.5-flash`.
- Classified the result at the contract-required external stop boundary.

No live labeling claim was produced.

## WHAT_WAS_REUSED

- the frozen G3.4D two-call plan;
- `CanonicalReaderFactory`-backed artifact access;
- `Gate3StructuralChunkFactory`;
- `Gate3FinancialLabelDictionaryFactory` and published dictionary `1.0.0`;
- the existing `Gate3ChunkBatchLabelingFactory` and
  `Gate2StructuredModelClientFactory` route;
- the strict existing response schema and validator.

## WHAT_WAS_ADDED

- this privacy-safe terminal report;
- one eight-file exact preflight evidence set outside Git.

No implementation, schema, contract, dictionary, validator, chunker, adapter,
database, registry, cache or fallback path was added.

## WHAT_WAS_NOT_NEEDED

- provider/model substitution;
- retry or repeated catalog polling;
- alias repair or normalization;
- a model-discovery subsystem;
- G3.5 persistence work;
- G3.6 workflow work;
- G3.7 end-to-end work.

## ACCEPTANCE_EVIDENCE

| Requirement | Result |
| --- | --- |
| provider submissions > 0 | `FAIL: 0` |
| previous compact case validated | `NOT_RUN` |
| large-chunk regression pass | `NOT_RUN` |
| strict bare alias demonstrated live | `NOT_PROVEN` |
| alias repair layer | `NONE` |
| dictionary injection exactly once | `PREPARED_NOT_SUBMITTED` |
| chunker unchanged | `PASS` |
| dictionary unchanged | `PASS` |
| validator unchanged | `PASS` |
| complete real document proven | `NOT_PROVEN` |

The exact-model check and terminal error are at
`services/broker-reports-gate1-proof/scripts/live_gate3_strict_alias_closeout.py:327`.
The submission counter is created only afterward at line 334 and incremented
only inside the completion boundary at line 342.

## RAW_EVIDENCE

Execution command used the frozen script with:

- explicit `--execute-strict-alias-live-reproof` authorization;
- a new external private-evidence directory;
- a separate in-repository safe-receipt destination.

Terminal process evidence:

```text
exit_code = 1
terminal_error = exact_model_not_published
provider_submissions = 0
```

External private preflight evidence summary:

```text
files = 8
bytes = 734743
aggregate_sha256 = 40554227cf601551ad6de01998dcd3947d544f5f217d87a04040d4d402f5347a
frozen_plan_sha256 = d56bec5c5970571b1b0fd616c22cda5dbc85a1204a9709ceee42c9de8e40bc00
store_tree_before_sha256 = 00c52459979ee2c20d3d3e2f32c766a17f3fb500d1ad4aba817c5e1e059ac0be
private_evidence_committed = false
```

The aggregate hash is SHA-256 over sorted relative-path/file-hash pairs. The
frozen script did not emit its success-path safe receipt because execution
stopped before transport, as required.

## KNOWN_LIMITATIONS

- Model publication is a point-in-time external catalog fact.
- There is no final model-visible request, raw provider output or validated
  live annotation result because no submission occurred.
- Earlier local contract proof remains valid but cannot satisfy this live
  acceptance requirement.

## OBSERVATIONS

This result is consistent with the previously observed intermittent model
catalog publication. It is evidence of an external availability blocker, not
evidence that a new Gate 3 model-management component is needed.

## KISS_CHECK

`PASS`.

The attempt reused the sole existing route, performed one required preflight,
made no retry, changed no closed contract and stopped immediately at the named
external blocker. No second owner or speculative infrastructure was created.

## BLOCKING_OBSERVATIONS

`models/gemini-3.5-flash` was not published in the authenticated OpenWebUI
model catalog at the authorized execution preflight.

## AUTO_CONTINUE

`NO`.

## NEXT_GOAL

`NONE` in this autonomous run. G3.5 is forbidden until G3.4D-LIVE reaches full
PASS; the same G3.4D-LIVE proof may be reconsidered only after exact-model
availability and a new execution decision.
