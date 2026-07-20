# Broker Reports Gate 2 FNS 2-NDFL and PDF parity closure

Date: 2026-07-20. Scope: Goal 2 actual-corpus source-contract closure.

## Outcome

The deterministic FNS 2-NDFL adapter and paired PDF/XML representation parity are implemented and proven on the private actual corpus. Goal 2 is closed independently of SBER holdout debt.

This is actual-corpus source readiness for the named withholding-report workflow. It is not broad PDF generalization, release approval or customer acceptance.

## Maintained route

```text
ArtifactStoreFactory.create
  -> ArtifactResolver
  -> Gate2InputReadinessFactory.create
  -> Gate2Fns2NdflAdapterFactory.create
  -> Gate2Fns2NdflParityFactory.create
  -> terminal typed/parity validation
```

Gate 1 remains neutral. Gate 2 consumes existing XML event refs and bounded PDF source units. It neither rereads source bytes nor mints source identity. Unknown FNS profiles and material contradictions fail closed; no LLM/provider fallback exists.

## Actual-corpus evidence

The committed safe proof is `BROKER_REPORTS_GATE2_FNS_2NDFL_ACTUAL_CORPUS.v1.safe.json`. It contains only counts, opaque digests and safety flags.

| Check | Result |
| --- | ---: |
| Neutral FNS XML units | 24 |
| Observed structural variants | 17 |
| Typed outputs / deterministic replays | 24 / 24 |
| Typed source facts | 351 |
| Paired PDF/XML groups | 24 |
| Preserved PDF candidates | 180 |
| Income/deduction candidates | 33 |
| Tax-summary candidates | 33 |
| Non-withheld-tax candidates | 33 |
| Other form/heading candidates | 81 |
| Unmatched material errors | 0 |
| PDF candidates canonicalized | 0 |
| Provider calls / tokens / cost | 0 / 0 / 0 |
| ArtifactStore mutation | none |

All 180 PDF candidates remain addressable. Recovery is explicitly deferred under validated paired-XML coverage; source identities are neither merged nor deleted.

## Canonical readiness integration

The read-only actual persisted run reports 24 typed packages, 24 reconciled pairs and 180 deferred PDF candidates with `artifactstore_unchanged=true`.

Its overall readiness remains failed only because the persisted DCP predates the Goal 1 ZIP-lineage fix:

- `gate2_source_ready_document_memory_blocked`: 24;
- `gate2_source_ready_document_has_no_private_slice`: 4;
- `gate2_source_ready_documents_not_packageable`: 1 aggregate error.

A fresh full normalization in Goal 4 is required to replace that stale graph. These errors are not parity failures.

## Verification

```text
python -m pytest tests/test_broker_reports_gate2_fns_2ndfl_parity.py tests/test_broker_reports_gate2_fns_2ndfl_adapter.py tests/test_broker_reports_gate2_input_readiness.py tests/test_broker_reports_gate1_archive_xml_visual_v1.py -q
26 passed

python scripts/prove_fns_2ndfl_actual_corpus.py --actual-config <ignored-local-config> --safe-output <safe-proof>
all 14 acceptance checks passed

python -m ruff check --ignore E402 <Goal-2 changed Python files>
All checks passed
```

The parity test suite covers forward and reverse matches, permitted presentation equivalence, contradictions, missing reverse/cardinality coverage, wrong document scope and tamper rejection.

## Readiness statement

- Actual readiness: proven for all 24 paired FNS 2-NDFL documents in this corpus.
- Generalization: limited to the maintained FNS profiles and explicit representation equivalences.
- Release: still gated by the existing default-off release valve and external SBER holdout debt.
- Customer acceptance: not claimed.
