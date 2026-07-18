# Broker Reports Single PDF Whole-Document Gate 2 E2E

Date: 2026-07-12

Status: `BROKER_REPORTS_SINGLE_PDF_E2E_PARTIAL`.

This proof processes one approved real broker PDF as a complete document through
the production global Gate 1 / Gate 2 path. Historical `Gate 1.5` references
mean only the metadata-passport compatibility sub-stage inside Gate 1. This
proof is intentionally scoped to
source-visible Gate 2 facts and coverage accounting. It does not run Gate 3,
cross-document consolidation, tax calculation, declaration mapping, XLS/XLSX
generation, OCR/VLM, or image-only transcription.

## Selected document boundary

Selected source: approved `case_group_002`, `source_ordinal=12`.

Selection reason:

- text-layer parent payload was complete;
- PDF layout coverage was complete;
- table candidates and line clusters were present;
- source units could be deterministically windowed without parent remainder;
- no OCR/VLM/RAG/vector path was needed.

Safe preparation counts:

| Metric | Count |
| --- | ---: |
| PDF pages | 6 |
| Usable text-layer pages | 6 |
| Partial/image-only pages | 0 |
| High table candidates | 14 |
| Line clusters | 6 |
| Gate 1 normalized source units | 20 |
| Normalized table projection artifacts | 14 |
| Gate 2 selected source units | 17 |
| Gate 2 selected normalized table projection units | 6 |
| Gate 2 selected fallback/full-source units | 11 |

## Orchestration behavior

The document was processed through deployed OpenWebUI Functions and repository
factories:

```text
process=false private intake
-> Gate 1 normalization
-> PDF text-layer/layout source units
-> normalized table projections plus fallback full-source units
-> domain context packet
-> Gate 2 input readiness
-> deterministic source-unit segmentation
-> domain package builder
-> live broker_reports_gate2_domain_source_fact_pipe
-> strict structured output
-> candidate binding validation
-> source-fact validation
-> deterministic stitch
-> private document extraction packet
```

The canonical provider run used one provider consistently:

- provider profile: `google_gemini`;
- model: `models/gemini-3.1-flash-lite`;
- adapter: `gemini_response_format`;
- structured output mode: `openwebui_response_format_json_schema`;
- response format: `json_schema`;
- repair attempts: `0`;
- hidden failover: `false`.

## Document-level coverage semantics

Every selected source ref is accounted into one of the Gate 2 terminal buckets:

- typed source-fact ownership;
- `unknown_source_row`;
- deterministic/model no-fact;
- rejected package/fact;
- explicit conflict;
- uncovered after validation/stitch;
- deferred/blocked source unit when present.

For this run, package/window partitioning itself was complete:

| Metric | Count |
| --- | ---: |
| Parent selected refs | 2489 |
| Derived accounted refs | 2489 |
| Duplicate parent refs | 0 |
| Unaccounted parent refs | 0 |
| Truncated source units | 0 |
| Pending parent remainders | 0 |
| Bounded windows | 116 |
| Model calls/packages | 175 |

Execution produced a private packet:

- document extraction packet ref: `art_560TBYfqv851r1MN0Gz9JLIrkrFMQ-ES`;
- normalization run: `normrun_99b36819b646dd60`;
- domain context packet ref: `art_D_9suS4GUshIzlg5v6s2SWa-HHihjIZH`.

## Analytical result

All 116 windows were executed and persisted, but the result is partial.

| Metric | Count |
| --- | ---: |
| Windows executed | 116 / 116 |
| Windows passed all strict terminal checks | 26 |
| Domain packages processed | 175 |
| Domain packages accepted | 55 |
| Domain packages rejected | 120 |
| Raw model calls passed | 124 |
| Raw model calls failed | 51 |
| Source fact refs | 55 |
| Validated source fact refs | 55 |
| Domain source fact refs | 55 |

Accepted source-fact types:

| Fact type | Count |
| --- | ---: |
| `cash_movement` | 1 |
| `unknown_source_row` | 16 |

Coverage result:

| Coverage bucket | Count |
| --- | ---: |
| Selected refs | 2489 |
| Typed fact owned refs | 1 |
| Unknown refs | 16 |
| No-fact refs | 297 |
| Conflict refs | 0 |
| Uncovered refs | 2175 |

Provider execution aggregates:

| Metric | Value |
| --- | ---: |
| Provider calls | 175 |
| Provider duration total | 655122 ms |
| Runtime wall time | 4209.349 s |
| Input tokens reported | 4584773 |
| Output tokens reported | 79902 |
| Total tokens reported | 4664675 |
| Calls with token usage | 124 |

The 51 provider errors were all `document_summary_evidence` calls through
Gemini strict JSON schema mode. Provider returned HTTP 400 with the message:
`Request contains an invalid argument.` No tokens or finish reason were reported
for those calls.

Top blocker classes:

- provider-specific Gemini strict-schema rejection for
  `document_summary_evidence`;
- candidate-binding/source-fact validation gaps, especially missing provenance
  and missing required semantic roles;
- high uncovered coverage caused by rejected packages and validation failures.

## Guards and restrictions

| Guard | Result |
| --- | --- |
| Ordinary processed upload | not used |
| OpenWebUI Knowledge/RAG | not used |
| Vector delta | zero |
| Document rows delta | zero |
| File rows delta | zero during Gate 2 |
| Knowledge rows delta | zero |
| OCR/VLM | not used |
| Gate 3 case assembly / Gate 4 tax-declaration-output | not run |
| OpenWebUI core patch | not used |

## Product verdict

The current pipeline is ready for further bounded single-document testing, but
not ready for a limited multi-document case proof yet.

The important positive result is that whole-document packaging, windowing,
private persistence, provider identity, no-RAG/no-vector guards, resumability,
and document-level packet persistence work on a real complete PDF.

The blocking result is that full document-level source-fact coverage was not
proven. Gemini Flash-Lite rejected all `document_summary_evidence` strict-schema
requests, and the accepted fact set is too sparse to treat this as a successful
document extraction.

Recommended next proof:

1. Run a focused diagnostic on `document_summary_evidence` with a schema-safe
   provider/profile or a narrower Gemini-compatible schema projection.
2. Keep candidate-binding validation strict; do not weaken validators to raise
   acceptance.
3. Re-run this same single-PDF proof only after provider/schema behavior is
   fixed or explicitly changed.
4. Move to multi-document only after one representative PDF reaches complete or
   acceptably bounded document coverage.
